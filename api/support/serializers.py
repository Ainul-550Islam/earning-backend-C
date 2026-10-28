# api/support/serializers.py  — WORLD #1 COMPLETE
from rest_framework import serializers
from .models import (
    SupportSettings, SupportTicket, FAQ,
    TicketMessage, TicketAttachment, LiveChatSession, LiveChatMessage,
    SupportAgent, KBCategory, KBArticle, OfferDispute, CannedResponse,
    TicketTag, NetworkAnnouncement,
)


class SupportSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SupportSettings
        fields = [
            'id', 'telegram_group', 'telegram_admin',
            'whatsapp_number', 'whatsapp_group', 'facebook_page', 'email_support',
            'support_hours_start', 'support_hours_end', 'support_timezone',
            'is_support_online', 'maintenance_mode', 'maintenance_message',
            'force_update', 'latest_version_code', 'latest_version_name',
            'update_message', 'play_store_url',
            'chat_widget_enabled', 'chat_widget_color', 'chat_bot_enabled',
        ]


class TicketMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    time_ago        = serializers.SerializerMethodField()

    class Meta:
        model  = TicketMessage
        fields = [
            'id', 'content', 'is_agent', 'is_internal',
            'sender_username', 'time_ago', 'created_at', 'is_edited',
        ]

    def get_time_ago(self, obj) -> str:
        from django.utils import timezone
        diff = (timezone.now() - obj.created_at).total_seconds()
        if diff < 60:   return 'just now'
        if diff < 3600: return f'{int(diff/60)}m ago'
        if diff < 86400:return f'{int(diff/3600)}h ago'
        return obj.created_at.strftime('%d %b %Y')


class TicketAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TicketAttachment
        fields = ['id', 'filename', 'file_type', 'size_mb', 'created_at']


class SupportTicketListSerializer(serializers.ModelSerializer):
    username     = serializers.CharField(source='user.username', read_only=True)
    status_label = serializers.SerializerMethodField()
    wait_hours   = serializers.SerializerMethodField()

    class Meta:
        model  = SupportTicket
        fields = [
            'id', 'ticket_id', 'username', 'subject', 'category',
            'priority', 'status', 'status_label',
            'created_at', 'updated_at', 'wait_hours',
            'satisfaction_rating', 'message_count',
        ]

    def get_status_label(self, obj) -> str:
        labels = {
            'open':         '🟡 Open',
            'in_progress':  '🔵 In Progress',
            'waiting_user': '🟠 Waiting for You',
            'resolved':     '✅ Resolved',
            'closed':       '⛔ Closed',
            'spam':         '🚫 Spam',
        }
        return labels.get(obj.status, obj.status)

    def get_wait_hours(self, obj) -> float:
        from django.utils import timezone
        return round((timezone.now() - obj.created_at).total_seconds() / 3600, 1)


class SupportTicketSerializer(serializers.ModelSerializer):
    username       = serializers.CharField(source='user.username', read_only=True)
    messages       = serializers.SerializerMethodField()
    attachments    = TicketAttachmentSerializer(many=True, read_only=True)
    assigned_agent = serializers.SerializerMethodField()

    class Meta:
        model  = SupportTicket
        fields = [
            'id', 'ticket_id', 'user', 'username',
            'subject', 'category', 'priority', 'status',
            'description', 'screenshot', 'channel',
            'admin_response', 'admin_responded_at',
            'created_at', 'updated_at', 'resolved_at',
            'escalated', 'satisfaction_rating', 'rating_comment',
            'message_count', 'messages', 'attachments', 'assigned_agent',
        ]
        read_only_fields = [
            'user', 'ticket_id', 'created_at', 'updated_at',
            'admin_response', 'admin_responded_at', 'resolved_at',
        ]

    def get_messages(self, obj):
        request = self.context.get('request')
        is_agent = request and (request.user.is_staff or request.user.is_superuser)
        qs = obj.messages.filter(is_internal=False) if not is_agent else obj.messages.all()
        return TicketMessageSerializer(qs, many=True).data

    def get_assigned_agent(self, obj) -> str | None:
        return obj.assigned_to.username if obj.assigned_to else None


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SupportTicket
        fields = ['subject', 'category', 'description', 'priority', 'screenshot']

    def validate_subject(self, v):
        if len(v.strip()) < 5:
            raise serializers.ValidationError('Subject must be at least 5 characters.')
        return v.strip()

    def validate_description(self, v):
        if len(v.strip()) < 10:
            raise serializers.ValidationError('Description must be at least 10 characters.')
        return v.strip()


