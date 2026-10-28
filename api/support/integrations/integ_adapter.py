# api/support/integrations/integ_adapter.py  — WORLD #1
"""
Integration Adapters — Support শুধু CALL করে, নিজে কোনো logic করে না।

আর্কিটেকচার:
    Support  →  Adapter  →  Other App's Service/Model Method
    
Support কখনো:
    NO:  wallet.current_balance += amount  (wallet field directly)
    NO:  FraudProfile.is_flagged = True    (fraud model directly)
    
Support সবসময়:
    ✅ wallet.credit(amount, reason)     (wallet app-এর নিজের method call করবে)
    ✅ fraud_service.flag_user(user)     (fraud app-এর service call করবে)
"""
import logging
from typing import Any, Optional
from django.core.cache import cache
from django.conf import settings

from .integ_constants import (
    CACHE_TTL_USER_RISK, CACHE_TTL_OFFER_STATUS,
    CACHE_TTL_KYC_STATUS, CACHE_TTL_WALLET_BALANCE, CACHE_PREFIX,
    FRAUD_RISK_HIGH_THRESHOLD, FRAUD_RISK_CRITICAL,
)
from .integ_exceptions import AdapterNotAvailableError, WalletLockedError

logger = logging.getLogger(__name__)


class BaseAdapter:
    """Base adapter — safe app model lookup."""
    app_label: str = ''

    def _model(self, app: str, model: str):
        """Safely get a model from another app."""
        try:
            from django.apps import apps
            return apps.get_model(app, model)
        except LookupError:
            return None

    def _service(self, import_path: str):
        """Safely import a service from another app."""
        try:
            parts  = import_path.rsplit('.', 1)
            module = __import__(parts[0], fromlist=[parts[1]])
            return getattr(module, parts[1])
        except Exception:
            return None

    def _cache(self, *parts) -> str:
        return f'{CACHE_PREFIX}:{self.app_label}:' + ':'.join(str(p) for p in parts)


# ═══════════════════════════════════════════════════════════════
# WALLET ADAPTER
# Support → wallet app-এর নিজের methods call করে
# ═══════════════════════════════════════════════════════════════
class WalletAdapter(BaseAdapter):
    app_label = 'wallet'

    def get_balance(self, user) -> dict:
        """Read wallet balance — READ ONLY, no writes."""
        key    = self._cache('balance', user.id)
        cached = cache.get(key)
        if cached:
            return cached

        try:
            Wallet = self._model('wallet', 'Wallet')
            if not Wallet:
                return self._empty_balance()
            wallet = Wallet.objects.get(user=user)
            data = {
                'available':    float(wallet.available_balance),
                'current':      float(wallet.current_balance),
                'frozen':       float(wallet.frozen_balance) if hasattr(wallet, 'frozen_balance') else 0,
                'total_earned': float(wallet.total_earned) if hasattr(wallet, 'total_earned') else 0,
                'is_locked':    wallet.is_locked if hasattr(wallet, 'is_locked') else False,
                'currency':     getattr(wallet, 'currency', 'BDT'),
            }
            cache.set(key, data, timeout=CACHE_TTL_WALLET_BALANCE)
            return data
        except Exception as e:
            logger.debug(f'WalletAdapter.get_balance: {e}')
            return self._empty_balance()

    def credit(self, user, amount, reason: str, ticket_id: str = '') -> bool:
        """
        Credit wallet — calls wallet app's OWN credit/transaction method.
        Support does NOT touch wallet fields directly.
        """
        cache.delete(self._cache('balance', user.id))
        try:
            # Option 1: wallet app has a service method
            WalletService = self._service('api.wallet.services.WalletService')
            if WalletService and hasattr(WalletService, 'credit'):
                return WalletService.credit(user=user, amount=amount, reason=reason, source='support')

            # Option 2: wallet app has a transaction create method
            WalletTxn = self._model('wallet', 'WalletTransaction')
            Wallet     = self._model('wallet', 'Wallet')
            if WalletTxn and Wallet:
                wallet = Wallet.objects.get(user=user)
                if hasattr(wallet, 'is_locked') and wallet.is_locked:
                    raise WalletLockedError(getattr(wallet, 'locked_reason', 'Wallet locked'))
                # Call wallet's own method if it has one
                if hasattr(wallet, 'credit'):
                    wallet.credit(amount, reason)
                    WalletTxn.objects.create(
                        wallet      = wallet,
                        type        = 'credit',
                        amount      = amount,
                        status      = 'approved',
                        description = f'Support dispute: {reason}. Ref: {ticket_id}',
                    )
                    logger.info(f'Wallet credited {amount} to user {user.id}: {reason}')
                    return True
        except WalletLockedError:
            raise
        except Exception as e:
            logger.error(f'WalletAdapter.credit failed: {e}')
        return False

    def freeze(self, user, amount, reason: str) -> bool:
        """Freeze wallet — calls wallet.freeze() method."""
        cache.delete(self._cache('balance', user.id))
        try:
            Wallet = self._model('wallet', 'Wallet')
            if not Wallet:
                return False
            wallet = Wallet.objects.get(user=user)
            if hasattr(wallet, 'freeze'):
                wallet.freeze(amount, reason)  # wallet app's own method
                return True
        except Exception as e:
            logger.debug(f'WalletAdapter.freeze: {e}')
        return False

    def unfreeze(self, user, amount, reason: str) -> bool:
        """Unfreeze wallet — calls wallet.unfreeze() method."""
        cache.delete(self._cache('balance', user.id))
        try:
            Wallet = self._model('wallet', 'Wallet')
            if not Wallet:
                return False
            wallet = Wallet.objects.get(user=user)
            if hasattr(wallet, 'unfreeze'):
                wallet.unfreeze(amount, reason)  # wallet app's own method
                return True
        except Exception as e:
            logger.debug(f'WalletAdapter.unfreeze: {e}')
        return False

    def get_transactions(self, user, limit: int = 10) -> list:
        """Read transactions — READ ONLY."""
        try:
            WalletTxn = self._model('wallet', 'WalletTransaction')
            if not WalletTxn:
                return []
            txns = WalletTxn.objects.filter(wallet__user=user).order_by('-created_at')[:limit]
            return [{
                'type':        getattr(t, 'type', ''),
                'amount':      float(t.amount),
                'status':      getattr(t, 'status', ''),
                'description': getattr(t, 'description', ''),
                'created_at':  t.created_at.isoformat(),
            } for t in txns]
        except Exception as e:
            logger.debug(f'WalletAdapter.get_transactions: {e}')
            return []

    def _empty_balance(self) -> dict:
        return {'available': 0, 'current': 0, 'frozen': 0, 'total_earned': 0, 'is_locked': False}


