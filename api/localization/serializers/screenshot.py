# serializers/screenshot.py
from rest_framework import serializers


class TranslationScreenshotSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.SerializerMethodField()
    key_string = serializers.CharField(
        source='translation_key.key', read_only=True
    )

    def get_uploaded_by_email(self, obj):
        return getattr(obj.uploaded_by, 'email', None) if obj.uploaded_by else None

    class Meta:
        from ..models.content import TranslationScreenshot
        model = TranslationScreenshot
        fields = [
            'id', 'created_at', 'updated_at',
            'translation_key', 'key_string',
            'title', 'description',
            'image_url',
            'page_url', 'component',
            'region_x', 'region_y', 'region_w', 'region_h',
            'uploaded_by', 'uploaded_by_email',
            'tags',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'uploaded_by']
        extra_kwargs = {
            'translation_key': {'write_only': True},
            'image_data': {'write_only': True},
        }
