"""
network_adapters/base_adapter.py
──────────────────────────────────
Abstract base for all CPA network adapters.

Responsibilities:
  1. FIELD_MAP    → translate network param names → our standard names
  2. STATUS_MAP   → translate raw status codes    → "approved" | "rejected" | "pending"
  3. normalise()  → apply field map + macro expansion + type coercion
  4. normalise_status() → convert "1" / "APPROVED" / "paid" → "approved"
  5. expand_macros()    → replace {click_id}, {sub_id} etc. in URL templates
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

# ── Status normalisation maps ──────────────────────────────────────────────────
_APPROVED_VALUES = {
    "1", "approved", "approve", "success", "successful", "complete",
    "completed", "paid", "confirmed", "accepted", "yes", "true",
    "converted", "conversion", "fired", "rewarded",
}
_REJECTED_VALUES = {
    "0", "rejected", "reject", "failed", "failure", "declined",
    "cancelled", "canceled", "denied", "invalid", "no", "false",
    "fraud", "chargeback", "reversed", "refunded",
}
_PENDING_VALUES = {
    "2", "pending", "hold", "review", "processing", "waiting",
    "under_review", "pending_review",
}


class BaseNetworkAdapter(ABC):
    """
    Base class every network adapter inherits from.

    Subclasses set:
        NETWORK_KEY    : str   → matches AdNetworkConfig.network_key
        FIELD_MAP      : dict  → { our_standard_name: network_param_name }
        STATUS_MAP     : dict  → network-specific { raw: "approved"|"rejected"|"pending" }
        REQUIRED_FIELDS: list  → standard field names that must be non-empty after mapping
    """

    NETWORK_KEY: str = ""
    FIELD_MAP: Dict[str, str] = {}
    STATUS_MAP: Dict[str, str] = {}
    REQUIRED_FIELDS: list = []
    SIGNATURE_ALGORITHM: str = "hmac_sha256"
    SIGNATURE_PARAM: str = "sig"
    TIMESTAMP_PARAM: str = "ts"

    # ── Public API ─────────────────────────────────────────────────────────────

    def normalise(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map network-specific param names → standard field names.
        Also copies unmapped params as _raw_{key} so nothing is lost.
        """
        result: Dict[str, Any] = {}
        mapped_network_params = set()

        for standard_name, network_param in self.FIELD_MAP.items():
            value = self._deep_get(raw_payload, network_param)
            if value is not None:
                result[standard_name] = value
            mapped_network_params.add(network_param.split(".")[0])

        # Pass through unmapped params
        for key, val in raw_payload.items():
            if key not in mapped_network_params:
                result[f"_raw_{key}"] = val

        # Type coercions
        if "payout" in result:
            result["payout"] = self._coerce_payout(result["payout"])
        if "currency" in result:
            result["currency"] = str(result["currency"]).upper().strip()

        return result

    def normalise_status(self, raw_status: str) -> str:
        """
        Convert raw network status value → "approved" | "rejected" | "pending" | "unknown".
        Empty status defaults to "approved" (most networks only fire on success).
        """
        if not raw_status:
            return "approved"

        cleaned = str(raw_status).lower().strip()

        if cleaned in self.STATUS_MAP:
            return self.STATUS_MAP[cleaned]
        if cleaned in _APPROVED_VALUES:
            return "approved"
        if cleaned in _REJECTED_VALUES:
            return "rejected"
        if cleaned in _PENDING_VALUES:
            return "pending"
        return "unknown"

    def expand_macros(self, url_template: str, context: Dict[str, Any]) -> str:
        """
        Replace {macro} placeholders in a URL template.

        Supported macros (pass any subset in context):
          {click_id}  {lead_id}  {offer_id}  {sub_id}  {payout}  {currency}
          {user_id}   {transaction_id}  {timestamp}  {status}  {goal_id}

        Unknown macros are left unchanged.
        """
        if not url_template:
            return url_template

        def replacer(match: re.Match) -> str:
            key = match.group(1)
            value = context.get(key)
            return str(value) if value is not None else match.group(0)

        return re.sub(r"\{(\w+)\}", replacer, url_template)

    def build_outbound_postback_url(
        self,
        network_config,
        context: Dict[str, Any],
    ) -> Optional[str]:
        """Build the S2S outbound postback URL using the network config template."""
        template = getattr(network_config, "postback_url_template", "")
        if not template:
            return None
        return self.expand_macros(template, context)

    def extract_signature(self, raw_payload: dict, headers: dict) -> str:
        return (
            headers.get("X-Postback-Signature", "")
            or headers.get("x-postback-signature", "")
            or raw_payload.get(self.SIGNATURE_PARAM, "")
        )

    def extract_timestamp(self, raw_payload: dict, headers: dict) -> str:
        return (
            headers.get("X-Postback-Timestamp", "")
            or headers.get("x-postback-timestamp", "")
            or raw_payload.get(self.TIMESTAMP_PARAM, "")
        )

    def parse_payout(self, value: Any) -> Decimal:
        return self._coerce_payout(value)

    def validate_required_fields(self, normalised: dict) -> list:
        missing = []
        for field_name in self.REQUIRED_FIELDS:
            val = normalised.get(field_name)
            if val is None or str(val).strip() == "":
                missing.append(field_name)
        return missing

    @abstractmethod
    def get_network_key(self) -> str:
        return self.NETWORK_KEY

    # ── Private helpers ────────────────────────────────────────────────────────

    def _coerce_payout(self, value: Any) -> Decimal:
        try:
            cleaned = str(value).strip().replace(",", "")
            return Decimal(cleaned)
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0")

    def _deep_get(self, data: dict, key: str) -> Any:
        """Support dot-notation: 'data.amount' → data['data']['amount']."""
        if "." not in key:
            return data.get(key)
        parts = key.split(".", 1)
        sub = data.get(parts[0])
        if isinstance(sub, dict):
            return self._deep_get(sub, parts[1])
        return None
