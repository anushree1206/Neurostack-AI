"""
Context Window Budget Manager.

Tracks token consumption per agent per turn, enforces budgets,
triggers compression when needed, and logs policy violations.
"""
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

except Exception:
    def count_tokens(text: str) -> int:
        return len(text) // 4


@dataclass
class ContextEntry:
    role: str
    content: str
    is_structured: bool = False  # structured = lossless during compression
    token_count: int = 0

    def __post_init__(self):
        if self.token_count == 0:
            self.token_count = count_tokens(self.content)


@dataclass
class AgentContext:
    agent_id: str
    max_budget: int
    entries: list[ContextEntry] = field(default_factory=list)
    policy_violations: list[str] = field(default_factory=list)

    @property
    def used_tokens(self) -> int:
        return sum(e.token_count for e in self.entries)

    @property
    def remaining_budget(self) -> int:
        return self.max_budget - self.used_tokens

    def check_budget(self, additional_tokens: int = 0) -> bool:
        return (self.used_tokens + additional_tokens) <= self.max_budget

    def add_entry(self, role: str, content: str, is_structured: bool = False) -> bool:
        entry = ContextEntry(role=role, content=content, is_structured=is_structured)
        if not self.check_budget(entry.token_count):
            violation = (
                f"Agent {self.agent_id} attempted to add {entry.token_count} tokens "
                f"but only {self.remaining_budget} remain of {self.max_budget} budget."
            )
            self.policy_violations.append(violation)
            logger.warning("POLICY_VIOLATION: %s", violation)
            return False
        self.entries.append(entry)
        return True

    def to_messages(self) -> list[dict]:
        return [{"role": e.role, "content": e.content} for e in self.entries]

    def input_hash(self) -> str:
        raw = "".join(e.content for e in self.entries)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ContextBudgetManager:
    def __init__(self):
        self._contexts: dict[str, AgentContext] = {}

    def create_context(self, agent_id: str, max_budget: int) -> AgentContext:
        ctx = AgentContext(agent_id=agent_id, max_budget=max_budget)
        self._contexts[agent_id] = ctx
        return ctx

    def get_context(self, agent_id: str) -> Optional[AgentContext]:
        return self._contexts.get(agent_id)

    def check_remaining(self, agent_id: str) -> int:
        ctx = self._contexts.get(agent_id)
        return ctx.remaining_budget if ctx else 0

    def needs_compression(self, ctx: AgentContext, threshold: float = 0.85) -> bool:
        return ctx.used_tokens > (ctx.max_budget * threshold)

    def compress_context(self, ctx: AgentContext) -> list[ContextEntry]:
        """
        Compress context: keep structured entries (lossless), summarize conversational.
        Returns entries that were removed for re-injection as compressed summary.
        """
        structured = [e for e in ctx.entries if e.is_structured]
        conversational = [e for e in ctx.entries if not e.is_structured]

        # Keep last 20% of conversational as-is (most recent context)
        keep_count = max(1, len(conversational) // 5)
        to_compress = conversational[:-keep_count] if len(conversational) > keep_count else []
        to_keep_conv = conversational[-keep_count:] if len(conversational) > keep_count else conversational

        ctx.entries = structured + to_keep_conv
        return to_compress

    def all_violations(self) -> list[str]:
        violations = []
        for ctx in self._contexts.values():
            violations.extend(ctx.policy_violations)
        return violations
