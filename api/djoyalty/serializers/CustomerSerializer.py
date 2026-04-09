# api/djoyalty/serializers/CustomerSerializer.py
from rest_framework import serializers
from django.db.models import Sum
from ..models.core import Customer
from .TxnSerializer import TxnSerializer
from .EventSerializer import EventSerializer

class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    transaction_count = serializers.SerializerMethodField()
    points_balance = serializers.SerializerMethodField()
    current_tier = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'code', 'full_name', 'firstname', 'lastname',
            'email', 'phone', 'city', 'zip', 'newsletter',
            'transaction_count', 'points_balance', 'current_tier', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_full_name(self, obj):
        return ' '.join(filter(None, [obj.firstname, obj.lastname])) or 'Unnamed Customer'

    def get_transaction_count(self, obj):
        return getattr(obj, 'transaction_count', obj.transactions.count())

    def get_points_balance(self, obj):
        lp = obj.loyalty_points.first()
        return str(lp.balance) if lp else '0'

    def get_current_tier(self, obj):
        ut = obj.current_tier
        return ut.tier.name if ut and ut.tier else 'bronze'

    def validate_code(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Code cannot be empty.')
        return value.strip().upper()

    def validate_email(self, value):
        if value and '@' not in value:
            raise serializers.ValidationError('Enter a valid email address.')
        return value


class CustomerDetailSerializer(CustomerSerializer):
    transactions = TxnSerializer(many=True, read_only=True)
    events = EventSerializer(many=True, read_only=True)
    total_spent = serializers.SerializerMethodField()
    discount_count = serializers.SerializerMethodField()
    lifetime_earned = serializers.SerializerMethodField()
    lifetime_redeemed = serializers.SerializerMethodField()

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + [
            'street', 'note', 'total_spent', 'discount_count',
            'lifetime_earned', 'lifetime_redeemed', 'transactions', 'events',
        ]

    def get_total_spent(self, obj):
        total = obj.transactions.aggregate(s=Sum('value'))['s']
        return float(total) if total is not None else 0.0

    def get_discount_count(self, obj):
        return obj.transactions.filter(is_discount=True).count()

    def get_lifetime_earned(self, obj):
        lp = obj.loyalty_points.first()
        return str(lp.lifetime_earned) if lp else '0'

    def get_lifetime_redeemed(self, obj):
        lp = obj.loyalty_points.first()
        return str(lp.lifetime_redeemed) if lp else '0'
