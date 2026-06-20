"""
Background worker for processing agent jobs asynchronously.
Jobs are submitted to a queue and processed one at a time.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.db.database import AsyncSessionLocal
from backend.db import models
from backend.agents.base import SharedContext
from backend.agents.orchestrator import OrchestratorAgent
from backend.context_manager import ContextBudgetManager
from backend.streaming import SSEStream

logger = logging.getLogger(__name__)

_job_streams: dict[str, SSEStream] = {}
_job_queue: asyncio.Queue = asyncio.Queue(maxsize=100)


def get_stream(job_id: str) -> Optional[SSEStream]:
    return _job_streams.get(job_id)


async def submit_job(query: str) -> tuple[str, SSEStream]:
    job_id = str(uuid.uuid4())
    stream = SSEStream()
    _job_streams[job_id] = stream

    async with AsyncSessionLocal() as db:
        job = models.Job(id=job_id, query=query, status="pending")
        db.add(job)
        await db.commit()

    await _job_queue.put(job_id)
    return job_id, stream


async def _process_job(job_id: str):
    stream = _job_streams.get(job_id)
    if not stream:
        logger.error("No stream found for job %s", job_id)
        return

    async with AsyncSessionLocal() as db:
        stmt = select(models.Job).where(models.Job.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return

        job.status = "running"
        await db.commit()

        query = job.query
        budget_mgr = ContextBudgetManager()
        shared_ctx = SharedContext(job_id=job_id, original_query=query)

        seq = [0]

        def log_event(agent_id: str, event_type: str, content: dict):
            seq[0] += 1
            ev = models.ExecutionEvent(
                id=str(uuid.uuid4()),
                job_id=job_id,
                sequence=seq[0],
                agent_id=agent_id,
                event_type=event_type,
                content=content,
            )
            db.add(ev)

        try:
            orchestrator = OrchestratorAgent(
                budget_manager=budget_mgr,
                stream=stream,
                job_id=job_id,
            )
            await orchestrator.execute(shared_ctx)

            for tool_log in shared_ctx.tool_call_history:
                tc = models.ToolCallLog(
                    id=str(uuid.uuid4()),
                    job_id=job_id,
                    agent_id=tool_log.get("agent_id", "unknown"),
                    tool_name=tool_log.get("tool", "unknown"),
                    attempt=tool_log.get("attempt", 0),
                    input_data=tool_log.get("input"),
                    output_data=tool_log.get("output"),
                    latency_ms=tool_log.get("latency_ms"),
                    accepted=tool_log.get("accepted"),
                    failure_mode=tool_log.get("failure_mode"),
                )
                db.add(tc)

            for routing in shared_ctx.routing_log:
                log_event("orchestrator", "routing_decision", routing)

            for agent_id, output in shared_ctx.agent_outputs.items():
                log_event(agent_id, "agent_start", {"agent_id": agent_id, "status": "started"})
                log_event(agent_id, "agent_done", {
                    "agent_id": agent_id,
                    "status": "completed",
                    "output_keys": list(output.keys()) if isinstance(output, dict) else [],
                })

            for agent_id in shared_ctx.agent_outputs:
                ctx = budget_mgr.get_context(agent_id)
                if ctx:
                    log_event(agent_id, "budget", {
                        "agent_id": agent_id,
                        "used": ctx.used_tokens,
                        "budget": ctx.max_budget,
                        "remaining": ctx.remaining_budget,
                    })
                    for v in ctx.policy_violations:
                        log_event(agent_id, "policy_violation", {
                            "agent_id": agent_id,
                            "message": v,
                        })

            for tool_log in shared_ctx.tool_call_history:
                log_event(
                    tool_log.get("agent_id", "unknown"),
                    "tool_call",
                    {
                        "tool": tool_log.get("tool"),
                        "attempt": tool_log.get("attempt", 0),
                        "accepted": tool_log.get("accepted"),
                        "latency_ms": tool_log.get("latency_ms"),
                        "failure_mode": tool_log.get("failure_mode"),
                    },
                )

            job.status = "done"
            job.final_answer = shared_ctx.final_answer or ""
            job.provenance_map = shared_ctx.provenance_map
            job.completed_at = datetime.utcnow()
            await db.commit()

            stream.emit_done(job_id, shared_ctx.final_answer or "")

        except Exception as e:
            logger.exception("Job %s failed: %s", job_id, e)
            job.status = "failed"
            job.final_answer = f"Pipeline failed: {str(e)}"
            job.completed_at = datetime.utcnow()
            await db.commit()
            stream.emit_error(str(e), job_id)
        finally:
            stream.close()
            await asyncio.sleep(300)
            _job_streams.pop(job_id, None)


async def worker_loop():
    logger.info("Worker loop started")
    while True:
        try:
            job_id = await _job_queue.get()
            asyncio.create_task(_process_job(job_id))
            _job_queue.task_done()
        except Exception as e:
            logger.exception("Worker loop error: %s", e)
            await asyncio.sleep(1)


async def get_job_trace(job_id: str, db: AsyncSession) -> Optional[dict]:
    stmt = select(models.Job).where(models.Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        return None

    stmt2 = select(models.ExecutionEvent).where(
        models.ExecutionEvent.job_id == job_id
    ).order_by(models.ExecutionEvent.sequence)
    ev_result = await db.execute(stmt2)
    events = ev_result.scalars().all()

    stmt3 = select(models.ToolCallLog).where(models.ToolCallLog.job_id == job_id)
    tc_result = await db.execute(stmt3)
    tool_calls = tc_result.scalars().all()

    return {
        "job_id": job_id,
        "query": job.query,
        "status": job.status,
        "final_answer": job.final_answer,
        "provenance_map": job.provenance_map,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "events": [
            {
                "sequence": e.sequence,
                "agent_id": e.agent_id,
                "event_type": e.event_type,
                "content": e.content,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in events
        ],
        "tool_calls": [
            {
                "tool_name": t.tool_name,
                "agent_id": t.agent_id,
                "attempt": t.attempt,
                "input": t.input_data,
                "output": t.output_data,
                "latency_ms": t.latency_ms,
                "accepted": t.accepted,
                "failure_mode": t.failure_mode,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in tool_calls
        ],
    }
