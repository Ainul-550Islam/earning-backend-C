# serializers.py - Defensive & Bulletproof

from rest_framework import serializers
from .models import Customer, Txn, Event
from django.db.models import Sum, Count, Q 


class TxnSerializer(serializers.ModelSerializer):
    type_label = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Txn
        fields = ['id', 'timestamp', 'customer', 'customer_name', 'value', 'is_discount', 'type_label']
        read_only_fields = ['timestamp']

    def get_type_label(self, obj):
        # Null Object Pattern
        if obj.is_discount:
            return 'Discount'
        return 'Full Price'

    def get_customer_name(self, obj):
        if obj.customer:
            return str(obj.customer)
        return 'Unknown Customer'

    def validate_value(self, value):
        if value is None:
            raise serializers.ValidationError("Value cannot be null.")
        return value


class EventSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    is_anonymous = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ['id', 'timestamp', 'customer', 'customer_name', 'is_anonymous', 'action', 'description']
        read_only_fields = ['timestamp']

    def get_customer_name(self, obj):
        # Null Object Pattern - customer না থাকলে Anonymous
        if obj.customer:
            return str(obj.customer)
        return 'Anonymous'

    def get_is_anonymous(self, obj):
        return obj.customer is None

    def validate_action(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Action cannot be empty.")
        return value.strip()


class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    transaction_count = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'code', 'full_name', 'firstname', 'lastname',
            'email', 'phone', 'city', 'zip', 'newsletter',
            'transaction_count', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_full_name(self, obj):
        # Null Object Pattern
        name = ' '.join(filter(None, [obj.firstname, obj.lastname]))
        return name or 'Unnamed Customer'

    def get_transaction_count(self, obj):
        return getattr(obj, 'transaction_count', obj.transactions.count())

    def validate_code(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Code cannot be empty.")
        return value.strip().upper()

    def validate_email(self, value):
        if value and '@' not in value:
            raise serializers.ValidationError("Enter a valid email address.")
        return value


class CustomerDetailSerializer(CustomerSerializer):
    """Detail view - transactions ও events সহ"""
    transactions = TxnSerializer(many=True, read_only=True)
    events = EventSerializer(many=True, read_only=True)
    total_spent = serializers.SerializerMethodField()
    discount_count = serializers.SerializerMethodField()

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + [
            'street', 'note', 'total_spent',
            'discount_count', 'transactions', 'events'
        ]

    def get_total_spent(self, obj):
        total = obj.transactions.aggregate(s=Sum('value'))['s']
        return float(total) if total is not None else 0.0

    def get_discount_count(self, obj):
        return obj.transactions.filter(is_discount=True).count()