"""
Messaging Filters — django-filter FilterSets.
"""
import django_filters
from .choices import ChatStatus, BroadcastStatus, SupportThreadStatus, SupportThreadPriority, InboxItemType
from .models import InternalChat, AdminBroadcast, SupportThread, UserInbox


class ChatFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=ChatStatus.choices)
    is_group = django_filters.BooleanFilter()

    class Meta:
        model = InternalChat
        fields = ["status", "is_group"]


class BroadcastFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=BroadcastStatus.choices)
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = AdminBroadcast
        fields = ["status"]


class SupportThreadFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=SupportThreadStatus.choices)
    priority = django_filters.ChoiceFilter(choices=SupportThreadPriority.choices)
    is_assigned = django_filters.BooleanFilter(method="filter_is_assigned")

    class Meta:
        model = SupportThread
        fields = ["status", "priority"]

    def filter_is_assigned(self, queryset, name, value):
        if value is True:
            return queryset.filter(assigned_agent__isnull=False)
        return queryset.filter(assigned_agent__isnull=True)


class UserInboxFilter(django_filters.FilterSet):
    item_type = django_filters.ChoiceFilter(choices=InboxItemType.choices)
    is_read = django_filters.BooleanFilter()
    is_archived = django_filters.BooleanFilter()

    class Meta:
        model = UserInbox
        fields = ["item_type", "is_read", "is_archived"]
