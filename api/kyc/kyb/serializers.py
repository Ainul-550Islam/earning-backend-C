# kyc/kyb/serializers.py  ── WORLD #1
from rest_framework import serializers
from .models import BusinessVerification, UBODeclaration, BusinessDirector


class UBODeclarationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UBODeclaration
        fields = ['id', 'full_name', 'nationality', 'dob', 'ownership_percentage',
                  'is_politically_exposed', 'address', 'is_verified', 'verified_at', 'created_at']
        read_only_fields = ['id', 'is_verified', 'verified_at', 'created_at']


class BusinessDirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BusinessDirector
        fields = ['id', 'full_name', 'designation', 'nationality', 'nid_number',
                  'is_verified', 'created_at']
        read_only_fields = ['id', 'is_verified', 'created_at']


class BusinessVerificationSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    ubos     = UBODeclarationSerializer(many=True, read_only=True, source='ubo_declarations')
    directors = BusinessDirectorSerializer(many=True, read_only=True)

    class Meta:
        model  = BusinessVerification
        fields = [
            'id', 'username', 'business_name', 'entity_type',
            'trade_license_no', 'tin_number', 'bin_number', 'registration_no',
            'incorporation_date', 'country_of_incorporation',
            'registered_address', 'website', 'phone', 'email',
            'status', 'risk_score', 'risk_level',
            'trade_license_doc', 'incorporation_doc', 'moa_doc',
            'rejection_reason', 'admin_notes',
            'verified_at', 'expires_at', 'created_at', 'updated_at',
            'ubos', 'directors',
        ]
        read_only_fields = ['id', 'status', 'risk_score', 'risk_level',
                            'verified_at', 'expires_at', 'created_at', 'updated_at']

    def get_username(self, obj):
        return obj.user.username if obj.user else None
