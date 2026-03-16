# kyc/serializers.py  ── 100% COMPLETE
from rest_framework import serializers
from .models import KYC, KYCVerificationLog


class KYCSerializer(serializers.ModelSerializer):
    """User নিজের KYC দেখার জন্য"""
    class Meta:
        model = KYC
        fields = [
            'id', 'user', 'full_name', 'date_of_birth', 'phone_number',
            'payment_number', 'payment_method', 'address_line', 'city', 'country',
            'status', 'is_name_verified', 'is_phone_verified', 'is_payment_verified',
            'document_type', 'document_number', 'document_front', 'document_back',
            'selfie_photo', 'is_face_verified', 'reviewed_at', 'rejection_reason',
            'risk_score', 'is_duplicate', 'admin_notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'reviewed_at', 'created_at', 'updated_at', 'risk_score']


class KYCAdminSerializer(serializers.ModelSerializer):
    """Admin এর জন্য — সব field দেখা যাবে"""
    username = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = KYC
        fields = [
            'id', 'user', 'username', 'email',
            'full_name', 'date_of_birth', 'phone_number',
            'payment_number', 'payment_method', 'address_line', 'city', 'country',
            'status', 'is_name_verified', 'is_phone_verified', 'is_payment_verified',
            'document_type', 'document_number', 'document_front', 'document_back',
            'selfie_photo', 'is_face_verified',
            'reviewed_at', 'reviewed_by',
            'rejection_reason', 'admin_notes',
            'risk_score', 'risk_factors', 'is_duplicate',
            'created_at', 'updated_at',
        ]

    def get_username(self, obj):
        return obj.user.username if obj.user else None

    def get_email(self, obj):
        return obj.user.email if obj.user else None


class KYCVerificationLogSerializer(serializers.ModelSerializer):
    performed_by__username = serializers.SerializerMethodField()

    class Meta:
        model = KYCVerificationLog
        fields = ['id', 'action', 'details', 'created_at', 'performed_by__username']

    def get_performed_by__username(self, obj):
        return obj.performed_by.username if obj.performed_by else None