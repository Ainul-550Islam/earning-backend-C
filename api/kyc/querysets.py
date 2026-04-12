# kyc/querysets.py  ── WORLD #1
"""
Standalone queryset helpers used by selectors & services.
Keeps business logic out of models.py.
"""
from django.db.models import Q


def kyc_search_qs(queryset, query: str):
    """Apply full-text search to a KYC queryset."""
    if not query:
        return queryset
    return queryset.filter(
        Q(full_name__icontains=query)
        | Q(phone_number__icontains=query)
        | Q(document_number__icontains=query)
        | Q(payment_number__icontains=query)
        | Q(user__username__icontains=query)
        | Q(user__email__icontains=query)
        | Q(city__icontains=query)
    )


def kyc_filter_qs(queryset, filters: dict):
    """
    Apply standard filters dict to KYC queryset.
    filters keys: status, document_type, is_duplicate, risk_min, risk_max,
                  created_after, created_before, tenant
    """
    if filters.get('status'):
        queryset = queryset.filter(status=filters['status'])
    if filters.get('document_type'):
        queryset = queryset.filter(document_type=filters['document_type'])
    if filters.get('is_duplicate') is not None:
        queryset = queryset.filter(is_duplicate=filters['is_duplicate'])
    if filters.get('risk_min') is not None:
        queryset = queryset.filter(risk_score__gte=filters['risk_min'])
    if filters.get('risk_max') is not None:
        queryset = queryset.filter(risk_score__lte=filters['risk_max'])
    if filters.get('created_after'):
        queryset = queryset.filter(created_at__date__gte=filters['created_after'])
    if filters.get('created_before'):
        queryset = queryset.filter(created_at__date__lte=filters['created_before'])
    if filters.get('tenant'):
        queryset = queryset.filter(tenant=filters['tenant'])
    return queryset


def get_blocked_kycs(queryset):
    """KYCs blocked by blacklist."""
    from .models import KYCBlacklist
    blacklisted_phones = KYCBlacklist.objects.filter(
        type='phone', is_active=True
    ).values_list('value', flat=True)
    blacklisted_docs = KYCBlacklist.objects.filter(
        type='document', is_active=True
    ).values_list('value', flat=True)
    return queryset.filter(
        Q(phone_number__in=blacklisted_phones) | Q(document_number__in=blacklisted_docs)
    )
