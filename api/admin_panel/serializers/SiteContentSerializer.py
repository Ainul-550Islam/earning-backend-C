# api/admin_panel/serializers/SiteContentSerializer.py
"""SiteContent serializer — migrated from serializers.py, all logic kept."""
from rest_framework import serializers
from ..models.core import SiteContent


class SiteContentSerializer(serializers.ModelSerializer):
    content_type_display = serializers.CharField(
        source='get_content_type_display', read_only=True
    )
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = SiteContent
        fields = [
            'id', 'identifier', 'title', 'content', 'content_type',
            'content_type_display', 'is_active', 'language',
            'meta_title', 'meta_description', 'meta_keywords',
            'order', 'created_at', 'updated_at', 'is_current',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_current(self, obj) -> bool:
        return obj.is_active

    def validate_identifier(self, value):
        if value:
            import re
            if not re.match(r'^[a-z0-9_-]+$', value):
                raise serializers.ValidationError(
                    'Identifier must be lowercase alphanumeric, hyphens, or underscores only.'
                )
        return value

    def validate(self, data):
        # Ensure unique_together ['identifier', 'language'] on update
        identifier = data.get('identifier', getattr(self.instance, 'identifier', None))
        language = data.get('language', getattr(self.instance, 'language', 'en'))
        qs = SiteContent.objects.filter(identifier=identifier, language=language)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'identifier': f'SiteContent with identifier="{identifier}" and language="{language}" already exists.'}
            )
        return data