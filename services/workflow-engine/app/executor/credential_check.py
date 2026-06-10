"""Pre-flight credential access check before a workflow run starts.

The workflow runner calls ``check_credentials`` immediately after
marking the run as ``running``. If any node references a credential
the caller doesn't have access to, the run fails fast with
``SecurityError`` (boundary #4) — *before* any LLM calls, HTTP
requests, or database writes happen on the workflow's behalf.

This is cheaper and safer than per-node checks: a single 403 fails
the whole run, and the credential service is only consulted once per
``credential_id`` even if multiple nodes share the same credential.
"""
from __future__ import annotations

from app.clients.credential import CredentialClient
from app.errors.classes import SecurityError


async def check_credentials(workflow_definition: dict, started_by: str) -> None:
    """Walk every node in ``workflow_definition`` and verify credential ACLs.

    Iterates ``workflow_definition["nodes"]``; for each node whose
    ``config`` contains a ``credential_id`` field, calls the
    credential service's ``check_access(credential_id, started_by)``.

    Args:
        workflow_definition: Canvas JSON (nodes + edges + variables).
        started_by: User id of the workflow run starter.

    Raises:
        SecurityError: when a credential is not accessible. The message
            names the offending ``credential_id`` and the user, so the
            audit log captures who tried to use what.
    """
    client = CredentialClient()
    try:
        for n in workflow_definition.get("nodes", []):
            cfg = n.get("config") or {}
            cid = cfg.get("credential_id")
            if not cid:
                continue
            allowed = await client.check_access(cid, started_by)
            if not allowed:
                raise SecurityError(
                    f"无权限访问凭证 {cid!r}。"
                    f"workflow 启动方 {started_by!r} 不在该凭证的访问列表中。"
                )
    finally:
        await client.aclose()


__all__ = ["check_credentials"]
