from rest_framework import serializers
from ..models.publisher import PublisherSmartLink
from .SmartLinkSerializer import SmartLinkSerializer


class PublisherSmartLinkSerializer(serializers.ModelSerializer):
    smartlink_detail = SmartLinkSerializer(source='smartlink', read_only=True)
    publisher_username = serializers.CharField(source='publisher.username', read_only=True)

    class Meta:
        model = PublisherSmartLink
        fields = [
            'id', 'publisher', 'publisher_username',
            'smartlink', 'smartlink_detail',
            'is_active', 'can_edit_targeting', 'can_edit_pool',
            'notes', 'assigned_at', 'updated_at',
        ]
        read_only_fields = ['id', 'assigned_at', 'updated_at', 'publisher_username']
