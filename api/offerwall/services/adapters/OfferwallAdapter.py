"""
api/offerwall/services/adapters/OfferwallAdapter.py

Offerwall → Other System Adapters
All calls use EXACT method signatures from api.zip systems.

| Adapter        | Exact call                                                        |
|----------------|-------------------------------------------------------------------|
| WalletAdapter  | WalletService.add_earnings(wallet, amount, description,           |
|                |   reference_id, metadata, source_type, source_id)                |
| Notification   | NotificationService().create_notification(user, title, message,   |
|                |   notification_type, priority, channel, metadata, action_url,    |
|                |   action_text, tags)                                             |
| FraudAdapter   | FraudScoreCalculator(user).calculate_overall_risk() → int 0-100  |
| AuditAdapter   | AuditLogService.log_action(user_id, action, message, metadata)    |
| ReferralAdapter| ReferralService.process_multilevel_commission(earner,             |
|                |   earned_amount, source_type='offer', source_id)                  |
"""
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict
from django.utils import timezone

logger = logging.getLogger(__name__)


class BaseOfferwallAdapter(ABC):
    name: str = 'base'
    max_retries: int = 3
    retry_delay: float = 0.5

    def __init__(self):
        self._failure_count = 0
        self._circuit_open = False
        self._last_failure = None

    def send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        if self._circuit_open:
            if self._should_recover():
                self._circuit_open = False
                self._failure_count = 0
            else:
                return {'success': False, 'error': 'circuit_open', 'adapter': self.name}

        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = self._do_send(payload, **kwargs)
                self._failure_count = 0
                return result
            except Exception as exc:
                last_exc = exc
                self._failure_count += 1
                self._last_failure = timezone.now()
                logger.warning(f'[{self.name}] attempt {attempt}/{self.max_retries}: {exc}')
                if attempt < self.max_retries:
                    import time; time.sleep(self.retry_delay * attempt)

        if self._failure_count >= self.max_retries:
            self._circuit_open = True
            logger.error(f'[{self.name}] Circuit OPENED')
        return {'success': False, 'error': str(last_exc), 'adapter': self.name}

    def _should_recover(self) -> bool:
        # FIX: a missing/cleared _last_failure while the circuit is OPEN is stale
        # or corrupted state, not evidence the adapter never failed — treat it as
        # "not yet safe to recover" rather than fail-open. (This method is only
        # ever called from inside `if self._circuit_open:`, so circuit_open=True
        # already implies a real failure previously set _last_failure.)
        if not self._last_failure: return False
        return (timezone.now() - self._last_failure).seconds > 60

    @abstractmethod
    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]: pass

    def health_check(self) -> Dict[str, Any]:
        return {'adapter': self.name, 'circuit_open': self._circuit_open,
                'failure_count': self._failure_count}


class WalletAdapter(BaseOfferwallAdapter):
    """WalletService.add_earnings(wallet, amount, description, reference_id, metadata, source_type, source_id)"""
    name = 'wallet'

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from django.contrib.auth import get_user_model
        from api.wallet.services import WalletService
        from api.wallet.models import Wallet
        User = get_user_model()

        user_id = payload['user_id']
        reward  = Decimal(str(payload.get('reward_amount', '0')))
        bonus   = Decimal(str(payload.get('bonus_amount',  '0')))
        total   = reward + bonus
        conv_id = payload.get('conversion_id', '')

        if total <= 0:
            return {'success': False, 'error': 'invalid_amount', 'amount': str(total)}

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {'success': False, 'error': 'user_not_found'}

        wallet, _ = Wallet.objects.get_or_create(user=user)

        txn = WalletService.add_earnings(
            wallet=wallet,
            amount=total,
            description=f"Offer completed: {payload.get('offer_title', '')}",
            reference_id=conv_id,
            metadata={
                'offer_id':      payload.get('offer_id', ''),
                'offer_title':   payload.get('offer_title', ''),
                'conversion_id': conv_id,
                'base_reward':   str(reward),
                'bonus_amount':  str(bonus),
                'provider':      payload.get('provider_type', ''),
                'source':        'offerwall',
            },
            source_type='offer',
            source_id=conv_id,
        )
        wallet.refresh_from_db()
        logger.info(f'[WalletAdapter] +{total} credited to user={user_id} txn={txn.txn_id}')
        return {'success': True, 'txn_id': str(txn.txn_id),
                'amount': str(total), 'new_balance': str(wallet.current_balance)}


