"""UUIDv7-style trace id generator.

Locks decision DC3 in
``openspec/changes/gateway-egress-enforcement-p0/design.md``:

* When the upstream caller provides an ``X-Trace-Id`` header the gateway
  reuses it verbatim; the generator is only used as a fallback.
* The id format is RFC 9562 UUIDv7: 48-bit millisecond timestamp in the
  high bits, 74 bits of randomness (12 bits of version/sub-clock +
  62 bits of randomness), fixed ``8`` version + ``9``/``a``/``b`` variant.

The stdlib's ``uuid.uuid7()`` is only available in Python 3.14+, so this
module ships a small, dependency-free implementation that:

* pulls the 48-bit unix-ms timestamp from ``time.time_ns()``,
* fills the random bits with ``os.urandom`` (so it's process-safe and
  not vulnerable to deterministic seeding), and
* serialises into the canonical 8-4-4-4-12 hex string.

The output is therefore 36 chars including 4 hyphens, starts with a
hex digit (the 4 most-significant bits of the timestamp), and is
lexicographically sortable by the millisecond the id was created.
"""
from __future__ import annotations

import os
import time
import uuid


def _unix_ms() -> int:
    """Return the current unix time in milliseconds (monotonic-ish)."""
    return time.time_ns() // 1_000_000


def generate_trace_id() -> str:
    """Return a fresh UUIDv7 hex string (36 chars, 4 hyphens).

    Format breakdown (RFC 9562 §5.7):

    * bits 0-47   = unix_ms (48 bits, big-endian)
    * bits 48-51  = version ``0x7``
    * bits 52-63  = 12 bits of randomness (``rand_a``)
    * bits 64-65  = variant ``0b10`` (RFC 4122)
    * bits 66-127 = 62 bits of randomness (``rand_b``)

    Stdlib ``uuid.UUID`` lets us set ``int`` + ``version=7`` and get
    the canonical hex form for free. We construct the int by hand so
    the timestamp + 74 random bits are in the right positions.
    """
    ts_ms = _unix_ms() & ((1 << 48) - 1)
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    rand_a = (rand >> 64) & 0xFFF  # 12 bits
    rand_b = rand & ((1 << 62) - 1)  # 62 bits
    uuid_int = (ts_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return str(uuid.UUID(int=uuid_int))


__all__ = ["generate_trace_id"]
