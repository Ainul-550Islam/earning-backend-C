# api/alerts/serializers.py
"""
DRF serializers for api.alerts. Ensures data can be sent via API.
"""
from rest_framework import serializers

try:
    from .models import AlertRule, AlertLog
except ImportError:
    AlertRule = AlertLog = None

if AlertRule is not None:
    class AlertRuleSerializer(serializers.ModelSerializer):
        class Meta:
            model = AlertRule
            fields = ['id', 'alert_type', 'severity', 'is_active', 'name', 'description', 'last_triggered']


if AlertLog is not None:
    class AlertLogSerializer(serializers.ModelSerializer):
        class Meta:
            model = AlertLog
            fields = ['id', 'rule', 'triggered_at', 'message', 'details', 'is_resolved', 'resolved_at']
