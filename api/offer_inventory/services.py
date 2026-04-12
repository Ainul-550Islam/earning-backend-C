# api/offer_inventory/services.py
"""
Service Layer — সব Business Logic এখানে।
Repository ব্যবহার করে, HTTP জানে না।
"""
import hashlib
import secrets
import logging
from decimal import Decimal
from typing import Optional, Tuple
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from .repository import (
    OfferRepository, ClickRepository, ConversionRepository,
    FraudRepository, WalletRepository, AnalyticsRepository,
    NotificationRepository, FeatureFlagRepository,
)
from .exceptions import (
    OfferNotFoundException, OfferExpiredException, OfferCapReachedException,
    AlreadyCompletedException, FraudDetectedException, IPBlockedException,
    VPNDetectedException, DuplicateConversionException, InvalidClickTokenException,
    InvalidPostbackException, InsufficientBalanceException, WalletLockedException,
    MinWithdrawalException, MaxWithdrawalException, KYCRequiredException,
    DailyLimitReachedException, FeatureDisabledException, RateLimitExceededException,
)
from .constants import (
    FRAUD_SCORE_THRESHOLD, AUTO_BLOCK_SCORE,
    MIN_WITHDRAWAL_BDT, MAX_WITHDRAWAL_BDT,
    CLICK_TOKEN_TTL_SECONDS, MAX_CLICKS_PER_HOUR,
    DEFAULT_PLATFORM_FEE_PCT, DEFAULT_REVENUE_SHARE,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# OFFER SERVICE
# ══════════════════════════════════════════════════════

class OfferService:

    @staticmethod
    def list_offers(tenant, user, request_meta: dict) -> list:
        """
        User-এর জন্য available offers।
        Geo, device, fraud check সহ।
        """
        if not FeatureFlagRepository.is_enabled('offer_wall', tenant):
            raise FeatureDisabledException()

        country = request_meta.get('country_code', '')
        device  = request_meta.get('device_type', '')

        return OfferRepository.get_active_offers(
            tenant=tenant,
            country=country,
            device=device,
        )

    @staticmethod
    def get_offer_detail(offer_id: str, tenant=None) -> object:
        offer = OfferRepository.get_offer_by_id(offer_id, tenant)
        if not offer:
            raise OfferNotFoundException()
        return offer

    @staticmethod
    def check_offer_eligibility(offer, user, ip: str) -> Tuple[bool, str]:
        """
        ইউজার এই অফার করতে পারবে কিনা সব check।
        Returns: (eligible: bool, reason: str)
        """
        # 1. Offer available?
        if not offer.is_available:
            return False, 'offer_not_available'

        # 2. IP blocked?
        if FraudRepository.is_ip_blocked(ip):
            return False, 'ip_blocked'

        # 3. User suspended?
        risk = FraudRepository.get_user_risk_profile(user.id)
        if risk and risk.is_suspended:
            return False, 'user_suspended'

        # 4. Daily limit?
        today_clicks = ClickRepository.count_user_clicks_today(user.id, offer.id)
        if today_clicks >= 3:  # প্রতিটি অফার দিনে max ৩ বার click
            return False, 'daily_limit'

        # 5. Offer cap?
        for cap in offer.caps.all():
            if cap.is_reached:
                return False, 'cap_reached'

        return True, 'ok'


# ══════════════════════════════════════════════════════
# CLICK SERVICE
# ══════════════════════════════════════════════════════

class ClickService:

    @staticmethod
    def generate_click_token() -> str:
        return secrets.token_hex(32)  # 64-char hex

    @staticmethod
    @transaction.atomic
    def record_click(offer_id: str, user, request_meta: dict) -> object:
        """
        Click record করো।
        Fraud check → token generate → DB save।
        """
        from .models import Click, SubID, TrafficSource

        ip         = request_meta.get('ip_address', '')
        user_agent = request_meta.get('user_agent', '')
        country    = request_meta.get('country_code', '')
        device     = request_meta.get('device_type', '')
        referrer   = request_meta.get('referrer', '')
        s1         = request_meta.get('s1', '')

        # ── Fraud Pre-checks ─────────────────────────
        FraudService.pre_click_check(ip, user, user_agent)

        # ── Rate limit ───────────────────────────────
        recent = ClickRepository.count_recent_clicks(ip, minutes=60)
        if recent >= MAX_CLICKS_PER_HOUR:
            raise RateLimitExceededException()

        # ── Offer validate ───────────────────────────
        offer = OfferRepository.get_offer_by_id(offer_id)
        if not offer:
            raise OfferNotFoundException()
        if not offer.is_available:
            raise OfferCapReachedException()

        token = ClickService.generate_click_token()

        # ── Create sub_id if exists ──────────────────
        sub_id_obj = None
        if s1:
            sub_id_obj, _ = SubID.objects.get_or_create(
                offer=offer, user=user, s1=s1,
                defaults={'s1': s1}
            )

        click = ClickRepository.create_click({
            'offer': offer,
            'user': user,
            'sub_id': sub_id_obj,
            'ip_address': ip,
            'user_agent': user_agent,
            'country_code': country,
            'device_type': device,
            'referrer': referrer,
            'click_token': token,
        })

        # Store in cache for fast validation
        cache.set(f'click_token:{token}', str(click.id), CLICK_TOKEN_TTL_SECONDS)

        logger.info(f'Click recorded: {token[:16]}... | offer={offer_id} | user={user.id}')
        return click

    @staticmethod
    def validate_click_token(token: str) -> object:
        """Token validate করো — cache first।"""
        cached = cache.get(f'click_token:{token}')
        if cached:
            click = ClickRepository.get_by_token(token)
            if click:
                return click

        # Fallback to DB
        click = ClickRepository.get_by_token(token)
        if not click:
            raise InvalidClickTokenException()
        return click


# ══════════════════════════════════════════════════════
# CONVERSION SERVICE
# ══════════════════════════════════════════════════════

class ConversionService:

    @staticmethod
    @transaction.atomic
    def process_conversion(click_token: str, transaction_id: str,
                           payout: Decimal, raw_data: dict) -> object:
        """
        Network postback process।
        Click validate → Duplicate check → Conversion create → Reward credit।
        """
        # 1. Click validate
        click = ClickService.validate_click_token(click_token)
        if click.converted:
            raise DuplicateConversionException()

        user  = click.user
        offer = click.offer

        # 2. Fraud check on conversion
        fingerprint = ConversionService._make_fingerprint(
            str(user.id), str(offer.id), click.ip_address
        )
        if ConversionRepository.check_duplicate(user.id, offer.id, fingerprint):
            raise DuplicateConversionException()

        # 3. Calculate reward
        reward = ConversionService._calculate_reward(offer, payout)

        # 4. Create conversion record
        conversion = ConversionRepository.create_conversion({
            'click': click,
            'offer': offer,
            'user': user,
            'payout_amount': payout,
            'reward_amount': reward,
            'transaction_id': transaction_id,
            'ip_address': click.ip_address,
            'country_code': click.country_code,
            'raw_postback': raw_data,
        })

        # 5. Mark click as converted
        ClickRepository.mark_as_converted(str(click.id))

        # 6. Store duplicate filter
        from .models import DuplicateConversionFilter
        DuplicateConversionFilter.objects.get_or_create(
            offer=offer, user=user, fingerprint=fingerprint
        )

        # 7. Auto-approve if offer trust level high
        if offer.network and offer.network.is_s2s_enabled:
            ConversionService.approve_conversion(str(conversion.id))
        else:
            # Notify admin for manual review
            NotificationRepository.create(
                user_id=None,
                notif_type='system',
                title='New Conversion Pending Review',
                body=f'Conversion {conversion.id} awaiting approval.',
            )

        # 8. Offer completion count
        OfferRepository.increment_offer_completions(str(offer.id))

        # 9. Update offer caps
        ConversionService._update_caps(offer)

        # 10. Analytics
        from api.offer_inventory.tasks import update_daily_stats
        update_daily_stats.delay(str(conversion.id))

        logger.info(f'Conversion created: {conversion.id} | offer={offer.id} | user={user.id}')
        return conversion

    @staticmethod
    @transaction.atomic
    def approve_conversion(conversion_id: str):
        """Approve করলে user reward পাবে।"""
        success = ConversionRepository.approve_conversion(conversion_id)
        if not success:
            return

        conversion = ConversionRepository.get_by_id(conversion_id)
        if not conversion:
            return

        # Credit wallet
        WalletRepository.credit_user(
            user_id=conversion.user_id,
            amount=conversion.reward_amount,
            source='conversion',
            source_id=str(conversion.id),
            description=f'{conversion.offer.title} সম্পন্ন করার পুরস্কার',
        )

        # Revenue share
        ConversionService._record_revenue_share(conversion)

        # Referral commission
        ConversionService._process_referral_commission(conversion)

        # Notify user
        NotificationRepository.create(
            user_id=conversion.user_id,
            notif_type='payment',
            title='🎉 পুরস্কার পেয়েছেন!',
            body=f'{conversion.offer.title} সম্পন্ন করে {conversion.reward_amount} পেলেন।',
            action_url='/wallet',
        )

        # Queue postback delivery
        from api.offer_inventory.tasks import deliver_postback
        deliver_postback.delay(str(conversion.id))

    @staticmethod
    def _calculate_reward(offer, payout: Decimal) -> Decimal:
        """Platform cut বাদ দিয়ে user reward।"""
        share_pct = Decimal(str(DEFAULT_REVENUE_SHARE)) / Decimal('100')
        if offer.reward_amount > 0:
            return offer.reward_amount
        return (payout * share_pct).quantize(Decimal('0.0001'))

    @staticmethod
    def _make_fingerprint(user_id: str, offer_id: str, ip: str) -> str:
        raw = f'{user_id}:{offer_id}:{ip}'
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _record_revenue_share(conversion):
        from .models import RevenueShare
        gross = conversion.payout_amount
        user_share = conversion.reward_amount
        platform_cut = gross - user_share
        RevenueShare.objects.create(
            offer=conversion.offer,
            conversion=conversion,
            gross_revenue=gross,
            platform_cut=platform_cut,
            user_share=user_share,
        )

    @staticmethod
    def _process_referral_commission(conversion):
        from .models import UserReferral, ReferralCommission
        from .constants import DEFAULT_REFERRAL_PCT
        try:
            referral = UserReferral.objects.get(referred_id=conversion.user_id)
            rate = Decimal(str(DEFAULT_REFERRAL_PCT)) / Decimal('100')
            commission = (conversion.payout_amount * rate).quantize(Decimal('0.0001'))
            ReferralCommission.objects.create(
                referrer=referral.referrer,
                referred_user=conversion.user,
                conversion=conversion,
                commission_pct=DEFAULT_REFERRAL_PCT,
                amount=commission,
            )
            WalletRepository.credit_user(
                user_id=referral.referrer_id,
                amount=commission,
                source='referral',
                source_id=str(conversion.id),
                description=f'Referral commission from {conversion.user.username}',
            )
        except UserReferral.DoesNotExist:
            pass

    @staticmethod
    def _update_caps(offer):
        """Offer caps count বাড়াও।"""
        from django.db.models import F
        offer.caps.filter(is_reached=False).update(
            current_count=F('current_count') + 1
        )
        # Auto-pause if cap reached
        for cap in offer.caps.all():
            cap.refresh_from_db()
            if cap.is_reached and cap.pause_on_hit:
                from .models import Offer
                Offer.objects.filter(id=offer.id).update(status='paused')
                logger.warning(f'Offer {offer.id} paused — {cap.cap_type} cap reached.')
                break


# ══════════════════════════════════════════════════════
# FRAUD SERVICE
# ══════════════════════════════════════════════════════

class FraudService:

    @staticmethod
    def pre_click_check(ip: str, user, user_agent: str):
        """Click-এর আগে সব fraud check।"""
        # 1. IP blocked?
        if FraudRepository.is_ip_blocked(ip):
            raise IPBlockedException()

        # 2. User suspended?
        risk = FraudRepository.get_user_risk_profile(user.id)
        if risk and risk.is_suspended:
            from .exceptions import UserSuspendedException
            raise UserSuspendedException()

        # 3. High risk user?
        if risk and risk.risk_score >= AUTO_BLOCK_SCORE:
            FraudRepository.block_ip(ip, reason='auto_high_risk')
            raise FraudDetectedException()

        # 4. VPN/Proxy check (basic)
        FraudService._check_vpn(ip)

        # 5. User-agent bot check
        FraudService._check_user_agent(user_agent)

    @staticmethod
    def _check_vpn(ip: str):
        from .models import ProxyList, VPNProvider
        import ipaddress
        try:
            ip_obj = ipaddress.ip_address(ip)
            for proxy in ProxyList.objects.filter(is_active=True):
                try:
                    network = ipaddress.ip_network(proxy.ip_range, strict=False)
                    if ip_obj in network:
                        raise VPNDetectedException()
                except ValueError:
                    continue
        except VPNDetectedException:
            raise
        except Exception:
            pass

    @staticmethod
    def _check_user_agent(user_agent: str):
        """Known bot UA detect।"""
        import re
        from .models import UserAgentBlacklist
        ua_lower = user_agent.lower()
        bot_keywords = ['bot', 'crawl', 'spider', 'scraper', 'headless', 'phantom', 'selenium']
        for keyword in bot_keywords:
            if keyword in ua_lower:
                raise FraudDetectedException()

    @staticmethod
    def evaluate_conversion(conversion) -> float:
        """Conversion-এর fraud score calculate।"""
        score = 0.0

        # Click-to-conversion time too fast?
        if conversion.click:
            delta = (conversion.created_at - conversion.click.created_at).total_seconds()
            if delta < 30:  # 30 সেকেন্ডের কম
                score += 30

        # IP risk?
        if conversion.ip_address:
            risk = FraudRepository.is_ip_blocked(conversion.ip_address)
            if risk:
                score += 40

        # User risk?
        user_risk = FraudRepository.get_user_risk_profile(conversion.user_id)
        if user_risk:
            score += user_risk.risk_score * 0.3

        return min(100.0, score)

    @staticmethod
    def auto_evaluate_and_act(conversion):
        """Conversion evaluate করে action নাও।"""
        score = FraudService.evaluate_conversion(conversion)
        if score >= FRAUD_SCORE_THRESHOLD:
            ConversionRepository.reject_conversion(
                str(conversion.id), f'Auto-rejected: fraud score {score:.1f}'
            )
            FraudRepository.update_risk_score(conversion.user_id, score_delta=10)
            logger.warning(f'Conversion {conversion.id} auto-rejected. Score: {score}')
        return score


# ══════════════════════════════════════════════════════
# WITHDRAWAL SERVICE
# ══════════════════════════════════════════════════════

class WithdrawalService:

    @staticmethod
    @transaction.atomic
    def create_withdrawal(user, amount: Decimal, payment_method_id: str, tenant=None) -> object:
        """
        Withdrawal request তৈরি।
        সব validation + balance check।
        """
        from .models import WithdrawalRequest, PaymentMethod, UserKYC

        # 1. Amount validation
        if amount < MIN_WITHDRAWAL_BDT:
            raise MinWithdrawalException()
        if amount > MAX_WITHDRAWAL_BDT:
            raise MaxWithdrawalException()

        # 2. KYC check
        try:
            kyc = UserKYC.objects.get(user=user, status='approved')
        except UserKYC.DoesNotExist:
            raise KYCRequiredException()

        # 3. Payment method
        try:
            method = PaymentMethod.objects.get(id=payment_method_id, user=user, is_verified=True)
        except PaymentMethod.DoesNotExist:
            from .exceptions import PaymentMethodNotFoundException
            raise PaymentMethodNotFoundException()

        # 4. Balance check
        try:
            from api.wallet.models import Wallet
            wallet = Wallet.objects.get(user=user)
            if wallet.is_locked:
                raise WalletLockedException()
            if wallet.available_balance < amount:
                raise InsufficientBalanceException()
        except ImportError:
            # api.wallet not installed — check via WalletTransaction sum
            from django.db.models import Sum as _Sum
            credits = WalletTransaction.objects.filter(user=user, tx_type='credit').aggregate(t=_Sum('amount'))['t'] or Decimal('0')
            debits  = WalletTransaction.objects.filter(user=user, tx_type='debit').aggregate(t=_Sum('amount'))['t'] or Decimal('0')
            balance = credits - debits
            if balance < amount:
                raise InsufficientBalanceException()

        # 5. Fee calculation
        fee = (amount * Decimal(str(DEFAULT_PLATFORM_FEE_PCT)) / Decimal('100')).quantize(Decimal('0.01'))
        import uuid
        ref = f'WD-{str(uuid.uuid4())[:8].upper()}'

        # 6. Create request
        request = WithdrawalRequest.objects.create(
            tenant=tenant,
            user=user,
            payment_method=method,
            amount=amount,
            fee=fee,
            currency='BDT',
            reference_no=ref,
        )

        # 7. Hold balance
        WalletRepository.debit_user(
            user_id=user.id,
            amount=amount,
            source='withdrawal',
            source_id=str(request.id),
            description=f'Withdrawal request {ref}',
        )

        # 8. Notify user
        NotificationRepository.create(
            user_id=user.id,
            notif_type='payment',
            title='উইথড্রয়াল অনুরোধ পাঠানো হয়েছে',
            body=f'{amount} টাকা উইথড্রয়ালের অনুরোধ প্রক্রিয়া করা হচ্ছে।',
        )

        logger.info(f'Withdrawal request created: {ref} | user={user.id} | amount={amount}')
        return request

    @staticmethod
    @transaction.atomic
    def approve_withdrawal(withdrawal_id: str, admin_user) -> object:
        from .models import WithdrawalRequest
        req = WithdrawalRequest.objects.select_for_update().get(
            id=withdrawal_id, status='pending'
        )
        req.status       = 'approved'
        req.processed_by = admin_user
        req.processed_at = timezone.now()
        req.save()

        NotificationRepository.create(
            user_id=req.user_id,
            notif_type='payment',
            title='✅ উইথড্রয়াল অনুমোদিত!',
            body=f'{req.net_amount} টাকা আপনার {req.payment_method.provider} নম্বরে পাঠানো হয়েছে।',
        )
        return req

    @staticmethod
    @transaction.atomic
    def reject_withdrawal(withdrawal_id: str, admin_user, reason: str) -> object:
        from .models import WithdrawalRequest
        req = WithdrawalRequest.objects.select_for_update().get(
            id=withdrawal_id, status='pending'
        )
        req.status          = 'rejected'
        req.rejected_reason = reason
        req.processed_by    = admin_user
        req.processed_at    = timezone.now()
        req.save()

        # Refund wallet
        WalletRepository.credit_user(
            user_id=req.user_id,
            amount=req.amount,
            source='refund',
            source_id=str(req.id),
            description=f'উইথড্রয়াল বাতিল ফেরত: {reason}',
        )

        NotificationRepository.create(
            user_id=req.user_id,
            notif_type='warning',
            title='❌ উইথড্রয়াল বাতিল',
            body=f'কারণ: {reason}। আপনার {req.amount} টাকা ওয়ালেটে ফেরত এসেছে।',
        )
        return req


# ══════════════════════════════════════════════════════
# POSTBACK SERVICE
# ══════════════════════════════════════════════════════

class PostbackService:

    @staticmethod
    def deliver(conversion_id: str, retry: int = 0):
        """Network-এ postback পাঠাও।"""
        import requests
        from .models import PostbackLog

        conversion = ConversionRepository.get_by_id(conversion_id)
        if not conversion or not conversion.offer.network:
            return False

        network = conversion.offer.network
        if not network.postback_url:
            return True

        url = network.postback_url.format(
            click_id=str(conversion.click_id) if conversion.click else '',
            transaction_id=conversion.transaction_id,
            payout=str(conversion.payout_amount),
            status='approved',
        )

        log = PostbackLog.objects.create(
            conversion=conversion,
            url=url,
            method='GET',
            retry_count=retry,
        )

        try:
            resp = requests.get(url, timeout=10)
            log.response_code = resp.status_code
            log.response_body = resp.text[:500]
            log.is_success    = resp.status_code == 200
            log.save()

            if log.is_success:
                ConversionRepository.mark_postback_sent(conversion_id)
            else:
                PostbackService._schedule_retry(conversion_id, retry)

        except Exception as e:
            log.response_body = str(e)
            log.is_success    = False
            log.save()
            PostbackService._schedule_retry(conversion_id, retry)

        return log.is_success

    @staticmethod
    def _schedule_retry(conversion_id: str, current_retry: int):
        from .constants import POSTBACK_RETRY_LIMIT, POSTBACK_RETRY_DELAY
        from api.offer_inventory.tasks import deliver_postback
        if current_retry < POSTBACK_RETRY_LIMIT:
            deliver_postback.apply_async(
                args=[conversion_id, current_retry + 1],
                countdown=POSTBACK_RETRY_DELAY * (current_retry + 1),
            )


# ══════════════════════════════════════════════════════
# WIRING TO NEW PRODUCTION MODULES
# ══════════════════════════════════════════════════════

class ConversionServiceV2:
    """
    Production-grade conversion service.
    Delegates to ConversionTracker (bulletproof dedup + locking).
    """

    @staticmethod
    def process(click_token: str, transaction_id: str,
                 payout: Decimal, raw_data: dict,
                 ip_address: str = '') -> object:
        """
        Bulletproof conversion recording.
        Uses Redis lock + DB select_for_update + 4-layer dedup.
        """
        from api.offer_inventory.conversion_tracking import ConversionTracker
        return ConversionTracker.record(
            click_token    = click_token,
            transaction_id = transaction_id,
            payout         = payout,
            raw_data       = raw_data,
            ip_address     = ip_address,
        )

    @staticmethod
    def approve_and_pay(conversion_id: str) -> dict:
        """
        Approve + pay in one call.
        Uses PayoutEngine with double-pay prevention.
        """
        from api.offer_inventory.payout_engine import PayoutEngine
        from api.offer_inventory.models import Conversion, ConversionStatus
        from django.utils import timezone

        # Mark approved
        approved_status = ConversionStatus.objects.get(name='approved')
        Conversion.objects.filter(
            id=conversion_id, status__name='pending'
        ).update(status=approved_status)

        # Pay
        return PayoutEngine.pay_conversion(conversion_id)


class ClickServiceV2:
    """
    Production click recording — delegates to ClickTracker.
    Full bot check + dedup + signing.
    """

    @staticmethod
    def record(offer, user, request_meta: dict) -> object:
        from api.offer_inventory.click_tracker import ClickTracker
        return ClickTracker.record(offer, user, request_meta)

    @staticmethod
    def get_by_token(token: str):
        from api.offer_inventory.click_tracker import ClickTracker
        return ClickTracker.get_by_token(token)


class FraudServiceV2:
    """
    Production fraud detection — uses FraudDetectionEngine.
    Multi-signal composite scoring.
    """

    @staticmethod
    def evaluate(request, user=None, offer=None) -> object:
        from api.offer_inventory.fraud_detection import FraudDetectionEngine
        return FraudDetectionEngine.evaluate(request, user=user, offer=offer)

    @staticmethod
    def evaluate_conversion(conversion) -> object:
        from api.offer_inventory.fraud_detection import FraudDetectionEngine
        return FraudDetectionEngine.evaluate_conversion(conversion)


class ReportingServiceV2:
    """Centralized reporting via ReportGenerator."""

    @staticmethod
    def get_report(report_type: str, **kwargs):
        from api.offer_inventory.reporting import ReportGenerator
        handlers = {
            'offer_performance'    : ReportGenerator.offer_performance,
            'conversion_summary'   : ReportGenerator.conversion_summary,
            'postback_delivery'    : ReportGenerator.postback_delivery_report,
            'user_growth'          : ReportGenerator.user_growth,
            'user_ltv'             : ReportGenerator.user_lifetime_value_distribution,
            'payout_reconciliation': ReportGenerator.payout_reconciliation,
            'offer_cap_usage'      : ReportGenerator.offer_cap_usage,
        }
        handler = handlers.get(report_type)
        if not handler:
            raise ValueError(f'Unknown report type: {report_type}')
        return handler(**kwargs)


class WebhookServiceV2:
    """Centralized webhook dispatching."""

    @staticmethod
    def dispatch_postback(network_slug: str, params: dict,
                           source_ip: str, **kwargs):
        from api.offer_inventory.webhooks import WebhookDispatcher
        return WebhookDispatcher.dispatch_postback(
            network_slug, params, source_ip, **kwargs
        )

    @staticmethod
    def fire_event(event: str, payload: dict, tenant=None):
        from api.offer_inventory.webhooks import WebhookDispatcher
        return WebhookDispatcher.deliver_to_all_configs(event, payload, tenant=tenant)
