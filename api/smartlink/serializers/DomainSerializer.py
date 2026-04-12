from rest_framework import serializers
from ..models.publisher import PublisherDomain
from ..constants import DOMAIN_DNS_TXT_PREFIX


class DomainSerializer(serializers.ModelSerializer):
    dns_txt_record = serializers.SerializerMethodField()
    dns_txt_host = serializers.SerializerMethodField()

    class Meta:
        model = PublisherDomain
        fields = [
            'id', 'domain', 'verification_status', 'verification_token',
            'is_verified', 'is_active', 'is_primary',
            'ssl_enabled', 'ssl_expires_at',
            'verified_at', 'last_checked_at',
            'dns_txt_record', 'dns_txt_host',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'verification_status', 'verification_token',
            'is_verified', 'ssl_enabled', 'ssl_expires_at',
            'verified_at', 'last_checked_at', 'created_at', 'updated_at',
        ]

    def get_dns_txt_record(self, obj):
        return obj.dns_txt_record

    def get_dns_txt_host(self, obj):
        return f"_smartlink-verify.{obj.domain}"

    def validate_domain(self, value):
        from ..validators import validate_custom_domain
        validate_custom_domain(value)
        return value.lower().strip()
