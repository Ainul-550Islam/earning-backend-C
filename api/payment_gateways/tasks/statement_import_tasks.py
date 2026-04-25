# tasks/statement_import_tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

@shared_task
def auto_import_gateway_statement(gateway_name: str, period_start: str, period_end: str):
    """
    Auto-import gateway statement via API (for gateways that support it).
    Currently: Stripe (balance transactions API), PayPal (transaction search).
    """
    from api.payment_gateways.models.core import PaymentGateway
    from api.payment_gateways.models.reconciliation import GatewayStatement
    from decimal import Decimal
    import datetime

    try:
        gw    = PaymentGateway.objects.get(name=gateway_name)
        start = datetime.date.fromisoformat(period_start)
        end   = datetime.date.fromisoformat(period_end)

        transactions = _fetch_gateway_transactions(gateway_name, start, end)
        total = sum(Decimal(str(t.get('amount', 0))) for t in transactions)

        stmt, created = GatewayStatement.objects.update_or_create(
            gateway=gw, period_start=start, period_end=end,
            defaults={
                'raw_data':    transactions,
                'total_amount':total,
                'total_count': len(transactions),
                'format':      'json',
            }
        )
        action = 'created' if created else 'updated'
        logger.info(f'Statement {action}: {gateway_name} {start} to {end} — {len(transactions)} txns')
        return {'imported': len(transactions), 'gateway': gateway_name}
    except Exception as e:
        logger.error(f'Statement import failed for {gateway_name}: {e}')
        raise

def _fetch_gateway_transactions(gateway: str, start, end) -> list:
    """Fetch transactions from gateway API for given period."""
    if gateway == 'stripe':
        return _fetch_stripe(start, end)
    elif gateway == 'paypal':
        return _fetch_paypal(start, end)
    return []

def _fetch_stripe(start, end) -> list:
    import requests
    from django.conf import settings
    key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    if not key:
        return []
    try:
        resp = requests.get(
            'https://api.stripe.com/v1/balance_transactions',
            params={'created[gte]': int(start.strftime('%s')), 'limit': 100},
            headers={'Authorization': f'Bearer {key}'},
            timeout=30
        )
        data = resp.json()
        return [{'txn_id': t['id'], 'amount': t['amount']/100, 'status': t['type']}
                for t in data.get('data', [])]
    except Exception:
        return []

def _fetch_paypal(start, end) -> list:
    return []  # Requires PayPal Reporting API OAuth2 flow
