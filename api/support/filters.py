# api/support/filters.py
from django.db.models import Q


def apply_ticket_filters(queryset, params):
    if params.get('status'):
        queryset = queryset.filter(status=params['status'])
    if params.get('priority'):
        queryset = queryset.filter(priority=params['priority'])
    if params.get('category'):
        queryset = queryset.filter(category=params['category'])
    q = params.get('search') or params.get('q')
    if q:
        queryset = queryset.filter(
            Q(ticket_id__icontains=q) | Q(subject__icontains=q) |
            Q(description__icontains=q) | Q(user__username__icontains=q)
        )
    if params.get('escalated') == 'true':
        queryset = queryset.filter(escalated=True)
    if params.get('unanswered') == 'true':
        queryset = queryset.filter(Q(admin_response='') | Q(admin_response__isnull=True))
    return queryset


class SupportTicketFilter:
    @staticmethod
    def apply(queryset, params):
        return apply_ticket_filters(queryset, params)


try:
    import django_filters

    class FAQFilter(django_filters.FilterSet):
        search = django_filters.CharFilter(method='filter_search')

        class Meta:
            from api.support.models import FAQ
            model = FAQ
            fields = ['category', 'is_active']

        def filter_search(self, qs, name, val):
            return qs.filter(Q(question__icontains=val) | Q(answer__icontains=val))

except ImportError:
    pass