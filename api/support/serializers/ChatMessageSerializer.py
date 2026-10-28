from rest_framework import serializers
from api.support.models import ChatMessage
class ChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    class Meta:
        model  = ChatMessage
        fields = ['id','session','content','message_type','is_read','is_agent','is_bot','sender_username','created_at']