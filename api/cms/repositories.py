# api/cms/repositories.py
"""Data repositories for CMS."""
from decimal import Decimal
from django.db import transaction as db_transaction
from django.db.models import Count
from django.db.models import F
from django.db.models import QuerySet
from django.db.models import Sum
from typing import Tuple
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar
from django.db import models
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Type variable for model types
ModelType = TypeVar('ModelType', bound=models.Model)


# ── Original Repositories (Preserved) ─────────────────────────────────────

class UserRepository:
    @staticmethod
    def get_by_id(user_id: int):
        from django.contrib.auth import get_user_model
        try:
            return get_user_model().objects.select_related(
                'profile', 'referral_code', 'earning_streak'
            ).get(id=user_id)
        except get_user_model().DoesNotExist:
            return None

    @staticmethod
    def get_by_username(username: str):
        from django.contrib.auth import get_user_model
        try:
            return get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist:
            return None

    @staticmethod
    def exists(user_id: int) -> bool:
        from django.contrib.auth import get_user_model
        return get_user_model().objects.filter(id=user_id, is_active=True).exists()


class VirtualBalanceRepository:
    @staticmethod
    def get(user) -> Optional[Any]:
        try:
            from api.cms.models_new.cpalead import UserVirtualBalance
            return UserVirtualBalance.objects.select_for_update().select_related('currency').get(user=user)
        except Exception:
            return None

    @staticmethod
    def get_or_create(user) -> Tuple[Any, bool]:
        from api.cms.models_new.cpalead import UserVirtualBalance, VirtualCurrency
        vc = VirtualCurrency.get_active()
        if not vc:
            raise ValueError("No active virtual currency")
        return UserVirtualBalance.objects.get_or_create(
            user=user,
            defaults={'currency': vc, 'balance': Decimal('0')}
        )

    @staticmethod
    def add_coins(user, amount: Decimal, source_id: str = '', description: str = '') -> bool:
        from api.cms.models_new.cpalead import UserVirtualBalance
        try:
            with db_transaction.atomic():
                bal = UserVirtualBalance.objects.select_for_update().get(user=user)
                return bal.add_coins(amount)
        except Exception as e:
            logger.error(f"[Repo] add_coins failed for user {user.id}: {e}")
            return False

    @staticmethod
    def spend_coins(user, amount: Decimal) -> bool:
        from api.cms.models_new.cpalead import UserVirtualBalance
        try:
            with db_transaction.atomic():
                bal = UserVirtualBalance.objects.select_for_update().get(user=user)
                return bal.spend_coins(amount)
        except Exception as e:
            logger.error(f"[Repo] spend_coins failed for user {user.id}: {e}")
            return False


class ConversionLogRepository:
    @staticmethod
    def create(data: Dict) -> Any:
        from api.cms.models_new.cpalead import ConversionLog
        return ConversionLog.objects.create(**data)

    @staticmethod
    def exists_by_lead_id(lead_id: str) -> bool:
        from api.cms.models_new.cpalead import ConversionLog
        return ConversionLog.objects.filter(lead_id=lead_id).exists()

    @staticmethod
    def mark_approved(conversion_id: int, virtual_amount: Decimal = Decimal('0')) -> bool:
        from api.cms.models_new.cpalead import ConversionLog
        updated = ConversionLog.objects.filter(id=conversion_id, status='pending').update(
            status='approved',
            virtual_amount_awarded=virtual_amount,
        )
        return bool(updated)

    @staticmethod
    def get_by_user(user, limit: int = 50) -> QuerySet:
        from api.cms.models_new.cpalead import ConversionLog
        return ConversionLog.objects.filter(user=user).order_by('-created_at')[:limit]

    @staticmethod
    def get_stats_for_user(user) -> Dict:
        from api.cms.models_new.cpalead import ConversionLog
        return ConversionLog.objects.filter(user=user, status='approved').aggregate(
            total_count=Count('id'),
            total_usd=Sum('payout_usd'),
            total_coins=Sum('virtual_amount_awarded'),
        )


