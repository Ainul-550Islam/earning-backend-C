# serializers/base.py
from rest_framework import serializers
import logging

logger = logging.getLogger(__name__)


class BulletproofSerializer(serializers.Serializer):
    """Serializer that catches exceptions during to_representation"""
    def to_representation(self, instance):
        try:
            return super().to_representation(instance)
        except Exception as e:
            logger.error(f"Serialization error in {self.__class__.__name__}: {e}")
            return {}


class BaseModelSerializer(serializers.ModelSerializer):
    """Base ModelSerializer with common read-only fields"""
    class Meta:
        abstract = True
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        try:
            return super().to_representation(instance)
        except Exception as e:
            logger.error(f"Serialization error in {self.__class__.__name__}: {e}")
            return {'id': getattr(instance, 'pk', None)}
