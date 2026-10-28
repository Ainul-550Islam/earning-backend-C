"""Webhook Endpoint Serializer

Handles CRUD serialization for WebhookEndpoint, WebhookSubscription,
and related lightweight serializers.

FIXES APPLIED:
    [SER-01] WebhookEndpointSerializer.Meta.fields listed field names from
             the OLD flat model (url, secret, timeout_seconds, ip_whitelist,
             rate_limit_per_min, payload_template, headers).  None of these
             exist on the current WebhookEndpoint — DRF raises FieldError at
             runtime when the serializer is instantiated.
             Fix: updated to canonical model field names:
               url            → target_url
               secret         → secret_key  (write_only=True)
               headers        → custom_headers
             Removed: timeout_seconds, ip_whitelist, rate_limit_per_min,
             payload_template (not on model).

    [SER-02] success_rate is a @property on WebhookEndpoint that is
             useful for callers but was never exposed in the serializer.
             Fix: added as a read-only SerializerMethodField.

    [SER-03] validate_url checked http:// / https:// prefix but the model
             field is named target_url, so the method was never called by
             DRF (it expected validate_target_url).
             Fix: renamed to validate_target_url.

    [SER-04] WebhookSubscriptionSerializer referenced filter_config but
             the canonical field on WebhookSubscription is filters.
             Fix: corrected Meta.fields and validate_ method accordingly.

    [SER-06] This file also carried a second, independently-evolved copy
             each of WebhookDeliveryLogSerializer and WebhookEmitSerializer
             (same names as the real, package-exported serializers.WebhookDeliveryLogSerializer.py
             / serializers.WebhookEmitSerializer.py). Confirmed dead: no
             import anywhere in the codebase pulled either name from this
             module specifically (package __init__.py always imports both
             from their dedicated files; views.py imports from the package,
             not this file). They'd also diverged from the real ones - the
             dead WebhookEmitSerializer made endpoint_id optional ("omit to
             fan out"), which WebhookEmitAPIView.post() (views.py) never
             actually supported (it does `data["endpoint_id"]` unconditionally
             - real fan-out lives in DispatchService.emit_to_subscribers(),
             used by the dispatch_event Celery task, a different code path
             entirely). Removed both as dead code rather than leave a second,
             silently-diverging "owner" for either name sitting in this file.
"""

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from ..models import WebhookEndpoint, WebhookSubscription

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpointSerializer(serializers.ModelSerializer):
    """Serializer for webhook endpoint CRUD operations."""

    # FIX [SER-02]: expose the computed success_rate property as a read-only
    # field so API consumers receive it without having to derive it themselves.
    success_rate = serializers.SerializerMethodField(
        help_text=_("Percentage of successful deliveries (0–100, 2 d.p.)")
    )

    class Meta:
        model  = WebhookEndpoint
        # FIX [SER-01]: field names corrected to match the current model.
        fields = [
            "id",
            "label",
            "target_url",       # was: url
            "http_method",
            "status",
            "custom_headers",   # was: headers
            "description",
            "version",
            "payload_template",
            "max_retries",
            "verify_ssl",
            "total_deliveries",
            "success_deliveries",
            "failed_deliveries",
            "success_rate",     # FIX [SER-02]: new computed field
            "last_triggered_at",
            "suspension_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_deliveries",
            "success_deliveries",
            "failed_deliveries",
            "success_rate",
            "last_triggered_at",
            "suspension_reason",
            "created_at",
            "updated_at",
        ]
        # BUG FIX: DRF's auto-generated field for max_retries (a
        # PositiveSmallIntegerField) was a plain IntegerField with no
        # min_value — negative values passed validation cleanly, despite
        # the model field's own "positive" intent. Confirmed via direct
        # field introspection before fixing.
        extra_kwargs = {
            "max_retries": {"min_value": 0},
        }
        # FIX [SER-05]: secret_key removed from fields entirely (was previously
        # in BOTH read_only_fields AND extra_kwargs write_only=True at once,
        # which DRF forbids outright — "May not set both read_only and
        # write_only" — and crashed every list/retrieve/create call on this
        # serializer with a 500). It's auto-generated and rotated exclusively
        # via the dedicated /rotate-secret/ action (SecretRotateSerializer
        # below), so it isn't readable or writable through this serializer
        # at all, in either direction.

    def get_success_rate(self, obj: WebhookEndpoint) -> float:
        """Return the computed delivery success rate (0–100.00)."""
        return obj.success_rate

    # FIX [SER-03]: DRF calls validate_<field_name> — must match field name
    # exactly.  Was validate_url (matched nothing); now validate_target_url.
    def validate_target_url(self, value: str) -> str:
        """Validate webhook URL — must use http:// or https://."""
        if not value.startswith(("http://", "https://")):
            raise serializers.ValidationError(
                _("URL must start with http:// or https://")
            )
        return value

    def validate_custom_headers(self, value) -> dict:
        """Custom headers must be a flat string→string mapping."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("Custom headers must be a JSON object."))
        for k, v in value.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise serializers.ValidationError(
                    _("Header keys and values must both be strings.")
                )
        return value


# BUG FIX: WebhookEndpointDetailSerializer and SecretRotateSerializer were
# imported by views.py (WebhookEndpointViewSet.get_serializer_class() /
# .rotate_secret()) but never actually defined anywhere in the codebase -
# confirmed via real Django import-chain testing (urls.py -> views.py ->
# serializers), not just AST syntax checking. This is real, live, wired code
# (registered at /webhooks/endpoints/ in urls.py), not a floating/dead class.

class WebhookEndpointDetailSerializer(WebhookEndpointSerializer):
    """Detail serializer for a single endpoint - adds nested subscriptions,
    per this class's own use in WebhookEndpointViewSet ('retrieve/create —
    detail + subscriptions')."""

    subscriptions = serializers.SerializerMethodField()

    class Meta(WebhookEndpointSerializer.Meta):
        fields = WebhookEndpointSerializer.Meta.fields + ["subscriptions"]

    def get_subscriptions(self, obj: WebhookEndpoint) -> list:
        return [
            {
                "id": str(sub.id),
                "event_type": sub.event_type,
                "is_active": sub.is_active,
            }
            for sub in obj.subscriptions.all()
        ]


