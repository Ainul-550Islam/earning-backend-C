"""
adapters/cpalead.py – CPAlead network-specific postback adapter.

CPAlead postback URL format (GET):
  https://yourdomain.com/api/postback/receive/cpalead/?
      user_id={user_id}
      &lead_id={lead_id}
      &offer_id={offer_id}
      &payout={payout}
      &goal_id={goal_id}
      &sub_id={sub_id}
      &sub_id2={sub_id2}
      &sub_id3={sub_id3}
      &transaction_id={transaction_id}
      &ip={ip}
      &country={country}
      &device={device}
      &os={os}
      &browser={browser}
      &timestamp={timestamp}
      &status={status}
      &currency={currency}

CPAlead-specific fields handled here that the generic adapter misses:
  • goal_id       – completion goal / event name
  • sub_id        – publisher sub ID 1
  • sub_id2       – publisher sub ID 2
  • sub_id3       – publisher sub ID 3
  • country       – ISO country code
  • device        – device type (desktop/mobile/tablet)
  • os            – operating system
  • browser       – browser name
  • status        – CPAlead lead status (approved/pending/reversed)
"""
import logging

from .base import BasePostbackAdapter

logger = logging.getLogger(__name__)

# CPAlead lead status values
CPALEAD_STATUS_APPROVED = "approved"
CPALEAD_STATUS_PENDING = "pending"
CPALEAD_STATUS_REVERSED = "reversed"


class CPALeadAdapter(BasePostbackAdapter):
    """
    Adapter for CPAlead postback payloads.

    Handles CPAlead-specific field names and enriches the standard
    payload with CPAlead extras (goal_id, sub_ids, geo, device info).
    """

    network_keys = ["cpalead", "cpa_lead", "cpaleadnet"]

    def adapt(self, raw_payload: dict, network_config) -> dict:
        """
        Translate CPAlead raw postback payload to standard internal format.

        Returns a dict with both standard fields and CPAlead-specific extras.
        """
        try:
            return self._do_adapt(raw_payload, network_config)
        except Exception as exc:
            logger.exception(
                "CPALeadAdapter.adapt() unexpected error for network=%s: %s",
                getattr(network_config, "network_key", "?"), exc,
            )
            return {"_error": str(exc), "_raw": raw_payload}

    def _do_adapt(self, payload: dict, network_config) -> dict:
        # Apply field_mapping from NetworkPostbackConfig first
        # (allows admin to override per-deployment if CPAlead changes their params)
        fm = getattr(network_config, "field_mapping", {}) or {}
        mapped = self._apply_field_mapping(payload, fm)

        # ── Standard fields ──────────────────────────────────────────────────
        lead_id = self._get(mapped, "lead_id", "click_id", "lid")
        offer_id = self._get(mapped, "offer_id", "campaign_id", "oid")
        user_id = self._get(mapped, "user_id", "uid", "publisher_user_id")
        payout = self._get_decimal(mapped, "payout", "commission", "amount")
        currency = self._get(mapped, "currency", default="USD")
        transaction_id = self._get(mapped, "transaction_id", "tid", "txn_id")
        timestamp = self._get(mapped, "timestamp", "ts", "time")

        # ── CPAlead-specific fields ───────────────────────────────────────────
        goal_id = self._get(mapped, "goal_id", "goal", "event_id", "event_name")
        sub_id1 = self._get(mapped, "sub_id", "sub_id1", "s1", "subid")
        sub_id2 = self._get(mapped, "sub_id2", "s2", "subid2")
        sub_id3 = self._get(mapped, "sub_id3", "s3", "subid3")
        country = self._get(mapped, "country", "geo", "country_code")
        device = self._get(mapped, "device", "device_type")
        os_name = self._get(mapped, "os", "operating_system", "platform")
        browser = self._get(mapped, "browser", "browser_name")
        status = self._get(mapped, "status", "lead_status")

        # ── Build result ──────────────────────────────────────────────────────
        # Derive event_type from goal_id if present (CPAlead convention)
        event_type = self._derive_event_type(goal_id, adapted_payload=dict(
            lead_id=lead_id, offer_id=offer_id, status=status
        ))

        result = {
            # Standard pipeline fields
            "lead_id": lead_id,
            "offer_id": offer_id,
            "user_id": user_id,
            "payout": payout,
            "currency": currency,
            "transaction_id": transaction_id,
            "timestamp": timestamp,

            # CPAlead extras
            "goal_id": goal_id,
            "sub_id1": sub_id1,
            "sub_id2": sub_id2,
            "sub_id3": sub_id3,
            "country": country,
            "device": device,
            "os": os_name,
            "browser": browser,
            "cpalead_status": status,

            # Normalised event + conversion status (used by PostbackLog)
            "event_type": event_type,
            "is_reversal": status.lower() == CPALEAD_STATUS_REVERSED,

            # Adapter metadata
            "_adapter": "cpalead",
            "_network_key": getattr(network_config, "network_key", ""),
        }

        logger.debug(
            "CPALeadAdapter: lead_id=%r offer_id=%r payout=%r goal_id=%r sub_id1=%r",
            lead_id, offer_id, payout, goal_id, sub_id1,
        )
        return result

    def _apply_field_mapping(self, payload: dict, field_mapping: dict) -> dict:
        """
        Apply the NetworkPostbackConfig.field_mapping to the raw payload.
        field_mapping = { standard_name: network_param_name }

        We build a copy of payload but also inject the standard names
        so downstream code can use standard_name keys directly.
        """
        result = dict(payload)
        # For each mapping entry, add the standard name → value if present
        for standard_name, network_name in field_mapping.items():
            if network_name in payload and standard_name not in result:
                result[standard_name] = payload[network_name]
        return result

    def _derive_event_type(self, goal_id: str, adapted_payload: dict) -> str:
        """
        Infer a ConversionEventType value from CPAlead goal_id / context.
        goal_id values like 'install', 'sale', 'registration' map directly.
        """
        if not goal_id:
            return "unknown"
        g = goal_id.lower()
        mapping = {
            "install": "install", "app_install": "install",
            "sale": "sale", "purchase": "sale", "order": "sale",
            "lead": "lead", "form": "lead", "submit": "lead",
            "registration": "registration", "signup": "registration", "register": "registration",
            "trial": "trial", "free_trial": "trial",
            "deposit": "deposit", "ftd": "deposit",
            "survey": "survey",
            "video": "video", "view": "video",
            "subscription": "subscription", "sub": "subscription",
        }
        for key, event in mapping.items():
            if key in g:
                return event
        return "custom"

    def is_lead_reversed(self, adapted: dict) -> bool:
        """Return True if CPAlead reported this lead as reversed/charged back."""
        return adapted.get("cpalead_status", "").lower() == CPALEAD_STATUS_REVERSED

    def is_lead_pending(self, adapted: dict) -> bool:
        """Return True if CPAlead reported this lead as still pending."""
        return adapted.get("cpalead_status", "").lower() == CPALEAD_STATUS_PENDING
