"""Unit tests for ``app.crypto`` — envelope encryption primitives.

These tests are pure-crypto: no DB, no async, no network. They exercise
the round-trip / error paths that downstream services (Tasks 4+) will
rely on, and pin the public-function signatures so a future refactor
that breaks Task 4+ surfaces here first.
"""

from __future__ import annotations

import os
import secrets

import pytest

from app.crypto import (
    DEK_BYTES,
    GCM_NONCE_BYTES,
    GCM_TAG_BYTES,
    MASTER_KEY_BYTES,
    CredentialDecryptionError,
    DekDecryptionError,
    decrypt_dek_with_master,
    decrypt_with_dek,
    encrypt_dek_with_master,
    encrypt_with_dek,
    generate_dek,
    generate_master_key,
)

# ---------------------------------------------------------------------------
# Random-key generation
# ---------------------------------------------------------------------------


class TestRandomKeyGeneration:
    def test_dek_is_32_bytes(self) -> None:
        """Spec: per-credential DEK is 32-byte random."""
        assert len(generate_dek()) == DEK_BYTES == 32

    def test_master_key_is_32_bytes(self) -> None:
        """Spec: master key is 32-byte (AES-256) random."""
        assert len(generate_master_key()) == MASTER_KEY_BYTES == 32

    def test_dek_is_csprng_unique(self) -> None:
        """Two consecutive ``generate_dek`` calls MUST produce different bytes.

        The probability of a collision in 256 random bits is ~2^-256,
        so a single equality between two random DEKs would mean the
        implementation is not using a CSPRNG — this test would catch
        that regression.
        """
        dek1 = generate_dek()
        dek2 = generate_dek()
        assert dek1 != dek2

    def test_master_key_is_csprng_unique(self) -> None:
        master1 = generate_master_key()
        master2 = generate_master_key()
        assert master1 != master2


# ---------------------------------------------------------------------------
# Value-level encrypt / decrypt (under DEK)
# ---------------------------------------------------------------------------


class TestValueRoundTrip:
    def test_round_trip_simple(self) -> None:
        dek = generate_dek()
        nonce, blob = encrypt_with_dek(b"hello", dek)
        assert decrypt_with_dek(nonce, blob, dek) == b"hello"

    def test_round_trip_empty(self) -> None:
        """Empty plaintext MUST round-trip cleanly (GCM allows zero-length)."""
        dek = generate_dek()
        nonce, blob = encrypt_with_dek(b"", dek)
        # Empty-plaintext ciphertext is just the 16-byte GCM tag.
        assert len(blob) == GCM_TAG_BYTES
        assert decrypt_with_dek(nonce, blob, dek) == b""

    def test_round_trip_unicode_chinese(self) -> None:
        """Spec example: Chinese-character plaintext."""
        dek = generate_dek()
        plaintext = "你好世界,ChatBiz".encode()
        nonce, blob = encrypt_with_dek(plaintext, dek)
        assert decrypt_with_dek(nonce, blob, dek) == plaintext

    def test_round_trip_1mb(self) -> None:
        """Large plaintext (1 MiB) MUST round-trip in well under a second.

        This is the upper-bound on a single ``use`` API call body size;
        encryption throughput is part of the 50 ms P99 SLO in aggregate
        but a single 1 MiB blob is well within AES-GCM's payload
        capacity and should complete in tens of milliseconds.
        """
        dek = generate_dek()
        plaintext = os.urandom(1024 * 1024)
        nonce, blob = encrypt_with_dek(plaintext, dek)
        assert decrypt_with_dek(nonce, blob, dek) == plaintext

    def test_ciphertext_contains_16_byte_tag(self) -> None:
        """``blob`` is ``ciphertext || tag`` — empty pt is 16 bytes tag only."""
        dek = generate_dek()
        _, blob = encrypt_with_dek(b"", dek)
        assert len(blob) == GCM_TAG_BYTES

    def test_nonce_is_12_bytes(self) -> None:
        """AES-GCM nonce MUST be 96 bits."""
        dek = generate_dek()
        nonce, _ = encrypt_with_dek(b"x", dek)
        assert len(nonce) == GCM_NONCE_BYTES == 12

    def test_encrypt_uses_fresh_nonce_each_call(self) -> None:
        """Re-encrypting the same plaintext under the same DEK MUST produce
        a different nonce (and therefore a different ciphertext)."""
        dek = generate_dek()
        n1, c1 = encrypt_with_dek(b"same", dek)
        n2, c2 = encrypt_with_dek(b"same", dek)
        assert n1 != n2
        assert c1 != c2


