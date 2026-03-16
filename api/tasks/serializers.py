from django.apps import apps
import logging
import json
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from rest_framework import serializers
from rest_framework.exceptions import ValidationError  
from django.db.models import Q, Count, Avg, Sum, F, ExpressionWrapper, fields 
from django.conf import settings
from decimal import Decimal
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import AdminLedger, MasterTask, UserTaskCompletion
def get_transaction_model():
    return apps.get_model('wallet', 'WalletTransaction') 
def get_withdrawal_model():
    return apps.get_model('wallet', 'WithdrawalRequest')

User = get_user_model()

logger = logging.getLogger(__name__)

# ============ SENTINEL VALUES ============

class _Missing:
    """Sentinel value for missing data (not None)"""
    def __repr__(self):
        return '<MISSING>'
    
    def __bool__(self):
        return False

MISSING = _Missing()

# ============ HELPER FUNCTIONS ============

def safe_getattr(obj, attr_path: str, default=None):
    """
    Safe nested attribute access using getattr
    Example: safe_getattr(user, 'profile.settings.theme', 'default')
    """
    try:
        value = obj
        for attr in attr_path.split('.'):
            value = getattr(value, attr, MISSING)
            if value is MISSING:
                return default
        return value if value is not MISSING else default
    except Exception as e:
        logger.debug(f"Error in safe_getattr for {attr_path}: {str(e)}")
        return default


def safe_dict_get(data: dict, *keys, default=None):
    """
    Safe nested dictionary access
    Example: safe_dict_get(data, 'user', 'profile', 'name', default='Anonymous')
    """
    try:
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, MISSING)
                if current is MISSING:
                    return default
            else:
                return default
        return current if current is not MISSING else default
    except Exception as e:
        logger.debug(f"Error in safe_dict_get: {str(e)}")
        return default


def safe_int(value, default=0) -> int:
    """Safely convert to int"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0) -> float:
    """Safely convert to float"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_str(value, default='') -> str:
    """Safely convert to string"""
    try:
        return str(value) if value is not None else default
    except Exception:
        return default


def safe_bool(value, default=False) -> bool:
    """Safely convert to boolean"""
    try:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
        return bool(value) if value is not None else default
    except Exception:
        return default


def deep_merge(dict1: dict, dict2: dict) -> dict:
    """
    Deep merge two dictionaries
    """
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ============ CIRCUIT BREAKER PATTERN ============

