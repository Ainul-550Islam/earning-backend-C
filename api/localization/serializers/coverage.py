# serializers/coverage.py
from rest_framework import serializers

class TranslationCoverageSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    language_name = serializers.CharField(source='language.name', read_only=True)
    class Meta:
        from ..models.analytics import TranslationCoverage
        model = TranslationCoverage
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
