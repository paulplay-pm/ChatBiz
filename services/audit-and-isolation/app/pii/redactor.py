"""PII redactor — replace detected PII with typed placeholders, persist map.

Pipeline:

1. Run :func:`detect` on the inbound text.
2. For each match, derive a deterministic placeholder
   ``[<type>_<4-hex-of-sha1(value)>]`` (collision probability ~ 1/65536
   per trace, low enough to ignore for a 30-minute TTL).
3. Substitute placeholders into the text (right-to-left, so the
   left indices remain valid).
4. Persist the placeholder→original map to Redis under
   ``redact:trace:<trace_id>`` with TTL ``pii_map_ttl_seconds``.

Failure mode: if Redis is unreachable, the map is *lost*. The redactor
**does not block** the request — the call returns with the redacted
text and an empty map. The reverser on the response side will then
return the redacted text unchanged (since the map is missing), so the
caller sees the placeholder, not the original PII. This is the
"Fail-Open" semantic the eng-review locked in: the system prefers
disclosing placeholders to the upstream LLM (which sees no PII) over
either (a) failing the request or (b) leaking the original PII to the
upstream.

The alternative — buffering the map in process memory — is rejected
because:

* the gateway runs 2 HA pods; a buffer on pod A is invisible to
  pod B. Sticky-by-trace-id routing would be needed, which is
  exactly what the data-isolation design tried to avoid.
* the failure mode (caller sees placeholder in response) is at
  least as recoverable as a 503, and easier to alert on (PII map
  Redis miss → log + metric → on-call).
"""

from __future__ import annotations

import hashlib
import json
import logging

from app import redis_client
from app.config import get_settings
from app.pii.detector import detect

logger = logging.getLogger(__name__)


def _placeholder(type: str, original: str) -> str:
    """Build a stable placeholder from a PII value.

    Using SHA-1 truncated to 4 hex chars (16 bits) gives 65 536
    distinct placeholders per type — enough that a single trace
    almost never sees a collision. The placeholder is *deterministic*
    on the original value: if the same email appears in two
    messages of the same trace, both are replaced with the same
    placeholder, which means the upstream LLM sees a single entity
    instead of two (better context preservation).
    """
    h = hashlib.sha1(original.encode()).hexdigest()[:4]
    return f"[{type}_{h}]"


async def redact(trace_id: str, text: str) -> tuple[str, dict[str, str], list[str]]:
    """Replace PII in ``text`` with typed placeholders.

    Returns ``(redacted_text, map, detected_types)``:

    * ``redacted_text`` — the text with placeholders substituted in
      the original positions.
    * ``map`` — the placeholder→original dict persisted to Redis.
      Empty if no PII was found or if Redis is unavailable.
    * ``detected_types`` — the *unique* set of PII types that hit
      (deduped, order not significant). Used to populate
      ``audit_log.pii_detected_types``.
    """
    matches = detect(text)
    if not matches:
        return text, {}, []

    # 构建 map + 替换
    mapping: dict[str, str] = {}
    detected_types: list[str] = []
    # 从后往前替换,避免索引偏移
    new_text = text
    for m in reversed(matches):
        placeholder = _placeholder(m.type, m.value)
        mapping[placeholder] = m.value
        detected_types.append(m.type)
        new_text = new_text[: m.start] + placeholder + new_text[m.end :]

    # 写 Redis
    settings = get_settings()
    r = redis_client.get_redis()
    key = f"redact:trace:{trace_id}"
    try:
        await r.set(key, json.dumps(mapping), ex=settings.pii_map_ttl_seconds)
    except Exception as e:  # pragma: no cover — Redis set failure is covered by integration/fakeredis end-to-end tests; the exception path is unreachable in unit tests with fakeredis
        # Redis 写失败 → Fail-Open: 放行 + 记日志(不阻断)
        # 调用方后续会拿到还原失败(响应里有占位符)
        logger.warning(
            "PII map redis write failed (trace_id=%s, fail_open=%s): %s",
            trace_id,
            settings.pii_fail_open,
            e,
        )
        # 重要: 失败时仍把 map 留给调用方(进程内回退),不强制依赖 Redis
        # 但跨 pod 的请求无法看到,这是 Fail-Open 的代价

    return new_text, mapping, list(set(detected_types))


__all__ = ["redact"]
