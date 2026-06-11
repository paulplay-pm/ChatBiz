"""Unit tests for the UUIDv7 trace id generator.

Covers:

* Output is 36 chars, 4 hyphens, 5 hex groups.
* First group encodes unix-ms timestamp in the high bits — the
  string is therefore roughly time-sortable.
* Two consecutive calls produce different ids (74 bits of randomness).
* Output is a valid :class:`uuid.UUID` with ``version == 7`` and
  the RFC 4122 variant set.
"""
from __future__ import annotations

import time
import uuid

from app.trace.id_gen import generate_trace_id


def test_format_is_canonical_uuid():
    """The id is 36 chars, 4 hyphens, and parses as a UUID."""
    tid = generate_trace_id()
    assert len(tid) == 36
    assert tid.count("-") == 4
    parsed = uuid.UUID(tid)
    # The hex string round-trips back to itself
    assert str(parsed) == tid


def test_version_is_7():
    """The UUID's version nibble (high 4 bits of group 3) is 7."""
    parsed = uuid.UUID(generate_trace_id())
    assert parsed.version == 7


def test_variant_is_rfc4122():
    """The variant nibble (high 2 bits of group 4) is 0b10."""
    parsed = uuid.UUID(generate_trace_id())
    # variant 0b10 == RFC 4122 ("specified"). The uuid lib exposes it
    # as the string "specified in RFC 4122" on Python 3.12.
    assert parsed.variant in {"specified", "specified in RFC 4122"}


def test_consecutive_ids_differ():
    """Two back-to-back calls produce different ids."""
    a = generate_trace_id()
    b = generate_trace_id()
    assert a != b


def test_timestamp_embedded_in_high_bits():
    """The first 48 bits are the unix-ms timestamp at generation time."""
    before_ms = int(time.time() * 1000)
    tid = generate_trace_id()
    after_ms = int(time.time() * 1000) + 1
    # The first 12 hex chars (group 1) are the high 48 bits of the int.
    ts_in_id = int(tid.split("-", 1)[0], 16)
    # ``UUID.timestamp`` is the unix timestamp in seconds (not ms), so we
    # re-derive ms from the int for the comparison.
    uuid_int = uuid.UUID(tid).int
    ts_ms_from_uuid = (uuid_int >> 80) & ((1 << 48) - 1)
    assert before_ms <= ts_ms_from_uuid <= after_ms, (
        f"timestamp {ts_ms_from_uuid} not in [{before_ms}, {after_ms}]"
    )
