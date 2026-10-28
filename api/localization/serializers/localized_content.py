# serializers/localized_content.py
from rest_framework import serializers


class LocalizedContentSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)

    class Meta:
        from ..models.content import LocalizedContent
        model = LocalizedContent
        fields = [
            'id', 'created_at', 'updated_at',
            'content_type', 'object_id',
            'language', 'language_code',
            'field_name', 'value',
            'is_approved', 'approved_by', 'approved_at',
            'is_machine_translated', 'review_status',
            'word_count', 'character_count',
            'source_locale', 'translation_note',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'word_count', 'character_count',
            'approved_by', 'approved_at',
        ]
        extra_kwargs = {
            'language': {'write_only': True},
            'content_type': {'write_only': True},
        }


class LocalizedSEOSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)

    class Meta:
        from ..models.content import LocalizedSEO
        model = LocalizedSEO
        fields = [
            'id', 'created_at', 'updated_at',
            'content_type', 'object_id',
            'language', 'language_code',
            'meta_title', 'meta_description', 'meta_keywords',
            'canonical_url', 'hreflang_tags',
            'og_title', 'og_description', 'og_image_url',
            'twitter_title', 'twitter_description', 'twitter_image_url',
            'structured_data',
            'is_indexable', 'is_followable', 'custom_robots',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'language': {'write_only': True},
            'content_type': {'write_only': True},
        }


class LocalizedImageSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True, default=None)
    country_code = serializers.CharField(source='country.code', read_only=True, default=None)

    class Meta:
        from ..models.content import LocalizedImage
        model = LocalizedImage
        fields = [
            'id', 'created_at', 'updated_at',
            'content_type', 'object_id',
            'language', 'language_code',
            'country', 'country_code',
            'image_url', 'alt_text', 'caption',
            'image_type', 'width', 'height',
            'is_default', 'is_approved', 'sort_order',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'language': {'write_only': True, 'required': False},
            'country': {'write_only': True, 'required': False},
            'content_type': {'write_only': True},
        }


class ContentLocaleMappingSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)

    class Meta:
        from ..models.content import ContentLocaleMapping
        model = ContentLocaleMapping
        fields = [
            'id', 'created_at', 'updated_at',
            'content_type', 'object_id',
            'language', 'language_code',
            'is_available', 'is_primary_locale',
            'publish_date', 'unpublish_date',
            'redirect_to_language', 'override_url', 'notes',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'language': {'write_only': True},
            'content_type': {'write_only': True},
            'redirect_to_language': {'required': False},
        }


class TranslationRequestSerializer(serializers.ModelSerializer):
    source_lang = serializers.CharField(source='source_language.code', read_only=True)
    requested_by_email = serializers.SerializerMethodField()
    assigned_to_email = serializers.SerializerMethodField()

    class Meta:
        from ..models.content import TranslationRequest
        model = TranslationRequest
        fields = [
            'id', 'created_at', 'updated_at',
            'title', 'description',
            'source_language', 'source_lang',
            'target_languages',
            'status', 'priority',
            'requested_by', 'requested_by_email',
            'assigned_to', 'assigned_to_email',
            'due_date', 'completed_at',
            'word_count', 'estimated_cost', 'actual_cost',
            'style_notes', 'tags',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'requested_by', 'completed_at',
        ]
        extra_kwargs = {
            'source_language': {'write_only': True},
            'assigned_to': {'required': False},
        }

    def get_requested_by_email(self, obj):
        return getattr(obj.requested_by, 'email', None) if obj.requested_by else None

    def get_assigned_to_email(self, obj):
        return getattr(obj.assigned_to, 'email', None) if obj.assigned_to else None
