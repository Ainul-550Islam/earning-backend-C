# kyc/filters.py  ── WORLD #1
try:
    from django_filters import rest_framework as filters
    from .models import KYC, KYCSubmission

    class KYCFilter(filters.FilterSet):
        status        = filters.CharFilter(field_name='status')
        document_type = filters.CharFilter(field_name='document_type')
        risk_min      = filters.NumberFilter(field_name='risk_score', lookup_expr='gte')
        risk_max      = filters.NumberFilter(field_name='risk_score', lookup_expr='lte')
        created_after = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
        created_before= filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
        is_duplicate  = filters.BooleanFilter(field_name='is_duplicate')
        search        = filters.CharFilter(method='search_filter')

        class Meta:
            model  = KYC
            fields = ['status', 'document_type', 'is_duplicate']

        def search_filter(self, queryset, name, value):
            from django.db.models import Q
            return queryset.filter(
                Q(full_name__icontains=value) | Q(phone_number__icontains=value) |
                Q(document_number__icontains=value) | Q(user__username__icontains=value)
            )

    class KYCSubmissionFilter(filters.FilterSet):
        status = filters.CharFilter(field_name='status')
        class Meta:
            model = KYCSubmission
            fields = ['status', 'document_type']

except ImportError:
    # django-filter not installed — skip
    KYCFilter = None
    KYCSubmissionFilter = None
