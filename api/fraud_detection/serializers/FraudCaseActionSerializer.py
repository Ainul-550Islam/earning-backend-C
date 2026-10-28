# =============================================================================
# fraud_detection/serializers/FraudCaseActionSerializer.py
# =============================================================================
from __future__ import annotations

from rest_framework import serializers

from api.fraud_detection.models import FraudCaseAction
from api.fraud_detection.choices import ActionType


class FraudCaseActionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudCaseAction
        fields = ['id', 'action_id', 'fraud_case', 'action_type', 'performed_by',
                  'note', 'is_completed', 'integrity_hash', 'created_at']
        read_only_fields = ['id', 'action_id', 'integrity_hash', 'created_at']


class FraudCaseActionListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudCaseAction
        fields = ['id', 'action_id', 'action_type', 'performed_by', 'is_completed', 'created_at']


class FraudCaseActionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudCaseAction
        fields = ['fraud_case', 'action_type', 'note']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['performed_by'] = request.user
        return FraudCaseAction.objects.create(**validated_data)


class FraudCaseActionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudCaseAction
        fields = ['note', 'is_completed']


class FraudCaseBulkActionSerializer(serializers.Serializer):
    case_ids    = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    action_type = serializers.ChoiceField(choices=ActionType.choices)
    note        = serializers.CharField(required=False, allow_blank=True)


class FraudCaseActionTimelineSerializer(serializers.ModelSerializer):
    performed_by_display = serializers.SerializerMethodField()

    class Meta:
        model  = FraudCaseAction
        fields = ['action_id', 'action_type', 'performed_by_display', 'note', 'is_completed', 'created_at']

    def get_performed_by_display(self, obj):
        return str(obj.performed_by) if obj.performed_by_id else 'System'


class FraudCaseActionStatisticsSerializer(serializers.Serializer):
    total_actions   = serializers.IntegerField()
    by_type         = serializers.DictField(child=serializers.IntegerField())
    completed_count = serializers.IntegerField()
    pending_count   = serializers.IntegerField()
