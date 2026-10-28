from rest_framework import serializers
from api.support.models import ChatQueue
class ChatQueueSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model  = ChatQueue
        fields = ['id','username','department','joined_at','estimated_wait_minutes','position','is_active']