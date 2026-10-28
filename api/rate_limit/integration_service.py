# api/rate_limit/integration_service.py
"""
Rate Limit Integration Service
================================
Central service that connects rate_limit with ALL other systems in the API.

Systems covered:
  1. Users (auth / registration / login / 2FA)
  2. Wallet (withdrawal / earning / transfer)
  3. Offerwall (offer completion / task submission)
  4. Referral (referral click / commission)
  5. Postback Engine (click / conversion tracking)
  6. KYC (identity verification)
  7. Fraud Detection (risk scoring bridge)
  8. Messaging / WebSocket (chat / call rate limit)
  9. Ad Networks (ad impression / click)
  10. Webhooks (inbound / outbound delivery)
  11. Security (endpoint protection / token validation)
  12. Tenants (per-tenant quota enforcement)

Usage pattern (ANY system):
    from api.rate_limit.integration_service import RateLimitIntegrationService

    result = RateLimitIntegrationService.check(
        action='wallet_withdrawal',
        request=request,          # optional — provides IP + user automatically
        user=user,                # or pass explicitly
        ip_address='1.2.3.4',    # or pass explicitly
        extra_context={...},      # any extra info
    )
    if not result.allowed:
        return Response({'error': result.reason}, status=429)
"""

from __future__ import annotations
from django.db import models

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('rate_limit.integration')


# ─────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class RateLimitResult:
    """Unified result object returned by every check."""
    allowed: bool
    reason: str = ''
    remaining: int = -1          # requests remaining in window (-1 = unknown)
    reset_at: Optional[Any] = None   # datetime when limit resets
    action: str = ''
    user_id: Optional[int] = None
    ip_address: str = ''
    config_name: str = ''
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_headers(self) -> Dict[str, str]:
        """Return HTTP headers to attach to response."""
        headers = {
            'X-RateLimit-Action': self.action,
            'X-RateLimit-Remaining': str(self.remaining),
            'X-RateLimit-Allowed': 'true' if self.allowed else 'false',
        }
        if self.reset_at:
            try:
                headers['X-RateLimit-Reset'] = self.reset_at.isoformat()
            except Exception:
                pass
        return headers

    def raise_if_blocked(self):
        """Raise DRF Throttled if not allowed."""
        if not self.allowed:
            from rest_framework.exceptions import Throttled
            raise Throttled(detail=self.reason or 'Rate limit exceeded.')


# ─────────────────────────────────────────────────────────────
# Action registry  (action_name → config_name in RateLimitConfig)
# Add / edit entries here to change limits without code changes.
# ─────────────────────────────────────────────────────────────

ACTION_CONFIG_MAP: Dict[str, str] = {
    # ── Users ──────────────────────────────────────────
    'user_login':               'users_login',
    'user_register':            'users_register',
    'user_2fa':                 'users_2fa',
    'user_password_reset':      'users_password_reset',
    'user_otp_request':         'users_otp_request',
    'user_profile_update':      'users_profile_update',

    # ── Wallet ─────────────────────────────────────────
    'wallet_withdrawal':        'wallet_withdrawal',
    'wallet_transfer':          'wallet_transfer',
    'wallet_earning':           'wallet_earning',
    'wallet_payment_request':   'wallet_payment_request',
    'wallet_balance_check':     'wallet_balance_check',

    # ── Offerwall ──────────────────────────────────────
    'offer_view':               'offerwall_offer_view',
    'offer_complete':           'offerwall_offer_complete',
    'offer_click':              'offerwall_offer_click',
    'task_submit':              'offerwall_task_submit',
    'task_complete':            'offerwall_task_complete',
    'survey_submit':            'offerwall_survey_submit',

    # ── Referral ───────────────────────────────────────
    'referral_click':           'referral_click',
    'referral_register':        'referral_register',
    'referral_commission':      'referral_commission',
    'referral_link_generate':   'referral_link_generate',

    # ── Postback Engine ────────────────────────────────
    'postback_click':           'postback_click',
    'postback_conversion':      'postback_conversion',
    'postback_impression':      'postback_impression',
    'postback_validation':      'postback_validation',

    # ── KYC ────────────────────────────────────────────
    'kyc_submit':               'kyc_submit',
    'kyc_document_upload':      'kyc_document_upload',
    'kyc_status_check':         'kyc_status_check',
    'kyc_reverification':       'kyc_reverification',

    # ── Fraud Detection ────────────────────────────────
    'fraud_report':             'fraud_report',
    'fraud_risk_check':         'fraud_risk_check',

    # ── Messaging / WebSocket ──────────────────────────
    'message_send':             'messaging_send',
    'message_websocket_connect':'messaging_ws_connect',
    'message_reaction':         'messaging_reaction',
    'call_initiate':            'messaging_call_initiate',

    # ── Ad Networks ────────────────────────────────────
    'ad_impression':            'ad_networks_impression',
    'ad_click':                 'ad_networks_click',
    'ad_conversion':            'ad_networks_conversion',

    # ── Webhooks ───────────────────────────────────────
    'webhook_inbound':          'webhooks_inbound',
    'webhook_outbound':         'webhooks_outbound',
    'webhook_retry':            'webhooks_retry',

    # ── Security / API ─────────────────────────────────
    'api_global':               'api_global',
    'security_token_validate':  'security_token_validate',
    'security_login_attempt':   'security_login_attempt',

    # ── Tenant ─────────────────────────────────────────
    'tenant_api_call':          'tenant_api_call',
    'tenant_export':            'tenant_export',
}


