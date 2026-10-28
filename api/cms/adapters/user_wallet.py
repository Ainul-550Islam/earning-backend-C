# api/cms/adapters/user_wallet.py
"""
Adapters for api.users and api.wallet

  UserAdapter   — get_user, get_user_profile, check_permission
  WalletAdapter — credit, debit, get_balance, get_transactions
"""
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


# ══════════════════════════════════════════════════════════════════════════════
# USER ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class UserAdapter(BaseAdapter):
    """CMS → api.users interface."""

    _system_name = 'api.users'

    @classmethod
    def _check_available(cls):
        from api.users.models import User  # noqa

    @classmethod
    def get_user(cls, user_id: int) -> Optional[Any]:
        """Fetch a user object by PK."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.filter(pk=user_id).first()
        except Exception as e:
            logger.warning("[CMS→Users] get_user(%s) failed: %s", user_id, e)
            return None

    @classmethod
    def get_user_profile(cls, user) -> Optional[Dict]:
        """Fetch extended profile from api.users if available."""
        try:
            from api.users.models import UserProfile
            profile = UserProfile.objects.filter(user=user).first()
            if profile:
                return {
                    'level': getattr(profile, 'level', 0),
                    'tier': getattr(profile, 'tier', 'basic'),
                    'country': getattr(profile, 'country', ''),
                    'kyc_verified': getattr(profile, 'kyc_verified', False),
                    'is_premium': getattr(profile, 'is_premium', False),
                }
            return {}
        except ImportError:
            return cls._unavailable('get_user_profile', {})
        except Exception as e:
            logger.warning("[CMS→Users] get_user_profile failed: %s", e)
            return {}

    @classmethod
    def check_permission(cls, user, permission: str) -> bool:
        """Check if user has a named permission (uses Django's standard permission system)."""
        try:
            return user.has_perm(permission)
        except Exception:
            return False

    @classmethod
    def get_user_country(cls, user) -> str:
        """Best-effort country resolution (profile → request IP fallback)."""
        try:
            from api.users.models import UserProfile
            profile = UserProfile.objects.filter(user=user).values('country').first()
            return (profile or {}).get('country', '')
        except ImportError:
            return getattr(user, 'country', '')
        except Exception:
            return ''

    @classmethod
    def get_users_by_segment(cls, segment_name: str) -> List[Any]:
        """Fetch user list for a named segment (used by CMS targeting)."""
        try:
            from api.users.models import UserSegment
            segment = UserSegment.objects.filter(name=segment_name, is_active=True).first()
            if segment:
                return list(segment.users.all())
            return []
        except ImportError:
            return []
        except Exception as e:
            logger.warning("[CMS→Users] get_users_by_segment(%s) failed: %s", segment_name, e)
            return []


# ══════════════════════════════════════════════════════════════════════════════
# WALLET ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class WalletAdapter(BaseAdapter):
    """CMS → api.wallet interface."""

    _system_name = 'api.wallet'

    @classmethod
    def _check_available(cls):
        from api.wallet.models import WalletTransaction  # noqa

    @classmethod
    def credit(
        cls,
        user,
        amount_usd: Decimal,
        source: str,
        ref_id: str = '',
        description: str = '',
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Credit user wallet. Returns True on success.
        CMS does NOT own the wallet — this is a one-way call only.
        """
        try:
            from api.wallet.models import WalletTransaction
            WalletTransaction.objects.create(
                user=user,
                tx_type='credit',
                amount=amount_usd,
                source=source,
                reference_id=ref_id,
                description=description,
                metadata=metadata or {},
            )
            logger.info("[CMS→Wallet] Credited $%s to user %s (source=%s)", amount_usd, user.pk, source)
            return True
        except ImportError:
            return cls._unavailable('credit', False)
        except Exception as e:
            logger.error("[CMS→Wallet] credit failed for user %s: %s", getattr(user, 'pk', '?'), e)
            return False

    @classmethod
    def debit(
        cls,
        user,
        amount_usd: Decimal,
        source: str,
        ref_id: str = '',
        description: str = '',
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Debit user wallet. Returns True on success."""
        try:
            from api.wallet.models import WalletTransaction
            WalletTransaction.objects.create(
                user=user,
                tx_type='debit',
                amount=amount_usd,
                source=source,
                reference_id=ref_id,
                description=description,
                metadata=metadata or {},
            )
            return True
        except ImportError:
            return cls._unavailable('debit', False)
        except Exception as e:
            logger.error("[CMS→Wallet] debit failed for user %s: %s", getattr(user, 'pk', '?'), e)
            return False

    @classmethod
    def get_balance(cls, user) -> Dict[str, Decimal]:
        """Return {'usd': Decimal, 'coins': Decimal} for the user."""
        try:
            from api.wallet.models import UserWallet
            wallet = UserWallet.objects.filter(user=user).first()
            if wallet:
                return {
                    'usd': Decimal(str(getattr(wallet, 'balance_usd', 0))),
                    'coins': Decimal(str(getattr(wallet, 'balance_coins', 0))),
                }
            return {'usd': Decimal('0'), 'coins': Decimal('0')}
        except ImportError:
            return cls._unavailable('get_balance', {'usd': Decimal('0'), 'coins': Decimal('0')})
        except Exception as e:
            logger.warning("[CMS→Wallet] get_balance failed: %s", e)
            return {'usd': Decimal('0'), 'coins': Decimal('0')}

    @classmethod
    def get_transaction_history(cls, user, limit: int = 50) -> List[Dict]:
        """Fetch recent transactions for a user."""
        try:
            from api.wallet.models import WalletTransaction
            txns = WalletTransaction.objects.filter(user=user).order_by('-created_at')[:limit]
            return [
                {
                    'id': t.pk,
                    'type': t.tx_type,
                    'amount': float(t.amount),
                    'source': t.source,
                    'description': t.description,
                    'created_at': t.created_at.isoformat(),
                }
                for t in txns
            ]
        except ImportError:
            return cls._unavailable('get_transaction_history', [])
        except Exception as e:
            logger.warning("[CMS→Wallet] get_transaction_history failed: %s", e)
            return []
