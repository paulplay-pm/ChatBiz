"""Unit tests for ``app.errors``.

The 7-class exception taxonomy is the contract between the API
boundary and the operator. The tests in this file guarantee:

* Each class is a real ``Exception`` subclass (catches in
  ``chat.py`` will actually fire).
* The classes are distinct (a ``PIIDetectorUnavailable`` is
  not also a ``Upstream5xx``).
* :func:`error_response` returns a dict that matches the
  ``ErrorResponse`` Pydantic schema, so a FastAPI exception
  handler can pass it straight into ``JSONResponse(**...)``.

One test per class — a small but explicit matrix that catches
the most common refactoring mistake: collapsing two related
classes into one and silently breaking the error metric
labels.
"""

from __future__ import annotations

import unittest

from app.errors import (
    AuthFailed,
    CredentialServiceUnavailable,
    PIIDetectorUnavailable,
    RedisUnavailable,
    Upstream5xx,
    UpstreamRateLimited,
    UpstreamTimeout,
    error_response,
)


class TestExceptionClasses(unittest.TestCase):
    """Each of the 7 classes is a real, distinct ``Exception``."""

    def test_pii_detector_unavailable(self):
        with self.assertRaises(PIIDetectorUnavailable):
            raise PIIDetectorUnavailable("regex crashed")
        self.assertTrue(issubclass(PIIDetectorUnavailable, Exception))

    def test_upstream_5xx(self):
        with self.assertRaises(Upstream5xx):
            raise Upstream5xx("500 from qwen")
        self.assertTrue(issubclass(Upstream5xx, Exception))

    def test_upstream_timeout(self):
        with self.assertRaises(UpstreamTimeout):
            raise UpstreamTimeout("30s elapsed")
        self.assertTrue(issubclass(UpstreamTimeout, Exception))

    def test_upstream_rate_limited(self):
        with self.assertRaises(UpstreamRateLimited):
            raise UpstreamRateLimited("429")
        self.assertTrue(issubclass(UpstreamRateLimited, Exception))

    def test_credential_service_unavailable(self):
        with self.assertRaises(CredentialServiceUnavailable):
            raise CredentialServiceUnavailable("conn refused")
        self.assertTrue(issubclass(CredentialServiceUnavailable, Exception))

    def test_redis_unavailable(self):
        with self.assertRaises(RedisUnavailable):
            raise RedisUnavailable("pool exhausted")
        self.assertTrue(issubclass(RedisUnavailable, Exception))

    def test_auth_failed(self):
        with self.assertRaises(AuthFailed):
            raise AuthFailed("bad token")
        self.assertTrue(issubclass(AuthFailed, Exception))

    def test_classes_are_distinct(self):
        """No two of the 7 should be the same class — important
        because the API layer uses ``except (ClassA, ClassB)``
        blocks and a merge would silently broaden the catch."""
        all_classes = {
            PIIDetectorUnavailable,
            Upstream5xx,
            UpstreamTimeout,
            UpstreamRateLimited,
            CredentialServiceUnavailable,
            RedisUnavailable,
            AuthFailed,
        }
        self.assertEqual(len(all_classes), 7)


class TestErrorResponse(unittest.TestCase):
    """``error_response`` returns the canonical ``ErrorResponse`` dict."""

    def test_basic_envelope(self):
        out = error_response(503, "CredentialServiceUnavailable", "down")
        self.assertEqual(out["status_code"], 503)
        self.assertEqual(out["body"]["error_class"], "CredentialServiceUnavailable")
        self.assertEqual(out["body"]["message"], "down")
        self.assertIsNone(out["body"]["trace_id"])

    def test_with_trace_id(self):
        out = error_response(
            504, "UpstreamTimeout", "timeout", trace_id="01HX_TRACE_123"
        )
        self.assertEqual(out["status_code"], 504)
        self.assertEqual(out["body"]["trace_id"], "01HX_TRACE_123")

    def test_envelope_keys(self):
        """The body must contain exactly the three keys
        ``ErrorResponse`` declares (and no extras)."""
        out = error_response(500, "X", "Y")
        self.assertEqual(set(out["body"].keys()), {"error_class", "message", "trace_id"})


if __name__ == "__main__":
    unittest.main()