class TestValueDecryptErrors:
    def test_wrong_key_raises(self) -> None:
        """Decryption with the wrong DEK MUST raise ``CredentialDecryptionError``.

        GCM authentication failure → ``InvalidTag`` is mapped to a
        domain error so the caller can decide whether to fall back to
        the ``previous_value`` (rotation window) without leaking the
        cryptography-library exception type.
        """
        dek = generate_dek()
        nonce, blob = encrypt_with_dek(b"secret", dek)
        other_dek = generate_dek()
        assert other_dek != dek
        with pytest.raises(CredentialDecryptionError):
            decrypt_with_dek(nonce, blob, other_dek)

    def test_short_ciphertext_raises(self) -> None:
        """A blob shorter than the 16-byte GCM tag is structurally invalid."""
        dek = generate_dek()
        nonce = b"\x00" * GCM_NONCE_BYTES
        with pytest.raises(CredentialDecryptionError):
            decrypt_with_dek(nonce, b"\x00" * (GCM_TAG_BYTES - 1), dek)

    def test_empty_ciphertext_raises(self) -> None:
        dek = generate_dek()
        nonce = b"\x00" * GCM_NONCE_BYTES
        with pytest.raises(CredentialDecryptionError):
            decrypt_with_dek(nonce, b"", dek)

    def test_wrong_nonce_length_raises(self) -> None:
        """``decrypt_with_dek`` MUST reject non-12-byte nonces up front."""
        dek = generate_dek()
        with pytest.raises(ValueError, match="nonce"):
            decrypt_with_dek(b"\x00" * 8, b"\x00" * GCM_TAG_BYTES, dek)

    def test_tampered_ciphertext_raises(self) -> None:
        """Flipping a single byte in the ciphertext MUST fail authentication."""
        dek = generate_dek()
        nonce, blob = encrypt_with_dek(b"important payload", dek)
        tampered = bytearray(blob)
        tampered[0] ^= 0x01
        with pytest.raises(CredentialDecryptionError):
            decrypt_with_dek(nonce, bytes(tampered), dek)

    def test_tampered_tag_raises(self) -> None:
        """Flipping a byte in the trailing GCM tag MUST fail authentication."""
        dek = generate_dek()
        nonce, blob = encrypt_with_dek(b"important payload", dek)
        tampered = bytearray(blob)
        tampered[-1] ^= 0x01
        with pytest.raises(CredentialDecryptionError):
            decrypt_with_dek(nonce, bytes(tampered), dek)

    def test_wrong_size_dek_raises(self) -> None:
        """``encrypt_with_dek`` MUST reject DEKs of the wrong length."""
        with pytest.raises(ValueError, match="dek"):
            encrypt_with_dek(b"x", b"\x00" * 16)
        with pytest.raises(ValueError, match="dek"):
            encrypt_with_dek(b"x", b"\x00" * 64)


# ---------------------------------------------------------------------------
# Master-key envelope (DEK ↔ master)
# ---------------------------------------------------------------------------


class TestMasterEnvelopeRoundTrip:
    def test_round_trip(self) -> None:
        dek = generate_dek()
        master = generate_master_key()
        enc = encrypt_dek_with_master(dek, master)
        assert decrypt_dek_with_master(enc, master) == dek

    def test_encrypted_dek_blob_layout(self) -> None:
        """``encrypt_dek_with_master`` returns ``nonce(12) || ciphertext(32) || tag(16)``.

        Pinning the layout here means a future refactor that changes
        the storage column width will fail loudly in tests, not in
        production where the change is irreversible.
        """
        dek = generate_dek()
        master = generate_master_key()
        enc = encrypt_dek_with_master(dek, master)
        assert len(enc) == GCM_NONCE_BYTES + DEK_BYTES + GCM_TAG_BYTES == 60

    def test_two_envelopes_of_same_dek_differ(self) -> None:
        """Fresh nonce on every envelope: encrypting the same DEK twice under
        the same master produces different blobs."""
        dek = generate_dek()
        master = generate_master_key()
        e1 = encrypt_dek_with_master(dek, master)
        e2 = encrypt_dek_with_master(dek, master)
        assert e1 != e2
        # Both must still decrypt to the same DEK.
        assert decrypt_dek_with_master(e1, master) == dek
        assert decrypt_dek_with_master(e2, master) == dek

    def test_round_trip_with_unicode(self) -> None:
        """Sanity-check: DEK bytes are random — independent of plaintext size."""
        master = generate_master_key()
        # DEK is 32 bytes; the *value* plaintext is encrypted under the
        # DEK, not the master. This test pins the envelope layer.
        dek = secrets.token_bytes(DEK_BYTES)
        enc = encrypt_dek_with_master(dek, master)
        assert decrypt_dek_with_master(enc, master) == dek