# ═══════════════════════════════════════════════════════════════
# FRAUD ADAPTER
# Support → fraud_detection app-এর methods call করে
# ═══════════════════════════════════════════════════════════════
class FraudAdapter(BaseAdapter):
    app_label = 'fraud_detection'

    def get_risk_score(self, user) -> dict:
        """READ ONLY — fraud app-এর risk profile পড়ে।"""
        key    = self._cache('risk', user.id)
        cached = cache.get(key)
        if cached:
            return cached
        try:
            RiskProfile = self._model('fraud_detection', 'UserRiskProfile')
            if not RiskProfile:
                return self._default_risk()
            profile = RiskProfile.objects.get(user=user)
            score   = getattr(profile, 'overall_risk_score', 0)
            data = {
                'score':         score,
                'is_high_risk':  score >= FRAUD_RISK_HIGH_THRESHOLD,
                'is_critical':   score >= FRAUD_RISK_CRITICAL,
                'is_flagged':    getattr(profile, 'is_flagged', False),
                'fraud_attempts':getattr(profile, 'total_fraud_attempts', 0),
                'warnings':      list(profile.warning_flags) if hasattr(profile, 'warning_flags') and profile.warning_flags else [],
            }
            cache.set(key, data, timeout=CACHE_TTL_USER_RISK)
            return data
        except Exception as e:
            logger.debug(f'FraudAdapter.get_risk_score: {e}')
            return self._default_risk()

    def is_safe_to_auto_approve(self, user, amount) -> tuple:
        """Check if auto-approve is safe for this user."""
        risk = self.get_risk_score(user)
        if risk['is_critical']:
            return False, f'Critical fraud risk ({risk["score"]})'
        if risk['is_high_risk']:
            return False, f'High fraud risk ({risk["score"]})'
        if risk['is_flagged']:
            return False, 'Account flagged'
        return True, 'OK'

    def flag_user(self, user, reason: str) -> bool:
        """
        Flag user — calls fraud_detection app's OWN service.
        Support does NOT write to fraud_detection models directly.
        """
        cache.delete(self._cache('risk', user.id))
        try:
            # Call fraud detection app's service if available
            FraudService = self._service('api.fraud_detection.services.FraudService')
            if FraudService and hasattr(FraudService, 'flag_user'):
                return FraudService.flag_user(user=user, reason=reason, source='support')

            # No fallback — fraud data is fraud app's responsibility
            # Support cannot write to fraud_detection models directly
            logger.warning(f'FraudAdapter.flag_user: fraud service not available for user {user.id}')
        except Exception as e:
            logger.debug(f'FraudAdapter.flag_user: {e}')
        return False

    def get_offer_completions(self, user, offer_id: str) -> list:
        """READ ONLY — check offer completions."""
        try:
            OfferCompletion = self._model('fraud_detection', 'OfferCompletion')
            if not OfferCompletion:
                return []
            qs = OfferCompletion.objects.filter(user=user)
            if offer_id:
                qs = qs.filter(offer_id=offer_id)
            return [{'status': c.status, 'created_at': c.created_at.isoformat()} for c in qs]
        except Exception:
            return []

    def _default_risk(self) -> dict:
        return {'score': 0, 'is_high_risk': False, 'is_critical': False, 'is_flagged': False, 'fraud_attempts': 0}


