from rest_framework import serializers
from api.support.models import AgentStatus
class AgentStatusSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='agent.user.username', read_only=True)
    class Meta:
        model  = AgentStatus
        fields = ['id','username','status','changed_at','last_seen','status_message']