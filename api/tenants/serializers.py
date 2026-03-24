from rest_framework import serializers
from .models import Tenant, TenantSettings, TenantBilling, TenantInvoice


class TenantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantSettings
        exclude = ['tenant', 'firebase_server_key']


class TenantBillingSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = TenantBilling
        fields = '__all__'

    def get_is_active(self, obj):
        return obj.is_active()


class TenantSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    settings = TenantSettingsSerializer(read_only=True)
    billing = TenantBillingSerializer(read_only=True)
    active_users = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id", "name", "slug", "domain", "admin_email",
            "primary_color", "secondary_color",
            "logo", "logo_url", "plan",
            "max_users", "is_active", "created_at",
            "settings", "billing", "active_users",
        ]
        read_only_fields = ["id", "slug", "created_at", "logo_url", "api_key"]
        extra_kwargs = {
            "api_key": {"write_only": True}
        }

    def get_logo_url(self, obj):
        request = self.context.get("request")
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None

    def get_active_users(self, obj):
        return obj.get_active_user_count()
