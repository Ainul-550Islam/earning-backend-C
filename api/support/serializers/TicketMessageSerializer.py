from rest_framework import serializers
from api.support.models import TicketMessage
from django.utils import timezone

class TicketMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    time_ago = serializers.SerializerMethodField()
    class Meta:
        model  = TicketMessage
        fields = ['id','ticket','content','is_agent','is_internal','is_read','sender_username','time_ago','attachment','created_at','is_edited']
        read_only_fields = ['created_at','is_edited']
    def get_time_ago(self, obj) -> str:
        diff = (timezone.now() - obj.created_at).total_seconds()
        if diff < 60: return 'just now'
        if diff < 3600: return f'{int(diff/60)}m ago'
        if diff < 86400: return f'{int(diff/3600)}h ago'
        return obj.created_at.strftime('%d %b %Y')