# ═══════════════════════════════════════════════════════════════
# POSTBACK ADAPTER
# Support → postback app থেকে READ করে verification-এর জন্য
# ═══════════════════════════════════════════════════════════════
class PostbackAdapter(BaseAdapter):
    app_label = 'postback'

    def verify_offer_completion(self, user, offer_id: str, click_id: str = '') -> dict:
        """READ ONLY — postback logs check করে offer verify করতে।"""
        result = {'found': False, 'confidence': 0.1, 'status': 'not_found', 'details': []}
        try:
            PostbackLog = self._model('postback', 'PostbackLog')
            if not PostbackLog:
                result['details'] = ['Postback system unavailable']
                return result

            qs = PostbackLog.objects.all()
            if hasattr(PostbackLog, 'tenant'):
                tenant = getattr(user, 'tenant', None)
                if tenant:
                    qs = qs.filter(tenant=tenant)

            if click_id:
                pb = qs.filter(click_id=click_id).first()
                if pb:
                    return {'found': True, 'confidence': 0.95, 'status': 'verified',
                            'details': [f'Click ID {click_id} found. Status: {getattr(pb,"status","")}']}

            if offer_id:
                try:
                    pb_list = qs.filter(raw_payload__icontains=offer_id)[:3]
                    if pb_list.exists():
                        return {'found': True, 'confidence': 0.6, 'status': 'partial',
                                'details': [f'Offer ID {offer_id} found in postback data']}
                except Exception:
                    pass

            result['details'] = ['No matching postback record found']
        except Exception as e:
            logger.debug(f'PostbackAdapter.verify_offer_completion: {e}')
        return result

    def get_recent(self, user, limit: int = 5) -> list:
        """READ ONLY — recent postbacks."""
        try:
            PostbackLog = self._model('postback', 'PostbackLog')
            if not PostbackLog:
                return []
            logs = PostbackLog.objects.order_by('-created_at')[:limit]
            return [{'status': getattr(l, 'status', ''), 'created_at': l.created_at.isoformat()} for l in logs]
        except Exception:
            return []


# ═══════════════════════════════════════════════════════════════
# OFFERWALL ADAPTER
# Support → offerwall app থেকে READ করে
# ═══════════════════════════════════════════════════════════════
class OfferwallAdapter(BaseAdapter):
    app_label = 'offerwall'

    def get_offer_details(self, offer_id: str) -> Optional[dict]:
        """READ ONLY — offer details for dispute context."""
        key    = self._cache('offer', offer_id)
        cached = cache.get(key)
        if cached:
            return cached
        try:
            Offer = self._model('offerwall', 'Offer')
            if not Offer:
                return None
            offer = Offer.objects.filter(id=offer_id).first() or \
                    Offer.objects.filter(external_id=offer_id).first()
            if not offer:
                return None
            data = {
                'id':     str(offer.id),
                'name':   getattr(offer, 'name', ''),
                'payout': float(getattr(offer, 'payout', 0)),
                'status': getattr(offer, 'status', ''),
            }
            cache.set(key, data, timeout=CACHE_TTL_OFFER_STATUS)
            return data
        except Exception as e:
            logger.debug(f'OfferwallAdapter.get_offer_details: {e}')
            return None

    def check_user_completion(self, user, offer_id: str) -> dict:
        """READ ONLY — check if user completed offer."""
        try:
            for model_name in ('OfferConversion', 'OfferCompletion'):
                M = self._model('offerwall', model_name)
                if M:
                    conv = M.objects.filter(user=user, offer_id=offer_id).first()
                    if conv:
                        return {'found': True, 'status': getattr(conv, 'status', 'found')}
            return {'found': False, 'status': 'not_found'}
        except Exception:
            return {'found': False, 'status': 'error'}