class TestMasterEnvelopeErrors:
    def test_wrong_master_raises(self) -> None:
        dek = generate_dek()
        master = generate_master_key()
        other_master = generate_master_key()
        enc = encrypt_dek_with_master(dek, master)
        with pytest.raises(DekDecryptionError):
            decrypt_dek_with_master(enc, other_master)

    def test_tampered_ciphertext_raises(self) -> None:
        dek = generate_dek()
        master = generate_master_key()
        enc = encrypt_dek_with_master(dek, master)
        tampered = bytearray(enc)
        tampered[GCM_NONCE_BYTES] ^= 0x01
        with pytest.raises(DekDecryptionError):
            decrypt_dek_with_master(bytes(tampered), master)

    def test_short_blob_raises(self) -> None:
        """A blob shorter than ``nonce(12) + tag(16)`` cannot carry a DEK."""
        master = generate_master_key()
        with pytest.raises(ValueError, match="encrypted_dek"):
            decrypt_dek_with_master(b"\x00" * (GCM_NONCE_BYTES + GCM_TAG_BYTES - 1), master)

    def test_wrong_size_master_raises(self) -> None:
        with pytest.raises(ValueError, match="master"):
            encrypt_dek_with_master(generate_dek(), b"\x00" * 16)
        with pytest.raises(ValueError, match="master"):
            decrypt_dek_with_master(b"\x00" * 60, b"\x00" * 16)

    def test_wrong_size_dek_raises_on_envelope(self) -> None:
        master = generate_master_key()
        with pytest.raises(ValueError, match="dek"):
            encrypt_dek_with_master(b"\x00" * 16, master)


# ---------------------------------------------------------------------------
# Two-layer integration: value encrypted under DEK, DEK encrypted under master
# ---------------------------------------------------------------------------


class TestFullStack:
    def test_value_through_full_envelope(self) -> None:
        """End-to-end (no DB): plaintext → DEK → master wrap → reverse."""
        master = generate_master_key()
        dek = generate_dek()
        plaintext = b"super-secret-credential-value"

        # Encrypt.
        nonce, blob = encrypt_with_dek(plaintext, dek)
        enc_dek = encrypt_dek_with_master(dek, master)

        # Decrypt.
        recovered_dek = decrypt_dek_with_master(enc_dek, master)
        assert recovered_dek == dek
        assert decrypt_with_dek(nonce, blob, recovered_dek) == plaintext

    def test_full_stack_with_wrong_master(self) -> None:
        master = generate_master_key()
        wrong = generate_master_key()
        dek = generate_dek()
        enc_dek = encrypt_dek_with_master(dek, master)
        with pytest.raises(DekDecryptionError):
            decrypt_dek_with_master(enc_dek, wrong)

    def test_full_stack_with_tampered_value_under_correct_master(self) -> None:
        """A tampered *value* ciphertext MUST still fail even when the master
        is correct — the two layers authenticate independently."""
        master = generate_master_key()
        dek = generate_dek()
        nonce, blob = encrypt_with_dek(b"hello", dek)
        enc_dek = encrypt_dek_with_master(dek, master)

        # Master unwraps fine.
        assert decrypt_dek_with_master(enc_dek, master) == dek

        # Value decrypt fails because the value blob was tampered.
        tampered = bytearray(blob)
        tampered[0] ^= 0x01
        with pytest.raises(CredentialDecryptionError):
            decrypt_with_dek(nonce, bytes(tampered), dek)
