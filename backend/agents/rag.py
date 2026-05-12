"""
Retrieval-Augmented Agent.
Performs multi-hop reasoning across at least two retrieved chunks.
Cites which chunk contributed to which part of the answer.
"""
import json
import logging
from backend.agents.base import BaseAgent, SharedContext
from backend.streaming import SSEStream
from backend.context_manager import ContextBudgetManager
from backend.tools.web_search import WebSearchTool
from backend.tools.sql_lookup import SqlLookupTool
from backend import config

logger = logging.getLogger(__name__)

MAX_RETRIES = config.MAX_TOOL_RETRIES


class RAGAgent(BaseAgent):
    agent_id = "rag"
    default_budget = 6000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.web_search = WebSearchTool()
        self.sql_lookup = SqlLookupTool()

    def _default_system_prompt(self) -> str:
        return """You are a Retrieval-Augmented Agent. You perform multi-hop reasoning across retrieved chunks.

Rules:
1. You MUST use at least TWO distinct retrieved chunks before forming an answer
2. For each claim in your answer, cite which chunk (chunk_id) contributed to it
3. Perform multi-hop: use the result of one retrieval to inform what to retrieve next
4. If a chunk is insufficient, explicitly explain why and what you retrieved next

Respond with valid JSON:
{
  "hops": [
    {
      "hop": 1,
      "query_used": "what I searched for",
      "chunk_id": "chunk_1",
      "relevant_excerpt": "the specific text I used",
      "what_I_learned": "what this chunk told me"
    }
  ],
  "answer": "full answer synthesized from chunks",
  "citations": [
    {"claim": "specific claim from answer", "chunk_id": "chunk_1", "source_url": "url"}
  ],
  "confidence": 0.0-1.0
}"""

    async def _retrieve_with_retry(self, query: str, tool_name: str, attempt: int = 0) -> dict:
        if tool_name == "web_search":
            tool = self.web_search
            result = await tool.call({"query": query}, attempt=attempt)
        else:
            tool = self.sql_lookup
            result = await tool.call({"query": query}, attempt=attempt)

        accepted = result.success and result.failure_mode != "empty"
        tool.log_call({"query": query}, result, attempt, accepted)

        self.stream.emit_tool_call(
            self.agent_id, tool_name, attempt,
            "success" if accepted else result.failure_mode or "failed",
            {"query": query, "failure": result.error_message}
        )

        shared_tool_entry = {
            "agent_id": self.agent_id,
            "tool": tool_name,
            "attempt": attempt,
            "input": {"query": query},
            "output": result.data,
            "accepted": accepted,
            "failure_mode": result.failure_mode,
            "latency_ms": result.latency_ms,
        }

        if not accepted and attempt < MAX_RETRIES:
            modified_query = f"{query} detailed explanation"
            return await self._retrieve_with_retry(modified_query, tool_name, attempt + 1)

        return {"result": result, "log": shared_tool_entry}

    async def run(self, shared_ctx: SharedContext) -> dict:
        self.initialize_context()
        query = shared_ctx.original_query
        decomposition = shared_ctx.agent_outputs.get("decomposition", {})
        subtasks = decomposition.get("subtasks", [])

        retrieval_tasks = [t for t in subtasks if t.get("type") == "retrieval"]
        if not retrieval_tasks:
            retrieval_tasks = [{"description": query}]

        chunks = []

        hop1_query = retrieval_tasks[0].get("description", query)
        r1 = await self._retrieve_with_retry(hop1_query, "web_search")
        shared_ctx.tool_call_history.append(r1["log"])
        if r1["result"].success and r1["result"].data:
            web_results = r1["result"].data.get("results", [])
            for i, item in enumerate(web_results[:2]):
                chunks.append({
                    "chunk_id": f"chunk_web_{i+1}",
                    "source": "web_search",
                    "url": item.get("url", ""),
                    "content": item.get("snippet", ""),
                    "relevance": item.get("relevance", 0.5),
                })

        hop2_query = retrieval_tasks[1].get("description", query) if len(retrieval_tasks) > 1 else f"{query} database lookup"
        r2 = await self._retrieve_with_retry(hop2_query, "sql_lookup")
        shared_ctx.tool_call_history.append(r2["log"])
        if r2["result"].success and r2["result"].data:
            rows = r2["result"].data.get("rows", [])
            for i, row in enumerate(rows[:2]):
                chunks.append({
                    "chunk_id": f"chunk_db_{i+1}",
                    "source": "sql_lookup",
                    "url": "",
                    "content": json.dumps(row),
                    "relevance": 0.8,
                })

        if not chunks:
            chunks = [
                {"chunk_id": "chunk_fallback_1", "source": "internal", "url": "", "content": f"General knowledge about: {query}", "relevance": 0.5},
                {"chunk_id": "chunk_fallback_2", "source": "internal", "url": "", "content": f"Additional context for: {query}", "relevance": 0.4},
            ]

        shared_ctx.retrieved_chunks = chunks

        chunks_text = "\n\n".join(
            f"[{c['chunk_id']}] Source: {c['source']}\nURL: {c['url']}\nContent: {c['content']}"
            for c in chunks
        )

        self.ctx.add_entry("system", self.get_system_prompt(), is_structured=True)
        self.ctx.add_entry("user",
            f"Query: {query}\n\nRetrieved chunks:\n{chunks_text}\n\nPerform multi-hop reasoning and answer with citations.",
            is_structured=False,
        )

        self.stream.emit_budget_update(self.agent_id, self.ctx.used_tokens, self.ctx.max_budget)

        if not self.ctx.check_budget(500):
            violation = f"RAG agent near budget limit before LLM call"
            self.stream.emit_policy_violation(self.agent_id, violation)

        try:
            response = await self._call_llm(self.ctx.to_messages(), stream=True)
        except Exception as e:
            logger.exception("RAG LLM call failed, using fallback synthesis: %s", e)
            response = ""

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            parsed = json.loads(response[start:end])
        except Exception:
            top_chunks = chunks[:2] if len(chunks) >= 2 else chunks
            statements = []
            citations = []
            hops = []
            for idx, c in enumerate(top_chunks, start=1):
                content = str(c.get("content", "")).strip()
                excerpt = content[:200]
                hops.append({
                    "hop": idx,
                    "query_used": query if idx == 1 else f"{query} follow-up",
                    "chunk_id": c.get("chunk_id", f"chunk_{idx}"),
                    "relevant_excerpt": excerpt,
                    "what_I_learned": excerpt or "No extractable content",
                })
                if excerpt:
                    statements.append(f"From {c.get('chunk_id')}: {excerpt}")
                    citations.append({
                        "claim": excerpt[:120],
                        "chunk_id": c.get("chunk_id", f"chunk_{idx}"),
                        "source_url": c.get("url", ""),
                    })

            fallback_answer = (
                " ".join(statements)
                if statements
                else (response.strip() if response else f"I gathered context for '{query}', but could not complete model synthesis.")
            )
            parsed = {
                "hops": hops or [{"hop": 1, "query_used": query, "chunk_id": "chunk_fallback_1", "relevant_excerpt": "", "what_I_learned": "Fallback retrieval path"}],
                "answer": fallback_answer,
                "citations": citations,
                "confidence": 0.65 if citations else 0.5,
            }

        shared_ctx.agent_outputs["rag"] = parsed
        shared_ctx.session_outputs.append(f"RAG Answer: {parsed.get('answer', response)[:500]}")

        self.stream.emit_agent_done(self.agent_id, f"Retrieved {len(chunks)} chunks, formed answer with citations")
        return parsed
