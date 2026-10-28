# =============================================================================
# fraud_detection/serializers/FraudCaseSerializer.py
# =============================================================================
from __future__ import annotations

from rest_framework import serializers

from api.fraud_detection.models import FraudCase, FraudCaseEvidence, FraudCaseAction
from api.fraud_detection.choices import CaseStatus, CasePriority, EvidenceType, ActionType


class FraudCaseEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudCaseEvidence
        fields = ['evidence_id', 'evidence_type', 'data', 'added_by', 'created_at']
        read_only_fields = ['evidence_id', 'created_at']


class FraudCaseSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    assigned_to_display = serializers.SerializerMethodField()

    class Meta:
        model  = FraudCase
        fields = [
            'id', 'case_number', 'user', 'user_display', 'title', 'description',
            'status', 'priority', 'risk_score', 'is_high_priority', 'escalation_level',
            'metadata', 'opened_at', 'resolved_at', 'assigned_to', 'assigned_to_display',
            'resolved_by', 'resolution_notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'case_number', 'created_at', 'updated_at']

    def get_user_display(self, obj):
        return str(obj.user) if obj.user_id else None

    def get_assigned_to_display(self, obj):
        return str(obj.assigned_to) if obj.assigned_to_id else None


class FraudCaseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    class Meta:
        model  = FraudCase
        fields = [
            'id', 'case_number', 'user', 'title', 'status', 'priority',
            'risk_score', 'is_high_priority', 'opened_at', 'assigned_to',
        ]


class FraudCaseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudCase
        fields = ['user', 'title', 'description', 'priority', 'metadata']

    def create(self, validated_data):
        return FraudCase.objects.create(**validated_data)


class FraudCaseUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudCase
        fields = ['title', 'description', 'priority', 'assigned_to', 'metadata', 'is_high_priority']


class FraudCaseStatusUpdateSerializer(serializers.Serializer):
    status           = serializers.ChoiceField(choices=CaseStatus.choices)
    resolution_notes = serializers.CharField(required=False, allow_blank=True)


class FraudCaseBulkUpdateSerializer(serializers.Serializer):
    ids              = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    status           = serializers.ChoiceField(choices=CaseStatus.choices, required=False)
    priority         = serializers.ChoiceField(choices=CasePriority.choices, required=False)
    assigned_to      = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        if not any(k in data for k in ('status', 'priority', 'assigned_to')):
            raise serializers.ValidationError('At least one of status, priority, or assigned_to must be provided.')
        return data


class FraudCaseActionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudCaseAction
        fields = ['action_id', 'action_type', 'performed_by', 'note', 'is_completed', 'created_at']
        read_only_fields = ['action_id', 'created_at']