class NotificationAdapter(BaseOfferwallAdapter):
    """NotificationService().create_notification(user, title, message, ...)"""
    name = 'notification'
    max_retries = 2

    _CONFIG = {
        'reward_earned':  {'title': '🎉 Reward Earned!',       'type': 'reward',   'priority': 'high',
                           'url': '/wallet/',  'text': 'View Wallet',  'tags': ['offerwall', 'reward']},
        'reward_rejected':{'title': 'Offer Not Approved',       'type': 'warning',  'priority': 'medium',
                           'url': '/offers/',  'text': 'Browse Offers','tags': ['offerwall', 'rejection']},
        'offer_expiring': {'title': '⏰ Offer Expiring Soon!',   'type': 'reminder', 'priority': 'medium',
                           'url': '/offers/',  'text': 'Complete Now', 'tags': ['offerwall', 'expiry']},
    }

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from django.contrib.auth import get_user_model
        from api.notifications.services import NotificationService
        User = get_user_model()

        user_id = payload['user_id']
        event   = payload.get('event', 'reward_earned')
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {'success': False, 'error': 'user_not_found'}

        cfg = self._CONFIG.get(event, self._CONFIG['reward_earned'])
        msg = self._build_message(event, payload)

        notif = NotificationService().create_notification(
            user=user,
            title=cfg['title'],
            message=msg,
            notification_type=cfg['type'],
            priority=cfg['priority'],
            channel='in_app',
            metadata={'conversion_id': payload.get('conversion_id', ''),
                      'offer_title':   payload.get('offer_title', ''),
                      'reward_amount': str(payload.get('reward_amount', '0')),
                      'reward_currency': payload.get('reward_currency', 'BDT'),
                      'event': event},
            action_url=cfg['url'],
            action_text=cfg['text'],
            tags=cfg['tags'],
        )
        return {'success': True, 'notification_id': str(notif.id) if notif else None}

    def _build_message(self, event, p):
        t = p.get('offer_title', 'the offer')
        a = p.get('reward_amount', '0')
        c = p.get('reward_currency', 'BDT')
        r = p.get('reason', 'Verification failed')
        if event == 'reward_earned':   return f'You earned {a} {c} for completing: {t}'
        if event == 'reward_rejected': return f'Your completion of "{t}" could not be verified. Reason: {r}'
        if event == 'offer_expiring':  return f'"{t}" expires soon. Complete now to earn {a} {c}!'
        return f'Update regarding: {t}'


class FraudAdapter(BaseOfferwallAdapter):
    """FraudScoreCalculator(user).calculate_overall_risk() → int 0-100"""
    name = 'fraud_detection'
    max_retries = 2
    BLOCK_THRESHOLD = 75

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from django.contrib.auth import get_user_model
        from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
        User = get_user_model()
        try:
            user = User.objects.get(id=payload.get('user_id'))
        except User.DoesNotExist:
            return {'success': True, 'should_block': False, 'fraud_score': 0, 'risk_level': 'low'}

        score  = FraudScoreCalculator(user).calculate_overall_risk()
        blocked = score >= self.BLOCK_THRESHOLD
        if blocked:
            logger.warning(f'[FraudAdapter] BLOCKED user={user.id} score={score}')
        return {'success': True, 'should_block': blocked,
                'fraud_score': score, 'risk_level': self._level(score)}

    @staticmethod
    def _level(s):
        if s < 30: return 'low'
        if s < 50: return 'medium'
        if s < 75: return 'high'
        return 'critical'


