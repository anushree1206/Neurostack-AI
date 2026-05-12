"""
Base tool class with failure contracts.
Every tool defines what it returns on: timeout, empty result, malformed input.
"""
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    success: bool
    data: Any
    failure_mode: Optional[str] = None  # "timeout" | "empty" | "malformed" | None
    latency_ms: float = 0.0
    error_message: Optional[str] = None

    @classmethod
    def timeout(cls, tool_name: str) -> "ToolResult":
        return cls(
            success=False,
            data=None,
            failure_mode="timeout",
            error_message=f"{tool_name}: operation timed out",
        )

    @classmethod
    def empty(cls, tool_name: str) -> "ToolResult":
        return cls(
            success=True,
            data=[],
            failure_mode="empty",
            error_message=f"{tool_name}: no results returned",
        )

    @classmethod
    def malformed(cls, tool_name: str, reason: str) -> "ToolResult":
        return cls(
            success=False,
            data=None,
            failure_mode="malformed",
            error_message=f"{tool_name}: malformed input — {reason}",
        )


class BaseTool(ABC):
    name: str = "base_tool"
    timeout_seconds: float = 10.0

    def log_call(
        self,
        input_data: Any,
        result: ToolResult,
        attempt: int,
        accepted: Optional[bool] = None,
    ):
        logger.info(
            "TOOL_CALL tool=%s attempt=%d success=%s failure=%s latency_ms=%.1f accepted=%s",
            self.name,
            attempt,
            result.success,
            result.failure_mode,
            result.latency_ms,
            accepted,
        )

    async def call(self, input_data: Any, attempt: int = 0) -> ToolResult:
        start = time.monotonic()
        try:
            result = await self._execute(input_data)
            result.latency_ms = (time.monotonic() - start) * 1000
            return result
        except TimeoutError:
            return ToolResult.timeout(self.name)
        except ValueError as e:
            return ToolResult.malformed(self.name, str(e))
        except Exception as e:
            logger.exception("Tool %s failed: %s", self.name, e)
            return ToolResult(
                success=False,
                data=None,
                failure_mode="error",
                error_message=str(e),
                latency_ms=(time.monotonic() - start) * 1000,
            )

    @abstractmethod
    async def _execute(self, input_data: Any) -> ToolResult:
        pass