class ClickLogRepository:
    @staticmethod
    def create(data: Dict) -> Any:
        from api.cms.models_new.cpalead import ClickLog
        return ClickLog.objects.create(**data)

    @staticmethod
    def count_by_ip(ip: str, window_hours: int = 1) -> int:
        from api.cms.models_new.cpalead import ClickLog
        import datetime
        cutoff = timezone.now() - datetime.timedelta(hours=window_hours)
        return ClickLog.objects.filter(ip_address=ip, created_at__gte=cutoff).count()

    @staticmethod
    def mark_converted(click_id: str) -> bool:
        from api.cms.models_new.cpalead import ClickLog
        updated = ClickLog.objects.filter(click_id=click_id).update(has_converted=True)
        return bool(updated)


class WithdrawalRepository:
    @staticmethod
    def create(data: Dict) -> Any:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.create(**data)

    @staticmethod
    def get_by_uuid(uuid_str: str) -> Optional[Any]:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        try:
            return WithdrawalRequest.objects.get(uuid=uuid_str)
        except Exception:
            return None

    @staticmethod
    def get_pending(limit: int = 100) -> QuerySet:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.filter(
            status='pending'
        ).select_related('user').order_by('created_at')[:limit]

    @staticmethod
    def update_status(request_id: int, status: str, **extra_fields) -> bool:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        update_data = {'status': status, **extra_fields}
        updated = WithdrawalRequest.objects.filter(id=request_id).update(**update_data)
        return bool(updated)

    @staticmethod
    def get_user_history(user, limit: int = 50) -> QuerySet:
        from api.cms.models_new.withdrawal import WithdrawalRequest
        return WithdrawalRequest.objects.filter(user=user).order_by('-created_at')[:limit]


class ReferralRepository:
    @staticmethod
    def get_relationship(referred_user) -> Optional[Any]:
        from api.cms.models_new.referral import ReferralRelationship
        try:
            return ReferralRelationship.objects.select_for_update().select_related(
                'referrer', 'referral_code'
            ).get(referred=referred_user, is_active=True)
        except Exception:
            return None

    @staticmethod
    def create_relationship(data: Dict) -> Any:
        from api.cms.models_new.referral import ReferralRelationship
        return ReferralRelationship.objects.create(**data)

    @staticmethod
    def create_earning(data: Dict) -> Any:
        from api.cms.models_new.referral import ReferralEarning
        return ReferralEarning.objects.create(**data)

    @staticmethod
    def get_code(user) -> Optional[Any]:
        from api.cms.models_new.referral import ReferralCode
        try:
            return ReferralCode.objects.get(user=user, is_active=True)
        except Exception:
            return None

    @staticmethod
    def get_code_by_value(code: str) -> Optional[Any]:
        from api.cms.models_new.referral import ReferralCode
        try:
            return ReferralCode.objects.select_related('user').get(
                code=code.upper().strip(), is_active=True
            )
        except Exception:
            return None


class NotificationRepository:
    @staticmethod
    def create(user, notification_type: str, title: str, message: str,
               extra_data: Dict = None) -> Any:
        try:
            from api.cms.models_new.extras import Notification
            return Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                extra_data=extra_data or {},
            )
        except Exception as e:
            logger.warning(f"[Repo] Notification create failed: {e}")
            return None

    @staticmethod
    def get_unread(user, limit: int = 20) -> QuerySet:
        try:
            from api.cms.models_new.extras import Notification
            return Notification.objects.filter(
                user=user, is_read=False
            ).order_by('-created_at')[:limit]
        except Exception:
            return []

    @staticmethod
    def mark_all_read(user) -> int:
        try:
            from api.cms.models_new.extras import Notification
            return Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        except Exception:
            return 0


