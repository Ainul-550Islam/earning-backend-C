from rest_framework import serializers
from .models import Tenant

class TenantSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id", "name", "slug", "domain",
            "primary_color", "secondary_color",
            "logo", "logo_url", "plan",
            "max_users", "is_active", "created_at"
        ]
        read_only_fields = ["id", "slug", "created_at", "logo_url"]
        extra_kwargs = {
            "api_key": {"write_only": True}
        }

    def get_logo_url(self, obj):
        request = self.context.get("request")
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None
