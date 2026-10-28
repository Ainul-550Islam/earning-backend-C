# =============================================================================
# fraud_detection/views_repositories.py  (DRY-refactored)
# =============================================================================
"""
API endpoints for all 6 Repository classes.

DRY improvements
-----------------
• Extends FraudBaseView / FraudAdminView — removes 45 throttle_classes
  and 45 permission_classes lines.
• self.ok()/self.err()/self.paginate()/self.get_or_none()/self.require_admin()
  from base — removes 5 duplicate helper definitions.
• lazy_repo() from utils replaces 6 identical try/except ImportError blocks.
• _RepoDetailBase mixin carries GET/PUT/PATCH/DELETE for all detail views.
• _RepoListBase mixin carries GET list + paginate for all list views.
• All inline admin checks replaced by self.require_admin().
"""
from __future__ import annotations
import logging
from typing import Any, Dict
from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone
from rest_framework import status
from api.fraud_detection.utils import FraudBaseView, FraudAdminView, lazy_repo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Repo accessors — one line each (lazy_repo is defined once in utils)
# ---------------------------------------------------------------------------
def _rule_repo():       return lazy_repo("FraudRuleRepository")
def _case_repo():       return lazy_repo("FraudCaseRepository")
def _alert_repo():      return lazy_repo("FraudAlertRepository")
def _risk_repo():       return lazy_repo("FraudRiskProfileRepository")
def _ip_rep_repo():     return lazy_repo("IPReputationRepository")
def _sus_ip_repo():     return lazy_repo("FraudSuspiciousIPRepository")


# ---------------------------------------------------------------------------
# Shared repo mixins
# ---------------------------------------------------------------------------

