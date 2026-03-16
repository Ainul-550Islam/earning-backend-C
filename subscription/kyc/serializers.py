from rest_framework import serializers
from .models import KYC, KYCVerificationLog

class KYCListSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = KYC
        fields = ['id', 'user', 'user_name', 'user_email', 'full_name', 'phone_number', 'status', 'document_type', 'created_at', 'risk_score']

class KYCDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYC
        fields = '__all__'

class KYCVerificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCVerificationLog
        fields = ['id', 'action', 'details', 'created_at']
