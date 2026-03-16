from rest_framework import serializers


class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with common configurations.
    """
    created_at = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    modified_at = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        abstract = True