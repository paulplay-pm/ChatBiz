"""HTTP clients for upstream ChatBiz services.

Each client is a thin wrapper around ``httpx.AsyncClient`` with three
behaviours that match the audit-and-isolation gateway:

1. **Lazy singleton client.** A per-instance ``httpx.AsyncClient`` is
   reused across requests so the underlying connection pool (and its
   TLS sessions) survives.
2. **Service token header.** Every call carries
   ``X-Service-Token: <workflow_engine_service_token>`` so the
   downstream service can authenticate the workflow-engine caller.
3. **Trace-id header.** Outgoing calls propagate
   ``X-Trace-Id: wf-trace`` so cross-service traces can be correlated
   in the audit-and-isolation log.

Callers should construct a client once at app startup (e.g. via
FastAPI lifespan), share it for the process lifetime, and call
``aclose()`` on shutdown. The clients are *not* module-level
singletons because that complicates test setup; lifespan-based
lifecycle is the same pattern FastAPI itself uses.
"""

from app.clients.audit_isolation import AuditIsolationClient
from app.clients.credential import CredentialClient
from app.clients.knowledge_base import KnowledgeBaseClient
from app.clients.agent_runtime import AgentRuntimeClient

__all__ = [
    "AuditIsolationClient",
    "CredentialClient",
    "KnowledgeBaseClient",
    "AgentRuntimeClient",
]
