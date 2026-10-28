from rest_framework import serializers
from api.support.models import SupportInsight, CSATReport, AgentReport, ChannelReport
class SupportInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SupportInsight
        fields = '__all__'
class CSATReportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CSATReport
        fields = '__all__'
class AgentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AgentReport
        fields = '__all__'
class ChannelReportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ChannelReport
        fields = '__all__'
class InsightSerializer(serializers.Serializer):
    period_days = serializers.IntegerField()
    total       = serializers.IntegerField()
    resolved    = serializers.IntegerField()
    open        = serializers.IntegerField()
    avg_response_hours = serializers.FloatField()
    csat_avg    = serializers.FloatField()
    sla_rate    = serializers.FloatField()