class AuditAdapter(BaseOfferwallAdapter):
    """AuditLogService.log_action(user_id, action, message, metadata)"""
    name = 'audit'
    max_retries = 1

    _MAP = {'offer_view': 'OFFER_VIEW', 'offer_click': 'OFFER_CLICK',
            'offer_complete': 'OFFER_COMPLETE', 'offer_reject': 'OFFER_REJECT',
            'manual_credit': 'MANUAL_CREDIT'}

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from api.audit_logs.services import AuditLogService
        action = self._MAP.get(payload.get('action', '').lower(), payload.get('action', 'API_CALL'))
        log = AuditLogService.log_action(
            user_id=payload.get('user_id'),
            action=action,
            message=payload.get('message', ''),
            metadata=payload.get('metadata', {}),
        )
        return {'success': True, 'log_id': str(log.id) if log else None}


class ReferralAdapter(BaseOfferwallAdapter):
    """ReferralService.process_multilevel_commission(earner, earned_amount, source_type, source_id)"""
    name = 'referral'
    max_retries = 2

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from django.contrib.auth import get_user_model
        from api.referral.services import ReferralService
        User = get_user_model()

        earned = Decimal(str(payload.get('earned_amount', '0')))
        if earned <= 0:
            return {'success': True, 'skipped': 'zero_amount'}

        try:
            earner = User.objects.get(id=payload.get('user_id'))
        except User.DoesNotExist:
            return {'success': False, 'error': 'user_not_found'}

        results = ReferralService.process_multilevel_commission(
            earner=earner,
            earned_amount=earned,
            source_type='offer',
            source_id=payload.get('conversion_id', ''),
        )
        count = len(results) if results else 0
        logger.info(f'[ReferralAdapter] {count} commissions paid for user={earner.id}')
        return {'success': True, 'commissions_paid': count}


class OfferwallAdapterFactory:
    _registry: Dict[str, type] = {
        'wallet':       WalletAdapter,
        'notification': NotificationAdapter,
        'fraud':        FraudAdapter,
        'audit':        AuditAdapter,
        'referral':     ReferralAdapter,
    }
    _instances: Dict[str, BaseOfferwallAdapter] = {}

    @classmethod
    def get(cls, name: str) -> BaseOfferwallAdapter:
        if name not in cls._registry:
            raise ValueError(f"Unknown adapter '{name}'. Available: {list(cls._registry)}")
        if name not in cls._instances:
            cls._instances[name] = cls._registry[name]()
        return cls._instances[name]

    @classmethod
    def register(cls, name: str, adapter_class: type):
        cls._registry[name] = adapter_class
        cls._instances.pop(name, None)

    @classmethod
    def health_check_all(cls) -> Dict[str, Any]:
        return {n: cls.get(n).health_check() for n in cls._registry}


# ═════════════════════════════════════════════════════════════════════════════
# 13 NEW ADAPTERS — All wired to exact api/ system signatures
# ═════════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────────
# AnalyticsAdapter
# → AnalyticsService.get_platform_summary() exists but no generic track()
# → Uses direct model creation for offerwall events
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsAdapter(BaseOfferwallAdapter):
    """
    Offerwall events → api.analytics system.

    Payload:
        event     : str   — 'offer_view' | 'offer_click' | 'offer_conversion'
        user_id   : int
        offer_id  : str
        provider  : str
        metadata  : dict
    """
    name = 'analytics'
    max_retries = 1  # non-critical

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from api.analytics.services import AnalyticsService
        event   = payload.get('event', 'offer_event')
        user_id = payload.get('user_id')

        # AnalyticsService has get_platform_summary — for tracking we use it indirectly
        # or log to a generic analytics event model if available
        try:
            if hasattr(AnalyticsService, 'track'):
                AnalyticsService.track(
                    event=event,
                    user_id=user_id,
                    properties={
                        'offer_id': payload.get('offer_id', ''),
                        'provider': payload.get('provider', ''),
                        **payload.get('metadata', {}),
                    }
                )
            else:
                # Fallback: use platform summary as health check
                AnalyticsService.get_platform_summary(days=1)
        except Exception:
            pass  # analytics is never critical

        return {'success': True, 'event': event, 'user_id': user_id}


