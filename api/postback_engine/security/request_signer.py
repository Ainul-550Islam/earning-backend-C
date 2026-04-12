"""
security/request_signer.py
────────────────────────────
Signs outbound S2S postback requests sent to networks.
When we confirm a conversion to a network, we sign the request
so the network can verify it came from us.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import time
import urllib.parse

logger = logging.getLogger(__name__)


class RequestSigner:
    """Signs outbound HTTP requests using HMAC-SHA256."""

    def sign(
        self,
        url: str,
        params: dict,
        secret: str,
        algorithm: str = "hmac_sha256",
        include_timestamp: bool = True,
    ) -> dict:
        """
        Sign an outbound request.
        Returns updated params dict with 'sig' and optionally 'ts' added.
        """
        if not secret:
            return params

        signed_params = dict(params)
        if include_timestamp:
            signed_params["ts"] = str(int(time.time()))

        sorted_params = sorted(signed_params.items())
        message = urllib.parse.urlencode(sorted_params)
        signature = self._compute_hmac(secret, message, algorithm)
        signed_params["sig"] = signature
        return signed_params

    def sign_headers(
        self,
        body: str,
        secret: str,
        algorithm: str = "hmac_sha256",
    ) -> dict:
        """
        Generate headers for a signed webhook request.
        Returns dict of headers to add to the request.
        """
        ts = str(int(time.time()))
        message = f"{ts}.{body}"
        signature = self._compute_hmac(secret, message, algorithm)
        return {
            "X-Postback-Signature": signature,
            "X-Postback-Timestamp": ts,
        }

    @staticmethod
    def _compute_hmac(secret: str, message: str, algorithm: str) -> str:
        algo_map = {
            "hmac_sha256": hashlib.sha256,
            "hmac_sha512": hashlib.sha512,
            "hmac_md5":    hashlib.md5,
        }
        algo = algo_map.get(algorithm, hashlib.sha256)
        return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), algo).hexdigest()


request_signer = RequestSigner()
