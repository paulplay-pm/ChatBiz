"""SHA-256 hashing of the post-redaction message list.

The audit log is **metadata-only** — the original prompt body
NEVER reaches the database (eng-review #1 lock-in). To make the
audit log queryable ("show me all requests whose redacted prompt
matches this hash") we compute a deterministic SHA-256 hex digest
of the message list and store it as ``audit_log.prompt_hash``.

Determinism requirements:

* Use ``orjson.dumps`` (not the stdlib ``json``) — the gateway
  is already orjson-everywhere, and orjson's default mode has no
  trailing whitespace and uses sorted dict keys, giving a stable
  byte layout.
* Hash the *list* (preserves order — message order matters for
  chat context) and serialise the role+content fields only
  (skipping the ``name`` and ``function_call`` extensions that
  the OpenAI schema accepts but the gateway doesn't redactor).
* Lowercase + hex — the SQL column is ``CHAR(64)`` (sha256 hex
  is 64 lowercase hex chars), so case matters for the column
  width.
"""

from __future__ import annotations

import hashlib

import orjson


def prompt_hash(redacted_messages: list) -> str:
    """Return the SHA-256 hex digest of the redacted message list.

    The list is serialised with ``orjson.dumps`` and hashed. The
    function is pure (no I/O) and stable across processes.
    """
    payload = orjson.dumps(redacted_messages)
    return hashlib.sha256(payload).hexdigest()


__all__ = ["prompt_hash"]
