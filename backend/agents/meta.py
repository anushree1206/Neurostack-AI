"""
Meta-Agent: Self-Improving Prompt Loop.
After each eval run, reads failure cases, identifies worst-performing prompt,
proposes a structured rewrite with diff and justification.
"""
import json
import logging
import difflib
from backend.agents.base import BaseAgent, SharedContext
from backend import config

logger = logging.getLogger(__name__)

AGENT_PROMPTS = {
    "orchestrator": "You are a master orchestrator that dynamically routes queries to sub-agents.",
    "decomposition": "You are a Decomposition Agent. Break queries into typed sub-tasks with dependency graphs.",
    "rag": "You are a Retrieval-Augmented Agent performing multi-hop reasoning.",
    "critique": "You are a Critique Agent reviewing claims at the span level.",
    "synthesis": "You are a Synthesis Agent merging outputs and resolving contradictions.",
}


class MetaAgent(BaseAgent):
    agent_id = "meta"
    default_budget = 4000

    def _default_system_prompt(self) -> str:
        return """You are a Meta-Agent responsible for improving prompts based on evaluation failures.

Your job:
1. Analyze which agent's prompt led to the worst performance on a specific scoring dimension
2. Propose a rewritten prompt that addresses the failure mode
3. Provide a structured diff and justification

Respond with valid JSON:
{
  "target_agent": "agent_id",
  "target_dimension": "scoring dimension",
  "failure_analysis": "what specifically failed",
  "original_prompt_excerpt": "the problematic part of the original prompt",
  "proposed_changes": ["change 1", "change 2"],
  "justification": "why these changes will improve performance",
  "proposed_full_prompt": "the full rewritten system prompt"
}"""

    async def analyze_failures(self, eval_results: list[dict]) -> dict:
        failed = [r for r in eval_results if not r.get("passed", True)]
        if not failed:
            failed = sorted(eval_results, key=lambda r: r.get("score_overall", 1.0))[:3]

        if not failed:
            return {"error": "No failed cases to analyze"}

        dimensions = [
            "score_correctness", "score_citation", "score_contradiction",
            "score_tool_efficiency", "score_budget_compliance", "score_critique_agreement"
        ]
        dim_scores = {d: [] for d in dimensions}
        for r in failed:
            for d in dimensions:
                v = r.get(d)
                if v is not None:
                    dim_scores[d].append(v)

        worst_dim = min(dim_scores, key=lambda d: sum(dim_scores[d]) / max(len(dim_scores[d]), 1) if dim_scores[d] else 1.0)
        worst_avg = sum(dim_scores[worst_dim]) / max(len(dim_scores[worst_dim]), 1) if dim_scores[worst_dim] else 0

        dim_to_agent = {
            "score_correctness": "synthesis",
            "score_citation": "rag",
            "score_contradiction": "synthesis",
            "score_tool_efficiency": "orchestrator",
            "score_budget_compliance": "orchestrator",
            "score_critique_agreement": "critique",
        }
        target_agent = dim_to_agent.get(worst_dim, "synthesis")

        failure_cases_text = json.dumps([
            {
                "case_id": r.get("case_id"),
                "query": r.get("query", "")[:200],
                "category": r.get("case_category"),
                worst_dim: r.get(worst_dim),
                "justification": (r.get("justifications") or {}).get(worst_dim, ""),
            }
            for r in failed[:5]
        ], indent=2)

        original_prompt = AGENT_PROMPTS.get(target_agent, "")

        self.initialize_context()
        self.ctx.add_entry("system", self.get_system_prompt(), is_structured=True)
        self.ctx.add_entry("user",
            f"Analyze these evaluation failures and propose a prompt rewrite.\n\n"
            f"Worst performing dimension: {worst_dim} (avg score: {worst_avg:.2f})\n"
            f"Target agent: {target_agent}\n"
            f"Current prompt: {original_prompt}\n\n"
            f"Failed cases:\n{failure_cases_text}"
        )

        response = await self._call_llm(
            self.ctx.to_messages(),
            stream=False,
            model=config.META_MODEL,
        )

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            parsed = json.loads(response[start:end])
        except Exception:
            parsed = {
                "target_agent": target_agent,
                "target_dimension": worst_dim,
                "failure_analysis": response[:300],
                "proposed_full_prompt": original_prompt,
                "justification": response[:200],
                "proposed_changes": [],
                "original_prompt_excerpt": original_prompt[:100],
            }

        proposed = parsed.get("proposed_full_prompt", original_prompt)
        diff = "\n".join(difflib.unified_diff(
            original_prompt.splitlines(),
            proposed.splitlines(),
            fromfile=f"{target_agent}_original",
            tofile=f"{target_agent}_proposed",
            lineterm="",
        ))
        parsed["diff"] = diff
        parsed["original_prompt"] = original_prompt
        parsed["worst_dimension"] = worst_dim
        parsed["worst_avg_score"] = round(worst_avg, 3)
        parsed["failed_case_count"] = len(failed)

        return parsed

    async def run(self, shared_ctx: SharedContext) -> dict:
        return {"status": "meta_agent_ready"}
