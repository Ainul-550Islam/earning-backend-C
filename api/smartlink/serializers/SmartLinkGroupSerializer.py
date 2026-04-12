from rest_framework import serializers
from ..models import SmartLinkGroup


class SmartLinkGroupSerializer(serializers.ModelSerializer):
    smartlink_count = serializers.SerializerMethodField()

    class Meta:
        model = SmartLinkGroup
        fields = ['id', 'name', 'description', 'color', 'is_active', 'smartlink_count', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_smartlink_count(self, obj):
        return obj.smartlinks.filter(is_archived=False).count()
