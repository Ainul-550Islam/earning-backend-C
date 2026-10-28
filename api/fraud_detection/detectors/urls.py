# =============================================================================
# fraud_detection/detectors/urls.py  — NEW FILE
# Included by master urls.py under: path("detectors/", include(...))
#
# Each detector gets:  run/, status/, metrics/, batch/
# Plus shared:         list/, run-all/, health/
# =============================================================================
from django.urls import path

# Views live in root-level views_detectors.py (DRY — logic defined once)
from api.fraud_detection.views_detectors import (
    DetectorListAPIView,
    DetectorStatusAPIView,
    DetectorRunAPIView,
    DetectorBatchAPIView,
    DetectorMetricsAPIView,
    DetectorHealthAPIView,
    DetectorRunAllAPIView,
    DetectorConfigAPIView,
    DetectorResetAPIView,
)

app_name = "detectors"

# ── Helper: build standard 4-endpoint group for a named detector ──────────────
def detector_routes(slug: str, name_prefix: str):
    return [
        path(f"{slug}/run/",     DetectorRunAPIView.as_view(),     {"detector": slug}, name=f"{name_prefix}-run"),
        path(f"{slug}/status/",  DetectorStatusAPIView.as_view(),  {"detector": slug}, name=f"{name_prefix}-status"),
        path(f"{slug}/metrics/", DetectorMetricsAPIView.as_view(), {"detector": slug}, name=f"{name_prefix}-metrics"),
        path(f"{slug}/batch/",   DetectorBatchAPIView.as_view(),   {"detector": slug}, name=f"{name_prefix}-batch"),
        path(f"{slug}/config/",  DetectorConfigAPIView.as_view(),  {"detector": slug}, name=f"{name_prefix}-config"),
        path(f"{slug}/reset/",   DetectorResetAPIView.as_view(),   {"detector": slug}, name=f"{name_prefix}-reset"),
    ]


urlpatterns = [
    # ── Shared endpoints ──────────────────────────────────────────────────────
    path("",              DetectorListAPIView.as_view(),   name="detector-list"),
    path("run-all/",      DetectorRunAllAPIView.as_view(), name="detector-run-all"),
    path("health/",       DetectorHealthAPIView.as_view(), name="detector-health"),

    # ── VelocityEngine ────────────────────────────────────────────────────────
    *detector_routes("velocity-engine",      "velocity-engine"),

    # ── BehavioralBiometrics ──────────────────────────────────────────────────
    *detector_routes("behavioral-biometrics", "behavioral-biometrics"),

    # ── ClickFraud ────────────────────────────────────────────────────────────
    *detector_routes("click-fraud",           "click-fraud"),

    # ── DeviceFingerprinter ───────────────────────────────────────────────────
    *detector_routes("device-fingerprinter",  "device-fingerprinter"),

    # ── GeoVelocity ───────────────────────────────────────────────────────────
    *detector_routes("geo-velocity",          "geo-velocity"),

    # ── GraphNetwork ──────────────────────────────────────────────────────────
    *detector_routes("graph-network",         "graph-network"),

    # ── MultiAccount ──────────────────────────────────────────────────────────
    *detector_routes("multi-account",         "multi-account"),

    # ── PatternAnalyzer ───────────────────────────────────────────────────────
    *detector_routes("pattern-analyzer",      "pattern-analyzer"),

    # ── ReferralFraud ─────────────────────────────────────────────────────────
    *detector_routes("referral-fraud",        "referral-fraud"),

    # ── VPNProxy ──────────────────────────────────────────────────────────────
    *detector_routes("vpn-proxy",             "vpn-proxy"),
]
