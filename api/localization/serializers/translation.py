# serializers/translation.py
from rest_framework import serializers
from django.utils import timezone

class TranslationKeySerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import TranslationKey
        model = TranslationKey
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class TranslationSerializer(serializers.ModelSerializer):
    key_string = serializers.CharField(source='key.key', read_only=True)
    language_code = serializers.CharField(source='language.code', read_only=True)
    class Meta:
        from ..models.core import Translation
        model = Translation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'word_count', 'char_count', 'edit_count']
    def validate(self, attrs):
        key = attrs.get('key')
        language = attrs.get('language')
        value = attrs.get('value')
        if key and key.max_length and value and len(value) > key.max_length:
            raise serializers.ValidationError({'value': f'Value exceeds max length of {key.max_length}'})
        return attrs
    def create(self, validated_data):
        language = validated_data.get('language')
        if language and language.is_default:
            validated_data['is_approved'] = True
            validated_data['approved_at'] = timezone.now()
        return super().create(validated_data)
