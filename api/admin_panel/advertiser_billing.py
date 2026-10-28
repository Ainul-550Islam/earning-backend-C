# api/admin_panel/advertiser_billing.py
"""Advertiser billing, deposits, invoices admin control."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone
from django.db.models import Sum, Count

logger = logging.getLogger(__name__)


class AdvertiserBillingAdmin:
    """Admin control for advertiser billing and deposits."""

    @classmethod
    def get_billing_overview(cls) -> Dict:
        try:
            from api.advertiser_portal.models import AdvertiserPortalBaseModel
            # Dynamic lookup
            import importlib
            mod = importlib.import_module('api.advertiser_portal.models')
            overview = {}
            for model_name in ['Advertiser', 'AdvertiserAccount', 'AdvertiserDeposit']:
                if hasattr(mod, model_name):
                    model = getattr(mod, model_name)
                    overview[model_name.lower()] = {'total': model.objects.count()}
            return {'success': True, 'data': overview}
        except Exception as e:
            return {'success': True, 'data': {'note': str(e)[:100]}}

    @classmethod
    def get_pending_deposits(cls, limit: int = 100) -> List[Dict]:
        try:
            from api.payment_gateways.models import GatewayTransaction
            return list(GatewayTransaction.objects.filter(
                status='PENDING',
                transaction_type='advertiser_deposit'
            ).values('id', 'user_id', 'amount', 'gateway', 'created_at').order_by('-created_at')[:limit])
        except Exception as e:
            return []

    @classmethod
    def approve_deposit(cls, transaction_id: Any, actor) -> Dict:
        try:
            from api.payment_gateways.models import GatewayTransaction
            txn = GatewayTransaction.objects.get(pk=transaction_id)
            txn.status = 'COMPLETED'
            txn.processed_by = actor
            txn.processed_at = timezone.now()
            txn.save()
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='approve_advertiser_deposit',
                              model_name='GatewayTransaction', object_id=str(transaction_id),
                              changes={'amount': float(txn.amount)})
            return {'success': True, 'transaction_id': transaction_id, 'amount': float(txn.amount)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_advertiser_spend(cls, advertiser_id: Any, days: int = 30) -> Dict:
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.payment_gateways.models import GatewayTransaction
            spend = GatewayTransaction.objects.filter(
                user_id=advertiser_id,
                transaction_type='campaign_spend',
                created_at__gte=cutoff
            ).aggregate(total=Sum('amount'), count=Count('id'))
            return {'advertiser_id': advertiser_id, 'period_days': days,
                    'total_spend': float(spend['total'] or 0), 'transactions': spend['count'] or 0}
        except Exception as e:
            return {'advertiser_id': advertiser_id, 'error': str(e)}


advertiser_billing_admin = AdvertiserBillingAdmin()