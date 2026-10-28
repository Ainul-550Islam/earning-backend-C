from ..services.domain import (
    routing_template_service, tenant_service,
    security_event_service,
)

"""
Tenant Admin Viewsets for Offer Routing System

Single owner for all tenant-scoped admin operations:
  TenantSettingsViewSet  — tenant configuration
  TenantBillingViewSet   — billing records (read-only)
  TenantInvoiceViewSet   — invoices (read-only)
  RoutingConfigViewSet   — routing config CRUD (overrides config.py)
  RoutingTemplateViewSet — routing templates
  RouteActionViewSet     — route actions CRUD
  SecurityEventViewSet   — security event log (read-only)
"""

from ..throttling import BulkOperationThrottle, RoutingEngineThrottle, AnalyticsThrottle, BulkOperationThrottle, EvaluatorThrottle
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from ..permissions import IsAuthenticatedOrReadOnly, CanManageRoutes, CanViewAnalytics
from ..serializers import (
    TenantSettingsSerializer, TenantBillingSerializer,
    TenantInvoiceSerializer, RoutingConfigSerializer,
    RoutingTemplateSerializer, SecurityEventSerializer,
)


class TenantSettingsViewSet(viewsets.ModelViewSet):
    """CRUD for tenant-level routing settings."""
    serializer_class = TenantSettingsSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    throttle_classes = [BulkOperationThrottle]

    def get_queryset(self):
        from ..models import TenantSettings
        qs = TenantSettings.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get settings for the authenticated tenant."""
        try:
            from ..models import TenantSettings
            settings = TenantSettings.objects.filter(tenant=request.user).first()
            if settings:
                return Response(self.get_serializer(settings).data)
            return Response({'detail': 'No settings found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_limits(self, request):
        """Update tenant resource limits."""
        try:
            from ..models import TenantSettings
            settings, _ = TenantSettings.objects.get_or_create(tenant=request.user)
            allowed_fields = ['max_routes', 'max_ab_tests', 'max_daily_decisions',
                              'personalization_enabled', 'ab_testing_enabled', 'cache_enabled']
            for field in allowed_fields:
                if field in request.data:
                    setattr(settings, field, request.data[field])
            settings.save()
            return Response(self.get_serializer(settings).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantBillingViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to tenant billing records."""
    serializer_class = TenantBillingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [BulkOperationThrottle]

    def get_queryset(self):
        from ..models import TenantBilling
        qs = TenantBilling.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def current_period(self, request):
        """Get billing data for the current period."""
        try:
            from ..models import TenantBilling
            from django.utils import timezone
            current = TenantBilling.objects.filter(
                tenant=request.user,
                created_at__month=timezone.now().month
            ).first()
            if current:
                return Response(self.get_serializer(current).data)
            return Response({'total_decisions': 0, 'total_cost': '0.00'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def billing_summary(self, request):
        """Get aggregated billing summary."""
        try:
            from ..models import TenantBilling
            from django.db.models import Sum, Count
            summary = TenantBilling.objects.filter(
                tenant=request.user
            ).aggregate(
                total_decisions=Sum('total_decisions'),
                total_cost=Sum('total_cost'),
                billing_periods=Count('id')
            )
            return Response({'success': True, 'summary': summary})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TenantInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to tenant invoices."""
    serializer_class = TenantInvoiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [BulkOperationThrottle]

    def get_queryset(self):
        from ..models import TenantInvoice
        qs = TenantInvoice.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=request.user)
            except Exception:
                pass
        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def unpaid(self, request):
        """Get all unpaid invoices."""
        try:
            from ..models import TenantInvoice
            qs = TenantInvoice.objects.filter(tenant=request.user, status='unpaid')
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RoutingTemplateViewSet(viewsets.ModelViewSet):
    """CRUD for routing configuration templates."""
    serializer_class = RoutingTemplateSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    throttle_classes = [BulkOperationThrottle]

    def get_queryset(self):
        from ..models import RoutingTemplate
        qs = RoutingTemplate.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(tenant=self.request.user)
            except Exception:
                pass
        return qs

    @action(detail=True, methods=['post'])
    def apply_template(self, request, pk=None):
        """Apply this template to create a new OfferRoute."""
        try:
            template = self.get_object()
            from ..models import OfferRoute
            config = getattr(template, 'config', {}) or {}
            route = OfferRoute.objects.create(
                tenant=request.user,
                name=request.data.get('name', f'Route from {template.name}'),
                **{k: v for k, v in config.items() if k in [
                    'priority', 'max_offers', 'cache_enabled', 'cache_ttl_seconds',
                    'personalization_enabled', 'fallback_enabled', 'ab_testing_enabled'
                ]}
            )
            return Response({'success': True, 'route_id': route.id},
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def defaults(self, request):
        """Get all default templates."""
        try:
            from ..models import RoutingTemplate
            qs = RoutingTemplate.objects.filter(is_default=True)
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RouteActionViewSet(viewsets.ModelViewSet):
    """CRUD for route actions (what happens when a route matches)."""
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageRoutes]
    throttle_classes = [BulkOperationThrottle]

    def get_serializer_class(self):
        from ..serializers import OfferRouteSerializer
        return OfferRouteSerializer

    def get_queryset(self):
        from ..models import RouteAction
        qs = RouteAction.objects.all()
        if self.request.user.is_authenticated:
            try:
                qs = qs.filter(route__tenant=self.request.user)
            except Exception:
                pass
        return qs.order_by('route__priority', 'action_order')

    @action(detail=False, methods=['get'])
    def by_route(self, request):
        """Get all actions for a specific route."""
        route_id = request.query_params.get('route_id')
        if not route_id:
            return Response({'error': 'route_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from ..models import RouteAction
            qs = RouteAction.objects.filter(route_id=route_id)
            return Response({'actions': list(qs.values())})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SecurityEventViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to security events (audit log for routing system)."""
    serializer_class = SecurityEventSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    throttle_classes = [BulkOperationThrottle]

    def get_queryset(self):
        from ..models import SecurityEvent
        qs = SecurityEvent.objects.all()
        if not self.request.user.is_superuser:
            try:
                qs = qs.filter(user=self.request.user)
            except Exception:
                pass
        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent security events (last 100)."""
        try:
            from ..models import SecurityEvent
            qs = SecurityEvent.objects.all().order_by('-created_at')[:100]
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_severity(self, request):
        """Get events filtered by severity."""
        severity = request.query_params.get('severity', 'warning')
        try:
            from ..models import SecurityEvent
            qs = SecurityEvent.objects.filter(severity=severity).order_by('-created_at')[:50]
            return Response(self.get_serializer(qs, many=True).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
