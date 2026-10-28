"""
adapters/base.py – Abstract base class for all postback network adapters.

Rules:
  • adapt() must return a dict with at minimum the STANDARD_FIELD_* keys.
  • Missing / unknown fields should be returned as empty string or None.
  • Never raise inside adapt() – return {'_error': reason} instead.
"""
from abc import ABC, abstractmethod


class BasePostbackAdapter(ABC):
    """
    Base class for all postback network adapters.

    Subclasses implement adapt() to translate network-specific payloads
    into the standard internal field format used by the postback pipeline.
    """

    #: Override in subclass with the network_key(s) this adapter handles.
    network_keys: list = []

    @abstractmethod
    def adapt(self, raw_payload: dict, network_config) -> dict:
        """
        Translate a raw postback payload into the standard field dict.

        Args:
            raw_payload:    The raw dict received from the network.
            network_config: The NetworkPostbackConfig instance.

        Returns:
            A dict with standardised field names. Must include:
                lead_id, offer_id, user_id, payout, currency,
                transaction_id, timestamp, sub_id1..sub_id5, goal_id.
            Unknown / not-present fields should be empty string or None.
        """

    def _get(self, payload: dict, *keys, default="") -> str:
        """
        Try each key in order and return the first non-empty string value.
        Falls back to default if none found.
        """
        for key in keys:
            val = payload.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
        return default

    def _get_decimal(self, payload: dict, *keys, default="0") -> str:
        """
        Extract a decimal-string value from payload. Returns '0' if missing/invalid.
        """
        raw = self._get(payload, *keys, default=default)
        try:
            float(raw)
            return raw
        except (ValueError, TypeError):
            return default
