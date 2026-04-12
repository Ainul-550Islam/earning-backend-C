# serializers/missing_translation.py
from rest_framework import serializers

class MissingTranslationSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    class Meta:
        from ..models.translation import MissingTranslation
        model = MissingTranslation
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'occurrence_count', 'last_seen_at']
