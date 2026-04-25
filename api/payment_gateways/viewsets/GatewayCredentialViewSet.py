# viewsets/GatewayCredentialViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from core.views import BaseViewSet
from api.payment_gateways.models.gateway_config import GatewayCredential, GatewayWebhookConfig
from rest_framework import serializers


class GatewayCredentialSerializer(serializers.ModelSerializer):
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)
    class Meta:
        model  = GatewayCredential
        fields = ['id','gateway_name','label','is_test_mode','is_active','is_verified',
                  'expires_at','last_verified','extra_fields','created_at']
        # Sensitive fields excluded from response
        extra_kwargs = {
            'api_key':      {'write_only': True},
            'api_secret':   {'write_only': True},
            'webhook_secret':{'write_only': True},
        }


class GatewayCredentialViewSet(BaseViewSet):
    """Admin: manage per-gateway API credentials."""
    queryset           = GatewayCredential.objects.all().order_by('gateway__name')
    serializer_class   = GatewayCredentialSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify credential by making a test API call."""
        cred    = self.get_object()
        from django.utils import timezone
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        result  = GatewayHealthService().check_single(cred.gateway.name)
        if result['status'] == 'healthy':
            cred.is_verified  = True
            cred.last_verified= timezone.now()
            cred.save(update_fields=['is_verified', 'last_verified'])
        return self.success_response(data=result, message=f'Credential verification: {result["status"]}')

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """Rotate API credentials (deactivate old, create new)."""
        old_cred = self.get_object()
        new_key  = request.data.get('api_key', '')
        new_secret = request.data.get('api_secret', '')
        if not new_key:
            return self.error_response(message='New api_key required.', status_code=400)
        old_cred.is_active = False
        old_cred.save(update_fields=['is_active'])
        new_cred = GatewayCredential.objects.create(
            gateway=old_cred.gateway, tenant=old_cred.tenant,
            label=f'{old_cred.label}_rotated',
            api_key=new_key, api_secret=new_secret,
            is_test_mode=old_cred.is_test_mode,
        )
        return self.success_response(
            data=GatewayCredentialSerializer(new_cred).data,
            message='Credentials rotated successfully.'
        )
