"""
Decomposition Agent.
Breaks ambiguous queries into typed sub-tasks with explicit dependency graphs.
Dependent sub-tasks do not execute until their dependencies resolve.
"""
import json
import logging
from backend.agents.base import BaseAgent, SharedContext
from backend.context_manager import ContextBudgetManager
from backend.streaming import SSEStream

logger = logging.getLogger(__name__)


class DecompositionAgent(BaseAgent):
    agent_id = "decomposition"
    default_budget = 4000

    def _default_system_prompt(self) -> str:
        return """You are a Decomposition Agent. Your job is to break a query into typed sub-tasks with explicit dependency graphs.

Rules:
1. Each sub-task must have: id, type (retrieval/synthesis/critique/computation/lookup), description, dependencies (list of sub-task ids that must complete first), priority (1-5)
2. Dependent sub-tasks MUST NOT be marked as executable until their dependencies resolve
3. Identify which sub-tasks are ambiguous and flag them
4. Be precise about dependencies: if task B needs the output of task A, then B depends on A

Respond with valid JSON only:
{
  "subtasks": [
    {
      "id": "t1",
      "type": "retrieval|synthesis|critique|computation|lookup",
      "description": "specific description",
      "dependencies": [],
      "priority": 1,
      "is_ambiguous": false,
      "ambiguity_note": ""
    }
  ],
  "dependency_graph": {"t2": ["t1"], "t3": ["t1", "t2"]},
  "complexity_assessment": "low|medium|high",
  "reasoning": "why you decomposed it this way"
}"""

    async def run(self, shared_ctx: SharedContext) -> dict:
        self.initialize_context()
        query = shared_ctx.original_query

        self.ctx.add_entry("system", self.get_system_prompt(), is_structured=True)
        self.ctx.add_entry("user", f"Decompose this query into sub-tasks:\n\n{query}")

        self.stream.emit_budget_update(self.agent_id, self.ctx.used_tokens, self.ctx.max_budget)

        try:
            response = await self._call_llm(self.ctx.to_messages(), stream=True)
        except Exception as e:
            logger.exception("Decomposition LLM call failed, using fallback: %s", e)
            response = ""

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            parsed = json.loads(response[start:end])
        except Exception:
            parsed = {
                "subtasks": [{"id": "t1", "type": "synthesis", "description": query, "dependencies": [], "priority": 1, "is_ambiguous": True, "ambiguity_note": "Could not parse full decomposition"}],
                "dependency_graph": {},
                "complexity_assessment": "medium",
                "reasoning": response or "Fallback decomposition used due to transient model/tool error.",
            }

        shared_ctx.decomposed_tasks = parsed.get("subtasks", [])
        shared_ctx.dependency_graph = parsed.get("dependency_graph", {})
        shared_ctx.agent_outputs["decomposition"] = parsed
        shared_ctx.session_outputs.append(f"Decomposition: {json.dumps(parsed, indent=2)}")

        self.stream.emit_agent_done(
            self.agent_id,
            f"Decomposed into {len(shared_ctx.decomposed_tasks)} sub-tasks"
        )
        return parsed
