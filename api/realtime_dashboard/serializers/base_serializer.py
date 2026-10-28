"""
Base serializer for Real-time Dashboard Backend.
"""
from rest_framework import serializers


class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with common read-only timestamp fields.

    All model serializers in this app inherit from this class so that
    `created_at` and `updated_at` are always read-only and never need
    to be re-declared in each subclass.

    FIXED: removed `class Meta: abstract = True`. DRF's ModelSerializer
    does not recognise `abstract` as a Meta option - it has no effect
    whatsoever and existed here only as misleading dead configuration.
    DRF serializer inheritance is controlled purely by Python class
    inheritance; there is no DRF-level concept of "abstract serializer".
    """

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
