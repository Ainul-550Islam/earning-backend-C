"""
Base serializer for Feature Flags & A/B Testing.
"""
from rest_framework import serializers


class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with common fields.

    FIX: this previously extended `serializers.Serializer`, but every
    subclass declares `class Meta: model = ...` and relies on DRF
    auto-generating fields from the model — that behavior belongs to
    `ModelSerializer`, not the plain `Serializer`. With the old base class,
    `Meta.model`/`Meta.fields` were silently ignored, so every serializer in
    this app had only the two explicitly declared fields and no working
    create()/update() — every POST/PUT through these serializers would have
    either errored or silently dropped all submitted data.
    """

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        abstract = True