class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls
    """
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def __call__(self, func):
        """Decorator usage - fixed to properly wrap methods"""
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        
        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        try:
            # Check if circuit is open
            if self.state == 'open':
                if self.last_failure_time and \
                   (timezone.now() - self.last_failure_time).seconds > self.recovery_timeout:
                    self.state = 'half-open'
                    logger.info(f"Circuit {self.name} moved to half-open state")
                else:
                    logger.warning(f"Circuit {self.name} is open - fast failing")
                    # Return safe default instead of raising exception
                    return None
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Success - reset if half-open
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0
                logger.info(f"Circuit {self.name} closed after successful call")
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = timezone.now()
            
            # Check if threshold reached
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.warning(f"Circuit {self.name} opened after {self.failure_count} failures")
            
            # Log and return safe default
            logger.error(f"Error in circuit breaker {self.name}: {str(e)}")
            return None


# Circuit breaker instances
task_serializer_circuit = CircuitBreaker('task_serializer', failure_threshold=10, recovery_timeout=120)


# ============ PYDANTIC SCHEMA VALIDATION (Optional) ============

try:
    from pydantic import BaseModel, Field, validator
    from pydantic.error_wrappers import ValidationError as PydanticValidationError
    
    class TaskMetadataSchema(BaseModel):
        """Pydantic schema for task metadata validation"""
        url: Optional[str] = None
        duration_seconds: Optional[int] = Field(None, ge=5, le=3600)
        game_type: Optional[str] = None
        input_type: Optional[str] = None
        action_type: Optional[str] = None
        provider: Optional[str] = None
        questions: List[Dict] = Field(default_factory=list)
        
        @validator('url')
        def validate_url(cls, v):
            if v and not v.startswith(('http://', 'https://')):
                raise ValueError('URL must start with http:// or https://')
            return v
        
        class Config:
            extra = 'forbid'  # No extra fields allowed
    
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    logger.info("Pydantic not available, using basic validation")


# ============ BASE SERIALIZER WITH BULLETPROOF PATTERNS ============

class BulletproofSerializer(serializers.Serializer):
    """
    Base serializer with bulletproof patterns
    All serializers should inherit from this
    """
    
    def to_representation(self, instance):
        """Override with try-except-else-finally pattern"""
        try:
            # Try to get representation
            data = super().to_representation(instance)
        except Exception as e:
            # Log error and return minimal safe data
            logger.error(f"Error in {self.__class__.__name__} to_representation: {str(e)}")
            data = self._get_safe_representation(instance)
        else:
            # Success - validate and clean data
            data = self._clean_representation(data)
        finally:
            # Always log and return something
            logger.debug(f"{self.__class__.__name__} representation generated")
            return data
    
    def _get_safe_representation(self, instance):
        """Return minimal safe data when error occurs"""
        if hasattr(instance, 'id'):
            return {'id': safe_int(getattr(instance, 'id', 0))}
        return {}
    
    def _clean_representation(self, data):
        """Clean and validate data before returning"""
        if isinstance(data, dict):
            # Remove None values if configured
            if getattr(self.Meta, 'omit_none', False):
                data = {k: v for k, v in data.items() if v is not None}
            
            # Ensure all values are serializable
            for key, value in data.items():
                if isinstance(value, (datetime, timezone.datetime)):
                    data[key] = value.isoformat()
                elif isinstance(value, (timedelta)):
                    data[key] = value.total_seconds()
        
        return data
    
    def validate(self, attrs):
        """Override with try-except pattern"""
        try:
            return super().validate(attrs)
        except Exception as e:
            logger.error(f"Validation error in {self.__class__.__name__}: {str(e)}")
            # Return original attrs on validation error to prevent complete failure
            return attrs


# ============ MASTER TASK SERIALIZER ============

class MasterTaskSerializer(BulletproofSerializer):
    """
    Unified serializer for all tasks with bulletproof error handling
    """
    
    # Basic fields
    id = serializers.IntegerField(read_only=True)
    task_id = serializers.CharField(read_only=True)
    name = serializers.CharField(required=True, max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    
    # Categorization
    system_type = serializers.ChoiceField(choices=MasterTask.SystemType.choices)
    system_type_display = serializers.SerializerMethodField()
    category = serializers.ChoiceField(choices=MasterTask.TaskCategory.choices)
    category_display = serializers.SerializerMethodField()
    
    # JSON fields with validation
    task_metadata = serializers.JSONField(required=False, default=dict)
    rewards = serializers.JSONField(required=False, default=dict)
    constraints = serializers.JSONField(required=False, default=dict)
    ui_config = serializers.JSONField(required=False, default=dict)
    
    # Status
    is_active = serializers.BooleanField(default=True)
    is_featured = serializers.BooleanField(default=False)
    sort_order = serializers.IntegerField(default=0, min_value=0)
    
    # Availability
    available_from = serializers.DateTimeField(required=False)
    available_until = serializers.DateTimeField(required=False, allow_null=True)
    
    # Targeting
    min_user_level = serializers.IntegerField(default=1, min_value=1)
    max_user_level = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    
    # Computed fields
    is_available = serializers.SerializerMethodField()
    time_status = serializers.SerializerMethodField()
    level_range = serializers.SerializerMethodField()
    reward_summary = serializers.SerializerMethodField()
    
    # Statistics
    total_completions = serializers.IntegerField(read_only=True)
    completion_rate = serializers.SerializerMethodField()
    
    # Timestamps
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = MasterTask
        fields = [
            'id', 'task_id', 'name', 'description',
            'system_type', 'system_type_display', 'category', 'category_display',
            'task_metadata', 'rewards', 'constraints', 'ui_config',
            'is_active', 'is_featured', 'sort_order',
            'available_from', 'available_until',
            'min_user_level', 'max_user_level',
            'is_available', 'time_status', 'level_range', 'reward_summary',
            'total_completions', 'completion_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['task_id', 'created_at', 'updated_at', 'total_completions']
        omit_none = True  # Custom Meta option
    
    def __init__(self, *args, **kwargs):
        """Initialize with context-aware defaults"""
        # Extract context
        self.user_level = safe_int(kwargs.get('context', {}).get('user_level'), 1)
        self.user_id = kwargs.get('context', {}).get('user_id')
        self.include_stats = safe_bool(kwargs.get('context', {}).get('include_stats'), False)
        
        super().__init__(*args, **kwargs)
    
    # ============ SERIALIZER METHOD FIELDS ============
    
    @task_serializer_circuit
    def get_system_type_display(self, obj):
        """Get system type display name with circuit breaker"""
        try:
            return safe_str(obj.get_system_type_display(), 'Unknown')
        except Exception as e:
            logger.error(f"Error getting system type display: {str(e)}")
            return 'Unknown'
    
    def get_category_display(self, obj):
        """Get category display name"""
        try:
            return safe_str(obj.get_category_display(), 'Unknown')
        except Exception as e:
            logger.error(f"Error getting category display: {str(e)}")
            return 'Unknown'
    
    def get_is_available(self, obj):
        """Check if task is available for current user"""
        try:
            if self.user_id:
                # [OK] Fixed: Properly handle tuple return from model method
                is_available, _ = obj.is_available_with_cooldown(
                    user_level=self.user_level,
                    user_id=self.user_id
                )
                return is_available
            else:
                # [OK] Fixed: Properly handle tuple return
                is_available, _ = obj.is_available_for_user(self.user_level)
                return is_available
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return False
    
    def get_time_status(self, obj):
        """Get time-based status"""
        try:
            return safe_str(obj.time_status, 'unknown')
        except Exception as e:
            logger.error(f"Error getting time status: {str(e)}")
            return 'unknown'
    
    def get_level_range(self, obj):
        """Get level range as string"""
        try:
            if obj.max_user_level:
                return f"{obj.min_user_level}-{obj.max_user_level}"
            return f"{obj.min_user_level}+"
        except Exception as e:
            logger.error(f"Error getting level range: {str(e)}")
            return '1+'
    
    def get_reward_summary(self, obj):
        """Get reward summary"""
        try:
            return {
                'points': safe_int(obj.get_reward_value('points', 0)),
                'coins': safe_int(obj.get_reward_value('coins', 0)),
                'experience': safe_int(obj.get_reward_value('experience', 0))
            }
        except Exception as e:
            logger.error(f"Error getting reward summary: {str(e)}")
            return {'points': 0, 'coins': 0, 'experience': 0}
    
    def get_completion_rate(self, obj):
        """Get completion rate (cached)"""
        try:
            # Try cache first
            cache_key = f"completion_rate_{obj.id}"
            rate = cache.get(cache_key)
            
            if rate is None:
                # Calculate rate
                total = safe_int(obj.total_completions, 0)
                rate = 0.0
                
                if total > 0 and hasattr(obj, 'completions'):
                    completed = obj.completions.filter(status='completed').count()
                    rate = round((completed / total) * 100, 2) if total > 0 else 0
                
                # Cache for 1 hour
                cache.set(cache_key, rate, 3600)
            
            return rate
        except Exception as e:
            logger.error(f"Error getting completion rate: {str(e)}")
            return 0.0
    
    # ============ VALIDATION METHODS ============
    
    def validate_task_metadata(self, value):
        """Validate task metadata with schema"""
        if not isinstance(value, dict):
            raise ValidationError("task_metadata must be a dictionary")
        
        # Use Pydantic if available
        if PYDANTIC_AVAILABLE:
            try:
                # Validate based on system type
                system_type = self.initial_data.get('system_type')
                
                if system_type == MasterTask.SystemType.CLICK_VISIT:
                    schema = TaskMetadataSchema(**value)
                elif system_type == MasterTask.SystemType.GAMIFIED:
                    if 'game_type' not in value:
                        raise ValidationError("Gamified tasks require game_type")
                # Add more validations...
                
            except PydanticValidationError as e:
                raise ValidationError({"task_metadata": str(e)})
        
        return value
    
    def validate_rewards(self, value):
        """Validate rewards structure"""
        if not isinstance(value, dict):
            raise ValidationError("rewards must be a dictionary")
        
        # Ensure points is positive
        points = safe_int(value.get('points'), 0)
        if points < 0:
            raise ValidationError({"rewards": "points cannot be negative"})
        
        # Set defaults for missing values
        return {
            'points': points,
            'coins': safe_int(value.get('coins'), 0),
            'experience': safe_int(value.get('experience'), 0),
            'bonus': value.get('bonus', {})
        }
    
    def validate_constraints(self, value):
        """Validate constraints"""
        if not isinstance(value, dict):
            raise ValidationError("constraints must be a dictionary")
        
        # Validate cooldown
        cooldown = safe_int(value.get('cooldown_minutes'), 0)
        if cooldown < 0:
            raise ValidationError({"constraints": "cooldown_minutes cannot be negative"})
        
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        try:
            # Validate date range
            available_from = attrs.get('available_from')
            available_until = attrs.get('available_until')
            
            if available_from and available_until and available_from > available_until:
                raise ValidationError({
                    'available_until': 'Available until must be after available from'
                })
            
            # Validate level range
            min_level = safe_int(attrs.get('min_user_level'), 1)
            max_level = attrs.get('max_user_level')
            
            if max_level and min_level > max_level:
                raise ValidationError({
                    'max_user_level': 'Max level must be greater than or equal to min level'
                })
            
            return attrs
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in validate: {str(e)}")
            return attrs
    
    # ============ CREATE/UPDATE METHODS ============
    
    @transaction.atomic  # [OK] Fixed: Now properly imported
    def create(self, validated_data):
        """Create task with transaction safety"""
        try:
            # Generate task_id if not provided
            if 'task_id' not in validated_data:
                system_type = validated_data.get('system_type')
                prefix = {
                    MasterTask.SystemType.CLICK_VISIT: 'CV',
                    MasterTask.SystemType.GAMIFIED: 'GM',
                    MasterTask.SystemType.DATA_INPUT: 'DI',
                    MasterTask.SystemType.GUIDE_SIGNUP: 'GS',
                    MasterTask.SystemType.EXTERNAL_WALL: 'EW',
                }.get(system_type, 'TS')
                
                import hashlib
                import time
                name = safe_str(validated_data.get('name', ''))
                hash_input = f"{name}{time.time()}".encode()
                unique_hash = hashlib.md5(hash_input).hexdigest()[:8]
                validated_data['task_id'] = f"{prefix}_{unique_hash}"
            
            # Create task
            task = MasterTask.objects.create(**validated_data)
            logger.info(f"Task created: {task.task_id}")
            
            return task
            
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            raise
    
    @transaction.atomic  # [OK] Fixed: Now properly imported
    def update(self, instance, validated_data):
        """Update task with transaction safety"""
        try:
            # Update fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            logger.info(f"Task updated: {instance.task_id}")
            
            return instance
            
        except Exception as e:
            logger.error(f"Error updating task: {str(e)}")
            raise
    
    # ============ TO REPRESENTATION WITH GRACEFUL DEGRADATION ============
    
    def to_representation(self, instance):
        """Override with graceful degradation"""
        try:
            data = super().to_representation(instance)
            
            # Add system-specific formatting
            system_type = data.get('system_type')
            
            if system_type == MasterTask.SystemType.GAMIFIED:
                data = self._format_gamified_task(data, instance)
            elif system_type == MasterTask.SystemType.DATA_INPUT:
                data = self._format_data_input_task(data, instance)
            elif system_type == MasterTask.SystemType.GUIDE_SIGNUP:
                data = self._format_guide_signup_task(data, instance)
            
            # Add stats if requested
            if self.include_stats:
                data['stats'] = self._get_task_stats(instance)
            
            return data
            
        except Exception as e:
            logger.error(f"Error in to_representation: {str(e)}")
            # Return minimal safe data
            return {
                'id': safe_int(getattr(instance, 'id', 0)),
                'task_id': safe_str(getattr(instance, 'task_id', 'unknown')),
                'name': safe_str(getattr(instance, 'name', 'Unknown Task')),
                'error': 'Partial data due to serialization error'
            }
    
    def _format_gamified_task(self, data, instance):
        """Format gamified task data"""
        try:
            metadata = safe_dict_get(data, 'task_metadata', default={})
            game_type = safe_str(metadata.get('game_type'), 'unknown')
            
            # Add game-specific configurations
            if game_type == 'spin':
                data['game_config'] = {
                    'segments': safe_int(metadata.get('segments'), 8),
                    'spin_cost': safe_int(metadata.get('spin_cost'), 0),
                    'daily_free': safe_int(metadata.get('daily_free_spins'), 1)
                }
            elif game_type == 'scratch':
                data['game_config'] = {
                    'grid_size': metadata.get('grid_size', {'rows': 3, 'cols': 3}),
                    'win_probability': safe_float(metadata.get('win_probability'), 0.3)
                }
            
            return data
        except Exception as e:
            logger.error(f"Error formatting gamified task: {str(e)}")
            return data
    
    def _format_data_input_task(self, data, instance):
        """Format data input task data"""
        try:
            metadata = safe_dict_get(data, 'task_metadata', default={})
            input_type = safe_str(metadata.get('input_type'), 'unknown')
            
            if input_type == 'quiz':
                questions = metadata.get('questions', [])
                if len(questions) > 10:  # Limit for API
                    data['metadata']['questions'] = questions[:10]
                    data['metadata']['total_questions'] = len(questions)
            
            return data
        except Exception as e:
            logger.error(f"Error formatting data input task: {str(e)}")
            return data
    
    def _format_guide_signup_task(self, data, instance):
        """Format guide/signup task data"""
        try:
            metadata = safe_dict_get(data, 'task_metadata', default={})
            action_type = safe_str(metadata.get('action_type'), 'unknown')
            
            if action_type == 'app_install':
                data['instructions'] = {
                    'steps': [
                        'Click the install button',
                        'Install the app from Play Store',
                        'Open the app',
                        'Come back to claim reward'
                    ],
                    'package_name': safe_str(metadata.get('package_name'), '')
                }
            
            return data
        except Exception as e:
            logger.error(f"Error formatting guide task: {str(e)}")
            return data
    
    def _get_task_stats(self, instance):
        """Get task statistics"""
        try:
            return {
                'total_completions': safe_int(instance.total_completions, 0),
                'unique_users': safe_int(instance.unique_users_completed, 0),
                'completion_rate': self.get_completion_rate(instance),
                'average_time': self._get_average_completion_time(instance)
            }
        except Exception as e:
            logger.error(f"Error getting task stats: {str(e)}")
            return {}
    
    def _get_average_completion_time(self, instance) -> Optional[float]:
        """Get average completion time in seconds - with proper error handling"""
        try:
            if hasattr(instance, 'completions'):
                # [OK] Fixed: Now using proper imports
                avg_result = instance.completions.filter(
                    status='completed',
                    completed_at__isnull=False
                ).annotate(
                    duration=ExpressionWrapper(
                        F('completed_at') - F('started_at'),
                        output_field=fields.DurationField()
                    )
                ).aggregate(avg_time=Avg('duration'))
                
                avg_time = avg_result.get('avg_time')
                if avg_time:
                    return avg_time.total_seconds()
            return None
        except Exception as e:
            logger.error(f"Error calculating average completion time: {str(e)}")
            return None


# ============ TASK COMPLETION SERIALIZER ============

class TaskCompletionSerializer(BulletproofSerializer):
    """
    Serializer for task completions with bulletproof patterns
    """
    
    id = serializers.IntegerField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    task = serializers.PrimaryKeyRelatedField(queryset=MasterTask.objects.all())
    
    # Nested serializers
    task_details = MasterTaskSerializer(source='task', read_only=True)
    
    status = serializers.ChoiceField(
        choices=['started', 'completed', 'failed', 'verified'],
        default='started'
    )
    status_display = serializers.SerializerMethodField()
    
    proof_data = serializers.JSONField(required=False, default=dict)
    rewards_awarded = serializers.JSONField(required=False, default=dict)
    
    # Timestamps
    started_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    verified_at = serializers.DateTimeField(read_only=True, allow_null=True)
    
    # Computed fields
    duration = serializers.SerializerMethodField()
    points_earned = serializers.SerializerMethodField()
    
    # Technical details
    ip_address = serializers.IPAddressField(required=False, allow_null=True)
    user_agent = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = UserTaskCompletion
        fields = [
            'id', 'user', 'task', 'task_details',
            'status', 'status_display',
            'proof_data', 'rewards_awarded',
            'started_at', 'completed_at', 'verified_at',
            'duration', 'points_earned',
            'ip_address', 'user_agent'
        ]
        read_only_fields = ['started_at', 'completed_at', 'verified_at']
    
    def get_status_display(self, obj):
        """Get human-readable status"""
        status_map = {
            'started': 'Started',
            'completed': 'Completed',
            'failed': 'Failed',
            'verified': 'Verified'
        }
        return safe_str(status_map.get(obj.status, obj.status), obj.status)
    
    def get_duration(self, obj) -> Optional[float]:
        """Get completion duration in seconds"""
        try:
            if obj.completed_at and obj.started_at:
                duration = obj.completed_at - obj.started_at
                return duration.total_seconds()
            return None
        except Exception:
            return None
    
    def get_points_earned(self, obj) -> int:
        """Get points earned"""
        try:
            return safe_int(obj.rewards_awarded.get('points', 0)) if obj.rewards_awarded else 0
        except Exception:
            return 0
    
    def validate(self, attrs):
        """Validate completion data"""
        try:
            request = self.context.get('request')
            user = getattr(request, 'user', None) if request else None
            
            # Check if task exists and is active
            task = attrs.get('task')
            if task and not task.is_active:
                raise ValidationError({"task": "Task is not active"})
            
            # Check if user already completed this task today
            if user and task and task.daily_completion_limit:
                today_start = timezone.now().replace(hour=0, minute=0, second=0)
                
                today_count = UserTaskCompletion.objects.filter(
                    user=user,
                    task=task,
                    started_at__gte=today_start,
                    status='completed'
                ).count()
                
                if today_count >= task.daily_completion_limit:
                    raise ValidationError("Daily limit reached for this task")
            
            return attrs
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in completion validation: {str(e)}")
            return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """Create completion with transaction safety"""
        try:
            request = self.context.get('request')
            
            # Set user from request
            if request and hasattr(request, 'user'):
                validated_data['user'] = request.user
            
            # Set IP and user agent
            validated_data['ip_address'] = self._get_client_ip(request)
            validated_data['user_agent'] = self._get_user_agent(request)
            
            # Check for existing started completion
            existing = UserTaskCompletion.objects.filter(
                user=validated_data['user'],
                task=validated_data['task'],
                status='started'
            ).first()
            
            if existing:
                return existing
            
            # Create new completion
            completion = UserTaskCompletion.objects.create(**validated_data)
            
            # Update Redis for tracking (with error handling)
            self._update_redis_tracking(completion)
            
            return completion
            
        except Exception as e:
            logger.error(f"Error creating completion: {str(e)}")
            raise
    
    def _get_client_ip(self, request) -> Optional[str]:
        """Get client IP safely - with type hint"""
        try:
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    return x_forwarded_for.split(',')[0]
                return request.META.get('REMOTE_ADDR')
        except Exception as e:
            logger.debug(f"Error getting client IP: {str(e)}")
        return None
    
    def _get_user_agent(self, request) -> str:
        """Get user agent safely - with type hint"""
        try:
            if request:
                return request.META.get('HTTP_USER_AGENT', '')
        except Exception as e:
            logger.debug(f"Error getting user agent: {str(e)}")
        return ''
    
    def _update_redis_tracking(self, completion):
        """Update Redis for tracking - with proper error handling"""
        try:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection("default")
            
            # Track user activity
            today = timezone.now().strftime('%Y%m%d')
            redis_key = f"user_activity:{completion.user.id}:{today}"
            redis_client.incr(redis_key)
            redis_client.expire(redis_key, 86400)  # 24 hours
            
        except ImportError:
            logger.debug("django_redis not installed, skipping Redis tracking")
        except Exception as e:
            logger.debug(f"Redis tracking error: {str(e)}")
            # Non-critical, continue


# ============ TASK LIST SERIALIZER ============

class TaskListSerializer(serializers.Serializer):
    """
    Serializer for grouped task list response
    """
    system_type = serializers.CharField()
    system_name = serializers.CharField()
    tasks = MasterTaskSerializer(many=True)
    count = serializers.IntegerField()
    
    def to_representation(self, instance):
        """Convert to representation with validation"""
        try:
            data = super().to_representation(instance)
            
            # Ensure count matches actual tasks
            tasks = data.get('tasks', [])
            data['count'] = len(tasks)
            
            return data
        except Exception as e:
            logger.error(f"Error in TaskListSerializer: {str(e)}")
            return {
                'system_type': 'unknown',
                'system_name': 'Unknown',
                'tasks': [],
                'count': 0
            }


# ============ BULK OPERATION SERIALIZER ============

class BulkTaskOperationSerializer(serializers.Serializer):
    """
    Serializer for bulk operations on tasks
    """
    task_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=True,
        min_length=1,
        max_length=100
    )
    operation = serializers.ChoiceField(
        choices=['activate', 'deactivate', 'delete'],
        required=True
    )
    
    def validate_task_ids(self, value):
        """Validate that all task IDs exist"""
        existing_ids = set(MasterTask.objects.filter(id__in=value).values_list('id', flat=True))
        missing_ids = set(value) - existing_ids
        
        if missing_ids:
            raise ValidationError(f"Tasks not found: {missing_ids}")
        
        return value
    
    def save(self):
        """Perform bulk operation"""
        data = self.validated_data
        task_ids = data['task_ids']
        operation = data['operation']
        
        if operation == 'activate':
            count = MasterTask.bulk_activate(task_ids)
        elif operation == 'deactivate':
            count = MasterTask.bulk_deactivate(task_ids)
        elif operation == 'delete':
            count, _ = MasterTask.objects.filter(id__in=task_ids).delete()
        else:
            count = 0
        
        return {
            'operation': operation,
            'affected_count': count,
            'task_ids': task_ids
        }


# ============ TASK STATISTICS SERIALIZER ============

class TaskStatisticsSerializer(serializers.Serializer):
    """
    Serializer for task statistics
    """
    total_tasks = serializers.IntegerField()
    active_tasks = serializers.IntegerField()
    featured_tasks = serializers.IntegerField()
    total_completions = serializers.IntegerField()
    unique_users = serializers.IntegerField()
    
    system_breakdown = serializers.JSONField()
    category_breakdown = serializers.JSONField()
    
    @classmethod
    def get_statistics(cls):
        """Get task statistics"""
        try:
            from django.db.models import Sum
            
            total_tasks = MasterTask.objects.count()
            active_tasks = MasterTask.objects.filter(is_active=True).count()
            featured_tasks = MasterTask.objects.filter(is_featured=True).count()
            
            total_completions = MasterTask.objects.aggregate(
                total=Sum('total_completions')
            )['total'] or 0
            
            unique_users = MasterTask.objects.aggregate(
                total=Sum('unique_users_completed')
            )['total'] or 0
            
            # System breakdown
            system_breakdown = {}
            for system_type, _ in MasterTask.SystemType.choices:
                count = MasterTask.objects.filter(system_type=system_type).count()
                if count > 0:
                    system_breakdown[system_type] = count
            
            # Category breakdown
            category_breakdown = {}
            for category, _ in MasterTask.TaskCategory.choices:
                count = MasterTask.objects.filter(category=category).count()
                if count > 0:
                    category_breakdown[category] = count
            
            return {
                'total_tasks': total_tasks,
                'active_tasks': active_tasks,
                'featured_tasks': featured_tasks,
                'total_completions': total_completions,
                'unique_users': unique_users,
                'system_breakdown': system_breakdown,
                'category_breakdown': category_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return {
                'total_tasks': 0,
                'active_tasks': 0,
                'featured_tasks': 0,
                'total_completions': 0,
                'unique_users': 0,
                'system_breakdown': {},
                'category_breakdown': {}
            }


# ============ ERROR RESPONSE SERIALIZER ============

class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    error_code = serializers.CharField(required=False)
    details = serializers.JSONField(required=False, allow_null=True)  # DictField → JSONField
    timestamp = serializers.DateTimeField(read_only=True)
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['timestamp'] = timezone.now().isoformat()
        return data

# ============ EXPORT SERIALIZER ============

class TaskExportSerializer(serializers.ModelSerializer):
    """
    Serializer for exporting tasks
    """
    class Meta:
        model = MasterTask
        fields = '__all__'
    
    def to_representation(self, instance):
        """Export with additional metadata"""
        try:
            data = super().to_representation(instance)
            
            # Add export metadata
            data['_exported_at'] = timezone.now().isoformat()
            data['_export_version'] = '1.0'
            
            return data
        except Exception as e:
            logger.error(f"Error exporting task: {str(e)}")
            return {'id': instance.id, 'error': 'Export failed'}
        
        
        
        
        """
