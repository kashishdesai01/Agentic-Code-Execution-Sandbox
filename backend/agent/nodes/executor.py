import asyncio
import time
from pathlib import Path

import aiofiles

from backend.agent.state import GraphState, ExecutionResult
from backend.config import settings
from backend.memory import redis_store


async def run_executor(state: GraphState) -> dict:
    task_id = state["task_id"]
    generated_code = state.get("generated_code")
    retry_count = state.get("retry_count", 0)

    # Fast-path: syntax failure before execution
    if generated_code is None:
        result = ExecutionResult(
            stdout="",
            stderr=state.get("error_trace") or "Code generation failed",
            exit_code=1,
            timed_out=False,
            execution_time_ms=0,
        )
        return {"execution_result": result.model_dump()}

    host_path = f"/tmp/task_{task_id}.py"
    async with aiofiles.open(host_path, "w") as f:
        await f.write(generated_code)

    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--read-only",
        "--memory", settings.docker_memory,
        "--cpus", settings.docker_cpus,
        "--tmpfs", "/tmp:size=64m,noexec",
        "-v", f"{host_path}:/sandbox/task.py:ro",
        settings.sandbox_image,
        "python", "/sandbox/task.py",
    ]

    timed_out = False
    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=settings.docker_timeout_seconds
            )
            exit_code = proc.returncode
        except asyncio.TimeoutError:
            timed_out = True
            proc.kill()
            await proc.communicate()
            stdout_bytes, stderr_bytes = b"", b"Execution timed out"
            exit_code = -1
    except FileNotFoundError:
        stdout_bytes, stderr_bytes = b"", b"docker executable not found"
        exit_code = -1
    except Exception as e:
        stdout_bytes, stderr_bytes = b"", str(e).encode()
        exit_code = -1

    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Clean up host temp file
    try:
        Path(host_path).unlink(missing_ok=True)
    except OSError:
        pass

    result = ExecutionResult(
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
        exit_code=exit_code if exit_code is not None else -1,
        timed_out=timed_out,
        execution_time_ms=elapsed_ms,
    )

    redis = await redis_store.get_redis_client()
    await redis_store.publish_progress(
        redis,
        task_id,
        "node_complete",
        {
            "node": "executor",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "retry_count": retry_count,
        },
    )

    return {"execution_result": result.model_dump()}
