# api/cms/abstracts.py
"""Abstract base classes for CMS models and services."""
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Type Variables ─────────────────────────────────────

T = TypeVar('T')
ModelType = TypeVar('ModelType', bound=models.Model)


# ── Original Abstract Models (Enhanced) ─────────────────────────────────────

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Override save to update timestamps."""
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
    
    def touch(self):
        """Update updated_at timestamp without saving other fields."""
        self.updated_at = timezone.now()
        self.save(update_fields=['updated_at'])


class UUIDModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class ActiveModel(models.Model):
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True

    def activate(self):
        self.is_active = True
        self.save(update_fields=['is_active'])

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=['is_active'])


class PublishableModel(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('review', 'In Review'),
        ('approved', 'Approved'), ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    status       = models.CharField(max_length=15, choices=STATUS_CHOICES,
                                    default='draft', db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
    
    def publish(self):
        """Publish the model."""
        self.status = 'published'
        self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_at'])
    
    def unpublish(self):
        """Unpublish the model."""
        self.status = 'draft'
        self.save(update_fields=['status'])
    
    def is_published(self) -> bool:
        """Check if model is published."""
        return self.status == 'published'


# ── Enhanced Abstract Models ─────────────────────────────────────

class SoftDeleteModel(models.Model):
    """Abstract model with soft delete functionality."""
    
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    class Meta:
        abstract = True
    
    def delete(self, using=None, keep_parents=False):
        """Soft delete model."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using)
    
    def hard_delete(self, using=None, keep_parents=False):
        """Permanently delete model."""
        super().delete(using=using, keep_parents=keep_parents)
    
    def restore(self):
        """Restore a soft-deleted model."""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class AuditModel(models.Model):
    """Abstract model with audit fields."""
    
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(class)s_created', db_index=True
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(class)s_updated', db_index=True
    )
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Set audit fields on save."""
        # Get current user from thread local if available
        current_user = getattr(self, '_current_user', None)
        
        if not current_user:
            try:
                from django.contrib.auth import get_current_user
                current_user = get_current_user()
            except (ImportError, AttributeError):
                pass
        
        if current_user and isinstance(current_user, User):
            if not self.pk:  # New object
                self.created_by = current_user
            self.updated_by = current_user
        
        super().save(*args, **kwargs)


# ── Combined Abstract Models ─────────────────────────────────────

class BaseCMSModel(TimestampedModel, UUIDModel, AuditModel, ActiveModel):
    """Base abstract model for all CMS models."""
    
    class Meta:
        abstract = True


class SoftDeleteCMSModel(TimestampedModel, UUIDModel, AuditModel, SoftDeleteModel):
    """Abstract model for CMS models with soft delete."""
    
    class Meta:
        abstract = True


class FullCMSModel(TimestampedModel, UUIDModel, AuditModel, SoftDeleteModel, ActiveModel):
    """Full-featured abstract model with all CMS features."""
    
    class Meta:
        abstract = True


# ── Abstract Service Classes ─────────────────────────────────────

class BaseService(ABC):
    """Abstract base class for all services."""
    
    def __init__(self, *args, **kwargs):
        """Initialize service."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute service logic."""
        pass
    
    def validate(self, *args, **kwargs) -> bool:
        """Validate service parameters."""
        return True
    
    def log_execution(self, *args, **kwargs):
        """Log service execution."""
        self.logger.info(f"Executing {self.__class__.__name__} with args: {args}, kwargs: {kwargs}")


