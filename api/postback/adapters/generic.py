"""
adapters/generic.py – Generic fallback adapter for all networks.

Used when no network-specific adapter is registered for a network_key.
Applies the NetworkPostbackConfig.field_mapping to normalise field names,
then tries common field name variants for each standard field.
"""
import logging

from .base import BasePostbackAdapter

logger = logging.getLogger(__name__)

# Common field name aliases used across different affiliate networks
_LEAD_ID_ALIASES = ["lead_id", "click_id", "clickid", "lid", "cid", "sub1", "aff_sub"]
_OFFER_ID_ALIASES = ["offer_id", "campaign_id", "campaignid", "oid", "cid", "aff_id"]
_USER_ID_ALIASES = ["user_id", "uid", "publisher_id", "pub_id", "pid", "aff_sub5"]
_PAYOUT_ALIASES = ["payout", "commission", "amount", "revenue", "price", "usd"]
_CURRENCY_ALIASES = ["currency", "cur", "coin"]
_TXN_ALIASES = ["transaction_id", "txn_id", "tid", "trans_id", "conversion_id"]
_TIMESTAMP_ALIASES = ["timestamp", "ts", "time", "datetime", "date"]
_GOAL_ALIASES = ["goal_id", "goal", "event", "event_id", "event_name", "type"]
_SUB1_ALIASES = ["sub_id", "sub_id1", "s1", "subid", "sub1", "aff_sub"]
_SUB2_ALIASES = ["sub_id2", "s2", "subid2", "sub2", "aff_sub2"]
_SUB3_ALIASES = ["sub_id3", "s3", "subid3", "sub3", "aff_sub3"]


class GenericAdapter(BasePostbackAdapter):
    """
    Generic adapter – tries common field name aliases.
    Registered as the fallback when no specific adapter matches.
    """

    network_keys = ["*"]  # Wildcard – catches all unregistered networks

    def adapt(self, raw_payload: dict, network_config) -> dict:
        try:
            return self._do_adapt(raw_payload, network_config)
        except Exception as exc:
            logger.exception("GenericAdapter.adapt() error: %s", exc)
            return {"_error": str(exc), "_raw": raw_payload}

    def _do_adapt(self, payload: dict, network_config) -> dict:
        fm = getattr(network_config, "field_mapping", {}) or {}
        mapped = self._apply_field_mapping(payload, fm)

        return {
            "lead_id": self._get(mapped, *_LEAD_ID_ALIASES),
            "offer_id": self._get(mapped, *_OFFER_ID_ALIASES),
            "user_id": self._get(mapped, *_USER_ID_ALIASES),
            "payout": self._get_decimal(mapped, *_PAYOUT_ALIASES),
            "currency": self._get(mapped, *_CURRENCY_ALIASES, default="USD"),
            "transaction_id": self._get(mapped, *_TXN_ALIASES),
            "timestamp": self._get(mapped, *_TIMESTAMP_ALIASES),
            "goal_id": self._get(mapped, *_GOAL_ALIASES),
            "sub_id1": self._get(mapped, *_SUB1_ALIASES),
            "sub_id2": self._get(mapped, *_SUB2_ALIASES),
            "sub_id3": self._get(mapped, *_SUB3_ALIASES),
            "_adapter": "generic",
            "_network_key": getattr(network_config, "network_key", ""),
        }

    def _apply_field_mapping(self, payload: dict, field_mapping: dict) -> dict:
        result = dict(payload)
        for standard_name, network_name in field_mapping.items():
            if network_name in payload and standard_name not in result:
                result[standard_name] = payload[network_name]
        return result
