"""
Code execution sandbox tool.
Runs Python snippets in a subprocess with timeout protection.
Returns stdout, stderr, and exit code.
On timeout: terminates process and returns timeout failure.
On malformed input: returns malformed failure without execution.
"""
import asyncio
import sys
from typing import Any
from backend.tools.base import BaseTool, ToolResult

BLOCKED_IMPORTS = [
    "os.remove", "shutil.rmtree", "subprocess", "socket",
    "__import__('os').remove", "open('/", "open(\"/",
]


def _is_safe(code: str) -> tuple[bool, str]:
    for blocked in BLOCKED_IMPORTS:
        if blocked in code:
            return False, f"blocked pattern: {blocked}"
    return True, ""


class CodeExecutorTool(BaseTool):
    name = "code_executor"
    timeout_seconds = 10.0

    async def _execute(self, input_data: Any) -> ToolResult:
        if not isinstance(input_data, dict) or "code" not in input_data:
            raise ValueError("input must be dict with 'code' key")

        code = str(input_data["code"]).strip()
        if not code:
            raise ValueError("code cannot be empty")

        if len(code) > 10000:
            raise ValueError("code too long (max 10000 chars)")

        safe, reason = _is_safe(code)
        if not safe:
            raise ValueError(f"unsafe code: {reason}")

        timeout = float(input_data.get("timeout", self.timeout_seconds))

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                exit_code = proc.returncode

                if not stdout and not stderr:
                    return ToolResult.empty(self.name)

                return ToolResult(
                    success=True,
                    data={
                        "stdout": stdout[:4000],
                        "stderr": stderr[:2000],
                        "exit_code": exit_code,
                        "code": code,
                    },
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult.timeout(self.name)

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                failure_mode="error",
                error_message=str(e),
            )
