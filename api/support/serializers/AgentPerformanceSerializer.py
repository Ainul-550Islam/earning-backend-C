from rest_framework import serializers
from api.support.models import AgentPerformance
class AgentPerformanceSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='agent.user.username', read_only=True)
    class Meta:
        model  = AgentPerformance
        fields = ['id','username','period','avg_response_minutes','avg_resolution_hours','csat_score','tickets_resolved','tickets_assigned','chats_handled','sla_breaches_caused']