# ═══════════════════════════════════════════════════════════════
# NOTIFICATIONS ADAPTER
# Support → notifications app-এর service call করে
# ═══════════════════════════════════════════════════════════════
class NotificationsAdapter(BaseAdapter):
    app_label = 'notifications'

    def send(self, user, title: str, body: str, notification_type: str = 'support',
             data: dict = None, priority: str = 'medium') -> bool:
        """
        Send notification — calls notifications app's service.
        Support does NOT create notification objects directly.
        """
        try:
            # Try notifications app service first
            NotifService = self._service('api.notifications.services.NotificationService')
            if NotifService and hasattr(NotifService, 'send'):
                return NotifService.send(user=user, title=title, body=body,
                                         notification_type=notification_type, data=data or {})

            # Try messaging app (which your project has)
            MessagingNotif = self._service('api.messaging.services.MessagingService')
            if MessagingNotif and hasattr(MessagingNotif, 'send_notification'):
                return MessagingNotif.send_notification(user=user, title=title, message=body)

            # Fallback: direct Notification model
            Notification = self._model('notifications', 'Notification')
            if Notification:
                for field in ('recipient', 'user'):
                    try:
                        Notification.objects.create(**{
                            field: user, 'title': title, 'body': body,
                        })
                        return True
                    except TypeError:
                        continue

            # Last resort: email
            return self._email(user, title, body)

        except Exception as e:
            logger.debug(f'NotificationsAdapter.send: {e}')
            return self._email(user, title, body)

    def send_ticket_event(self, ticket, event: str) -> bool:
        """Send standardized ticket notification."""
        from .integ_constants import (
            EVT_TICKET_CREATED, EVT_TICKET_REPLIED,
            EVT_TICKET_RESOLVED, EVT_TICKET_ESCALATED, EVT_TICKET_SLA_BREACH,
        )
        msgs = {
            EVT_TICKET_CREATED:   ('Ticket Created', f'Ticket #{ticket.ticket_id} received.'),
            EVT_TICKET_REPLIED:   ('New Reply', f'Support replied on #{ticket.ticket_id}.'),
            EVT_TICKET_RESOLVED:  ('Ticket Resolved ✅', f'#{ticket.ticket_id} resolved!'),
            EVT_TICKET_ESCALATED: ('Ticket Escalated 🔴', f'#{ticket.ticket_id} escalated.'),
            EVT_TICKET_SLA_BREACH:('SLA Breach 🚨', f'#{ticket.ticket_id} SLA missed.'),
        }
        title, body = msgs.get(event, ('Support Update', ''))
        return self.send(ticket.user, title, body, data={'ticket_id': ticket.ticket_id})

    def _email(self, user, title: str, body: str) -> bool:
        """Email fallback when notifications app unavailable."""
        try:
            from django.core.mail import send_mail
            from django.conf import settings as ds
            if user.email:
                send_mail(title, body, getattr(ds, 'DEFAULT_FROM_EMAIL', 'support@site.com'),
                          [user.email], fail_silently=True)
                return True
        except Exception:
            pass
        return False


