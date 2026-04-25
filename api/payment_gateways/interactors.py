# api/payment_gateways/interactors.py
# Interactors — orchestrate complex cross-service interactions
# Sit between use_cases and services. Handle multi-step flows.
# "Do not summarize or skip any logic. Provide the full code."

from decimal import Decimal
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


class DepositFlowInteractor:
    """
    Orchestrates the complete deposit flow end-to-end.
    Coordinates: GatewayRouter → FraudCheck → Gateway → DB → Wallet → Notification
    """

    def __init__(self):
        from api.payment_gateways.services.GatewayRouterService import GatewayRouterService
        from api.payment_gateways.services.GatewayFallbackService import GatewayFallbackService
        from api.payment_gateways.services.GatewayHealthService import GatewayHealthService
        from api.payment_gateways.repositories import DepositRepository
        self.router   = GatewayRouterService()
        self.fallback = GatewayFallbackService()
        self.health   = GatewayHealthService()
        self.repo     = DepositRepository()

    def initiate(self, user, amount: Decimal, preferred_gateway: str,
                  currency: str = 'BDT', country: str = 'BD',
                  ip: str = '', user_agent: str = '') -> dict:
        """
        Full deposit initiation with auto-routing and fallback.

        1. Check preferred gateway health
        2. Route to best available gateway if preferred is down
        3. Initiate deposit
        4. Return payment URL
        """
        # Check if preferred gateway is healthy
        health = self.health.check_single(preferred_gateway)
        if health.get('status') == 'down':
            logger.warning(f'Preferred gateway {preferred_gateway} is down, routing...')
            routing = self.router.select(user, amount, country=country)
            gateway = routing.get('gateway', preferred_gateway)
        else:
            gateway = preferred_gateway

        from api.payment_gateways.use_cases import InitiateDepositUseCase
        result = InitiateDepositUseCase().execute(
            user=user, amount=amount, gateway=gateway,
            currency=currency, ip=ip, user_agent=user_agent,
        )

        # If primary fails, try fallback
        if not result.get('success') and gateway != preferred_gateway:
            chain  = self.fallback.get_fallback_chain(gateway)
            for fb_gw in chain[1:3]:
                logger.info(f'Trying fallback gateway: {fb_gw}')
                result = InitiateDepositUseCase().execute(
                    user=user, amount=amount, gateway=fb_gw,
                    currency=currency, ip=ip, user_agent=user_agent,
                )
                if result.get('success'):
                    result['used_fallback'] = True
                    result['original_gateway'] = preferred_gateway
                    break

        return result

    def verify(self, reference_id: str) -> dict:
        """
        Verify a pending deposit by polling the gateway.
        Called when webhook hasn't arrived after expected time.
        """
        deposit = self.repo.get_by_reference(reference_id)
        if not deposit:
            return {'success': False, 'error': 'Deposit not found'}
        if deposit.status == 'completed':
            return {'success': True, 'already_completed': True}

        try:
            from api.payment_gateways.services.PaymentFactory import PaymentFactory
            processor = PaymentFactory.get_processor(deposit.gateway)
            result    = processor.verify_payment(
                deposit.session_key or deposit.gateway_ref or reference_id
            )
            if result and getattr(result, 'status', None) in ('completed', 'Authorized'):
                from api.payment_gateways.use_cases import CompleteDepositUseCase
                return CompleteDepositUseCase().execute(
                    reference_id, deposit.gateway_ref or '', {}
                )
            return {'success': False, 'status': 'still_pending'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class WithdrawalFlowInteractor:
    """
    Orchestrates complete withdrawal flow.
    Coordinates: Validation → Balance → KYC → Payout → Gateway → Notification
    """

    def process_batch(self, payout_ids: List[int]) -> dict:
        """Process multiple approved payouts in batch."""
        from api.payment_gateways.use_cases import ProcessPayoutUseCase
        results = {'success': 0, 'failed': 0, 'errors': []}
        uc      = ProcessPayoutUseCase()
        for pid in payout_ids:
            try:
                r = uc.execute(pid)
                if r.get('success'):
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({'id': pid, 'error': r.get('error', '')})
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({'id': pid, 'error': str(e)})
        logger.info(f'Batch payout: {results["success"]} success, {results["failed"]} failed')
        return results

    def schedule_payout(self, user, amount: Decimal, method: str,
                         account_number: str, schedule_type: str = 'net30') -> dict:
        """
        Create a scheduled payout request.
        schedule_type: 'daily' | 'weekly' | 'net15' | 'net30' | 'manual'
        """
        from api.payment_gateways.use_cases import RequestWithdrawalUseCase
        from api.payment_gateways.utils.DateUtils import DateUtils
        result = RequestWithdrawalUseCase().execute(
            user=user, amount=amount, method=method, account_number=account_number
        )
        if result.get('success'):
            # Set scheduled date
            scheduled_date = DateUtils.next_payout_date(schedule_type)
            from api.payment_gateways.models.core import PayoutRequest
            PayoutRequest.objects.filter(id=result['payout_id']).update(
                metadata={'scheduled_date': str(scheduled_date), 'schedule_type': schedule_type}
            )
            result['scheduled_date'] = str(scheduled_date)
        return result


class ConversionFlowInteractor:
    """
    Orchestrates conversion tracking and approval flow.
    Coordinates: ClickTracker → FraudCheck → BlacklistCheck → ConversionCap → Approve → Postback
    """

    def process_postback(self, params: dict, ip: str = '') -> dict:
        """
        Process incoming advertiser postback and record conversion.

        Flow:
            1. Validate click_id exists
            2. Check blacklist for this publisher/offer
            3. Check conversion duplicate
            4. Check offer cap
            5. Create conversion
            6. Auto-approve if rules pass
            7. Fire publisher postback
        """
        from api.payment_gateways.tracking.models import Click
        from api.payment_gateways.blacklist.BlacklistEngine import BlacklistEngine
        from api.payment_gateways.repositories import ConversionRepository
        from api.payment_gateways.use_cases import ApproveConversionUseCase
        from api.payment_gateways.integration_system.sync_manager import sync_manager

        click_id = params.get('click_id', '')
        payout   = Decimal(str(params.get('payout', '0') or '0'))
        status   = params.get('status', 'approved')

        if not click_id:
            return {'success': False, 'error': 'click_id required'}

        # 1. Find click
        try:
            click = Click.objects.select_related('publisher', 'offer').get(click_id=click_id)
        except Click.DoesNotExist:
            logger.warning(f'Postback: click_id not found: {click_id}')
            return {'success': False, 'error': 'click_id not found'}

        # 2. Check duplicate
        if sync_manager.check_conversion_duplicate(click_id):
            logger.info(f'Postback: duplicate conversion for click {click_id}')
            return {'success': True, 'duplicate': True}

        # 3. Blacklist check
        if click.offer and click.offer.advertiser_id:
            bl = BlacklistEngine().is_blocked(
                offer_id=click.offer_id,
                advertiser_id=click.offer.advertiser_id,
                ip=ip, country=click.country_code,
                device=click.device_type,
                publisher_id=click.publisher_id,
            )
            if bl.get('blocked'):
                logger.info(f'Postback blocked by blacklist: {bl["reason"]}')
                return {'success': False, 'error': f'Blocked: {bl["reason"]}'}

        # 4. Check cap
        if click.offer:
            from api.payment_gateways.offers.ConversionCapEngine import ConversionCapEngine
            cap = ConversionCapEngine().check_caps(click.offer)
            if not cap['can_convert']:
                return {'success': False, 'error': cap['reason']}

        # 5. Create conversion
        repo = ConversionRepository()
        conv = repo.create(
            publisher=click.publisher, offer=click.offer, click=click,
            payout=payout or (click.offer.publisher_payout if click.offer else Decimal('0')),
            cost=click.offer.advertiser_cost if click.offer else Decimal('0'),
            country=click.country_code, currency=click.offer.currency if click.offer else 'USD',
        )

        # 6. Mark click as converted
        Click.objects.filter(click_id=click_id).update(is_converted=True)

        # 7. Auto-approve if status is approved
        if status == 'approved':
            return ApproveConversionUseCase().execute(conv.conversion_id)

        return {'success': True, 'conversion_id': conv.conversion_id, 'status': 'pending'}


class ReconciliationInteractor:
    """
    Orchestrates the full reconciliation pipeline.
    Compares our DB records against gateway statements for all gateways.
    """

    def run_nightly(self) -> dict:
        """Run full nightly reconciliation for all gateways."""
        from api.payment_gateways.models.core import PaymentGateway
        from api.payment_gateways.services.ReconciliationService import ReconciliationService
        from datetime import date, timedelta

        yesterday = date.today() - timedelta(days=1)
        svc       = ReconciliationService()
        results   = {}

        for gw in PaymentGateway.objects.filter(status='active'):
            try:
                result = svc.reconcile(gw.name, yesterday)
                results[gw.name] = result

                # Alert if discrepancy > $100
                if abs(result.get('discrepancy', 0)) > 100:
                    logger.warning(f'Large reconciliation discrepancy: {gw.name} ${result["discrepancy"]}')
            except Exception as e:
                results[gw.name] = {'error': str(e)}
                logger.error(f'Reconciliation failed for {gw.name}: {e}')

        logger.info(f'Nightly reconciliation done: {len(results)} gateways')
        return results


class FraudReviewInteractor:
    """
    Orchestrates fraud review workflow.
    Coordinates: FraudDetector → RiskScore → Action → Alert
    """

    def review_transaction(self, user, amount: Decimal, gateway: str,
                            ip: str = '', user_agent: str = '') -> dict:
        """
        Full fraud review for any transaction.
        Returns action: 'allow' | 'flag' | 'verify' | 'block'
        """
        from api.payment_gateways.integrations_adapters.FraudAdapter import FraudAdapter
        from api.payment_gateways.tracking.FingerprintEngine import FingerprintEngine
        from api.payment_gateways.openAI import ai_fraud_risk_score

        # 1. Rule-based fraud check
        fraud_result = FraudAdapter().check(user, amount, gateway, ip_address=ip)

        # 2. AI fraud scoring (additional layer)
        if fraud_result.get('risk_score', 0) > 30:
            ai_result = ai_fraud_risk_score(user, amount, gateway, ip, user_agent)
            # Combine scores (weighted average)
            combined = int(fraud_result['risk_score'] * 0.6 + ai_result.get('risk_score', 0) * 0.4)
            fraud_result['risk_score'] = combined
            fraud_result['ai_reasons'] = ai_result.get('reasons', [])
            fraud_result['ai_score']   = ai_result.get('risk_score', 0)

        # 3. Determine action
        score  = fraud_result.get('risk_score', 0)
        action = fraud_result.get('action', 'allow')

        if score >= 80:
            action = 'block'
        elif score >= 60:
            action = 'verify'
        elif score >= 40:
            action = 'flag'

        fraud_result['action'] = action

        # 4. Log fraud events
        if action in ('flag', 'verify', 'block'):
            from api.payment_gateways.signals import fraud_detected
            fraud_detected.send(
                sender=None, user=user,
                transaction=type('T', (), {'gateway': gateway, 'amount': amount})(),
                result=fraud_result,
            )

        return fraud_result