class ModelService(BaseService, Generic[ModelType]):
    """Abstract base class for model services."""
    
    model_class: Type[ModelType] = None
    
    def __init__(self, model_class: Type[ModelType] = None):
        """Initialize model service."""
        super().__init__()
        if model_class:
            self.model_class = model_class
        
        if not self.model_class:
            raise ValueError(f"Model class must be set for {self.__class__.__name__}")
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> ModelType:
        """Execute service logic."""
        pass
    
    def get_queryset(self):
        """Get model queryset."""
        return self.model_class.objects.all()
    
    def get_instance(self, pk: Any) -> ModelType:
        """Get model instance by primary key."""
        try:
            return self.get_queryset().get(pk=pk)
        except self.model_class.DoesNotExist:
            raise ValidationError(f"{self.model_class.__name__} with pk {pk} does not exist")
    
    def create_instance(self, **kwargs) -> ModelType:
        """Create new model instance."""
        return self.model_class.objects.create(**kwargs)
    
    def update_instance(self, instance: ModelType, **kwargs) -> ModelType:
        """Update model instance."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete_instance(self, instance: ModelType, soft: bool = True) -> bool:
        """Delete model instance."""
        if soft and hasattr(instance, 'delete'):
            instance.delete()
        else:
            instance.hard_delete()
        return True


# ── Abstract Repository Classes ─────────────────────────────────────

class BaseRepository(ABC, Generic[ModelType]):
    """Abstract base class for repositories."""
    
    def __init__(self, model_class: Type[ModelType]):
        """Initialize repository."""
        self.model_class = model_class
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def get_by_id(self, id: Any) -> Optional[ModelType]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    def get_all(self) -> List[ModelType]:
        """Get all entities."""
        pass
    
    @abstractmethod
    def save(self, entity: ModelType) -> ModelType:
        """Save entity."""
        pass
    
    @abstractmethod
    def delete(self, entity: ModelType) -> bool:
        """Delete entity."""
        pass
    
    def create(self, **kwargs) -> ModelType:
        """Create new entity."""
        entity = self.model_class(**kwargs)
        return self.save(entity)
    
    def update(self, entity: ModelType, **kwargs) -> ModelType:
        """Update entity."""
        for key, value in kwargs.items():
            setattr(entity, key, value)
        return self.save(entity)
    
    def exists(self, **kwargs) -> bool:
        """Check if entity exists."""
        return self.model_class.objects.filter(**kwargs).exists()
    
    def count(self, **kwargs) -> int:
        """Count entities."""
        return self.model_class.objects.filter(**kwargs).count()


class QuerySetRepository(BaseRepository[ModelType]):
    """Repository implementation using Django QuerySet."""
    
    def __init__(self, model_class: Type[ModelType]):
        """Initialize queryset repository."""
        super().__init__(model_class)
        self.queryset = model_class.objects.all()
    
    def get_by_id(self, id: Any) -> Optional[ModelType]:
        """Get entity by ID."""
        try:
            return self.queryset.get(pk=id)
        except self.model_class.DoesNotExist:
            return None
    
    def get_all(self) -> List[ModelType]:
        """Get all entities."""
        return list(self.queryset)
    
    def save(self, entity: ModelType) -> ModelType:
        """Save entity."""
        entity.save()
        return entity
    
    def delete(self, entity: ModelType) -> bool:
        """Delete entity."""
        entity.delete()
        return True
    
    def filter(self, **kwargs) -> 'QuerySetRepository[ModelType]':
        """Filter entities."""
        new_repo = self.__class__(self.model_class)
        new_repo.queryset = self.queryset.filter(**kwargs)
        return new_repo
    
    def order_by(self, *args) -> 'QuerySetRepository[ModelType]':
        """Order entities."""
        new_repo = self.__class__(self.model_class)
        new_repo.queryset = self.queryset.order_by(*args)
        return new_repo
    
    def limit(self, count: int) -> 'QuerySetRepository[ModelType]':
        """Limit entities."""
        new_repo = self.__class__(self.model_class)
        new_repo.queryset = self.queryset[:count]
        return new_repo
    
    def first(self) -> Optional[ModelType]:
        """Get first entity."""
        try:
            return self.queryset.first()
        except self.model_class.DoesNotExist:
            return None
    
    def last(self) -> Optional[ModelType]:
        """Get last entity."""
        try:
            return self.queryset.last()
        except self.model_class.DoesNotExist:
            return None


# ── Abstract Manager Classes ─────────────────────────────────────

class BaseManager(ABC):
    """Abstract base class for managers."""
    
    def __init__(self, *args, **kwargs):
        """Initialize manager."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def process(self, *args, **kwargs) -> Any:
        """Process request."""
        pass
    
    def validate_request(self, *args, **kwargs) -> bool:
        """Validate request parameters."""
        return True
    
    def log_request(self, *args, **kwargs):
        """Log request processing."""
        self.logger.info(f"Processing request with {self.__class__.__name__}")


