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
        })

    def emit_agent_start(self, agent_id: str, budget: int):
        self.emit("agent_start", {"agent_id": agent_id, "budget": budget})

    def emit_agent_done(self, agent_id: str, summary: str = ""):
        self.emit("agent_done", {"agent_id": agent_id, "summary": summary})

    def emit_tool_call(self, agent_id: str, tool_name: str, attempt: int, status: str, data: dict = None):
        self.emit("tool_call", {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "attempt": attempt,
            "status": status,
            "data": data or {},
        })

    def emit_routing_decision(self, from_agent: str, to_agent: str, justification: str):
        self.emit("routing", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "justification": justification,
        })

    def emit_budget_update(self, agent_id: str, used: int, budget: int):
        self.emit("budget", {
            "agent_id": agent_id,
            "used": used,
            "budget": budget,
            "remaining": budget - used,
        })

    def emit_policy_violation(self, agent_id: str, message: str):
        self.emit("policy_violation", {
            "agent_id": agent_id,
            "message": message,
        })

    def emit_error(self, message: str, job_id: str = ""):
        self.emit("error", {"message": message, "job_id": job_id})

    def emit_done(self, job_id: str, answer: str):
        self.emit("done", {"job_id": job_id, "answer": answer})

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