Serializers for AdminLedger model with bulletproof error handling
"""

# ============ HELPER FUNCTIONS ============

def safe_decimal(value, default=Decimal('0')):
    """Safely convert to Decimal"""
    try:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    """Safely convert to float"""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


# ============ ADMIN LEDGER SERIALIZER ============

class AdminLedgerSerializer(serializers.ModelSerializer):
    """
    Serializer for AdminLedger model with complete field validation
    """
    
    # Read-only fields
    entry_id = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    # Related object details (nested serializers for GET requests)
    task_details = serializers.SerializerMethodField(read_only=True)
    user_details = serializers.SerializerMethodField(read_only=True)
    completion_details = serializers.SerializerMethodField(read_only=True)
    transaction_details = serializers.SerializerMethodField(read_only=True)
    
    # Human-readable display fields
    source_display = serializers.SerializerMethodField()
    source_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminLedger
        fields = [
            'id',
            'entry_id',
            'amount',
            'source',
            'source_type',
            'source_display',
            'source_type_display',
            'task',
            'task_details',
            'user',
            'user_details',
            'completion',
            'completion_details',
            'transaction',
            'transaction_details',
            'withdrawal',
            'metadata',
            'description',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'entry_id', 'created_at', 'updated_at']
    
    def get_source_display(self, obj):
        """Get human-readable source"""
        return obj.source.replace('_', ' ').title() if obj.source else ''
    
    def get_source_type_display(self, obj):
        """Get source type display name"""
        return dict(AdminLedger.SOURCE_CHOICES).get(obj.source_type, obj.source_type)
    
    def get_task_details(self, obj):
        """Get task details safely"""
        if obj.task:
            try:
                return {
                    'id': obj.task.id,
                    'task_id': obj.task.task_id,
                    'name': obj.task.name,
                    'system_type': obj.task.system_type,
                }
            except Exception as e:
                logger.error(f"Error getting task details: {str(e)}")
                return {'id': obj.task.id, 'error': 'Failed to load details'}
        return None
    
    def get_user_details(self, obj):
        """Get user details safely"""
        if obj.user:
            try:
                return {
                    'id': obj.user.id,
                    'username': obj.user.username,
                    'email': obj.user.email,
                }
            except Exception as e:
                logger.error(f"Error getting user details: {str(e)}")
                return {'id': obj.user.id, 'error': 'Failed to load details'}
        return None
    
    def get_completion_details(self, obj):
        """Get completion details safely"""
        if obj.completion:
            try:
                return {
                    'id': obj.completion.id,
                    'status': obj.completion.status,
                    'completed_at': obj.completion.completed_at.isoformat() if obj.completion.completed_at else None,
                }
            except Exception as e:
                logger.error(f"Error getting completion details: {str(e)}")
                return {'id': obj.completion.id, 'error': 'Failed to load details'}
        return None
    
    def get_transaction_details(self, obj):
        """Get transaction details safely"""
        if obj.transaction:
            try:
                return {
                    'id': obj.transaction.id,
                    'transaction_id': obj.transaction.transaction_id,
                    'amount': float(obj.transaction.amount),
                    'transaction_type': obj.transaction.transaction_type,
                }
            except Exception as e:
                logger.error(f"Error getting transaction details: {str(e)}")
                return {'id': obj.transaction.id, 'error': 'Failed to load details'}
        return None
    
    def validate_amount(self, value):
        """Validate amount is positive"""
        if value <= 0:
            raise ValidationError("Amount must be greater than 0")
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        source_type = attrs.get('source_type')
        task = attrs.get('task')
        withdrawal = attrs.get('withdrawal')
        
        # Validate source consistency
        if source_type == AdminLedger.SOURCE_TASK and not task:
            raise ValidationError({"task": "Task is required for task revenue"})
        
        if source_type == AdminLedger.SOURCE_WITHDRAWAL_FEE and not withdrawal:
            raise ValidationError({"withdrawal": "Withdrawal is required for withdrawal fee"})
        
        return attrs
    
    def to_representation(self, instance):
        """Convert to representation with safe float conversion"""
        try:
            data = super().to_representation(instance)
            
            # Convert Decimal to float for JSON serialization
            if 'amount' in data and data['amount'] is not None:
                data['amount'] = safe_float(data['amount'])
            
            return data
            
        except Exception as e:
            logger.error(f"Error in to_representation: {str(e)}")
            return {
                'id': instance.id,
                'entry_id': instance.entry_id,
                'error': 'Failed to serialize fully'
            }


# ============ ADMIN LEDGER LIST SERIALIZER ============

class AdminLedgerListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views
    """
    
    source_display = serializers.SerializerMethodField()
    source_type_display = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    task_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminLedger
        fields = [
            'id',
            'entry_id',
            'amount',
            'source',
            'source_display',
            'source_type',
            'source_type_display',
            'username',
            'task_name',
            'description',
            'created_at',
        ]
    
    def get_source_display(self, obj):
        return obj.source.replace('_', ' ').title() if obj.source else ''
    
    def get_source_type_display(self, obj):
        return dict(AdminLedger.SOURCE_CHOICES).get(obj.source_type, obj.source_type)
    
    def get_username(self, obj):
        if obj.user:
            return obj.user.username
        return None
    
    def get_task_name(self, obj):
        if obj.task:
            return obj.task.name
        return None
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'amount' in data:
            data['amount'] = safe_float(data['amount'])
        return data


