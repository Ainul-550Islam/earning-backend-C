"""
schemas.py – Pydantic v2 validation schemas for Postback Engine.

Every incoming postback payload is validated against these schemas BEFORE
any database writes. Invalid payloads raise SchemaValidationException
which translates to a structured rejection (logged as REJECTED with
reason=SCHEMA_VALIDATION).

Why Pydantic here instead of DRF serializers?
  • Pydantic coerces + validates in a single pass with zero DB hits.
  • Works in Celery tasks (no Django request context required).
  • Returns rich error detail per-field for debugging.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

try:
    from pydantic import (
        BaseModel,
        Field,
        field_validator,
        model_validator,
        ConfigDict,
    )
    PYDANTIC_V2 = True
except ImportError:
    # Pydantic v1 fallback
    from pydantic import BaseModel, Field, validator
    PYDANTIC_V2 = False

from .exceptions import SchemaValidationException

# ── Regex patterns ─────────────────────────────────────────────────────────────
_CURRENCY_RE = re.compile(r'^[A-Z]{3}$')
_SAFE_ID_RE  = re.compile(r'^[\w\-\.]{1,255}$')    # alphanumeric + - . _
_GOAL_RE     = re.compile(r'^[\w\-]{0,100}$')


# ══════════════════════════════════════════════════════════════════════════════
# Base postback payload schema (fields shared by all networks)
# ══════════════════════════════════════════════════════════════════════════════

class BasePostbackPayload(BaseModel):
    """
    Minimum required schema for any incoming postback.
    Network adapters normalise their specific params to these standard names
    before this validation runs.
    """
    if PYDANTIC_V2:
        model_config = ConfigDict(
            extra="allow",        # allow extra fields (network-specific)
            str_strip_whitespace=True,
            coerce_numbers_to_str=False,
            arbitrary_types_allowed=True,
        )

    # ── Core fields ────────────────────────────────────────────────────────────
    lead_id:        Optional[str] = Field(None,  min_length=1, max_length=255)
    click_id:       Optional[str] = Field(None,  max_length=255)
    offer_id:       Optional[str] = Field(None,  max_length=255)
    transaction_id: Optional[str] = Field(None,  max_length=255)
    payout:         Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("100000"))
    currency:       Optional[str] = Field("USD", min_length=3, max_length=3)
    status:         Optional[str] = Field(None,  max_length=50)
    goal_id:        Optional[str] = Field(None,  max_length=100)
    goal_value:     Optional[Decimal] = Field(None, ge=Decimal("0"))

    # ── Validators ─────────────────────────────────────────────────────────────

    if PYDANTIC_V2:
        @field_validator("currency")
        @classmethod
        def validate_currency(cls, v: Optional[str]) -> Optional[str]:
            if v is None:
                return "USD"
            v = v.upper().strip()
            if not _CURRENCY_RE.match(v):
                raise ValueError(f"Invalid currency code: {v!r}. Must be 3 uppercase letters.")
            return v

        @field_validator("lead_id", "click_id", "offer_id", "transaction_id", mode="before")
        @classmethod
        def sanitise_id(cls, v: Any) -> Optional[str]:
            if v is None:
                return None
            s = str(v).strip()
            if s == "":
                return None
            if not _SAFE_ID_RE.match(s):
                raise ValueError(
                    f"ID field contains invalid characters: {s[:50]!r}. "
                    "Allowed: alphanumeric, hyphens, dots, underscores."
                )
            return s

        @field_validator("payout", mode="before")
        @classmethod
        def coerce_payout(cls, v: Any) -> Optional[Decimal]:
            if v is None:
                return Decimal("0")
            try:
                return Decimal(str(v).replace(",", "").strip())
            except Exception:
                raise ValueError(f"Invalid payout value: {v!r}")

        @field_validator("goal_id")
        @classmethod
        def validate_goal_id(cls, v: Optional[str]) -> Optional[str]:
            if v is None:
                return None
            if not _GOAL_RE.match(v):
                raise ValueError(f"Invalid goal_id: {v!r}")
            return v

        @model_validator(mode="after")
        def require_lead_or_click(self) -> "BasePostbackPayload":
            if not self.lead_id and not self.click_id:
                raise ValueError(
                    "At least one of 'lead_id' or 'click_id' must be present."
                )
            return self

    else:
        # Pydantic v1 validators
        @validator("currency", always=True)
        def validate_currency(cls, v):
            if not v:
                return "USD"
            v = v.upper().strip()
            if not _CURRENCY_RE.match(v):
                raise ValueError(f"Invalid currency: {v!r}")
            return v

        @validator("payout", pre=True, always=True)
        def coerce_payout(cls, v):
            if v is None:
                return Decimal("0")
            try:
                return Decimal(str(v).replace(",", "").strip())
            except Exception:
                raise ValueError(f"Invalid payout: {v!r}")


# ══════════════════════════════════════════════════════════════════════════════
# Network-specific schemas (extend BasePostbackPayload)
# ══════════════════════════════════════════════════════════════════════════════

class CPALeadPayload(BasePostbackPayload):
    """CPALead-specific: lead_id (sub1) is required."""
    lead_id: str = Field(..., min_length=1, max_length=255)

    if PYDANTIC_V2:
        @model_validator(mode="after")
        def require_lead_id(self) -> "CPALeadPayload":
            if not self.lead_id:
                raise ValueError("CPALead requires 'lead_id' (sub1).")
            return self


class AdGatePayload(BasePostbackPayload):
    """AdGate requires lead_id (user_id) and payout (reward)."""
    lead_id: str = Field(..., min_length=1, max_length=255)
    payout: Decimal = Field(..., ge=Decimal("0"))


class AppLovinPayload(BasePostbackPayload):
    """AppLovin SSV: payout required, user_id optional (custom_data)."""
    payout: Decimal = Field(..., ge=Decimal("0"), le=Decimal("10000"))

    if PYDANTIC_V2:
        @model_validator(mode="after")
        def require_payout(self) -> "AppLovinPayload":
            if self.payout <= 0:
                raise ValueError("AppLovin payout must be > 0.")
            return self


class UnityAdsPayload(BasePostbackPayload):
    """Unity Ads SSV: user_id is required."""
    user_id: str = Field(..., min_length=1, max_length=255)


class IronSourcePayload(BasePostbackPayload):
    """IronSource: userId required."""
    user_id: str = Field(..., min_length=1, max_length=255)


class ImpactPayload(BasePostbackPayload):
    """Impact requires lead_id (ClickId) and offer_id (CampaignId)."""
    lead_id:  str = Field(..., min_length=1, max_length=255)
    offer_id: str = Field(..., min_length=1, max_length=255)


class EverflowPayload(BasePostbackPayload):
    """Everflow postback schema."""
    lead_id: str = Field(..., min_length=1, max_length=255)


class HasOffersPayload(BasePostbackPayload):
    """HasOffers / TUNE postback."""
    lead_id:  str = Field(..., min_length=1, max_length=255)
    offer_id: str = Field(..., min_length=1, max_length=255)


# ══════════════════════════════════════════════════════════════════════════════
# Webhook / Outbound schemas (for validating data WE send to third parties)
# ══════════════════════════════════════════════════════════════════════════════

class WebhookConversionPayload(BaseModel):
    """Schema for outbound conversion webhook payloads."""
    if PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid")

    event:          str
    conversion_id:  str
    transaction_id: str
    lead_id:        str
    offer_id:       Optional[str] = None
    network:        str
    user_id:        str
    payout_usd:     float
    points_awarded: int
    currency:       str = "USD"
    status:         str
    converted_at:   str
    country:        Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# Admin / Config schemas
# ══════════════════════════════════════════════════════════════════════════════

class FieldMappingSchema(BaseModel):
    """Validates AdNetworkConfig.field_mapping JSON."""
    if PYDANTIC_V2:
        model_config = ConfigDict(extra="allow")

    lead_id:        Optional[str] = None
    click_id:       Optional[str] = None
    offer_id:       Optional[str] = None
    payout:         Optional[str] = None
    currency:       Optional[str] = None
    transaction_id: Optional[str] = None
    user_id:        Optional[str] = None
    status:         Optional[str] = None
    goal_id:        Optional[str] = None

    if PYDANTIC_V2:
        @model_validator(mode="before")
        @classmethod
        def validate_all_strings(cls, values: dict) -> dict:
            for k, v in values.items():
                if v is not None and not isinstance(v, str):
                    raise ValueError(f"field_mapping[{k!r}] must be a string, got {type(v)}")
            return values


class RewardRuleSchema(BaseModel):
    """Validates a single entry in AdNetworkConfig.reward_rules."""
    points: int = Field(0, ge=0, le=1_000_000)
    usd:    float = Field(0.0, ge=0.0, le=10_000.0)


# ══════════════════════════════════════════════════════════════════════════════
# Validation function (called by base_handler._validate_schema)
# ══════════════════════════════════════════════════════════════════════════════

# Map network_key → Pydantic schema class
_SCHEMA_REGISTRY: Dict[str, type] = {
    "cpalead":    CPALeadPayload,
    "adgate":     AdGatePayload,
    "applovin":   AppLovinPayload,
    "unity":      UnityAdsPayload,
    "ironsource": IronSourcePayload,
    "impact":     ImpactPayload,
    "everflow":   EverflowPayload,
    "hasoffers":  HasOffersPayload,
}


def validate_postback_payload(
    normalised: Dict[str, Any],
    network_key: str = "",
) -> BasePostbackPayload:
    """
    Validate a normalised postback payload against the appropriate Pydantic schema.

    Raises SchemaValidationException (which translates to a REJECTED postback
    with reason=SCHEMA_VALIDATION) if validation fails.

    Returns the validated Pydantic model instance on success.
    """
    schema_cls = _SCHEMA_REGISTRY.get(network_key, BasePostbackPayload)

    # Strip _raw_ passthrough fields before validation
    clean = {k: v for k, v in normalised.items() if not k.startswith("_raw_")}

    try:
        return schema_cls(**clean)
    except Exception as exc:
        # Extract human-readable error list from Pydantic
        errors = _format_pydantic_errors(exc)
        raise SchemaValidationException(
            f"Payload validation failed for network '{network_key}': {errors}",
            detail=errors,
        ) from exc


def validate_field_mapping(data: dict) -> FieldMappingSchema:
    """Validate AdNetworkConfig.field_mapping on save."""
    try:
        return FieldMappingSchema(**data)
    except Exception as exc:
        errors = _format_pydantic_errors(exc)
        raise SchemaValidationException(
            f"Invalid field_mapping: {errors}", detail=errors
        ) from exc


def validate_reward_rule(data: dict) -> RewardRuleSchema:
    """Validate a single reward rule entry."""
    try:
        return RewardRuleSchema(**data)
    except Exception as exc:
        errors = _format_pydantic_errors(exc)
        raise SchemaValidationException(
            f"Invalid reward_rule: {errors}", detail=errors
        ) from exc


def validate_webhook_payload(data: dict) -> WebhookConversionPayload:
    """Validate outbound webhook payload before sending."""
    try:
        return WebhookConversionPayload(**data)
    except Exception as exc:
        errors = _format_pydantic_errors(exc)
        raise SchemaValidationException(
            f"Invalid webhook payload: {errors}", detail=errors
        ) from exc


# ── Helper ─────────────────────────────────────────────────────────────────────

def _format_pydantic_errors(exc: Exception) -> str:
    """Extract a readable error string from a Pydantic ValidationError."""
    try:
        # Pydantic v2
        if hasattr(exc, "errors"):
            errs = exc.errors()
            parts = []
            for e in errs:
                loc = " → ".join(str(x) for x in e.get("loc", []))
                msg = e.get("msg", str(e))
                parts.append(f"{loc}: {msg}" if loc else msg)
            return "; ".join(parts)
    except Exception:
        pass
    return str(exc)
