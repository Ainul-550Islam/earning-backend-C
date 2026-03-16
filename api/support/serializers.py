# api/support/serializers.py  —  COMPLETE serializers
from rest_framework import serializers
from .models import SupportSettings, SupportTicket, FAQ


class SupportSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SupportSettings
        fields = [
            'id', 'telegram_group', 'telegram_admin',
            'whatsapp_number', 'whatsapp_group', 'facebook_page',
            'email_support', 'support_hours_start', 'support_hours_end',
            'is_support_online', 'maintenance_mode', 'maintenance_message',
            'force_update', 'latest_version_code', 'latest_version_name',
            'update_message', 'play_store_url',
        ]


class SupportTicketSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = SupportTicket
        fields = [
            'id', 'ticket_id', 'user', 'username',
            'subject', 'category', 'priority', 'status',
            'description', 'screenshot',
            'admin_response', 'admin_responded_at',
            'created_at', 'updated_at', 'resolved_at',
        ]
        read_only_fields = [
            'user', 'ticket_id', 'created_at', 'updated_at',
            'admin_response', 'admin_responded_at', 'resolved_at',
        ]


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FAQ
        fields = ['id', 'question', 'answer', 'category', 'is_active', 'order', 'created_at']
        read_only_fields = ['created_at']