# ─────────────────────────────────────────────────────────────
# Core service
# ─────────────────────────────────────────────────────────────

class RateLimitIntegrationService:
    """
    Central bridge between rate_limit and every other app.

    All public methods are @staticmethod / @classmethod so systems
    can call them without instantiating anything.
    """

    # ── Public entry point ─────────────────────────────────────

    @classmethod
    def check(
        cls,
        action: str,
        request=None,
        user=None,
        ip_address: str = '',
        tenant=None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> RateLimitResult:
        """
        Main check method.  Call this from ANY system.

        Args:
            action:        Action name from ACTION_CONFIG_MAP (e.g. 'wallet_withdrawal').
            request:       Django request object (optional, used to auto-extract user + IP).
            user:          Django User instance (override request.user).
            ip_address:    Client IP (override auto-detection).
            tenant:        Tenant object (for per-tenant quota).
            extra_context: Any extra info logged with the request.

        Returns:
            RateLimitResult — always check .allowed before proceeding.
        """
        try:
            user = user or (request.user if request and hasattr(request, 'user') and request.user.is_authenticated else None)
            ip_address = ip_address or cls._extract_ip(request)
            tenant = tenant or cls._extract_tenant(request, user)
            extra_context = extra_context or {}

            config_name = ACTION_CONFIG_MAP.get(action, action)
            result = cls._run_check(
                action=action,
                config_name=config_name,
                user=user,
                ip_address=ip_address,
                tenant=tenant,
                extra_context=extra_context,
            )

            # Log to rate_limit DB
            cls._log(result, action, user, ip_address, request, extra_context)

            return result

        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] check() error for action={action}: {e}')
            # Fail open — never block legitimate traffic due to internal errors
            return RateLimitResult(allowed=True, action=action, reason='rate_limit_error_fail_open')

    @classmethod
    def check_and_raise(cls, action: str, **kwargs) -> RateLimitResult:
        """check() + raise DRF Throttled if blocked. Convenience for views."""
        result = cls.check(action, **kwargs)
        result.raise_if_blocked()
        return result

    # ── System-specific convenience methods ────────────────────

    # ---- Users ----

    @classmethod
    def check_login(cls, request, ip_address: str = '') -> RateLimitResult:
        return cls.check('user_login', request=request, ip_address=ip_address)

    @classmethod
    def check_register(cls, request, ip_address: str = '') -> RateLimitResult:
        return cls.check('user_register', request=request, ip_address=ip_address)

    @classmethod
    def check_2fa(cls, user, request=None) -> RateLimitResult:
        return cls.check('user_2fa', user=user, request=request)

    @classmethod
    def check_password_reset(cls, request, ip_address: str = '') -> RateLimitResult:
        return cls.check('user_password_reset', request=request, ip_address=ip_address)

    # ---- Wallet ----

    @classmethod
    def check_withdrawal(cls, user, request=None, amount=None) -> RateLimitResult:
        return cls.check(
            'wallet_withdrawal',
            user=user,
            request=request,
            extra_context={'amount': str(amount)} if amount else {},
        )

    @classmethod
    def check_wallet_earning(cls, user, task_type: str = '', request=None) -> RateLimitResult:
        return cls.check(
            'wallet_earning',
            user=user,
            request=request,
            extra_context={'task_type': task_type},
        )

    @classmethod
    def check_payment_request(cls, user, request=None) -> RateLimitResult:
        return cls.check('wallet_payment_request', user=user, request=request)

    # ---- Offerwall ----

    @classmethod
    def check_offer_complete(cls, user, offer_id=None, offer_wall: str = '', request=None) -> RateLimitResult:
        return cls.check(
            'offer_complete',
            user=user,
            request=request,
            extra_context={'offer_id': str(offer_id) if offer_id else '', 'offer_wall': offer_wall},
        )

    @classmethod
    def check_task_submit(cls, user, task_type: str = '', request=None) -> RateLimitResult:
        return cls.check(
            'task_submit',
            user=user,
            request=request,
            extra_context={'task_type': task_type},
        )

    @classmethod
    def check_survey_submit(cls, user, request=None) -> RateLimitResult:
        return cls.check('survey_submit', user=user, request=request)

    # ---- Referral ----

    @classmethod
    def check_referral_click(cls, ip_address: str, request=None) -> RateLimitResult:
        return cls.check('referral_click', request=request, ip_address=ip_address)

    @classmethod
    def check_referral_commission(cls, user, request=None) -> RateLimitResult:
        return cls.check('referral_commission', user=user, request=request)

    # ---- Postback Engine ----

    @classmethod
    def check_postback_click(cls, ip_address: str, network: str = '', request=None) -> RateLimitResult:
        return cls.check(
            'postback_click',
            request=request,
            ip_address=ip_address,
            extra_context={'network': network},
        )

    @classmethod
    def check_postback_conversion(cls, ip_address: str, network: str = '', request=None) -> RateLimitResult:
        return cls.check(
            'postback_conversion',
            request=request,
            ip_address=ip_address,
            extra_context={'network': network},
        )

    # ---- KYC ----

    @classmethod
    def check_kyc_submit(cls, user, request=None) -> RateLimitResult:
        return cls.check('kyc_submit', user=user, request=request)

    @classmethod
    def check_kyc_document_upload(cls, user, request=None) -> RateLimitResult:
        return cls.check('kyc_document_upload', user=user, request=request)

    # ---- Fraud Detection ----

    @classmethod
    def check_fraud_risk(cls, user=None, ip_address: str = '', request=None) -> RateLimitResult:
        return cls.check('fraud_risk_check', user=user, ip_address=ip_address, request=request)

    # ---- Messaging / WebSocket ----

    @classmethod
    def check_message_send(cls, user, request=None) -> RateLimitResult:
        return cls.check('message_send', user=user, request=request)

    @classmethod
    def check_ws_connect(cls, user=None, ip_address: str = '', request=None) -> RateLimitResult:
        return cls.check('message_websocket_connect', user=user, ip_address=ip_address, request=request)

    @classmethod
    def check_call_initiate(cls, user, request=None) -> RateLimitResult:
        return cls.check('call_initiate', user=user, request=request)

    # ---- Ad Networks ----

    @classmethod
    def check_ad_click(cls, ip_address: str, user=None, network: str = '', request=None) -> RateLimitResult:
        return cls.check(
            'ad_click',
            user=user,
            ip_address=ip_address,
            request=request,
            extra_context={'network': network},
        )

    @classmethod
    def check_ad_impression(cls, ip_address: str, user=None, request=None) -> RateLimitResult:
        return cls.check('ad_impression', user=user, ip_address=ip_address, request=request)

    # ---- Webhooks ----

    @classmethod
    def check_webhook_inbound(cls, ip_address: str, request=None) -> RateLimitResult:
        return cls.check('webhook_inbound', ip_address=ip_address, request=request)

    @classmethod
    def check_webhook_outbound(cls, ip_address: str = '', request=None) -> RateLimitResult:
        return cls.check('webhook_outbound', ip_address=ip_address, request=request)

    # ---- Security ----

    @classmethod
    def check_security_token(cls, ip_address: str = '', request=None) -> RateLimitResult:
        return cls.check('security_token_validate', ip_address=ip_address, request=request)

    # ---- Tenant ----

    @classmethod
    def check_tenant_api(cls, tenant, user=None, request=None) -> RateLimitResult:
        return cls.check('tenant_api_call', tenant=tenant, user=user, request=request)

    # ─────────────────────────────────────────────────────────────
    # Bulk / batch check
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def check_multiple(
        cls,
        actions: list,
        request=None,
        user=None,
        ip_address: str = '',
    ) -> Dict[str, RateLimitResult]:
        """
        Check multiple actions at once.
        Returns dict of {action_name: RateLimitResult}.
        All blocked = overall blocked.

        Usage:
            results = RateLimitIntegrationService.check_multiple(
                ['offer_complete', 'wallet_earning'],
                user=request.user,
                request=request,
            )
            if not all(r.allowed for r in results.values()):
                return Response({'error': 'rate limit'}, status=429)
        """
        return {
            action: cls.check(action, request=request, user=user, ip_address=ip_address)
            for action in actions
        }

    # ─────────────────────────────────────────────────────────────
    # Status / introspection
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def get_user_status(cls, user) -> Dict[str, Any]:
        """
        Return a full rate-limit status summary for a user.
        Useful for dashboard / admin panel.
        """
        try:
            from api.rate_limit.models import UserRateLimitProfile, RateLimitLog
            from django.db.models import Count
            from datetime import timedelta

            profile = UserRateLimitProfile.objects.filter(user=user).first()
            now = timezone.now()
            last_hour = now - timedelta(hours=1)
            last_day = now - timedelta(days=1)

            recent_logs = RateLimitLog.objects.filter(user=user, timestamp__gte=last_hour)
            blocked_today = RateLimitLog.objects.filter(
                user=user,
                timestamp__gte=last_day,
                status='blocked',
            ).count()

            return {
                'user_id': user.id,
                'is_premium': getattr(profile, 'is_premium', False) if profile else False,
                'health_score': getattr(profile, 'health_score', 100) if profile else 100,
                'suspicion_score': getattr(profile, 'suspicion_score', 0) if profile else 0,
                'blocked_today': blocked_today,
                'requests_last_hour': recent_logs.count(),
                'is_blocked': getattr(profile, 'is_temporarily_blocked', False) if profile else False,
                'custom_limit': getattr(profile, 'custom_rate_limit', None) if profile else None,
            }
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] get_user_status error: {e}')
            return {'user_id': getattr(user, 'id', None), 'error': str(e)}

    @classmethod
    def get_ip_status(cls, ip_address: str) -> Dict[str, Any]:
        """Return rate-limit status for an IP address."""
        try:
            from api.rate_limit.models import IPBlockList, RateLimitLog
            from datetime import timedelta

            now = timezone.now()
            blocked = IPBlockList.objects.filter(
                ip_address=ip_address,
                is_active=True,
            ).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
            ).first()

            recent = RateLimitLog.objects.filter(
                ip_address=ip_address,
                timestamp__gte=now - timedelta(hours=1),
            ).count()

            return {
                'ip_address': ip_address,
                'is_blocked': blocked is not None,
                'block_reason': getattr(blocked, 'block_reason', '') if blocked else '',
                'expires_at': blocked.expires_at.isoformat() if blocked and blocked.expires_at else None,
                'requests_last_hour': recent,
            }
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] get_ip_status error: {e}')
            return {'ip_address': ip_address, 'error': str(e)}

    @classmethod
    def reset_user_limits(cls, user, actions: Optional[list] = None) -> bool:
        """
        Reset rate limit counters for a user (all or specific actions).
        Used by admin panel / support system.
        """
        try:
            from api.rate_limit.services import RateLimitService
            svc = RateLimitService()
            svc.reset_user_limits_by_id(user.id, action_names=actions)
            logger.info(f'[RateLimitIntegrationService] Reset limits for user={user.id} actions={actions}')
            return True
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] reset_user_limits error: {e}')
            return False

    @classmethod
    def block_ip(cls, ip_address: str, reason: str, hours: int = 24, blocked_by=None) -> bool:
        """
        Immediately block an IP address.
        Called by fraud_detection, security, admin_panel.
        """
        try:
            from api.rate_limit.services import IPBlockService
            svc = IPBlockService()
            svc.block_ip_for_hours(
                ip_address=ip_address,
                reason=reason,
                hours=hours,
                blocked_by_user_id=getattr(blocked_by, 'id', None) if blocked_by else None,
            )
            logger.warning(f'[RateLimitIntegrationService] IP blocked: {ip_address} reason={reason}')
            return True
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] block_ip error: {e}')
            return False

    @classmethod
    def unblock_ip(cls, ip_address: str) -> bool:
        """Unblock an IP address."""
        try:
            from api.rate_limit.models import IPBlockList
            IPBlockList.objects.filter(ip_address=ip_address, is_active=True).update(is_active=False)
            logger.info(f'[RateLimitIntegrationService] IP unblocked: {ip_address}')
            return True
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] unblock_ip error: {e}')
            return False

    @classmethod
    def update_user_suspicion(cls, user, score_delta: int, reason: str = '') -> bool:
        """
        Update a user's suspicion score.
        Called by: fraud_detection, postback_engine, offerwall.
        """
        try:
            from api.rate_limit.models import UserRateLimitProfile
            from django.db.models import F
            profile, _ = UserRateLimitProfile.objects.get_or_create(user=user)
            new_score = max(0, min(100, (profile.suspicion_score or 0) + score_delta))
            UserRateLimitProfile.objects.filter(user=user).update(suspicion_score=new_score)
            logger.info(f'[RateLimitIntegrationService] suspicion updated user={user.id} delta={score_delta} new={new_score} reason={reason}')
            return True
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] update_user_suspicion error: {e}')
            return False

    @classmethod
    def set_premium(cls, user, is_premium: bool) -> bool:
        """
        Mark a user as premium (higher limits).
        Called by: wallet (after premium purchase), subscription app.
        """
        try:
            from api.rate_limit.models import UserRateLimitProfile
            profile, _ = UserRateLimitProfile.objects.get_or_create(user=user)
            profile.is_premium = is_premium
            profile.save(update_fields=['is_premium'])
            logger.info(f'[RateLimitIntegrationService] set_premium user={user.id} premium={is_premium}')
            return True
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] set_premium error: {e}')
            return False

    # ─────────────────────────────────────────────────────────────
    # Fraud Detection ↔ Rate Limit bridge
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def sync_fraud_signal(
        cls,
        user=None,
        ip_address: str = '',
        risk_score: int = 0,
        fraud_type: str = '',
        auto_block: bool = False,
    ) -> Dict[str, Any]:
        """
        Receive a fraud signal from fraud_detection and reflect it in rate_limit.

        Called by:
            - api/fraud_detection/middleware.py
            - api/fraud_detection/detectors/*

        If risk_score >= 80  → increase suspicion score
        If risk_score >= 95  → auto-block IP (if auto_block=True)
        """
        result = {'suspicion_updated': False, 'ip_blocked': False}
        try:
            if user and risk_score >= 50:
                delta = int(risk_score / 10)
                cls.update_user_suspicion(user, delta, reason=f'fraud_signal:{fraud_type}')
                result['suspicion_updated'] = True

            if ip_address and auto_block and risk_score >= 95:
                cls.block_ip(ip_address, reason=f'fraud_detection:{fraud_type}', hours=48)
                result['ip_blocked'] = True

        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] sync_fraud_signal error: {e}')

        return result

    @classmethod
    def sync_kyc_status(cls, user, kyc_verified: bool) -> bool:
        """
        When KYC is verified/rejected, update rate_limit profile.
        KYC verified users get higher limits.
        """
        try:
            from api.rate_limit.models import UserRateLimitProfile
            profile, _ = UserRateLimitProfile.objects.get_or_create(user=user)
            # KYC verified = lower suspicion, higher custom limit
            if kyc_verified:
                profile.suspicion_score = max(0, (profile.suspicion_score or 0) - 20)
                if not profile.custom_rate_limit:
                    profile.custom_rate_limit = 500  # elevated limit for verified users
            profile.save(update_fields=['suspicion_score', 'custom_rate_limit'])
            logger.info(f'[RateLimitIntegrationService] kyc_status synced user={user.id} verified={kyc_verified}')
            return True
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] sync_kyc_status error: {e}')
            return False

    @classmethod
    def sync_tenant_limits(cls, tenant, plan_name: str = '', api_quota: int = 0) -> bool:
        """
        When a tenant upgrades/downgrades plan, update their rate limit configs.
        Called by: api/tenants/ plan change signals.
        """
        try:
            from api.rate_limit.models import RateLimitConfig
            configs = RateLimitConfig.objects.filter(tenant=tenant, is_active=True)
            if api_quota > 0:
                configs.filter(rate_limit_type='global').update(requests_per_unit=api_quota)
            logger.info(f'[RateLimitIntegrationService] tenant limits synced tenant={getattr(tenant, "id", tenant)} plan={plan_name}')
            return True
        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] sync_tenant_limits error: {e}')
            return False

    # ─────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def _run_check(
        cls,
        action: str,
        config_name: str,
        user,
        ip_address: str,
        tenant,
        extra_context: Dict,
    ) -> RateLimitResult:
        """Core logic: load config → call RateLimitService → return result."""
        try:
            from api.rate_limit.services import RateLimitService
            from api.rate_limit.models import RateLimitConfig

            # 1. Load config (cache for 60 s)
            cache_key = f'rl_config:{config_name}'
            config = cache.get(cache_key)
            if config is None:
                config = RateLimitConfig.objects.filter(
                    name=config_name,
                    is_active=True,
                ).first()
                if config:
                    cache.set(cache_key, config, 60)

            if not config:
                # No config defined → allow (fail open)
                return RateLimitResult(
                    allowed=True,
                    action=action,
                    config_name=config_name,
                    user_id=getattr(user, 'id', None),
                    ip_address=ip_address,
                    extra={'no_config': True},
                )

            # 2. Build identifier
            identifier = cls._build_identifier(config, user, ip_address, tenant)

            # 3. Whitelist / Blacklist check (fast path)
            if ip_address:
                if ip_address in (config.whitelist or []):
                    return RateLimitResult(
                        allowed=True, action=action,
                        config_name=config_name, ip_address=ip_address,
                        extra={'whitelisted': True},
                    )
                if ip_address in (config.blacklist or []):
                    return RateLimitResult(
                        allowed=False,
                        reason='IP is blacklisted',
                        action=action,
                        config_name=config_name,
                        ip_address=ip_address,
                        extra={'blacklisted': True},
                    )

            # 4. Delegate to RateLimitService
            svc = RateLimitService()
            check_result = svc.check_request_by_config(
                config=config,
                identifier=identifier,
                user_id=getattr(user, 'id', None),
                ip_address=ip_address,
                extra_context=extra_context,
            )

            allowed = check_result.get('allowed', True)
            return RateLimitResult(
                allowed=allowed,
                reason=check_result.get('reason', '') if not allowed else '',
                remaining=check_result.get('remaining', -1),
                reset_at=check_result.get('reset_at'),
                action=action,
                config_name=config_name,
                user_id=getattr(user, 'id', None),
                ip_address=ip_address,
                extra=check_result.get('extra', {}),
            )

        except Exception as e:
            logger.error(f'[RateLimitIntegrationService] _run_check error: {e}')
            return RateLimitResult(allowed=True, action=action, reason='check_error_fail_open')

    @staticmethod
    def _extract_ip(request) -> str:
        """Extract real IP from request (handles proxies / X-Forwarded-For)."""
        if not request:
            return ''
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    @staticmethod
    def _extract_tenant(request, user):
        """Extract tenant from request or user."""
        if request and hasattr(request, 'tenant'):
            return request.tenant
        if user and hasattr(user, 'tenant'):
            return user.tenant
        return None

    @staticmethod
    def _build_identifier(config, user, ip_address: str, tenant) -> str:
        """Build the unique identifier for rate limiting based on config type."""
        rate_type = config.rate_limit_type or 'global'
        if rate_type == 'user' and user:
            return f'user:{user.id}'
        elif rate_type == 'ip' and ip_address:
            return f'ip:{ip_address}'
        elif rate_type == 'endpoint' and config.endpoint:
            uid = getattr(user, 'id', 'anon')
            return f'endpoint:{config.endpoint}:{uid}'
        elif rate_type == 'tenant' and tenant:
            return f'tenant:{getattr(tenant, "id", str(tenant))}'
        elif user:
            return f'user:{user.id}'
        elif ip_address:
            return f'ip:{ip_address}'
        return 'global'

    @classmethod
    def _log(cls, result: RateLimitResult, action: str, user, ip_address: str, request, extra_context: Dict):
        """Async-safe DB log (only blocked requests + sampling for allowed)."""
        try:
            import random
            # Log all blocked + 5% of allowed (to reduce DB writes)
            if not result.allowed or random.random() < 0.05:
                from api.rate_limit.models import RateLimitLog, RateLimitConfig
                config = RateLimitConfig.objects.filter(name=result.config_name).first() if result.config_name else None
                if config:
                    RateLimitLog.objects.create(
                        config=config,
                        user=user,
                        ip_address=ip_address or result.ip_address,
                        endpoint=request.path if request else action,
                        request_method=request.method if request else 'INTERNAL',
                        status='blocked' if not result.allowed else 'allowed',
                        extra_data={
                            'action': action,
                            'reason': result.reason,
                            **extra_context,
                        },
                    )
        except Exception as e:
            logger.debug(f'[RateLimitIntegrationService] _log error (non-critical): {e}')


