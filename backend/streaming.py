"""
Server-Sent Events (SSE) streaming utilities.
Provides structured event emission for real-time agent activity.
"""
import json
import asyncio
from typing import AsyncGenerator, Any


def format_sse(data: Any, event: str = "message") -> str:
    payload = json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"


class SSEStream:
    """
    Async queue-backed SSE stream.
    Agents push events; the FastAPI endpoint consumes them.
    """
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._done = False

    def emit(self, event_type: str, data: dict):
        self._queue.put_nowait({"type": event_type, **data})

    def emit_token(self, agent_id: str, token: str, budget_remaining: int):
        self.emit("token", {
            "agent_id": agent_id,
            "token": token,
            "budget_remaining": budget_remaining,
            "timestamp": self._get_timestamp(),
            "event_type": "token_generation"
        })

    def emit_agent_start(self, agent_id: str, budget: int):
        self.emit("agent_start", {
            "agent_id": agent_id,
            "budget": budget,
            "status": "starting",
            "timestamp": self._get_timestamp(),
            "event_type": "agent_initialization"
        })

    def emit_agent_done(self, agent_id: str, summary: str = ""):
        self.emit("agent_done", {
            "agent_id": agent_id,
            "summary": summary,
            "status": "completed",
            "timestamp": self._get_timestamp(),
            "event_type": "agent_completion"
        })

    def emit_tool_call(self, agent_id: str, tool_name: str, attempt: int, status: str, data: dict = None):
        # Enhanced tool call with detailed status and human-readable messages
        status_messages = {
            "success": f"✅ {tool_name} completed successfully",
            "failed": f"❌ {tool_name} failed",
            "retry": f"🔄 {tool_name} retry attempt {attempt}",
            "empty": f"⚠️ {tool_name} returned no results"
        }
        
        self.emit("tool_call", {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "attempt": attempt,
            "status": status,
            "human_readable_status": status_messages.get(status, f"🔧 {tool_name} - {status}"),
            "data": data or {},
            "timestamp": self._get_timestamp(),
            "event_type": "tool_execution"
        })

    def emit_routing_decision(self, from_agent: str, to_agent: str, justification: str):
        self.emit("routing", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "justification": justification,
            "routing_type": "agent_pipeline",
            "timestamp": self._get_timestamp(),
            "event_type": "routing_decision"
        })

    def emit_budget_update(self, agent_id: str, used: int, budget: int):
        remaining = budget - used
        utilization = (used / budget) * 100 if budget > 0 else 0
        
        self.emit("budget", {
            "agent_id": agent_id,
            "used": used,
            "budget": budget,
            "remaining": remaining,
            "utilization_percent": round(utilization, 2),
            "status": "warning" if utilization > 80 else "normal",
            "timestamp": self._get_timestamp(),
            "event_type": "budget_update"
        })

    def emit_policy_violation(self, agent_id: str, message: str):
        self.emit("policy_violation", {
            "agent_id": agent_id,
            "message": message,
            "severity": "warning",
            "timestamp": self._get_timestamp(),
            "event_type": "policy_violation"
        })

    def emit_error(self, message: str, job_id: str = ""):
        self.emit("error", {
            "message": message,
            "job_id": job_id,
            "severity": "error",
            "timestamp": self._get_timestamp(),
            "event_type": "system_error"
        })

    def emit_done(self, job_id: str, answer: str):
        self.emit("done", {
            "job_id": job_id,
            "answer": answer,
            "status": "completed",
            "timestamp": self._get_timestamp(),
            "event_type": "job_completion"
        })

    def emit_retrieval_summary(self, agent_id: str, source_type: str, sources_found: int, query_used: str):
        """Enhanced retrieval event with detailed summary"""
        self.emit("retrieval_summary", {
            "agent_id": agent_id,
            "source_type": source_type,
            "sources_found": sources_found,
            "query_used": query_used,
            "status": "completed" if sources_found > 0 else "no_results",
            "timestamp": self._get_timestamp(),
            "event_type": "retrieval_summary"
        })

    def emit_reasoning_trace(self, agent_id: str, reasoning_step: str, confidence: float):
        """Enhanced reasoning event for multi-hop analysis"""
        self.emit("reasoning_trace", {
            "agent_id": agent_id,
            "reasoning_step": reasoning_step,
            "confidence": confidence,
            "timestamp": self._get_timestamp(),
            "event_type": "reasoning_trace"
        })

    def emit_synthesis_progress(self, agent_id: str, section: str, progress_percent: float):
        """Enhanced synthesis progress event"""
        self.emit("synthesis_progress", {
            "agent_id": agent_id,
            "section": section,
            "progress_percent": progress_percent,
            "timestamp": self._get_timestamp(),
            "event_type": "synthesis_progress"
        })

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        import datetime
        return datetime.datetime.utcnow().isoformat() + "Z"

    def close(self):
        self._done = True
        self._queue.put_nowait(None)

    async def __aiter__(self) -> AsyncGenerator[str, None]:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield format_sse(item)
            if item.get("type") == "done":
                break
