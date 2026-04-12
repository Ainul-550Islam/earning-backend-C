"""
Messaging Filters — Complete django-filter FilterSets for all models.
"""
import django_filters
from django.db.models import Q
from .choices import (
    ChatStatus, BroadcastStatus, SupportThreadStatus,
    SupportThreadPriority, InboxItemType, MessageType,
    MessageStatus, CallStatus, CallType, PresenceStatus,
)
from .models import (
    InternalChat, AdminBroadcast, SupportThread, UserInbox,
    ChatMessage, CallSession, UserPresence, CPANotification,
    CPABroadcast, MessageTemplate, AffiliateConversationThread,
    MediaAttachment, MessageReport,
)


class ChatFilter(django_filters.FilterSet):
    status   = django_filters.ChoiceFilter(choices=ChatStatus.choices)
    is_group = django_filters.BooleanFilter()
    is_encrypted = django_filters.BooleanFilter()
    name     = django_filters.CharFilter(lookup_expr="icontains")
    created_after  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model  = InternalChat
        fields = ["status", "is_group", "is_encrypted"]


class ChatMessageFilter(django_filters.FilterSet):
    message_type   = django_filters.ChoiceFilter(choices=MessageType.choices)
    status         = django_filters.ChoiceFilter(choices=MessageStatus.choices)
    sender         = django_filters.NumberFilter(field_name="sender_id")
    is_edited      = django_filters.BooleanFilter()
    is_forwarded   = django_filters.BooleanFilter()
    created_after  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    search         = django_filters.CharFilter(field_name="content", lookup_expr="icontains")

    class Meta:
        model  = ChatMessage
        fields = ["message_type", "status", "is_edited", "is_forwarded"]


class BroadcastFilter(django_filters.FilterSet):
    status         = django_filters.ChoiceFilter(choices=BroadcastStatus.choices)
    audience_type  = django_filters.CharFilter()
    created_after  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    scheduled_after  = django_filters.DateTimeFilter(field_name="scheduled_at", lookup_expr="gte")
    scheduled_before = django_filters.DateTimeFilter(field_name="scheduled_at", lookup_expr="lte")
    created_by     = django_filters.NumberFilter(field_name="created_by_id")

    class Meta:
        model  = AdminBroadcast
        fields = ["status", "audience_type"]


class SupportThreadFilter(django_filters.FilterSet):
    status          = django_filters.ChoiceFilter(choices=SupportThreadStatus.choices)
    priority        = django_filters.ChoiceFilter(choices=SupportThreadPriority.choices)
    is_assigned     = django_filters.BooleanFilter(method="filter_is_assigned")
    assigned_agent  = django_filters.NumberFilter(field_name="assigned_agent_id")
    user            = django_filters.NumberFilter(field_name="user_id")
    subject         = django_filters.CharFilter(lookup_expr="icontains")
    created_after   = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    last_reply_after  = django_filters.DateTimeFilter(field_name="last_reply_at", lookup_expr="gte")

    class Meta:
        model  = SupportThread
        fields = ["status", "priority"]

    def filter_is_assigned(self, queryset, name, value):
        if value is True:
            return queryset.filter(assigned_agent__isnull=False)
        return queryset.filter(assigned_agent__isnull=True)


class UserInboxFilter(django_filters.FilterSet):
    item_type   = django_filters.ChoiceFilter(choices=InboxItemType.choices)
    is_read     = django_filters.BooleanFilter()
    is_archived = django_filters.BooleanFilter()
    created_after  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model  = UserInbox
        fields = ["item_type", "is_read", "is_archived"]


class CallSessionFilter(django_filters.FilterSet):
    call_type  = django_filters.ChoiceFilter(choices=CallType.choices)
    status     = django_filters.ChoiceFilter(choices=CallStatus.choices)
    initiated_by = django_filters.NumberFilter(field_name="initiated_by_id")
    created_after  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model  = CallSession
        fields = ["call_type", "status"]


class UserPresenceFilter(django_filters.FilterSet):
    status       = django_filters.ChoiceFilter(choices=PresenceStatus.choices)
    is_invisible = django_filters.BooleanFilter()
    last_seen_on = django_filters.CharFilter()
    last_seen_after = django_filters.DateTimeFilter(field_name="last_seen_at", lookup_expr="gte")

    class Meta:
        model  = UserPresence
        fields = ["status", "is_invisible"]