# ─────────────────────────────────────────────────────────────
# Django Mixin — drop into any ViewSet
# ─────────────────────────────────────────────────────────────

class RateLimitIntegrationMixin:
    """
    Drop-in mixin for DRF ViewSets and APIViews.

    class WalletWithdrawView(RateLimitIntegrationMixin, APIView):
        rate_limit_action = 'wallet_withdrawal'

        def post(self, request):
            self.check_rate_limit(request)   # raises Throttled if blocked
            ...
    """
    rate_limit_action: str = 'api_global'

    def check_rate_limit(self, request, action: str = '', **kwargs):
        action = action or self.rate_limit_action
        result = RateLimitIntegrationService.check(action, request=request, **kwargs)
        result.raise_if_blocked()
        return result

    def get_rate_limit_headers(self, result: RateLimitResult) -> Dict[str, str]:
        return result.to_headers()


# ─────────────────────────────────────────────────────────────
# Decorator — use on any view function
# ─────────────────────────────────────────────────────────────

def rate_limit_action(action: str, raise_on_block: bool = True):
    """
    Decorator for function-based views or DRF @action methods.

    @rate_limit_action('offer_complete')
    def complete_offer(request, pk):
        ...
    """
    def decorator(view_func):
        from functools import wraps

        @wraps(view_func)
        def wrapper(request_or_self, *args, **kwargs):
            # Handle both function views and method views (self, request)
            if hasattr(request_or_self, 'method'):
                req = request_or_self
            elif args and hasattr(args[0], 'method'):
                req = args[0]
            else:
                req = None

            result = RateLimitIntegrationService.check(action, request=req)
            if not result.allowed and raise_on_block:
                result.raise_if_blocked()

            response = view_func(request_or_self, *args, **kwargs)

            # Attach headers to response
            if result and hasattr(response, 'headers'):
                for k, v in result.to_headers().items():
                    response.headers[k] = v

            return response

        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────
