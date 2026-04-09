# api/djoyalty/serializers/MilestoneSerializer.py
from rest_framework import serializers
from ..models.engagement import Milestone, UserMilestone

class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ['id', 'name', 'description', 'milestone_type', 'threshold', 'points_reward', 'is_active', 'created_at']

class UserMilestoneSerializer(serializers.ModelSerializer):
    milestone_name = serializers.SerializerMethodField()
    class Meta:
        model = UserMilestone
        fields = ['id', 'customer', 'milestone', 'milestone_name', 'points_awarded', 'reached_at']
    def get_milestone_name(self, obj): return obj.milestone.name if obj.milestone else ''
