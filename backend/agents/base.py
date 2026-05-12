"""
Base agent class. All agents inherit from this.
"""
import hashlib
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any
from backend.context_manager import ContextBudgetManager, AgentContext
from backend.streaming import SSEStream
from backend import config

logger = logging.getLogger(__name__)


def make_openai_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        base_url=config.OPENAI_BASE_URL or None,
        api_key=config.OPENAI_API_KEY,
    )


class SharedContext:
    """
    Shared context object passed between agents.
    All inter-agent communication passes through this object.
    Agents must NOT call each other directly.
    """
    def __init__(self, job_id: str, original_query: str):
        self.job_id = job_id
        self.original_query = original_query
        self.decomposed_tasks: list[dict] = []
        self.dependency_graph: dict[str, list[str]] = {}
        self.retrieved_chunks: list[dict] = []
        self.agent_outputs: dict[str, Any] = {}
        self.critique_results: dict[str, Any] = {}
        self.final_answer: Optional[str] = None
        self.provenance_map: list[dict] = []
        self.tool_call_history: list[dict] = []
        self.routing_log: list[dict] = []
        self.session_outputs: list[str] = []  # for self-reflection tool


class BaseAgent(ABC):
    agent_id: str = "base"
    default_budget: int = 6000

    def __init__(
        self,
        budget_manager: ContextBudgetManager,
        stream: SSEStream,
        job_id: str,
        prompt_overrides: dict = None,
    ):
        self.budget_manager = budget_manager
        self.stream = stream
        self.job_id = job_id
        self.prompt_overrides = prompt_overrides or {}
        self._client = None  # Lazy-load client
        self.ctx: Optional[AgentContext] = None
        self._event_sequence = 0
    
    @property
    def client(self):
        """Lazy-load OpenAI client"""
        if self._client is None:
            self._client = make_openai_client()
        return self._client

    def _next_seq(self) -> int:
        self._event_sequence += 1
        return self._event_sequence

    def get_system_prompt(self) -> str:
        key = f"{self.agent_id}_system"
        return self.prompt_overrides.get(key, self._default_system_prompt())

    @abstractmethod
    def _default_system_prompt(self) -> str:
        pass

    def initialize_context(self) -> AgentContext:
        self.ctx = self.budget_manager.create_context(self.agent_id, self.default_budget)
        self.stream.emit_agent_start(self.agent_id, self.default_budget)
        return self.ctx

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:12]

    async def _call_llm(
        self,
        messages: list[dict],
        model: str = None,
        max_tokens: int = 4096,
        stream: bool = True,
    ) -> str:
        model = model or config.AGENT_MODEL
        start = time.monotonic()
        full_response = ""

        if stream:
            resp = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_tokens,
                stream=True,
            )
            async for chunk in resp:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full_response += delta
                    budget_rem = self.ctx.remaining_budget if self.ctx else 0
                    self.stream.emit_token(self.agent_id, delta, budget_rem)
        else:
            resp = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_tokens,
                stream=False,
            )
            full_response = resp.choices[0].message.content or ""

        latency = (time.monotonic() - start) * 1000
        return full_response

    @abstractmethod
    async def run(self, shared_ctx: SharedContext) -> Any:
        pass