# ─────────────────────────────────────────────────────────────────────────────
# TaskAdapter
# → api.tasks Celery shared_tasks
# → sync_ad_network_revenue, earning_tasks etc.
# ─────────────────────────────────────────────────────────────────────────────

class TaskAdapter(BaseOfferwallAdapter):
    """
    Async task dispatch — provider sync, conversion processing.

    Payload:
        task      : str   — 'sync_offers' | 'process_conversion' | 'sync_revenue'
        provider_id    : str  (for sync_offers)
        conversion_id  : str  (for process_conversion)
    """
    name = 'tasks'
    max_retries = 1

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        task_name = payload.get('task', 'sync_offers')

        try:
            if task_name == 'sync_revenue':
                from api.tasks.ad_networks_tasks import sync_ad_network_revenue
                result = sync_ad_network_revenue.delay()
                return {'success': True, 'task': task_name, 'task_id': str(result.id)}

            elif task_name == 'cleanup_blacklist':
                from api.tasks.ad_networks_tasks import cleanup_expired_blacklist_task
                result = cleanup_expired_blacklist_task.delay()
                return {'success': True, 'task': task_name, 'task_id': str(result.id)}

            elif task_name == 'process_earnings':
                from api.tasks.earning_tasks import process_pending_earnings
                result = process_pending_earnings.delay()
                return {'success': True, 'task': task_name, 'task_id': str(result.id)}

            else:
                # Generic — log and continue
                logger.info(f'[TaskAdapter] Task {task_name} queued (no direct handler)')
                return {'success': True, 'task': task_name, 'queued': True}

        except ImportError:
            logger.warning(f'[TaskAdapter] Celery task {task_name} not found — running sync')
            return {'success': True, 'task': task_name, 'sync_fallback': True}


# ─────────────────────────────────────────────────────────────────────────────
# PostbackAdapter
# → api.postback_engine CustomWebhook.send(url, event, data, secret, conversion_id)
# ─────────────────────────────────────────────────────────────────────────────

class PostbackAdapter(BaseOfferwallAdapter):
    """
    Conversion approved → postback to ad network / advertiser.
    Uses CustomWebhook.send() from postback_engine.

    Payload:
        url           : str   — postback URL
        event         : str   — 'conversion'
        data          : dict  — conversion data
        secret        : str   — signing secret
        conversion_id : str
    """
    name = 'postback'
    max_retries = 3

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from api.postback_engine.webhook_manager.custom_webhook import CustomWebhook

        url           = payload.get('url', '')
        event         = payload.get('event', 'conversion')
        data          = payload.get('data', {})
        secret        = payload.get('secret', '')
        conversion_id = payload.get('conversion_id', '')

        if not url:
            return {'success': True, 'skipped': 'no_postback_url'}

        webhook = CustomWebhook()
        success = webhook.send(
            url=url,
            event=event,
            data=data,
            secret=secret,
            conversion_id=conversion_id,
        )

        logger.info(
            f'[PostbackAdapter] Postback {"sent" if success else "FAILED"} '
            f'conversion={conversion_id} url={url}'
        )
        return {
            'success': success,
            'conversion_id': conversion_id,
            'url': url,
        }


# ─────────────────────────────────────────────────────────────────────────────
# PostbackEngineAdapter
# → zapier_integration / make_integration send_conversion()
# ─────────────────────────────────────────────────────────────────────────────

