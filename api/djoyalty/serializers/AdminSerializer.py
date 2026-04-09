# api/djoyalty/serializers/AdminSerializer.py
from rest_framework import serializers
from ..models.core import Customer

class AdminCustomerDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    points_balance = serializers.SerializerMethodField()
    lifetime_earned = serializers.SerializerMethodField()
    current_tier = serializers.SerializerMethodField()
    transaction_count = serializers.SerializerMethodField()
    badge_count = serializers.SerializerMethodField()
    streak_days = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ['id', 'code', 'full_name', 'email', 'phone', 'city', 'newsletter', 'is_active', 'created_at', 'points_balance', 'lifetime_earned', 'current_tier', 'transaction_count', 'badge_count', 'streak_days']

    def get_full_name(self, obj): return obj.full_name
    def get_points_balance(self, obj):
        lp = obj.loyalty_points.first()
        return str(lp.balance) if lp else '0'
    def get_lifetime_earned(self, obj):
        lp = obj.loyalty_points.first()
        return str(lp.lifetime_earned) if lp else '0'
    def get_current_tier(self, obj):
        ut = obj.current_tier
        return ut.tier.name if ut and ut.tier else 'bronze'
    def get_transaction_count(self, obj): return obj.transactions.count()
    def get_badge_count(self, obj): return obj.user_badges.count()
    def get_streak_days(self, obj):
        streak = obj.daily_streak.first()
        return streak.current_streak if streak else 0
