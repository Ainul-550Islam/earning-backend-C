"""
Rollout Rule serializer for Feature Flags & A/B Testing.
"""
from rest_framework import serializers

from ..models.rollout_rule import RolloutRule
from .base_serializer import BaseSerializer


class RolloutRuleSerializer(BaseSerializer):
    """
    Serializer for RolloutRule model.
    """
    
    flag_name = serializers.CharField(source='flag.name', read_only=True)
    
    class Meta:
        model = RolloutRule
        fields = [
            'id', 'flag', 'flag_name', 'rule_type', 'field',
            'operator', 'value', 'priority', 'is_active',
            'description', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RolloutRuleListSerializer(BaseSerializer):
    """
    List serializer for RolloutRule model.
    """
    
    flag_name = serializers.CharField(source='flag.name', read_only=True)
    
    class Meta:
        model = RolloutRule
        fields = [
            'id', 'flag', 'flag_name', 'rule_type', 'field',
            'operator', 'priority', 'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']
