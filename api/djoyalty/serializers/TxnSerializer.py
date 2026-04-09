# api/djoyalty/serializers/TxnSerializer.py
from rest_framework import serializers
from ..models.core import Txn

class TxnSerializer(serializers.ModelSerializer):
    type_label = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Txn
        fields = ['id', 'timestamp', 'customer', 'customer_name', 'value', 'is_discount', 'type_label', 'reference']
        read_only_fields = ['timestamp']

    def get_type_label(self, obj):
        return 'Discount' if obj.is_discount else 'Full Price'

    def get_customer_name(self, obj):
        return str(obj.customer) if obj.customer else 'Unknown Customer'

    def validate_value(self, value):
        if value is None:
            raise serializers.ValidationError('Value cannot be null.')
        return value
