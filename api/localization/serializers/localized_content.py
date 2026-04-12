# serializers/localized_content.py
from rest_framework import serializers

class LocalizedContentSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    class Meta:
        from ..models.content import LocalizedContent
        model = LocalizedContent
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'word_count', 'character_count']

class LocalizedSEOSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    class Meta:
        from ..models.content import LocalizedSEO
        model = LocalizedSEO
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class LocalizedImageSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.content import LocalizedImage
        model = LocalizedImage
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class ContentLocaleMappingSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.content import ContentLocaleMapping
        model = ContentLocaleMapping
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class TranslationRequestSerializer(serializers.ModelSerializer):
    source_lang = serializers.CharField(source='source_language.code', read_only=True)
    requested_by_email = serializers.CharField(source='requested_by.email', read_only=True)
    assigned_to_email = serializers.CharField(source='assigned_to.email', read_only=True)
    class Meta:
        from ..models.content import TranslationRequest
        model = TranslationRequest
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'requested_by']
