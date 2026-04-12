"""
validation_engines/signature_validator.py
───────────────────────────────────────────
HMAC signature validation for incoming postbacks.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
from ..exceptions import InvalidSignatureException, SignatureExpiredException
from ..constants import SIGNATURE_TOLERANCE_SECONDS
from django.utils import timezone

logger = logging.getLogger(__name__)


class SignatureValidator:

    def validate(
        self,
        secret: str,
        payload: dict,
        provided_signature: str,
        algorithm: str = "hmac_sha256",
        timestamp_str: str = "",
        nonce: str = "",
    ) -> bool:
        if not provided_signature:
            raise InvalidSignatureException("No signature provided.")

        # Timestamp replay protection
        if timestamp_str:
            self._check_timestamp(timestamp_str)

        expected = self._compute(secret, payload, algorithm, timestamp_str, nonce)
        if not hmac.compare_digest(
            expected.encode(), provided_signature.encode()
        ):
            raise InvalidSignatureException("Signature verification failed.")
        return True

    def _check_timestamp(self, timestamp_str: str) -> None:
        try:
            ts = float(timestamp_str)
            age = abs(timezone.now().timestamp() - ts)
            if age > SIGNATURE_TOLERANCE_SECONDS:
                raise SignatureExpiredException(
                    f"Timestamp {age:.0f}s old (max {SIGNATURE_TOLERANCE_SECONDS}s)."
                )
        except (ValueError, TypeError):
            raise InvalidSignatureException("Invalid timestamp format.")

    def _compute(self, secret: str, payload: dict, algorithm: str, ts: str, nonce: str) -> str:
        import urllib.parse
        sorted_params = sorted(payload.items())
        msg = urllib.parse.urlencode(sorted_params)
        if ts:   msg += f"&ts={ts}"
        if nonce: msg += f"&nonce={nonce}"
        algo_map = {
            "hmac_sha256": hashlib.sha256,
            "hmac_sha512": hashlib.sha512,
            "hmac_md5":    hashlib.md5,
        }
        algo = algo_map.get(algorithm, hashlib.sha256)
        return hmac.new(secret.encode(), msg.encode(), algo).hexdigest()


signature_validator = SignatureValidator()
