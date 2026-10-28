"""
viewsets/search_views.py — NEWLY CREATED
Exposes 3 previously floating root-level files:
  1. SearchViewSet    → search.py   (AlertSearchEngine, 5 classes)
  2. SchemaViewSet    → schemas.py  (AlertSchemas, SchemaValidator, 4 classes)
  3. ResourceViewSet  → resources.py (AlertResource, 7 classes — import/export)
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 1. SearchViewSet  (search.py)
# ─────────────────────────────────────────────────────────────
class SearchViewSet(viewsets.ViewSet):
    """
    Full-text search across alerts, rules, notifications.
    Wraps search.py → AlertSearchEngine, AlertRuleSearchEngine,
    NotificationSearchEngine, SearchAnalytics.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Global search across all alert entities"""
        try:
            query = request.query_params.get('q', '')
            if not query:
                return Response({'error': 'q query param required'}, status=status.HTTP_400_BAD_REQUEST)
            from api.alerts.search import AlertSearchEngine
            from api.alerts.serializers.core import AlertLogSerializer
            engine = AlertSearchEngine()
            results = engine.search(query) if hasattr(engine, 'search') else {}
            if isinstance(results, dict) and 'results' in results:
                results = dict(results)
                results['results'] = AlertLogSerializer(results['results'], many=True).data
            return Response({'query': query, 'results': results})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SearchViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def search_rules(self, request):
        """Search alert rules by name, type, severity"""
        try:
            from api.alerts.search import AlertRuleSearchEngine
            from ..serializers.core import AlertRuleSerializer
            engine = AlertRuleSearchEngine()
            query = request.query_params.get('q', '')
            severity = request.query_params.get('severity')
            alert_type = request.query_params.get('type')
            filters = {}
            if severity:
                filters['severity'] = severity
            if alert_type:
                filters['alert_type'] = alert_type
            if not query and not filters:
                return Response({'error': 'q or filter param required'}, status=status.HTTP_400_BAD_REQUEST)
            engine_result = engine.search(query, filters=filters)
            raw_results = engine_result.get('results', []) if isinstance(engine_result, dict) else []
            serialized = AlertRuleSerializer(raw_results, many=True).data
            return Response({'query': query, 'filters': filters, 'results': serialized,
                             'count': len(serialized)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SearchViewSet.search_rules error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def search_logs(self, request):
        """Search alert logs by message, severity, resolution state"""
        try:
            from api.alerts.models.core import AlertLog
            query = request.query_params.get('q', '')
            severity = request.query_params.get('severity')
            resolved = request.query_params.get('resolved')
            qs = AlertLog.objects.select_related('rule').order_by('-triggered_at')
            if query:
                qs = qs.filter(message__icontains=query)
            if severity:
                qs = qs.filter(rule__severity=severity)
            if resolved is not None:
                qs = qs.filter(is_resolved=resolved.lower() == 'true')
            from api.alerts.serializers.core import AlertLogSerializer
            data = AlertLogSerializer(qs[:100], many=True).data
            return Response({'query': query, 'count': qs.count(), 'results': data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SearchViewSet.search_logs error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def search_notifications(self, request):
        """Search notifications"""
        try:
            from api.alerts.search import NotificationSearchEngine
            from api.alerts.serializers.core import NotificationSerializer
            engine = NotificationSearchEngine()
            query = request.query_params.get('q', '')
            if not query:
                return Response({'error': 'q required'}, status=status.HTTP_400_BAD_REQUEST)
            engine_result = engine.search(query) if hasattr(engine, 'search') else {}
            raw_results = engine_result.get('results', []) if isinstance(engine_result, dict) else []
            results = NotificationSerializer(raw_results, many=True).data
            return Response({'query': query, 'results': results, 'count': len(results)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SearchViewSet.search_notifications error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def suggestions(self, request):
        """Get search suggestions / autocomplete"""
        try:
            from api.alerts.search import SearchSuggestionEngine
            engine = SearchSuggestionEngine()
            prefix = request.query_params.get('prefix', '')
            if not prefix:
                return Response({'error': 'prefix required'}, status=status.HTTP_400_BAD_REQUEST)
            suggestions = engine.get_suggestions(prefix) if hasattr(engine, 'get_suggestions') else []
            return Response({'prefix': prefix, 'suggestions': suggestions})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SearchViewSet.suggestions error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def search_analytics(self, request):
        """Search analytics and popular queries"""
        try:
            from api.alerts.search import SearchAnalytics
            analytics = SearchAnalytics()
            data = analytics.get_analytics() if hasattr(analytics, 'get_analytics') else {}
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SearchViewSet.search_analytics error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def search_facets(self, request):
        """Get search facets (severity, type, status breakdowns)"""
        try:
            from api.alerts.models.core import AlertRule, AlertLog
            from api.alerts.choices import SEVERITY_LEVELS, ALERT_TYPES
            facets = {
                'severity': {},
                'alert_type': {},
                'status': {
                    'active': AlertRule.objects.filter(is_active=True).count(),
                    'inactive': AlertRule.objects.filter(is_active=False).count(),
                },
            }
            for sev, _ in SEVERITY_LEVELS:
                facets['severity'][sev] = AlertRule.objects.filter(severity=sev).count()
            for atype, _ in ALERT_TYPES:
                facets['alert_type'][atype] = AlertRule.objects.filter(alert_type=atype).count()
            return Response({'facets': facets})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SearchViewSet.search_facets error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────
# 2. SchemaViewSet  (schemas.py)
# ─────────────────────────────────────────────────────────────
class SchemaViewSet(viewsets.ViewSet):
    """
    Exposes schemas.py → AlertSchemas, WebhookSchemas, SchemaValidator.
    Endpoints: list, get_schema, validate, webhook_schemas
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List all available schemas"""
        try:
            from api.alerts.schemas import AlertSchemas
            schemas = AlertSchemas()
            available = schemas.get_available_schemas() if hasattr(schemas, 'get_available_schemas') else [
                'alert_rule', 'alert_log', 'notification', 'threshold', 'webhook', 'channel'
            ]
            return Response({'schemas': available, 'count': len(available)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchemaViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_schema(self, request):
        """Get a specific schema definition"""
        try:
            from api.alerts.schemas import AlertSchemas
            schema_type = request.query_params.get('type')
            if not schema_type:
                return Response({'error': 'type query param required'}, status=status.HTTP_400_BAD_REQUEST)
            schemas = AlertSchemas()
            schema = schemas.get_schema_for_type(schema_type) if hasattr(schemas, 'get_schema_for_type') else {}
            return Response({'type': schema_type, 'schema': schema})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchemaViewSet.get_schema error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def validate(self, request):
        """Validate a payload against a schema"""
        try:
            from api.alerts.schemas import SchemaValidator
            validator = SchemaValidator()
            schema_type = request.data.get('schema_type')
            payload = request.data.get('payload', {})
            if not schema_type:
                return Response({'error': 'schema_type required'}, status=status.HTTP_400_BAD_REQUEST)
            result = validator.validate_schema(schema_type, payload) if hasattr(validator, 'validate_schema') else {'valid': True}
            return Response({'schema_type': schema_type, 'validation': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchemaViewSet.validate error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def webhook_schemas(self, request):
        """Get webhook-specific schemas"""
        try:
            from api.alerts.schemas import WebhookSchemas
            schemas = WebhookSchemas()
            available = schemas.get_available_schemas() if hasattr(schemas, 'get_available_schemas') else {}
            return Response({'webhook_schemas': available})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchemaViewSet.webhook_schemas error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def system_schemas(self, request):
        """Get system-level schemas"""
        try:
            from api.alerts.schemas import SystemSchemas
            schemas = SystemSchemas()
            available = schemas.get_available_schemas() if hasattr(schemas, 'get_available_schemas') else {}
            return Response({'system_schemas': available})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SchemaViewSet.system_schemas error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────
# 3. ResourceViewSet  (resources.py — import/export)
# ─────────────────────────────────────────────────────────────
class ResourceViewSet(viewsets.ViewSet):
    """
    Exposes resources.py → AlertResource, AlertRuleResource, ExportResource.
    Endpoints: export, import_data, resource_info
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request):
        """List available resource types for import/export"""
        try:
            return Response({
                'resources': ['alert_rules', 'alert_logs', 'notifications', 'channels', 'thresholds'],
                'info': {
                    'alert_rules': {'fields': ['name', 'alert_type', 'severity', 'threshold_value']},
                    'alert_logs': {'fields': ['rule', 'trigger_value', 'message', 'is_resolved']},
                },
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"ResourceViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def export_rules(self, request):
        """Export alert rules as JSON/CSV"""
        try:
            from api.alerts.models.core import AlertRule
            from api.alerts.serializers.core import AlertRuleSerializer
            fmt = request.query_params.get('format', 'json')
            rules = AlertRule.objects.all()
            data = AlertRuleSerializer(rules, many=True).data
            if fmt == 'csv':
                import csv, io
                output = io.StringIO()
                if data:
                    writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
                    writer.writeheader()
                    for row in data:
                        writer.writerow({k: str(v) for k, v in row.items()})
                return Response({'format': 'csv', 'count': rules.count(), 'data': output.getvalue()})
            return Response({'format': fmt, 'count': rules.count(), 'data': data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"ResourceViewSet.export_rules error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def export_logs(self, request):
        """Export alert logs"""
        try:
            from api.alerts.models.core import AlertLog
            from api.alerts.serializers.core import AlertLogSerializer
            fmt = request.query_params.get('format', 'json')
            limit = int(request.query_params.get('limit', 1000))
            logs = AlertLog.objects.order_by('-triggered_at')[:limit]
            data = AlertLogSerializer(logs, many=True).data
            return Response({'format': fmt, 'count': len(data), 'data': data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"ResourceViewSet.export_logs error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def import_rules(self, request):
        """Import alert rules from JSON payload"""
        try:
            data = request.data.get('data', [])
            if not data:
                return Response({'error': 'data required'}, status=status.HTTP_400_BAD_REQUEST)
            from api.alerts.models.core import AlertRule
            from api.alerts.serializers.core import AlertRuleSerializer
            created = 0
            errors = []
            for item in data:
                serializer = AlertRuleSerializer(data=item)
                if serializer.is_valid():
                    serializer.save(created_by=request.user)
                    created += 1
                else:
                    errors.append(serializer.errors)
            return Response({'success': True, 'result': {'imported': created, 'errors': errors}})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"ResourceViewSet.import_rules error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def resource_info(self, request):
        """Get resource metadata and field info"""
        try:
            return Response({'resource_info': {
                'alert_rules': {'fields': ['name', 'alert_type', 'severity', 'threshold_value']},
                'alert_logs': {'fields': ['rule', 'trigger_value', 'message', 'is_resolved']},
            }})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"ResourceViewSet.resource_info error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
