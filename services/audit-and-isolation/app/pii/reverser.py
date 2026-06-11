"""PII reverser — swap placeholders in upstream response back to originals.

The reverser is the *mirror image* of the redactor. It reads the
trace-keyed map from Redis (populated by :mod:`app.pii.redactor`) and
applies string replacement to the response text. If the map is
missing (TTL expired, Redis evicted, or the original redactor's
write failed), the reverser returns the redacted text unchanged —
which means the caller sees the placeholder, not the original PII.
This is Fail-Open in the conservative direction: we prefer showing
``[身份证_ab12]`` to the caller over either (a) crashing the
response or (b) re-running the detector on the response (which
would re-detect the original PII in the *caller's* context, but
only if the LLM echoed it back — a fragile signal at best).
"""

from __future__ import annotations

import json
import logging

from app import redis_client

logger = logging.getLogger(__name__)


async def reverse(trace_id: str, text: str) -> str:
    """Restore the original PII values in ``text`` for ``trace_id``.

    Returns ``text`` unchanged in three cases:

    * ``text`` contains no ``[`` character (cheap short-circuit;
      virtually all real LLM responses contain a bracket somewhere,
      but model boilerplate like ``"OK"`` should not pay the Redis
      round-trip).
    * Redis is unreachable (Fail-Open).
    * The map is missing (TTL expired or never written).

    The actual swap is a plain ``str.replace`` loop, not a regex
    scan: the placeholders are pre-escaped by :func:`_placeholder`
    (only ``[``, ``]``, type label, and 4 hex chars) so no
    regex-escape concerns apply, and ``str.replace`` is faster
    than a ``re.sub`` with a callback for the typical case of
    fewer than 10 placeholders per response.
    """
    if "[" not in text:
        return text
    r = redis_client.get_redis()
    try:
        raw = await r.get(f"redact:trace:{trace_id}")
    except Exception as e:
        # Fail-Open: Redis 挂 → 返回原文(占位符)
        logger.warning("PII reverser redis read failed (trace_id=%s): %s", trace_id, e)
        return text
    if not raw:
        return text
    try:
        mapping = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as e:  # pragma: no cover — json.loads with a non-JSON str from fakeredis raises JSONDecodeError; this path is verified by integration integration tests.
        logger.warning("PII reverser map parse failed (trace_id=%s): %s", trace_id, e)
        return text
    # 替换占位符
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text


__all__ = ["reverse"]
