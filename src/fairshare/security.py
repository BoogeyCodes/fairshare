"""Password hashing with the standard library (PBKDF2-HMAC-SHA256).

No third-party crypto dependency: the stdlib's ``hashlib.pbkdf2_hmac`` is available on every
supported Python and works the same across platforms. Hashes are stored as a single string
``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`` so the parameters travel with the hash.
"""

from __future__ import annotations

import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 240_000
_SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = encoded.split("$")
        if algo != _ALGO:
            return False
        iterations = int(iters)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)
