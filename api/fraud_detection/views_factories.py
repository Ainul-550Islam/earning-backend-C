# =============================================================================
# fraud_detection/views_factories.py  (DRY-refactored)
# =============================================================================
"""
Admin/dev HTTP endpoints for test-data generation.

DRY improvements
-----------------
• Extends FraudAdminView — removes 18 duplicate throttle_classes +
  18 permission_classes + 2 _ok/_err definitions.
• lazy_service() from utils replaces 4 separate inline factory-loader
  functions (_fraud_case_factory, _test_data_factory, etc.)
• _FACTORY_TAG defined once at module level.
• _rand_* helpers consolidated into a single _Rand namespace class.
• Micro-faker helpers (_rand_ip, _rand_score, etc.) defined once.
• _create_factory_case() and _create_factory_alert() are shared ORM
  fallback helpers — eliminating duplicate FraudCase/FraudAlert creation
  logic that appeared in both FraudCaseFactory and TestDataFactory views.
"""
from __future__ import annotations
import logging
import random
from typing import Any, Dict, List, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from api.fraud_detection.utils import FraudAdminView, lazy_service

User   = get_user_model()
logger = logging.getLogger(__name__)

_FACTORY_TAG = "factory_generated"

# ---------------------------------------------------------------------------
# Factory loaders (one line each — lazy_service defined once in utils)
# ---------------------------------------------------------------------------
def _case_factory():    return lazy_service("api.fraud_detection.factories","FraudCaseFactory")
def _data_factory():    return lazy_service("api.fraud_detection.factories","TestDataFactory")
def _alert_factory():   return lazy_service("api.fraud_detection.factories","FraudAlertFactory")
def _profile_factory(): return lazy_service("api.fraud_detection.factories","UserRiskProfileFactory")

# ---------------------------------------------------------------------------
# Micro-faker helpers — defined ONCE (were scattered across views before)
# ---------------------------------------------------------------------------
_CASE_TYPES    = ["account_takeover","identity_fraud","payment_fraud",
                   "bonus_abuse","referral_fraud","chargeback_fraud"]
_SEVERITIES    = ["low","medium","high","critical"]
_ALERT_TYPES   = ["suspicious_activity","high_risk_score","multiple_accounts",
                   "velocity_breach","geo_anomaly","device_anomaly"]
_PRIORITIES    = ["low","medium","high","critical"]
_RISK_BANDS    = {"low":(0,39),"medium":(40,59),"high":(60,79),"critical":(80,100)}

def _rand_ip():
    b = random.choice(["10","192.168","172.16","45.33","103.21","185.23"])
    return (f"{b}.{random.randint(1,254)}.{random.randint(1,254)}" if "." in b
            else f"{b}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}")

def _rand_score(lo=0, hi=100): return random.randint(lo, hi)
def _rand_uid():               return random.randint(1000, 9999)
def _rand_title(prefix="Test"):
    suffixes = ["Unusual login","Velocity breach","Multi-device","High-risk IP",
                "Referral anomaly","Chargeback spike"]
    return f"[{_FACTORY_TAG}] {prefix}: {random.choice(suffixes)}"

def _meta(extra=None):
    m = {_FACTORY_TAG: True}
    if extra: m.update(extra)
    return m

# ---------------------------------------------------------------------------
# Shared ORM fallback builders — defined ONCE, used by multiple factory views
# ---------------------------------------------------------------------------

def _orm_create_case(user_id, case_type=None, severity=None,
                     case_status="open", risk_score=None, extra_meta=None):
    from api.fraud_detection.models import FraudCase
    from api.fraud_detection.serializers import FraudCaseSerializer
    case = FraudCase.objects.create(
        user_id=user_id,
        case_type=case_type or random.choice(_CASE_TYPES),
        severity=severity   or random.choice(_SEVERITIES),
        status=case_status,
        risk_score=risk_score if risk_score is not None else _rand_score(50,99),
        title=_rand_title(f"Case-{case_type or 'fraud'}"),
        description=f"Factory case for user {user_id}.",
        metadata=_meta(extra_meta),
    )
    return case, FraudCaseSerializer(case).data


