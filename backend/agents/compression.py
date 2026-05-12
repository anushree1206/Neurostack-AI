"""
Compression Agent.
Summarizes older context to fit within budget constraints.
Lossless for structured data (tool outputs, scores, citations).
Lossy only for conversational filler.
"""
import logging
from backend.agents.base import BaseAgent, SharedContext
from backend.context_manager import AgentContext, ContextEntry

logger = logging.getLogger(__name__)


class CompressionAgent(BaseAgent):
    agent_id = "compression"
    default_budget = 3000

    def _default_system_prompt(self) -> str:
        return """You are a Compression Agent. Summarize conversational context while preserving key information.

Rules:
1. Preserve ALL numbers, scores, URLs, citations, structured data exactly
2. Compress only narrative/conversational text
3. Keep technical terms exact
4. Output a concise summary that retains the essential information"""

    async def compress_entries(self, entries: list[ContextEntry]) -> str:
        if not entries:
            return ""

        combined = "\n".join(f"[{e.role}]: {e.content}" for e in entries)
        if len(combined) < 500:
            return combined

        self.initialize_context()
        self.ctx.add_entry("system", self.get_system_prompt(), is_structured=True)
        self.ctx.add_entry("user", f"Summarize the following context, preserving all structured data:\n\n{combined[:3000]}")

        return await self._call_llm(self.ctx.to_messages(), stream=False)

    async def run(self, shared_ctx: SharedContext) -> dict:
        return {"status": "compression_complete"}
