"""
Django mixins for alerts app
"""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class AlertPermissionMixin:
    """Mixin for alert-specific permissions"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not self.has_alert_permission(request):
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def has_alert_permission(self, request):
        """Check if user has alert permissions"""
        return (
            request.user.is_staff or
            request.user.has_perm('alerts.view_alerts') or
            request.user.has_perm('alerts.manage_alerts')
        )


class AlertRulePermissionMixin:
    """Mixin for alert rule permissions"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not self.has_rule_permission(request):
            messages.error(request, 'You do not have permission to manage alert rules.')
            return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def has_rule_permission(self, request):
        """Check if user has rule permissions"""
        return (
            request.user.is_staff or
            request.user.has_perm('alerts.manage_alert_rules')
        )


class NotificationPermissionMixin:
    """Mixin for notification permissions"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not self.has_notification_permission(request):
            messages.error(request, 'You do not have permission to manage notifications.')
            return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def has_notification_permission(self, request):
        """Check if user has notification permissions"""
        return (
            request.user.is_staff or
            request.user.has_perm('alerts.manage_notifications')
        )


class CacheMixin:
    """Mixin for caching view data"""
    
    cache_timeout = 300  # 5 minutes
    cache_key_prefix = 'alerts'
    
    def get_cache_key(self, request, *args, **kwargs):
        """Generate cache key"""
        key_parts = [
            self.cache_key_prefix,
            self.__class__.__name__,
            str(request.user.id) if request.user.is_authenticated else 'anonymous',
            request.GET.urlencode()
        ]
        return ':'.join(key_parts)
    
    def get_cached_data(self, request, *args, **kwargs):
        """Get data from cache"""
        cache_key = self.get_cache_key(request, *args, **kwargs)
        return cache.get(cache_key)
    
    def set_cached_data(self, request, data, *args, **kwargs):
        """Set data in cache"""
        cache_key = self.get_cache_key(request, *args, **kwargs)
        cache.set(cache_key, data, self.cache_timeout)
    
    def clear_cache(self, request, *args, **kwargs):
        """Clear cache for this view"""
        cache_key = self.get_cache_key(request, *args, **kwargs)
        cache.delete(cache_key)


class AuditLogMixin:
    """Mixin for audit logging"""
    
    def form_valid(self, form):
        """Log form submission"""
        response = super().form_valid(form)
        
        # Log the action
        self.log_action(
            user=self.request.user,
            action=self.get_action_name(),
            object_type=self.get_object_type(),
            object_id=self.get_object_id(),
            changes=form.cleaned_data
        )
        
        return response
    
    def get_action_name(self):
        """Get action name for logging"""
        if hasattr(self, 'action_name'):
            return self.action_name
        return self.__class__.__name__.replace('View', '').lower()
    
    def get_object_type(self):
        """Get object type for logging"""
        if hasattr(self, 'model'):
            return self.model.__name__.lower()
        return 'unknown'
    
    def get_object_id(self):
        """Get object ID for logging"""
        if hasattr(self, 'object') and self.object:
            return self.object.id
        return None
    
    def log_action(self, user, action, object_type, object_id, changes):
        """Log the action"""
        from .models import AuditLog
        
        AuditLog.objects.create(
            user=user,
            action=action,
            object_type=object_type,
            object_id=object_id,
            changes=changes,
            timestamp=timezone.now(),
            ip_address=self.get_client_ip()
        )
    
    def get_client_ip(self):
        """Get client IP address"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class AjaxFormMixin:
    """Mixin for AJAX form handling"""
    
    def form_invalid(self, form):
        """Handle invalid form for AJAX"""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors,
                'message': 'Please correct the errors below.'
            }, status=400)
        return super().form_invalid(form)
    
    def form_valid(self, form):
        """Handle valid form for AJAX"""
        response = super().form_valid(form)
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': self.get_success_message(),
                'redirect_url': self.get_success_url()
            })
        
        return response
    
    def get_success_message(self):
        """Get success message"""
        if hasattr(self, 'success_message'):
            return self.success_message
        return 'Operation completed successfully.'


class BulkActionMixin:
    """Mixin for bulk actions"""
    
    def post(self, request, *args, **kwargs):
        """Handle bulk action POST"""
        action = request.POST.get('bulk_action')
        selected_ids = request.POST.getlist('selected_ids')
        
        if not action:
            messages.error(request, 'No action selected.')
            return redirect(self.get_success_url())
        
        if not selected_ids:
            messages.error(request, 'No items selected.')
            return redirect(self.get_success_url())
        
        try:
            result = self.perform_bulk_action(action, selected_ids)
            messages.success(request, self.get_bulk_success_message(action, result))
        except Exception as e:
            logger.error(f"Bulk action {action} failed: {e}")
            messages.error(request, f'Bulk action failed: {str(e)}')
        
        return redirect(self.get_success_url())
    
    def perform_bulk_action(self, action, selected_ids):
        """Perform the bulk action"""
        method_name = f'bulk_{action}'
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            return method(selected_ids)
        else:
            raise ValueError(f"Unknown bulk action: {action}")
    
    def get_bulk_success_message(self, action, result):
        """Get success message for bulk action"""
        return f'Bulk {action} completed successfully.'


