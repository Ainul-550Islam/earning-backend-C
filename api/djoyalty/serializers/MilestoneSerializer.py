# api/djoyalty/serializers/MilestoneSerializer.py
from rest_framework import serializers
from ..models.engagement import Milestone, UserMilestone


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = [
            'id', 'name', 'description',
            'milestone_type', 'threshold',
            'points_reward', 'reward_badge',
            'is_repeatable', 'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class UserMilestoneSerializer(serializers.ModelSerializer):
    milestone_name = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = UserMilestone
        fields = [
            'id', 'customer', 'customer_code',
            'milestone', 'milestone_name',
            'points_awarded', 'achieved_at',
            'times_achieved', 'last_reward_at',
            'created_at',
        ]
        read_only_fields = ['id', 'customer_code', 'milestone_name', 'created_at']

    def get_milestone_name(self, obj) -> str:
        return obj.milestone.name if obj.milestone else ''

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def validate_threshold(self, value):
        from decimal import Decimal
        if Decimal(str(value)) <= 0:
            from rest_framework import serializers
            raise serializers.ValidationError('Milestone threshold must be greater than 0.')
        return value

    def validate_points_reward(self, value):
        from decimal import Decimal
        if Decimal(str(value)) < 0:
            from rest_framework import serializers
            raise serializers.ValidationError('Points reward cannot be negative.')
        return value
