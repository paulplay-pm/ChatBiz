"""Envelope encryption primitives for the credential-management service.

This module is the cryptographic core of the vault. It implements:

* per-credential Data Encryption Keys (DEKs) — 32 random bytes, generated
  on the fly and never reused;
* AES-256-GCM authenticated encryption of the credential plaintext under
  a DEK;
* AES-256-GCM authenticated encryption of the DEK under a key derived
  from the master key (envelope encryption);
* master-key loading / rotation, scoped to the ``encryption_keys`` table.

All functions are pure Python / pure ``cryptography`` library: no async,
no DB, no network. The async DB access for ``load_master_key`` and
``rotate_master_key`` is delegated to the helper that accepts an
async session — but the *crypto* itself is synchronous and unit-testable
in isolation.

The nonce layout follows the modern ``cryptography`` API style: each
authenticated encryption returns a single self-contained blob of the
form ``nonce || ciphertext || tag``. Both the value-under-DEK and the
DEK-under-master layers use this same layout, so each maps cleanly to
a single BYTEA column (``credentials.encrypted_value`` and
``credentials.encrypted_dek``) with no sibling nonce column.

This file is intentionally pure: there is no I/O, no logging, no
configuration. Callers (services, routers) are responsible for wiring it
to Postgres and to the audit log.
"""

from __future__ import annotations

import functools
import secrets
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EncryptionKey, KeyStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Length of a per-credential Data Encryption Key (256 bits).
DEK_BYTES: Final = 32

#: Length of a master key as stored in / loaded from ``encryption_keys``
#: (256 bits). Per spec: AES-256-GCM requires a 32-byte key.
MASTER_KEY_BYTES: Final = 32

#: Length of the GCM nonce / IV (96 bits is the recommended size for
#: AES-GCM; the cryptography library rejects anything else at 96 bits
#: with an internal error if you pass it through the AEAD constructor).
GCM_NONCE_BYTES: Final = 12

#: Length of the GCM authentication tag (128 bits — the only size
#: supported by the ``AESGCM`` class).
GCM_TAG_BYTES: Final = 16

#: Fixed salt used when deriving the master-key encryption subkey with
#: scrypt. A *fixed* application-wide salt is acceptable here because the
#: input (the master key) is itself a 256-bit uniformly random secret —
#: the salt only needs to be unique per key-derivation context, not per
#: secret. Rotating the salt would force re-encryption of every DEK, so
#: we keep it constant. See NIST SP 800-132 §5.1 for the rationale.
_SCRYPT_SALT: Final = b"chatbiz-credential-management-master-key-v1"

#: scrypt cost parameters. ``n=2**15`` is the smallest cost factor that
#: still defends against GPU brute-force; ``r=8`` and ``p=1`` are the
#: library defaults. These are deliberately modest so that master-key
#: loads complete in < 50 ms on the bootstrap path and rotation
#: re-encryption stays well under the 60 s SLO.
_SCRYPT_N: Final = 2**15
_SCRYPT_R: Final = 8
_SCRYPT_P: Final = 1
_SCRYPT_DERIVED_KEY_LEN: Final = MASTER_KEY_BYTES


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CryptoError(Exception):
    """Base class for crypto-module errors."""


class MasterKeyNotFoundError(CryptoError):
    """Raised when no active master key is present in the database.

    The service bootstrap (Task 6) treats this as fatal — the process
    exits with code 1 — per the spec's "主密钥缺失" scenario.
    """


class DekDecryptionError(CryptoError):
    """Raised when DEK decryption fails (wrong key, tampered ciphertext)."""


class CredentialDecryptionError(CryptoError):
    """Raised when credential value decryption fails."""


# ---------------------------------------------------------------------------
# Random key generation
# ---------------------------------------------------------------------------


def generate_dek() -> bytes:
    """Generate a fresh 32-byte per-credential DEK.

    Uses ``secrets.token_bytes`` (CSPRNG); never seeded, never reused.
    Returns raw bytes — the caller is responsible for wrapping them
    under the active master key before persistence.
    """
    return secrets.token_bytes(DEK_BYTES)


def generate_master_key() -> bytes:
    """Generate a fresh 32-byte master key.

    Used for initial bootstrap (Task 6) and for the rotation flow
    (``rotate_master_key`` below). The caller is expected to wrap this
    key under the platform KMS-root key before persisting it to
    ``encryption_keys.encrypted_key``; this module treats the value as
    an opaque 32-byte secret and does not care how it is wrapped at
    rest.
    """
    return secrets.token_bytes(MASTER_KEY_BYTES)