class ContentBlockRepository:
    @staticmethod
    def get_for_page(parent_type: str, parent_id: int) -> QuerySet:
        from api.cms.models_new.blocks import ContentBlock
        return ContentBlock.objects.filter(
            parent_type=parent_type,
            parent_id=parent_id,
            is_visible=True,
        ).order_by('order')

    @staticmethod
    def create(data: Dict) -> Any:
        from api.cms.models_new.blocks import ContentBlock
        return ContentBlock.objects.create(**data)

    @staticmethod
    def update(block_id: int, data: Dict, update_fields: List[str] = None) -> bool:
        from api.cms.models_new.blocks import ContentBlock
        updated = ContentBlock.objects.filter(id=block_id).update(**data)
        return bool(updated)

    @staticmethod
    def delete(block_id: int) -> bool:
        from api.cms.models_new.blocks import ContentBlock
        deleted, _ = ContentBlock.objects.filter(id=block_id).delete()
        return bool(deleted)


class FormSubmissionRepository:
    @staticmethod
    def create(form_id: int, data: Dict, user=None, ip: str = '') -> Any:
        from api.cms.models_new.forms import FormSubmission
        return FormSubmission.objects.create(
            form_id=form_id,
            user=user,
            data=data,
            ip_address=ip or None,
        )

    @staticmethod
    def get_for_form(form_id: int, limit: int = 100) -> QuerySet:
        from api.cms.models_new.forms import FormSubmission
        return FormSubmission.objects.filter(form_id=form_id).order_by('-submitted_at')[:limit]

    @staticmethod
    def count_user_submissions(form_id: int, user) -> int:
        from api.cms.models_new.forms import FormSubmission
        return FormSubmission.objects.filter(form_id=form_id, user=user).count()


class SmartLinkRepository:
    @staticmethod
    def get_by_slug(slug: str) -> Optional[Any]:
        from api.cms.models_new.smartlink import SmartLink
        try:
            return SmartLink.objects.prefetch_related(
                'routing_rules'
            ).get(slug=slug, is_active=True)
        except Exception:
            return None

    @staticmethod
    def increment_clicks(smartlink_id: int) -> None:
        from api.cms.models_new.smartlink import SmartLink
        SmartLink.objects.filter(id=smartlink_id).update(total_clicks=F('total_clicks') + 1)

    @staticmethod
    def log_click(data: Dict) -> Any:
        from api.cms.models_new.smartlink import SmartLinkClick
        try:
            return SmartLinkClick.objects.create(**data)
        except Exception:
            return None


class UserProfileRepository:
    @staticmethod
    def get_or_create(user) -> Tuple[Any, bool]:
        from api.cms.models_new.withdrawal import UserProfile
        return UserProfile.objects.get_or_create(user=user)

    @staticmethod
    def update_earnings(user, usd: Decimal = Decimal('0'),
                        coins: Decimal = Decimal('0')) -> None:
        from api.cms.models_new.withdrawal import UserProfile
        update_fields = {}
        if usd > 0:
            update_fields['total_earned_usd'] = F('total_earned_usd') + usd
        if coins > 0:
            update_fields['total_earned_coins'] = F('total_earned_coins') + coins
        if update_fields:
            UserProfile.objects.filter(user=user).update(**update_fields)

    @staticmethod
    def increment_offer_count(user) -> None:
        from api.cms.models_new.withdrawal import UserProfile
        UserProfile.objects.filter(user=user).update(
            total_offers_completed=F('total_offers_completed') + 1
        )


# ── Enhanced Repository Classes ─────────────────────────────────────