# ============ ADMIN LEDGER CREATE SERIALIZER ============

class AdminLedgerCreateSerializer(serializers.Serializer):
    """
    Serializer for creating admin ledger entries
    """
    
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    source = serializers.CharField(max_length=50)
    source_type = serializers.ChoiceField(choices=AdminLedger.SOURCE_CHOICES)
    task_id = serializers.IntegerField(required=False, allow_null=True)
    user_id = serializers.IntegerField(required=False, allow_null=True)
    completion_id = serializers.IntegerField(required=False, allow_null=True)
    transaction_id = serializers.IntegerField(required=False, allow_null=True)
    withdrawal_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)
    
    def validate_task_id(self, value):
        """Validate task exists"""
        if value:
            try:
                MasterTask.objects.get(id=value)
            except MasterTask.DoesNotExist:
                raise ValidationError(f"Task with id {value} does not exist")
        return value
    
    def validate_user_id(self, value):
        """Validate user exists"""
        if value:
            try:
                User.objects.get(id=value)
            except User.DoesNotExist:
                raise ValidationError(f"User with id {value} does not exist")
        return value
    
    def validate_completion_id(self, value):
        """Validate completion exists"""
        if value:
            try:
                UserTaskCompletion.objects.get(id=value)
            except UserTaskCompletion.DoesNotExist:
                raise ValidationError(f"Completion with id {value} does not exist")
        return value
    
    def validate_transaction_id(self, value):
        """Validate transaction exists"""
        if value:
            try:
                Transaction.objects.get(id=value)
            except Transaction.DoesNotExist:
                raise ValidationError(f"Transaction with id {value} does not exist")
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        source_type = attrs.get('source_type')
        
        # Validate required fields based on source type
        if source_type == AdminLedger.SOURCE_TASK and not attrs.get('task_id'):
            raise ValidationError("task_id is required for task revenue")
        
        if source_type == AdminLedger.SOURCE_WITHDRAWAL_FEE and not attrs.get('withdrawal_id'):
            raise ValidationError("withdrawal_id is required for withdrawal fee")
        
        return attrs
    
    def create(self, validated_data):
        """Create admin ledger entry"""
        # Extract related object IDs
        task_id = validated_data.pop('task_id', None)
        user_id = validated_data.pop('user_id', None)
        completion_id = validated_data.pop('completion_id', None)
        transaction_id = validated_data.pop('transaction_id', None)
        withdrawal_id = validated_data.pop('withdrawal_id', None)
        
        # Get related objects
        task = MasterTask.objects.get(id=task_id) if task_id else None
        user = User.objects.get(id=user_id) if user_id else None
        completion = UserTaskCompletion.objects.get(id=completion_id) if completion_id else None
        transaction = Transaction.objects.get(id=transaction_id) if transaction_id else None
        withdrawal = None
        if withdrawal_id:
            from .models import WithdrawalRequest
            withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)
        
        # Create ledger entry
        ledger = AdminLedger.objects.create(
            amount=validated_data['amount'],
            source=validated_data['source'],
            source_type=validated_data['source_type'],
            task=task,
            user=user,
            completion=completion,
            transaction=transaction,
            withdrawal=withdrawal,
            description=validated_data.get('description', ''),
            metadata=validated_data.get('metadata', {})
        )
        
        return ledger


