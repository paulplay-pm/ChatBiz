"""Code execution node — run user-supplied code in a Docker sandbox.

The sandbox is opt-in (controlled by ``DOCKER_SANDBOX_ENABLED``) and uses
hard CPU / memory / network limits to prevent abuse. We do **not** mount the
host filesystem or expose the host network — the container has ``network_mode="none"``
and no volumes, so the only data the code can see is what the workflow
passes in (Phase 5 will add ``input_variables`` binding via stdin or env vars).

We support Python and Node for the MVP. The image is pinned
(``python:3.12-slim`` / ``node:20-slim``) to keep the cold-start time
predictable. Phase 5 may add a custom image registry hook so enterprise
customers can bring their own.
"""
from __future__ import annotations

from typing import Literal

import docker
from pydantic import Field

from app.config import get_settings
from app.errors.classes import CodeExecutionFailed
from app.nodes.contracts.base import BaseConfig, BaseNode
from app.nodes.registry import register


class CodeConfig(BaseConfig):
    """Configuration for the code execution node."""

    language: Literal["python", "node"] = "python"
    code: str = Field(..., description="源代码 (Python 3.12 or Node 20)")
    input_variables: list[str] = Field(
        default_factory=list,
        description="从 inputs 注入到执行上下文的 key 列表(Phase 5 将通过 env vars 注入)",
    )
    cpu: float = Field(0.5, ge=0.1, le=4.0, description="CPU 核心数上限")
    memory_mb: int = Field(256, ge=64, le=4096, description="内存上限 (MB)")
    timeout_s: int = Field(30, ge=1, le=300, description="执行超时 (s)")


@register("code", version="1.0.0")
class CodeNode(BaseNode):
    """Node contract for the code execution node."""

    config: CodeConfig


async def code_execute(config: CodeConfig, inputs: dict) -> dict:
    """Run ``config.code`` in a Docker container with hard limits.

    Returns ``{stdout, stderr, exit_code}`` on success. On non-zero exit or
    Docker error, raises ``CodeExecutionFailed`` (boundary #2) so the runner
    can mark the node failed and decide retry/skip/fail-fast per workflow
    error policy.
    """
    s = get_settings()
    if not s.docker_sandbox_enabled:
        raise CodeExecutionFailed("Docker sandbox disabled via DOCKER_SANDBOX_ENABLED=false")
    image = "python:3.12-slim" if config.language == "python" else "node:20-slim"
    cmd = [
        "sh",
        "-c",
        "cat > /tmp/code.txt && "
        + ("python3 /tmp/code.txt" if config.language == "python" else "node /tmp/code.txt"),
    ]
    client = docker.DockerClient(base_url=f"unix://{s.docker_socket}")
    try:
        container = client.containers.run(
            image,
            command=cmd,
            stdin_open=True,
            detach=True,
            cpu_quota=int(config.cpu * 100000),
            cpu_period=100000,
            mem_limit=f"{config.memory_mb}m",
            network_mode="none",
        )
        try:
            container.wait(timeout=config.timeout_s)
        except Exception as e:
            # Timeout or other wait failure — force-remove the container so we
            # don't leak it, then re-raise as CodeExecutionFailed.
            try:
                container.remove(force=True)
            except Exception:
                pass
            raise CodeExecutionFailed(
                f"code execution timed out after {config.timeout_s}s: {type(e).__name__}: {e}"
            ) from e
        stdout = container.logs(stdout=True, stderr=False).decode()
        stderr = container.logs(stdout=False, stderr=True).decode()
        exit_code = container.attrs["State"].get("ExitCode", 0)
        container.remove(force=True)
        if exit_code != 0:
            raise CodeExecutionFailed(
                f"code execution failed (exit={exit_code}): {stderr}"
            )
        return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}
    except CodeExecutionFailed:
        raise
    except Exception as e:
        raise CodeExecutionFailed(
            f"code execution failed: {type(e).__name__}: {e}"
        ) from e


__all__ = ["CodeConfig", "CodeNode", "code_execute"]
