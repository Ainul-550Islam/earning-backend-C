# api/offer_inventory/marketing/promotional_codes.py
"""
Promotional Codes System.
Generate, validate, and redeem promo codes.
Supports percentage discounts, fixed bonuses, free offers.
"""
import logging
import secrets
import string
from decimal import Decimal
from datetime import timedelta
from django.db import models, transaction
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

CODE_CHARSET = string.ascii_uppercase + string.digits
CODE_CACHE_TTL = 300   # 5 min


class PromoCodeManager:
    """Generate and manage promotional codes."""

    @staticmethod
    def generate_code(length: int = 8) -> str:
        """Generate a unique promo code."""
        return ''.join(secrets.choice(CODE_CHARSET) for _ in range(length))

    @classmethod
    def create_campaign(cls, name: str, code_type: str,
                         value: Decimal, count: int = 100,
                         max_per_user: int = 1,
                         expires_days: int = 30,
                         tenant=None) -> list:
        """
        Create a batch of promo codes.
        code_type: 'flat_bonus' | 'pct_bonus' | 'free_offer'
        value: bonus amount (BDT) or percentage
        Returns list of code strings.
        """
        from api.offer_inventory.models import SystemSetting

        codes    = []
        existing = set()

        for _ in range(count):
            while True:
                code = cls.generate_code()
                if code not in existing:
                    existing.add(code)
                    break

            # Store in SystemSetting as JSON blob
            key = f'promo_code:{code}'
            data = {
                'name'        : name,
                'code'        : code,
                'code_type'   : code_type,
                'value'       : str(value),
                'max_per_user': max_per_user,
                'used_count'  : 0,
                'expires_at'  : (timezone.now() + timedelta(days=expires_days)).isoformat(),
                'created_at'  : timezone.now().isoformat(),
                'is_active'   : True,
                'tenant'      : str(tenant.id) if tenant else None,
            }
            try:
                SystemSetting.objects.create(
                    tenant     =tenant,
                    key        =key,
                    value      =__import__('json').dumps(data),
                    value_type ='json',
                    description=f'Promo code: {name}',
                )
            except Exception:
                pass
            codes.append(code)

        logger.info(f'Created {count} promo codes for campaign: {name}')
        return codes

    @classmethod
    @transaction.atomic
    def redeem(cls, code: str, user) -> dict:
        """
        Redeem a promo code for a user.
        Returns {'success': bool, 'reward': Decimal, 'message': str}
        """
        import json
        from api.offer_inventory.models import SystemSetting

        # Load code data
        cache_key = f'promo_cache:{code}'
        data_str  = cache.get(cache_key)
        if not data_str:
            try:
                setting  = SystemSetting.objects.get(key=f'promo_code:{code}')
                data_str = setting.value
                cache.set(cache_key, data_str, CODE_CACHE_TTL)
            except SystemSetting.DoesNotExist:
                return {'success': False, 'reward': Decimal('0'), 'message': 'Code not found'}

        try:
            data = json.loads(data_str)
        except Exception:
            return {'success': False, 'reward': Decimal('0'), 'message': 'Invalid code data'}

        # Validity checks
        if not data.get('is_active'):
            return {'success': False, 'reward': Decimal('0'), 'message': 'Code is no longer active'}

        from django.utils.dateparse import parse_datetime
        expires = parse_datetime(data.get('expires_at', ''))
        if expires and timezone.now() > expires:
            return {'success': False, 'reward': Decimal('0'), 'message': 'Code has expired'}

        # Per-user limit check
        user_key  = f'promo_used:{code}:{user.id}'
        used_count = cache.get(user_key, 0)
        if used_count >= data.get('max_per_user', 1):
            return {'success': False, 'reward': Decimal('0'), 'message': 'Code already used'}

        # Calculate reward
        code_type = data.get('code_type', 'flat_bonus')
        value     = Decimal(str(data.get('value', '0')))
        reward    = Decimal('0')

        if code_type == 'flat_bonus':
            reward = value
        elif code_type == 'pct_bonus':
            # % of user's current balance
            try:
                from api.wallet.models import Wallet
                wallet = Wallet.objects.get(user=user)
                reward = (wallet.current_balance * value / Decimal('100')).quantize(Decimal('0.01'))
            except Exception:
                reward = Decimal('10')   # Fallback flat amount

        # Apply reward
        if reward > 0:
            from api.offer_inventory.repository import WalletRepository
            WalletRepository.credit_user(
                user_id    =user.id,
                amount     =reward,
                source     ='promo_code',
                source_id  =code,
                description=f'Promo code redeemed: {code}',
            )

        # Mark as used
        cache.set(user_key, used_count + 1, 86400 * 30)
        cache.delete(cache_key)   # Invalidate cached code data

        # Notify
        from api.offer_inventory.repository import NotificationRepository
        NotificationRepository.create(
            user_id   =user.id,
            notif_type='success',
            title     ='🎁 প্রোমো কোড সফল!',
            body      =f'আপনি {reward} টাকা বোনাস পেয়েছেন!',
        )

        logger.info(f'Promo code redeemed: {code} | user={user.id} | reward={reward}')
        return {'success': True, 'reward': reward, 'message': f'{reward} টাকা বোনাস যোগ হয়েছে!'}

    @staticmethod
    def deactivate(code: str):
        """Deactivate a promo code."""
        import json
        from api.offer_inventory.models import SystemSetting
        try:
            setting = SystemSetting.objects.get(key=f'promo_code:{code}')
            data    = json.loads(setting.value)
            data['is_active'] = False
            setting.value     = json.dumps(data)
            setting.save(update_fields=['value'])
            cache.delete(f'promo_cache:{code}')
        except Exception as e:
            logger.error(f'Deactivate promo error: {e}')