class FAQSerializer(serializers.ModelSerializer):
    helpful_ratio = serializers.ReadOnlyField()

    class Meta:
        model  = FAQ
        fields = [
            'id', 'question', 'answer', 'category',
            'is_active', 'order', 'helpful_yes', 'helpful_no',
            'helpful_ratio', 'view_count', 'tags', 'created_at',
        ]
        read_only_fields = ['created_at', 'helpful_yes', 'helpful_no', 'view_count']


class LiveChatSessionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = LiveChatSession
        fields = [
            'id', 'session_id', 'username', 'status',
            'queue_position', 'rating', 'started_at', 'ended_at',
        ]


class LiveChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model  = LiveChatMessage
        fields = ['id', 'content', 'is_agent', 'is_bot', 'msg_type', 'sender_username', 'created_at']


class KBCategorySerializer(serializers.ModelSerializer):
    article_count = serializers.SerializerMethodField()

    class Meta:
        model  = KBCategory
        fields = ['id', 'name', 'slug', 'icon', 'order', 'article_count']

    def get_article_count(self, obj) -> int:
        return obj.articles.filter(status='published', is_public=True).count()


class KBArticleListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model  = KBArticle
        fields = ['id', 'title', 'slug', 'summary', 'category_name', 'view_count', 'tags', 'created_at']


class KBArticleSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    helpful_ratio = serializers.SerializerMethodField()

    class Meta:
        model  = KBArticle
        fields = [
            'id', 'title', 'slug', 'body', 'summary', 'category_name',
            'status', 'is_public', 'tags', 'view_count',
            'helpful_yes', 'helpful_no', 'helpful_ratio', 'created_at', 'updated_at',
        ]

    def get_helpful_ratio(self, obj) -> float:
        total = obj.helpful_yes + obj.helpful_no
        return round(obj.helpful_yes / total * 100, 1) if total else 0


class OfferDisputeSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = OfferDispute
        fields = [
            'id', 'username', 'offer_id', 'offer_name', 'expected_amount',
            'click_id', 'status', 'verification_status', 'confidence_score',
            'created_at', 'resolved_at',
        ]
        read_only_fields = ['status', 'verification_status', 'confidence_score', 'created_at']


class CannedResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CannedResponse
        fields = ['id', 'shortcut', 'title', 'content', 'category', 'use_count']


class TicketTagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TicketTag
        fields = ['id', 'name', 'color']


class NetworkAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model  = NetworkAnnouncement
        fields = ['id', 'title', 'content', 'type', 'starts_at', 'ends_at', 'created_at']


class TicketStatsSerializer(serializers.Serializer):
    total      = serializers.IntegerField()
    open       = serializers.IntegerField()
    in_progress= serializers.IntegerField()
    waiting_user = serializers.IntegerField()
    resolved   = serializers.IntegerField()
    closed     = serializers.IntegerField()
    urgent     = serializers.IntegerField()
    unanswered = serializers.IntegerField()
    today      = serializers.IntegerField()
    avg_response_hours = serializers.FloatField()


class WithdrawalDisputeSerializer(serializers.ModelSerializer):
    """Serializer for WithdrawalDispute model."""
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        from api.support.models import WithdrawalDispute
        model  = WithdrawalDispute
        fields = [
            'id', 'user_username', 'transaction_id', 'amount',
            'payment_method', 'account_number', 'status',
            'resolution_notes', 'created_at', 'resolved_at',
        ]
        read_only_fields = ['id', 'status', 'resolution_notes', 'created_at', 'resolved_at']


class SupportAgentSerializer(serializers.ModelSerializer):
    """Serializer for SupportAgent model."""
    username   = serializers.CharField(source='user.username', read_only=True)
    email      = serializers.CharField(source='user.email', read_only=True)
    status     = serializers.CharField(source='status_record.status', read_only=True, default='offline')
    department_name = serializers.CharField(source='department.name', read_only=True, default='')

    class Meta:
        from api.support.models import SupportAgent
        model  = SupportAgent
        fields = [
            'id', 'username', 'email', 'role', 'department_name',
            'is_active', 'is_available', 'status',
            'max_concurrent_chats', 'max_concurrent_tickets',
            'skills', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class TicketSLASerializer(serializers.ModelSerializer):
    """Serializer for TicketSLA model."""
    is_breached = serializers.SerializerMethodField()

    class Meta:
        from api.support.models import TicketSLA
        model  = TicketSLA
        fields = [
            'first_response_due', 'resolution_due',
            'first_response_at', 'resolution_at',
            'first_response_breached', 'resolution_breached',
            'is_breached', 'warning_sent',
        ]

    def get_is_breached(self, obj):
        return obj.is_breached