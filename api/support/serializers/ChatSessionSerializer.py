from rest_framework import serializers
from api.support.models import ChatSession
class ChatSessionSerializer(serializers.ModelSerializer):
    username   = serializers.CharField(source='user.username', read_only=True)
    agent_name = serializers.CharField(source='agent.username', read_only=True)
    class Meta:
        model  = ChatSession
        fields = ['id','session_id','username','agent_name','status','queue_position','started_at','ended_at']