class BaseRepository:
    """Base repository with common functionality."""
    
    def __init__(self, model: Type[ModelType]):
        """Initialize repository with model."""
        self.model = model
        self.logger = logging.getLogger(f"{__name__}.{model.__name__}")
    
    def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get record by ID."""
        try:
            return self.model.objects.get(id=id)
        except self.model.DoesNotExist:
            return None
        except Exception as e:
            self.logger.error(f"Error getting {self.model.__name__} by ID {id}: {e}")
            return None
    
    def create(self, **kwargs) -> Optional[ModelType]:
        """Create new record."""
        try:
            instance = self.model.objects.create(**kwargs)
            self.logger.info(f"Created {self.model.__name__}: {instance.id}")
            return instance
        except Exception as e:
            self.logger.error(f"Error creating {self.model.__name__}: {e}")
            return None
    
    def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """Update record by ID."""
        try:
            instance = self.model.objects.get(id=id)
            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)
            instance.save()
            self.logger.info(f"Updated {self.model.__name__}: {instance.id}")
            return instance
        except self.model.DoesNotExist:
            self.logger.error(f"{self.model.__name__} with ID {id} not found")
            return None
        except Exception as e:
            self.logger.error(f"Error updating {self.model.__name__} {id}: {e}")
            return None
    
    def delete(self, id: int) -> bool:
        """Delete record by ID."""
        try:
            instance = self.model.objects.get(id=id)
            instance.delete()
            self.logger.info(f"Deleted {self.model.__name__}: {instance.id}")
            return True
        except self.model.DoesNotExist:
            self.logger.error(f"{self.model.__name__} with ID {id} not found")
            return False
        except Exception as e:
            self.logger.error(f"Error deleting {self.model.__name__} {id}: {e}")
            return False
    
    def exists(self, **kwargs) -> bool:
        """Check if record exists."""
        try:
            return self.model.objects.filter(**kwargs).exists()
        except Exception as e:
            self.logger.error(f"Error checking {self.model.__name__} existence: {e}")
            return False


class SurveyRepository(BaseRepository):
    """Enhanced repository for Survey model."""
    
    def __init__(self):
        from api.cms.models_new.survey import Survey
        super().__init__(Survey)
    
    def get_active_surveys(self) -> models.QuerySet:
        """Get active surveys."""
        try:
            return self.model.objects.filter(is_active=True)
        except Exception as e:
            self.logger.error(f"Error getting active surveys: {e}")
            return self.model.objects.none()
    
    def get_surveys_by_category(self, category: str) -> models.QuerySet:
        """Get surveys by category."""
        return self.filter_by_field('category', category)
    
    def get_featured_surveys(self, limit: int = 10) -> List[ModelType]:
        """Get featured surveys."""
        try:
            return list(self.model.objects.filter(
                is_featured=True,
                is_active=True
            ).order_by('-created_at')[:limit])
        except Exception as e:
            self.logger.error(f"Error getting featured surveys: {e}")
            return []


class RewardRepository(BaseRepository):
    """Enhanced repository for RewardTransaction model."""
    
    def __init__(self):
        from api.cms.models_new.rewards import RewardTransaction
        super().__init__(RewardTransaction)
    
    def get_user_balance(self, user_id: int) -> float:
        """Calculate user's current balance."""
        try:
            from django.db.models import Sum
            earned = self.model.objects.filter(
                user_id=user_id,
                transaction_type='earned',
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            withdrawn = self.model.objects.filter(
                user_id=user_id,
                transaction_type='withdrawal',
                status__in=['pending', 'completed']
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            return float(earned - withdrawn)
        except Exception as e:
            self.logger.error(f"Error calculating user balance: {e}")
            return 0.0


# ── Repository Manager ─────────────────────────────────────

class EnhancedRepositoryManager:
    """Manager for accessing enhanced repositories."""
    
    def __init__(self):
        """Initialize repository manager."""
        self.survey = SurveyRepository()
        self.reward = RewardRepository()
        self.logger = logging.getLogger(f"{__name__}.manager")
    
    def get_repository(self, model_name: str) -> Optional[BaseRepository]:
        """Get repository by model name."""
        repository_map = {
            'survey': self.survey,
            'reward': self.reward
        }
        return repository_map.get(model_name.lower())
    
    def create_repository(self, model: Type[ModelType]) -> BaseRepository:
        """Create repository for any model."""
        return BaseRepository(model)


# Global enhanced repository manager
enhanced_repository_manager = EnhancedRepositoryManager()
