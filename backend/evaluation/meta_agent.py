"""
Self-Improving Prompt Loop Meta-Agent

Reads failure cases, identifies worst-performing prompts, proposes rewrites.
Stores proposals for human approval and tracks performance deltas.
"""

import json
import time
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging
from backend.evaluation.storage import EvaluationStorage
from backend.evaluation.evaluator import EvaluationScore
from backend.agents.base import BaseAgent, SharedContext
from backend.streaming import SSEStream
from backend import config

logger = logging.getLogger(__name__)

@dataclass
class PromptRewrite:
    """Proposed prompt rewrite with metadata"""
    rewrite_id: str
    run_id: str
    test_id: str
    agent_type: str
    old_prompt: str
    new_prompt: str
    diff_summary: str
    justification: str
    status: str  # 'pending', 'approved', 'rejected'
    performance_delta: Optional[float] = None
    created_at: float = field(default_factory=time.time)

class MetaAgent(BaseAgent):
    """Meta-agent for self-improving prompts"""
    
    agent_id = "meta_agent"
    default_budget = 4000
    
    def __init__(self, storage: EvaluationStorage):
        super().__init__(
            budget_manager=None,  # Will be set in run()
            stream=None,  # Will be set in run()
            job_id="meta_analysis"
        )
        self.storage = storage
        self._client = None  # Lazy-load client
    
    @property
    def client(self):
        """Lazy-load OpenAI client"""
        if self._client is None:
            self._client = self._make_openai_client()
        return self._client
    
    def _default_system_prompt(self) -> str:
        """Default system prompt for meta-agent analyzing failures"""
        return """You are a meta-agent responsible for improving prompts based on failure analysis.

Your role:
1. Analyze patterns in failing test cases
2. Identify which agent prompts contributed to failures
3. Propose targeted rewrites that address the root causes
4. Provide clear justification for each proposed change

Guidelines:
- Focus on the worst-performing dimensions first
- Propose specific, actionable improvements
- Maintain consistency with the agent's role
- Consider edge cases identified in failures
- Keep prompts concise but comprehensive"""
    
    def _make_openai_client(self):
        from openai import AsyncOpenAI
        return AsyncOpenAI(
            base_url=config.OPENAI_BASE_URL or None,
            api_key=config.OPENAI_API_KEY,
        )
    
    async def analyze_failure_patterns(self, run_id: str) -> Dict[str, Any]:
        """Analyze failure patterns across all test cases"""
        # Get evaluation summary for the run
        history = await self.storage.get_evaluation_history(limit=5)
        current_run = None
        for run in history:
            if run["run_id"] == run_id:
                current_run = run
                break
        
        if not current_run:
            return {"error": "Run not found"}
        
        # Analyze worst performing dimensions
        worst_performing = self._identify_worst_performing(current_run)
        
        return {
            "run_id": run_id,
            "analysis_timestamp": time.time(),
            "worst_performing_dimensions": worst_performing,
            "total_tests": current_run.get("total_tests", 0),
            "overall_average": current_run.get("overall_average", 0),
            "recommendations": self._generate_recommendations(worst_performing)
        }
    
    def _identify_worst_performing(self, run_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Identify worst-performing prompts by dimension"""
        categories = run_summary.get("category_breakdown", {})
        dimension_averages = run_summary.get("dimension_averages", {})
        
        worst_performing = {}
        
        # Find worst performing in each category
        for category, test_cases in categories.items():
            if not test_cases:
                continue
                
            # Find worst performing test in this category
            worst_test = None
            worst_score = float('inf')
            
            for test_id in test_cases:
                # Get individual test score (would need to query database)
                # For now, use category average as proxy
                category_avg = dimension_averages.get("answer_correctness", 0)
                if category_avg < worst_score:
                    worst_score = category_avg
                    worst_test = test_id
            
            if worst_test:
                worst_performing[category] = {
                    "test_id": worst_test,
                    "dimension": "answer_correctness",
                    "score": worst_score,
                    "category_average": dimension_averages.get("answer_correctness", 0)
                }
        
        # Find worst performing overall
        worst_overall = run_summary.get("worst_performing", "")
        if worst_overall:
            worst_performing["overall"] = {
                "test_id": worst_overall,
                "dimension": "overall_score",
                "score": run_summary.get("overall_average", 0),
                "category_averages": dimension_averages
            }
        
        return worst_performing
    
    def _generate_recommendations(self, worst_performing: Dict[str, Any]) -> List[str]:
        """Generate specific recommendations for prompt rewrites"""
        recommendations = []
        
        for category, worst in worst_performing.items():
            if worst["score"] < 0.5:  # Poor performance threshold
                if category == "adversarial":
                    recommendations.append(
                        f"Adversarial test {worst['test_id']}: Implement explicit input validation and "
                        f"system prompt hardening. Current score: {worst['score']:.3f}"
                    )
                else:
                    recommendations.append(
                        f"{category.title()} test {worst['test_id']}: Add more specific instructions "
                        f"and examples. Current score: {worst['score']:.3f}"
                    )
        
        # General recommendations
        if any(worst["score"] < 0.6 for worst in worst_performing.values()):
            recommendations.append(
                "Consider implementing few-shot examples to improve performance"
            )
            recommendations.append(
                "Review and tighten system prompts for clarity"
            )
        
        return recommendations
    
    async def propose_rewrite(self, run_id: str, test_id: str, agent_type: str) -> PromptRewrite:
        """Propose a specific prompt rewrite for a failing test case"""
        
        # Get the original prompt that failed
        original_prompt = await self._get_original_prompt(agent_type)
        if not original_prompt:
            raise ValueError(f"Could not find original prompt for agent type: {agent_type}")
        
        # Analyze the failure pattern
        failure_analysis = await self._analyze_failure_pattern(run_id, test_id, agent_type)
        
        # Generate rewrite using LLM
        rewrite_prompt = f"""
You are an expert prompt engineer. Analyze the failing test case and propose a better prompt.

Original Prompt:
{original_prompt}

Test Case ID: {test_id}
Agent Type: {agent_type}
Failure Analysis:
{json.dumps(failure_analysis, indent=2)}

Requirements for new prompt:
1. Must maintain the same core functionality
2. Must address the specific failure pattern identified
3. Must be more robust against the failure mode
4. Must include explicit guardrails for adversarial inputs
5. Must be clear and specific

Respond with valid JSON:
{{
  "new_prompt": "the complete rewritten prompt",
  "diff_summary": "specific changes made and why",
  "justification": "detailed reasoning for the rewrite",
  "expected_improvement": "what specific improvement is expected"
}}
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=config.AGENT_MODEL,
                messages=[{"role": "user", "content": rewrite_prompt}],
                max_completion_tokens=2000,
                stream=False,
            )
            
            rewrite_data = json.loads(response.choices[0].message.content)
            
            return PromptRewrite(
                rewrite_id=str(uuid.uuid4()),
                run_id=run_id,
                test_id=test_id,
                agent_type=agent_type,
                old_prompt=original_prompt,
                new_prompt=rewrite_data.get("new_prompt", ""),
                diff_summary=rewrite_data.get("diff_summary", ""),
                justification=rewrite_data.get("justification", ""),
                status="pending",
                created_at=time.time()
            )
            
        except Exception as e:
            logger.exception(f"Failed to generate rewrite for {agent_type}-{test_id}: {e}")
            raise
    
    async def _get_original_prompt(self, agent_type: str) -> Optional[str]:
        """Get the original prompt used by an agent type"""
        # In a real implementation, this would be stored in a database
        # For now, return default prompts based on agent type
        default_prompts = {
            "decomposition": """You are a Decomposition Agent. Break queries into sub-tasks with dependency graphs.

Rules:
1. Identify the main question and any sub-questions
2. Create explicit dependency relationships between sub-tasks
3. Dependent sub-tasks must not execute until dependencies resolve
4. Output structured JSON with sub-tasks and dependencies

Respond with valid JSON:
{
  "sub_tasks": {...},
  "dependencies": {...}
}""",
            "rag": """You are a RAG Agent. Perform multi-hop reasoning across retrieved chunks.

Rules:
1. Use at least TWO distinct retrieved chunks before answering
2. Cite which chunk contributed to which part of answer
3. Perform multi-hop: use result of one retrieval to inform next
4. If insufficient, explain what you need next

Respond with valid JSON:
{
  "hops": [...],
  "answer": "...",
  "citations": [...]
}""",
            "critique": """You are a Critique Agent. Review outputs claim-by-claim.

Rules:
1. Assign confidence score per claim (0.0-1.0)
2. Flag specific spans you disagree with
3. Provide reasoning for disagreements
4. Do not reject entire output

Respond with valid JSON:
{
  "confidence_scores": {...},
  "disagreements": [...],
  "reasoning": "..."
}""",
            "synthesis": """You are a Synthesis Agent. Merge outputs and resolve contradictions.

Rules:
1. Create provenance map linking sentences to sources
2. Resolve contradictions flagged by critique agent
3. Maintain coherence and flow
4. Cite all contributing sources

Respond with valid JSON:
{
  "final_answer": "...",
  "provenance_map": {...}
}"""
        }
        
        return default_prompts.get(agent_type)
    
    async def _analyze_failure_pattern(self, run_id: str, test_id: str, agent_type: str) -> Dict[str, Any]:
        """Analyze specific failure pattern for a test case"""
        # Get execution trace for this test
        trace = await self.storage.get_execution_trace(test_id)
        if not trace:
            return {"error": "No trace found"}
        
        # Get evaluation score
        # In real implementation, would query database
        # For now, simulate analysis based on test_id patterns
        
        failure_patterns = {
            "adversarial": {
                "injection": "System prompt not properly hardened against injection attempts",
                "premise_flaw": "Failed to detect false premises in adversarial queries",
                "contradiction": "Poor handling of contradictory information"
            },
            "ambiguous": {
                "overspecific": "Prompt too generic for underspecified queries",
                "underconstrained": "Missing guardrails for handling edge cases",
                "decomposition": "Poor task breakdown for complex queries"
            },
            "straightforward": {
                "retrieval": "Insufficient or irrelevant information retrieval",
                "citation": "Poor citation accuracy or missing citations",
                "reasoning": "Logical gaps in reasoning chain"
            }
        }
        
        category = "adversarial" if test_id.startswith("adv_") else \
                 "ambiguous" if test_id.startswith("amb_") else "straightforward"
        
        pattern = failure_patterns.get(category, {}).get(agent_type, "Unknown failure pattern")
        
        return {
            "test_id": test_id,
            "agent_type": agent_type,
            "failure_category": category,
            "failure_pattern": pattern,
            "trace_analysis": {
                "total_latency_ms": trace.get("total_latency_ms", 0),
                "tool_calls_count": len(trace.get("tool_calls_made", [])),
                "outputs_count": len(trace.get("outputs_received", []))
            }
        }
    
    async def run(self, shared_ctx: SharedContext) -> Dict[str, Any]:
        """Run meta-agent analysis"""
        run_id = shared_ctx.job_id or str(uuid.uuid4())
        
        try:
            # Analyze failure patterns
            analysis = await self.analyze_failure_patterns(run_id)
            
            # Generate rewrites for worst performing cases
            worst_performing = analysis.get("worst_performing_dimensions", {})
            rewrite_proposals = []
            
            for category, worst in worst_performing.items():
                if worst["score"] < 0.7:  # Threshold for proposing rewrites
                    rewrite = await self.propose_rewrite(run_id, worst["test_id"], category)
                    rewrite_proposals.append(rewrite)
            
            # Store all proposals
            for rewrite in rewrite_proposals:
                await self.storage.store_prompt_rewrite(
                    run_id, rewrite.test_id, rewrite.agent_type,
                    rewrite.old_prompt, rewrite.new_prompt,
                    rewrite.diff_summary, rewrite.justification
                )
            
            return {
                "status": "completed",
                "run_id": run_id,
                "analysis": analysis,
                "rewrite_proposals": len(rewrite_proposals),
                "worst_performing": len(worst_performing)
            }
            
        except Exception as e:
            logger.exception(f"Meta-agent failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
