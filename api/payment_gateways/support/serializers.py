# api/payment_gateways/support/serializers.py
from rest_framework import serializers
from .models import SupportTicket, TicketMessage


class TicketMessageSerializer(serializers.ModelSerializer):
    sender_name   = serializers.SerializerMethodField()
    sender_email  = serializers.EmailField(source='sender.email', read_only=True)

    class Meta:
        model  = TicketMessage
        fields = ['id','message','is_staff','sender_name','sender_email',
                  'attachment_url','created_at']
        read_only_fields = ['is_staff','created_at']

    def get_sender_name(self, obj):
        return obj.sender.get_full_name() or obj.sender.username


class SupportTicketListSerializer(serializers.ModelSerializer):
    user_email     = serializers.EmailField(source='user.email', read_only=True)
    messages_count = serializers.SerializerMethodField()

    class Meta:
        model  = SupportTicket
        fields = ['id','ticket_number','subject','category','priority','status',
                  'user_email','messages_count','created_at']

    def get_messages_count(self, obj):
        return obj.messages.count()


class SupportTicketDetailSerializer(serializers.ModelSerializer):
    user_email      = serializers.EmailField(source='user.email', read_only=True)
    assigned_to_name= serializers.SerializerMethodField()
    messages        = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model  = SupportTicket
        fields = ['id','ticket_number','subject','category','priority','status',
                  'description','related_txn_ref','attachment_url','user_email',
                  'assigned_to_name','resolved_at','messages','created_at']
        read_only_fields = ['ticket_number','resolved_at','created_at']

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return None


class CreateTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SupportTicket
        fields = ['subject','category','priority','description',
                  'related_txn_ref','attachment_url']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ReplyTicketSerializer(serializers.Serializer):
    message        = serializers.CharField(min_length=5)
    attachment_url = serializers.URLField(required=False, allow_blank=True)
