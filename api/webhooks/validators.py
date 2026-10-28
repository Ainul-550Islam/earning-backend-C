# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Validators
validators.py

FIX APPLIED:
  - Added explicit wiring notes for every validator showing which model
    field or serializer uses it (was documented only in utils.py)
  - Added is_valid_webhook_url() helper (used by utils.py)
  - Added validate_webhook_url to __all__ so it's clearly exportable
  - Added HTTPS-enforcement option via settings
  - All existing validation logic preserved unchanged

Wiring map (validator → model field):
    validate_webhook_url      → WebhookEndpoint.target_url (validators=[])
    validate_secret           → WebhookEndpoint.secret_key (validators=[])
    validate_event_type       → WebhookSubscription.event_type
    validate_filter_config    → WebhookFilter.filter_config
    validate_payload_template → WebhookTemplate.payload_template
    validate_transform_rules  → WebhookTemplate.transform_rules
    validate_rate_limit_config→ WebhookEndpoint.rate_limit_config (via model field)
    validate_ip_whitelist     → WebhookEndpoint.allowed_ip_list
    validate_headers          → WebhookEndpoint.custom_headers
    validate_batch_size       → WebhookBatch.batch_size (validators=[])
    validate_timeout          → WebhookEndpoint.timeout_seconds (validators=[])
    validate_max_retries      → WebhookEndpoint.max_retries
    is_valid_webhook_url      → utils.py is_valid_webhook_url()
"""

import ipaddress
import re
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .constants import (
    DeliveryStatus,
    HttpMethod,
)
from .choices import FilterOperator


# ── URL Validation ────────────────────────────────────────────────────────────

# SECURITY FIX (SSRF): hostnames that are always blocked regardless of what
# they resolve to, since they unambiguously mean "this machine" or a
# well-known internal/cloud-metadata target. Checked in addition to
# resolving the hostname and inspecting the resulting IP(s) below.
_BLOCKED_HOSTNAMES = {
    "localhost", "localhost.localdomain", "metadata.google.internal",
}


def _is_disallowed_ip(ip_str: str) -> bool:
    """True if `ip_str` is loopback, private, link-local (this covers the
    169.254.169.254 cloud metadata endpoint used by AWS/GCP/Azure/etc.),
    reserved, or otherwise not a normal public routable address."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # can't parse it -> treat as unsafe
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def _is_disallowed_host(hostname: str) -> bool:
    """
    SECURITY FIX (SSRF): resolves `hostname` and rejects it if it (or any of
    its resolved addresses) points at the local machine, a private/internal
    network, or a link-local address such as the 169.254.169.254 cloud
    metadata endpoint. Without this, any authenticated user could register a
    WebhookEndpoint pointing at an internal service and have the server make
    requests to it on their behalf.

    Note: this is a registration-time check. A target that resolves safely
    now but is re-pointed at an internal address later (DNS rebinding) is a
    separate, harder problem; see also the allow_redirects=False fix in
    DispatchService, which closes the more common redirect-based bypass.
    """
    hostname = hostname.lower().strip("[]")  # strip IPv6 literal brackets
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".local"):
        return True

    try:
        # If the hostname is already a literal IP, this just re-parses it.
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        # Can't resolve — fail closed rather than silently allowing it through.
        return True

    for family, _type, _proto, _canon, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        if _is_disallowed_ip(ip_str):
            return True
    return False


