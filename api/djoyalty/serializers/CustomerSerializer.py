# api/djoyalty/serializers/CustomerSerializer.py
"""
Customer serializers।
CustomerSerializer -- list/create
CustomerDetailSerializer -- retrieve (with full stats)
"""
from decimal import Decimal
from rest_framework import serializers
from ..models.core import Customer
from ..validators import validate_customer_code


class CustomerSerializer(serializers.ModelSerializer):
    """Customer list & create serializer।"""
    full_name = serializers.SerializerMethodField()
    points_balance = serializers.SerializerMethodField()
    # Override 'code' field: strip model-level validators so validate_code() can
    # uppercase the value BEFORE regex validation runs (field validators run first in DRF)
    code = serializers.CharField(
        max_length=50, required=False,
        help_text='Customer unique code -- will be uppercased automatically.',
    )
    current_tier = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'code', 'loyalty_number', 'firstname', 'lastname', 'full_name',
            'email', 'phone', 'city', 'country', 'date_of_birth', 'gender',
            'newsletter', 'sms_opt_in', 'push_opt_in',
            'is_active', 'is_verified',
            'points_balance', 'current_tier',
            'referral_code',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'loyalty_number', 'full_name', 'points_balance', 'current_tier', 'created_at', 'updated_at']

    def get_full_name(self, obj) -> str:
        return obj.full_name

    def get_points_balance(self, obj) -> str:
        from decimal import Decimal
        val = Decimal(str(obj.points_balance)).normalize()
        # '{:f}' avoids scientific notation (2.5E+2 -> 250)
        return '{:f}'.format(val)

    def get_current_tier(self, obj) -> str | None:
        ut = obj.current_tier
        if ut and ut.tier:
            return ut.tier.name
        return None

    def validate_code(self, value):
        if value:
            value = value.strip().upper()
            validate_customer_code(value)
        return value

    def validate_email(self, value):
        if value:
            value = value.strip().lower()
            if Customer.objects.filter(email=value).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError('A customer with this email already exists.')
        return value


class CustomerDetailSerializer(CustomerSerializer):
    """
    Customer detail serializer -- includes tier, badges, stats।
    """
    tier_details = serializers.SerializerMethodField()
    badges_count = serializers.SerializerMethodField()
    streak_days = serializers.SerializerMethodField()
    lifetime_earned = serializers.SerializerMethodField()
    lifetime_redeemed = serializers.SerializerMethodField()
    total_transactions = serializers.SerializerMethodField()

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + [
            'tier_details', 'badges_count', 'streak_days',
            'lifetime_earned', 'lifetime_redeemed', 'total_transactions',
            'metadata', 'notes',
        ]

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

    def get_streak_days(self, obj) -> int:
        streak = obj.daily_streaks.filter(is_active=True).first()
        return streak.current_streak if streak else 0

    def get_lifetime_earned(self, obj) -> str:
        lp = obj.loyalty_points.first()
        return str(lp.lifetime_earned if lp else Decimal('0'))

    def get_lifetime_redeemed(self, obj) -> str:
        lp = obj.loyalty_points.first()
        return str(lp.lifetime_redeemed if lp else Decimal('0'))

    def get_total_transactions(self, obj) -> int:
        return obj.transactions.count()
