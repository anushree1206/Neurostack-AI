"""
Self-reflection tool: lets an agent re-read its own previous session outputs
and identify contradictions.
On empty: no previous outputs to reflect on.
On malformed: bad input format.
"""
import logging
from typing import Any
from backend.tools.base import BaseTool, ToolResult
from backend import config

logger = logging.getLogger(__name__)


async def _find_contradictions(outputs: list[str]) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        base_url=config.OPENAI_BASE_URL or None,
        api_key=config.OPENAI_API_KEY,
    )
    combined = "\n\n---OUTPUT BOUNDARY---\n\n".join(
        f"[Output {i+1}]: {o}" for i, o in enumerate(outputs)
    )
    prompt = f"""You are reviewing multiple outputs from an AI agent in the same session.
Identify any factual contradictions, inconsistencies, or conflicts between these outputs.

Outputs to review:
{combined}

Respond in this exact JSON format:
{{
  "has_contradictions": true/false,
  "contradictions": [
    {{
      "output_a": 1,
      "output_b": 2,
      "claim_a": "the claim from output 1",
      "claim_b": "the conflicting claim from output 2",
      "severity": "low/medium/high"
    }}
  ],
  "summary": "brief summary of findings"
}}"""

    resp = await client.chat.completions.create(
        model=config.AGENT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=1024,
        stream=False,
    )
    raw = resp.choices[0].message.content.strip()
    import json
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return {"has_contradictions": False, "contradictions": [], "summary": raw}


class SelfReflectionTool(BaseTool):
    name = "self_reflection"
    timeout_seconds = 20.0

    async def _execute(self, input_data: Any) -> ToolResult:
        if not isinstance(input_data, dict):
            raise ValueError("input must be a dict")

        session_outputs = input_data.get("session_outputs", [])
        if not session_outputs:
            return ToolResult.empty(self.name)

        if not isinstance(session_outputs, list):
            raise ValueError("session_outputs must be a list of strings")

        if len(session_outputs) < 2:
            return ToolResult(
                success=True,
                data={
                    "has_contradictions": False,
                    "contradictions": [],
                    "summary": "Only one output available; no comparison possible.",
                },
            )

        result = await _find_contradictions(session_outputs)
        return ToolResult(success=True, data=result)