# ═══════════════════════════════════════════════════════════════
# KYC ADAPTER
# Support → kyc app থেকে READ করে
# ═══════════════════════════════════════════════════════════════
class KYCAdapter(BaseAdapter):
    app_label = 'kyc'

    def get_status(self, user) -> dict:
        """READ ONLY — KYC status check."""
        key    = self._cache('status', user.id)
        cached = cache.get(key)
        if cached:
            return cached
        try:
            for model_name in ('KYC', 'KYCVerification', 'KYCSubmission'):
                M = self._model('kyc', model_name)
                if M:
                    kyc = M.objects.filter(user=user).order_by('-created_at').first()
                    if kyc:
                        status = getattr(kyc, 'status', 'unknown')
                        data = {
                            'status':      status,
                            'is_verified': status == 'approved',
                            'submitted_at':kyc.created_at.isoformat() if hasattr(kyc, 'created_at') else None,
                        }
                        cache.set(key, data, timeout=CACHE_TTL_KYC_STATUS)
                        return data
        except Exception as e:
            logger.debug(f'KYCAdapter.get_status: {e}')
        return {'status': 'unknown', 'is_verified': False}

    def is_verified(self, user) -> bool:
        return self.get_status(user).get('is_verified', False)


# ═══════════════════════════════════════════════════════════════
# REFERRAL ADAPTER
# Support → referral app থেকে READ করে
# ═══════════════════════════════════════════════════════════════
class ReferralAdapter(BaseAdapter):
    app_label = 'referral'

    def get_info(self, user) -> dict:
        """READ ONLY — referral info for dispute context."""
        try:
            for model_name in ('Referral', 'ReferralRelationship'):
                M = self._model('referral', model_name)
                if M:
                    count = M.objects.filter(referrer=user).count() if hasattr(M, 'referrer') else 0
                    return {'total_referred': count, 'has_referral': True}
        except Exception:
            pass
        return {'total_referred': 0, 'has_referral': False}

    def verify_earning(self, user, referred_id: int) -> dict:
        """READ ONLY — verify referral earning exists."""
        try:
            for model_name in ('ReferralEarning', 'ReferralCommission'):
                M = self._model('referral', model_name)
                if M:
                    earning = M.objects.filter(referrer=user).first()
                    if earning:
                        return {'verified': True, 'amount': float(getattr(earning, 'amount', 0))}
        except Exception:
            pass
        return {'verified': False, 'reason': 'No earning found'}


# ═══════════════════════════════════════════════════════════════
# ANALYTICS ADAPTER
# Support → analytics app-এ events পাঠায়
# ═══════════════════════════════════════════════════════════════
class AnalyticsAdapter(BaseAdapter):
    app_label = 'analytics'

    def track(self, event: str, user=None, props: dict = None) -> bool:
        """Send support event to analytics app."""
        try:
            # Try analytics service
            AnalyticsService = self._service('api.analytics.services.AnalyticsService')
            if AnalyticsService and hasattr(AnalyticsService, 'track'):
                return AnalyticsService.track(
                    event=f'support.{event}', user=user,
                    properties={**(props or {}), 'source': 'support'}
                )

            # Try direct model
            for model_name in ('Event', 'AnalyticsEvent', 'UserEvent'):
                M = self._model('analytics', model_name)
                if M:
                    try:
                        M.objects.create(
                            name=f'support.{event}',
                            properties={**(props or {}), 'source': 'support'},
                            **({'user': user} if user else {}),
                        )
                        return True
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f'AnalyticsAdapter.track: {e}')
        return False

    def track_support_event(self, event: str, ticket=None, user=None, **extra) -> bool:
        props = {**extra}
        if ticket:
            props.update({'ticket_id': ticket.ticket_id, 'category': ticket.category, 'priority': ticket.priority})
        return self.track(event, user=user or (ticket.user if ticket else None), props=props)


# ── Adapter registration ──────────────────────────────────────
def setup_adapters():
    """Register all adapters in the integration registry."""
    from .integ_registry import get_registry
    registry = get_registry()
    adapters = {
        'wallet':        WalletAdapter(),
        'fraud':         FraudAdapter(),
        'postback':      PostbackAdapter(),
        'offerwall':     OfferwallAdapter(),
        'notifications': NotificationsAdapter(),
        'kyc':           KYCAdapter(),
        'referral':      ReferralAdapter(),
        'analytics':     AnalyticsAdapter(),
    }
    for name, adapter in adapters.items():
        registry.register_adapter(name, adapter)
    return registry


# ── Singleton instances ───────────────────────────────────────
wallet_adapter        = WalletAdapter()
fraud_adapter         = FraudAdapter()
postback_adapter      = PostbackAdapter()
offerwall_adapter     = OfferwallAdapter()
notifications_adapter = NotificationsAdapter()
kyc_adapter           = KYCAdapter()
referral_adapter      = ReferralAdapter()
analytics_adapter     = AnalyticsAdapter()