class TransactionManager(BaseManager):
    """Manager for handling database transactions."""
    
    def __init__(self, retry_count: int = 3, retry_delay: float = 1.0):
        """Initialize transaction manager."""
        super().__init__()
        self.retry_count = retry_count
        self.retry_delay = retry_delay
    
    def process(self, func, *args, **kwargs) -> Any:
        """Process function within transaction."""
        from django.db import transaction
        
        for attempt in range(self.retry_count):
            try:
                with transaction.atomic():
                    return func(*args, **kwargs)
            except Exception as e:
                self.logger.warning(f"Transaction attempt {attempt + 1} failed: {e}")
                if attempt == self.retry_count - 1:
                    raise
                import time
                time.sleep(self.retry_delay)
    
    def validate_request(self, func, *args, **kwargs) -> bool:
        """Validate transaction request."""
        return callable(func)


# ── Abstract Strategy Classes ─────────────────────────────────────

class BaseStrategy(ABC):
    """Abstract base class for strategy pattern."""
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute strategy."""
        pass
    
    def validate_context(self, *args, **kwargs) -> bool:
        """Validate strategy context."""
        return True


class RewardCalculationStrategy(BaseStrategy):
    """Abstract strategy for reward calculations."""
    
    @abstractmethod
    def calculate_reward(self, base_amount: float, **kwargs) -> float:
        """Calculate reward amount."""
        pass


class NotificationStrategy(BaseStrategy):
    """Abstract strategy for notifications."""
    
    @abstractmethod
    def send_notification(self, recipient: Any, message: str, **kwargs) -> bool:
        """Send notification."""
        pass


# ── Abstract Observer Classes ─────────────────────────────────────

class BaseObserver(ABC):
    """Abstract base class for observer pattern."""
    
    @abstractmethod
    def update(self, subject: Any, **kwargs) -> None:
        """Update observer."""
        pass


class BaseSubject(ABC):
    """Abstract base class for subject in observer pattern."""
    
    def __init__(self):
        """Initialize subject."""
        self._observers: List[BaseObserver] = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def attach(self, observer: BaseObserver) -> None:
        """Attach observer."""
        if observer not in self._observers:
            self._observers.append(observer)
            self.logger.info(f"Observer {observer.__class__.__name__} attached")
    
    def detach(self, observer: BaseObserver) -> None:
        """Detach observer."""
        if observer in self._observers:
            self._observers.remove(observer)
            self.logger.info(f"Observer {observer.__class__.__name__} detached")
    
    def notify(self, **kwargs) -> None:
        """Notify all observers."""
        for observer in self._observers:
            try:
                observer.update(self, **kwargs)
            except Exception as e:
                self.logger.error(f"Error notifying observer {observer.__class__.__name__}: {e}")


# ── Abstract Factory Classes ─────────────────────────────────────

class BaseFactory(ABC):
    """Abstract base class for factory pattern."""
    
    @abstractmethod
    def create(self, *args, **kwargs) -> Any:
        """Create object."""
        pass


class ModelFactory(BaseFactory, Generic[ModelType]):
    """Abstract factory for creating model instances."""
    
    model_class: Type[ModelType] = None
    
    def __init__(self, model_class: Type[ModelType] = None):
        """Initialize model factory."""
        if model_class:
            self.model_class = model_class
        
        if not self.model_class:
            raise ValueError(f"Model class must be set for {self.__class__.__name__}")
    
    def create(self, **kwargs) -> ModelType:
        """Create model instance."""
        return self.model_class.objects.create(**kwargs)
    
    def build(self, **kwargs) -> ModelType:
        """Build model instance without saving."""
        return self.model_class(**kwargs)


# ── Abstract Command Classes ─────────────────────────────────────

class BaseCommand(ABC):
    """Abstract base class for command pattern."""
    
    def __init__(self, *args, **kwargs):
        """Initialize command."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute command."""
        pass
    
    def undo(self, *args, **kwargs) -> Any:
        """Undo command (optional)."""
        raise NotImplementedError("Undo not implemented")
    
    def validate(self, *args, **kwargs) -> bool:
        """Validate command parameters."""
        return True


