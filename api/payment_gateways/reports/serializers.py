# api/payment_gateways/reports/serializers.py
from rest_framework import serializers
from .models import ReconciliationReport

class ReconciliationReportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReconciliationReport
        fields = ['id','report_date','data','created_at']
        read_only_fields = ['id','created_at']

class DailyReportRequestSerializer(serializers.Serializer):
    date = serializers.DateField(required=False, help_text='YYYY-MM-DD (default: yesterday)')

class MonthlyReportRequestSerializer(serializers.Serializer):
    year  = serializers.IntegerField(required=False, min_value=2020, max_value=2099)
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)

class GatewayReportRequestSerializer(serializers.Serializer):
    gateway = serializers.ChoiceField(choices=[
        'bkash','nagad','sslcommerz','amarpay','upay','shurjopay','stripe','paypal'
    ])
    days = serializers.IntegerField(required=False, default=30, min_value=1, max_value=365)

class ExportRequestSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to   = serializers.DateField(required=False)
    gateway   = serializers.ChoiceField(
        choices=['bkash','nagad','sslcommerz','amarpay','upay','shurjopay','stripe','paypal'],
        required=False
    )
    status    = serializers.ChoiceField(
        choices=['pending','processing','completed','failed','cancelled'],
        required=False
    )
