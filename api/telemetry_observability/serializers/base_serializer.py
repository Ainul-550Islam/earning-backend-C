"""
Base Serializer for Telemetry Observability.

All domain serializers inherit from BaseSerializer so that
created_at / updated_at are defined ONCE — never repeated per model.

DRY: import BaseSerializer in every serializer file.
"""
from rest_framework import serializers


class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with shared read-only timestamp fields.
    Inherit instead of serializers.ModelSerializer for all model serializers.
    """
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