class CPANotificationFilter(django_filters.FilterSet):
    notification_type = django_filters.CharFilter()
    is_read    = django_filters.BooleanFilter()
    is_dismissed = django_filters.BooleanFilter()
    priority   = django_filters.CharFilter()
    object_type = django_filters.CharFilter()
    created_after  = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    # Filter by category groups
    category   = django_filters.CharFilter(method="filter_by_category")

    class Meta:
        model  = CPANotification
        fields = ["notification_type", "is_read", "priority"]

    def filter_by_category(self, queryset, name, value):
        CATEGORY_MAP = {
            "offers":      ["offer.approved", "offer.rejected", "offer.paused",
                            "offer.new", "offer.expiring", "offer.reactivated"],
            "conversions": ["conversion.received", "conversion.approved",
                            "conversion.rejected", "conversion.chargeback", "postback.failed"],
            "payments":    ["payout.processed", "payout.reminder",
                            "payout.threshold", "payout.failed", "payout.hold"],
            "account":     ["affiliate.approved", "affiliate.rejected", "affiliate.suspended",
                            "affiliate.reinstated", "affiliate.banned", "affiliate.manager"],
            "system":      ["system.maintenance", "system.announcement",
                            "api.key_expiring", "terms.updated"],
            "performance": ["milestone.reached", "epc.drop", "fraud.alert"],
        }
        types = CATEGORY_MAP.get(value, [])
        if types:
            return queryset.filter(notification_type__in=types)
        return queryset


class CPABroadcastFilter(django_filters.FilterSet):
    status           = django_filters.CharFilter()
    audience_filter  = django_filters.CharFilter()
    notification_type = django_filters.CharFilter()
    created_after    = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before   = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    created_by       = django_filters.NumberFilter(field_name="created_by_id")

    class Meta:
        model  = CPABroadcast
        fields = ["status", "audience_filter"]


class MessageTemplateFilter(django_filters.FilterSet):
    category  = django_filters.CharFilter()
    is_active = django_filters.BooleanFilter()
    name      = django_filters.CharFilter(lookup_expr="icontains")
    tags      = django_filters.CharFilter(method="filter_by_tag")

    class Meta:
        model  = MessageTemplate
        fields = ["category", "is_active"]

    def filter_by_tag(self, queryset, name, value):
        return queryset.filter(tags__contains=[value])


class AffiliateThreadFilter(django_filters.FilterSet):
    status    = django_filters.CharFilter()
    manager   = django_filters.NumberFilter(field_name="manager_id")
    affiliate = django_filters.NumberFilter(field_name="affiliate_id")
    has_unread_manager = django_filters.BooleanFilter(method="filter_manager_unread")
    tag       = django_filters.CharFilter(method="filter_by_tag")

    class Meta:
        model  = AffiliateConversationThread
        fields = ["status", "manager"]

    def filter_manager_unread(self, queryset, name, value):
        if value:
            return queryset.filter(manager_unread__gt=0)
        return queryset.filter(manager_unread=0)

    def filter_by_tag(self, queryset, name, value):
        return queryset.filter(tags__contains=[value])


class MediaAttachmentFilter(django_filters.FilterSet):
    status        = django_filters.CharFilter()
    is_nsfw       = django_filters.BooleanFilter()
    is_virus_free = django_filters.BooleanFilter()
    mimetype      = django_filters.CharFilter(lookup_expr="startswith")
    uploaded_by   = django_filters.NumberFilter(field_name="uploaded_by_id")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")

    class Meta:
        model  = MediaAttachment
        fields = ["status", "is_nsfw"]


class MessageReportFilter(django_filters.FilterSet):
    reason      = django_filters.CharFilter()
    status      = django_filters.CharFilter()
    reported_by = django_filters.NumberFilter(field_name="reported_by_id")
    reviewed_by = django_filters.NumberFilter(field_name="reviewed_by_id")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")

    class Meta:
        model  = MessageReport
        fields = ["reason", "status"]
