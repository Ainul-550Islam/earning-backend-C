# api/support/mixins.py
"""
DRF Mixins for support views.
Full reusable mixin classes — no summarizing, full code.
"""
import logging
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class TenantFilterMixin:
    """
    Automatically filter querysets by the authenticated user tenant.
    Add to any ViewSet or APIView that needs tenant isolation.
    """
    def get_tenant_queryset(self, queryset):
        user   = getattr(self, 'request', None) and self.request.user
        if not user or user.is_superuser:
            return queryset
        tenant = getattr(user, 'tenant', None)
        if tenant and hasattr(queryset.model, 'tenant'):
            return queryset.filter(tenant=tenant)
        return queryset


class PaginationMixin:
    """
    Standard pagination for support list endpoints.
    Supports ?page=1&per_page=20 query params.
    Max 100 per page.
    """
    default_page_size = 20
    max_page_size     = 100

    def paginate_queryset_custom(self, queryset, request):
        try:
            page     = max(1, int(request.query_params.get('page', 1)))
            per_page = min(int(request.query_params.get('per_page', self.default_page_size)), self.max_page_size)
        except (TypeError, ValueError):
            page, per_page = 1, self.default_page_size

        total = queryset.count()
        start = (page - 1) * per_page
        items = queryset[start:start + per_page]

        return {
            'items':    items,
            'count':    total,
            'page':     page,
            'per_page': per_page,
            'has_next': start + per_page < total,
            'has_prev': page > 1,
            'pages':    (total + per_page - 1) // per_page,
        }

    def paginated_response(self, data, pagination_info):
        return Response({
            'results':  data,
            'count':    pagination_info['count'],
            'page':     pagination_info['page'],
            'per_page': pagination_info['per_page'],
            'has_next': pagination_info['has_next'],
            'has_prev': pagination_info['has_prev'],
            'pages':    pagination_info['pages'],
        })


class OwnershipMixin:
    """
    Mixin that restricts object access to the owner or staff.
    Uses has_object_permission pattern.
    """
    owner_field = 'user'  # The field on the model that holds the owner

    def check_object_ownership(self, obj, request):
        if request.user.is_staff or request.user.is_superuser:
            return True
        owner = getattr(obj, self.owner_field, None)
        if owner is None:
            return False
        if hasattr(owner, 'id'):
            return owner.id == request.user.id
        return owner == request.user.id

    def get_owned_queryset(self, queryset, request):
        if request.user.is_staff or request.user.is_superuser:
            return queryset
        return queryset.filter(**{self.owner_field: request.user})


class AuditMixin:
    """
    Mixin that logs all CUD operations to the audit log.
    Add to ViewSets that handle sensitive operations (disputes, wallet credits).
    """
    audit_action_prefix = 'support'

    def audit_log(self, action: str, obj=None, request=None, extra: dict = None):
        try:
            from api.support.integrations.project_specific.audit_log_bridge import audit_bridge
            agent = getattr(request, 'user', None) if request else None
            ticket = getattr(obj, 'ticket', None) if obj else None
            audit_bridge.log_agent_action(
                ticket  = ticket,
                agent   = agent,
                action  = f'{self.audit_action_prefix}.{action}',
                details = extra or {},
            )
        except Exception as e:
            logger.debug(f'AuditMixin.audit_log: {e}')


class CacheInvalidateMixin:
    """
    Mixin that invalidates relevant caches after mutations.
    Used in ViewSets that modify support settings, FAQ, KB articles.
    """
    cache_keys_to_invalidate = []  # Override in subclass

    def invalidate_caches(self):
        try:
            from django.core.cache import cache
            for key in self.cache_keys_to_invalidate:
                cache.delete(key)
            # Always clear support settings cache
            cache.delete('support:settings:singleton')
        except Exception as e:
            logger.debug(f'CacheInvalidateMixin: {e}')

    def perform_create(self, serializer):
        result = super().perform_create(serializer)
        self.invalidate_caches()
        return result

    def perform_update(self, serializer):
        result = super().perform_update(serializer)
        self.invalidate_caches()
        return result

    def perform_destroy(self, instance):
        result = super().perform_destroy(instance)
        self.invalidate_caches()
        return result


class SLAMixin:
    """
    Mixin for ticket operations that need to respect SLA.
    Provides helper methods for SLA-aware ticket handling.
    """
    def setup_sla_for_ticket(self, ticket):
        """Setup SLA deadlines — also adjusts for subscription tier."""
        try:
            from api.support.services import sla_service
            sla_service._setup_sla(ticket)
            # Adjust for subscription tier
            try:
                from api.support.integrations.project_specific.subscription_sla import subscription_sla
                subscription_sla.adjust_sla_for_subscription(ticket)
            except Exception:
                pass
        except Exception as e:
            logger.debug(f'SLAMixin.setup_sla: {e}')

    def get_sla_status(self, ticket) -> dict:
        """Get current SLA status for a ticket."""
        try:
            sla = ticket.sla
            from django.utils import timezone
            now = timezone.now()
            fr_overdue  = 0.0
            res_overdue = 0.0
            if sla.first_response_due and not sla.first_response_at:
                diff = (now - sla.first_response_due).total_seconds()
                fr_overdue = max(0.0, round(diff / 3600, 1))
            if sla.resolution_due and not sla.resolution_at:
                diff = (now - sla.resolution_due).total_seconds()
                res_overdue = max(0.0, round(diff / 3600, 1))
            return {
                'breached':         sla.is_breached,
                'fr_due':           sla.first_response_due,
                'res_due':          sla.resolution_due,
                'fr_overdue_hours': fr_overdue,
                'res_overdue_hours':res_overdue,
            }
        except Exception:
            return {}


class NotificationMixin:
    """
    Mixin that fires notifications on ticket state changes.
    Add to views that change ticket status.
    """
    def notify_status_change(self, ticket, new_status: str, request=None):
        try:
            from api.support.services import notification_service
            if new_status == 'resolved':
                notification_service.notify_ticket_resolved(ticket)
            elif new_status in ('in_progress', 'waiting_user') and ticket.admin_response:
                user = getattr(request, 'user', None) if request else None
                notification_service.notify_new_reply(ticket, user, is_agent=True)
        except Exception as e:
            logger.debug(f'NotificationMixin.notify_status_change: {e}')