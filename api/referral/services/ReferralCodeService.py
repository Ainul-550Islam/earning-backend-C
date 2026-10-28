# api/referral/services/ReferralCodeService.py
# Generate, validate, and track referral codes
# ============================================================

import random
import string
from django.db import transaction
from django.utils import timezone
import logging
from api.referral.models.tree import ReferralCode

logger = logging.getLogger(__name__)


class ReferralCodeService:
    """
    Referral code lifecycle management।
    Generate → Validate → Track clicks/conversions।
    """

    CODE_CHARS = string.ascii_uppercase + string.digits
    CODE_LENGTH = 8

    @staticmethod
    def generate_unique_code(length: int = 8) -> str:
        """Unique random code generate করো।"""
        from api.referral.models import ReferralCode

        for _ in range(20):  # max 20 attempts
            code = ''.join(
                random.choices(ReferralCodeService.CODE_CHARS, k=length)
            )
            if not ReferralCode.objects.filter(code=code).exists():
                return code

        # Fallback: longer code
        return ''.join(
            random.choices(ReferralCodeService.CODE_CHARS, k=length + 4)
        )

    @staticmethod
    @transaction.atomic
    def get_or_create_primary_code(user) -> 'ReferralCode':
        """
        User এর primary referral code পাও।
        না থাকলে create করো।
        """
        from api.referral.models import ReferralCode

        code = ReferralCode.objects.filter(
            user=user, is_primary=True, is_active=True
        ).first()

        if not code:
            # User model এ referral_code field থেকে নাও (backward compat)
            existing_code = getattr(user, 'referral_code', None)

            code_value = (
                existing_code if existing_code
                else ReferralCodeService.generate_unique_code()
            )

            code = ReferralCode.objects.create(
                user=user,
                code=code_value,
                is_primary=True,
                is_active=True,
            )
            logger.info(f"Primary code created for {user.username}: {code_value}")

        return code

    @staticmethod
    @transaction.atomic
    def create_code(
        user,
        custom_code: str = None,
        source_tag: str = '',
        campaign_id: int = None,
        expires_at=None,
    ) -> dict:
        """
        নতুন referral code তৈরি করো।
        Custom code অথবা auto-generated।
        """
        from api.referral.models import ReferralCode, ReferralCampaign

        # Custom code validation
        if custom_code:
            custom_code = custom_code.strip().upper()
            if len(custom_code) < 4:
                return {'success': False, 'error': 'Custom code too short (min 4 chars)'}
            if len(custom_code) > 30:
                return {'success': False, 'error': 'Custom code too long (max 30 chars)'}
            if ReferralCode.objects.filter(custom_code=custom_code).exists():
                return {'success': False, 'error': 'Custom code already taken'}

        campaign = None
        if campaign_id:
            try:
                campaign = ReferralCampaign.objects.get(
                    id=campaign_id, is_active=True
                )
            except ReferralCampaign.DoesNotExist:
                return {'success': False, 'error': 'Campaign not found or inactive'}

        code = ReferralCode.objects.create(
            user=user,
            code=ReferralCodeService.generate_unique_code(),
            custom_code=custom_code,
            source_tag=source_tag,
            campaign=campaign,
            expires_at=expires_at,
            is_active=True,
            is_primary=False,
        )

        return {
            'success': True,
            'code_id': code.id,
            'code': code.code,
            'custom_code': code.custom_code,
            'active_code': code.get_active_code(),
        }

    @staticmethod
    def validate_code(code_value: str) -> dict:
        """
        Code validate করো।
        Returns: {'valid': bool, 'user': user, 'code': ReferralCode}
        """
        from api.referral.models import ReferralCode

        if not code_value:
            return {'valid': False, 'error': 'No code provided'}

        code_value = code_value.strip().upper()

        # Custom code check first
        code = ReferralCode.objects.filter(
            custom_code=code_value, is_active=True
        ).select_related('user').first()

        # Fallback to system code
        if not code:
            code = ReferralCode.objects.filter(
                code=code_value, is_active=True
            ).select_related('user').first()

        # Backward compat: check user.referral_code field
        if not code:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(referral_code=code_value)
                # Auto-create code record
                code = ReferralCodeService.get_or_create_primary_code(user)
            except (User.DoesNotExist, Exception):
                return {'valid': False, 'error': 'Code not found'}

        if not code:
            return {'valid': False, 'error': 'Code not found'}

        if code.is_expired():
            return {'valid': False, 'error': 'Code expired'}

        if not code.user.is_active:
            return {'valid': False, 'error': 'Referrer account inactive'}

        return {
            'valid': True,
            'user': code.user,
            'code': code,
            'code_value': code.get_active_code(),
        }

    @staticmethod
    def track_click(code_value: str, ip: str = None, user_agent: str = None) -> bool:
        """Code click record করো। Unique click detection।"""
        from api.referral.models import ReferralCode
        from django.core.cache import cache

        result = ReferralCodeService.validate_code(code_value)
        if not result['valid']:
            return False

        code = result['code']

        # Unique click detection via cache (IP-based)
        is_unique = True
        if ip:
            cache_key = f"ref_click:{code.id}:{ip}"
            if cache.get(cache_key):
                is_unique = False
            else:
                cache.set(cache_key, 1, timeout=86400)  # 24 hours

        code.record_click(is_unique=is_unique)
        return True

    @staticmethod
    def get_code_stats(user) -> list:
        """User এর সব codes এবং তাদের stats।"""
        from api.referral.models import ReferralCode

        codes = ReferralCode.objects.filter(
            user=user
        ).order_by('-is_primary', '-created_at')

        return [{
            'id': c.id,
            'code': c.code,
            'custom_code': c.custom_code,
            'active_code': c.get_active_code(),
            'source_tag': c.source_tag,
            'clicks': c.clicks,
            'unique_clicks': c.unique_clicks,
            'conversions': c.conversions,
            'conversion_rate': c.conversion_rate,
            'revenue_generated': float(c.revenue_generated),
            'is_primary': c.is_primary,
            'is_active': c.is_active,
            'expires_at': (
                c.expires_at.strftime('%Y-%m-%d') if c.expires_at else None
            ),
            'created_at': c.created_at.strftime('%Y-%m-%d'),
        } for c in codes]

    @staticmethod
    @transaction.atomic
    def deactivate_code(code_id: int, user) -> dict:
        """Code deactivate করো।"""
        from api.referral.models import ReferralCode

        try:
            code = ReferralCode.objects.get(id=code_id, user=user)
        except ReferralCode.DoesNotExist:
            return {'success': False, 'error': 'Code not found'}

        if code.is_primary:
            return {'success': False, 'error': 'Cannot deactivate primary code'}

        code.is_active = False
        code.save(update_fields=['is_active'])

        return {'success': True, 'code_id': code.id}

    @staticmethod
    @transaction.atomic
    def set_custom_code(code_id: int, user, custom_code: str) -> dict:
        """Code এর custom alias set করো।"""
        from api.referral.models import ReferralCode

        try:
            code = ReferralCode.objects.get(id=code_id, user=user)
        except ReferralCode.DoesNotExist:
            return {'success': False, 'error': 'Code not found'}

        custom_code = custom_code.strip().upper()

        if ReferralCode.objects.filter(
            custom_code=custom_code
        ).exclude(id=code_id).exists():
            return {'success': False, 'error': 'Custom code already taken'}

        code.custom_code = custom_code
        code.save(update_fields=['custom_code'])

        return {
            'success': True,
            'code_id': code.id,
            'custom_code': custom_code,
        }