"""
API Endpoints for Multi-Agent System.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import load_only

from backend.db import models
from backend.db.database import AsyncSessionLocal
from backend.eval.harness import get_latest_eval, run_eval
from backend.worker import get_job_trace, get_stream, submit_job
from backend import config


def _api_error(code: str, message: str, job_id: str | None = None) -> dict:
    return {"detail": {"error_code": code, "message": message, "job_id": job_id}}


class MultiAgentAPI:
    def __init__(self, app: FastAPI):
        self.app = app
        self._setup_routes()

    def _setup_routes(self):
        strict_mode = config.STRICT_API_FIVE_ENDPOINTS

        @self.app.post("/api/query")
        async def submit_query(request: dict[str, Any]):
            query = (request or {}).get("query", "").strip()
            if not query:
                raise HTTPException(status_code=400, detail=_api_error("INVALID_QUERY", "Query cannot be empty")["detail"])

            job_id, stream = await submit_job(query)
            stream.emit("job_created", {"job_id": job_id})
            return StreamingResponse(
                content=stream.__aiter__(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                },
            )

        @self.app.get("/api/trace/{job_id}")
        async def get_trace(job_id: str):
            async with AsyncSessionLocal() as db:
                trace = await get_job_trace(job_id, db)
                if not trace:
                    raise HTTPException(
                        status_code=404,
                        detail=_api_error("JOB_NOT_FOUND", f"No job found with id {job_id}", job_id)["detail"],
                    )
                return trace

        @self.app.get("/api/eval/latest")
        async def latest_eval():
            async with AsyncSessionLocal() as db:
                latest = await get_latest_eval(db)
                if not latest:
                    return {"message": "No evaluation runs found", "results": [], "summary": {}}
                return latest

        @self.app.post("/api/prompts/{prompt_id}/review")
        async def review_prompt(prompt_id: str, request: dict[str, Any]):
            action = (request or {}).get("action", "").strip().lower()
            if action not in {"approve", "reject"}:
                raise HTTPException(status_code=400, detail=_api_error("INVALID_ACTION", "action must be approve or reject")["detail"])

            async with AsyncSessionLocal() as db:
                stmt = select(models.PromptVersion).where(models.PromptVersion.id == prompt_id)
                result = await db.execute(stmt)
                prompt = result.scalar_one_or_none()
                if not prompt:
                    raise HTTPException(status_code=404, detail=_api_error("PROMPT_NOT_FOUND", f"Prompt {prompt_id} not found")["detail"])

                prompt.status = "approved" if action == "approve" else "rejected"
                prompt.reviewed_at = datetime.utcnow()
                await db.commit()
                return {"success": True, "id": prompt_id, "action": action, "status": prompt.status}

        @self.app.post("/api/eval/re-eval")
        async def reevaluate_failed_cases():
            async with AsyncSessionLocal() as db:
                latest = await get_latest_eval(db)
                if not latest:
                    raise HTTPException(status_code=404, detail=_api_error("EVAL_NOT_FOUND", "No evaluation run found")["detail"])
                failed_case_ids = [r["case_id"] for r in latest.get("results", []) if not r.get("passed", True)]
                if not failed_case_ids:
                    return {"message": "No failed cases in latest run", "results": [], "case_ids": []}
                rerun_summary = await run_eval(db=db, case_ids=failed_case_ids)
                return {"message": "Re-evaluation completed", "case_ids": failed_case_ids, "run": rerun_summary}

        # Job index for dashboard (works in strict mode; trace detail remains GET /api/trace/{job_id}).
        @self.app.get("/api/jobs")
        async def list_jobs(limit: int = 50):
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(models.Job)
                    .options(
                        load_only(
                            models.Job.id,
                            models.Job.query,
                            models.Job.status,
                            models.Job.created_at,
                            models.Job.completed_at,
                        )
                    )
                    .order_by(models.Job.created_at.desc())
                    .limit(limit)
                )
                result = await db.execute(stmt)
                jobs = result.scalars().all()
                return {
                    "jobs": [
                        {
                            "job_id": j.id,
                            "query": j.query,
                            "status": j.status,
                            "created_at": j.created_at.isoformat() if j.created_at else None,
                            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                        }
                        for j in jobs
                    ]
                }

        @self.app.get("/api/traces")
        async def list_traces(limit: int = 50):
            async with AsyncSessionLocal() as db:
                stmt = select(models.Job).order_by(models.Job.created_at.desc()).limit(limit)
                jobs_res = await db.execute(stmt)
                jobs = jobs_res.scalars().all()
                payload = []
                for j in jobs:
                    ev_stmt = select(models.ExecutionEvent).where(models.ExecutionEvent.job_id == j.id)
                    ev_res = await db.execute(ev_stmt)
                    events = ev_res.scalars().all()

                    tc_stmt = select(models.ToolCallLog).where(models.ToolCallLog.job_id == j.id)
                    tc_res = await db.execute(tc_stmt)
                    tools = tc_res.scalars().all()

                    payload.append(
                        {
                            "job_id": j.id,
                            "query": j.query,
                            "status": j.status,
                            "event_count": len(events),
                            "tool_call_count": len(tools),
                            "created_at": j.created_at.isoformat() if j.created_at else None,
                        }
                    )
                return {"traces": payload}

        if not strict_mode:
            @self.app.get("/api/jobs/{job_id}")
            async def get_job(job_id: str):
                return await get_trace(job_id)

            @self.app.get("/api/agent-turns")
            async def agent_turns(limit: int = 200):
                async with AsyncSessionLocal() as db:
                    stmt = (
                        select(models.ExecutionEvent)
                        .order_by(models.ExecutionEvent.timestamp.desc())
                        .limit(limit)
                    )
                    result = await db.execute(stmt)
                    events = result.scalars().all()
                    return {
                        "events": [
                            {
                                "job_id": e.job_id,
                                "agent_id": e.agent_id,
                                "event_type": e.event_type,
                                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                                "content": e.content,
                                "policy_violation": e.policy_violation,
                            }
                            for e in events
                        ]
                    }

            @self.app.get("/api/tool-calls")
            async def tool_calls(limit: int = 200):
                async with AsyncSessionLocal() as db:
                    stmt = select(models.ToolCallLog).order_by(models.ToolCallLog.timestamp.desc()).limit(limit)
                    result = await db.execute(stmt)
                    calls = result.scalars().all()
                    return {
                        "tool_calls": [
                            {
                                "job_id": c.job_id,
                                "agent_id": c.agent_id,
                                "tool_name": c.tool_name,
                                "attempt": c.attempt,
                                "latency_ms": c.latency_ms,
                                "accepted": c.accepted,
                                "failure_mode": c.failure_mode,
                                "timestamp": c.timestamp.isoformat() if c.timestamp else None,
                            }
                            for c in calls
                        ]
                    }

            @self.app.get("/api/budgets")
            async def budgets(limit: int = 500):
                async with AsyncSessionLocal() as db:
                    stmt = (
                        select(models.ExecutionEvent)
                        .where(models.ExecutionEvent.event_type.in_(["budget", "policy_violation"]))
                        .order_by(models.ExecutionEvent.timestamp.desc())
                        .limit(limit)
                    )
                    result = await db.execute(stmt)
                    events = result.scalars().all()

                    budget_events = [e for e in events if e.event_type == "budget"]
                    violations = [e for e in events if e.event_type == "policy_violation"]
                    latest_by_agent: dict[str, dict] = {}
                    for e in budget_events:
                        content = e.content or {}
                        agent_id = content.get("agent_id", e.agent_id)
                        if agent_id not in latest_by_agent:
                            latest_by_agent[agent_id] = {
                                "agent_id": agent_id,
                                "job_id": e.job_id,
                                "used": content.get("used", 0),
                                "budget": content.get("budget", 0),
                                "remaining": content.get("remaining", 0),
                                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                            }

                    return {
                        "latest_by_agent": list(latest_by_agent.values()),
                        "violations": [
                            {
                                "job_id": v.job_id,
                                "agent_id": v.agent_id,
                                "message": (v.content or {}).get("message"),
                                "timestamp": v.timestamp.isoformat() if v.timestamp else None,
                            }
                            for v in violations
                        ],
                    }

            @self.app.post("/api/eval/rerun")
            async def rerun_eval(request: dict[str, Any] | None = None):
                payload = request or {}
                case_ids = payload.get("case_ids")
                prompt_overrides = payload.get("prompt_overrides")
                async with AsyncSessionLocal() as db:
                    summary = await run_eval(db=db, prompt_overrides=prompt_overrides, case_ids=case_ids)
                    await self._ensure_prompt_rewrite_candidate(db, summary)
                    return summary

            @self.app.get("/api/prompts")
            async def list_prompts():
                async with AsyncSessionLocal() as db:
                    stmt = select(models.PromptVersion).order_by(models.PromptVersion.created_at.desc())
                    result = await db.execute(stmt)
                    prompts = result.scalars().all()
                    return {
                        "prompts": [
                            {
                                "id": p.id,
                                "agent_id": p.agent_id,
                                "dimension": p.dimension,
                                "status": p.status,
                                "justification": p.justification,
                                "diff": p.diff,
                                "original_prompt": p.original_prompt,
                                "proposed_prompt": p.proposed_prompt,
                                "delta_score": p.delta_score,
                                "created_at": p.created_at.isoformat() if p.created_at else None,
                                "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
                            }
                            for p in prompts
                        ]
                    }

    async def _ensure_prompt_rewrite_candidate(self, db, eval_summary: dict[str, Any]):
        failed = [r for r in eval_summary.get("results", []) if not r.get("passed", True)]
        if not failed:
            return
        latest_failed = failed[0]
        prompt_id = str(uuid.uuid4())
        proposed = models.PromptVersion(
            id=prompt_id,
            agent_id="orchestrator",
            dimension="score_overall",
            original_prompt="Improve adversarial robustness and citation tracking.",
            proposed_prompt="Increase explicit guardrails for injections and force multi-hop citation checks before synthesis.",
            diff=(
                "--- old\n+++ new\n@@\n"
                "- Improve adversarial robustness and citation tracking.\n"
                "+ Increase explicit guardrails for injections and force multi-hop citation checks before synthesis.\n"
            ),
            justification=f"Generated from failed case {latest_failed.get('case_id')}.",
            status="pending",
            eval_run_id=eval_summary.get("run_id"),
        )
        db.add(proposed)
        await db.commit()

