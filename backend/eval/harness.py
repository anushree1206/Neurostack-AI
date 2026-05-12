"""
Evaluation Harness.
Runs 15 test cases through the full pipeline.
Stores results with full reproducibility.
"""
import logging
import time
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.eval.cases import EVAL_CASES, EvalCase
from backend.eval.scorer import score_case
from backend.agents.base import SharedContext
from backend.agents.orchestrator import OrchestratorAgent
from backend.context_manager import ContextBudgetManager
from backend.streaming import SSEStream
from backend.db import models

logger = logging.getLogger(__name__)


async def run_single_case(
    case: EvalCase,
    db: AsyncSession,
    eval_run_id: str,
    prompt_overrides: dict = None,
    stream: Optional[SSEStream] = None,
) -> dict:
    job_id = str(uuid.uuid4())
    budget_mgr = ContextBudgetManager()
    eval_stream = stream or SSEStream()

    shared_ctx = SharedContext(job_id=job_id, original_query=case.query)

    start_time = time.monotonic()
    try:
        orchestrator = OrchestratorAgent(
            budget_manager=budget_mgr,
            stream=eval_stream,
            job_id=job_id,
            prompt_overrides=prompt_overrides or {},
        )
        await orchestrator.execute(shared_ctx, prompt_overrides=prompt_overrides)
    except Exception as e:
        logger.exception("Eval case %s failed: %s", case.case_id, e)
        shared_ctx.final_answer = f"[Pipeline error: {str(e)}]"

    elapsed_ms = (time.monotonic() - start_time) * 1000

    policy_violations = budget_mgr.all_violations()
    case_score = score_case(
        case=case,
        final_answer=shared_ctx.final_answer or "",
        agent_outputs=shared_ctx.agent_outputs,
        tool_call_history=shared_ctx.tool_call_history,
        policy_violations=policy_violations,
    )

    result_dict = case_score.to_dict()
    result_dict["job_id"] = job_id
    result_dict["elapsed_ms"] = round(elapsed_ms, 1)
    result_dict["prompts_used"] = prompt_overrides or {}
    result_dict["tool_calls_made"] = shared_ctx.tool_call_history

    db_result = models.EvalResult(
        id=str(uuid.uuid4()),
        run_id=eval_run_id,
        case_id=case.case_id,
        case_category=case.category,
        query=case.query,
        job_id=job_id,
        final_answer=shared_ctx.final_answer or "",
        score_correctness=case_score.correctness.score,
        score_citation=case_score.citation_accuracy.score,
        score_contradiction=case_score.contradiction_resolution.score,
        score_tool_efficiency=case_score.tool_efficiency.score,
        score_budget_compliance=case_score.budget_compliance.score,
        score_critique_agreement=case_score.critique_agreement.score,
        score_overall=case_score.overall,
        justifications=case_score.to_dict()["justifications"],
        prompts_used=prompt_overrides or {},
        tool_calls_made=shared_ctx.tool_call_history,
        passed=case_score.passed,
    )
    db.add(db_result)
    await db.commit()

    return result_dict


async def run_eval(
    db: AsyncSession,
    prompt_overrides: dict = None,
    case_ids: Optional[list[str]] = None,
    stream: Optional[SSEStream] = None,
) -> dict:
    run_id = str(uuid.uuid4())
    run_label = f"eval_run_{run_id[:8]}"

    db_run = models.EvalRun(
        id=run_id,
        run_label=run_label,
        prompt_versions=prompt_overrides or {},
    )
    db.add(db_run)
    await db.commit()

    cases_to_run = EVAL_CASES
    if case_ids:
        cases_to_run = [c for c in EVAL_CASES if c.case_id in case_ids]

    results = []
    for case in cases_to_run:
        logger.info("Running eval case %s (%s)", case.case_id, case.category)
        try:
            result = await run_single_case(
                case=case,
                db=db,
                eval_run_id=run_id,
                prompt_overrides=prompt_overrides,
                stream=stream,
            )
            results.append(result)
        except Exception as e:
            logger.exception("Case %s crashed: %s", case.case_id, e)
            results.append({
                "case_id": case.case_id,
                "case_category": case.category,
                "query": case.query,
                "error": str(e),
                "score_overall": 0.0,
                "passed": False,
            })

    by_category = {}
    for r in results:
        cat = r.get("case_category", "unknown")
        by_category.setdefault(cat, []).append(r)

    dimensions = ["score_correctness", "score_citation", "score_contradiction",
                  "score_tool_efficiency", "score_budget_compliance", "score_critique_agreement"]

    summary = {
        "run_id": run_id,
        "run_label": run_label,
        "total_cases": len(results),
        "passed": sum(1 for r in results if r.get("passed", False)),
        "failed": sum(1 for r in results if not r.get("passed", True)),
        "overall_avg": round(sum(r.get("score_overall", 0) for r in results) / max(len(results), 1), 3),
        "by_category": {
            cat: {
                "count": len(rs),
                "passed": sum(1 for r in rs if r.get("passed", False)),
                "avg_overall": round(sum(r.get("score_overall", 0) for r in rs) / max(len(rs), 1), 3),
                **{
                    dim: round(sum(r.get(dim, 0) for r in rs) / max(len(rs), 1), 3)
                    for dim in dimensions
                },
            }
            for cat, rs in by_category.items()
        },
        "by_dimension": {
            dim: round(sum(r.get(dim, 0) for r in results) / max(len(results), 1), 3)
            for dim in dimensions
        },
        "results": results,
        "prompt_overrides": prompt_overrides or {},
    }

    db_run.summary = {k: v for k, v in summary.items() if k != "results"}
    await db.commit()

    return summary


async def get_latest_eval(db: AsyncSession) -> Optional[dict]:
    stmt = select(models.EvalRun).order_by(models.EvalRun.created_at.desc()).limit(1)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        return None

    stmt2 = select(models.EvalResult).where(models.EvalResult.run_id == run.id)
    res2 = await db.execute(stmt2)
    results = res2.scalars().all()

    return {
        "run_id": run.id,
        "run_label": run.run_label,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "summary": run.summary or {},
        "results": [
            {
                "case_id": r.case_id,
                "case_category": r.case_category,
                "query": r.query,
                "score_overall": r.score_overall,
                "score_correctness": r.score_correctness,
                "score_citation": r.score_citation,
                "score_contradiction": r.score_contradiction,
                "score_tool_efficiency": r.score_tool_efficiency,
                "score_budget_compliance": r.score_budget_compliance,
                "score_critique_agreement": r.score_critique_agreement,
                "passed": r.passed,
                "justifications": r.justifications,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in results
        ],
    }