class _RepoListBase(FraudBaseView):
    """List view mixin: GET paginated list with ORM fallback."""
    _repo_fn      = None   # callable → repo instance
    _model        = None   # Django model class
    _serializer   = None   # DRF serializer class
    _repo_method  = "get_all"
    _order_field  = "-created_at"

    def _build_qs(self, request, qs):
        """Override to apply request filters to queryset."""
        return qs

    def _build_repo_kwargs(self, request) -> Dict:
        """Override to pass filter kwargs to repo.get_all()."""
        return {}

    def get(self, request):
        repo = self._repo_fn() if self._repo_fn else None
        try:
            if repo and hasattr(repo, self._repo_method):
                kw = self._build_repo_kwargs(request)
                kw.update({
                    "page":      int(request.query_params.get("page", 1)),
                    "page_size": int(request.query_params.get("page_size", 20)),
                })
                return self.ok(getattr(repo, self._repo_method)(**kw))
            qs   = self._build_qs(request,
                                   self._model.objects.all().order_by(self._order_field))
            meta = self.paginate(qs)
            s, e = meta.pop("slice")
            return self.ok({**meta,
                             "results": self._serializer(qs[s:e], many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("%s.get: %s", self.__class__.__name__, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class _RepoDetailBase(FraudBaseView):
    """Detail view mixin: GET/PUT/PATCH/DELETE with ORM fallback."""
    _repo_fn    = None
    _model      = None
    _serializer = None

    def get(self, request, pk):
        repo = self._repo_fn() if self._repo_fn else None
        try:
            if repo and hasattr(repo, "get_by_id"):
                data = repo.get_by_id(pk)
                if data is None:
                    return self.err(f"{self._model.__name__} not found.",
                                     status.HTTP_404_NOT_FOUND)
                return self.ok(data)
            obj = self.get_or_none(self._model, pk=pk)
            if obj is None:
                return self.err(f"{self._model.__name__} not found.",
                                 status.HTTP_404_NOT_FOUND)
            return self.ok(self._serializer(obj).data)
        except Exception as exc:
            logger.exception("%s.get pk=%s: %s", self.__class__.__name__, pk, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _update(self, request, pk, partial):
        if e := self.require_admin(): return e
        repo = self._repo_fn() if self._repo_fn else None
        try:
            if repo and hasattr(repo, "update"):
                result = repo.update(pk, request.data, partial=partial)
                if result is None:
                    return self.err(f"{self._model.__name__} not found.",
                                     status.HTTP_404_NOT_FOUND)
                return self.ok(result)
            obj = self.get_or_none(self._model, pk=pk)
            if obj is None:
                return self.err(f"{self._model.__name__} not found.",
                                 status.HTTP_404_NOT_FOUND)
            ser = self._serializer(obj, data=request.data, partial=partial)
            if not ser.is_valid():
                return self.err(ser.errors)
            return self.ok(self._serializer(ser.save()).data)
        except Exception as exc:
            logger.exception("%s._update pk=%s: %s", self.__class__.__name__, pk, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, pk):   return self._update(request, pk, partial=False)
    def patch(self, request, pk): return self._update(request, pk, partial=True)

    def delete(self, request, pk):
        if e := self.require_admin(): return e
        repo = self._repo_fn() if self._repo_fn else None
        try:
            if repo and hasattr(repo, "delete"):
                if not repo.delete(pk):
                    return self.err(f"{self._model.__name__} not found.",
                                     status.HTTP_404_NOT_FOUND)
                return self.ok({"deleted": True, "id": pk})
            obj = self.get_or_none(self._model, pk=pk)
            if obj is None:
                return self.err(f"{self._model.__name__} not found.",
                                 status.HTTP_404_NOT_FOUND)
            obj.delete()
            return self.ok({"deleted": True, "id": pk})
        except Exception as exc:
            logger.exception("%s.delete pk=%s: %s", self.__class__.__name__, pk, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 1. FraudRuleRepository
# =============================================================================

class FraudRuleRepoListAPIView(_RepoListBase):
    """GET/POST /fraud/repository/rules/"""
    _repo_fn    = staticmethod(_rule_repo)

    @property
    def _model(self):
        from api.fraud_detection.models import FraudRule; return FraudRule

    @property
    def _serializer(self):
        from api.fraud_detection.serializers import FraudRuleSerializer
        return FraudRuleSerializer

    def _build_qs(self, request, qs):
        if request.query_params.get("is_active") is not None:
            qs = qs.filter(is_active=request.query_params["is_active"].lower()=="true")
        if request.query_params.get("rule_type"):
            qs = qs.filter(rule_type=request.query_params["rule_type"])
        if request.query_params.get("severity"):
            qs = qs.filter(severity=request.query_params["severity"])
        return qs

    def post(self, request):
        if e := self.require_admin(): return e
        repo = _rule_repo()
        try:
            if repo and hasattr(repo, "create"):
                return self.ok(repo.create(request.data), status.HTTP_201_CREATED)
            from api.fraud_detection.models import FraudRule
            from api.fraud_detection.serializers import FraudRuleSerializer
            ser = FraudRuleSerializer(data=request.data)
            if not ser.is_valid(): return self.err(ser.errors)
            return self.ok(FraudRuleSerializer(ser.save()).data, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudRuleRepoListAPIView.post: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRuleRepoDetailAPIView(_RepoDetailBase):
    """GET/PUT/PATCH/DELETE /fraud/repository/rules/<pk>/"""
    _repo_fn = staticmethod(_rule_repo)
    @property
    def _model(self):
        from api.fraud_detection.models import FraudRule; return FraudRule
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import FraudRuleSerializer
        return FraudRuleSerializer


class FraudRuleRepoActiveAPIView(FraudBaseView):
    """GET /fraud/repository/rules/active/"""
    def get(self, request):
        repo = _rule_repo()
        try:
            if repo and hasattr(repo, "get_active"):
                return self.ok(repo.get_active(
                    rule_type=request.query_params.get("rule_type"),
                    severity=request.query_params.get("severity")))
            from api.fraud_detection.models import FraudRule
            from api.fraud_detection.serializers import FraudRuleSerializer
            qs = FraudRule.objects.filter(is_active=True).order_by("-weight","-created_at")
            if request.query_params.get("rule_type"):
                qs = qs.filter(rule_type=request.query_params["rule_type"])
            if request.query_params.get("severity"):
                qs = qs.filter(severity=request.query_params["severity"])
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "results": FraudRuleSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudRuleRepoActiveAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRuleRepoByTypeAPIView(FraudBaseView):
    """GET /fraud/repository/rules/type/<rule_type>/"""
    def get(self, request, rule_type: str):
        repo = _rule_repo()
        try:
            if repo and hasattr(repo, "get_by_type"):
                return self.ok(repo.get_by_type(rule_type))
            from api.fraud_detection.models import FraudRule
            from api.fraud_detection.serializers import FraudRuleSerializer
            qs   = FraudRule.objects.filter(rule_type=rule_type).order_by("-weight")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "rule_type": rule_type,
                             "results": FraudRuleSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudRuleRepoByTypeAPIView type=%s: %s", rule_type, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRuleRepoStatsAPIView(FraudBaseView):
    """GET /fraud/repository/rules/stats/"""
    def get(self, request):
        repo = _rule_repo()
        try:
            if repo and hasattr(repo, "get_stats"):
                return self.ok(repo.get_stats())
            from api.fraud_detection.models import FraudRule
            qs = FraudRule.objects.all()
            return self.ok({
                "total":          qs.count(),
                "active":         qs.filter(is_active=True).count(),
                "inactive":       qs.filter(is_active=False).count(),
                "avg_weight":     round(qs.aggregate(a=Avg("weight"))["a"] or 0.0, 4),
                "by_type":        list(qs.values("rule_type").annotate(count=Count("id"))),
                "by_severity":    list(qs.values("severity").annotate(count=Count("id"))),
                "top_triggered":  list(qs.order_by("-trigger_count")
                                         .values("id","name","trigger_count")[:10]),
                "source": "orm_fallback",
            })
        except Exception as exc:
            logger.exception("FraudRuleRepoStatsAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRuleRepoBulkStatusAPIView(FraudAdminView):
    """PATCH /fraud/repository/rules/bulk-status/"""
    def patch(self, request):
        ids       = request.data.get("ids", [])
        is_active = request.data.get("is_active")
        if not ids:       return self.err("ids list is required.")
        if is_active is None: return self.err("is_active (true/false) is required.")
        repo = _rule_repo()
        try:
            if repo and hasattr(repo, "bulk_update_status"):
                return self.ok(repo.bulk_update_status(ids, bool(is_active)))
            from api.fraud_detection.models import FraudRule
            updated = FraudRule.objects.filter(pk__in=ids).update(is_active=bool(is_active))
            return self.ok({"updated": updated, "ids": ids,
                             "is_active": bool(is_active), "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudRuleRepoBulkStatusAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRuleRepoTopTriggeredAPIView(FraudBaseView):
    """GET /fraud/repository/rules/top-triggered/"""
    def get(self, request):
        try:
            limit = min(50, int(request.query_params.get("limit", 10)))
        except (TypeError, ValueError):
            limit = 10
        repo = _rule_repo()
        try:
            if repo and hasattr(repo, "get_top_triggered"):
                return self.ok(repo.get_top_triggered(limit=limit))
            from api.fraud_detection.models import FraudRule
            from api.fraud_detection.serializers import FraudRuleSerializer
            qs = FraudRule.objects.order_by("-trigger_count")[:limit]
            return self.ok({"limit": limit, "results": FraudRuleSerializer(qs,many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudRuleRepoTopTriggeredAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 2. FraudCaseRepository
# =============================================================================

class FraudCaseRepoListAPIView(_RepoListBase):
    """GET/POST /fraud/repository/cases/"""
    _repo_fn = staticmethod(_case_repo)
    @property
    def _model(self):
        from api.fraud_detection.models import FraudCase; return FraudCase
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import FraudCaseSerializer
        return FraudCaseSerializer

    def _build_qs(self, request, qs):
        for field in ("status","severity","case_type"):
            if request.query_params.get(field):
                qs = qs.filter(**{field: request.query_params[field]})
        if request.query_params.get("user_id"):
            qs = qs.filter(user_id=request.query_params["user_id"])
        return qs

    def post(self, request):
        if e := self.require_admin(): return e
        repo = _case_repo()
        try:
            if repo and hasattr(repo, "create"):
                return self.ok(repo.create(request.data), status.HTTP_201_CREATED)
            from api.fraud_detection.models import FraudCase
            from api.fraud_detection.serializers import FraudCaseSerializer
            ser = FraudCaseSerializer(data=request.data)
            if not ser.is_valid(): return self.err(ser.errors)
            return self.ok(FraudCaseSerializer(ser.save()).data, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudCaseRepoListAPIView.post: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseRepoDetailAPIView(_RepoDetailBase):
    """GET/PUT/PATCH/DELETE /fraud/repository/cases/<pk>/"""
    _repo_fn = staticmethod(_case_repo)
    @property
    def _model(self):
        from api.fraud_detection.models import FraudCase; return FraudCase
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import FraudCaseSerializer
        return FraudCaseSerializer


class FraudCaseRepoByUserAPIView(FraudBaseView):
    """GET /fraud/repository/cases/user/<user_id>/"""
    def get(self, request, user_id: int):
        repo = _case_repo()
        try:
            if repo and hasattr(repo, "get_by_user"):
                return self.ok(repo.get_by_user(user_id))
            from api.fraud_detection.models import FraudCase
            from api.fraud_detection.serializers import FraudCaseSerializer
            qs   = FraudCase.objects.filter(user_id=user_id).order_by("-created_at")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "user_id": user_id,
                             "results": FraudCaseSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudCaseRepoByUserAPIView user=%s: %s", user_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseRepoByStatusAPIView(FraudBaseView):
    """GET /fraud/repository/cases/status/<case_status>/"""
    def get(self, request, case_status: str):
        repo = _case_repo()
        try:
            if repo and hasattr(repo, "get_by_status"):
                return self.ok(repo.get_by_status(case_status))
            from api.fraud_detection.models import FraudCase
            from api.fraud_detection.serializers import FraudCaseSerializer
            qs   = FraudCase.objects.filter(status=case_status).order_by("-created_at")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "status": case_status,
                             "results": FraudCaseSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudCaseRepoByStatusAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseRepoOpenAPIView(FraudBaseView):
    """GET /fraud/repository/cases/open/"""
    def get(self, request):
        repo = _case_repo()
        try:
            if repo and hasattr(repo, "get_open"):
                return self.ok(repo.get_open())
            from api.fraud_detection.models import FraudCase
            from api.fraud_detection.serializers import FraudCaseSerializer
            qs   = FraudCase.objects.filter(
                status__in=["open","investigating"]).order_by("-risk_score","-created_at")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "results": FraudCaseSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudCaseRepoOpenAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseRepoBulkStatusAPIView(FraudAdminView):
    """PATCH /fraud/repository/cases/bulk-status/"""
    def patch(self, request):
        ids        = request.data.get("ids", [])
        new_status = request.data.get("status")
        if not ids:        return self.err("ids list is required.")
        if not new_status: return self.err("status is required.")
        repo = _case_repo()
        try:
            if repo and hasattr(repo, "bulk_update_status"):
                return self.ok(repo.bulk_update_status(ids, new_status))
            from api.fraud_detection.models import FraudCase
            updated = FraudCase.objects.filter(pk__in=ids).update(
                status=new_status, updated_at=timezone.now())
            return self.ok({"updated": updated, "ids": ids,
                             "new_status": new_status, "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudCaseRepoBulkStatusAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudCaseRepoStatsAPIView(FraudBaseView):
    """GET /fraud/repository/cases/stats/"""
    def get(self, request):
        repo = _case_repo()
        try:
            if repo and hasattr(repo, "get_stats"):
                return self.ok(repo.get_stats())
            from api.fraud_detection.models import FraudCase
            qs = FraudCase.objects.all()
            return self.ok({
                "total":          qs.count(),
                "open":           qs.filter(status__in=["open","investigating"]).count(),
                "resolved":       qs.filter(status="resolved").count(),
                "avg_risk_score": round(qs.aggregate(a=Avg("risk_score"))["a"] or 0.0, 2),
                "by_status":      list(qs.values("status").annotate(count=Count("id"))),
                "by_severity":    list(qs.values("severity").annotate(count=Count("id"))),
                "source": "orm_fallback",
            })
        except Exception as exc:
            logger.exception("FraudCaseRepoStatsAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 3. FraudAlertRepository
# =============================================================================

class FraudAlertRepoListAPIView(_RepoListBase):
    """GET/POST /fraud/repository/alerts/"""
    _repo_fn = staticmethod(_alert_repo)
    @property
    def _model(self):
        from api.fraud_detection.models import FraudAlert; return FraudAlert
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import FraudAlertSerializer
        return FraudAlertSerializer

    def _build_qs(self, request, qs):
        if request.query_params.get("is_resolved") is not None:
            qs = qs.filter(is_resolved=request.query_params["is_resolved"].lower()=="true")
        for field in ("priority","alert_type"):
            if request.query_params.get(field):
                qs = qs.filter(**{field: request.query_params[field]})
        if request.query_params.get("user_id"):
            qs = qs.filter(user_id=request.query_params["user_id"])
        return qs

    def post(self, request):
        if e := self.require_admin(): return e
        repo = _alert_repo()
        try:
            if repo and hasattr(repo, "create"):
                return self.ok(repo.create(request.data), status.HTTP_201_CREATED)
            from api.fraud_detection.models import FraudAlert
            from api.fraud_detection.serializers import FraudAlertSerializer
            ser = FraudAlertSerializer(data=request.data)
            if not ser.is_valid(): return self.err(ser.errors)
            return self.ok(FraudAlertSerializer(ser.save()).data, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("FraudAlertRepoListAPIView.post: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertRepoDetailAPIView(_RepoDetailBase):
    """GET/PATCH/DELETE /fraud/repository/alerts/<pk>/"""
    _repo_fn = staticmethod(_alert_repo)
    @property
    def _model(self):
        from api.fraud_detection.models import FraudAlert; return FraudAlert
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import FraudAlertSerializer
        return FraudAlertSerializer


class FraudAlertRepoResolveAPIView(FraudAdminView):
    """POST /fraud/repository/alerts/<pk>/resolve/"""
    def post(self, request, pk):
        repo = _alert_repo()
        try:
            if repo and hasattr(repo, "resolve"):
                result = repo.resolve(pk, request.user,
                                       request.data.get("resolution_notes",""))
                if result is None:
                    return self.err("FraudAlert not found.", status.HTTP_404_NOT_FOUND)
                return self.ok(result)
            from api.fraud_detection.models import FraudAlert
            from api.fraud_detection.serializers import FraudAlertSerializer
            alert = self.get_or_none(FraudAlert, pk=pk)
            if alert is None:
                return self.err("FraudAlert not found.", status.HTTP_404_NOT_FOUND)
            alert.is_resolved      = True
            alert.resolved_at      = timezone.now()
            alert.resolved_by      = request.user
            alert.resolution_notes = request.data.get("resolution_notes","")
            alert.save(update_fields=["is_resolved","resolved_at",
                                       "resolved_by","resolution_notes"])
            return self.ok(FraudAlertSerializer(alert).data)
        except Exception as exc:
            logger.exception("FraudAlertRepoResolveAPIView pk=%s: %s", pk, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertRepoUnresolvedAPIView(FraudBaseView):
    """GET /fraud/repository/alerts/unresolved/"""
    def get(self, request):
        repo = _alert_repo()
        try:
            if repo and hasattr(repo, "get_unresolved"):
                return self.ok(repo.get_unresolved(
                    priority=request.query_params.get("priority")))
            from api.fraud_detection.models import FraudAlert
            from api.fraud_detection.serializers import FraudAlertSerializer
            qs = FraudAlert.objects.filter(is_resolved=False).order_by("-priority","-created_at")
            if request.query_params.get("priority"):
                qs = qs.filter(priority=request.query_params["priority"])
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "results": FraudAlertSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudAlertRepoUnresolvedAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertRepoByPriorityAPIView(FraudBaseView):
    """GET /fraud/repository/alerts/priority/<priority>/"""
    def get(self, request, priority: str):
        repo = _alert_repo()
        try:
            if repo and hasattr(repo, "get_by_priority"):
                return self.ok(repo.get_by_priority(priority))
            from api.fraud_detection.models import FraudAlert
            from api.fraud_detection.serializers import FraudAlertSerializer
            qs   = FraudAlert.objects.filter(priority=priority).order_by("-created_at")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "priority": priority,
                             "results": FraudAlertSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudAlertRepoByPriorityAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertRepoCriticalAPIView(FraudBaseView):
    """GET /fraud/repository/alerts/critical/"""
    def get(self, request):
        repo = _alert_repo()
        try:
            if repo and hasattr(repo, "get_critical"):
                return self.ok(repo.get_critical())
            from api.fraud_detection.models import FraudAlert
            from api.fraud_detection.serializers import FraudAlertSerializer
            qs   = FraudAlert.objects.filter(priority="critical",is_resolved=False).order_by("-created_at")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "results": FraudAlertSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudAlertRepoCriticalAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertRepoBulkResolveAPIView(FraudAdminView):
    """POST /fraud/repository/alerts/bulk-resolve/"""
    def post(self, request):
        ids   = request.data.get("ids", [])
        notes = request.data.get("resolution_notes","Bulk resolve.")
        if not ids: return self.err("ids list is required.")
        repo = _alert_repo()
        try:
            if repo and hasattr(repo, "bulk_resolve"):
                return self.ok(repo.bulk_resolve(ids, request.user, notes))
            from api.fraud_detection.models import FraudAlert
            updated = FraudAlert.objects.filter(pk__in=ids,is_resolved=False).update(
                is_resolved=True, resolved_at=timezone.now(),
                resolved_by=request.user, resolution_notes=notes)
            return self.ok({"resolved": updated, "ids": ids, "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudAlertRepoBulkResolveAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudAlertRepoStatsAPIView(FraudBaseView):
    """GET /fraud/repository/alerts/stats/"""
    def get(self, request):
        repo = _alert_repo()
        try:
            if repo and hasattr(repo, "get_stats"):
                return self.ok(repo.get_stats())
            from api.fraud_detection.models import FraudAlert
            qs = FraudAlert.objects.all()
            return self.ok({
                "total":      qs.count(),
                "unresolved": qs.filter(is_resolved=False).count(),
                "resolved":   qs.filter(is_resolved=True).count(),
                "critical":   qs.filter(priority="critical",is_resolved=False).count(),
                "by_priority": list(qs.values("priority").annotate(count=Count("id"))),
                "by_type":     list(qs.values("alert_type").annotate(count=Count("id"))),
                "source": "orm_fallback",
            })
        except Exception as exc:
            logger.exception("FraudAlertRepoStatsAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 4. FraudRiskProfileRepository
# =============================================================================

class FraudRiskProfileRepoListAPIView(_RepoListBase):
    """GET /fraud/repository/risk-profiles/"""
    _repo_fn     = staticmethod(_risk_repo)
    _order_field = "-overall_risk_score"
    @property
    def _model(self):
        from api.fraud_detection.models import UserRiskProfile; return UserRiskProfile
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import UserRiskProfileSerializer
        return UserRiskProfileSerializer

    def _build_qs(self, request, qs):
        for bool_field in ("is_flagged","is_restricted"):
            if request.query_params.get(bool_field) is not None:
                qs = qs.filter(**{bool_field: request.query_params[bool_field].lower()=="true"})
        if request.query_params.get("monitoring_level"):
            qs = qs.filter(monitoring_level=request.query_params["monitoring_level"])
        if request.query_params.get("min_score"):
            qs = qs.filter(overall_risk_score__gte=int(request.query_params["min_score"]))
        if request.query_params.get("max_score"):
            qs = qs.filter(overall_risk_score__lte=int(request.query_params["max_score"]))
        return qs


class FraudRiskProfileRepoDetailAPIView(_RepoDetailBase):
    """GET/PATCH /fraud/repository/risk-profiles/<pk>/"""
    _repo_fn = staticmethod(_risk_repo)
    @property
    def _model(self):
        from api.fraud_detection.models import UserRiskProfile; return UserRiskProfile
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import UserRiskProfileSerializer
        return UserRiskProfileSerializer


class FraudRiskProfileRepoByUserAPIView(FraudBaseView):
    """GET /fraud/repository/risk-profiles/user/<user_id>/"""
    def get(self, request, user_id: int):
        repo = _risk_repo()
        try:
            if repo and hasattr(repo, "get_by_user"):
                data = repo.get_by_user(user_id)
                if data is None:
                    return self.err("UserRiskProfile not found.", status.HTTP_404_NOT_FOUND)
                return self.ok(data)
            from api.fraud_detection.models import UserRiskProfile
            from api.fraud_detection.serializers import UserRiskProfileSerializer
            profile = self.get_or_none(UserRiskProfile, user_id=user_id)
            if profile is None:
                return self.err("UserRiskProfile not found.", status.HTTP_404_NOT_FOUND)
            return self.ok(UserRiskProfileSerializer(profile).data)
        except Exception as exc:
            logger.exception("FraudRiskProfileRepoByUserAPIView user=%s: %s", user_id, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRiskProfileRepoHighRiskAPIView(FraudBaseView):
    """GET /fraud/repository/risk-profiles/high-risk/"""
    def get(self, request):
        try:
            threshold = int(request.query_params.get("threshold", 70))
        except (TypeError, ValueError):
            threshold = 70
        repo = _risk_repo()
        try:
            if repo and hasattr(repo, "get_high_risk"):
                return self.ok(repo.get_high_risk(threshold=threshold))
            from api.fraud_detection.models import UserRiskProfile
            from api.fraud_detection.serializers import UserRiskProfileSerializer
            qs   = UserRiskProfile.objects.filter(
                overall_risk_score__gte=threshold).order_by("-overall_risk_score")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "threshold": threshold,
                             "results": UserRiskProfileSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudRiskProfileRepoHighRiskAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRiskProfileRepoFlaggedAPIView(FraudBaseView):
    """GET /fraud/repository/risk-profiles/flagged/"""
    def get(self, request):
        repo = _risk_repo()
        try:
            if repo and hasattr(repo, "get_flagged"):
                return self.ok(repo.get_flagged())
            from api.fraud_detection.models import UserRiskProfile
            from api.fraud_detection.serializers import UserRiskProfileSerializer
            qs   = UserRiskProfile.objects.filter(
                Q(is_flagged=True)|Q(is_restricted=True)).order_by("-overall_risk_score")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "results": UserRiskProfileSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudRiskProfileRepoFlaggedAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRiskProfileRepoBulkRecalculateAPIView(FraudAdminView):
    """POST /fraud/repository/risk-profiles/bulk-recalculate/"""
    def post(self, request):
        user_ids = request.data.get("user_ids", [])
        if not user_ids: return self.err("user_ids list is required.")
        repo = _risk_repo()
        try:
            if repo and hasattr(repo, "bulk_recalculate"):
                return self.ok(repo.bulk_recalculate(user_ids))
            from api.fraud_detection.models import UserRiskProfile
            updated = UserRiskProfile.objects.filter(user_id__in=user_ids).update(
                next_assessment_due=timezone.now(), last_risk_assessment=timezone.now())
            return self.ok({"queued": updated, "user_ids": user_ids,
                             "message": "Profiles marked for recalculation.",
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("FraudRiskProfileRepoBulkRecalculateAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudRiskProfileRepoStatsAPIView(FraudBaseView):
    """GET /fraud/repository/risk-profiles/stats/"""
    def get(self, request):
        repo = _risk_repo()
        try:
            if repo and hasattr(repo, "get_stats"):
                return self.ok(repo.get_stats())
            from api.fraud_detection.models import UserRiskProfile
            qs  = UserRiskProfile.objects.all()
            agg = qs.aggregate(
                avg_overall=Avg("overall_risk_score"), avg_account=Avg("account_risk_score"),
                avg_payment=Avg("payment_risk_score"), avg_behavior=Avg("behavior_risk_score"),
                max_score=Max("overall_risk_score"),   min_score=Min("overall_risk_score"),
            )
            return self.ok({
                "total":        qs.count(),
                "flagged":      qs.filter(is_flagged=True).count(),
                "restricted":   qs.filter(is_restricted=True).count(),
                "distribution": {
                    "low (0-19)":     qs.filter(overall_risk_score__range=[0,19]).count(),
                    "medium (20-49)": qs.filter(overall_risk_score__range=[20,49]).count(),
                    "high (50-79)":   qs.filter(overall_risk_score__range=[50,79]).count(),
                    "critical (80+)": qs.filter(overall_risk_score__gte=80).count(),
                },
                "avg_scores": {k: round(v or 0.0, 2) for k, v in agg.items()},
                "source": "orm_fallback",
            })
        except Exception as exc:
            logger.exception("FraudRiskProfileRepoStatsAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 5. IPReputationRepository
# =============================================================================

class IPReputationRepoListAPIView(_RepoListBase):
    """GET /fraud/repository/ip-reputation/"""
    _repo_fn     = staticmethod(_ip_rep_repo)
    _order_field = "-fraud_score"
    @property
    def _model(self):
        from api.fraud_detection.models import IPReputation; return IPReputation
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import IPReputationSerializer
        return IPReputationSerializer

    def _build_qs(self, request, qs):
        if request.query_params.get("is_blacklisted") is not None:
            qs = qs.filter(is_blacklisted=request.query_params["is_blacklisted"].lower()=="true")
        if request.query_params.get("country"):
            qs = qs.filter(country__iexact=request.query_params["country"])
        if request.query_params.get("min_fraud_score"):
            qs = qs.filter(fraud_score__gte=int(request.query_params["min_fraud_score"]))
        return qs


class IPReputationRepoDetailAPIView(_RepoDetailBase):
    """GET/PATCH /fraud/repository/ip-reputation/<pk>/"""
    _repo_fn = staticmethod(_ip_rep_repo)
    @property
    def _model(self):
        from api.fraud_detection.models import IPReputation; return IPReputation
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import IPReputationSerializer
        return IPReputationSerializer


class IPReputationRepoLookupAPIView(FraudBaseView):
    """GET /fraud/repository/ip-reputation/lookup/<ip_address>/"""
    def get(self, request, ip_address: str):
        repo = _ip_rep_repo()
        try:
            if repo and hasattr(repo, "get_by_ip"):
                data = repo.get_by_ip(ip_address)
                if data is None:
                    return self.err("IPReputation not found.", status.HTTP_404_NOT_FOUND)
                return self.ok(data)
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            rec = IPReputation.objects.filter(ip_address=ip_address).first()
            if rec is None:
                return self.err("IPReputation not found.", status.HTTP_404_NOT_FOUND)
            return self.ok(IPReputationSerializer(rec).data)
        except Exception as exc:
            logger.exception("IPReputationRepoLookupAPIView ip=%s: %s", ip_address, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationRepoBlacklistedAPIView(FraudBaseView):
    """GET /fraud/repository/ip-reputation/blacklisted/"""
    def get(self, request):
        repo = _ip_rep_repo()
        try:
            if repo and hasattr(repo, "get_blacklisted"):
                return self.ok(repo.get_blacklisted())
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            qs   = IPReputation.objects.filter(is_blacklisted=True).order_by("-fraud_score")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "results": IPReputationSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("IPReputationRepoBlacklistedAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationRepoBlacklistAPIView(FraudAdminView):
    """POST /fraud/repository/ip-reputation/blacklist/"""
    def post(self, request):
        ip     = request.data.get("ip_address")
        reason = request.data.get("reason","Manually blacklisted.")
        if not ip: return self.err("ip_address is required.")
        repo = _ip_rep_repo()
        try:
            if repo and hasattr(repo, "blacklist"):
                return self.ok(repo.blacklist(ip, reason, request.user))
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            rec, created = IPReputation.objects.get_or_create(ip_address=ip)
            rec.is_blacklisted   = True
            rec.blacklist_reason = reason
            rec.blacklisted_at   = timezone.now()
            rec.save(update_fields=["is_blacklisted","blacklist_reason","blacklisted_at"])
            return self.ok({"blacklisted": True, "created": created,
                             "ip_address": ip,
                             "data": IPReputationSerializer(rec).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("IPReputationRepoBlacklistAPIView ip=%s: %s", ip, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationRepoUnblacklistAPIView(FraudAdminView):
    """POST /fraud/repository/ip-reputation/unblacklist/"""
    def post(self, request):
        ip = request.data.get("ip_address")
        if not ip: return self.err("ip_address is required.")
        repo = _ip_rep_repo()
        try:
            if repo and hasattr(repo, "unblacklist"):
                return self.ok(repo.unblacklist(ip))
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            rec = IPReputation.objects.filter(ip_address=ip).first()
            if rec is None:
                return self.err("IPReputation not found.", status.HTTP_404_NOT_FOUND)
            rec.is_blacklisted=False; rec.blacklist_reason=""; rec.blacklisted_at=None
            rec.save(update_fields=["is_blacklisted","blacklist_reason","blacklisted_at"])
            return self.ok({"unblacklisted": True, "ip_address": ip,
                             "data": IPReputationSerializer(rec).data,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("IPReputationRepoUnblacklistAPIView ip=%s: %s", ip, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationRepoBulkCheckAPIView(FraudBaseView):
    """POST /fraud/repository/ip-reputation/bulk-check/"""
    def post(self, request):
        ip_list = request.data.get("ip_addresses", [])[:50]
        if not ip_list: return self.err("ip_addresses list is required (max 50).")
        repo = _ip_rep_repo()
        try:
            if repo and hasattr(repo, "bulk_check"):
                return self.ok(repo.bulk_check(ip_list))
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            known = {r.ip_address: IPReputationSerializer(r).data
                     for r in IPReputation.objects.filter(ip_address__in=ip_list)}
            results = [{"ip_address": ip, "found": ip in known, **(known.get(ip) or {})}
                       for ip in ip_list]
            return self.ok({"checked": len(ip_list), "found": len(known),
                             "results": results, "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("IPReputationRepoBulkCheckAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IPReputationRepoStatsAPIView(FraudBaseView):
    """GET /fraud/repository/ip-reputation/stats/"""
    def get(self, request):
        repo = _ip_rep_repo()
        try:
            if repo and hasattr(repo, "get_stats"):
                return self.ok(repo.get_stats())
            from api.fraud_detection.models import IPReputation
            qs  = IPReputation.objects.all()
            agg = qs.aggregate(avg_fraud=Avg("fraud_score"),avg_spam=Avg("spam_score"),
                               avg_malware=Avg("malware_score"))
            return self.ok({
                "total":         qs.count(),
                "blacklisted":   qs.filter(is_blacklisted=True).count(),
                "high_risk":     qs.filter(fraud_score__gte=70).count(),
                "top_countries": list(qs.values("country").annotate(count=Count("id"))
                                       .order_by("-count")[:20]),
                "avg_scores":    {k: round(v or 0.0, 2) for k, v in agg.items()},
                "source": "orm_fallback",
            })
        except Exception as exc:
            logger.exception("IPReputationRepoStatsAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 6. FraudSuspiciousIPRepository
# =============================================================================

class SuspiciousIPRepoListAPIView(_RepoListBase):
    """GET/POST /fraud/repository/suspicious-ips/"""
    _repo_fn     = staticmethod(_sus_ip_repo)
    _order_field = "-fraud_score"
    @property
    def _model(self):
        from api.fraud_detection.models import IPReputation; return IPReputation
    @property
    def _serializer(self):
        from api.fraud_detection.serializers import IPReputationSerializer
        return IPReputationSerializer

    def _build_qs(self, request, qs):
        return qs.filter(Q(is_blacklisted=True)|Q(fraud_score__gte=60))

    def post(self, request):
        if e := self.require_admin(): return e
        repo = _sus_ip_repo()
        try:
            if repo and hasattr(repo, "create"):
                return self.ok(repo.create(request.data), status.HTTP_201_CREATED)
            ip = request.data.get("ip_address")
            if not ip: return self.err("ip_address is required.")
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            rec, created = IPReputation.objects.get_or_create(ip_address=ip)
            rec.fraud_score      = max(rec.fraud_score, 80)
            rec.is_blacklisted   = True
            rec.blacklist_reason = request.data.get("reason","Marked suspicious.")
            rec.blacklisted_at   = timezone.now()
            if request.data.get("country"):   rec.country = request.data["country"]
            rec.save()
            return self.ok({"created": created, "ip_address": ip,
                             "data": IPReputationSerializer(rec).data,
                             "source": "orm_fallback_via_ip_reputation"},
                            status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception("SuspiciousIPRepoListAPIView.post: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SuspiciousIPRepoDetailAPIView(FraudBaseView):
    """GET/DELETE /fraud/repository/suspicious-ips/<pk>/"""
    def get(self, request, pk):
        repo = _sus_ip_repo()
        try:
            if repo and hasattr(repo, "get_by_id"):
                data = repo.get_by_id(pk)
                if data is None:
                    return self.err("Record not found.", status.HTTP_404_NOT_FOUND)
                return self.ok(data)
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            rec = self.get_or_none(IPReputation, pk=pk)
            if rec is None:
                return self.err("Record not found.", status.HTTP_404_NOT_FOUND)
            return self.ok(IPReputationSerializer(rec).data)
        except Exception as exc:
            logger.exception("SuspiciousIPRepoDetailAPIView.get pk=%s: %s", pk, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        if e := self.require_admin(): return e
        repo = _sus_ip_repo()
        try:
            if repo and hasattr(repo, "delete"):
                if not repo.delete(pk):
                    return self.err("Record not found.", status.HTTP_404_NOT_FOUND)
                return self.ok({"deleted": True, "id": pk})
            from api.fraud_detection.models import IPReputation
            rec = self.get_or_none(IPReputation, pk=pk)
            if rec is None:
                return self.err("Record not found.", status.HTTP_404_NOT_FOUND)
            rec.is_blacklisted=False; rec.blacklist_reason=""
            rec.blacklisted_at=None
            rec.fraud_score = max(0, rec.fraud_score - 40)
            rec.save()
            return self.ok({"removed_from_suspicious": True, "id": pk,
                             "source": "orm_fallback"})
        except Exception as exc:
            logger.exception("SuspiciousIPRepoDetailAPIView.delete pk=%s: %s", pk, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SuspiciousIPRepoByCountryAPIView(FraudBaseView):
    """GET /fraud/repository/suspicious-ips/country/<country>/"""
    def get(self, request, country: str):
        repo = _sus_ip_repo()
        try:
            if repo and hasattr(repo, "get_by_country"):
                return self.ok(repo.get_by_country(country))
            from api.fraud_detection.models import IPReputation
            from api.fraud_detection.serializers import IPReputationSerializer
            qs   = IPReputation.objects.filter(
                country__iexact=country, is_blacklisted=True).order_by("-fraud_score")
            meta = self.paginate(qs); s, e = meta.pop("slice")
            return self.ok({**meta, "country": country,
                             "results": IPReputationSerializer(qs[s:e],many=True).data,
                             "source": "orm_fallback_via_ip_reputation"})
        except Exception as exc:
            logger.exception("SuspiciousIPRepoByCountryAPIView country=%s: %s", country, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SuspiciousIPRepoBulkAddAPIView(FraudAdminView):
    """POST /fraud/repository/suspicious-ips/bulk-add/"""
    def post(self, request):
        ip_list = request.data.get("ip_addresses", [])[:200]
        reason  = request.data.get("reason","Bulk import.")
        if not ip_list: return self.err("ip_addresses list is required (max 200).")
        repo = _sus_ip_repo()
        try:
            if repo and hasattr(repo, "bulk_add"):
                return self.ok(repo.bulk_add(ip_list, reason))
            from api.fraud_detection.models import IPReputation
            now = timezone.now(); created=0; updated=0
            for ip in ip_list:
                rec, is_new = IPReputation.objects.get_or_create(ip_address=ip)
                rec.is_blacklisted=True; rec.blacklist_reason=reason
                rec.blacklisted_at=now; rec.fraud_score=max(rec.fraud_score,80)
                rec.save(update_fields=["is_blacklisted","blacklist_reason",
                                         "blacklisted_at","fraud_score"])
                if is_new: created += 1
                else:       updated += 1
            return self.ok({"processed": len(ip_list), "created": created,
                             "updated": updated, "reason": reason,
                             "source": "orm_fallback_via_ip_reputation"})
        except Exception as exc:
            logger.exception("SuspiciousIPRepoBulkAddAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SuspiciousIPRepoBulkRemoveAPIView(FraudAdminView):
    """DELETE /fraud/repository/suspicious-ips/bulk-remove/"""
    def delete(self, request):
        ip_list = request.data.get("ip_addresses", [])[:200]
        if not ip_list: return self.err("ip_addresses list is required.")
        repo = _sus_ip_repo()
        try:
            if repo and hasattr(repo, "bulk_remove"):
                return self.ok(repo.bulk_remove(ip_list))
            from api.fraud_detection.models import IPReputation
            removed = IPReputation.objects.filter(ip_address__in=ip_list).update(
                is_blacklisted=False, blacklist_reason="", blacklisted_at=None)
            return self.ok({"removed": removed, "ips": ip_list,
                             "source": "orm_fallback_via_ip_reputation"})
        except Exception as exc:
            logger.exception("SuspiciousIPRepoBulkRemoveAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SuspiciousIPRepoCheckAPIView(FraudBaseView):
    """GET /fraud/repository/suspicious-ips/check/<ip_address>/"""
    def get(self, request, ip_address: str):
        repo = _sus_ip_repo()
        try:
            if repo and hasattr(repo, "is_suspicious"):
                return self.ok(repo.is_suspicious(ip_address))
            from api.fraud_detection.models import IPReputation
            rec = IPReputation.objects.filter(ip_address=ip_address).first()
            if rec is None:
                return self.ok({"ip_address": ip_address, "is_suspicious": False,
                                  "is_blacklisted": False, "fraud_score": 0,
                                  "source": "orm_fallback"})
            return self.ok({
                "ip_address":     ip_address,
                "is_suspicious":  rec.is_blacklisted or rec.fraud_score >= 60,
                "is_blacklisted": rec.is_blacklisted,
                "fraud_score":    rec.fraud_score,
                "reason":         rec.blacklist_reason,
                "country":        rec.country,
                "source":         "orm_fallback_via_ip_reputation",
            })
        except Exception as exc:
            logger.exception("SuspiciousIPRepoCheckAPIView ip=%s: %s", ip_address, exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SuspiciousIPRepoStatsAPIView(FraudBaseView):
    """GET /fraud/repository/suspicious-ips/stats/"""
    def get(self, request):
        repo = _sus_ip_repo()
        try:
            if repo and hasattr(repo, "get_stats"):
                return self.ok(repo.get_stats())
            from api.fraud_detection.models import IPReputation
            qs = IPReputation.objects.filter(is_blacklisted=True)
            return self.ok({
                "total_suspicious":   qs.count(),
                "high_fraud_score":   qs.filter(fraud_score__gte=80).count(),
                "medium_fraud_score": qs.filter(fraud_score__range=[60,79]).count(),
                "by_country":         list(qs.values("country")
                                             .annotate(count=Count("id"))
                                             .order_by("-count")[:20]),
                "source": "orm_fallback_via_ip_reputation",
            })
        except Exception as exc:
            logger.exception("SuspiciousIPRepoStatsAPIView: %s", exc)
            return self.err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
RepositoryStatsAPIView = FraudRuleRepoStatsAPIView
RepositoryQueryAPIView = FraudRuleRepoListAPIView
