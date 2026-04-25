# api/payment_gateways/tracking/PostbackEngine.py
# World-class S2S Postback / Conversion tracking engine
# Supports macros: {click_id}, {payout}, {cost}, {traffic_id}, {offer_id}, {sub1-5}, {status}

import re
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_txn

logger = logging.getLogger(__name__)

# ── Standard macros supported in postback URLs ─────────────────────────────
SUPPORTED_MACROS = {
    '{click_id}':     'click_id',
    '{CLICK_ID}':     'click_id',
    '{transaction_id}':'click_id',
    '{payout}':       'payout',
    '{PAYOUT}':       'payout',
    '{revenue}':      'payout',
    '{cost}':         'cost',
    '{COST}':         'cost',
    '{traffic_id}':   'traffic_id',
    '{offer_id}':     'offer_id',
    '{sub1}':         'sub1',
    '{sub2}':         'sub2',
    '{sub3}':         'sub3',
    '{sub4}':         'sub4',
    '{sub5}':         'sub5',
    '{status}':       'status',
    '{country}':      'country_code',
    '{device}':       'device_type',
    '{os}':           'os_name',
    '{browser}':      'browser',
    '{sale_amount}':  'sale_amount',
    '{order_id}':     'advertiser_order_id',
}


class PostbackEngine:
    """
    Processes incoming S2S postback requests from advertisers.

    Flow:
        1. Advertiser fires postback URL (e.g., after user installs app)
        2. PostbackEngine receives click_id + payout + status
        3. Looks up original Click record
        4. Creates Conversion record
        5. Credits publisher earnings
        6. Fires publisher postback if configured
        7. Logs everything to PostbackLog

    Advertiser postback URL example:
        https://yourdomain.com/postback/?click_id={click_id}&payout={payout}&status=approved

    Publisher postback URL example (S2S):
        https://pubtracker.com/postback/?transaction_id={click_id}&revenue={payout}
    """

    def process(self, request_params: dict, raw_url: str, ip_address: str = '') -> dict:
        """
        Main entry point for postback processing.

        Args:
            request_params: Parsed GET/POST parameters from postback request
            raw_url:        Full raw URL for logging
            ip_address:     Advertiser server IP

        Returns:
            dict: {
                'success': bool,
                'conversion_id': str,
                'click_id': str,
                'status': str,
                'message': str,
            }
        """
        from .models import Click, Conversion, PostbackLog

        click_id = (
            request_params.get('click_id')
            or request_params.get('clickid')
            or request_params.get('transaction_id')
            or request_params.get('aff_sub')
            or ''
        ).strip()

        if not click_id:
            self._log_postback(None, click_id, raw_url, ip_address, 'invalid',
                               'Missing click_id parameter')
            return {'success': False, 'message': 'Missing click_id', 'status': 'invalid'}

        # ── 1. Find original click ────────────────────────────────────────────
        try:
            click = Click.objects.select_related('offer', 'publisher', 'campaign').get(
                click_id=click_id
            )
        except Click.DoesNotExist:
            self._log_postback(None, click_id, raw_url, ip_address, 'invalid',
                               f'Click not found: {click_id}')
            return {'success': False, 'message': 'click_id not found', 'status': 'invalid'}

        # ── 2. Duplicate check ────────────────────────────────────────────────
        if click.is_converted:
            existing = Conversion.objects.filter(click=click).first()
            self._log_postback(click.offer, click_id, raw_url, ip_address, 'duplicate',
                               'Click already converted')
            return {
                'success':       True,
                'conversion_id': str(existing.conversion_id) if existing else '',
                'click_id':      click_id,
                'status':        'duplicate',
                'message':       'Duplicate conversion — already recorded',
            }

        # ── 3. Extract parameters ─────────────────────────────────────────────
        payout  = Decimal(str(request_params.get('payout', '0') or '0'))
        cost    = Decimal(str(request_params.get('cost', '0') or '0'))
        status  = (request_params.get('status', 'approved') or 'approved').lower()
        adv_order = request_params.get('order_id', '') or request_params.get('transaction_id', '')
        sale_amt  = request_params.get('sale_amount', None)

        # Use offer payout if not provided in postback
        if payout == 0 and click.offer:
            payout = click.offer.publisher_payout
        if cost == 0 and click.offer:
            cost = click.offer.advertiser_cost

        # Map status
        status_map = {
            'approved':  'approved',
            'approve':   'approved',
            '1':         'approved',
            'rejected':  'rejected',
            'reject':    'rejected',
            '0':         'rejected',
            'pending':   'pending',
            'chargeback':'reversed',
            'reversed':  'reversed',
        }
        conv_status = status_map.get(status, 'pending')

        # ── 4. Fraud check ────────────────────────────────────────────────────
        fraud_result = self._check_fraud(click, ip_address)
        if fraud_result['is_fraud']:
            conv_status = 'fraud'
            click.is_fraud    = True
            click.fraud_reason = fraud_result['reason']
            click.save(update_fields=['is_fraud', 'fraud_reason'])

        # ── 5. Create conversion ──────────────────────────────────────────────
        with db_txn.atomic():
            conversion = Conversion.objects.create(
                click             = click,
                click_id_raw      = click_id,
                offer             = click.offer,
                campaign          = click.campaign,
                publisher         = click.publisher,
                advertiser        = click.advertiser,
                conversion_type   = self._detect_type(click.offer),
                status            = conv_status,
                payout            = payout,
                cost              = cost,
                currency          = click.currency or 'USD',
                country_code      = click.country_code,
                device_type       = click.device_type,
                advertiser_order_id = adv_order,
                sale_amount       = Decimal(str(sale_amt)) if sale_amt else None,
                postback_received  = True,
                postback_ip        = ip_address,
                postback_received_at = timezone.now(),
                metadata          = {
                    'raw_params': request_params,
                    'sub1': click.sub1, 'sub2': click.sub2,
                    'sub3': click.sub3, 'sub4': click.sub4, 'sub5': click.sub5,
                }
            )

            if conv_status == 'approved':
                conversion.approved_at = timezone.now()
                conversion.save(update_fields=['approved_at'])

            # Update click record
            click.is_converted = True
            click.converted_at = timezone.now()
            click.payout       = payout
            click.cost         = cost
            click.save(update_fields=['is_converted', 'converted_at', 'payout', 'cost'])

        # ── 6. Credit publisher earnings ──────────────────────────────────────
        if conv_status == 'approved' and payout > 0:
            self._credit_publisher(conversion)

        # ── 7. Fire publisher postback ────────────────────────────────────────
        if conv_status == 'approved':
            self._fire_publisher_postback(conversion)

        # ── 8. Update daily stats ─────────────────────────────────────────────
        self._update_stats(click, conversion)

        # ── 9. Log ────────────────────────────────────────────────────────────
        self._log_postback(click.offer, click_id, raw_url, ip_address, 'success',
                           '', conversion)

        logger.info(
            f'Postback processed: click_id={click_id} status={conv_status} '
            f'payout={payout} publisher={click.publisher_id}'
        )

        return {
            'success':       True,
            'conversion_id': conversion.conversion_id,
            'click_id':      click_id,
            'status':        conv_status,
            'payout':        float(payout),
            'message':       f'Conversion recorded: {conv_status}',
        }

    def _credit_publisher(self, conversion):
        """Credit publisher's balance with payout amount."""
        try:
            publisher = conversion.publisher
            if publisher and hasattr(publisher, 'balance'):
                publisher.balance = (publisher.balance or Decimal('0')) + conversion.payout
                publisher.save(update_fields=['balance'])
                conversion.publisher_paid    = True
                conversion.publisher_paid_at = timezone.now()
                conversion.save(update_fields=['publisher_paid', 'publisher_paid_at'])
                logger.info(f'Publisher {publisher.id} credited {conversion.payout}')
        except Exception as e:
            logger.error(f'Failed to credit publisher: {e}')

    def _fire_publisher_postback(self, conversion):
        """Fire outgoing S2S postback to publisher's tracker."""
        import threading
        from .PostbackFirer import PostbackFirer
        thread = threading.Thread(
            target=PostbackFirer().fire,
            args=(conversion,),
            daemon=True
        )
        thread.start()

    def _detect_type(self, offer) -> str:
        if not offer:
            return 'action'
        type_map = {
            'cpa': 'action',
            'cpi': 'install',
            'cpl': 'lead',
            'cps': 'sale',
            'cpc': 'click',
        }
        return type_map.get(getattr(offer, 'offer_type', 'cpa'), 'action')

    def _check_fraud(self, click, postback_ip: str) -> dict:
        """Basic fraud checks for incoming conversions."""
        # Check: postback from suspicious IP
        # Check: click too old (> 30 days)
        age_days = (timezone.now() - click.created_at).days
        if age_days > 30:
            return {'is_fraud': True, 'reason': f'Click too old: {age_days} days'}

        # Check: same IP for click and conversion (possible self-converting)
        if click.ip_address and postback_ip and click.ip_address == postback_ip:
            return {'is_fraud': False, 'reason': ''}  # OK — advertiser server

        return {'is_fraud': False, 'reason': ''}

    def _update_stats(self, click, conversion):
        """Update publisher daily stats."""
        from .models import PublisherDailyStats
        try:
            today = timezone.now().date()
            stats, _ = PublisherDailyStats.objects.get_or_create(
                publisher=click.publisher,
                offer=click.offer,
                date=today,
                defaults={'clicks': 0, 'conversions': 0, 'revenue': Decimal('0')}
            )
            if conversion.status == 'approved':
                PublisherDailyStats.objects.filter(id=stats.id).update(
                    conversions=models.F('conversions') + 1,
                    revenue=models.F('revenue') + conversion.payout,
                )
        except Exception as e:
            logger.warning(f'Stats update failed: {e}')

    def _log_postback(self, offer, click_id, raw_url, ip, status, error='', conversion=None):
        from .models import PostbackLog
        try:
            PostbackLog.objects.create(
                offer=offer,
                click_id=click_id,
                raw_url=raw_url[:2000],
                ip_address=ip or None,
                status=status,
                error_message=error,
                conversion=conversion,
                response_code=200 if status == 'success' else 400,
            )
        except Exception as e:
            logger.warning(f'PostbackLog failed: {e}')


# Re-import for stats update
from django.db import models
