from rest_framework import serializers
from .models import Tenant

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = "__all__"
        read_only_fields = ["id", "api_key", "created_at", "updated_at"]
