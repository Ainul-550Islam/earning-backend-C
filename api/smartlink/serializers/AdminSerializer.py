from rest_framework import serializers
from ..models import SmartLink
from .SmartLinkDetailSerializer import SmartLinkDetailSerializer


class AdminSmartLinkSerializer(SmartLinkDetailSerializer):
    """Extended serializer for admin — includes publisher details and all stats."""
    publisher_id = serializers.IntegerField(source='publisher.id', read_only=True)
    publisher_username = serializers.CharField(source='publisher.username', read_only=True)
    publisher_email = serializers.CharField(source='publisher.email', read_only=True)

    class Meta(SmartLinkDetailSerializer.Meta):
        fields = SmartLinkDetailSerializer.Meta.fields + [
            'publisher_id', 'publisher_email',
        ]
