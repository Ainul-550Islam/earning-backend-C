# api/payment_gateways/schedules/serializers.py
from rest_framework import serializers
from decimal import Decimal
from .models import PaymentSchedule, ScheduledPayout, EarlyPaymentRequest

class PaymentScheduleSerializer(serializers.ModelSerializer):
    schedule_type_display = serializers.CharField(source='get_schedule_type_display', read_only=True)
    payment_method_display= serializers.CharField(source='get_payment_method_display', read_only=True)
    user_email            = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model  = PaymentSchedule
        fields = ['id','schedule_type','schedule_type_display','status','payment_method',
                  'payment_method_display','payment_account','payment_currency',
                  'minimum_payout','next_payout_date','last_payout_date',
                  'last_payout_amount','user_email','notes']
        read_only_fields = ['next_payout_date','last_payout_date','last_payout_amount']

class ScheduledPayoutSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    class Meta:
        model  = ScheduledPayout
        fields = ['id','amount','fee','net_amount','currency','payment_method',
                  'payment_account','status','period_start','period_end',
                  'scheduled_date','processed_at','error_message','user_email']

class EarlyPaymentRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    class Meta:
        model  = EarlyPaymentRequest
        fields = ['id','amount','early_fee','net_amount','payment_method',
                  'payment_account','status','reason','processed_at','admin_notes','user_email']
        read_only_fields = ['early_fee','net_amount','status','processed_at']

class RequestEarlyPaymentSerializer(serializers.Serializer):
    amount         = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1'))
    payment_method = serializers.ChoiceField(choices=[m[0] for m in EarlyPaymentRequest._meta.get_field('payment_method').choices])
    payment_account= serializers.CharField(max_length=200)
    reason         = serializers.CharField(required=False, allow_blank=True)
