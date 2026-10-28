"""
api/support/portal/portal_serializers.py
FILE 37/70 — Customer Portal Serializers
"""
from rest_framework import serializers
from api.support.models import SupportTicket, TicketMessage, TicketRating


class PortalTicketListSerializer(serializers.ModelSerializer):
    """Lightweight ticket list for portal"""
    status_label   = serializers.SerializerMethodField()
    priority_label = serializers.SerializerMethodField()
    wait_hours     = serializers.SerializerMethodField()
    has_new_reply  = serializers.SerializerMethodField()

    class Meta:
        model  = SupportTicket
        fields = [
            'ticket_id', 'subject', 'category', 'status', 'status_label',
            'priority', 'priority_label', 'created_at', 'updated_at',
            'message_count', 'wait_hours', 'has_new_reply', 'satisfaction_rating',
        ]

    def get_status_label(self, obj) -> str:
        labels = {
            'open':         '🟡 Open',
            'in_progress':  '🔵 In Progress',
            'waiting_user': '🟠 Waiting for Your Reply',
            'resolved':     '✅ Resolved',
            'closed':       '⛔ Closed',
            'spam':         '🚫 Spam',
        }
        return labels.get(obj.status, obj.status)

    def get_priority_label(self, obj) -> str:
        labels = {'urgent': '🚨 Urgent', 'high': '⚠️ High', 'medium': '📢 Medium', 'low': 'ℹ️ Low'}
        return labels.get(obj.priority, obj.priority)

    def get_wait_hours(self, obj) -> float:
        from django.utils import timezone
        diff = (timezone.now() - obj.created_at).total_seconds() / 3600
        return round(diff, 1)

    def get_has_new_reply(self, obj) -> bool:
        return obj.status == 'waiting_user'


class PortalTicketDetailSerializer(serializers.ModelSerializer):
    """Full ticket detail for portal"""
    status_label   = serializers.SerializerMethodField()
    can_reply      = serializers.SerializerMethodField()
    can_rate       = serializers.SerializerMethodField()
    can_reopen     = serializers.SerializerMethodField()
    agent_username = serializers.CharField(source='assigned_to.username', allow_null=True, read_only=True)

    class Meta:
        model  = SupportTicket
        fields = [
            'ticket_id', 'subject', 'description', 'category', 'status',
            'status_label', 'priority', 'channel', 'created_at', 'updated_at',
            'resolved_at', 'message_count', 'agent_username',
            'admin_response', 'admin_responded_at',
            'satisfaction_rating', 'rating_comment', 'rated_at',
            'can_reply', 'can_rate', 'can_reopen',
        ]
        read_only_fields = fields

    def get_status_label(self, obj) -> str:
        labels = {
            'open':         '🟡 Open — Our team is reviewing your request',
            'in_progress':  '🔵 In Progress — We are working on it',
            'waiting_user': '🟠 Waiting — Please reply to our response',
            'resolved':     '✅ Resolved — Issue has been fixed',
            'closed':       '⛔ Closed',
        }
        return labels.get(obj.status, obj.status)

    def get_can_reply(self, obj) -> bool:
        return obj.status not in ['closed', 'spam']

    def get_can_rate(self, obj) -> bool:
        return obj.status in ['resolved', 'closed'] and not obj.satisfaction_rating

    def get_can_reopen(self, obj) -> bool:
        return obj.status in ['resolved', 'closed']


class PortalMessageSerializer(serializers.ModelSerializer):
    """Message in ticket thread"""
    sender_name    = serializers.SerializerMethodField()
    sender_type    = serializers.SerializerMethodField()
    time_ago       = serializers.SerializerMethodField()

    class Meta:
        model  = TicketMessage
        fields = [
            'id', 'content', 'is_agent', 'created_at', 'is_edited',
            'sender_name', 'sender_type', 'time_ago',
        ]

    def get_sender_name(self, obj) -> str:
        if obj.is_agent:
            return 'Support Team'
        return obj.sender.username if obj.sender else 'You'

    def get_sender_type(self, obj) -> str:
        return 'agent' if obj.is_agent else 'user'

    def get_time_ago(self, obj) -> str:
        from django.utils import timezone
        diff = (timezone.now() - obj.created_at).total_seconds()
        if diff < 60:
            return 'just now'
        if diff < 3600:
            return f'{int(diff/60)}m ago'
        if diff < 86400:
            return f'{int(diff/3600)}h ago'
        return obj.created_at.strftime('%d %b %Y')


class PortalCreateTicketSerializer(serializers.Serializer):
    category    = serializers.ChoiceField(choices=[
        ("payment","Payment"),("withdrawal","Withdrawal"),("coins","Coins"),
        ("account","Account"),("fraud","Fraud"),("kyc","KYC"),
        ("technical","Technical"),("referral","Referral"),("offer","Offer"),("other","Other"),
    ])
    subject     = serializers.CharField(min_length=5, max_length=200)
    description = serializers.CharField(min_length=10, max_length=5000)
    check_kb_first = serializers.BooleanField(default=True)


class PortalRateSerializer(serializers.Serializer):
    rating         = serializers.IntegerField(min_value=1, max_value=5)
    comment        = serializers.CharField(max_length=500, required=False, default='')
    agent_rating   = serializers.IntegerField(min_value=1, max_value=5, required=False)
    speed_rating   = serializers.IntegerField(min_value=1, max_value=5, required=False)
    solution_rating= serializers.IntegerField(min_value=1, max_value=5, required=False)