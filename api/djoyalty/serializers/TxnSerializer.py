# api/djoyalty/serializers/TxnSerializer.py
from rest_framework import serializers
from ..models.core import Txn


class TxnSerializer(serializers.ModelSerializer):
    type_label = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Txn
        fields = [
            'id', 'customer', 'customer_name', 'value', 'is_discount',
            'txn_type', 'source', 'reference_id', 'description',
            'currency', 'type_label', 'timestamp', 'created_at',
        ]
        read_only_fields = ['id', 'type_label', 'customer_name', 'created_at']

    def get_type_label(self, obj) -> str:
        return obj.type_label

    def get_customer_name(self, obj) -> str:
        if obj.customer:
            return f'{obj.customer.code} -- {obj.customer.full_name}'
        return 'Unknown'
