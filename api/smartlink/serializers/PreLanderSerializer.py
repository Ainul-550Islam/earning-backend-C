from rest_framework import serializers
from ..models import PreLander


class PreLanderSerializer(serializers.ModelSerializer):
    pass_through_rate = serializers.SerializerMethodField()

    class Meta:
        model = PreLander
        fields = [
            'id', 'name', 'url', 'type', 'is_active',
            'pass_through_params', 'views', 'pass_through_count',
            'pass_through_rate', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'views', 'pass_through_count', 'created_at', 'updated_at']

    def get_pass_through_rate(self, obj):
        return obj.pass_through_rate
