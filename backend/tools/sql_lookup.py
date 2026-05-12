"""
Structured data lookup tool: converts natural language to SQL and queries the database.
On timeout: returns timeout failure.
On empty: returns empty result.
On malformed input: returns malformed failure.
"""
import asyncio
import logging
from typing import Any
from backend.tools.base import BaseTool, ToolResult
from backend import config

logger = logging.getLogger(__name__)

SAMPLE_DATA = {
    "papers": [
        {"id": 1, "title": "Attention Is All You Need", "year": 2017, "citations": 80000, "topic": "transformers"},
        {"id": 2, "title": "BERT: Pre-training of Deep Bidirectional Transformers", "year": 2018, "citations": 60000, "topic": "nlp"},
        {"id": 3, "title": "GPT-3: Language Models are Few-Shot Learners", "year": 2020, "citations": 30000, "topic": "llm"},
        {"id": 4, "title": "Chain-of-Thought Prompting", "year": 2022, "citations": 8000, "topic": "prompting"},
        {"id": 5, "title": "ReAct: Synergizing Reasoning and Acting", "year": 2022, "citations": 4000, "topic": "agents"},
    ],
    "models": [
        {"id": 1, "name": "GPT-4", "provider": "OpenAI", "context_window": 128000, "released": 2023},
        {"id": 2, "name": "Claude 3 Opus", "provider": "Anthropic", "context_window": 200000, "released": 2024},
        {"id": 3, "name": "Gemini Ultra", "provider": "Google", "context_window": 1000000, "released": 2024},
        {"id": 4, "name": "Llama 3", "provider": "Meta", "context_window": 8000, "released": 2024},
    ],
}


async def _nl_to_sql(query: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        base_url=config.OPENAI_BASE_URL or None,
        api_key=config.OPENAI_API_KEY,
    )
    prompt = f"""Convert the natural language query to a simple SQL SELECT query.
Available tables:
- papers(id, title, year, citations, topic)
- models(id, name, provider, context_window, released)

Natural language query: {query}

Respond with ONLY the SQL query, no explanation."""
    resp = await client.chat.completions.create(
        model=config.AGENT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=256,
        stream=False,
    )
    return resp.choices[0].message.content.strip()


def _heuristic_sql(query: str) -> str:
    """Best-effort deterministic SQL fallback when LLM SQL generation fails."""
    q = query.lower()
    if any(k in q for k in ("model", "provider", "context window", "released")):
        if "openai" in q:
            return "SELECT * FROM models WHERE provider = 'OpenAI' LIMIT 5"
        if "anthropic" in q:
            return "SELECT * FROM models WHERE provider = 'Anthropic' LIMIT 5"
        return "SELECT * FROM models LIMIT 5"

    topic = None
    for t in ("transformers", "nlp", "llm", "prompting", "agents"):
        if t in q:
            topic = t
            break

    if topic:
        return f"SELECT * FROM papers WHERE topic = '{topic}' ORDER BY citations DESC LIMIT 5"
    if "recent" in q or "latest" in q or "new" in q:
        return "SELECT * FROM papers WHERE year > 2020 ORDER BY year DESC LIMIT 5"
    if "citation" in q or "most cited" in q or "top" in q:
        return "SELECT * FROM papers ORDER BY citations DESC LIMIT 5"
    return "SELECT * FROM papers LIMIT 5"


def _execute_in_memory(sql: str) -> list[dict]:
    sql_lower = sql.lower()
    if "papers" in sql_lower:
        data = SAMPLE_DATA["papers"]
    elif "models" in sql_lower:
        data = SAMPLE_DATA["models"]
    else:
        return []

    results = list(data)

    if "where" in sql_lower:
        if "topic" in sql_lower:
            topic = None
            for t in ["transformers", "nlp", "llm", "prompting", "agents"]:
                if t in sql_lower:
                    topic = t
                    break
            if topic:
                results = [r for r in results if r.get("topic") == topic]
        if "year >" in sql_lower or "year>" in sql_lower:
            results = [r for r in results if r.get("year", 0) > 2020]

    if "order by citations desc" in sql_lower or "citations desc" in sql_lower:
        results.sort(key=lambda x: x.get("citations", 0), reverse=True)

    if "limit" in sql_lower:
        try:
            limit_val = int(sql_lower.split("limit")[-1].strip().split()[0])
            results = results[:limit_val]
        except Exception:
            pass

    return results


class SqlLookupTool(BaseTool):
    name = "sql_lookup"
    timeout_seconds = 15.0

    async def _execute(self, input_data: Any) -> ToolResult:
        if not isinstance(input_data, dict) or "query" not in input_data:
            raise ValueError("input must be dict with 'query' key")

        nl_query = str(input_data["query"]).strip()
        if not nl_query:
            raise ValueError("query cannot be empty")

        try:
            sql = await asyncio.wait_for(_nl_to_sql(nl_query), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning("sql_lookup timeout while generating SQL, using heuristic fallback")
            sql = _heuristic_sql(nl_query)
        except Exception as e:
            logger.warning("sql_lookup NL->SQL failed (%s), using heuristic fallback", e)
            sql = _heuristic_sql(nl_query)

        if not sql.lower().startswith("select"):
            return ToolResult.malformed(self.name, "generated SQL must be a SELECT statement")

        try:
            rows = _execute_in_memory(sql)
        except Exception as e:
            return ToolResult(success=False, data=None, failure_mode="error", error_message=str(e))

        if not rows:
            return ToolResult.empty(self.name)

        return ToolResult(
            success=True,
            data={"nl_query": nl_query, "sql": sql, "rows": rows, "row_count": len(rows)},
        )