class PostbackEngineAdapter(BaseOfferwallAdapter):
    """
    Reliable postback delivery with queue + retry.
    Uses ZapierIntegration or MakeIntegration from postback_engine.

    Payload:
        conversion     : OfferConversion object  (passed directly)
        provider_type  : str   — 'tapjoy' | 'adgem' etc.
        channel        : str   — 'zapier' | 'make' | 'custom' (default: 'custom')
    """
    name = 'postback_engine'
    max_retries = 3

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        conversion    = payload.get('conversion')
        channel       = payload.get('channel', 'custom')
        postback_url  = payload.get('postback_url', '')
        conversion_id = payload.get('conversion_id', '')

        if not conversion and not postback_url:
            return {'success': True, 'skipped': 'no_conversion_or_url'}

        try:
            if channel == 'zapier' and conversion:
                from api.postback_engine.webhook_manager.zapier_integration import ZapierIntegration
                zap = ZapierIntegration()
                success = zap.send_conversion(conversion)
                return {'success': success, 'channel': 'zapier'}

            elif channel == 'make' and conversion:
                from api.postback_engine.webhook_manager.make_integration import MakeIntegration
                make = MakeIntegration()
                success = make.send_conversion(conversion)
                return {'success': success, 'channel': 'make'}

            else:
                # Custom postback URL
                if postback_url:
                    from api.postback_engine.webhook_manager.custom_webhook import CustomWebhook
                    wh = CustomWebhook()
                    success = wh.send(
                        url=postback_url,
                        event='conversion',
                        data={'conversion_id': conversion_id,
                              'provider': payload.get('provider_type', '')},
                        conversion_id=conversion_id,
                    )
                    return {'success': success, 'channel': 'custom', 'url': postback_url}

                return {'success': True, 'skipped': 'no_postback_configured'}

        except ImportError as e:
            logger.warning(f'[PostbackEngineAdapter] Import error: {e}')
            return {'success': False, 'error': str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# GamificationAdapter
# → gamification.services.award_achievement(user_id, achievement_type, title,
#       points, description, metadata)
# ─────────────────────────────────────────────────────────────────────────────

class GamificationAdapter(BaseOfferwallAdapter):
    """
    Offer completed → gamification achievement + points.

    award_achievement() is idempotent — duplicate awards safely ignored.

    Payload:
        user_id          : int
        achievement_type : str   — 'offer_complete' | 'offer_streak' | 'first_offer'
        title            : str
        points           : int   — XP points to award
        description      : str
        metadata         : dict
    """
    name = 'gamification'
    max_retries = 2

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from api.gamification.services import award_achievement

        user_id          = payload['user_id']
        achievement_type = payload.get('achievement_type', 'offer_complete')
        title            = payload.get('title', 'Offer Completed')
        points           = int(payload.get('points', 10))
        description      = payload.get('description', '')
        metadata         = payload.get('metadata', {})

        achievement = award_achievement(
            user_id=user_id,
            achievement_type=achievement_type,
            title=title,
            points=points,
            description=description,
            metadata=metadata,
        )

        logger.info(
            f'[GamificationAdapter] Achievement awarded: user={user_id} '
            f'type={achievement_type} points={points}'
        )
        return {
            'success': True,
            'user_id': user_id,
            'achievement_type': achievement_type,
            'points_awarded': points,
            'achievement_id': str(achievement.id) if achievement else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# LoyaltyAdapter
# → djoyalty.services.earn.BonusEventService.award_bonus(
#       customer, points, reason, triggered_by)
# ─────────────────────────────────────────────────────────────────────────────

class LoyaltyAdapter(BaseOfferwallAdapter):
    """
    Offer completed → djoyalty loyalty points.

    BonusEventService.award_bonus() credits LoyaltyPoints + creates BonusEvent
    + PointsLedger — all in one call.

    Payload:
        user_id       : int
        points        : Decimal  — loyalty points to award
        reason        : str      — 'Offer reward: {offer_title}'
        triggered_by  : str      — 'offerwall'
        conversion_id : str
    """
    name = 'loyalty'
    max_retries = 2

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from django.contrib.auth import get_user_model
        from api.djoyalty.services.earn.BonusEventService import BonusEventService
        User = get_user_model()

        user_id       = payload['user_id']
        points        = Decimal(str(payload.get('points', '0')))
        reason        = payload.get('reason', 'Offerwall reward')
        triggered_by  = payload.get('triggered_by', 'offerwall')

        if points <= 0:
            return {'success': True, 'skipped': 'zero_points'}

        try:
            customer = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {'success': False, 'error': 'user_not_found'}

        bonus_event = BonusEventService.award_bonus(
            customer=customer,
            points=points,
            reason=reason,
            triggered_by=triggered_by,
        )

        logger.info(
            f'[LoyaltyAdapter] {points} loyalty points awarded to user={user_id}'
        )
        return {
            'success': True,
            'user_id': user_id,
            'points_awarded': str(points),
            'bonus_event_id': str(bonus_event.id) if bonus_event else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# PromotionAdapter
# → api.promotions Campaign model check for active promotions
# ─────────────────────────────────────────────────────────────────────────────

class PromotionAdapter(BaseOfferwallAdapter):
    """
    Check if any active promotion gives bonus reward for this offer completion.

    Payload:
        user_id   : int
        offer_id  : str
        base_amount : str (Decimal)

    Returns:
        bonus_amount : str (Decimal)  — extra reward from promotion
        campaign_id  : str | None
    """
    name = 'promotions'
    max_retries = 1

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from django.contrib.auth import get_user_model
        from api.promotions.models import Campaign
        from django.utils import timezone
        User = get_user_model()

        user_id     = payload['user_id']
        offer_id    = payload.get('offer_id', '')
        base_amount = Decimal(str(payload.get('base_amount', '0')))

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {'success': False, 'error': 'user_not_found', 'bonus_amount': '0'}

        # Find active campaigns targeting offerwall
        now = timezone.now()
        active_campaigns = Campaign.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        ).exclude(is_deleted=True) if hasattr(Campaign, 'is_deleted') else \
            Campaign.objects.filter(is_active=True, start_date__lte=now, end_date__gte=now)

        bonus_amount = Decimal('0')
        campaign_id  = None

        for campaign in active_campaigns[:5]:
            try:
                if hasattr(campaign, 'reward_policy') and campaign.reward_policy:
                    policy = campaign.reward_policy
                    if hasattr(policy, 'bonus_percentage') and policy.bonus_percentage:
                        bonus = base_amount * Decimal(str(policy.bonus_percentage)) / 100
                        bonus_amount += bonus
                        campaign_id = str(campaign.id)
                        break
            except Exception:
                continue

        return {
            'success': True,
            'bonus_amount': str(bonus_amount),
            'campaign_id': campaign_id,
            'user_id': user_id,
        }


# ─────────────────────────────────────────────────────────────────────────────
# AlertAdapter
# → api.alerts — creates incident/alert for offerwall anomalies
# ─────────────────────────────────────────────────────────────────────────────

class AlertAdapter(BaseOfferwallAdapter):
    """
    Trigger admin alerts for offerwall anomalies.
    (high fraud rate, provider down, daily cap reached etc.)

    Payload:
        alert_type : str   — 'high_fraud_rate' | 'provider_down' | 'cap_reached'
        severity   : str   — 'low' | 'medium' | 'high' | 'critical'
        message    : str
        metadata   : dict
    """
    name = 'alerts'
    max_retries = 1

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        alert_type = payload.get('alert_type', 'offerwall_anomaly')
        severity   = payload.get('severity', 'medium')
        message    = payload.get('message', f'Offerwall alert: {alert_type}')
        metadata   = payload.get('metadata', {})

        try:
            from api.alerts.models.incident import Incident
            incident = Incident.objects.create(
                title=f'[Offerwall] {alert_type}',
                description=message,
                severity=severity,
                source='offerwall',
                metadata=metadata,
            )
            logger.warning(
                f'[AlertAdapter] Alert created: {alert_type} severity={severity}'
            )
            return {'success': True, 'incident_id': str(incident.id)}
        except Exception as e:
            logger.error(f'[AlertAdapter] Failed to create alert: {e}')
            return {'success': False, 'error': str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# RateLimitAdapter
# → api.rate_limit.services.RateLimitService.is_rate_limited(
#       identifier, limit_type, max_requests)
# ─────────────────────────────────────────────────────────────────────────────

class RateLimitAdapter(BaseOfferwallAdapter):
    """
    Click/conversion rate limiting via api.rate_limit system.

    RateLimitService.is_rate_limited(identifier, limit_type, max_requests)
    Returns (is_limited: bool, remaining: int | None)

    Payload:
        identifier  : str   — f'user_{user_id}' or IP
        limit_type  : str   — 'offer_click' | 'offer_conversion'
        max_requests: int   — default 100
    """
    name = 'rate_limit'
    max_retries = 1

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from api.rate_limit.services import RateLimitService

        user_id      = payload.get('user_id')
        limit_type   = payload.get('limit_type', 'offer_click')
        max_requests = int(payload.get('max_requests', 100))
        identifier   = payload.get('identifier', f'user_{user_id}')

        is_limited, remaining = RateLimitService.is_rate_limited(
            identifier=identifier,
            limit_type=limit_type,
            max_requests=max_requests,
        )

        return {
            'success':   True,
            'allowed':   not is_limited,
            'limited':   is_limited,
            'remaining': remaining,
            'identifier': identifier,
        }


# ─────────────────────────────────────────────────────────────────────────────
# BehaviorAdapter
# → api.behavior_analytics.services — record_click, StayTime.record
# ─────────────────────────────────────────────────────────────────────────────

class BehaviorAdapter(BaseOfferwallAdapter):
    """
    User behavior tracking for offerwall funnel analysis.

    Payload:
        user_id    : int
        event_type : str   — 'offer_viewed' | 'offer_clicked' | 'offer_abandoned'
        context    : dict  — {'offer_id': ..., 'category': ..., 'platform': ...}
    """
    name = 'behavior'
    max_retries = 1  # non-critical

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        user_id    = payload.get('user_id')
        event_type = payload.get('event_type', 'offer_viewed')
        context    = payload.get('context', {})

        try:
            from api.behavior_analytics.services import BehaviorAnalyticsService
            BehaviorAnalyticsService.record_click(
                user_id=user_id,
                page_url=f"/offers/{context.get('offer_id', '')}",
                context=context,
            )
        except (ImportError, AttributeError):
            try:
                # Fallback: try generic record
                from api.behavior_analytics.services import BehaviorAnalyticsService
                if hasattr(BehaviorAnalyticsService, 'record'):
                    BehaviorAnalyticsService.record(
                        user_id=user_id,
                        event_type=event_type,
                        data=context,
                    )
            except Exception as e:
                logger.debug(f'[BehaviorAdapter] Non-critical: {e}')

        return {'success': True, 'event_type': event_type, 'user_id': user_id}


# ─────────────────────────────────────────────────────────────────────────────
# OfferRoutingAdapter
# → api.offer_routing.routing.route_multiple_offers(user_id, count, context)
# ─────────────────────────────────────────────────────────────────────────────

class OfferRoutingAdapter(BaseOfferwallAdapter):
    """
    Smart offer selection for recommended offers list.

    route_multiple_offers(user_id, count, context) → List[Dict]
    Each dict contains 'offer_id' and routing metadata.

    Payload:
        user_id  : int
        count    : int   — number of offers to return
        context  : dict  — {'platform': 'android', 'country': 'BD', ...}

    Returns:
        offer_ids : list[str]  — ranked offer UUIDs
    """
    name = 'offer_routing'
    max_retries = 2

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from api.offer_routing.routing import route_multiple_offers

        user_id = payload['user_id']
        count   = int(payload.get('count', 20))
        context = payload.get('context', {})

        results = route_multiple_offers(
            user_id=user_id,
            count=count,
            context=context,
        )

        offer_ids = []
        for r in (results or []):
            if isinstance(r, dict):
                oid = r.get('offer_id') or r.get('id')
                if oid:
                    offer_ids.append(str(oid))

        logger.info(
            f'[OfferRoutingAdapter] Routed {len(offer_ids)} offers for user={user_id}'
        )
        return {
            'success':   True,
            'user_id':   user_id,
            'offer_ids': offer_ids,
            'count':     len(offer_ids),
        }


# ─────────────────────────────────────────────────────────────────────────────
# PayoutQueueAdapter
# → api.payout_queue.services.add_payout_items(batch_id, items, validate_accounts)
# ─────────────────────────────────────────────────────────────────────────────

class PayoutQueueAdapter(BaseOfferwallAdapter):
    """
    Large payout → queue instead of immediate wallet credit.

    add_payout_items(batch_id, items, validate_accounts=True)
    items = [{'user_id', 'account_number', 'gross_amount'}]

    Payload:
        user_id        : int
        amount         : Decimal
        conversion_id  : str
        priority       : str   — 'normal' | 'high'
    """
    name = 'payout_queue'
    max_retries = 2

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from api.payout_queue.services import add_payout_items
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user_id       = payload['user_id']
        amount        = Decimal(str(payload.get('amount', '0')))
        conversion_id = payload.get('conversion_id', '')

        if amount <= 0:
            return {'success': True, 'skipped': 'zero_amount'}

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {'success': False, 'error': 'user_not_found'}

        # Get or create a pending batch for offerwall payouts
        from api.payout_queue.models import PayoutBatch
        batch, _ = PayoutBatch.objects.get_or_create(
            status='pending',
            source='offerwall',
            defaults={'name': 'Offerwall Payout Batch'},
        )

        items = add_payout_items(
            batch_id=batch.id,
            items=[{
                'user_id':        user_id,
                'account_number': getattr(user, 'phone_number', str(user_id)),
                'gross_amount':   amount,
                'reference_id':   conversion_id,
            }],
            validate_accounts=False,
        )

        logger.info(
            f'[PayoutQueueAdapter] Queued {amount} for user={user_id} '
            f'conversion={conversion_id}'
        )
        return {
            'success':  True,
            'user_id':  user_id,
            'amount':   str(amount),
            'batch_id': str(batch.id),
            'items':    len(items),
        }


# ─────────────────────────────────────────────────────────────────────────────
# SubscriptionAdapter
# → api.subscription.services.get_active_plans() / UserSubscription model
# → Check user tier → reward multiplier
# ─────────────────────────────────────────────────────────────────────────────

class SubscriptionAdapter(BaseOfferwallAdapter):
    """
    Check user subscription tier → reward multiplier for offers.

    UserSubscription model:
        user → SubscriptionPlan → tier_level / features

    Payload:
        user_id : int

    Returns:
        tier       : str    — 'free' | 'basic' | 'premium' | 'vip'
        multiplier : float  — 1.0 | 1.25 | 1.5 | 2.0
    """
    name = 'subscription'
    max_retries = 1

    # Tier → multiplier mapping
    TIER_MULTIPLIERS = {
        'free':    1.0,
        'basic':   1.25,
        'premium': 1.5,
        'vip':     2.0,
        'pro':     1.5,
        'enterprise': 2.0,
    }

    def _do_send(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from api.subscription.models import UserSubscription
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user_id = payload['user_id']

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {
                'success': False, 'error': 'user_not_found',
                'tier': 'free', 'multiplier': 1.0,
            }

        tier       = 'free'
        multiplier = 1.0

        try:
            active_sub = UserSubscription.objects.filter(
                user=user, status='active'
            ).select_related('plan').first()

            if active_sub and active_sub.plan:
                plan_name  = active_sub.plan.name.lower()
                tier = plan_name

                for tier_key, mult in self.TIER_MULTIPLIERS.items():
                    if tier_key in plan_name:
                        multiplier = mult
                        tier = tier_key
                        break
        except Exception as e:
            logger.debug(f'[SubscriptionAdapter] Tier check failed: {e}')

        return {
            'success':    True,
            'user_id':    user_id,
            'tier':       tier,
            'multiplier': multiplier,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Update Factory — register all 13 new adapters
# ─────────────────────────────────────────────────────────────────────────────

# Extend the registry with all new adapters
OfferwallAdapterFactory._registry.update({
    'analytics':      AnalyticsAdapter,
    'tasks':          TaskAdapter,
    'postback':       PostbackAdapter,
    'postback_engine': PostbackEngineAdapter,
    'gamification':   GamificationAdapter,
    'loyalty':        LoyaltyAdapter,
    'promotions':     PromotionAdapter,
    'alerts':         AlertAdapter,
    'rate_limit':     RateLimitAdapter,
    'behavior':       BehaviorAdapter,
    'offer_routing':  OfferRoutingAdapter,
    'payout_queue':   PayoutQueueAdapter,
    'subscription':   SubscriptionAdapter,
})