class ExportMixin:
    """Mixin for data export functionality"""
    
    export_formats = ['csv', 'json', 'xlsx']
    
    def get_export_format(self):
        """Get export format from request"""
        format_type = self.request.GET.get('format', 'csv')
        if format_type not in self.export_formats:
            format_type = 'csv'
        return format_type
    
    def get_export_filename(self, format_type):
        """Generate export filename"""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        return f'alerts_export_{timestamp}.{format_type}'
    
    def export_data(self, queryset, format_type):
        """Export data in specified format"""
        if format_type == 'csv':
            return self.export_to_csv(queryset)
        elif format_type == 'json':
            return self.export_to_json(queryset)
        elif format_type == 'xlsx':
            return self.export_to_xlsx(queryset)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def export_to_csv(self, queryset):
        """Export queryset to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.get_export_filename("csv")}"'
        
        writer = csv.writer(response)
        
        # Write headers
        if hasattr(self, 'export_fields'):
            writer.writerow(self.export_fields)
        else:
            writer.writerow(['ID', 'Name', 'Created At'])  # Default headers
        
        # Write data
        for obj in queryset:
            row = []
            if hasattr(self, 'export_fields'):
                for field in self.export_fields:
                    row.append(str(getattr(obj, field, '')))
            else:
                row = [str(obj.id), str(obj), str(getattr(obj, 'created_at', ''))]
            writer.writerow(row)
        
        return response
    
    def export_to_json(self, queryset):
        """Export queryset to JSON"""
        from django.http import HttpResponse
        import json
        
        data = []
        for obj in queryset:
            if hasattr(self, 'get_export_data'):
                data.append(self.get_export_data(obj))
            else:
                data.append({
                    'id': obj.id,
                    'name': str(obj),
                    'created_at': getattr(obj, 'created_at', None)
                })
        
        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{self.get_export_filename("json")}"'
        
        return response
    
    def export_to_xlsx(self, queryset):
        """Export queryset to XLSX"""
        try:
            import openpyxl
            from django.http import HttpResponse
            from io import BytesIO
            
            workbook = openpyxl.Workbook()
            worksheet = workbook.active
            worksheet.title = 'Alerts Export'
            
            # Write headers
            if hasattr(self, 'export_fields'):
                worksheet.append(self.export_fields)
            else:
                worksheet.append(['ID', 'Name', 'Created At'])
            
            # Write data
            for obj in queryset:
                row = []
                if hasattr(self, 'export_fields'):
                    for field in self.export_fields:
                        row.append(str(getattr(obj, field, '')))
                else:
                    row = [str(obj.id), str(obj), str(getattr(obj, 'created_at', ''))]
                worksheet.append(row)
            
            # Save to BytesIO
            output = BytesIO()
            workbook.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{self.get_export_filename("xlsx")}"'
            
            return response
        
        except ImportError:
            raise ValueError("openpyxl is required for XLSX export")


class RealTimeMixin:
    """Mixin for real-time updates"""
    
    def get_real_time_data(self, request):
        """Get real-time data for the view"""
        return {
            'timestamp': timezone.now().isoformat(),
            'user_id': request.user.id if request.user.is_authenticated else None,
        }
    
    def get_context_data(self, **kwargs):
        """Add real-time data to context"""
        context = super().get_context_data(**kwargs)
        context['real_time_data'] = self.get_real_time_data(self.request)
        return context


class TransactionMixin:
    """Mixin for database transactions"""
    
    def dispatch(self, request, *args, **kwargs):
        """Wrap dispatch in transaction"""
        with transaction.atomic():
            return super().dispatch(request, *args, **kwargs)


class TenantIsolationMixin:
    """
    Enforces strict multi-tenant data isolation on all QuerySets and create operations.

    Place as the FIRST mixin in every ModelViewSet that has a `tenant` FK field so
    it sits first in the MRO and transparently scopes every queryset.

    Tenant resolution order:
      1. request.user.tenant_id  (FK attribute set by auth layer / JWT claim)
      2. HTTP_X_TENANT_ID header  (service-to-service calls). Only honoured for
         superusers and service accounts (``user.is_service_account``); for everybody
         else the header is ignored - otherwise any authenticated user could read or
         write another tenant's data just by sending it.

    Fail-closed multi-tenancy: set ``ENABLE_MULTI_TENANT = True`` in settings and a
    non-privileged user whose tenant cannot be resolved gets an EMPTY queryset instead
    of every tenant's rows. The default (False) keeps single-tenant installs unchanged.

    Usage::

        class AlertRuleViewSet(TenantIsolationMixin, viewsets.ModelViewSet):
            ...
            def perform_create(self, serializer):
                serializer.save(created_by=self.request.user, **self.tenant_save_kwargs())
    """

    def get_tenant_id(self):
        """
        Return the integer tenant PK for the authenticated user.
        Returns None for unauthenticated requests (DRF permission classes handle rejection).
        """
        user = getattr(self.request, 'user', None)
        if user is None or not user.is_authenticated:
            return None

        # Primary source: FK attribute on User model (e.g. user.tenant_id)
        tenant_id = getattr(user, 'tenant_id', None)
        if tenant_id is not None:
            return tenant_id

        # Secondary: explicit header for service-to-service calls (privileged callers only)
        if self._is_cross_tenant_user(user):
            raw = self.request.META.get('HTTP_X_TENANT_ID', '').strip()
            if raw:
                try:
                    return int(raw)
                except (ValueError, TypeError):
                    pass

        return None

    @staticmethod
    def _is_cross_tenant_user(user):
        """Superusers and service accounts may act across / on behalf of tenants."""
        return bool(getattr(user, 'is_superuser', False) or getattr(user, 'is_service_account', False))

    @staticmethod
    def _multi_tenant_enforced():
        from django.conf import settings
        return bool(getattr(settings, 'ENABLE_MULTI_TENANT', False))

    def get_tenant(self):
        """Return the Tenant object (triggers a DB hit; prefer get_tenant_id where possible)."""
        user = getattr(self.request, 'user', None)
        if user is None or not user.is_authenticated:
            return None
        return getattr(user, 'tenant', None)

    def get_queryset(self):
        """
        Transparently scope all querysets to the current tenant.
        Subclasses that override get_queryset() gain isolation automatically
        because they call super().get_queryset() which lands here first.
        """
        qs = super().get_queryset()
        tenant_id = self.get_tenant_id()
        if tenant_id is not None:
            qs = qs.filter(tenant_id=tenant_id)
        elif self._multi_tenant_enforced():
            user = getattr(self.request, 'user', None)
            if not self._is_cross_tenant_user(user):
                qs = qs.none()  # fail closed: no resolvable tenant means no data
        return qs

    def tenant_save_kwargs(self):
        """
        Return a dict to spread into serializer.save() so that new records are
        stamped with the current tenant.  Returns {} when tenant cannot be resolved
        (lets the DB constraint / clean() catch the missing FK rather than 500ing here).
        """
        tenant_id = self.get_tenant_id()
        if tenant_id is not None:
            return {'tenant_id': tenant_id}
        return {}

    def perform_create(self, serializer):
        """
        Default implementation stamps both created_by and tenant.
        Subclasses that need to add more kwargs should call:
            serializer.save(extra=value, **self.tenant_save_kwargs())
        and NOT call super().perform_create() to avoid double-save.
        """
        serializer.save(
            created_by=self.request.user,
            **self.tenant_save_kwargs(),
        )


class RateLimitMixin:
    """Mixin for rate limiting"""
    
    rate_limit_requests = 100
    rate_limit_period = 3600  # 1 hour
    
    def dispatch(self, request, *args, **kwargs):
        """Check rate limit before processing"""
        if not self.check_rate_limit(request):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f'You have exceeded the rate limit of {self.rate_limit_requests} requests per {self.rate_limit_period} seconds.'
                }, status=429)
            else:
                messages.error(request, 'Rate limit exceeded. Please try again later.')
                return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def check_rate_limit(self, request):
        """Check if request is within rate limit"""
        if not request.user.is_authenticated:
            return True  # Skip rate limiting for anonymous users
        
        cache_key = f'rate_limit_{request.user.id}_{self.__class__.__name__}'
        current_count = cache.get(cache_key, 0)
        
        if current_count >= self.rate_limit_requests:
            return False
        
        # Increment counter
        cache.set(cache_key, current_count + 1, self.rate_limit_period)
        return True


class AlertContextMixin:
    """Mixin for alert-specific context data"""
    
    def get_context_data(self, **kwargs):
        """Add alert context to template context"""
        context = super().get_context_data(**kwargs)
        
        # Add alert counts
        context.update({
            'unresolved_alerts_count': self.get_unresolved_alerts_count(),
            'critical_alerts_count': self.get_critical_alerts_count(),
            'recent_alerts': self.get_recent_alerts(),
        })
        
        return context
    
    def get_unresolved_alerts_count(self):
        """Get count of unresolved alerts"""
        from .models import AlertLog
        return AlertLog.objects.filter(is_resolved=False).count()
    
    def get_critical_alerts_count(self):
        """Get count of critical alerts"""
        from .models import AlertLog
        return AlertLog.objects.filter(
            is_resolved=False,
            rule__severity='critical'
        ).count()
    
    def get_recent_alerts(self):
        """Get recent alerts"""
        from .models import AlertLog
        return AlertLog.objects.select_related('rule').order_by('-triggered_at')[:5]
