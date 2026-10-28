# api/cms/serializers_new/WorkflowSerializer.py
"""
Serializers for Workflow Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.workflow import WorkflowState, WorkflowTransition, WorkflowRule

User = get_user_model()


class WorkflowRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowRule
        fields = [
            'id', 'content_type', 'requires_approval', 'approver_group',
            'auto_publish', 'notify_on_submit', 'notify_on_approve',
            'notify_on_reject', 'is_active',
        ]
        read_only_fields = ['id']


class WorkflowTransitionSerializer(serializers.ModelSerializer):
    transitioned_by_display = serializers.StringRelatedField(source='transitioned_by', read_only=True)

    class Meta:
        model = WorkflowTransition
        fields = [
            'id', 'workflow_state', 'from_state', 'to_state',
            'transitioned_by', 'transitioned_by_display', 'note', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class WorkflowStateSerializer(serializers.ModelSerializer):
    transitions = WorkflowTransitionSerializer(many=True, read_only=True)
    assigned_to_display = serializers.StringRelatedField(source='assigned_to', read_only=True)
    created_by_display = serializers.StringRelatedField(source='created_by', read_only=True)

    class Meta:
        model = WorkflowState
        fields = [
            'uuid', 'content_type', 'object_id', 'state',
            'assigned_to', 'assigned_to_display',
            'created_by', 'created_by_display',
            'note', 'due_date', 'transitions',
        ]
        read_only_fields = ['uuid']

    def validate(self, data):
        valid_states = ['draft', 'review', 'approved', 'published', 'rejected', 'archived']
        if data.get('state') and data['state'] not in valid_states:
            raise serializers.ValidationError(
                {"state": f"state must be one of: {', '.join(valid_states)}"}
            )
        return data
