# api/payment_gateways/repositories.py
# Repository pattern — data access layer
# Abstracts DB operations behind clean interfaces.
# Services call repositories instead of model.objects directly.
# "Do not summarize or skip any logic. Provide the full code."

from decimal import Decimal
from typing import Optional, List, Dict
from django.db import transaction as db_txn
from django.utils import timezone
import logging, time, secrets

logger = logging.getLogger(__name__)


class TransactionRepository:
    """CRUD operations for GatewayTransaction."""

    def create(self, user, transaction_type: str, gateway: str,
                amount: Decimal, fee: Decimal, currency: str = 'BDT',
                metadata: dict = None) -> object:
        from api.payment_gateways.models.core import GatewayTransaction
        ref = f'{transaction_type[:3].upper()}-{gateway[:4].upper()}-{int(time.time()*1000)}-{secrets.token_hex(3).upper()}'
        return GatewayTransaction.objects.create(
            user=user, transaction_type=transaction_type, gateway=gateway,
            amount=amount, fee=fee, net_amount=amount - fee, currency=currency,
            status='pending', reference_id=ref, metadata=metadata or {},
        )

    def update_status(self, reference_id: str, status: str,
                       gateway_ref: str = '', metadata_update: dict = None) -> bool:
        from api.payment_gateways.models.core import GatewayTransaction
        update = {'status': status}
        if status == 'completed':
            update['completed_at'] = timezone.now()
        if gateway_ref:
            update['gateway_reference'] = gateway_ref
        rows = GatewayTransaction.objects.filter(reference_id=reference_id).update(**update)
        if metadata_update and rows:
            txn = GatewayTransaction.objects.get(reference_id=reference_id)
            txn.metadata.update(metadata_update)
            txn.save(update_fields=['metadata'])
        return rows > 0

    def get_by_reference(self, reference_id: str) -> Optional[object]:
        from api.payment_gateways.models.core import GatewayTransaction
        try:
            return GatewayTransaction.objects.select_related('user').get(reference_id=reference_id)
        except GatewayTransaction.DoesNotExist:
            return None

    def get_for_user(self, user, status: str = None, limit: int = 50) -> list:
        from api.payment_gateways.models.core import GatewayTransaction
        qs = GatewayTransaction.objects.filter(user=user)
        if status:
            qs = qs.filter(status=status)
        return list(qs.order_by('-created_at')[:limit])

    def exists_recent_duplicate(self, user, amount: Decimal,
                                  gateway: str, seconds: int = 30) -> bool:
        from api.payment_gateways.models.core import GatewayTransaction
        from datetime import timedelta
        return GatewayTransaction.objects.filter(
            user=user, amount=amount, gateway=gateway,
            status='pending',
            created_at__gte=timezone.now() - timedelta(seconds=seconds),
        ).exists()


