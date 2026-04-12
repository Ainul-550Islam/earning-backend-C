from __future__ import annotations

import json
from typing import Any

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import SiteSettings


DEFAULT_ACTIVE_FEATURES = ["3D_WALLET", "ENGAGEMENT_HUB", "DAILY_GOLDEN_COIN_CLAIM"]


def _coerce_str(value: Any, default: str | None = None) -> str | None:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _parse_active_features(value: Any) -> list[str]:
    if value is None:
        return DEFAULT_ACTIVE_FEATURES

    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    if isinstance(value, dict):
        return [str(k).strip() for k, enabled in value.items() if bool(enabled) and str(k).strip()]

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return DEFAULT_ACTIVE_FEATURES
        if text.startswith("[") or text.startswith("{"):
            try:
                return _parse_active_features(json.loads(text))
            except Exception:
                pass
        return [part.strip() for part in text.split(",") if part.strip()]

    return DEFAULT_ACTIVE_FEATURES


def _get_setting(tenant_id: str, key: str, default: Any = None) -> Any:
    # White-label key strategy:
    # 1) tenant.{tenant_id}.{key}
    # 2) {tenant_id}.{key}
    # 3) plain {key}
    candidates = [
        f"tenant.{tenant_id}.{key}",
        f"{tenant_id}.{key}",
        key,
    ]
    for candidate in candidates:
        try:
            setting = SiteSettings.objects.get(key=candidate, is_public=True)
            return setting.get_value()
        except SiteSettings.DoesNotExist:
            continue
    return default


@api_view(["GET"])
@permission_classes([AllowAny])
def public_tenant_settings(request):
    tenant_id = request.headers.get("X-Tenant-ID", "default").strip() or "default"

    site_name = _coerce_str(_get_setting(tenant_id, "site_name", "Dashboard"), "Dashboard")
    logo_url = _coerce_str(_get_setting(tenant_id, "logo_url", None), None)
    primary_color = _coerce_str(_get_setting(tenant_id, "primary_color", "#22e6ff"), "#22e6ff")
    secondary_color = _coerce_str(_get_setting(tenant_id, "secondary_color", "#9b5cff"), "#9b5cff")
    google_client_id = _coerce_str(_get_setting(tenant_id, "google_client_id", None), None)
    active_features = _parse_active_features(_get_setting(tenant_id, "active_features", DEFAULT_ACTIVE_FEATURES))

    return Response(
        {
            "site_name": site_name,
            "logo_url": logo_url,
            "primary_color": primary_color,
            "secondary_color": secondary_color,
            "google_client_id": google_client_id,
            "active_features": active_features,
        }
    )

