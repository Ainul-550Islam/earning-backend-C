# api/support/admin_filters.py
"""
Additional Django admin filters for support.
Import and add to list_filter in admin.py.
"""
from django.contrib import admin
from django.utils import timezone
from datetime import timedelta


class SLABreachFilter(admin.SimpleListFilter):
    title          = 'SLA Status'
    parameter_name = 'sla_breach'

    def lookups(self, request, model_admin):
        return [
            ('breached',   '🚨 SLA Breached'),
            ('at_risk',    '⚠️ At Risk (within 1h)'),
            ('compliant',  '✅ Compliant'),
        ]

    def queryset(self, request, queryset):
        from django.db.models import Q
        if self.value() == 'breached':
            return queryset.filter(
                Q(sla__first_response_breached=True) | Q(sla__resolution_breached=True)
            )
        if self.value() == 'at_risk':
            soon = timezone.now() + timedelta(hours=1)
            return queryset.filter(
                sla__first_response_due__lte=soon,
                sla__first_response_at__isnull=True,
                status__in=['open', 'in_progress'],
            )
        if self.value() == 'compliant':
            return queryset.filter(
                sla__first_response_breached=False,
                sla__resolution_breached=False,
            )
        return queryset


class TenantFilter(admin.SimpleListFilter):
    title          = 'Tenant'
    parameter_name = 'tenant'

    def lookups(self, request, model_admin):
        try:
            from django.apps import apps
            Tenant = apps.get_model('tenants', 'Tenant')
            return [(str(t.id), t.name) for t in Tenant.objects.filter(is_active=True)[:20]]
        except Exception:
            return []

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tenant_id=self.value())
        return queryset


class AssignmentFilter(admin.SimpleListFilter):
    title          = 'Assignment'
    parameter_name = 'assignment'

    def lookups(self, request, model_admin):
        return [
            ('unassigned', '❓ Unassigned'),
            ('assigned',   '✅ Assigned'),
            ('assigned_to_me', '👤 Assigned to Me'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'unassigned':
            return queryset.filter(assigned_to__isnull=True)
        if self.value() == 'assigned':
            return queryset.filter(assigned_to__isnull=False)
        if self.value() == 'assigned_to_me':
            return queryset.filter(assigned_to=request.user)
        return queryset


class EscalatedFilter(admin.SimpleListFilter):
    title          = 'Escalation'
    parameter_name = 'escalated'

    def lookups(self, request, model_admin):
        return [('yes', '🔴 Escalated'), ('no', '⬜ Not Escalated')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(escalated=True)
        if self.value() == 'no':
            return queryset.filter(escalated=False)
        return queryset