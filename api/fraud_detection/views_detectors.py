# =============================================================================
# fraud_detection/views_detectors.py  (DRY-refactored)
# =============================================================================
"""
HTTP API for all 10 detectors in fraud_detection/detectors/.

DRY improvements
-----------------
• Extends FraudBaseView / FraudAdminView — eliminates 37 throttle_classes
  and 37 permission_classes lines.
• _ok/_err removed — uses self.ok()/self.err() from base.
• lazy_detector() and record_stat() imported from utils (no duplication).
• _DetectorBase mixin carries all detect/batch/config boilerplate;
  each concrete detector is reduced to 3 class-level attributes.
• DETECTOR_REGISTRY and SLUG_TO_KEY defined once.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from rest_framework import status
from api.fraud_detection.utils import (
    FraudBaseView, FraudAdminView, lazy_detector, record_stat,
)

logger      = logging.getLogger(__name__)
_UNAVAILABLE = "Detector module not available. Check detectors/ directory."


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DETECTOR_REGISTRY: Dict[str, Dict] = {
    "click_fraud": {
        "slug": "click-fraud", "class_name": "ClickFraudDetector",
        "description": "Detects fraudulent clicks: bots, duplicates, velocity abuse.",
        "input_fields": ["user_id","click_id","ip_address","offer_id","timestamp","user_agent"],
        "primary_method": "detect",
    },
    "device_fingerprint": {
        "slug": "device-fingerprint", "class_name": "DeviceFingerprinter",
        "description": "Generates and compares device fingerprints; flags spoofed/shared devices.",
        "input_fields": ["user_id","user_agent","screen_resolution","timezone","canvas_hash","ip_address"],
        "primary_method": "detect",
    },
    "multi_account": {
        "slug": "multi-account", "class_name": "MultiAccountDetector",
        "description": "Detects users operating multiple accounts via IP/device clustering.",
        "input_fields": ["user_id","ip_address","device_id","email_domain"],
        "primary_method": "detect",
    },
    "pattern_analyzer": {
        "slug": "pattern-analyzer", "class_name": "PatternAnalyzer",
        "description": "ML-based pattern analysis for behavioural anomalies.",
        "input_fields": ["user_id","events","timeframe_hours"],
        "primary_method": "analyze",
    },
    "vpn_proxy": {
        "slug": "vpn-proxy", "class_name": "VPNProxyDetector",
        "description": "Identifies VPN / proxy / Tor exit nodes from IP data.",
        "input_fields": ["ip_address","user_id"],
        "primary_method": "detect",
    },
    "biometrics": {
        "slug": "biometrics", "class_name": "BehavioralBiometricsAnalyzer",
        "description": "Session biometrics: typing cadence, scroll patterns, mouse dynamics.",
        "input_fields": ["user_id","session_id","keystrokes","mouse_events","duration_ms"],
        "primary_method": "analyze",
    },
    "geo_velocity": {
        "slug": "geo-velocity", "class_name": "GeoVelocityDetector",
        "description": "Impossible-travel detection based on login geo timestamps.",
        "input_fields": ["user_id","ip_address","timestamp"],
        "primary_method": "detect",
    },
    "graph_network": {
        "slug": "graph-network", "class_name": "GraphNetworkAnalyzer",
        "description": "Graph-based fraud ring and cluster analysis.",
        "input_fields": ["user_id","ip_address","device_id","referrer_id","related_user_ids"],
        "primary_method": "analyze",
    },
    "velocity_engine": {
        "slug": "velocity-engine", "class_name": "VelocityEngine",
        "description": "Sliding-window velocity checks per user/IP/event.",
        "input_fields": ["user_id","ip_address","event_type","timestamp"],
        "primary_method": "check",
    },
    "referral_fraud": {
        "slug": "referral-fraud", "class_name": "ReferralFraudDetector",
        "description": "Self-referral, referral rings, IP/device clustering, velocity.",
        "input_fields": ["referrer_user_id","referred_user_id","referral_code",
                         "ip_address","device_id","timestamp"],
        "primary_method": "detect",
    },
}

SLUG_TO_KEY = {v["slug"]: k for k, v in DETECTOR_REGISTRY.items()}


# =============================================================================
# Global views
# =============================================================================

class DetectorListAPIView(FraudBaseView):
    """GET /fraud/detectors/"""
    def get(self, request):
        available_only = request.query_params.get("available_only","false").lower() == "true"
        detectors = []
        for key, meta in DETECTOR_REGISTRY.items():
            inst      = lazy_detector(meta["class_name"])
            available = inst is not None
            if available_only and not available:
                continue
            detectors.append({
                "key": key, "slug": meta["slug"],
                "class_name": meta["class_name"],
                "description": meta["description"],
                "available": available,
                "input_fields": meta["input_fields"],
                "primary_method": meta["primary_method"],
                "detect_url": f"/fraud/detectors/{meta['slug']}/detect/",
                "batch_url":  f"/fraud/detectors/{meta['slug']}/batch/",
                "config_url": f"/fraud/detectors/{meta['slug']}/config/",
                "stats": cache.get(f"detector_stats:{meta['slug']}") or {},
            })
        return self.ok({"total": len(DETECTOR_REGISTRY),
                         "available": sum(1 for d in detectors if d["available"]),
                         "detectors": detectors})


class DetectorHealthAPIView(FraudBaseView):
    """GET /fraud/detectors/health/"""
    def get(self, request):
        health = [{"detector": k, "class_name": m["class_name"],
                   "status": "ok" if lazy_detector(m["class_name"]) else "unavailable"}
                  for k, m in DETECTOR_REGISTRY.items()]
        ok_n  = sum(1 for h in health if h["status"] == "ok")
        return self.ok({"overall": "healthy" if ok_n == len(health) else "degraded",
                         "available": ok_n, "total": len(health),
                         "detectors": health})


class DetectorStatsAPIView(FraudBaseView):
    """GET /fraud/detectors/stats/"""
    def get(self, request):
        stats = {k: cache.get(f"detector_stats:{m['slug']}") or {"runs":0,"errors":0}
                 for k, m in DETECTOR_REGISTRY.items()}
        return self.ok({
            "total_runs":   sum(s.get("runs",0)   for s in stats.values()),
            "total_errors": sum(s.get("errors",0) for s in stats.values()),
            "by_detector":  stats,
        })


class DetectorGenericRunAPIView(FraudBaseView):
    """POST /fraud/detectors/run/"""
    def post(self, request):
        slug    = request.data.get("detector")
        payload = request.data.get("data", {})
        if not slug:
            return self.err("detector slug is required.")
        key = SLUG_TO_KEY.get(slug)
        if key is None:
            return self.err(f"Unknown detector '{slug}'. "
                            f"Valid: {sorted(SLUG_TO_KEY.keys())}.")
        meta = DETECTOR_REGISTRY[key]
        inst = lazy_detector(meta["class_name"])
        if inst is None:
            return self.err(_UNAVAILABLE, status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            method = getattr(inst, meta["primary_method"], None) or inst.detect
            result = method(payload)
            record_stat(slug, True, request.user)
            return self.ok({"detector": slug, "method": meta["primary_method"],
                             "result": result})
        except Exception as exc:
            record_stat(slug, False, request.user)
            logger.exception("DetectorGenericRunAPIView detector=%s: %s", slug, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Shared detector mixin  (DRY: all 10 detectors × 3 views share this)
# =============================================================================

class _DetectorBase(FraudBaseView):
    """
    All three views per detector (detect/analyze/check, batch, config)
    inherit from this. Subclasses set class-level attributes only.

    Concrete detectors override _class_name, _slug, _batch_key,
    _primary_method, and optionally _validate_detect().
    """
    _class_name:    str = ""
    _slug:          str = ""
    _primary_method:str = "detect"
    _batch_key:     str = "items"

    def _inst(self):
        return lazy_detector(self._class_name)

    def _unavail(self):
        return self.err(_UNAVAILABLE, status.HTTP_503_SERVICE_UNAVAILABLE)

    def _validate_detect(self, request):
        """Override to add required-field validation. Return err or None."""
        return None

    # ── detect / analyze / check ──────────────────────────────────────────
    def _detect_post(self, request):
        if e := self._validate_detect(request): return e
        inst = self._inst()
        if inst is None: return self._unavail()
        try:
            method = getattr(inst, self._primary_method, None) or inst.detect
            result = method(request.data)
            record_stat(self._slug, True, request.user)
            return self.ok({"detector": self._slug.replace("-","_"), "result": result})
        except Exception as exc:
            record_stat(self._slug, False, request.user)
            logger.exception("%s._detect_post: %s", self.__class__.__name__, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── batch ─────────────────────────────────────────────────────────────
    def _batch_post(self, request):
        items = request.data.get(self._batch_key, [])[:200]
        if not items:
            return self.err(f"{self._batch_key} list is required.")
        inst = self._inst()
        if inst is None: return self._unavail()
        try:
            method = getattr(inst, self._primary_method, None) or inst.detect
            results = (inst.batch_detect(items)
                       if hasattr(inst, "batch_detect")
                       else [method(i) for i in items])
            record_stat(self._slug, True, request.user)
            return self.ok({"detector": self._slug.replace("-","_"),
                             "count": len(results), "results": results})
        except Exception as exc:
            record_stat(self._slug, False, request.user)
            logger.exception("%s._batch_post: %s", self.__class__.__name__, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── config GET ────────────────────────────────────────────────────────
    def _config_get(self, request):
        inst = self._inst()
        if inst is None: return self._unavail()
        cfg = getattr(inst, "_cfg", None) or getattr(inst, "config", {})
        return self.ok({"detector": self._slug.replace("-","_"), "config": cfg})

    # ── config PATCH ──────────────────────────────────────────────────────
    def _config_patch(self, request):
        if e := self.require_admin(request): return e
        from django.conf import settings
        key = self._slug.upper().replace("-","_") + "_CONFIG"
        cfg = getattr(settings, key, {})
        cfg.update(request.data)
        setattr(settings, key, cfg)
        return self.ok({"updated": True, "config": cfg})


# =============================================================================
# 10 concrete detector view triplets
# Each detector = 3 view classes (detect, batch, config) with ≤6 lines each.
# =============================================================================

# ── 1. ClickFraudDetector ────────────────────────────────────────────────────
class ClickFraudDetectAPIView(_DetectorBase):
    _class_name = "ClickFraudDetector"; _slug = "click-fraud"
    _batch_key  = "events"
    def post(self, request): return self._detect_post(request)

class ClickFraudBatchAPIView(_DetectorBase):
    _class_name = "ClickFraudDetector"; _slug = "click-fraud"
    _batch_key  = "events"
    def post(self, request): return self._batch_post(request)

class ClickFraudConfigAPIView(_DetectorBase):
    _class_name = "ClickFraudDetector"; _slug = "click-fraud"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 2. DeviceFingerprinter ───────────────────────────────────────────────────
class DeviceFingerprinterDetectAPIView(_DetectorBase):
    _class_name     = "DeviceFingerprinter"; _slug = "device-fingerprint"
    _primary_method = "fingerprint"; _batch_key = "devices"
    def post(self, request): return self._detect_post(request)

class DeviceFingerprinterBatchAPIView(_DetectorBase):
    _class_name     = "DeviceFingerprinter"; _slug = "device-fingerprint"
    _primary_method = "fingerprint"; _batch_key = "devices"
    def post(self, request): return self._batch_post(request)

class DeviceFingerprinterConfigAPIView(_DetectorBase):
    _class_name = "DeviceFingerprinter"; _slug = "device-fingerprint"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 3. MultiAccountDetector ──────────────────────────────────────────────────
class MultiAccountDetectAPIView(_DetectorBase):
    _class_name = "MultiAccountDetector"; _slug = "multi-account"
    _batch_key  = "users"
    def post(self, request): return self._detect_post(request)

class MultiAccountBatchAPIView(_DetectorBase):
    _class_name = "MultiAccountDetector"; _slug = "multi-account"
    _batch_key  = "users"
    def post(self, request): return self._batch_post(request)

class MultiAccountConfigAPIView(_DetectorBase):
    _class_name = "MultiAccountDetector"; _slug = "multi-account"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 4. PatternAnalyzer ───────────────────────────────────────────────────────
class PatternAnalyzerAPIView(_DetectorBase):
    _class_name     = "PatternAnalyzer"; _slug = "pattern-analyzer"
    _primary_method = "analyze"; _batch_key = "users"
    def post(self, request): return self._detect_post(request)

class PatternAnalyzerBatchAPIView(_DetectorBase):
    _class_name     = "PatternAnalyzer"; _slug = "pattern-analyzer"
    _primary_method = "analyze"; _batch_key = "users"
    def post(self, request): return self._batch_post(request)

class PatternAnalyzerConfigAPIView(_DetectorBase):
    _class_name = "PatternAnalyzer"; _slug = "pattern-analyzer"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 5. VPNProxyDetector ──────────────────────────────────────────────────────
class VPNProxyDetectAPIView(_DetectorBase):
    _class_name = "VPNProxyDetector"; _slug = "vpn-proxy"
    _batch_key  = "ip_addresses"
    def _validate_detect(self, r):
        if not r.data.get("ip_address"):
            return self.err("ip_address is required.")
    def post(self, request): return self._detect_post(request)

class VPNProxyBatchAPIView(_DetectorBase):
    _class_name = "VPNProxyDetector"; _slug = "vpn-proxy"
    _batch_key  = "ip_addresses"
    def post(self, request):
        ips = request.data.get("ip_addresses", [])[:100]
        if not ips: return self.err("ip_addresses list is required.")
        inst = self._inst()
        if inst is None: return self._unavail()
        try:
            results = (inst.batch_detect([{"ip_address": ip} for ip in ips])
                       if hasattr(inst, "batch_detect")
                       else [inst.detect({"ip_address": ip}) for ip in ips])
            record_stat(self._slug, True, request.user)
            return self.ok({"detector": "vpn_proxy", "count": len(results),
                             "results": results})
        except Exception as exc:
            record_stat(self._slug, False, request.user)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

class VPNProxyConfigAPIView(_DetectorBase):
    _class_name = "VPNProxyDetector"; _slug = "vpn-proxy"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 6. BehavioralBiometricsAnalyzer ──────────────────────────────────────────
class BiometricsAnalyzeAPIView(_DetectorBase):
    _class_name     = "BehavioralBiometricsAnalyzer"; _slug = "biometrics"
    _primary_method = "analyze"; _batch_key = "sessions"
    def post(self, request): return self._detect_post(request)

class BiometricsBatchAPIView(_DetectorBase):
    _class_name     = "BehavioralBiometricsAnalyzer"; _slug = "biometrics"
    _primary_method = "analyze"; _batch_key = "sessions"
    def post(self, request): return self._batch_post(request)

class BiometricsConfigAPIView(_DetectorBase):
    _class_name = "BehavioralBiometricsAnalyzer"; _slug = "biometrics"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 7. GeoVelocityDetector ───────────────────────────────────────────────────
class GeoVelocityDetectAPIView(_DetectorBase):
    _class_name = "GeoVelocityDetector"; _slug = "geo-velocity"
    _batch_key  = "events"
    def _validate_detect(self, r):
        if not r.data.get("user_id"):    return self.err("user_id is required.")
        if not r.data.get("ip_address"): return self.err("ip_address is required.")
    def post(self, request): return self._detect_post(request)

class GeoVelocityBatchAPIView(_DetectorBase):
    _class_name = "GeoVelocityDetector"; _slug = "geo-velocity"
    _batch_key  = "events"
    def post(self, request): return self._batch_post(request)

class GeoVelocityConfigAPIView(_DetectorBase):
    _class_name = "GeoVelocityDetector"; _slug = "geo-velocity"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 8. GraphNetworkAnalyzer ──────────────────────────────────────────────────
class GraphNetworkAnalyzeAPIView(_DetectorBase):
    _class_name     = "GraphNetworkAnalyzer"; _slug = "graph-network"
    _primary_method = "analyze"; _batch_key = "entities"
    def _validate_detect(self, r):
        if not r.data.get("user_id"): return self.err("user_id is required.")
    def post(self, request): return self._detect_post(request)

class GraphNetworkBatchAPIView(_DetectorBase):
    _class_name     = "GraphNetworkAnalyzer"; _slug = "graph-network"
    _primary_method = "analyze"; _batch_key = "entities"
    def post(self, request): return self._batch_post(request)

class GraphNetworkConfigAPIView(_DetectorBase):
    _class_name = "GraphNetworkAnalyzer"; _slug = "graph-network"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 9. VelocityEngine ────────────────────────────────────────────────────────
class VelocityEngineCheckAPIView(_DetectorBase):
    _class_name     = "VelocityEngine"; _slug = "velocity-engine"
    _primary_method = "check"; _batch_key = "events"
    def _validate_detect(self, r):
        if not r.data.get("user_id"):    return self.err("user_id is required.")
        if not r.data.get("event_type"): return self.err("event_type is required.")
    def post(self, request): return self._detect_post(request)

class VelocityEngineBatchAPIView(_DetectorBase):
    _class_name     = "VelocityEngine"; _slug = "velocity-engine"
    _primary_method = "check"; _batch_key = "events"
    def post(self, request): return self._batch_post(request)

class VelocityEngineResetAPIView(FraudAdminView):
    """POST /fraud/detectors/velocity-engine/reset/"""
    def post(self, request):
        uid  = request.data.get("user_id")
        et   = request.data.get("event_type")
        ip   = request.data.get("ip_address")
        if not any([uid, et, ip]):
            return self.err("At least one of user_id, event_type, ip_address required.")
        inst = lazy_detector("VelocityEngine")
        if inst is None:
            return self.err(_UNAVAILABLE, status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            result = (inst.reset(user_id=uid, event_type=et, ip_address=ip)
                      if hasattr(inst, "reset")
                      else {"reset": True, "note": "reset() not implemented"})
            record_stat("velocity-engine", True, request.user)
            return self.ok({"detector": "velocity_engine", "result": result})
        except Exception as exc:
            logger.exception("VelocityEngineResetAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

class VelocityEngineConfigAPIView(_DetectorBase):
    _class_name     = "VelocityEngine"; _slug = "velocity-engine"
    _primary_method = "check"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── 10. ReferralFraudDetector ────────────────────────────────────────────────
class ReferralFraudDetectAPIView(_DetectorBase):
    _class_name = "ReferralFraudDetector"; _slug = "referral-fraud"
    _batch_key  = "referrals"
    def _validate_detect(self, r):
        if not r.data.get("referrer_user_id"):
            return self.err("referrer_user_id is required.")
        if not r.data.get("referred_user_id"):
            return self.err("referred_user_id is required.")
    def post(self, request):
        if e := self._validate_detect(request): return e
        inst = self._inst()
        if inst is None: return self._unavail()
        try:
            result = inst.detect(dict(request.data))
            record_stat(self._slug, True, request.user)
            return self.ok({
                "detector":  "referral_fraud",
                "risk_score": result.get("risk_score", 0),
                "is_fraud":   result.get("is_fraud", False),
                "reasons":    result.get("reasons", []),
                "full":       result,
            })
        except Exception as exc:
            record_stat(self._slug, False, request.user)
            logger.exception("ReferralFraudDetectAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReferralFraudBatchAPIView(_DetectorBase):
    _class_name = "ReferralFraudDetector"; _slug = "referral-fraud"
    _batch_key  = "referrals"
    def post(self, request):
        refs = request.data.get("referrals", [])[:100]
        if not refs: return self.err("referrals list is required (max 100).")
        inst = self._inst()
        if inst is None: return self._unavail()
        try:
            results     = inst.batch_detect(refs)
            fraud_count = sum(1 for r in results if r.get("is_fraud"))
            record_stat(self._slug, True, request.user)
            return self.ok({"detector": "referral_fraud",
                             "total": len(results), "fraud_found": fraud_count,
                             "results": results})
        except Exception as exc:
            record_stat(self._slug, False, request.user)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReferralFraudAnalyzeAPIView(_DetectorBase):
    _class_name     = "ReferralFraudDetector"; _slug = "referral-fraud"
    _primary_method = "analyze"
    def post(self, request):
        if not request.data.get("referrer_user_id"):
            return self.err("referrer_user_id is required.")
        inst = self._inst()
        if inst is None: return self._unavail()
        try:
            result = inst.analyze(dict(request.data))
            record_stat(self._slug, True, request.user)
            return self.ok({"detector": "referral_fraud", "analysis": result})
        except Exception as exc:
            record_stat(self._slug, False, request.user)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReferralFraudConfigAPIView(_DetectorBase):
    _class_name = "ReferralFraudDetector"; _slug = "referral-fraud"
    def get(self, request):   return self._config_get(request)
    def patch(self, request): return self._config_patch(request)


# ── ALIASES + MISSING: names expected by urls.py & detectors/urls.py ─────────
from api.fraud_detection.detectors import DETECTOR_REGISTRY

class DetectorRunAPIView(_DetectorBase):
    """POST /detectors/<slug>/run/ — run a specific detector by slug."""
    def post(self, request, detector: str = ""):
        cls = DETECTOR_REGISTRY.get(detector.replace("-", "_").lower()) or \
              DETECTOR_REGISTRY.get(detector)
        if not cls:
            from rest_framework.response import Response
            from rest_framework import status
            return Response({"error": f"Unknown detector: {detector}"}, status=status.HTTP_404_NOT_FOUND)
        try:
            result = cls().detect(request.data)
            from rest_framework.response import Response
            return Response({"success": True, "detector": detector, "result": result})
        except Exception as exc:
            from rest_framework.response import Response
            from rest_framework import status
            return Response({"success": False, "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DetectorStatusAPIView(_DetectorBase):
    """GET /detectors/<slug>/status/ — current detector state."""
    def get(self, request, detector: str = ""):
        from rest_framework.response import Response
        cls = DETECTOR_REGISTRY.get(detector)
        if not cls:
            from rest_framework import status
            return Response({"error": f"Unknown detector: {detector}"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detector": detector, "status": "active", "class": cls.__name__})

class DetectorBatchAPIView(_DetectorBase):
    """POST /detectors/<slug>/batch/ — run detector on a list of records."""
    def post(self, request, detector: str = ""):
        from rest_framework.response import Response
        from rest_framework import status
        cls = DETECTOR_REGISTRY.get(detector)
        if not cls:
            return Response({"error": f"Unknown detector: {detector}"}, status=status.HTTP_404_NOT_FOUND)
        records = request.data.get("records", [])
        det = cls()
        results = []
        for rec in records:
            try:
                results.append({"input": rec, "result": det.detect(rec)})
            except Exception as exc:
                results.append({"input": rec, "error": str(exc)})
        return Response({"detector": detector, "processed": len(results), "results": results})

class DetectorMetricsAPIView(_DetectorBase):
    """GET /detectors/<slug>/metrics/ — performance metrics."""
    def get(self, request, detector: str = ""):
        from rest_framework.response import Response
        from django.core.cache import cache
        key     = f"detector_metrics:{detector}"
        metrics = cache.get(key, {"total_runs": 0, "avg_latency_ms": 0, "error_rate": 0})
        return Response({"detector": detector, "metrics": metrics})

class DetectorConfigAPIView(_DetectorBase):
    """GET/POST /detectors/<slug>/config/ — read or update detector config."""
    def get(self, request, detector: str = ""):
        from rest_framework.response import Response
        from django.core.cache import cache
        return Response({"detector": detector, "config": cache.get(f"detector_config:{detector}", {})})

    def post(self, request, detector: str = ""):
        from rest_framework.response import Response
        from django.core.cache import cache
        cache.set(f"detector_config:{detector}", request.data, timeout=86400)
        return Response({"detector": detector, "config": request.data, "saved": True})

class DetectorResetAPIView(_DetectorBase):
    """POST /detectors/<slug>/reset/ — reset detector state/config."""
    def post(self, request, detector: str = ""):
        from rest_framework.response import Response
        from django.core.cache import cache
        cache.delete(f"detector_config:{detector}")
        cache.delete(f"detector_metrics:{detector}")
        return Response({"detector": detector, "reset": True})

class DetectorRunAllAPIView(DetectorListAPIView):
    """POST /detectors/run-all/ — run ALL detectors on a payload."""
    def post(self, request):
        from rest_framework.response import Response
        payload = request.data
        results = {}
        for slug, cls in DETECTOR_REGISTRY.items():
            try:
                results[slug] = cls().detect(payload)
            except Exception as exc:
                results[slug] = {"error": str(exc)}
        return Response({"results": results, "total": len(results)})
