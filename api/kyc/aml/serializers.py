# kyc/aml/serializers.py  ── WORLD #1
from rest_framework import serializers
from .models import PEPSanctionsScreening, SanctionsList, PEPDatabase, AMLAlert


class PEPSanctionsScreeningSerializer(serializers.ModelSerializer):
    reviewed_by_username = serializers.SerializerMethodField()
    is_high_risk         = serializers.BooleanField(read_only=True)
    requires_edd         = serializers.BooleanField(read_only=True)

    class Meta:
        model  = PEPSanctionsScreening
        fields = [
            'id', 'kyc', 'provider', 'status', 'reference_id',
            'screened_name', 'screened_dob', 'screened_country',
            'is_pep', 'is_sanctioned', 'is_adverse_media',
            'match_count', 'match_score', 'matches',
            'review_note', 'reviewed_by_username', 'reviewed_at',
            'is_high_risk', 'requires_edd',
            'screened_at', 'updated_at', 'next_review_at',
        ]
        read_only_fields = ['id', 'screened_at', 'updated_at']

    def get_reviewed_by_username(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None


class SanctionsListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SanctionsList
        fields = ['id', 'source', 'list_name', 'entry_name', 'aliases',
                  'entity_type', 'is_active', 'listed_date', 'external_id', 'last_updated']


class PEPDatabaseSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PEPDatabase
        fields = ['id', 'full_name', 'aliases', 'category', 'country',
                  'position', 'party', 'is_current', 'source', 'last_updated']


class AMLAlertSerializer(serializers.ModelSerializer):
    username             = serializers.SerializerMethodField()
    assigned_to_username = serializers.SerializerMethodField()

    class Meta:
        model  = AMLAlert
        fields = [
            'id', 'alert_type', 'severity', 'status',
            'description', 'evidence', 'username',
            'assigned_to_username', 'resolution_note',
            'sar_filed', 'sar_reference', 'created_at', 'resolved_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_username(self, obj):
        return obj.user.username if obj.user else None

    def get_assigned_to_username(self, obj):
        return obj.assigned_to.username if obj.assigned_to else None