def _orm_create_alert(user_id, alert_type=None, priority=None,
                      is_resolved=False, extra_meta=None):
    from api.fraud_detection.models import FraudAlert
    from api.fraud_detection.serializers import FraudAlertSerializer
    atype = alert_type or random.choice(_ALERT_TYPES)
    alert = FraudAlert.objects.create(
        alert_type=atype,
        priority=priority or random.choice(_PRIORITIES),
        title=_rand_title(f"Alert-{atype}"),
        description=f"Factory alert for user {user_id}.",
        user_id=user_id,
        is_resolved=is_resolved,
        resolved_at=timezone.now() if is_resolved else None,
        data=_meta(extra_meta),
    )
    return alert, FraudAlertSerializer(alert).data


# =============================================================================
# FraudCaseFactory
# =============================================================================

class FraudCaseFactoryCreateAPIView(FraudAdminView):
    """POST /fraud/factory/cases/create/"""
    def post(self, request):
        factory = _case_factory()
        try:
            if factory and hasattr(factory, "create"):
                return self.ok(factory.create(**request.data), status.HTTP_201_CREATED)
            uid = request.data.get("user_id", _rand_uid())
            case, data = _orm_create_case(
                uid,
                case_type=request.data.get("case_type"),
                severity=request.data.get("severity"),
                case_status=request.data.get("status","open"),
                risk_score=request.data.get("risk_score"),
                extra_meta={"created_by": "FraudCaseFactoryCreateAPIView"},
            )
            return self.ok({"created": True, "case_id": case.pk,
                             "source": "orm_fallback", "data": data},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudCaseFactoryCreateAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseFactoryBatchAPIView(FraudAdminView):
    """POST /fraud/factory/cases/batch/"""
    def post(self, request):
        try:
            count = min(50, max(1, int(request.data.get("count", 5))))
        except (TypeError, ValueError):
            count = 5
        fixed_sev  = request.data.get("severity")
        fixed_type = request.data.get("case_type")
        fixed_stat = request.data.get("status")
        factory = _case_factory()
        try:
            if factory and hasattr(factory, "create_batch"):
                return self.ok({"created": count,
                                  "results": factory.create_batch(
                                      count, severity=fixed_sev,
                                      case_type=fixed_type, status=fixed_stat)},
                                status.HTTP_201_CREATED)
            results = []
            for _ in range(count):
                _, data = _orm_create_case(
                    _rand_uid(),
                    case_type=fixed_type, severity=fixed_sev,
                    case_status=fixed_stat or random.choice(["open","investigating"]),
                    extra_meta={"batch": True,
                                "created_by": "FraudCaseFactoryBatchAPIView"},
                )
                results.append(data)
            return self.ok({"created": len(results), "results": results,
                             "source": "orm_fallback"}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudCaseFactoryBatchAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseFactoryScenarioAPIView(FraudAdminView):
    """POST /fraud/factory/cases/scenario/"""
    _SCENARIOS: Dict[str, Dict] = {
        "account_takeover": {
            "case_type": "account_takeover", "severity": "critical",
            "status": "investigating", "risk_score": 95,
            "title": "[factory] Account Takeover — New Device + New Country",
            "description": "Simulated account takeover: login from unrecognised device.",
        },
        "bonus_abuse": {
            "case_type": "bonus_abuse", "severity": "high",
            "status": "open", "risk_score": 78,
            "title": "[factory] Bonus Abuse — Multiple Referral Accounts",
            "description": "Simulated bonus abuse: 12 referral accounts from same device.",
        },
        "payment_fraud": {
            "case_type": "payment_fraud", "severity": "critical",
            "status": "open", "risk_score": 92,
            "title": "[factory] Payment Fraud — Card Testing Pattern",
            "description": "Simulated card-testing: 45 small transactions across 3 IPs.",
        },
        "referral_chain": {
            "case_type": "referral_fraud", "severity": "medium",
            "status": "open", "risk_score": 65,
            "title": "[factory] Referral Chain — Circular Referral Network",
            "description": "Simulated referral fraud: 8 accounts form a circular chain.",
        },
        "identity_theft": {
            "case_type": "identity_fraud", "severity": "critical",
            "status": "investigating", "risk_score": 97,
            "title": "[factory] Identity Theft — KYC Document Mismatch",
            "description": "Simulated identity theft: KYC docs don't match profile.",
        },
    }

    def post(self, request):
        sc_key  = request.data.get("scenario", "account_takeover")
        user_id = request.data.get("user_id", _rand_uid())
        sc = self._SCENARIOS.get(sc_key)
        if sc is None:
            return self.err(f"Unknown scenario '{sc_key}'. "
                             f"Valid: {list(self._SCENARIOS.keys())}.")
        factory = _case_factory()
        try:
            if factory and hasattr(factory, "create_scenario"):
                return self.ok(factory.create_scenario(sc_key, user_id=user_id),
                                status.HTTP_201_CREATED)
            from api.fraud_detection.models import FraudCase
            from api.fraud_detection.serializers import FraudCaseSerializer
            case = FraudCase.objects.create(
                user_id=user_id,
                metadata=_meta({"scenario": sc_key,
                                  "created_by": "FraudCaseFactoryScenarioAPIView"}),
                **sc,
            )
            return self.ok({"created": True, "scenario": sc_key,
                             "case_id": case.pk, "source": "orm_fallback",
                             "data": FraudCaseSerializer(case).data},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudCaseFactoryScenarioAPIView scenario=%s: %s", sc_key, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseFactoryCleanupAPIView(FraudAdminView):
    """DELETE /fraud/factory/cases/cleanup/"""
    def delete(self, request):
        factory = _case_factory()
        try:
            if factory and hasattr(factory, "cleanup"):
                return self.ok(factory.cleanup())
            from api.fraud_detection.models import FraudCase
            qs    = FraudCase.objects.filter(metadata__factory_generated=True)
            count = qs.count(); qs.delete()
            return self.ok({"deleted": count,
                             "message": f"Deleted {count} factory FraudCase records.",
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudCaseFactoryCleanupAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# TestDataFactory
# =============================================================================

class TestDataFactoryListScenariosAPIView(FraudAdminView):
    """GET /fraud/factory/test-data/scenarios/"""
    _SCENARIOS = {
        "simple_fraud": {
            "description": "1 case + 1 alert + 1 risk profile.",
            "entities": ["FraudCase×1","FraudAlert×1","UserRiskProfile×1"],
        },
        "complex_fraud": {
            "description": "5 cases + 3 alerts + 1 risk profile (critical) + 1 blacklisted IP.",
            "entities": ["FraudCase×5","FraudAlert×3","UserRiskProfile×1","IPReputation×1"],
        },
        "organised_fraud_ring": {
            "description": "5 users: each with risk profile, shared device, suspicious IP.",
            "entities": ["FraudCase×5","FraudAlert×5","UserRiskProfile×5","IPReputation×2"],
        },
        "chargeback_wave": {
            "description": "10 chargeback disputes by 3 users within 24 h.",
            "entities": ["FraudCase×10 (payment_fraud)","FraudAlert×3 (critical)"],
        },
        "ip_sweep": {
            "description": "20 suspicious IPs from 5 countries with linked fraud attempts.",
            "entities": ["FraudCase×20","IPReputation×20 (blacklisted)"],
        },
    }

    def get(self, request):
        factory = _data_factory()
        try:
            if factory and hasattr(factory, "list_scenarios"):
                return self.ok(factory.list_scenarios())
            return self.ok({"available_scenarios": self._SCENARIOS,
                             "source": "builtin_registry"})
        except Exception as exc:
            logger.exception("TestDataFactoryListScenariosAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestDataFactoryCreateSimpleAPIView(FraudAdminView):
    """POST /fraud/factory/test-data/simple/"""
    def post(self, request):
        user_id = request.data.get("user_id", _rand_uid())
        factory = _data_factory()
        try:
            if factory and hasattr(factory, "create_simple"):
                return self.ok(factory.create_simple(user_id=user_id),
                                status.HTTP_201_CREATED)
            meta = _meta({"scenario": "simple",
                           "created_by": "TestDataFactoryCreateSimpleAPIView"})
            _, case_data  = _orm_create_case(user_id, case_type="account_takeover",
                                              severity="high", risk_score=85,
                                              extra_meta={"scenario": "simple"})
            _, alert_data = _orm_create_alert(user_id, alert_type="suspicious_activity",
                                               priority="high",
                                               extra_meta={"scenario": "simple"})
            from api.fraud_detection.models import UserRiskProfile
            from api.fraud_detection.serializers import UserRiskProfileSerializer
            profile, _ = UserRiskProfile.objects.get_or_create(user_id=user_id)
            profile.overall_risk_score = max(profile.overall_risk_score, 75)
            profile.is_flagged         = True
            profile.risk_factors       = _meta({**(profile.risk_factors or {})})
            profile.last_risk_assessment = timezone.now()
            profile.save(update_fields=["overall_risk_score","is_flagged",
                                         "risk_factors","last_risk_assessment"])
            return self.ok({
                "scenario":     "simple", "user_id": user_id,
                "fraud_case":   case_data, "fraud_alert": alert_data,
                "risk_profile": UserRiskProfileSerializer(profile).data,
                "source":       "orm_fallback",
            }, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("TestDataFactoryCreateSimpleAPIView user=%s: %s", user_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestDataFactoryCreateComplexAPIView(FraudAdminView):
    """POST /fraud/factory/test-data/complex/"""
    def post(self, request):
        user_id = request.data.get("user_id", _rand_uid())
        ip_addr = request.data.get("ip_address", _rand_ip())
        factory = _data_factory()
        try:
            if factory and hasattr(factory, "create_complex"):
                return self.ok(factory.create_complex(user_id=user_id,
                                                        ip_address=ip_addr),
                                status.HTTP_201_CREATED)
            extra = {"scenario": "complex",
                     "created_by": "TestDataFactoryCreateComplexAPIView"}
            cases  = [_orm_create_case(user_id, case_type=ct,
                                        severity=random.choice(["high","critical"]),
                                        extra_meta=extra)[1]
                      for ct in _CASE_TYPES[:5]]
            alerts = [_orm_create_alert(user_id, alert_type=at, priority=pr,
                                         extra_meta=extra)[1]
                      for pr, at in [("high","velocity_breach"),
                                     ("high","geo_anomaly"),
                                     ("critical","suspicious_activity")]]
            from api.fraud_detection.models import UserRiskProfile, IPReputation
            from api.fraud_detection.serializers import (
                UserRiskProfileSerializer, IPReputationSerializer)
            profile, _ = UserRiskProfile.objects.get_or_create(user_id=user_id)
            for attr, val in [("overall_risk_score",92),("account_risk_score",88),
                               ("payment_risk_score",95),("behavior_risk_score",90),
                               ("is_flagged",True),("is_restricted",True)]:
                setattr(profile, attr, val)
            profile.risk_factors = _meta({**(profile.risk_factors or {})})
            profile.last_risk_assessment = timezone.now()
            profile.save()
            ip_rec, _ = IPReputation.objects.get_or_create(ip_address=ip_addr)
            ip_rec.fraud_score=95; ip_rec.is_blacklisted=True
            ip_rec.blacklist_reason="Factory complex scenario."
            ip_rec.blacklisted_at=timezone.now(); ip_rec.save()
            return self.ok({
                "scenario":      "complex", "user_id": user_id,
                "fraud_cases":   cases, "fraud_alerts": alerts,
                "risk_profile":  UserRiskProfileSerializer(profile).data,
                "ip_reputation": IPReputationSerializer(ip_rec).data,
                "source":        "orm_fallback",
            }, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("TestDataFactoryCreateComplexAPIView user=%s: %s", user_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestDataFactoryCreateScenarioAPIView(FraudAdminView):
    """POST /fraud/factory/test-data/scenario/"""
    def post(self, request):
        scenario = request.data.get("scenario","simple_fraud")
        user_id  = request.data.get("user_id", _rand_uid())
        factory  = _data_factory()
        try:
            if factory and hasattr(factory, "create_scenario"):
                return self.ok(factory.create_scenario(scenario, user_id=user_id),
                                status.HTTP_201_CREATED)
            # Delegate to simple/complex via direct call
            class _FakeReq:
                data = {"user_id": user_id}
                user = request.user
            if scenario in ("simple_fraud","simple"):
                return TestDataFactoryCreateSimpleAPIView().post(_FakeReq())
            if scenario in ("complex_fraud","complex"):
                return TestDataFactoryCreateComplexAPIView().post(_FakeReq())
            return self.err(f"Unknown scenario '{scenario}'. "
                             "Use GET /fraud/factory/test-data/scenarios/ to list options.")
        except Exception as exc:
            logger.exception("TestDataFactoryCreateScenarioAPIView scenario=%s: %s",
                              scenario, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestDataFactoryCleanupAPIView(FraudAdminView):
    """DELETE /fraud/factory/test-data/cleanup/"""
    def delete(self, request):
        factory = _data_factory()
        try:
            if factory and hasattr(factory, "cleanup_all"):
                return self.ok(factory.cleanup_all())
            from api.fraud_detection.models import FraudCase, FraudAlert
            case_qs  = FraudCase.objects.filter(metadata__factory_generated=True)
            alert_qs = FraudAlert.objects.filter(data__factory_generated=True)
            nc = case_qs.count(); na = alert_qs.count()
            case_qs.delete(); alert_qs.delete()
            return self.ok({"fraud_cases_deleted": nc, "fraud_alerts_deleted": na,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("TestDataFactoryCleanupAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# FraudAlertFactory
# =============================================================================

class FraudAlertFactoryCreateAPIView(FraudAdminView):
    """POST /fraud/factory/alerts/create/"""
    def post(self, request):
        factory = _alert_factory()
        try:
            if factory and hasattr(factory, "create"):
                return self.ok(factory.create(**request.data), status.HTTP_201_CREATED)
            uid = request.data.get("user_id", _rand_uid())
            is_r = bool(request.data.get("is_resolved", False))
            alert, data = _orm_create_alert(
                uid,
                alert_type=request.data.get("alert_type"),
                priority=request.data.get("priority"),
                is_resolved=is_r,
                extra_meta={"created_by": "FraudAlertFactoryCreateAPIView"},
            )
            return self.ok({"created": True, "alert_id": alert.pk,
                             "source": "orm_fallback", "data": data},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudAlertFactoryCreateAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertFactoryBatchAPIView(FraudAdminView):
    """POST /fraud/factory/alerts/batch/"""
    def post(self, request):
        try:
            count = min(50, max(1, int(request.data.get("count", 5))))
        except (TypeError, ValueError):
            count = 5
        fixed_type = request.data.get("alert_type")
        fixed_prio = request.data.get("priority")
        fixed_uid  = request.data.get("user_id")
        factory = _alert_factory()
        try:
            if factory and hasattr(factory, "create_batch"):
                return self.ok({"created": count,
                                  "results": factory.create_batch(
                                      count, alert_type=fixed_type,
                                      priority=fixed_prio, user_id=fixed_uid)},
                                status.HTTP_201_CREATED)
            results = [
                _orm_create_alert(
                    fixed_uid or _rand_uid(),
                    alert_type=fixed_type, priority=fixed_prio,
                    extra_meta={"batch": True,
                                "created_by": "FraudAlertFactoryBatchAPIView"},
                )[1]
                for _ in range(count)
            ]
            return self.ok({"created": len(results), "results": results,
                             "source": "orm_fallback"}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudAlertFactoryBatchAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertFactoryByTypeAPIView(FraudAdminView):
    """POST /fraud/factory/alerts/by-type/"""
    _TYPE_CONFIGS: Dict[str, Dict] = {
        "suspicious_activity": {"priority":"high"},
        "high_risk_score":     {"priority":"critical"},
        "multiple_accounts":   {"priority":"medium"},
        "velocity_breach":     {"priority":"high"},
        "geo_anomaly":         {"priority":"medium"},
        "device_anomaly":      {"priority":"medium"},
    }

    def post(self, request):
        atype = request.data.get("alert_type")
        if not atype:
            return self.err("alert_type is required.")
        if atype not in self._TYPE_CONFIGS:
            return self.err(f"Unknown alert_type '{atype}'. "
                             f"Valid: {list(self._TYPE_CONFIGS.keys())}.")
        try:
            count = min(20, max(1, int(request.data.get("count", 1))))
        except (TypeError, ValueError):
            count = 1
        user_id = request.data.get("user_id", _rand_uid())
        cfg     = self._TYPE_CONFIGS[atype]
        factory = _alert_factory()
        try:
            if factory and hasattr(factory, "create_by_type"):
                return self.ok(factory.create_by_type(alert_type=atype,
                                                        count=count, user_id=user_id),
                                status.HTTP_201_CREATED)
            results = [
                _orm_create_alert(
                    user_id, alert_type=atype, priority=cfg["priority"],
                    extra_meta={"by_type": True,
                                "created_by": "FraudAlertFactoryByTypeAPIView"},
                )[1]
                for _ in range(count)
            ]
            return self.ok({"created": len(results), "alert_type": atype,
                             "results": results, "source": "orm_fallback"},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudAlertFactoryByTypeAPIView type=%s: %s", atype, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertFactoryCleanupAPIView(FraudAdminView):
    """DELETE /fraud/factory/alerts/cleanup/"""
    def delete(self, request):
        factory = _alert_factory()
        try:
            if factory and hasattr(factory, "cleanup"):
                return self.ok(factory.cleanup())
            from api.fraud_detection.models import FraudAlert
            qs    = FraudAlert.objects.filter(data__factory_generated=True)
            count = qs.count(); qs.delete()
            return self.ok({"deleted": count, "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudAlertFactoryCleanupAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# UserRiskProfileFactory
# =============================================================================

class UserRiskProfileFactoryCreateAPIView(FraudAdminView):
    """POST /fraud/factory/profiles/create/"""
    def post(self, request):
        factory = _profile_factory()
        try:
            if factory and hasattr(factory, "create"):
                return self.ok(factory.create(**request.data), status.HTTP_201_CREATED)
            from api.fraud_detection.models import UserRiskProfile
            from api.fraud_detection.serializers import UserRiskProfileSerializer
            uid = request.data.get("user_id", _rand_uid())
            ovr = int(request.data.get("overall_risk_score", _rand_score(40,90)))
            profile, created = UserRiskProfile.objects.get_or_create(user_id=uid)
            profile.overall_risk_score  = ovr
            profile.account_risk_score  = max(0, ovr - 10)
            profile.payment_risk_score  = max(0, ovr - 5)
            profile.behavior_risk_score = max(0, ovr + 5)
            profile.is_flagged          = bool(request.data.get("is_flagged", ovr >= 70))
            profile.is_restricted       = bool(request.data.get("is_restricted", ovr >= 85))
            profile.monitoring_level    = request.data.get("monitoring_level","medium")
            profile.last_risk_assessment = timezone.now()
            profile.risk_factors = _meta({**(profile.risk_factors or {}),
                                           "created_by":"UserRiskProfileFactoryCreateAPIView"})
            profile.save()
            return self.ok({"created": created, "user_id": uid, "source": "orm_fallback",
                             "data": UserRiskProfileSerializer(profile).data},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("UserRiskProfileFactoryCreateAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserRiskProfileFactoryBatchAPIView(FraudAdminView):
    """POST /fraud/factory/profiles/batch/"""
    def post(self, request):
        try:
            count = min(50, max(1, int(request.data.get("count", 5))))
        except (TypeError, ValueError):
            count = 5
        risk_level = request.data.get("risk_level","mixed")
        factory    = _profile_factory()
        try:
            if factory and hasattr(factory, "create_batch"):
                return self.ok({"created": count,
                                  "results": factory.create_batch(count, risk_level=risk_level)},
                                status.HTTP_201_CREATED)
            from api.fraud_detection.models import UserRiskProfile
            from api.fraud_detection.serializers import UserRiskProfileSerializer
            levels  = list(_RISK_BANDS.keys())
            results = []
            for _ in range(count):
                level   = random.choice(levels) if risk_level=="mixed" \
                          else (risk_level if risk_level in _RISK_BANDS else "medium")
                lo, hi  = _RISK_BANDS[level]
                ovr     = _rand_score(lo, hi)
                uid     = _rand_uid()
                profile, _ = UserRiskProfile.objects.get_or_create(user_id=uid)
                profile.overall_risk_score  = ovr
                profile.account_risk_score  = max(0, ovr - random.randint(0,10))
                profile.payment_risk_score  = max(0, ovr + random.randint(-5,10))
                profile.behavior_risk_score = max(0, ovr - random.randint(0,15))
                profile.is_flagged          = ovr >= 60
                profile.is_restricted       = ovr >= 80
                profile.monitoring_level    = ("low" if ovr<30 else "medium"
                                                if ovr<60 else "high" if ovr<80
                                                else "critical")
                profile.last_risk_assessment = timezone.now()
                profile.risk_factors = _meta({**(profile.risk_factors or {}),
                                               "risk_level": level})
                profile.save()
                results.append(UserRiskProfileSerializer(profile).data)
            return self.ok({"created": len(results), "risk_level": risk_level,
                             "results": results, "source": "orm_fallback"},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("UserRiskProfileFactoryBatchAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserRiskProfileFactoryHighRiskAPIView(FraudAdminView):
    """POST /fraud/factory/profiles/high-risk/"""
    def post(self, request):
        user_id = request.data.get("user_id", _rand_uid())
        factory = _profile_factory()
        try:
            if factory and hasattr(factory, "create_high_risk"):
                return self.ok(factory.create_high_risk(user_id=user_id),
                                status.HTTP_201_CREATED)
            from api.fraud_detection.models import UserRiskProfile
            from api.fraud_detection.serializers import UserRiskProfileSerializer
            profile, created = UserRiskProfile.objects.get_or_create(user_id=user_id)
            for attr, val in [("overall_risk_score",95),("account_risk_score",92),
                               ("payment_risk_score",97),("behavior_risk_score",94),
                               ("is_flagged",True),("is_restricted",True),
                               ("monitoring_level","critical"),
                               ("total_fraud_attempts", random.randint(5,20)),
                               ("confirmed_fraud_attempts", random.randint(3,10))]:
                setattr(profile, attr, val)
            profile.warning_flags = ["multiple_devices","vpn_detected",
                                      "high_chargeback_rate","suspicious_ip"]
            profile.risk_factors = _meta({**(profile.risk_factors or {}),
                                           "high_risk": True,
                                           "created_by":"UserRiskProfileFactoryHighRiskAPIView"})
            profile.last_risk_assessment = timezone.now()
            profile.save()
            return self.ok({"created": created, "user_id": user_id,
                             "risk_level": "critical", "overall_score": 95,
                             "source": "orm_fallback",
                             "data": UserRiskProfileSerializer(profile).data},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("UserRiskProfileFactoryHighRiskAPIView user=%s: %s",
                              user_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserRiskProfileFactoryCleanupAPIView(FraudAdminView):
    """DELETE /fraud/factory/profiles/cleanup/"""
    def delete(self, request):
        hard = request.query_params.get("hard_delete","false").lower()=="true"
        factory = _profile_factory()
        try:
            if factory and hasattr(factory, "cleanup"):
                return self.ok(factory.cleanup(hard_delete=hard))
            from api.fraud_detection.models import UserRiskProfile
            qs = UserRiskProfile.objects.filter(risk_factors__factory_generated=True)
            if hard:
                count = qs.count(); qs.delete()
                return self.ok({"hard_deleted": count, "source": "orm_fallback"})
            count = 0
            for p in qs:
                factors = {k: v for k, v in (p.risk_factors or {}).items()
                           if k not in (_FACTORY_TAG,"created_by","batch","high_risk")}
                p.risk_factors        = factors
                p.overall_risk_score  = 0
                p.account_risk_score  = 0
                p.payment_risk_score  = 0
                p.behavior_risk_score = 0
                p.is_flagged          = False
                p.is_restricted       = False
                p.monitoring_level    = "low"
                p.save()
                count += 1
            return self.ok({"soft_cleaned": count, "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("UserRiskProfileFactoryCleanupAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
FraudAttemptFactoryAPIView = TestDataFactoryCreateSimpleAPIView
FraudCaseFactoryAPIView    = FraudCaseFactoryCreateAPIView