def validate_webhook_url(url: str) -> str:
    """
    Validate webhook URL format.

    Used by: WebhookEndpoint.target_url field validators=[validate_webhook_url]
             validate_webhook_url(url) also called in WebhookEndpointSerializer

    Args:
        url: Webhook URL to validate

    Returns:
        Validated URL string

    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError(_("Webhook URL is required"))

    try:
        parsed = urlparse(url)

        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(
                _("Webhook URL must include scheme and domain (e.g., https://example.com/webhook)")
            )

        # Enforce HTTPS in production (can be overridden in dev via settings)
        allow_http = getattr(settings, "WEBHOOKS_ALLOW_HTTP", False)
        if parsed.scheme not in ("http", "https"):
            raise ValidationError(_("Webhook URL must use HTTP or HTTPS scheme"))

        if parsed.scheme == "http" and not allow_http:
            raise ValidationError(
                _("Webhook URL must use HTTPS (HTTP is disabled in production). "
                  "Set WEBHOOKS_ALLOW_HTTP=True in development settings to override.")
            )

        if len(url) > 2048:
            raise ValidationError(_("Webhook URL must be less than 2048 characters"))

        # SECURITY FIX (SSRF): block targets that point at this machine or an
        # internal/private network. Can be disabled via
        # WEBHOOKS['BLOCK_PRIVATE_NETWORKS'] = False for local dev against a
        # test receiver, but defaults to enabled.
        webhooks_settings = getattr(settings, "WEBHOOKS", {})
        block_private = webhooks_settings.get("BLOCK_PRIVATE_NETWORKS", True)
        if block_private and parsed.hostname and _is_disallowed_host(parsed.hostname):
            raise ValidationError(
                _("Webhook URL may not point at a local, private, or internal network address")
            )

        return url

    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(_("Invalid webhook URL format: {}").format(str(exc)))


def is_valid_webhook_url(url: str) -> bool:
    """
    Boolean helper for validate_webhook_url.
    Used by utils.py is_valid_webhook_url() and InboundWebhookService.

    Returns True/False without raising.
    """
    try:
        validate_webhook_url(url)
        return True
    except ValidationError:
        return False


# ── Secret Validation ─────────────────────────────────────────────────────────

def validate_secret(secret: str) -> str:
    """
    Validate webhook secret strength and format.

    Used by: WebhookEndpoint.secret_key, SecretRotationService

    Args:
        secret: Webhook secret to validate

    Raises:
        ValidationError: If secret is too weak or invalid
    """
    if not secret:
        raise ValidationError(_("Webhook secret is required"))

    if len(secret) < 32:
        raise ValidationError(_("Webhook secret must be at least 32 characters long"))

    if len(secret) > 256:
        raise ValidationError(_("Webhook secret must be less than 256 characters long"))

    weak_patterns = [
        r"password", r"123456", r"qwerty", r"abc123",
        r"admin", r"root", r"test", r"webhook", r"secret", r"key",
    ]
    for pattern in weak_patterns:
        if re.search(pattern, secret.lower()):
            raise ValidationError(_("Webhook secret contains common weak patterns"))

    has_upper   = any(c.isupper() for c in secret)
    has_lower   = any(c.islower() for c in secret)
    has_digit   = any(c.isdigit() for c in secret)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:<>?,./'" for c in secret)

    if not (has_upper and has_lower and has_digit and has_special):
        raise ValidationError(
            _("Webhook secret must contain uppercase, lowercase, digits, and special characters")
        )

    return secret


# ── Event Type Validation ─────────────────────────────────────────────────────

def validate_event_type(event_type: str) -> str:
    """
    Validate event type format.

    Used by: WebhookEmitSerializer (4 fields), EventTypeValidateAPIView.
    (validators.py's own historical comment also claimed
    WebhookSubscription.event_type - confirmed false: that model field has
    no validators=[] at all, and WebhookSubscriptionSerializer never calls
    this function. Corrected the comment above.)

    Format only - deliberately does NOT check EventType membership.

    CORRECTION (Session 9, same session): a previous fix in this same
    session made this raise for any event_type not in EventType.choices,
    reasoning from this function's own docstring ("or not in allowed
    list") and from EventType.all_choices() genuinely never having existed
    (a real, separate bug, fixed correctly). That was wrong on the
    whitelist question specifically - caught before shipping by tracing
    every caller rather than stopping at "the tests pass now":

    EventTypeValidateAPIView (views.py) calls this function for its format
    check, then does its OWN separate, explicit check for EventType
    membership - as a WARNING, not an error, with a comment stating
    outright that a format-valid, non-predefined event type "will still
    work for custom/internal events." Under strict enforcement, that
    warning branch can never run (validate_event_type() would already
    have raised whenever the membership check would fire), silently
    making deliberately-written code unreachable - a real regression this
    session's own earlier fix introduced without noticing.

    Separately, and independently confirming the same conclusion: a
    systematic search for the ~40 non-canonical event-type strings found
    in utils.py's old dict (see Cluster 5) turned up seven real,
    live signal handlers (signals/wallet_signals.py, withdrawal_signals.py,
    offer_signals.py, kyc_signals.py, payment_signals.py, fraud_signals.py,
    plus INTEGRATION_SYSTEM's own separate signal set) actively firing
    webhook events with event_type values never added to EventType.
    Strict enforcement here would not have blocked those specific emits
    (they don't route through this validator), but would have blocked
    anyone using WebhookEmitSerializer's manual-emit endpoints to send an
    equivalent test/custom event for any of them.

    Format is still fully enforced below - only genuinely malformed
    strings are rejected.

    Raises:
        ValidationError: if event_type is empty or not in domain.action
            format
    """
    if not event_type:
        raise ValidationError(_("Event type is required"))

    if not re.match(r"^[a-z0-9_]+\.[a-z0-9_]+$", event_type):
        raise ValidationError(
            _("Event type must be in format: domain.action (e.g., user.created)")
        )

    return event_type


# ── Filter Config Validation ──────────────────────────────────────────────────

def validate_filter_config(config: dict) -> dict:
    """
    Validate webhook filter configuration.

    Used by: WebhookFilter.filter_config, WebhookFilterSerializer

    Raises:
        ValidationError: If filter config is malformed
    """
    if not isinstance(config, dict):
        raise ValidationError(_("Filter configuration must be a JSON object"))

    for key, value in config.items():
        if key == "field_path":
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(_("Filter field path cannot be empty"))

        elif key == "operator":
            allowed_operators = [choice[0] for choice in FilterOperator.CHOICES]
            if value not in allowed_operators:
                raise ValidationError(
                    _('Filter operator "{}" is not allowed').format(value)
                )

        elif key == "value":
            if value is None:
                raise ValidationError(_("Filter value cannot be null"))

    return config


# ── Payload Template Validation ───────────────────────────────────────────────

def validate_payload_template(template: str) -> str:
    """
    Validate Jinja2 payload template syntax.

    Used by: WebhookTemplate.payload_template, PayloadTransformer.validate_template()

    Raises:
        ValidationError: If Jinja2 template syntax is invalid
    """
    if not isinstance(template, str):
        raise ValidationError(_("Payload template must be a string"))

    if not template.strip():
        raise ValidationError(_("Payload template cannot be empty"))

    try:
        from jinja2 import Environment, TemplateSyntaxError
        env = Environment()
        env.from_string(template)
    except ImportError:
        pass  # Jinja2 optional — skip syntax check if not installed
    except Exception as exc:
        raise ValidationError(
            _("Invalid Jinja2 template syntax: {}").format(str(exc))
        )

    return template


# ── Transform Rules Validation ────────────────────────────────────────────────

def validate_transform_rules(rules: dict) -> dict:
    """
    Validate webhook transformation rules.

    Used by: WebhookTemplate.transform_rules, PayloadTransformer

    Raises:
        ValidationError: If rules are malformed
    """
    if not isinstance(rules, dict):
        raise ValidationError(_("Transform rules must be a JSON object"))

    SUPPORTED_TYPES = [
        "add_field", "remove_field", "rename_field",
        "map_value", "format_date", "calculate_field",
    ]

    for rule_name, rule_config in rules.items():
        if not isinstance(rule_config, dict):
            raise ValidationError(
                _('Transform rule "{}" must be a JSON object').format(rule_name)
            )

        rule_type = rule_config.get("type")
        if not rule_type:
            raise ValidationError(
                _('Transform rule "{}" must have a type').format(rule_name)
            )

        if rule_type not in SUPPORTED_TYPES:
            raise ValidationError(
                _('Transform rule type "{}" is not supported').format(rule_type)
            )

        if rule_type == "add_field" and "field_name" not in rule_config:
            raise ValidationError(_("Add field rule must have field_name"))
        elif rule_type == "remove_field" and "path" not in rule_config:
            raise ValidationError(_("Remove field rule must have path"))
        elif rule_type == "rename_field":
            if "old_name" not in rule_config or "new_name" not in rule_config:
                raise ValidationError(_("Rename field rule must have old_name and new_name"))

    return rules


# ── Rate Limit Config Validation ──────────────────────────────────────────────

def validate_rate_limit_config(config: dict) -> dict:
    """
    Validate rate limiting configuration JSON.

    Used by: WebhookEndpoint.rate_limit_config model field (validators=[])
             RateLimiterService configuration

    Raises:
        ValidationError: If config is malformed
    """
    if not isinstance(config, dict):
        raise ValidationError(_("Rate limit configuration must be a JSON object"))

    if "window_seconds" not in config:
        raise ValidationError(_("Rate limit configuration must include window_seconds"))

    if "max_requests" not in config:
        raise ValidationError(_("Rate limit configuration must include max_requests"))

    window_seconds = config["window_seconds"]
    max_requests   = config["max_requests"]

    if not isinstance(window_seconds, int) or window_seconds < 60:
        raise ValidationError(_("Rate limit window must be at least 60 seconds"))

    if not isinstance(max_requests, int) or max_requests < 1:
        raise ValidationError(_("Rate limit max requests must be at least 1"))

    if max_requests > 10000:
        raise ValidationError(_("Rate limit max requests cannot exceed 10000"))

    return config


# ── IP Whitelist Validation ───────────────────────────────────────────────────

def validate_ip_whitelist(whitelist: list) -> list:
    """
    Validate IP whitelist.

    Used by: WebhookEndpoint.allowed_ip_list, InboundWebhookService.check_ip()

    Raises:
        ValidationError: If any IP address is invalid
    """
    if not isinstance(whitelist, list):
        raise ValidationError(_("IP whitelist must be a list"))

    for ip in whitelist:
        if not isinstance(ip, str) or not ip.strip():
            raise ValidationError(_("IP addresses must be non-empty strings"))

        try:
            from ipaddress import ip_address, ip_network
            # Accept both single IPs and CIDR notation
            if "/" in ip:
                ip_network(ip, strict=False)
            else:
                ip_address(ip)
        except ValueError:
            raise ValidationError(
                _("Invalid IP address format: {}").format(ip)
            )

    return whitelist


# ── Headers Validation ────────────────────────────────────────────────────────

def validate_headers(headers: dict) -> dict:
    """
    Validate custom webhook headers.

    Used by: WebhookEndpoint.custom_headers, DispatchService._build_headers()

    Raises:
        ValidationError: If any header is restricted or malformed
    """
    if not isinstance(headers, dict):
        raise ValidationError(_("Headers must be a JSON object"))

    RESTRICTED = {"host", "authorization", "content-type", "content-length", "user-agent"}

    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValidationError(_('Header "{}" must be a string').format(key))

        if key.lower() in RESTRICTED:
            raise ValidationError(
                _('Header "{}" is restricted and cannot be overridden').format(key)
            )

    return headers


# ── Batch Size Validation ─────────────────────────────────────────────────────

def validate_batch_size(size: int) -> int:
    """
    Validate webhook batch size.

    Used by: WebhookBatch.batch_size field (validators=[validate_batch_size])
             BatchDispatchService

    Raises:
        ValidationError: If size is out of allowed range
    """
    if not isinstance(size, int):
        raise ValidationError(_("Batch size must be an integer"))

    if size < 1:
        raise ValidationError(_("Batch size must be at least 1"))

    if size > 1000:
        raise ValidationError(_("Batch size cannot exceed 1000"))

    return size


# ── Timeout Validation ────────────────────────────────────────────────────────

def validate_timeout(timeout: int) -> int:
    """
    Validate webhook timeout in seconds.

    Used by: WebhookEndpoint.timeout_seconds (validators=[validate_timeout])
             DispatchService HTTP request configuration

    Raises:
        ValidationError: If timeout is out of allowed range
    """
    if not isinstance(timeout, int):
        raise ValidationError(_("Timeout must be an integer"))

    if timeout < 1:
        raise ValidationError(_("Timeout must be at least 1 second"))

    if timeout > 300:
        raise ValidationError(_("Timeout cannot exceed 300 seconds"))

    return timeout


# ── Max Retries Validation ────────────────────────────────────────────────────

def validate_max_retries(max_retries: int) -> int:
    """
    Validate maximum retry attempts.

    Used by: WebhookEndpoint.max_retries, DispatchService retry logic

    Raises:
        ValidationError: If max_retries is out of allowed range
    """
    if not isinstance(max_retries, int):
        raise ValidationError(_("Max retries must be an integer"))

    if max_retries < 0:
        raise ValidationError(_("Max retries must be at least 0"))

    if max_retries > 10:
        raise ValidationError(_("Max retries cannot exceed 10"))

    return max_retries


# ── Public API ────────────────────────────────────────────────────────────────

__all__ = [
    "validate_webhook_url",
    "is_valid_webhook_url",
    "validate_secret",
    "validate_event_type",
    "validate_filter_config",
    "validate_payload_template",
    "validate_transform_rules",
    "validate_rate_limit_config",
    "validate_ip_whitelist",
    "validate_headers",
    "validate_batch_size",
    "validate_timeout",
    "validate_max_retries",
]
