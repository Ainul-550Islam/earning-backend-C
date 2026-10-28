# api/djoyalty/serializers/AdminSerializer.py
from decimal import Decimal
from rest_framework import serializers
from ..models.core import Customer


class AdminCustomerDetailSerializer(serializers.ModelSerializer):
    """Full admin view of a customer -- all data।"""
    full_name = serializers.SerializerMethodField()
    points_balance = serializers.SerializerMethodField()
    lifetime_earned = serializers.SerializerMethodField()
    lifetime_redeemed = serializers.SerializerMethodField()
    lifetime_expired = serializers.SerializerMethodField()
    current_tier = serializers.SerializerMethodField()
    tier_details = serializers.SerializerMethodField()
    badges_count = serializers.SerializerMethodField()
    streak_current = serializers.SerializerMethodField()
    total_transactions = serializers.SerializerMethodField()
    total_spend = serializers.SerializerMethodField()
    active_vouchers = serializers.SerializerMethodField()
    pending_redemptions = serializers.SerializerMethodField()
    fraud_flags = serializers.SerializerMethodField()
    referral_count = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'code', 'loyalty_number',
            'firstname', 'lastname', 'full_name',
            'email', 'phone', 'city', 'country',
            'is_active', 'is_verified',
            'newsletter', 'sms_opt_in',
            'points_balance', 'lifetime_earned', 'lifetime_redeemed', 'lifetime_expired',
            'current_tier', 'tier_details',
            'badges_count', 'streak_current',
            'total_transactions', 'total_spend',
            'active_vouchers', 'pending_redemptions',
            'fraud_flags', 'referral_count',
            'metadata', 'notes',
            'created_at', 'updated_at', 'last_activity_at',
        ]
        read_only_fields = ['id', 'loyalty_number', 'created_at', 'updated_at']

    def get_full_name(self, obj) -> str:
        return obj.full_name

    def get_points_balance(self, obj) -> str:
        lp = obj.loyalty_points.first()
        return str(lp.balance if lp else Decimal('0'))

    def get_lifetime_earned(self, obj) -> str:
        lp = obj.loyalty_points.first()
        return str(lp.lifetime_earned if lp else Decimal('0'))

    def get_lifetime_redeemed(self, obj) -> str:
        lp = obj.loyalty_points.first()
        return str(lp.lifetime_redeemed if lp else Decimal('0'))

    def get_lifetime_expired(self, obj) -> str:
        lp = obj.loyalty_points.first()
        return str(lp.lifetime_expired if lp else Decimal('0'))

    def get_current_tier(self, obj) -> str:
        ut = obj.current_tier
        return ut.tier.name if ut and ut.tier else 'bronze'

    def get_tier_details(self, obj) -> dict | None:
        ut = obj.current_tier
        if ut and ut.tier:
            return {
                'name': ut.tier.name,
                'label': ut.tier.label,
                'color': ut.tier.color,
                'icon': ut.tier.icon,
                'earn_multiplier': str(ut.tier.earn_multiplier),
                'assigned_at': ut.assigned_at.isoformat() if ut.assigned_at else None,
            }
        return None

    def get_badges_count(self, obj) -> int:
        return obj.user_badges.count()

    def get_streak_current(self, obj) -> int:
        streak = obj.daily_streaks.filter(is_active=True).first()
        return streak.current_streak if streak else 0

    def get_total_transactions(self, obj) -> int:
        return obj.transactions.count()

    def get_total_spend(self, obj) -> str:
        from django.db.models import Sum
        result = obj.transactions.filter(value__gt=0).aggregate(s=Sum('value'))
        return str(result['s'] or Decimal('0'))

    def get_active_vouchers(self, obj) -> int:
        return obj.vouchers.filter(status='active').count()

    def get_pending_redemptions(self, obj) -> int:
        return obj.redemption_requests.filter(status='pending').count()

    def get_fraud_flags(self, obj) -> int:
        return obj.abuse_logs.filter(is_resolved=False).count()

    def get_referral_count(self, obj) -> int:
        return obj.referrals.count()