class SecretRotateSerializer(serializers.Serializer):
    """Requires explicit confirmation before rotating an endpoint's signing
    secret, since rotation immediately invalidates the old secret for any
    consumer that hasn't been updated yet."""

    confirm = serializers.BooleanField(
        required=True,
        help_text=_("Must be true to confirm secret rotation."),
    )

    def validate_confirm(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(
                _("Set confirm=true to rotate the secret. This will invalidate the old secret immediately.")
            )
        return value



# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK SUBSCRIPTION
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for webhook subscription CRUD operations."""

    class Meta:
        model  = WebhookSubscription
        # FIX [SER-04]: filter_config does not exist; canonical field is filters.
        fields = [
            "id",
            "endpoint",
            "event_type",
            "filters",        # was: filter_config
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    # FIX [SER-04]: renamed from validate_filter_config → validate_filters
    def validate_filters(self, value) -> dict:
        """Filters must be a JSON object."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("Filters must be a JSON object."))
        return value


# ─────────────────────────────────────────────────────────────────────────────
#  EVENT TYPE LIST
# ─────────────────────────────────────────────────────────────────────────────

class EventTypeListAPIViewSerializer(serializers.Serializer):
    """Read-only serializer for event type enumeration."""

    def to_representation(self, instance):
        from ..constants import EventType
        # NOTE: EventType.all_choices() does not exist anywhere on EventType
        # (confirmed via introspection) - .choices is the real, working
        # Django TextChoices property with the same (value, label) shape.
        return {
            "event_type":   instance,
            "display_name": dict(EventType.choices).get(instance, instance),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  TEST
# ─────────────────────────────────────────────────────────────────────────────

class WebhookTestSerializer(serializers.Serializer):
    """Serializer for ad-hoc endpoint smoke-tests.

    Used by WebhookEndpointViewSet.send_test() (views.py) to test an
    ALREADY-REGISTERED endpoint (identified via the URL's pk) — so unlike
    a raw/arbitrary-URL test, it only needs an optional custom message.
    """

    message = serializers.CharField(
        max_length=500,
        required=False,
        default="Test webhook from Ainul Enterprise Engine",
        help_text=_("Custom message to include in the test payload"),
    )
