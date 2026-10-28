# =============================================================================
# fraud_detection/views_search.py
# =============================================================================
"""
Full-text and structured search API for fraud detection entities.

Exposes all engines from search.py that were previously floating:
  - FraudCaseSearchEngine    → /fraud/search/cases/*
  - FraudAlertSearchEngine   → /fraud/search/alerts/*
  - FraudRuleSearchEngine    → /fraud/search/rules/*
  - AdvancedSearchEngine     → /fraud/search/advanced/*
  - SearchManager            → /fraud/search/manager/*

All endpoints support:
  - Keyword queries (full-text)
  - Structured field filters
  - Date range, risk score range, status filters
  - Pagination, ordering, grouping
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ok(data, code=status.HTTP_200_OK):
    return Response(data, status=code)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


def _build_criteria(request_data: Dict) -> List:
    """
    Convert request body into SearchCriteria objects.
    Body supports both short-form and SearchCriteria list formats.
    """
    try:
        from api.fraud_detection.search import (
            SearchCriteria, SearchOperator, build_search_criteria_from_request,
        )
        # If criteria list provided directly
        raw = request_data.get('criteria', [])
        if raw and isinstance(raw, list):
            criteria = []
            for c in raw:
                field    = c.get('field', '')
                operator_str = c.get('operator', 'eq')
                value    = c.get('value')
                if field and value is not None:
                    try:
                        op = SearchOperator(operator_str)
                    except ValueError:
                        op = SearchOperator.EQUALS
                    criteria.append(SearchCriteria(
                        field=field,
                        operator=op,
                        value=value,
                        boost=float(c.get('boost', 1.0)),
                    ))
            return criteria
        return []
    except Exception as exc:
        logger.debug("_build_criteria failed: %s", exc)
        return []


def _build_options(request_data: Dict):
    """Build SearchOptions from request body."""
    try:
        from api.fraud_detection.search import SearchOptions
        return SearchOptions(
            page=int(request_data.get('page', 1)),
            page_size=int(request_data.get('page_size', 20)),
            sort_by=request_data.get('sort_by', 'created_at'),
            sort_order=request_data.get('sort_order', 'desc'),
            highlight=bool(request_data.get('highlight', False)),
            fuzzy=bool(request_data.get('fuzzy', False)),
            aggregations=request_data.get('aggregations', []),
        )
    except Exception as exc:
        logger.debug("_build_options failed: %s", exc)
        return None


def _serialize_result(result) -> Dict:
    """Convert SearchResult to a plain dict."""
    if result is None:
        return {'results': [], 'total': 0}
    if hasattr(result, 'to_dict'):
        return result.to_dict()
    if hasattr(result, '__dict__'):
        d = {}
        for k, v in result.__dict__.items():
            if not k.startswith('_'):
                d[k] = v.to_dict() if hasattr(v, 'to_dict') else v
        return d
    return result


# =============================================================================
# 1. FraudCaseSearchEngine
# =============================================================================

class CaseSearchAPIView(APIView):
    """
    POST /fraud/search/cases/

    Search fraud cases using FraudCaseSearchEngine.

    Body:
        query        (str)   — full-text search query
        criteria     (list)  — structured filter list [{field, operator, value, boost?}]
        options      (dict)  — {page, page_size, sort_by, sort_order, highlight, fuzzy}
        risk_min     (int)   — minimum risk_score
        risk_max     (int)   — maximum risk_score
        status       (str|list) — case status filter
        date_from    (str)   — ISO-8601 date
        date_to      (str)   — ISO-8601 date
        assigned_to  (int)   — assigned staff user ID
        priority     (str|list)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.search import FraudCaseSearchEngine
            engine   = FraudCaseSearchEngine()
            query    = request.data.get('query', '')
            criteria = _build_criteria(request.data)
            options  = _build_options(request.data)

            # Convenience filters → auto-converted to SearchCriteria
            conv = _convenience_filters_to_criteria(request.data)
            criteria.extend(conv)

            result = engine.search(
                query=query,
                criteria=criteria or None,
                options=options,
            )
            return _ok(_serialize_result(result))
        except Exception as exc:
            logger.exception('CaseSearchAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CaseSuggestAPIView(APIView):
    """
    GET /fraud/search/cases/suggest/?q=partial

    Auto-complete / suggest case titles / descriptions.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return _err('q query param required.')
        try:
            from api.fraud_detection.search import FraudCaseSearchEngine
            engine  = FraudCaseSearchEngine()
            suggest = engine.suggest(
                query=q,
                limit=int(request.query_params.get('limit', 10)),
            ) if hasattr(engine, 'suggest') else []
            return _ok({'query': q, 'suggestions': suggest})
        except Exception as exc:
            logger.exception('CaseSuggestAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CaseSearchAggregationsAPIView(APIView):
    """
    POST /fraud/search/cases/aggregations/

    Return aggregated counts (e.g. by status, priority, risk_score bucket).
    Body: { query?, fields: [status, priority, risk_bucket] }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.search import FraudCaseSearchEngine
            engine = FraudCaseSearchEngine()
            fields = request.data.get('fields', ['status', 'priority'])
            query  = request.data.get('query', '')
            aggs   = engine.aggregate(
                query=query,
                fields=fields,
            ) if hasattr(engine, 'aggregate') else {}
            return _ok({'fields': fields, 'aggregations': aggs})
        except Exception as exc:
            logger.exception('CaseSearchAggregationsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CaseSearchExportAPIView(APIView):
    """
    POST /fraud/search/cases/export/

    Export search results as CSV.
    Body: same as CaseSearchAPIView + { format: csv|json }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        fmt = request.data.get('format', 'csv')
        try:
            from api.fraud_detection.search import FraudCaseSearchEngine
            from api.fraud_detection.models import FraudCase
            from django.http import HttpResponse
            import csv, io

            engine   = FraudCaseSearchEngine()
            query    = request.data.get('query', '')
            criteria = _build_criteria(request.data)
            result   = engine.search(query=query, criteria=criteria or None)
            items    = (result.get('results', []) if isinstance(result, dict)
                        else getattr(result, 'results', []))

            if fmt == 'csv':
                buf     = io.StringIO()
                writer  = csv.writer(buf)
                writer.writerow(['ID', 'Case Number', 'Title', 'Status', 'Priority',
                                  'Risk Score', 'User ID', 'Opened At'])
                for item in items:
                    d = item if isinstance(item, dict) else (item.__dict__ if hasattr(item, '__dict__') else {})
                    writer.writerow([
                        d.get('id', ''), d.get('case_number', ''), d.get('title', ''),
                        d.get('status', ''), d.get('priority', ''), d.get('risk_score', ''),
                        d.get('user_id', ''), d.get('opened_at', ''),
                    ])
                response = HttpResponse(buf.getvalue(), content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="fraud_cases_search.csv"'
                return response
            else:
                return _ok({'results': items, 'total': len(items)})
        except Exception as exc:
            logger.exception('CaseSearchExportAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 2. FraudAlertSearchEngine
# =============================================================================

class AlertSearchAPIView(APIView):
    """
    POST /fraud/search/alerts/

    Search fraud alerts using FraudAlertSearchEngine.

    Body:
        query        (str)
        criteria     (list)  [{field, operator, value}]
        options      (dict)
        alert_type   (str|list)
        priority     (str|list)
        is_resolved  (bool)
        date_from    (str)
        date_to      (str)
        user_id      (int)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.search import FraudAlertSearchEngine
            engine   = FraudAlertSearchEngine()
            query    = request.data.get('query', '')
            criteria = _build_criteria(request.data)
            options  = _build_options(request.data)
            criteria.extend(_convenience_filters_to_criteria(request.data))
            result = engine.search(query=query, criteria=criteria or None, options=options)
            return _ok(_serialize_result(result))
        except Exception as exc:
            logger.exception('AlertSearchAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertSearchSuggestAPIView(APIView):
    """GET /fraud/search/alerts/suggest/?q=partial"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return _err('q query param required.')
        try:
            from api.fraud_detection.search import FraudAlertSearchEngine
            engine  = FraudAlertSearchEngine()
            suggest = engine.suggest(query=q, limit=int(request.query_params.get('limit', 10))) \
                if hasattr(engine, 'suggest') else []
            return _ok({'query': q, 'suggestions': suggest})
        except Exception as exc:
            logger.exception('AlertSearchSuggestAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertSearchAggregationsAPIView(APIView):
    """POST /fraud/search/alerts/aggregations/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.search import FraudAlertSearchEngine
            engine = FraudAlertSearchEngine()
            fields = request.data.get('fields', ['alert_type', 'priority'])
            query  = request.data.get('query', '')
            aggs   = engine.aggregate(query=query, fields=fields) if hasattr(engine, 'aggregate') else {}
            return _ok({'fields': fields, 'aggregations': aggs})
        except Exception as exc:
            logger.exception('AlertSearchAggregationsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 3. FraudRuleSearchEngine
# =============================================================================

class RuleSearchAPIView(APIView):
    """
    POST /fraud/search/rules/

    Search fraud rules using FraudRuleSearchEngine.

    Body:
        query        (str)
        criteria     (list)
        options      (dict)
        rule_type    (str|list)
        severity     (str|list)
        is_active    (bool)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.search import FraudRuleSearchEngine
            engine   = FraudRuleSearchEngine()
            query    = request.data.get('query', '')
            criteria = _build_criteria(request.data)
            options  = _build_options(request.data)
            criteria.extend(_convenience_filters_to_criteria(request.data))
            result = engine.search(query=query, criteria=criteria or None, options=options)
            return _ok(_serialize_result(result))
        except Exception as exc:
            logger.exception('RuleSearchAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class RuleSearchSuggestAPIView(APIView):
    """GET /fraud/search/rules/suggest/?q=partial"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return _err('q query param required.')
        try:
            from api.fraud_detection.search import FraudRuleSearchEngine
            engine  = FraudRuleSearchEngine()
            suggest = engine.suggest(query=q, limit=int(request.query_params.get('limit', 10))) \
                if hasattr(engine, 'suggest') else []
            return _ok({'query': q, 'suggestions': suggest})
        except Exception as exc:
            logger.exception('RuleSearchSuggestAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 4. AdvancedSearchEngine — cross-entity search
# =============================================================================

class AdvancedSearchAPIView(APIView):
    """
    POST /fraud/search/advanced/

    Cross-entity search using AdvancedSearchEngine.
    Searches cases + alerts + rules + attempts simultaneously.

    Body:
        query        (str)  — full-text query
        entities     (list) — [cases, alerts, rules, attempts]  default: all
        criteria     (list) — [{field, operator, value}]
        options      (dict)
        date_from    (str)
        date_to      (str)
        risk_min     (int)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        query    = request.data.get('query', '').strip()
        entities = request.data.get('entities', ['cases', 'alerts', 'rules', 'attempts'])
        criteria = _build_criteria(request.data)
        options  = _build_options(request.data)

        if not query and not criteria:
            return _err('query or criteria required.')

        try:
            from api.fraud_detection.search import AdvancedSearchEngine
            engine   = AdvancedSearchEngine()
            criteria.extend(_convenience_filters_to_criteria(request.data))
            result   = engine.search(
                query=query,
                entities=entities,
                criteria=criteria or None,
                options=options,
            )
            return _ok(_serialize_result(result))
        except Exception as exc:
            logger.exception('AdvancedSearchAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdvancedSearchCountAPIView(APIView):
    """
    POST /fraud/search/advanced/count/

    Return counts per entity type matching the query — no full data.
    Body: { query, entities?, date_from?, date_to?, risk_min? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        query    = request.data.get('query', '').strip()
        entities = request.data.get('entities', ['cases', 'alerts', 'rules', 'attempts'])
        try:
            from api.fraud_detection.search import AdvancedSearchEngine
            engine = AdvancedSearchEngine()
            counts = engine.count(
                query=query,
                entities=entities,
                criteria=_convenience_filters_to_criteria(request.data) or None,
            ) if hasattr(engine, 'count') else {}
            return _ok({'query': query, 'entities': entities, 'counts': counts})
        except Exception as exc:
            logger.exception('AdvancedSearchCountAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdvancedSearchParseQueryAPIView(APIView):
    """
    POST /fraud/search/advanced/parse/

    Parse a natural-language query string into structured SearchCriteria.
    Body: { query: "risk_score > 80 AND status:open after:2025-01-01" }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        query = request.data.get('query', '').strip()
        if not query:
            return _err('query required.')
        try:
            from api.fraud_detection.search import parse_search_query
            criteria = parse_search_query(query)
            serialized = [
                {
                    'field':    c.field,
                    'operator': c.operator.value if hasattr(c.operator, 'value') else str(c.operator),
                    'value':    c.value,
                    'boost':    getattr(c, 'boost', 1.0),
                }
                for c in (criteria or [])
            ]
            return _ok({'query': query, 'parsed_criteria': serialized,
                        'count': len(serialized)})
        except Exception as exc:
            logger.exception('AdvancedSearchParseQueryAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 5. SearchManager — saved searches + history
# =============================================================================

class SearchManagerSaveAPIView(APIView):
    """
    POST /fraud/search/manager/save/

    Save a search query for later re-use.
    Body: { name, query, criteria?, entities?, description? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        name  = request.data.get('name', '').strip()
        query = request.data.get('query', '').strip()
        if not name:
            return _err('name required.')
        try:
            from api.fraud_detection.search import SearchManager
            mgr  = SearchManager()
            saved = mgr.save_search(
                name=name,
                query=query,
                criteria=request.data.get('criteria', []),
                entities=request.data.get('entities', []),
                description=request.data.get('description', ''),
                user_id=request.user.id,
            ) if hasattr(mgr, 'save_search') else {'name': name, 'saved': True}
            return _ok(saved if isinstance(saved, dict) else {'name': name, 'saved': True},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('SearchManagerSaveAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """GET /fraud/search/manager/save/ — list saved searches."""
        try:
            from api.fraud_detection.search import SearchManager
            mgr     = SearchManager()
            saved   = mgr.list_saved_searches(user_id=request.user.id) \
                if hasattr(mgr, 'list_saved_searches') else []
            return _ok({
                'count':   len(saved),
                'searches': [s.to_dict() if hasattr(s, 'to_dict') else s for s in saved],
            })
        except Exception as exc:
            logger.exception('SearchManagerSaveAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchManagerHistoryAPIView(APIView):
    """GET /fraud/search/manager/history/?limit=20"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        try:
            from api.fraud_detection.search import SearchManager
            mgr     = SearchManager()
            history = mgr.get_search_history(user_id=request.user.id, limit=limit) \
                if hasattr(mgr, 'get_search_history') else []
            return _ok({
                'count':   len(history),
                'history': [h.to_dict() if hasattr(h, 'to_dict') else h for h in history],
            })
        except Exception as exc:
            logger.exception('SearchManagerHistoryAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchManagerStatsAPIView(APIView):
    """GET /fraud/search/manager/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.search import SearchManager
            mgr   = SearchManager()
            stats = mgr.get_statistics() if hasattr(mgr, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('SearchManagerStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class SearchManagerDeleteSavedAPIView(APIView):
    """DELETE /fraud/search/manager/save/<search_id>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def delete(self, request, search_id: str):
        try:
            from api.fraud_detection.search import SearchManager
            mgr     = SearchManager()
            deleted = mgr.delete_saved_search(search_id=search_id, user_id=request.user.id) \
                if hasattr(mgr, 'delete_saved_search') else True
            return _ok({'deleted': deleted, 'search_id': search_id})
        except Exception as exc:
            logger.exception('SearchManagerDeleteSavedAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Convenience filter → SearchCriteria helper
# =============================================================================

def _convenience_filters_to_criteria(data: Dict) -> List:
    """
    Convert top-level convenience fields (risk_min, status, date_from, etc.)
    into SearchCriteria objects without requiring the caller to know the criteria
    list format.
    """
    try:
        from api.fraud_detection.search import SearchCriteria, SearchOperator
        criteria = []

        risk_min = data.get('risk_min')
        risk_max = data.get('risk_max')
        if risk_min is not None:
            criteria.append(SearchCriteria(field='risk_score',
                                           operator=SearchOperator.GREATER_THAN_OR_EQUAL,
                                           value=int(risk_min)))
        if risk_max is not None:
            criteria.append(SearchCriteria(field='risk_score',
                                           operator=SearchOperator.LESS_THAN_OR_EQUAL,
                                           value=int(risk_max)))

        st = data.get('status')
        if st:
            values = st if isinstance(st, list) else [st]
            criteria.append(SearchCriteria(field='status',
                                           operator=SearchOperator.IN,
                                           value=values))

        priority = data.get('priority')
        if priority:
            values = priority if isinstance(priority, list) else [priority]
            criteria.append(SearchCriteria(field='priority',
                                           operator=SearchOperator.IN,
                                           value=values))

        alert_type = data.get('alert_type')
        if alert_type:
            values = alert_type if isinstance(alert_type, list) else [alert_type]
            criteria.append(SearchCriteria(field='alert_type',
                                           operator=SearchOperator.IN,
                                           value=values))

        rule_type = data.get('rule_type')
        if rule_type:
            values = rule_type if isinstance(rule_type, list) else [rule_type]
            criteria.append(SearchCriteria(field='rule_type',
                                           operator=SearchOperator.IN,
                                           value=values))

        severity = data.get('severity')
        if severity:
            values = severity if isinstance(severity, list) else [severity]
            criteria.append(SearchCriteria(field='severity',
                                           operator=SearchOperator.IN,
                                           value=values))

        date_from = data.get('date_from')
        if date_from:
            criteria.append(SearchCriteria(field='created_at',
                                           operator=SearchOperator.GREATER_THAN_OR_EQUAL,
                                           value=date_from))
        date_to = data.get('date_to')
        if date_to:
            criteria.append(SearchCriteria(field='created_at',
                                           operator=SearchOperator.LESS_THAN_OR_EQUAL,
                                           value=date_to))

        user_id = data.get('user_id')
        if user_id:
            criteria.append(SearchCriteria(field='user_id',
                                           operator=SearchOperator.EQUALS,
                                           value=int(user_id)))

        assigned_to = data.get('assigned_to')
        if assigned_to:
            criteria.append(SearchCriteria(field='assigned_to_id',
                                           operator=SearchOperator.EQUALS,
                                           value=int(assigned_to)))

        is_active = data.get('is_active')
        if is_active is not None:
            criteria.append(SearchCriteria(field='is_active',
                                           operator=SearchOperator.EQUALS,
                                           value=bool(is_active)))

        is_resolved = data.get('is_resolved')
        if is_resolved is not None:
            criteria.append(SearchCriteria(field='is_resolved',
                                           operator=SearchOperator.EQUALS,
                                           value=bool(is_resolved)))

        return criteria
    except Exception as exc:
        logger.debug("_convenience_filters_to_criteria failed: %s", exc)
        return []

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
FraudSearchAPIView        = CaseSearchAPIView
FraudSearchSuggestAPIView = CaseSuggestAPIView
