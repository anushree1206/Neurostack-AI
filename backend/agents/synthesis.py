"""
Synthesis Agent.
Merges outputs from all sub-agents, resolves contradictions flagged by critique,
and produces a final answer with a provenance map.
"""
import json
import logging
from backend.agents.base import BaseAgent, SharedContext

logger = logging.getLogger(__name__)


class SynthesisAgent(BaseAgent):
    agent_id = "synthesis"
    default_budget = 6000

    def _default_system_prompt(self) -> str:
        return """You are a Synthesis Agent. You merge outputs from multiple agents into a coherent final answer.

Rules:
1. Resolve ALL contradictions flagged by the critique agent — do not surface them to the user
2. Every sentence in your final answer must have a provenance entry linking it to its source agent and chunk
3. If critique flagged a claim, either correct it or explain why it stands
4. Your answer must be complete, accurate, and self-consistent

Respond with valid JSON:
{
  "final_answer": "complete, well-written answer to the original query",
  "contradiction_resolutions": [
    {
      "conflict": "what was contradicted",
      "resolution": "how you resolved it",
      "source_kept": "which agent/claim you kept and why"
    }
  ],
  "provenance_map": [
    {
      "sentence": "exact sentence from final_answer",
      "source_agent": "agent_id",
      "source_chunk": "chunk_id or null",
      "confidence": 0.0-1.0
    }
  ],
  "quality_score": 0.0-1.0,
  "critique_agreement": true/false
}"""

    async def run(self, shared_ctx: SharedContext) -> dict:
        self.initialize_context()

        agents_summary = {}
        for agent_id, output in shared_ctx.agent_outputs.items():
            if agent_id in ("critique", "synthesis"):
                continue
            text = json.dumps(output, indent=2)
            agents_summary[agent_id] = text[:1500]

        critique_summary = {}
        for agent_id, critique in shared_ctx.critique_results.items():
            critique_summary[agent_id] = {
                "verdict": critique.get("overall_verdict"),
                "flagged_spans": critique.get("flagged_spans", []),
                "summary": critique.get("summary", ""),
            }

        chunks_text = "\n".join(
            f"[{c['chunk_id']}] {c['content'][:200]}"
            for c in shared_ctx.retrieved_chunks
        )

        context_blob = (
            f"Original query: {shared_ctx.original_query}\n\n"
            f"Agent outputs:\n{json.dumps(agents_summary, indent=2)}\n\n"
            f"Critique results:\n{json.dumps(critique_summary, indent=2)}\n\n"
            f"Retrieved chunks:\n{chunks_text}"
        )

        self.ctx.add_entry("system", self.get_system_prompt(), is_structured=True)
        self.ctx.add_entry("user",
            f"Synthesize a final answer from all agent outputs and resolve contradictions:\n\n{context_blob}",
        )

        self.stream.emit_budget_update(self.agent_id, self.ctx.used_tokens, self.ctx.max_budget)

        if not self.ctx.check_budget(1000):
            violation = "Synthesis agent approaching budget limit"
            self.stream.emit_policy_violation(self.agent_id, violation)
            logger.warning("POLICY_VIOLATION: %s", violation)

        try:
            response = await self._call_llm(self.ctx.to_messages(), stream=True)
        except Exception as e:
            logger.exception("Synthesis LLM call failed, using fallback: %s", e)
            response = ""

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            parsed = json.loads(response[start:end])
        except Exception:
            rag_output = shared_ctx.agent_outputs.get("rag", {}) or {}
            rag_answer = (rag_output.get("answer") or "").strip()
            decomposition = shared_ctx.agent_outputs.get("decomposition", {}) or {}
            subtask_count = len(decomposition.get("subtasks", []) or [])
            critique_count = len(shared_ctx.critique_results or {})

            if rag_answer:
                fallback_answer = rag_answer
            else:
                fallback_answer = (
                    f"Fallback synthesis summary: query='{shared_ctx.original_query}', "
                    f"subtasks={subtask_count}, critique_reviews={critique_count}. "
                    "Primary model synthesis was unavailable, so this answer is assembled from prior agent outputs."
                )
            parsed = {
                "final_answer": fallback_answer,
                "contradiction_resolutions": [],
                "provenance_map": [
                    {
                        "sentence": fallback_answer[:220],
                        "source_agent": "rag" if rag_answer else "synthesis",
                        "source_chunk": None,
                        "confidence": 0.7 if rag_answer else 0.55,
                    }
                ],
                "quality_score": 0.7 if rag_answer else 0.55,
                "critique_agreement": True,
            }

        shared_ctx.final_answer = parsed.get("final_answer", response)
        shared_ctx.provenance_map = parsed.get("provenance_map", [])
        shared_ctx.agent_outputs["synthesis"] = parsed
        shared_ctx.session_outputs.append(f"Synthesis: {shared_ctx.final_answer[:400]}")

        self.stream.emit_agent_done(
            self.agent_id,
            f"Synthesized final answer ({len(shared_ctx.final_answer)} chars)"
        )
        return parsed