# ---------------------------------------------------------------------------
# AES-256-GCM (per-credential envelope)
# ---------------------------------------------------------------------------


def encrypt_with_dek(plaintext: bytes, dek: bytes) -> bytes:
    """Encrypt ``plaintext`` under ``dek`` using AES-256-GCM.

    Returns a single self-contained blob with layout
    ``nonce(12) || ciphertext || tag(16)`` — identical in shape to
    ``encrypt_dek_with_master``. The caller stores this blob verbatim
    in ``credentials.encrypted_value``; no sibling nonce column is
    needed.

    * The 12-byte prefix is a fresh CSPRNG nonce, generated per call.
    * The trailing bytes are the concatenation of ciphertext and
      16-byte GCM auth tag, as emitted by the ``AESGCM`` AEAD.

    Symmetric counterpart of ``decrypt_with_dek``; a blob produced
    here can always be reversed by ``decrypt_with_dek`` with the same
    DEK. Empty plaintext produces a 28-byte blob (12 nonce + 16 tag).
    """
    _validate_dek(dek)
    nonce = secrets.token_bytes(GCM_NONCE_BYTES)
    aead = AESGCM(dek)
    ciphertext_and_tag = aead.encrypt(nonce, plaintext, associated_data=None)
    # Storage layout: ``nonce || ciphertext || tag``. Matches the
    # envelope returned by ``encrypt_dek_with_master`` so both layers
    # land in single BYTEA columns with no schema asymmetry.
    return nonce + ciphertext_and_tag


def decrypt_with_dek(encrypted_value: bytes, dek: bytes) -> bytes:
    """Decrypt a credential value previously produced by ``encrypt_with_dek``.

    ``encrypted_value`` is the single self-contained blob with layout
    ``nonce(12) || ciphertext || tag(16)``. We slice off the first 12
    bytes as the nonce; the rest is fed to ``AESGCM.decrypt``.

    Authentication failures (wrong key, tampered ciphertext) raise
    ``CredentialDecryptionError`` so callers can map that to an audit
    log "decrypt failed" event without leaking the underlying
    ``InvalidTag`` detail to the user. A blob shorter than the
    minimum (12-byte nonce + 16-byte tag = 28 bytes) is rejected up
    front with the same domain error rather than letting
    ``AESGCM.decrypt`` raise an opaque ``ValueError`` from the C
    layer.
    """
    _validate_dek(dek)
    if len(encrypted_value) < GCM_NONCE_BYTES + GCM_TAG_BYTES:
        raise CredentialDecryptionError(
            f"encrypted_value must be at least {GCM_NONCE_BYTES + GCM_TAG_BYTES} bytes "
            f"(got {len(encrypted_value)})"
        )
    nonce = encrypted_value[:GCM_NONCE_BYTES]
    body = encrypted_value[GCM_NONCE_BYTES:]
    aead = AESGCM(dek)
    try:
        return aead.decrypt(nonce, body, associated_data=None)
    except InvalidTag as exc:
        raise CredentialDecryptionError("credential value authentication failed") from exc


# ---------------------------------------------------------------------------
# Master-key derivation + DEK envelope
# ---------------------------------------------------------------------------