class DepositRepository:
    """CRUD operations for DepositRequest."""

    def create(self, user, gateway: str, amount: Decimal, fee: Decimal,
                currency: str = 'BDT', ip: str = '', user_agent: str = '') -> object:
        from api.payment_gateways.models.deposit import DepositRequest
        ref = f'DEP-{gateway[:4].upper()}-{int(time.time()*1000)}-{secrets.token_hex(3).upper()}'
        from datetime import timedelta
        return DepositRequest.objects.create(
            user=user, gateway=gateway, amount=amount, fee=fee,
            net_amount=amount - fee, currency=currency, status='initiated',
            reference_id=ref, ip_address=ip or None, user_agent=user_agent[:500],
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def update_after_gateway_call(self, deposit_id: int, payment_url: str,
                                    session_key: str, gateway_response: dict) -> bool:
        from api.payment_gateways.models.deposit import DepositRequest
        return bool(DepositRequest.objects.filter(id=deposit_id).update(
            payment_url=payment_url, session_key=session_key,
            gateway_response=gateway_response, status='pending',
        ))

    def mark_completed(self, reference_id: str, gateway_ref: str,
                        callback_data: dict) -> Optional[object]:
        from api.payment_gateways.models.deposit import DepositRequest
        try:
            with db_txn.atomic():
                deposit = DepositRequest.objects.select_for_update().get(
                    reference_id=reference_id
                )
                if deposit.status == 'completed':
                    return deposit  # Already done — idempotent
                deposit.status       = 'completed'
                deposit.gateway_ref  = gateway_ref
                deposit.callback_data= callback_data
                deposit.completed_at = timezone.now()
                deposit.save()
                return deposit
        except DepositRequest.DoesNotExist:
            logger.error(f'DepositRepository: deposit not found: {reference_id}')
            return None

    def mark_failed(self, reference_id: str, reason: str = '') -> bool:
        from api.payment_gateways.models.deposit import DepositRequest
        return bool(DepositRequest.objects.filter(
            reference_id=reference_id, status__in=('initiated', 'pending')
        ).update(status='failed'))

    def mark_expired(self, older_than_minutes: int = 60) -> int:
        from api.payment_gateways.models.deposit import DepositRequest
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(minutes=older_than_minutes)
        return DepositRequest.objects.filter(
            status__in=('initiated', 'pending'),
            initiated_at__lte=cutoff,
        ).update(status='expired')

    def get_by_reference(self, reference_id: str) -> Optional[object]:
        from api.payment_gateways.models.deposit import DepositRequest
        try:
            return DepositRequest.objects.select_related('user').get(reference_id=reference_id)
        except DepositRequest.DoesNotExist:
            return None

    def get_by_session_key(self, session_key: str) -> Optional[object]:
        from api.payment_gateways.models.deposit import DepositRequest
        try:
            return DepositRequest.objects.get(session_key=session_key)
        except DepositRequest.DoesNotExist:
            return None


class PayoutRepository:
    """CRUD operations for PayoutRequest."""

    def create(self, user, amount: Decimal, fee: Decimal, method: str,
                account_number: str, account_name: str = '',
                currency: str = 'BDT') -> object:
        from api.payment_gateways.models.core import PayoutRequest
        ref = f'PAY-{method[:4].upper()}-{int(time.time()*1000)}-{secrets.token_hex(3).upper()}'
        return PayoutRequest.objects.create(
            user=user, amount=amount, fee=fee, net_amount=amount - fee,
            currency=currency, payout_method=method, account_number=account_number,
            account_name=account_name, status='pending', reference_id=ref,
        )

    def approve(self, payout_id: int, approved_by) -> bool:
        from api.payment_gateways.models.core import PayoutRequest
        return bool(PayoutRequest.objects.filter(
            id=payout_id, status='pending'
        ).update(status='approved', processed_by=approved_by))

    def reject(self, payout_id: int, rejected_by, reason: str = '') -> bool:
        from api.payment_gateways.models.core import PayoutRequest
        return bool(PayoutRequest.objects.filter(
            id=payout_id, status='pending'
        ).update(status='rejected', processed_by=rejected_by, admin_notes=reason))

    def mark_completed(self, payout_id: int, gateway_ref: str = '') -> bool:
        from api.payment_gateways.models.core import PayoutRequest
        return bool(PayoutRequest.objects.filter(id=payout_id).update(
            status='completed',
            gateway_reference=gateway_ref,
            processed_at=timezone.now(),
        ))

    def mark_failed(self, payout_id: int, reason: str = '') -> bool:
        from api.payment_gateways.models.core import PayoutRequest
        return bool(PayoutRequest.objects.filter(id=payout_id).update(
            status='failed', admin_notes=reason
        ))


class ConversionRepository:
    """CRUD operations for Conversion model."""

    def create(self, publisher, offer, click, payout: Decimal,
                cost: Decimal, country: str = '', currency: str = 'USD',
                metadata: dict = None) -> object:
        from api.payment_gateways.tracking.models import Conversion
        import uuid
        return Conversion.objects.create(
            publisher=publisher, offer=offer, click=click,
            conversion_id=f'conv_{uuid.uuid4().hex[:20]}',
            click_id_raw=click.click_id if click else '',
            conversion_type=offer.offer_type if offer else 'action',
            status='pending', payout=payout, cost=cost,
            revenue=cost - payout, currency=currency,
            country_code=country, metadata=metadata or {},
        )

    def approve(self, conversion_id: str) -> bool:
        from api.payment_gateways.tracking.models import Conversion
        rows = Conversion.objects.filter(
            conversion_id=conversion_id, status='pending'
        ).update(status='approved', approved_at=timezone.now())
        return rows > 0

    def reject(self, conversion_id: str, reason: str = '') -> bool:
        from api.payment_gateways.tracking.models import Conversion
        return bool(Conversion.objects.filter(
            conversion_id=conversion_id
        ).update(status='rejected'))

    def mark_publisher_paid(self, conversion_ids: list) -> int:
        from api.payment_gateways.tracking.models import Conversion
        return Conversion.objects.filter(
            conversion_id__in=conversion_ids, status='approved', publisher_paid=False
        ).update(publisher_paid=True, publisher_paid_at=timezone.now())

    def get_by_click_id(self, click_id: str) -> Optional[object]:
        from api.payment_gateways.tracking.models import Conversion
        try:
            return Conversion.objects.get(click_id_raw=click_id)
        except Conversion.DoesNotExist:
            return None

    def exists(self, click_id: str) -> bool:
        """Check if conversion already recorded for this click."""
        from api.payment_gateways.tracking.models import Conversion
        return Conversion.objects.filter(
            click_id_raw=click_id,
            status__in=('approved', 'pending', 'processing')
        ).exists()


class GatewayCredentialRepository:
    """CRUD for GatewayCredential model."""

    def get_active(self, gateway_name: str, tenant=None) -> Optional[object]:
        from api.payment_gateways.models.gateway_config import GatewayCredential
        from api.payment_gateways.models.core import PaymentGateway
        try:
            gw = PaymentGateway.objects.get(name=gateway_name)
            qs = GatewayCredential.objects.filter(gateway=gw, is_active=True)
            if tenant:
                qs = qs.filter(tenant=tenant)
            else:
                qs = qs.filter(tenant__isnull=True)
            return qs.first()
        except Exception:
            return None

    def create(self, gateway_name: str, api_key: str, api_secret: str,
                merchant_id: str = '', is_test: bool = True, tenant=None) -> object:
        from api.payment_gateways.models.gateway_config import GatewayCredential
        from api.payment_gateways.models.core import PaymentGateway
        gw = PaymentGateway.objects.get(name=gateway_name)
        return GatewayCredential.objects.create(
            gateway=gw, tenant=tenant, api_key=api_key,
            api_secret=api_secret, merchant_id=merchant_id, is_test_mode=is_test,
        )
