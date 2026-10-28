# api/admin_panel/repositories.py
"""
Admin Panel Repositories — Data Access Layer (Repository Pattern).
Each repository = one model's data access.
All DB operations (read + write) go through repositories.
Decouples business logic from ORM.

Usage:
    from api.admin_panel.repositories import UserRepository, WalletRepository
    user = UserRepository.get_by_id(123)
    WalletRepository.freeze(user_id=123)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


# ===========================================================================
# BASE REPOSITORY
# ===========================================================================

class BaseRepository:
    model = None

    @classmethod
    def get_by_id(cls, pk: Any):
        try:
            return cls.model.objects.get(pk=pk)
        except cls.model.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"[{cls.__name__}.get_by_id] {e}")
            return None

    @classmethod
    def get_all(cls, **filters) -> QuerySet:
        return cls.model.objects.filter(**filters)

    @classmethod
    def count(cls, **filters) -> int:
        return cls.model.objects.filter(**filters).count()

    @classmethod
    def exists(cls, **filters) -> bool:
        return cls.model.objects.filter(**filters).exists()

    @classmethod
    def delete(cls, pk: Any) -> bool:
        try:
            cls.model.objects.filter(pk=pk).delete()
            return True
        except Exception:
            return False

    @classmethod
    def bulk_update(cls, queryset, **fields) -> int:
        return queryset.update(**fields)


# ===========================================================================
# USER REPOSITORY
# ===========================================================================

class UserRepository(BaseRepository):
    model = User

    @classmethod
    def get_by_id(cls, user_id: Any) -> Optional[User]:
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    @classmethod
    def get_by_username(cls, username: str) -> Optional[User]:
        try:
            return User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            return None

    @classmethod
    def get_by_email(cls, email: str) -> Optional[User]:
        try:
            return User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None

    @classmethod
    def ban(cls, user_id: Any) -> bool:
        return bool(User.objects.filter(pk=user_id, is_active=True).update(is_active=False))

    @classmethod
    def unban(cls, user_id: Any) -> bool:
        return bool(User.objects.filter(pk=user_id, is_active=False).update(is_active=True))

    @classmethod
    def search(cls, q: str, limit: int = 50) -> QuerySet:
        return User.objects.filter(
            Q(username__icontains=q) | Q(email__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )[:limit]

    @classmethod
    def get_new_users(cls, days: int = 7) -> QuerySet:
        cutoff = timezone.now() - timedelta(days=days)
        return User.objects.filter(date_joined__gte=cutoff).order_by('-date_joined')

    @classmethod
    def get_inactive_users(cls, days_since_login: int = 30) -> QuerySet:
        cutoff = timezone.now() - timedelta(days=days_since_login)
        return User.objects.filter(
            is_active=True,
            last_login__lt=cutoff
        )

    @classmethod
    def bulk_ban(cls, user_ids: List[Any]) -> int:
        return User.objects.filter(pk__in=user_ids, is_active=True).update(is_active=False)


# ===========================================================================
# WALLET REPOSITORY
# ===========================================================================

class WalletRepository(BaseRepository):

    @classmethod
    def get_by_user(cls, user_id: Any):
        try:
            from api.wallet.models import Wallet
            return Wallet.objects.get(user_id=user_id)
        except Exception:
            return None

    @classmethod
    def freeze(cls, user_id: Any) -> bool:
        try:
            from api.wallet.models import Wallet
            return bool(Wallet.objects.filter(user_id=user_id, is_locked=False).update(is_locked=True))
        except Exception:
            return False

    @classmethod
    def unfreeze(cls, user_id: Any) -> bool:
        try:
            from api.wallet.models import Wallet
            return bool(Wallet.objects.filter(user_id=user_id, is_locked=True).update(is_locked=False))
        except Exception:
            return False

    @classmethod
    def adjust_balance(cls, user_id: Any, amount) -> Tuple[bool, float]:
        """Adjust wallet balance. Returns (success, new_balance)."""
        try:
            from api.wallet.models import Wallet
            from decimal import Decimal
            with transaction.atomic():
                wallet = Wallet.objects.select_for_update().get(user_id=user_id)
                wallet.current_balance += Decimal(str(amount))
                if wallet.current_balance < 0:
                    return False, float(wallet.current_balance - Decimal(str(amount)))
                wallet.save(update_fields=['balance'])
                return True, float(wallet.current_balance)
        except Exception as e:
            logger.error(f"[WalletRepository.adjust_balance] {e}")
            return False, 0.0

    @classmethod
    def get_balance(cls, user_id: Any) -> float:
        try:
            from api.wallet.models import Wallet
            wallet = Wallet.objects.get(user_id=user_id)
            return float(wallet.current_balance)
        except Exception:
            return 0.0

    @classmethod
    def get_top_balances(cls, limit: int = 20) -> List[Dict]:
        try:
            from api.wallet.models import Wallet
            return list(
                Wallet.objects.filter(is_locked=False, balance__gt=0)
                .values('user_id', 'balance').order_by('-balance')[:limit]
            )
        except Exception:
            return []


# ===========================================================================
# PAYOUT REPOSITORY
# ===========================================================================

class PayoutRepository(BaseRepository):

    @classmethod
    def get_pending(cls, limit: int = 100) -> QuerySet:
        try:
            from api.payout_queue.models import PayoutItem
            return PayoutItem.objects.filter(status='QUEUED').select_related('user').order_by('created_at')[:limit]
        except Exception:
            return []

    @classmethod
    def approve(cls, item_id: Any, approved_by, transaction_ref: str = '') -> bool:
        try:
            from api.payout_queue.models import PayoutItem
            updated = PayoutItem.objects.filter(pk=item_id, status='QUEUED').update(
                status='SUCCESS',
                gateway_reference=transaction_ref[:200] if transaction_ref else '',
            )
            return bool(updated)
        except Exception:
            return False

    @classmethod
    def reject(cls, item_id: Any, rejected_by, reason: str) -> bool:
        try:
            from api.payout_queue.models import PayoutItem
            updated = PayoutItem.objects.filter(pk=item_id, status='QUEUED').update(
                status='FAILED',
                error_message=reason[:500],
            )
            return bool(updated)
        except Exception:
            return False

    @classmethod
    def cancel_for_user(cls, user_id: Any) -> int:
        try:
            from api.payout_queue.models import PayoutItem
            return PayoutItem.objects.filter(user_id=user_id, status='QUEUED').update(status='CANCELLED')
        except Exception:
            return 0

    @classmethod
    def get_stats(cls, days: int = 7) -> Dict:
        try:
            from api.payout_queue.models import PayoutItem
            from django.db.models import Count, Sum
            cutoff = timezone.now() - timedelta(days=days)
            return PayoutItem.objects.filter(created_at__gte=cutoff).aggregate(
                total=Count('id'),
                pending=Count('id', filter=Q(status='QUEUED')),
                approved=Count('id', filter=Q(status='SUCCESS')),
                paid=Count('id', filter=Q(status='SUCCESS')),
                rejected=Count('id', filter=Q(status='FAILED')),
                total_amount=Sum('amount', filter=Q(status='SUCCESS')),
            )
        except Exception:
            return {}


# ===========================================================================
# FRAUD REPOSITORY
# ===========================================================================

class FraudRepository(BaseRepository):

    @classmethod
    def block_ip(cls, ip: str, reason: str, is_permanent: bool = False) -> Tuple[bool, bool]:
        """Block IP. Returns (success, created)."""
        try:
            from api.fraud_detection.models import BlockedIP
            obj, created = BlockedIP.objects.get_or_create(
                ip_address=ip,
                defaults={'reason': reason, 'is_permanent': is_permanent}
            )
            if not created:
                obj.reason = reason
                obj.is_permanent = is_permanent
                obj.save(update_fields=['reason', 'is_permanent'])
            return True, created
        except Exception as e:
            logger.error(f"[FraudRepository.block_ip] {e}")
            return False, False

    @classmethod
    def unblock_ip(cls, ip: str) -> bool:
        try:
            from api.fraud_detection.models import BlockedIP
            deleted, _ = BlockedIP.objects.filter(ip_address=ip).delete()
            return bool(deleted)
        except Exception:
            return False

    @classmethod
    def get_fraud_rules(cls, is_active: Optional[bool] = None) -> List[Dict]:
        try:
            from api.fraud_detection.models import FraudRule
            qs = FraudRule.objects.all()
            if is_active is not None:
                qs = qs.filter(is_active=is_active)
            return list(qs.values('id', 'name', 'rule_type', 'is_active', 'weight', 'action_on_trigger'))
        except Exception:
            return []

    @classmethod
    def update_fraud_settings(cls, settings_data: Dict) -> bool:
        try:
            from api.fraud_detection.models import FraudSettings
            settings = FraudSettings.objects.first()
            if settings:
                for key, value in settings_data.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                settings.save()
                return True
            return False
        except Exception:
            return False


# ===========================================================================
# KYC REPOSITORY
# ===========================================================================

class KYCRepository(BaseRepository):

    @classmethod
    def get_by_id(cls, kyc_id: Any):
        try:
            from api.kyc.models import KYC
            return KYC.objects.select_related('user').get(pk=kyc_id)
        except Exception:
            return None

    @classmethod
    def get_by_user(cls, user_id: Any):
        try:
            from api.kyc.models import KYC
            return KYC.objects.filter(user_id=user_id).first()
        except Exception:
            return None

    @classmethod
    def approve(cls, kyc_id: Any, reviewed_by, notes: str = '') -> bool:
        try:
            from api.kyc.models import KYC
            return bool(KYC.objects.filter(pk=kyc_id, status='QUEUED').update(
                status='SUCCESS', reviewed_by=reviewed_by,
                reviewed_at=timezone.now(), reviewer_notes=notes,
            ))
        except Exception:
            return False

    @classmethod
    def reject(cls, kyc_id: Any, reviewed_by, reason: str) -> bool:
        try:
            from api.kyc.models import KYC
            return bool(KYC.objects.filter(pk=kyc_id, status='QUEUED').update(
                status='FAILED', reviewed_by=reviewed_by,
                reviewed_at=timezone.now(), rejection_reason=reason,
            ))
        except Exception:
            return False

    @classmethod
    def get_pending_count(cls) -> int:
        try:
            from api.kyc.models import KYC
            return KYC.objects.filter(status='QUEUED').count()
        except Exception:
            return 0


# ===========================================================================
# ADMIN ACTIVITY REPOSITORY
# ===========================================================================

class AdminActivityRepository(BaseRepository):

    @classmethod
    def create(cls, actor, action: str, model_name: str = '',
               object_id: str = '', changes: Dict = None, status: str = 'success',
               ip: str = '', method: str = '', path: str = '') -> Optional[Any]:
        try:
            from api.admin_panel.models.activity import AdminActivity
            return AdminActivity.log(
                actor=actor, action=action, model_name=model_name,
                object_id=object_id, changes=changes or {}, status=status,
                ip=ip, method=method, path=path,
            )
        except Exception as e:
            logger.debug(f"[AdminActivityRepository.create] {e}")
            return None

    @classmethod
    def get_recent(cls, actor=None, days: int = 7, limit: int = 100) -> List[Dict]:
        try:
            from api.admin_panel.models.activity import AdminActivity
            cutoff = timezone.now() - timedelta(days=days)
            qs = AdminActivity.objects.filter(created_at__gte=cutoff)
            if actor:
                qs = qs.filter(actor=actor)
            return list(qs.values(
                'id', 'actor__username', 'action', 'model_name', 'status', 'created_at'
            ).order_by('-created_at')[:limit])
        except Exception:
            return []


# ===========================================================================
# SYSTEM CONFIG REPOSITORY
# ===========================================================================

class SystemConfigRepository(BaseRepository):

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        try:
            from api.admin_panel.models.config import SystemConfig
            obj = SystemConfig.objects.get(key=key)
            return obj.get_typed_value()
        except Exception:
            return default

    @classmethod
    def set(cls, key: str, value: Any, value_type: str = 'string', group: str = 'general') -> bool:
        try:
            from api.admin_panel.models.config import SystemConfig
            SystemConfig.objects.update_or_create(
                key=key,
                defaults={'value': str(value), 'value_type': value_type, 'group': group}
            )
            from django.core.cache import cache
            cache.delete(f'admin_panel:config:{key}')
            return True
        except Exception:
            return False

    @classmethod
    def get_group(cls, group: str) -> Dict:
        try:
            from api.admin_panel.models.config import SystemConfig
            return {obj.key: obj.get_typed_value() for obj in SystemConfig.objects.filter(group=group)}
        except Exception:
            return {}


# ===========================================================================
# NOTIFICATION REPOSITORY
# ===========================================================================

class NotificationRepository(BaseRepository):

    @classmethod
    def send_to_user(cls, user_id: Any, title: str, message: str, notification_type: str = 'info') -> bool:
        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user_id=user_id, title=title,
                message=message, notification_type=notification_type,
            )
            return True
        except Exception as e:
            logger.debug(f"[NotificationRepository.send_to_user] {e}")
            return False

    @classmethod
    def broadcast(cls, title: str, message: str, user_ids: List[Any] = None,
                  notification_type: str = 'broadcast') -> int:
        try:
            from api.notifications.models import Notification
            from django.contrib.auth import get_user_model
            User = get_user_model()
            qs = User.objects.filter(is_active=True)
            if user_ids:
                qs = qs.filter(pk__in=user_ids)
            notifications = [
                Notification(
                    user_id=u.pk, title=title,
                    message=message, notification_type=notification_type,
                )
                for u in qs.iterator(chunk_size=500)
            ]
            Notification.objects.bulk_create(notifications, batch_size=500, ignore_conflicts=True)
            return len(notifications)
        except Exception as e:
            logger.error(f"[NotificationRepository.broadcast] {e}")
            return 0