# Signals receiver — connect in apps.py ready()
# ─────────────────────────────────────────────────────────────

def register_integration_signals():
    """
    Call this from RateLimitAppConfig.ready() to auto-sync
    signals from other apps into rate_limit.

    In apps.py:
        def ready(self):
            from api.rate_limit.integration_service import register_integration_signals
            register_integration_signals()
    """
    try:
        from django.db.models.signals import post_save
        from django.contrib.auth import get_user_model

        User = get_user_model()

        def on_user_created(sender, instance, created, **kwargs):
            if created:
                try:
                    from api.rate_limit.models import UserRateLimitProfile
                    UserRateLimitProfile.objects.get_or_create(user=instance)
                except Exception as e:
                    logger.debug(f'on_user_created signal error: {e}')

        post_save.connect(on_user_created, sender=User, dispatch_uid='rl_integration_user_created')
        logger.info('[RateLimitIntegrationService] Integration signals registered')

    except Exception as e:
        logger.warning(f'[RateLimitIntegrationService] register_integration_signals error: {e}')


# ─────────────────────────────────────────────────────────────
# Register all app-specific actions at import time
# ─────────────────────────────────────────────────────────────

def _auto_register_all_actions():
    try:
        from api.rate_limit.adapters.remaining_apps import NEW_ACTION_CONFIGS
        ACTION_CONFIG_MAP.update(NEW_ACTION_CONFIGS)
    except Exception:
        pass

_auto_register_all_actions()

# ─────────────────────────────────────────────────────────────
# Exports
# ─────────────────────────────────────────────────────────────

__all__ = [
    'RateLimitIntegrationService',
    'RateLimitIntegrationMixin',
    'RateLimitResult',
    'rate_limit_action',
    'register_integration_signals',
    'ACTION_CONFIG_MAP',
]