class CommandInvoker:
    """Invoker for command pattern."""
    
    def __init__(self):
        """Initialize invoker."""
        self._history: List[BaseCommand] = []
        self._undo_stack: List[BaseCommand] = []
    
    def execute_command(self, command: BaseCommand, *args, **kwargs) -> Any:
        """Execute command."""
        if command.validate(*args, **kwargs):
            result = command.execute(*args, **kwargs)
            self._history.append(command)
            self._undo_stack.clear()  # Clear undo stack on new command
            return result
        raise ValueError("Command validation failed")
    
    def undo_last_command(self) -> Any:
        """Undo last command."""
        if not self._history:
            raise ValueError("No commands to undo")
        
        command = self._history.pop()
        result = command.undo()
        self._undo_stack.append(command)
        return result
    
    def redo_last_command(self) -> Any:
        """Redo last undone command."""
        if not self._undo_stack:
            raise ValueError("No commands to redo")
        
        command = self._undo_stack.pop()
        result = command.execute()
        self._history.append(command)
        return result


# ── Abstract Validator Classes ─────────────────────────────────────

class BaseValidator(ABC):
    """Abstract base class for validators."""
    
    @abstractmethod
    def validate(self, value: Any, **kwargs) -> bool:
        """Validate value."""
        pass
    
    def get_error_message(self, value: Any, **kwargs) -> str:
        """Get error message for invalid value."""
        return f"Invalid value: {value}"


class ModelValidator(BaseValidator, Generic[ModelType]):
    """Abstract validator for models."""
    
    model_class: Type[ModelType] = None
    
    def __init__(self, model_class: Type[ModelType] = None):
        """Initialize model validator."""
        if model_class:
            self.model_class = model_class
        
        if not self.model_class:
            raise ValueError(f"Model class must be set for {self.__class__.__name__}")
    
    def validate(self, instance: ModelType, **kwargs) -> bool:
        """Validate model instance."""
        return instance.full_clean() is None
    
    def get_error_message(self, instance: ModelType, **kwargs) -> str:
        """Get validation error message."""
        try:
            instance.full_clean()
            return ""
        except ValidationError as e:
            return str(e)

    def get_meta_title(self, fallback: str = '') -> str:
        return self.meta_title or fallback

    def get_meta_description(self, fallback: str = '') -> str:
        return self.meta_description or fallback


class RewardableModel(models.Model):
    """Mixin for content that rewards users on interaction."""
    reward_enabled = models.BooleanField(default=False)
    reward_coins   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reward_per_day_limit = models.PositiveIntegerField(default=1,
        help_text="Max times this reward can be earned per day per user")

    class Meta:
        abstract = True

    def award_reward_to(self, user) -> bool:
        if not self.reward_enabled or self.reward_coins <= 0:
            return False
        try:
            from api.cms.services_new.CPALeadService import VirtualCurrencyService
            return VirtualCurrencyService.award_coins(
                user=user,
                amount=self.reward_coins,
                reason=f"Reward: {getattr(self, 'title', str(self))}",
                tx_type='earn_content',
            )
        except Exception:
            return False


class SluggedModel(models.Model):
    slug = models.SlugField(max_length=300, unique=True, db_index=True)

    class Meta:
        abstract = True


class OrderedModel(models.Model):
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ['order']

    def move_up(self):
        self.order = max(0, self.order - 1)
        self.save(update_fields=['order'])

    def move_down(self):
        self.order += 1
        self.save(update_fields=['order'])


class SEOModel(models.Model):
    """Abstract mixin that adds SEO metadata fields to any model."""
    seo_title       = models.CharField(max_length=200, blank=True, default='')
    seo_description = models.TextField(blank=True, default='')
    seo_keywords    = models.CharField(max_length=500, blank=True, default='')
    og_title        = models.CharField(max_length=200, blank=True, default='')
    og_description  = models.TextField(blank=True, default='')
    og_image        = models.URLField(blank=True, default='')
    canonical_url   = models.URLField(blank=True, default='')
    robots_meta     = models.CharField(
        max_length=100, blank=True, default='index,follow',
        help_text='e.g. "index,follow" or "noindex,nofollow"',
    )

    class Meta:
        abstract = True

    def get_seo_title(self) -> str:
        return self.seo_title or str(self)

    def get_seo_description(self) -> str:
        return self.seo_description


class BaseContentModel(UUIDModel, TimestampedModel, PublishableModel,
                       ActiveModel, SEOModel, SluggedModel):
    """Full-featured abstract base for all CMS content models."""
    class Meta:
        abstract = True