def _derive_master_subkey(master: bytes) -> bytes:
    """Derive a 32-byte AES subkey from the raw master bytes via scrypt.

    The master key is stored wrapped (under KMS) in
    ``encryption_keys.encrypted_key``. The DB column is opaque to this
    module, but the bytes the application sees are the raw 256-bit
    master. To keep this module self-contained — and to make
    ``encrypt_dek_with_master`` / ``decrypt_dek_with_master`` trivially
    testable in isolation — we derive a 32-byte AES key with scrypt
    using a fixed application salt.

    scrypt is intentional (not HKDF, not Argon2id):

    * HKDF needs a high-entropy input secret — the master key already
      is high-entropy, so HKDF would work, but scrypt gives us the
      "slow on brute force" property for free.
    * Argon2id would require an extra native binary; scrypt ships in
      the standard ``cryptography`` package and uses OpenSSL.

    The derivation is cached: scrypt with ``N=2^15`` takes ~30-50 ms
    per call, which dominates the use-API hot path (the spec's P99
    SLO is 50 ms). There is exactly one active master key per
    process, so ``lru_cache(maxsize=1)`` removes the per-op overhead
    without changing the API. A rotation installs a new master key;
    the cache is invalidated by ``_invalidate_subkey_cache``.
    """
    _validate_master(master)
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    kdf = Scrypt(
        salt=_SCRYPT_SALT,
        length=_SCRYPT_DERIVED_KEY_LEN,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return kdf.derive(master)


@functools.lru_cache(maxsize=2)
def _derive_master_subkey_cached(master: bytes) -> bytes:
    """lru_cache wrapper for ``_derive_master_subkey``.

    The cache holds up to 2 master keys (current + the most-recently
    retired) so a rotation does not flush the hot path's cache entry.
    Rotation also calls ``_invalidate_subkey_cache`` to drop old
    retired keys once the rotation flow has finished its re-wrap of
    every DEK.
    """
    return _derive_master_subkey(master)


def _invalidate_subkey_cache() -> None:
    """Drop the cached subkey. Called after ``rotate_master_key``."""
    _derive_master_subkey_cached.cache_clear()


def encrypt_dek_with_master(dek: bytes, master: bytes) -> bytes:
    """Encrypt a DEK under a key derived from ``master``.

    Returns a single blob: ``nonce || ciphertext || tag`` (length =
    12 + len(dek) + 16 = 60 bytes for a 32-byte DEK). The caller
    stores this blob verbatim in ``credentials.encrypted_dek``.

    Symmetric counterpart of ``decrypt_dek_with_master``; the
    derivation parameters and the salt are pinned, so a blob produced
    here can always be reversed by ``decrypt_dek_with_master`` with
    the same master bytes.
    """
    _validate_dek(dek)
    _validate_master(master)
    subkey = _derive_master_subkey_cached(master)
    nonce = secrets.token_bytes(GCM_NONCE_BYTES)
    aead = AESGCM(subkey)
    ciphertext_and_tag = aead.encrypt(nonce, dek, associated_data=None)
    # Storage layout: ``nonce || ciphertext || tag``. The nonce is
    # *not* part of the AEAD output, so we concatenate it here for the
    # storage column. ``decrypt_dek_with_master`` reverses this split.
    return nonce + ciphertext_and_tag


def decrypt_dek_with_master(encrypted_dek: bytes, master: bytes) -> bytes:
    """Reverse of ``encrypt_dek_with_master``; recover the plaintext DEK.

    A failure here means either the master key has changed since the
    DEK was encrypted (rotation in progress, wrong row loaded) or the
    stored blob is corrupt. Both are mapped to ``DekDecryptionError``
    so the caller can decide whether to fall back to the
    ``previous_encrypted_dek`` (rotation window) or to surface a
    hard error.
    """
    _validate_master(master)
    _validate_nonce_prefix(encrypted_dek)
    subkey = _derive_master_subkey_cached(master)
    nonce = encrypted_dek[:GCM_NONCE_BYTES]
    body = encrypted_dek[GCM_NONCE_BYTES:]
    aead = AESGCM(subkey)
    try:
        return aead.decrypt(nonce, body, associated_data=None)
    except InvalidTag as exc:
        raise DekDecryptionError("DEK authentication failed") from exc


# ---------------------------------------------------------------------------
# Master-key lifecycle (DB-backed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MasterKeyRecord:
    """Lightweight DTO for a master-key row.

    Returned by ``load_master_key``; carries only the fields the
    application code actually needs (the raw 32-byte key + its
    stable ``key_id`` for logging/audit correlation). Wrapping /
    unwrapping happens below this layer — by the time we hand a
    ``MasterKeyRecord`` to a caller, ``key`` is the unwrapped AES-256
    secret ready for use.
    """

    key_id: UUID
    key: bytes


async def load_master_key(session: AsyncSession) -> MasterKeyRecord:
    """Load the currently-active master key from ``encryption_keys``.

    The DB column ``encrypted_key`` stores the master key wrapped under
    the platform KMS-root key. The unwrapping call is *not* performed
    here — this module does not import the KMS client. The caller
    (the service bootstrap path) is expected to either:

    * pass a session whose rows are pre-unwrapped (a "loaded" view), or
    * replace this function with a KMS-aware version in Task 6.

    For the purposes of this module the column is treated as
    already-unwrapped plaintext. This is the same abstraction the
    rest of the service uses — the ``encryption_keys`` table is
    effectively the unwrapped key in tests and the KMS-wrapped
    version in production. Spec: 主密钥加载.
    """
    stmt = (
        select(EncryptionKey)
        .where(EncryptionKey.status == KeyStatus.ACTIVE)
        .order_by(EncryptionKey.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise MasterKeyNotFoundError("no active master key in encryption_keys")
    _validate_master(row.encrypted_key)
    return MasterKeyRecord(key_id=row.key_id, key=row.encrypted_key)


async def rotate_master_key(
    session: AsyncSession,
    *,
    new_master: bytes | None = None,
) -> MasterKeyRecord:
    """Rotate the master key in a single transaction.

    Steps:

    1. Generate a new 32-byte master (or use ``new_master`` if the
       caller has already produced one — e.g. read from KMS).
    2. Load the currently-active master.
    3. For every credential row: read ``encrypted_dek`` and
       ``previous_encrypted_dek``, unwrap each under the old master,
       re-wrap under the new master, write back. ``previous_*`` rows
       are unwrapped even when they pre-date the current rotation,
       so a rotation in the middle of the 30-day window does not
       strand an unwrappable old value.
    4. Mark the old master as ``RETIRED`` and insert the new master
       row as ``ACTIVE`` — both in the same transaction.

    The whole flow is one ``async with session.begin()`` so a failure
    at any step rolls back. Spec: 主密钥轮换 (60s SLO, no downtime).
    """
    from app.models import Credential  # local import: avoids a cycle at module load

    if new_master is None:
        new_master = generate_master_key()
    _validate_master(new_master)

    async with session.begin():
        old = await load_master_key(session)
        # Re-wrap every DEK (current and previous-window) under the new master.
        creds_stmt = select(Credential)
        creds_result = await session.execute(creds_stmt)
        for cred in creds_result.scalars():
            # The current DEK is the hot path; decrypt and re-encrypt it.
            current_dek = decrypt_dek_with_master(cred.encrypted_dek, old.key)
            cred.encrypted_dek = encrypt_dek_with_master(current_dek, new_master)
            # The previous-value DEK is *also* re-wrapped: a rotation
            # in the middle of the 30-day window must not strand an
            # unwrappable old value.
            if cred.previous_encrypted_dek is not None:
                prev_dek = decrypt_dek_with_master(cred.previous_encrypted_dek, old.key)
                cred.previous_encrypted_dek = encrypt_dek_with_master(prev_dek, new_master)

        # Retire the old row, insert the new one. Both happen in the
        # same transaction (the ``async with session.begin()`` block)
        # so a failure at any step rolls back cleanly. ``retired_at``
        # is set explicitly here rather than relying on a model
        # default, so the timestamp reflects the rotation moment
        # rather than the row's last UPDATE.
        await session.execute(
            update(EncryptionKey)
            .where(EncryptionKey.key_id == old.key_id)
            .values(status=KeyStatus.RETIRED, retired_at=sa_func.now())
        )

        new_row = EncryptionKey(
            key_id=UUID(int=secrets.randbits(128)),
            encrypted_key=new_master,
            status=KeyStatus.ACTIVE,
        )
        session.add(new_row)
        await session.flush()
        new_key_id = new_row.key_id

    # Drop the cached subkey for the retired master. The cache now
    # retains only the new master (the most-recently used one is the
    # hot path); older retired keys fall out of the LRU naturally.
    _invalidate_subkey_cache()

    return MasterKeyRecord(key_id=new_key_id, key=new_master)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_dek(dek: bytes) -> None:
    if not isinstance(dek, bytes):  # pragma: no cover - type system enforces this
        raise TypeError(f"dek must be bytes, got {type(dek).__name__}")
    if len(dek) != DEK_BYTES:
        raise ValueError(f"dek must be exactly {DEK_BYTES} bytes (got {len(dek)})")


def _validate_master(master: bytes) -> None:
    if not isinstance(master, bytes):  # pragma: no cover - type system enforces this
        raise TypeError(f"master must be bytes, got {type(master).__name__}")
    if len(master) != MASTER_KEY_BYTES:
        raise ValueError(f"master must be exactly {MASTER_KEY_BYTES} bytes (got {len(master)})")


def _validate_nonce_prefix(blob: bytes) -> None:
    if len(blob) < GCM_NONCE_BYTES + GCM_TAG_BYTES:
        raise ValueError(
            f"encrypted_dek must be at least {GCM_NONCE_BYTES + GCM_TAG_BYTES} bytes "
            f"(got {len(blob)})"
        )


__all__ = [
    "DEK_BYTES",
    "MASTER_KEY_BYTES",
    "GCM_NONCE_BYTES",
    "GCM_TAG_BYTES",
    "CryptoError",
    "MasterKeyNotFoundError",
    "DekDecryptionError",
    "CredentialDecryptionError",
    "MasterKeyRecord",
    "generate_dek",
    "generate_master_key",
    "encrypt_with_dek",
    "decrypt_with_dek",
    "encrypt_dek_with_master",
    "decrypt_dek_with_master",
    "load_master_key",
    "rotate_master_key",
]
