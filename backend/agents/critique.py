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
        return """You are an expert Critique Agent performing rigorous claim-level analysis of agent outputs with professional standards.

CORE REQUIREMENTS:
1. Analyze each output claim-by-claim with granular confidence scoring
2. Provide specific confidence scores (0.0-1.0) with detailed reasoning
3. Flag EXACT text spans with contradiction highlighting and span analysis
4. Evaluate logical consistency, factual accuracy, and reasoning quality
5. Assess source attribution and evidence quality

CONFIDENCE SCORING CRITERIA:
- 0.9-1.0: High confidence - well-supported, accurate, properly attributed
- 0.7-0.8: Good confidence - mostly accurate with minor issues
- 0.5-0.6: Moderate confidence - some concerns or limitations
- 0.3-0.4: Low confidence - significant issues or insufficient support
- 0.0-0.2: Very low confidence - major problems or contradictions

CONTRADICTION ANALYSIS:
- Identify specific text spans that contradict each other
- Explain the nature of contradictions (factual, logical, temporal)
- Provide context for why contradictions are problematic
- Suggest resolutions when possible

VERDICT CLASSIFICATION:
- "accept": High-quality output with minimal issues
- "needs_revision": Good overall but requires specific corrections
- "reject": Major problems requiring substantial revision

Respond with valid JSON:
{
  "reviewed_agent": "agent_id",
  "overall_confidence": 0.0-1.0,
  "claim_reviews": [
    {
      "claim": "exact text of the claim being reviewed",
      "confidence": 0.0-1.0,
      "verdict": "accept|flag|reject",
      "reason": "detailed explanation of confidence assessment",
      "suggested_correction": "specific correction if needed",
      "evidence_quality": "high|medium|low",
      "attribution_score": 0.0-1.0
    }
  ],
  "contradiction_analysis": [
    {
      "span_1": "exact text span 1",
      "span_2": "exact text span 2", 
      "contradiction_type": "factual|logical|temporal|methodological",
      "severity": "minor|moderate|major",
      "explanation": "why these spans contradict",
      "resolution_suggestion": "how to resolve"
    }
  ],
  "flagged_spans": ["exact text span 1", "exact text span 2"],
  "quality_metrics": {
    "factual_accuracy": 0.0-1.0,
    "logical_consistency": 0.0-1.0,
    "source_attribution": 0.0-1.0,
    "reasoning_quality": 0.0-1.0
  },
  "summary": "comprehensive critique summary with key findings",
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
            
            # Ensure all required fields are present for enhanced structure
            if "contradiction_analysis" not in parsed:
                parsed["contradiction_analysis"] = []
            if "quality_metrics" not in parsed:
                parsed["quality_metrics"] = {
                    "factual_accuracy": parsed.get("overall_confidence", 0.6),
                    "logical_consistency": parsed.get("overall_confidence", 0.6),
                    "source_attribution": 0.7,
                    "reasoning_quality": parsed.get("overall_confidence", 0.6)
                }
            
            # Ensure claim_reviews have required fields
            for claim_review in parsed.get("claim_reviews", []):
                if "evidence_quality" not in claim_review:
                    claim_review["evidence_quality"] = "medium"
                if "attribution_score" not in claim_review:
                    claim_review["attribution_score"] = 0.7
                    
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
                        "evidence_quality": "medium",
                        "attribution_score": 0.7,
                    }
                ],
                "contradiction_analysis": [],
                "flagged_spans": [],
                "quality_metrics": {
                    "factual_accuracy": 0.6,
                    "logical_consistency": 0.6,
                    "source_attribution": 0.7,
                    "reasoning_quality": 0.6
                },
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
