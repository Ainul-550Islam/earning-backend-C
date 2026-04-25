# api/payment_gateways/mixins.py
from rest_framework.response import Response
from decimal import Decimal


class PaymentResponseMixin:
    """Standard response format for payment endpoints."""

    def payment_success(self, data=None, message='Success', status_code=200):
        return Response({'success': True, 'message': message, 'data': data or {}}, status=status_code)

    def payment_error(self, message='Error', errors=None, status_code=400):
        return Response({'success': False, 'message': message, 'errors': errors or []}, status=status_code)


class GatewayMixin:
    """Common gateway operations for viewsets."""

    def get_gateway_or_404(self, gateway_name):
        from api.payment_gateways.models.core import PaymentGateway
        try:
            return PaymentGateway.objects.get(name=gateway_name, status='active')
        except PaymentGateway.DoesNotExist:
            return None

    def validate_deposit_amount(self, amount, gateway):
        from api.payment_gateways.services.PaymentValidator import PaymentValidator
        return PaymentValidator().validate_deposit(
            user=self.request.user,
            amount=Decimal(str(amount)),
            gateway=gateway,
        )


class PublisherMixin:
    """Mixin for publisher-only viewsets."""

    def get_publisher_queryset(self, queryset):
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(publisher=self.request.user)

    def get_publisher_profile(self):
        try:
            from api.payment_gateways.publisher.models import PublisherProfile
            return PublisherProfile.objects.get(user=self.request.user)
        except Exception:
            return None


class CurrencyMixin:
    """Multi-currency support for viewsets."""

    def convert_for_user(self, amount: Decimal, from_currency: str) -> dict:
        from api.payment_gateways.services.MultiCurrencyEngine import MultiCurrencyEngine
        engine = MultiCurrencyEngine()
        return engine.get_payout_in_user_currency(amount, self.request.user)

    def format_amount(self, amount: Decimal, currency: str) -> str:
        from api.payment_gateways.services.MultiCurrencyEngine import MultiCurrencyEngine
        return MultiCurrencyEngine().format_amount(amount, currency)


class AuditMixin:
    """Auto audit-log all write operations."""

    def perform_create(self, serializer):
        instance = super().perform_create(serializer)
        self._audit_log('create', instance)
        return instance

    def perform_update(self, serializer):
        instance = super().perform_update(serializer)
        self._audit_log('update', instance)
        return instance

    def _audit_log(self, action, instance):
        from api.payment_gateways.integration_system.integ_audit_logs import audit_logger
        audit_logger.log(
            event_type   = f'{self.__class__.__name__}.{action}',
            source_module= 'api.payment_gateways',
            user_id      = self.request.user.id,
            payload      = {'model': instance.__class__.__name__, 'id': getattr(instance, 'id', None)},
            success      = True,
        )
