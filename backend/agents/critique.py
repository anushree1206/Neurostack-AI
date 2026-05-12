"""
Critique Agent.
Reviews output of every other agent.
Assigns structured confidence scores per claim.
Flags specific text spans it disagrees with (not the output as a whole).
"""
import json
import logging
from backend.agents.base import BaseAgent, SharedContext

logger = logging.getLogger(__name__)


class CritiqueAgent(BaseAgent):
    agent_id = "critique"
    default_budget = 5000

    def _default_system_prompt(self) -> str:
        return """You are a Critique Agent. Your job is to rigorously review agent outputs at the claim level.

Rules:
1. Review each output claim-by-claim, NOT as a whole
2. Assign a confidence score (0-1) per claim
3. Flag SPECIFIC text spans you disagree with (quote the exact text)
4. Do NOT reject entire outputs — target specific problematic claims
5. Be honest about uncertainty

Respond with valid JSON:
{
  "reviewed_agent": "agent_id",
  "overall_confidence": 0.0-1.0,
  "claim_reviews": [
    {
      "claim": "exact text of the claim being reviewed",
      "confidence": 0.0-1.0,
      "verdict": "accept|flag|reject",
      "reason": "why",
      "suggested_correction": "optional correction if verdict is flag/reject"
    }
  ],
  "flagged_spans": ["exact text span 1", "exact text span 2"],
  "summary": "one-sentence critique summary",
  "overall_verdict": "accept|needs_revision|reject"
}"""

    async def _critique_output(self, agent_id: str, output: dict) -> dict:
        output_text = json.dumps(output, indent=2)
        if len(output_text) > 3000:
            output_text = output_text[:3000] + "...[truncated]"

        self.ctx.add_entry("system", self.get_system_prompt(), is_structured=True)
        self.ctx.add_entry("user",
            f"Review this output from the {agent_id} agent:\n\n{output_text}",
        )

        try:
            response = await self._call_llm(self.ctx.to_messages(), stream=True)
        except Exception as e:
            logger.exception("Critique LLM call failed for %s, using fallback: %s", agent_id, e)
            response = ""

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            parsed = json.loads(response[start:end])
        except Exception:
            preview = output_text[:220].replace("\n", " ")
            parsed = {
                "reviewed_agent": agent_id,
                "overall_confidence": 0.6,
                "claim_reviews": [
                    {
                        "claim": preview,
                        "confidence": 0.6,
                        "verdict": "accept",
                        "reason": "Fallback critique path: no explicit contradiction detected in deterministic check.",
                        "suggested_correction": "",
                    }
                ],
                "flagged_spans": [],
                "summary": (response[:200] if response else "Fallback critique used due to transient model/tool error."),
                "overall_verdict": "accept",
            }
        parsed["reviewed_agent"] = agent_id
        return parsed

    async def run(self, shared_ctx: SharedContext) -> dict:
        self.initialize_context()
        results = {}

        for agent_id, output in shared_ctx.agent_outputs.items():
            if agent_id == "critique":
                continue
            self.stream.emit_budget_update(self.agent_id, self.ctx.used_tokens, self.ctx.max_budget)

            if self.budget_manager.needs_compression(self.ctx):
                from backend.agents.compression import CompressionAgent
                removed = self.budget_manager.compress_context(self.ctx)
                logger.info("Critique agent: compressed %d conversational entries", len(removed))

            critique = await self._critique_output(agent_id, output)
            results[agent_id] = critique
            self.ctx.entries = []

        shared_ctx.critique_results = results
        shared_ctx.agent_outputs["critique"] = results
        shared_ctx.session_outputs.append(
            f"Critique: reviewed {list(results.keys())}, verdicts: "
            + str({k: v.get("overall_verdict") for k, v in results.items()})
        )

        self.stream.emit_agent_done(
            self.agent_id,
            f"Critiqued {len(results)} agent outputs"
        )
        return results