# ============ PROFIT REPORT SERIALIZER ============

class ProfitReportSerializer(serializers.Serializer):
    """
    Serializer for profit reports
    """
    
    total_profit = serializers.FloatField()
    profit_last_30_days = serializers.FloatField()
    average_daily_profit = serializers.FloatField()
    by_source = serializers.JSONField()
    daily_breakdown = serializers.ListField()
    top_sources = serializers.ListField()
    period_days = serializers.IntegerField()
    generated_at = serializers.DateTimeField()
    
    def to_representation(self, instance):
        """Ensure all values are JSON serializable"""
        data = super().to_representation(instance)
        
        # Convert any Decimal to float
        if 'total_profit' in data:
            data['total_profit'] = safe_float(data['total_profit'])
        
        return data


# ============ PROFIT BY SOURCE SERIALIZER ============

class ProfitBySourceSerializer(serializers.Serializer):
    """
    Serializer for profit breakdown by source
    """
    
    source = serializers.CharField()
    source_display = serializers.CharField()
    amount = serializers.FloatField()
    percentage = serializers.FloatField()
    
    @classmethod
    def from_dict(cls, data: Dict[str, float], total: float):
        """Create list of serialized objects from dictionary"""
        result = []
        for source, amount in data.items():
            percentage = (amount / total * 100) if total > 0 else 0
            result.append({
                'source': source,
                'source_display': source.replace('_', ' ').title(),
                'amount': amount,
                'percentage': round(percentage, 2)
            })
        return result


# ============ DAILY PROFIT SERIALIZER ============

class DailyProfitSerializer(serializers.Serializer):
    """
    Serializer for daily profit data
    """
    
    date = serializers.DateField()
    profit = serializers.FloatField()
    timestamp = serializers.FloatField(required=False)
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'profit' in data:
            data['profit'] = safe_float(data['profit'])
        return data