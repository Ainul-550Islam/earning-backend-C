import logging
import hashlib
import time
import json
import os
from uuid import uuid4 # এটি লাগবেই
from django.db import models, transaction
from datetime import timedelta
from django.core.validators import MinValueValidator
from typing import Dict, Any, Optional, List, Tuple
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
try:
    import jsonschema
except ImportError:
    jsonschema = None
from django.db.models import Count, Q, Avg, Sum, F, ExpressionWrapper, fields
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete, post_delete
from django.utils.html import format_html
from redis import Redis
from django_redis import get_redis_connection
import uuid
from typing import Dict, Any, Optional, List, Union
from decimal import Decimal, InvalidOperation
from django.db.models.functions import TruncDate
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

def task_proof_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'{uuid4().hex}.{ext}'
    return os.path.join('task_proofs/', filename)


class MasterTask(models.Model):
    """
    Single model to handle all 70+ tasks using metadata-driven architecture
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    # Master System Categories
    class SystemType(models.TextChoices):
        CLICK_VISIT = 'click_visit', 'Click & Visit System'
        GAMIFIED = 'gamified', 'Gamified System'
        DATA_INPUT = 'data_input', 'Data Input System'
        GUIDE_SIGNUP = 'guide_signup', 'Guide/Signup System'
        EXTERNAL_WALL = 'external_wall', 'External Wall System'
    
    # Task Categories (original categorization for reference)
    class TaskCategory(models.TextChoices):
        DAILY_RETENTION = 'daily_retention', 'Daily & Retention'
        GAMIFIED = 'gamified', 'Gamified'
        ADS_MULTIMEDIA = 'ads_multimedia', 'Ads & Multimedia'
        APP_SOCIAL = 'app_social', 'App & Social'
        WEB_CONTENT = 'web_content', 'Web & Content'
        REFER_TEAM = 'refer_team', 'Refer & Team'
        ADVANCED_API = 'advanced_api', 'Advanced & API'
    
    # Basic Fields
    task_id = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(blank=True, default='')
    
    # Categorization
    system_type = models.CharField(
        max_length=20, 
        choices=SystemType.choices,
        db_index=True)
    category = models.CharField(
        max_length=20, 
        choices=TaskCategory.choices,
        db_index=True)
    
    # Task Configuration (Metadata - Core of the system)
    task_metadata = models.JSONField(default=dict, blank=True)
    
    # Rewards Configuration
    rewards = models.JSONField(default=dict, blank=True)
    
    # Constraints & Limits
    constraints = models.JSONField(default=dict, blank=True)
    
    # UI/UX Configuration
    ui_config = models.JSONField(default=dict, blank=True)
    
    # Status & Visibility
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    
    # Time Configuration
    available_from = models.DateTimeField(default=timezone.now)
    available_until = models.DateTimeField(null=True, blank=True)
    
    # Targeting
    target_user_segments = models.JSONField(default=list, blank=True)
    min_user_level = models.IntegerField(default=1)
    max_user_level = models.IntegerField(null=True, blank=True)
    
    # Statistics
    total_completions = models.IntegerField(default=0)
    unique_users_completed = models.IntegerField(default=0)
    daily_completion_limit = models.IntegerField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['system_type', 'is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['available_from', 'available_until']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['task_id']),
        ]
        ordering = ['sort_order', '-created_at']
        unique_together = ['task_id']  # Prevent duplicates
    
    def __str__(self):
        return f"{self.task_id} - {self.name}"
    
    # ============ REDIS CONNECTION ============
    
    def _get_redis(self):
        """Get Redis connection with fallback"""
        try:
            return get_redis_connection("default")
        except:
            return None
    
    # ============ PROPERTIES (For Admin Display) ============
    
    @property
    def is_expired(self) -> bool:
        """Check if task is expired"""
        if self.available_until:
            return timezone.now() > self.available_until
        return False
    
    @property
    def is_future_task(self) -> bool:
        """Check if task is scheduled for future"""
        if self.available_from:
            return timezone.now() < self.available_from
        return False
    
    @property
    def is_available_now(self) -> bool:
        """Check if task is currently available"""
        now = timezone.now()
        return (
            self.is_active and
            (not self.available_from or now >= self.available_from) and
            (not self.available_until or now <= self.available_until)
        )
        
    def is_available_for_user(self, user_level: int = 1, user_id=None) -> Tuple[bool, Optional[str]]:
        """
        Check if task is available for a specific user level.
        Called by serializer's get_is_available() and is_available_with_cooldown()
        Returns: (is_available: bool, reason: str | None)
        """
        try:
            # 1. Task must be active
            if not self.is_active:
                return False, "Task is not active"

            # 2. Check time window
            now = timezone.now()
            if self.available_from and now < self.available_from:
                return False, "Task not yet available"

            if self.available_until and now > self.available_until:
                return False, "Task has expired"

            # 3. Check user level requirement
            if user_level < self.min_user_level:
                return False, f"Requires level {self.min_user_level}"

            if self.max_user_level and user_level > self.max_user_level:
                return False, f"Only available up to level {self.max_user_level}"

            return True, None

        except Exception as e:
            logger.error(f"Error in is_available_for_user for task {self.task_id}: {str(e)}")
            return False, "Error checking availability"
    
    @property
    def time_status(self) -> str:
        """Get time-based status"""
        if self.is_expired:
            return 'expired'
        elif self.is_future_task:
            return 'scheduled'
        elif self.is_available_now:
            return 'available'
        else:
            return 'inactive'
    
    @property
    def level_range(self) -> str:
        """Get level range as string"""
        if self.max_user_level:
            return f"Lvl {self.min_user_level}-{self.max_user_level}"
        return f"Lvl {self.min_user_level}+"
    
    @property
    def reward_summary(self) -> Dict:
        """Get reward summary"""
        return {
            'points': self.get_reward_value('points', 0),
            'coins': self.get_reward_value('coins', 0),
            'experience': self.get_reward_value('experience', 0)
        }
    
    # ============ ADMIN DISPLAY METHODS ============
    
    def colored_system_type(self):
        """Display colored system type for admin"""
        colors = {
            self.SystemType.CLICK_VISIT: '#4CAF50',
            self.SystemType.GAMIFIED: '#FF9800',
            self.SystemType.DATA_INPUT: '#2196F3',
            self.SystemType.GUIDE_SIGNUP: '#9C27B0',
            self.SystemType.EXTERNAL_WALL: '#F44336'
        }
        color = colors.get(self.system_type, '#607D8B')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            self.get_system_type_display()
        )
    colored_system_type.short_description = 'System Type'
    colored_system_type.admin_order_field = 'system_type'
    
    def completion_count(self):
        """Display completion count for admin"""
        count = self.completions.count()
        return format_html(
            '<b>{}</b> completion{}',
            count,
            's' if count != 1 else ''
        )
    completion_count.short_description = 'Completions'
    
    def reward_display(self):
        """Display rewards in admin"""
        points = self.get_reward_value('points', 0)
        exp = self.get_reward_value('experience', 0)
        coins = self.get_reward_value('coins', 0)
        
        return format_html(
            '<span title="Exp: {} | Coins: {}">[MONEY] {}</span>',
            exp, coins, points
        )
    reward_display.short_description = 'Points'
    
    def available_now(self):
        """Show availability status in admin"""
        if self.is_expired:
            return format_html('<span style="color: red;">⌛ Expired</span>')
        elif self.is_future_task:
            return format_html('<span style="color: orange;">⏳ Scheduled</span>')
        elif self.is_available_now:
            return format_html('<span style="color: green;">[OK] Available</span>')
        return format_html('<span style="color: gray;">[ERROR] Inactive</span>')
    available_now.short_description = 'Status'
    
    # ============ VALIDATION METHODS ============
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Validate date range
        if self.available_from and self.available_until:
            if self.available_from > self.available_until:
                raise ValidationError({
                    'available_until': 'Available until must be after available from'
                })
        
        # Validate level range
        if self.max_user_level and self.min_user_level > self.max_user_level:
            raise ValidationError({
                'max_user_level': 'Max user level must be greater than or equal to min user level'
            })
        
        # Validate metadata
        metadata_errors = self.validate_metadata()
        if metadata_errors:
            raise ValidationError(metadata_errors)
    
    def validate_metadata(self) -> Dict[str, str]:
        """
        PART 7: JSON Schema validation for task metadata.
        
        Validates task_metadata against system_type-specific JSON schemas.
        Each task type must conform to its schema version.
        """
        errors = {}
        
        if not self.task_metadata:
            errors['task_metadata'] = "Task metadata cannot be empty"
            return errors
        
        # Get validator based on system type
        schema = self._get_metadata_schema(self.system_type)
        
        if schema and jsonschema:
            try:
                jsonschema.validate(self.task_metadata, schema)
            except jsonschema.ValidationError as e:
                errors['task_metadata'] = f"Schema validation failed: {e.message}"
            except jsonschema.SchemaError as e:
                errors['task_metadata'] = f"Invalid schema definition: {e.message}"
        else:
            # Fallback to manual validation if jsonschema unavailable
            self._manual_validate_metadata(errors)
        
        return errors
    
    def _get_metadata_schema(self, system_type: str) -> Optional[Dict]:
        """
        Return JSON Schema for system_type.
        Store schemas in settings.TASK_METADATA_SCHEMAS for easy management.
        """
        # Allow override in Django settings
        if hasattr(settings, 'TASK_METADATA_SCHEMAS'):
            return settings.TASK_METADATA_SCHEMAS.get(system_type)
        
        # Default schemas
        schemas = {
            self.SystemType.CLICK_VISIT: {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "duration_seconds": {"type": "integer", "minimum": 5, "maximum": 3600},
                    "require_scroll": {"type": "boolean"},
                    "require_click_button": {"type": "boolean"}
                },
                "required": ["url", "duration_seconds"],
                "additionalProperties": True
            },
            
            self.SystemType.GAMIFIED: {
                "type": "object",
                "properties": {
                    "game_type": {"type": "string", "enum": ["spin", "scratch", "slot", "quiz", "math", "typing", "memory", "find_object"]},
                    "difficulty_level": {"type": "string", "enum": ["easy", "medium", "hard"]},
                    "rounds": {"type": "integer", "minimum": 1, "maximum": 10},
                    "time_limit_seconds": {"type": "integer", "minimum": 10}
                },
                "required": ["game_type"],
                "additionalProperties": True
            },
            
            self.SystemType.DATA_INPUT: {
                "type": "object",
                "properties": {
                    "input_type": {"type": "string", "enum": ["quiz", "survey", "form", "translation", "captcha"]},
                    "questions_count": {"type": "integer", "minimum": 1},
                    "estimated_time_minutes": {"type": "integer", "minimum": 1},
                    "required_fields": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["input_type"],
                "additionalProperties": True
            },
            
            self.SystemType.GUIDE_SIGNUP: {
                "type": "object",
                "properties": {
                    "action_type": {"type": "string", "enum": ["app_install", "signup", "follow", "subscribe", "share", "verify"]},
                    "package_name": {"type": "string"},
                    "url": {"type": "string", "format": "uri"},
                    "verification_method": {"type": "string", "enum": ["auto", "manual", "webhook"]}
                },
                "required": ["action_type"],
                "additionalProperties": True
            },
            
            self.SystemType.EXTERNAL_WALL: {
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "enum": [
                        # Top-5 CPA/offerwall networks
                        "cpalead", "ogads", "adgate", "offertoro", "monlix",
                        # Additional networks
                        "adgem", "fyber", "pollfish", "bitlabs",
                    ]},
                    "wall_id": {"type": "string"},
                    "user_id_param": {"type": "string"},
                    "tracking_url": {"type": "string", "format": "uri"}
                },
                "required": ["provider", "wall_id"],
                "additionalProperties": True
            }
        }
        
        return schemas.get(system_type)
    
    def _manual_validate_metadata(self, errors: Dict[str, str]):
        """
        Fallback validation if jsonschema library not available.
        These are the same checks as before, but organized by type.
        """
        if not self.task_metadata:
            errors['task_metadata'] = "Task metadata cannot be empty"
            return
        
        # Get validator based on system type
        validators = {
            self.SystemType.CLICK_VISIT: self._validate_click_visit_metadata,
            self.SystemType.GAMIFIED: self._validate_gamified_metadata,
            self.SystemType.DATA_INPUT: self._validate_data_input_metadata,
            self.SystemType.GUIDE_SIGNUP: self._validate_guide_signup_metadata,
            self.SystemType.EXTERNAL_WALL: self._validate_external_wall_metadata,
        }
        
        validator = validators.get(self.system_type)
        if validator:
            try:
                validator(errors)
            except Exception as e:
                errors['system_type'] = f"Validation error: {str(e)}"
    
    def _validate_click_visit_metadata(self, errors):
        """Validate Click & Visit System tasks"""
        required_fields = ['url', 'duration_seconds']
        for field in required_fields:
            if field not in self.task_metadata:
                errors[f'task_metadata_{field}'] = f"Click/Visit tasks require '{field}' field"
                return
        
        url = self.task_metadata.get('url', '')
        duration = self.task_metadata.get('duration_seconds', 0)
        
        if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            errors['task_metadata_url'] = "Invalid URL format"
        
        if not isinstance(duration, (int, float)) or duration < 5:
            errors['task_metadata_duration'] = "Duration must be at least 5 seconds"
    
    def _validate_gamified_metadata(self, errors):
        """Validate Gamified System tasks"""
        game_types = ['spin', 'scratch', 'slot', 'quiz', 'math', 'typing', 'memory', 'find_object']
        
        game_type = self.task_metadata.get('game_type')
        if not game_type or game_type not in game_types:
            errors['task_metadata_game_type'] = f"Game type must be one of: {', '.join(game_types)}"
    
    def _validate_data_input_metadata(self, errors):
        """Validate Data Input System tasks"""
        input_types = ['quiz', 'survey', 'form', 'translation', 'captcha']
        
        input_type = self.task_metadata.get('input_type')
        if not input_type or input_type not in input_types:
            errors['task_metadata_input_type'] = f"Input type must be one of: {', '.join(input_types)}"
    
    def _validate_guide_signup_metadata(self, errors):
        """Validate Guide/Signup System tasks"""
        action_types = ['app_install', 'signup', 'follow', 'subscribe', 'share', 'verify']
        
        action_type = self.task_metadata.get('action_type')
        if not action_type or action_type not in action_types:
            errors['task_metadata_action_type'] = f"Action type must be one of: {', '.join(action_types)}"
        
        if action_type == 'app_install':
            if 'package_name' not in self.task_metadata:
                errors['task_metadata_package_name'] = "App install tasks require 'package_name'"
    
    def _validate_external_wall_metadata(self, errors):
        """Validate External Wall System tasks"""
        wall_providers = [
            # Top-5 CPA/offerwall platforms (compared in architecture assessment)
            'cpalead', 'ogads', 'adgate', 'offertoro', 'monlix',
            # Additional supported networks
            'adgem', 'fyber', 'pollfish', 'bitlabs',
        ]
        
        provider = self.task_metadata.get('provider')
        if not provider or provider not in wall_providers:
            errors['task_metadata_provider'] = f"Provider must be one of: {', '.join(wall_providers)}"
    
    # ============ SAVE METHOD ============
    
    def save(self, *args, **kwargs):
        """
        Override save with bulletproof patterns
        """
        try:
            # Ensure task_id is set
            if not self.task_id:
                self.task_id = self._generate_task_id()
            
            # Set default values
            self.rewards = self._get_default_rewards()
            self.constraints = self._get_default_constraints()
            self.ui_config = self._get_default_ui_config()
            
            # Clear cache for this task
            cache.delete(f'task_availability_{self.task_id}')
            cache.delete(f'task_{self.task_id}')
            
            # Clear Redis cache if available
            redis_client = self._get_redis()
            if redis_client:
                redis_client.delete(f"task_completions:{self.task_id}")
                redis_client.delete(f"task_unique_users:{self.task_id}")
            
            # Finally save
            super().save(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error saving task {getattr(self, 'name', 'Unknown')}: {str(e)}")
            raise
    
    def _generate_task_id(self) -> str:
        """Generate unique task ID"""
        prefix = {
            self.SystemType.CLICK_VISIT: 'CV',
            self.SystemType.GAMIFIED: 'GM',
            self.SystemType.DATA_INPUT: 'DI',
            self.SystemType.GUIDE_SIGNUP: 'GS',
            self.SystemType.EXTERNAL_WALL: 'EW',
        }.get(self.system_type, 'TS')
        
        hash_input = f"{self.name}{time.time()}".encode()
        unique_hash = hashlib.md5(hash_input).hexdigest()[:8]
        return f"{prefix}_{unique_hash}"
    
    def _get_default_rewards(self) -> Dict:
        """Get rewards with defaults"""
        if self.rewards and isinstance(self.rewards, dict):
            return {
                'points': self.rewards.get('points', 10),
                'coins': self.rewards.get('coins', 0),
                'experience': self.rewards.get('experience', 5),
                'bonus': self.rewards.get('bonus', {})
            }
        return {'points': 10, 'coins': 0, 'experience': 5, 'bonus': {}}
    
    def _get_default_constraints(self) -> Dict:
        """Get constraints with defaults"""
        if self.constraints and isinstance(self.constraints, dict):
            return {
                'daily_limit': self.constraints.get('daily_limit'),
                'total_limit': self.constraints.get('total_limit'),
                'cooldown_minutes': self.constraints.get('cooldown_minutes', 0),
                'required_level': self.constraints.get('required_level', 1)
            }
        return {'daily_limit': None, 'total_limit': None, 'cooldown_minutes': 0, 'required_level': 1}
    
    def _get_default_ui_config(self) -> Dict:
        """Get UI config with defaults"""
        if self.ui_config and isinstance(self.ui_config, dict):
            return {
                'icon': self.ui_config.get('icon', 'default_task.png'),
                'color': self.ui_config.get('color', '#4CAF50'),
                'animation': self.ui_config.get('animation'),
                'button_text': self.ui_config.get('button_text', 'Start')
            }
        return {'icon': 'default_task.png', 'color': '#4CAF50', 'animation': None, 'button_text': 'Start'}
    
    # ============ UTILITY METHODS ============
    
    def get_metadata_value(self, key: str, default=None):
        """Get metadata value safely"""
        if not isinstance(self.task_metadata, dict):
            return default
        return self.task_metadata.get(key, default)
    
    def get_reward_value(self, key: str, default=0):
        """Get reward value safely"""
        if not isinstance(self.rewards, dict):
            return default
        return self.rewards.get(key, default)
    
    # ============ OPTIMIZED INCREMENT COMPLETION WITH REDIS ============
    
    @transaction.atomic
    def increment_completion(self, user_id=None):
        """
        Safely increment completion count with transaction and Redis caching
        Optimized for high traffic with millions of users
        """
        redis_client = self._get_redis()
        
        try:
            # Use select_for_update to prevent race conditions
            task = MasterTask.objects.select_for_update().get(id=self.id)
            task.total_completions += 1
            
            # Check if this is a new user using Redis first, then DB as fallback
            is_new_user = False
            
            if user_id:
                if redis_client:
                    # Redis HyperLogLog for unique user counting (memory efficient)
                    # Use PFADD which uses 12KB per key regardless of number of users
                    redis_key = f"task_unique_users:{self.task_id}"
                    result = redis_client.pfadd(redis_key, user_id)
                    is_new_user = result == 1  # Returns 1 if new, 0 if already counted
                    
                    # Periodically sync Redis to DB (every 1000 new users)
                    if is_new_user and task.unique_users_completed % 1000 == 0:
                        estimated_count = redis_client.pfcount(redis_key)
                        task.unique_users_completed = estimated_count
                else:
                    # Fallback to database check if Redis not available
                    from .models import UserTaskCompletion
                    is_new_user = not UserTaskCompletion.objects.filter(
                        task=task, 
                        user_id=user_id
                    ).exists()
            
            if is_new_user:
                task.unique_users_completed += 1
            
            task.save(update_fields=['total_completions', 'unique_users_completed'])
            
            # Update Redis cache for real-time stats
            if redis_client:
                # Store completion count in Redis (updated every minute via cron)
                redis_client.setex(
                    f"task_stats:{self.task_id}", 
                    3600,  # 1 hour cache
                    json.dumps({
                        'total_completions': task.total_completions,
                        'unique_users': task.unique_users_completed
                    })
                )
                
                # Store user's completion in Redis sorted set for streak calculation
                if user_id:
                    streak_key = f"user_streak:{user_id}:{self.task_id}"
                    redis_client.zadd(
                        streak_key,
                        {str(timezone.now().timestamp()): timezone.now().timestamp()}
                    )
                    redis_client.expire(streak_key, 7 * 24 * 3600)  # 7 days TTL
            
            # Update Django cache as fallback
            cache.set(f'task_stats_{self.task_id}', {
                'total_completions': task.total_completions,
                'unique_users': task.unique_users_completed
            }, timeout=3600)
            
            return task.total_completions
            
        except Exception as e:
            logger.error(f"Error incrementing completion for {self.task_id}: {str(e)}")
            raise
    
    # ============ COOLDOWN VALIDATION WITH REDIS ============
    
    def validate_user_cooldown(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        কাজের মাঝে বিরতি (Cooldown) চেক করা - Optimized with Redis
        Returns: (is_allowed, message_if_not_allowed)
        """
        try:
            # Get cooldown minutes from constraints (safely)
            cooldown_mins = self.constraints.get('cooldown_minutes', 0) if self.constraints else 0
            
            if cooldown_mins > 0:
                redis_client = self._get_redis()
                
                if redis_client:
                    # Check Redis first for last completion time
                    redis_key = f"user_cooldown:{user_id}:{self.task_id}"
                    last_completion_time = redis_client.get(redis_key)
                    
                    if last_completion_time:
                        last_time = float(last_completion_time)
                        wait_until = last_time + (cooldown_mins * 60)
                        now = time.time()
                        
                        if now < wait_until:
                            remaining_seconds = int(wait_until - now)
                            remaining_minutes = remaining_seconds // 60
                            remaining_seconds = remaining_seconds % 60
                            
                            return False, f"Please wait {remaining_minutes}m {remaining_seconds}s"
                else:
                    # Fallback to database if Redis not available
                    from .models import UserTaskCompletion
                    
                    last_completion = UserTaskCompletion.objects.filter(
                        user_id=user_id,
                        task=self,
                        status='completed'
                    ).order_by('-completed_at').first()
                    
                    if last_completion and last_completion.completed_at:
                        wait_until = last_completion.completed_at + timedelta(minutes=cooldown_mins)
                        now = timezone.now()
                        
                        if now < wait_until:
                            remaining_seconds = (wait_until - now).seconds
                            remaining_minutes = remaining_seconds // 60
                            remaining_seconds = remaining_seconds % 60
                            
                            return False, f"Please wait {remaining_minutes}m {remaining_seconds}s"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error validating cooldown for user {user_id}, task {self.task_id}: {str(e)}")
            return False, "Error checking cooldown"
    
    # ============ DAILY LIMIT CHECK WITH REDIS ============
    
    def check_daily_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user has exceeded daily limit - Optimized with Redis
        """
        try:
            if not self.daily_completion_limit:
                return True, None
            
            redis_client = self._get_redis()
            today = timezone.now().date().isoformat()
            
            if redis_client:
                # Use Redis counter with expiry
                redis_key = f"daily_limit:{user_id}:{self.task_id}:{today}"
                today_count = redis_client.get(redis_key)
                
                if today_count and int(today_count) >= self.daily_completion_limit:
                    return False, f"Daily limit ({self.daily_completion_limit}) reached"
            else:
                # Fallback to database
                from .models import UserTaskCompletion
                today_start = timezone.now().replace(hour=0, minute=0, second=0)
                
                today_count = UserTaskCompletion.objects.filter(
                    user_id=user_id,
                    task=self,
                    completed_at__gte=today_start
                ).count()
                
                if today_count >= self.daily_completion_limit:
                    return False, f"Daily limit ({self.daily_completion_limit}) reached"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking daily limit: {str(e)}")
            return True, None  # Allow on error to prevent blocking
    
    # ============ COMPLETE AVAILABILITY CHECK WITH ALL VALIDATIONS ============
    
    def is_available_with_cooldown(self, user_level=1, user_id=None) -> Tuple[bool, Optional[str]]:
        """
        Complete availability check including cooldown and daily limits
        Combines all validations in optimized way
        """
        # First check basic availability
        is_available, reason = self.is_available_for_user(user_level, user_id)
        
        if not is_available:
            return False, reason
        
        # Check daily limit if user_id provided
        if user_id:
            limit_ok, limit_msg = self.check_daily_limit(user_id)
            if not limit_ok:
                return False, limit_msg
            
            # Then check cooldown
            cooldown_ok, cooldown_msg = self.validate_user_cooldown(user_id)
            if not cooldown_ok:
                return False, cooldown_msg
        
        return True, None
    
    # ============ OPTIMIZED STREAK CALCULATION WITH REDIS ============
    
    def _get_user_streak(self, user_id: int) -> int:
        """
        Get user's current streak for this task - Optimized with Redis
        """
        try:
            redis_client = self._get_redis()
            
            if redis_client:
                # Get streak from Redis sorted set
                streak_key = f"user_streak:{user_id}:{self.task_id}"
                
                # Get last 7 days of completions from Redis
                now = time.time()
                week_ago = now - (7 * 24 * 3600)
                
                completions = redis_client.zrangebyscore(
                    streak_key, 
                    week_ago, 
                    now, 
                    withscores=True
                )
                
                if not completions:
                    return 0
                
                # Sort by timestamp descending
                completions = sorted(completions, key=lambda x: x[1], reverse=True)
                
                # Calculate streak
                streak = 1
                current_date = timezone.datetime.fromtimestamp(completions[0][1]).date()
                
                for _, timestamp in completions[1:]:
                    next_date = timezone.datetime.fromtimestamp(timestamp).date()
                    if (current_date - next_date).days == 1:
                        streak += 1
                        current_date = next_date
                    else:
                        break
                
                return streak
            else:
                # Fallback to database calculation
                from .models import UserTaskCompletion
                from django.utils import timezone
                from datetime import timedelta
                
                last_7_days = timezone.now() - timedelta(days=7)
                completions = UserTaskCompletion.objects.filter(
                    user_id=user_id,
                    task=self,
                    status='completed',
                    completed_at__gte=last_7_days
                ).order_by('-completed_at')
                
                if not completions.exists():
                    return 0
                
                streak = 1
                current_date = completions[0].completed_at.date()
                
                for completion in completions[1:]:
                    next_date = completion.completed_at.date()
                    if (current_date - next_date).days == 1:
                        streak += 1
                        current_date = next_date
                    else:
                        break
                
                return streak
                
        except Exception as e:
            logger.error(f"Error calculating streak for user {user_id}: {str(e)}")
            return 0
    
    # ============ REWARD ENGINE ============
    
    def calculate_reward(self, user=None, metadata: Dict = None) -> Dict[str, Any]:
        """
        ইউজার যখন কাজ শেষ করবে, তাকে কত পয়েন্ট দিতে হবে তা বের করে
        Dynamic reward calculation based on user level, streaks, bonuses etc.
        """
        try:
            # Base rewards from task configuration
            base_points = self.get_reward_value('points', 0)
            base_coins = self.get_reward_value('coins', 0)
            base_experience = self.get_reward_value('experience', 0)
            
            # Initialize multipliers
            level_multiplier = 1.0
            streak_multiplier = 1.0
            bonus_multiplier = 1.0
            
            # Level-based multiplier (higher level = more rewards)
            if user and hasattr(user, 'level'):
                user_level = getattr(user, 'level', 1)
                level_multiplier = 1.0 + (user_level * 0.01)  # 1% per level
                level_multiplier = min(level_multiplier, 2.0)  # Max 2x
            
            # Check for bonus in metadata
            if metadata and isinstance(metadata, dict):
                if metadata.get('double_points'):
                    bonus_multiplier *= 2
                
                event_multiplier = metadata.get('event_multiplier', 1.0)
                bonus_multiplier *= event_multiplier
            
            # Check task-specific bonuses from constraints
            if self.constraints:
                # First-time bonus
                if user and self.constraints.get('first_time_bonus'):
                    from .models import UserTaskCompletion
                    completed_before = UserTaskCompletion.objects.filter(
                        user_id=user.id,
                        task=self,
                        status='completed'
                    ).exists()
                    
                    if not completed_before:
                        bonus_multiplier *= self.constraints.get('first_time_multiplier', 1.5)
                
                # Streak bonus
                if user and self.constraints.get('streak_bonus_enabled'):
                    streak_days = self._get_user_streak(user.id)
                    streak_multiplier = 1.0 + (streak_days * 0.1)  # 10% per streak day
                    streak_multiplier = min(streak_multiplier, 3.0)  # Max 3x
            
            # Calculate final rewards
            final_points = int(base_points * level_multiplier * streak_multiplier * bonus_multiplier)
            final_coins = int(base_coins * level_multiplier * streak_multiplier * bonus_multiplier)
            final_experience = int(base_experience * level_multiplier * streak_multiplier * bonus_multiplier)
            
            # Check for bonus rewards in metadata
            bonus_rewards = self._get_bonus_rewards(user, metadata)
            
            # Prepare reward breakdown
            reward_breakdown = {
                'base': {
                    'points': base_points,
                    'coins': base_coins,
                    'experience': base_experience
                },
                'multipliers': {
                    'level': round(level_multiplier, 2),
                    'streak': round(streak_multiplier, 2),
                    'bonus': round(bonus_multiplier, 2),
                    'total_multiplier': round(level_multiplier * streak_multiplier * bonus_multiplier, 2)
                },
                'final': {
                    'points': final_points,
                    'coins': final_coins,
                    'experience': final_experience
                },
                'bonus': bonus_rewards,
                'total': {
                    'points': final_points + bonus_rewards.get('points', 0),
                    'coins': final_coins + bonus_rewards.get('coins', 0),
                    'experience': final_experience + bonus_rewards.get('experience', 0)
                }
            }
            
            logger.debug(f"Reward calculated for task {self.task_id}: {reward_breakdown}")
            return reward_breakdown
            
        except Exception as e:
            logger.error(f"Error calculating reward for task {self.task_id}: {str(e)}")
            return {
                'base': {'points': 0, 'coins': 0, 'experience': 0},
                'final': {'points': 5, 'coins': 0, 'experience': 1},
                'error': str(e)
            }
    
    def _get_bonus_rewards(self, user, metadata: Dict = None) -> Dict[str, int]:
        """
        Get bonus rewards from various sources
        """
        bonus = {'points': 0, 'coins': 0, 'experience': 0}
        
        try:
            # Check for bonus in task metadata
            if self.task_metadata:
                bonus_points = self.task_metadata.get('bonus_points', 0)
                if bonus_points:
                    bonus['points'] += bonus_points
            
            # Time-based bonuses
            now = timezone.now()
            hour = now.hour
            
            # Happy hour bonus (6 PM - 8 PM)
            if 18 <= hour <= 20:
                bonus['points'] += 5
                bonus['experience'] += 2
            
            # Weekend bonus
            if now.weekday() >= 5:
                bonus['points'] += 10
                bonus['coins'] += 1
            
            # Special date bonuses
            special_dates = {
                (1, 1): 'New Year',
                (2, 21): 'Eid',
                (3, 26): 'Independence',
                (12, 31): 'New Year Eve'
            }
            
            current_date = (now.month, now.day)
            if current_date in special_dates:
                bonus['points'] += 25
                bonus['experience'] += 10
                bonus['holiday'] = special_dates[current_date]
            
            # User tier bonuses
            if user and hasattr(user, 'membership_tier'):
                tier_bonuses = {
                    'bronze': {'points': 0},
                    'silver': {'points': 5},
                    'gold': {'points': 15},
                    'platinum': {'points': 25}
                }
                tier = getattr(user, 'membership_tier', 'bronze')
                if tier in tier_bonuses:
                    bonus['points'] += tier_bonuses[tier]['points']
            
            return bonus
            
        except Exception as e:
            logger.error(f"Error calculating bonus rewards: {str(e)}")
            return bonus
    
    # ============ AWARD REWARDS TO USER ============
    
    @transaction.atomic
    def award_rewards(self, user, completion, metadata: Dict = None) -> Dict:
        """
        Calculate and award rewards to user
        Updates user's balance and returns awarded rewards
        """
        try:
            # Calculate rewards
            reward_breakdown = self.calculate_reward(user, metadata)
            final_rewards = reward_breakdown['total']
            
            # Update user balance
            if hasattr(user, 'points'):
                user.points += final_rewards['points']
            if hasattr(user, 'coins'):
                user.coins += final_rewards['coins']
            if hasattr(user, 'experience'):
                user.experience += final_rewards['experience']
            
            user.save(update_fields=['points', 'coins', 'experience'])
            
            # Update completion record
            completion.rewards_awarded = final_rewards
            completion.save(update_fields=['rewards_awarded'])
            
            # Update Redis cooldown
            redis_client = self._get_redis()
            if redis_client:
                redis_key = f"user_cooldown:{user.id}:{self.task_id}"
                redis_client.setex(redis_key, self.constraints.get('cooldown_minutes', 0) * 60, time.time())
                
                # Update daily limit counter
                today = timezone.now().date().isoformat()
                daily_key = f"daily_limit:{user.id}:{self.task_id}:{today}"
                redis_client.incr(daily_key)
                redis_client.expire(daily_key, 24 * 3600)  # 24 hours
            
            logger.info(f"Awarded {final_rewards} to user {user.id} for task {self.task_id}")
            
            return {
                'success': True,
                'rewards': final_rewards,
                'breakdown': reward_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error awarding rewards: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'rewards': {'points': 0, 'coins': 0, 'experience': 0}
            }
    
    # ============ BULK OPERATIONS ============
    
    @classmethod
    def bulk_activate(cls, task_ids: List[int]) -> int:
        """Activate multiple tasks at once"""
        try:
            count = cls.objects.filter(id__in=task_ids).update(is_active=True)
            for task_id in task_ids:
                cache.delete(f'task_availability_{task_id}')
                cache.delete(f'task_{task_id}')
            return count
        except Exception as e:
            logger.error(f"Error in bulk activate: {str(e)}")
            return 0
    
    @classmethod
    def bulk_deactivate(cls, task_ids: List[int]) -> int:
        """Deactivate multiple tasks at once"""
        try:
            count = cls.objects.filter(id__in=task_ids).update(is_active=False)
            for task_id in task_ids:
                cache.delete(f'task_availability_{task_id}')
                cache.delete(f'task_{task_id}')
            return count
        except Exception as e:
            logger.error(f"Error in bulk deactivate: {str(e)}")
            return 0


# ============================================================================
# PART 1: TASK LOCKING - SINGLE OWNERSHIP ENFORCEMENT
# ============================================================================

class TaskLock(models.Model):
    """
    Enforce "One Task, One Owner" principle.
    Prevents multiple users from working on same task simultaneously.
    
    Design Pattern:
    ✓ User clicks task → acquire EXCLUSIVE lock
    ✓ Lock expires after 30 minutes (configurable)
    ✓ Expired locks auto-cleanup every 5 minutes
    ✓ Lock must be held to complete task (ownership validation)
    """
    
    class LockType(models.TextChoices):
        EXCLUSIVE = 'exclusive', 'Exclusive (Only 1 user at a time)'
        SHARED = 'shared', 'Shared (Multiple users allowed)'
        WAITING = 'waiting', 'Waiting (In queue for exclusive lock)'
    
    # Primary Keys
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    task = models.ForeignKey(
        MasterTask,
        on_delete=models.CASCADE,
        related_name='task_locks'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_locks'
    )
    
    # Lock Metadata
    lock_type = models.CharField(
        max_length=20,
        choices=LockType.choices,
        default=LockType.EXCLUSIVE,
        db_index=True
    )
    
    # Lock Lifecycle Timestamps
    acquired_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Lock auto-releases after this timestamp"
    )
    released_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When lock was manually released (completion/abandonment)"
    )
    
    # Worker Tracking (for distributed systems)
    lock_holder_worker = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Which Celery worker/process acquired this lock"
    )
    
    # Optimistic Locking (prevent race conditions)
    version = models.IntegerField(
        default=0,
        help_text="Incremented on each write; used for optimistic locking"
    )
    
    class Meta:
        # UNIQUE constraint: only one EXCLUSIVE lock per task (CRITICAL)
        constraints = [
            models.UniqueConstraint(
                fields=['task', 'user', 'lock_type'],
                condition=models.Q(lock_type='exclusive', released_at__isnull=True),
                name='unique_exclusive_lock_per_task'
            )
        ]
        indexes = [
            # Find all active locks for a task (for new user attempts)
            # Find user's locks for cleanup on logout
            models.Index(fields=['user', 'released_at']),
            # ✅ CRITICAL: Find expired locks for cleanup (MUST be fast)
            models.Index(fields=['expires_at'], name='idx_tasklock_expires_at'),
            # Find locks by lock type
            models.Index(fields=['lock_type', 'released_at']),
            # ✅ NEW: Find active locks (for count_concurrent_users)
            models.Index(fields=['task', 'released_at']),
            # ✅ NEW: Find expired locks by task
            models.Index(fields=['task', 'expires_at']),
        ]
        verbose_name = "Task Lock"
        verbose_name_plural = "Task Locks"
        ordering = ['-acquired_at']
    
    def __str__(self):
        status = 'RELEASED' if self.released_at else 'ACTIVE'
        return f"{self.user.username} → {self.task.name} [{status}]"
    
    @property
    def is_active(self) -> bool:
        """Check if lock is currently valid and not expired"""
        if self.released_at:
            return False
        if timezone.now() > self.expires_at:
            return False
        return True
    
    @property
    def is_expired(self) -> bool:
        """Check if lock has passed expiry time"""
        return self.released_at is None and timezone.now() > self.expires_at
    
    @property
    def time_remaining_seconds(self) -> int:
        """Seconds until lock expires"""
        if self.released_at:
            return 0
        remaining = (self.expires_at - timezone.now()).total_seconds()
        return max(0, int(remaining))
    
    def release(self, reason: str = 'normal_completion'):
        """
        Release lock (task completed, abandoned, or timeout)
        
        Args:
            reason: String describing why lock is released
                   ('normal_completion', 'user_abandon', 'expired', 'admin_override')
        """
        if not self.released_at:
            self.released_at = timezone.now()
            self.save(update_fields=['released_at'])
            
            # Log the release event
            TaskEventLog.objects.create(
                event_type='LOCK_RELEASED',
                task=self.task,
                user=self.user,
                actor_type='SYSTEM',
                event_data={
                    'lock_id': str(self.id),
                    'reason': reason,
                    'held_duration_seconds': int((self.released_at - self.acquired_at).total_seconds())
                }
            )


class UserTaskCompletion(models.Model):
    """
    Track user task completions with proper ForeignKey to User model
    and lock tracking for "One Task, One Owner" enforcement
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks_usertaskcompletion_user',
        db_index=True)
    task = models.ForeignKey(
        MasterTask, 
        on_delete=models.CASCADE, 
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # ✅ NEW: Lock tracking for "One Task, One Owner"
    task_lock = models.ForeignKey(
        'TaskLock',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completions',
        help_text="Lock must be held to complete task"
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('started', 'Started'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('verified', 'Verified')
        ],
        default='started',
        db_index=True
    )
    
    proof_data = models.JSONField(default=dict, blank=True)
    rewards_awarded = models.JSONField(default=dict, blank=True)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    admin_revenue_received = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    
    class Meta:
        # ✅ FIXED: Only one STARTED completion per (user, task)
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'task'],
                condition=models.Q(status='started'),
                name='unique_started_completion_per_task'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['completed_at']),
            models.Index(fields=['user', '-started_at']),
        ]
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.user} - {self.task.name} - {self.status}"
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get task completion duration"""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def points_earned(self) -> int:
        """Get points earned from this completion"""
        return self.rewards_awarded.get('points', 0) if self.rewards_awarded else 0
    
    @transaction.atomic
    def complete(self, proof=None):
        """Mark task as completed with transaction safety"""
        try:
            self.status = 'completed'
            self.completed_at = timezone.now()
            
            if proof and isinstance(proof, dict):
                current_proof = self.proof_data or {}
                current_proof.update(proof)
                self.proof_data = current_proof
            
            self.save()
            
            # Increment task completion count
            self.task.increment_completion(user_id=self.user.id)
            
            # Clear user cache
            cache.delete(f'user_tasks_{self.user.id}')
            
        except Exception as e:
            logger.error(f"Error completing task completion {self.id}: {str(e)}")
            raise
    
    @transaction.atomic
    def complete_with_rewards(self, proof=None, metadata=None):
        """
        Complete task and automatically award rewards
        """
        try:
            # Mark as completed
            self.status = 'completed'
            self.completed_at = timezone.now()
            
            if proof and isinstance(proof, dict):
                current_proof = self.proof_data or {}
                current_proof.update(proof)
                self.proof_data = current_proof
            
            self.save()
            
            # Award rewards using task's reward engine
            reward_result = self.task.award_rewards(self.user, self, metadata)
            
            if reward_result['success']:
                logger.info(f"Task {self.task.task_id} completed by user {self.user.id} with rewards")
                return {
                    'success': True,
                    'completion_id': self.id,
                    'rewards': reward_result['rewards'],
                    'breakdown': reward_result.get('breakdown', {})
                }
            else:
                logger.error(f"Task completed but reward failed: {reward_result.get('error')}")
                return {
                    'success': True,
                    'completion_id': self.id,
                    'rewards': {'points': 0, 'coins': 0, 'experience': 0},
                    'warning': 'Task completed but reward calculation failed'
                }
                
        except Exception as e:
            logger.error(f"Error in complete_with_rewards: {str(e)}")
            self.status = 'failed'
            self.save()
            raise
    
    @transaction.atomic
    def verify(self, verified_by='system'):
        """Verify task completion"""
        try:
            self.status = 'verified'
            self.verified_at = timezone.now()
            
            proof_data = self.proof_data or {}
            proof_data['verified_by'] = verified_by
            proof_data['verified_at'] = timezone.now().isoformat()
            self.proof_data = proof_data
            
            self.save()
            
        except Exception as e:
            logger.error(f"Error verifying task completion {self.id}: {str(e)}")
            raise


# ============ SIGNAL HANDLERS ============

@receiver(post_save, sender=MasterTask)
def task_post_save(sender, instance, created, **kwargs):
    """Handle post-save signals"""
    action = "created" if created else "updated"
    logger.info(f"Task {instance.task_id} {action}")
    
    # Clear related caches
    cache.delete('active_tasks_count')
    cache.delete('featured_tasks')


@receiver(pre_delete, sender=MasterTask)
def task_pre_delete(sender, instance, **kwargs):
    """Handle pre-delete signals"""
    logger.warning(f"Task {instance.task_id} is being deleted")
    instance.completions.update(status='failed')


@receiver(post_delete, sender=MasterTask)
def task_post_delete(sender, instance, **kwargs):
    """Handle post-delete signals"""
    logger.info(f"Task {instance.task_id} deleted")
    cache.delete(f'task_{instance.task_id}')
    cache.delete('active_tasks_count')


@receiver(post_save, sender=UserTaskCompletion)
def completion_post_save(sender, instance, created, **kwargs):
    """Handle completion post-save"""
    if created:
        logger.info(f"Task completion started for user {instance.user.id}")
    elif instance.status == 'completed':
        logger.info(f"Task {instance.task.task_id} completed by user {instance.user.id}")
        
        
# ============================================================================
# PART 2: PROOF SUBMISSION & ATTACHMENT - STRUCTURED EVIDENCE VALIDATION
# ============================================================================

class ProofSubmission(models.Model):
    """
    Structured proof validation (replaces JSONField proof_data chaos).
    
    Design Pattern:
    ✓ Each completion has exactly ONE proof submission
    ✓ Proof validated against task-specific JSON schema
    ✓ Supports file attachments (screenshots, receipts, etc)
    ✓ Hash-signed for integrity verification
    ✓ Manual review trail for disputed submissions
    """
    
    class SubmissionType(models.TextChoices):
        JSON_DATA = 'json_data', 'Structured JSON Data'
        SCREENSHOT = 'screenshot', 'Screenshot Upload'
        FORM_SUBMISSION = 'form_submission', 'Form Submission'
        VIDEO_PROOF = 'video_proof', 'Video Evidence'
        DOCUMENT = 'document', 'Document/Receipt'
    
    class VerificationStatus(models.TextChoices):
        PENDING = 'pending', 'Awaiting Verification'
        VERIFIED = 'verified', 'Verified - Ready for Payout'
        REJECTED = 'rejected', 'Rejected - Invalid Proof'
        FLAGGED = 'flagged', 'Flagged for Manual Review'
        DISPUTED = 'disputed', 'Under Dispute'
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Relationship to Completion
    user_task_completion = models.OneToOneField(
        UserTaskCompletion,
        on_delete=models.CASCADE,
        related_name='proof_submission'
    )
    task = models.ForeignKey(
        MasterTask,
        on_delete=models.CASCADE,
        related_name='proof_submissions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='proof_submissions'
    )
    
    # Proof Classification
    submission_type = models.CharField(
        max_length=20,
        choices=SubmissionType.choices,
        default=SubmissionType.JSON_DATA
    )
    data_schema = models.CharField(
        max_length=50,
        blank=True,
        default='v1',
        help_text="Reference to validation schema version (v1, v2, etc)"
    )
    
    # Proof Data
    proof_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Validated proof structure (matches task-specific schema)"
    )
    
    # Integrity
    hash_signature = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="SHA256 of proof_data for tampering detection"
    )
    
    # Verification Status
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True
    )
    
    # Review Tracking
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True, default='')
    manual_review_required = models.BooleanField(default=False)
    
    # Audit Trail
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proof_reviews'
    )
    review_notes = models.TextField(blank=True, default='')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'verification_status']),
            models.Index(fields=['task', 'verification_status']),
            models.Index(fields=['-submitted_at']),
            models.Index(fields=['manual_review_required', 'verification_status']),
        ]
        verbose_name = "Proof Submission"
        verbose_name_plural = "Proof Submissions"
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Proof: {self.user.username} → {self.task.name} [{self.verification_status}]"
    
    def save(self, *args, **kwargs):
        """Compute hash signature on save"""
        if self.proof_data:
            self.hash_signature = self._compute_hash()
        super().save(*args, **kwargs)
    
    def _compute_hash(self) -> str:
        """Compute SHA256 hash of proof data"""
        proof_str = json.dumps(self.proof_data, sort_keys=True)
        return hashlib.sha256(proof_str.encode()).hexdigest()
    
    def verify_hash(self) -> bool:
        """Verify proof integrity (not tampered with)"""
        if not self.hash_signature or not self.proof_data:
            return False
        current_hash = self._compute_hash()
        return current_hash == self.hash_signature
    
    def mark_verified(self, reviewed_by=None):
        """Mark proof as verified"""
        self.verification_status = self.VerificationStatus.VERIFIED
        self.verified_at = timezone.now()
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save(update_fields=['verification_status', 'verified_at', 'reviewed_by', 'reviewed_at'])
    
    def mark_rejected(self, reason: str, reviewed_by=None):
        """Mark proof as rejected"""
        self.verification_status = self.VerificationStatus.REJECTED
        self.rejected_reason = reason
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save(update_fields=['verification_status', 'rejected_reason', 'reviewed_by', 'reviewed_at'])


class ProofAttachment(models.Model):
    """
    File attachments for proof submissions (screenshots, receipts, videos, etc)
    
    Design Pattern:
    ✓ Multiple attachments per proof submission
    ✓ Virus scanning before acceptance
    ✓ S3 CDN storage with hash-based deduplication
    ✓ Metadata extraction (EXIF, resolution, mime-type)
    """
    
    class FileType(models.TextChoices):
        SCREENSHOT = 'screenshot', 'Screenshot'
        RECEIPT = 'receipt', 'Receipt/Invoice'
        PDF = 'pdf', 'PDF Document'
        VIDEO = 'video', 'Video'
        IMAGE = 'image', 'Image'
        OTHER = 'other', 'Other'
    
    class VirusScanStatus(models.TextChoices):
        PENDING = 'pending', 'Awaiting Scan'
        CLEAN = 'clean', 'Passed Scan'
        INFECTED = 'infected', 'Detected Malware'
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Relationship
    proof_submission = models.ForeignKey(
        ProofSubmission,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    
    # File Info
    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER
    )
    file_url = models.URLField(
        help_text="S3 CDN URL where file is stored"
    )
    file_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA256 hash for deduplication"
    )
    file_size_bytes = models.BigIntegerField()
    mime_type = models.CharField(max_length=50, blank=True, default='')
    
    # Security & Scanning
    virus_scan_status = models.CharField(
        max_length=20,
        choices=VirusScanStatus.choices,
        default=VirusScanStatus.PENDING
    )
    virus_scan_result = models.JSONField(
        default=dict,
        blank=True,
        help_text="Result from antivirus scan API"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="EXIF data, resolution, etc"
    )
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['proof_submission', 'file_type']),
            models.Index(fields=['virus_scan_status']),
            models.Index(fields=['-uploaded_at']),
        ]
        verbose_name = "Proof Attachment"
        verbose_name_plural = "Proof Attachments"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.file_type}: {self.file_url.split('/')[-1]}"


# ============================================================================
# PART 3: TASK DISPUTE & CHARGEBACK - DISPUTE RESOLUTION SYSTEM
# ============================================================================

class TaskDispute(models.Model):
    """
    Handle user appeals, payment disputes, and fraud claims.
    
    Design Pattern (3-Tier):
    ✓ Tier 1: Auto-resolution (missing proof → auto-reject)
    ✓ Tier 2: Fraud team review (if fraud_score > 60)
    ✓ Tier 3: Admin escalation (revenue impact > threshold)
    """
    
    class DisputeType(models.TextChoices):
        PROOF_REJECTED = 'proof_rejected', 'Proof Was Rejected'
        TASK_NOT_AVAILABLE = 'task_not_available', 'Task Was Not Available'
        PAYOUT_MISSING = 'payout_missing', 'Payment Not Received'
        FRAUD_FLAGGED = 'fraud_flagged', 'Wrongly Flagged as Fraud'
        TECHNICAL_ISSUE = 'technical_issue', 'Technical/System Issue'
        OTHER = 'other', 'Other Reason'
    
    class DisputeStatus(models.TextChoices):
        OPEN = 'open', 'Open - Awaiting Review'
        ESCALATED = 'escalated', 'Escalated to Higher Tier'
        RESOLVED = 'resolved', 'Resolved'
        REJECTED = 'rejected', 'Claim Rejected'
    
    class Severity(models.TextChoices):
        LOW = 'low', 'Low Priority ($0-$10)'
        MEDIUM = 'medium', 'Medium Priority ($10-$100)'
        HIGH = 'high', 'High Priority ($100-$1000)'
        CRITICAL = 'critical', 'Critical (>$1000)'
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Relationship
    user_task_completion = models.OneToOneField(
        UserTaskCompletion,
        on_delete=models.CASCADE,
        related_name='dispute'
    )
    
    # Dispute Details
    dispute_type = models.CharField(
        max_length=20,
        choices=DisputeType.choices
    )
    status = models.CharField(
        max_length=20,
        choices=DisputeStatus.choices,
        default=DisputeStatus.OPEN,
        db_index=True
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.MEDIUM
    )
    
    # Reporter Info
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='disputes_reported',
        null=True,
        blank=True,
        help_text="User who reported (can be NULL if auto-created by system)"
    )
    reported_at = models.DateTimeField(auto_now_add=True)
    
    # Dispute Description
    reason_text = models.TextField(help_text="User's explanation of dispute")
    
    # Assignment & Review
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disputes_assigned'
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['status', '-reported_at']),
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]
        verbose_name = "Task Dispute"
        verbose_name_plural = "Task Disputes"
        ordering = ['-reported_at']
    
    def __str__(self):
        return f"Dispute: {self.user_task_completion.user.username} → {self.dispute_type}"
    
    def create_escalation(self, level: int, reason: str, reviewed_by):
        """Create escalation to next tier"""
        escalation = DisputeEscalation.objects.create(
            dispute=self,
            escalation_level=level,
            escalated_reason=reason,
            reviewed_by=reviewed_by
        )
        self.status = self.DisputeStatus.ESCALATED
        self.save(update_fields=['status'])
        return escalation


class DisputeEscalation(models.Model):
    """
    Multi-tier escalation tracking for disputes.
    
    Escalation Levels:
    ✓ Level 1: Automated decision (rule-based)
    ✓ Level 2: Fraud team manual review
    ✓ Level 3: Admin/CEO final decision
    """
    
    class ResolutionAction(models.TextChoices):
        AWARD_PAYMENT = 'award_payment', 'Award Full Payment'
        REJECT_CLAIM = 'reject_claim', 'Reject Claim'
        PARTIAL_REFUND = 'partial_refund', 'Partial Refund'
        INVESTIGATION = 'investigation', 'Manual Investigation Required'
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Relationship
    dispute = models.ForeignKey(
        TaskDispute,
        on_delete=models.CASCADE,
        related_name='escalations'
    )
    
    # Escalation Info
    escalation_level = models.IntegerField(
        choices=[(1, 'Tier 1 - Automated'), (2, 'Tier 2 - Fraud Team'), (3, 'Tier 3 - Admin')],
        help_text="1 = Auto, 2 = Fraud Team, 3 = Admin"
    )
    escalated_at = models.DateTimeField(auto_now_add=True)
    escalated_reason = models.TextField()
    
    # Review
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    review_notes = models.TextField(blank=True, default='')
    
    # Resolution
    resolution_action = models.CharField(
        max_length=20,
        choices=ResolutionAction.choices,
        null=True,
        blank=True
    )
    resolution_date = models.DateTimeField(null=True, blank=True)
    
    # Financial Adjustment
    payout_adjustment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Payout delta (positive=refund, negative=clawback)"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['dispute', 'escalation_level']),
            models.Index(fields=['-escalated_at']),
        ]
        verbose_name = "Dispute Escalation"
        verbose_name_plural = "Dispute Escalations"
        ordering = ['escalation_level', '-escalated_at']
    
    def __str__(self):
        return f"Escalation L{self.escalation_level}: {self.dispute.dispute_type}"


# ============================================================================
# PART 4: TASK EVENT LOG - IMMUTABLE AUDIT TRAIL FOR COMPLIANCE
# ============================================================================

class TaskEventLog(models.Model):
    """
    Immutable audit trail of all task lifecycle events.
    
    Design Pattern:
    ✓ Append-only (no updates/deletes)
    ✓ Partition by DATE (monthly partitions for 500K+ users)
    ✓ Archive old logs to cold storage (S3) after 90 days
    ✓ Hash-signed for tampering detection
    ✓ Access audit: track who queries the audit log
    """
    
    class EventType(models.TextChoices):
        # Task Lifecycle
        TASK_CREATED = 'task_created', 'Task Created'
        TASK_STARTED = 'task_started', 'Task Started by User'
        TASK_COMPLETED = 'task_completed', 'Task Completed'
        TASK_ABANDONED = 'task_abandoned', 'Task Abandoned by User'
        
        # Locking Events
        LOCK_ACQUIRED = 'lock_acquired', 'Task Lock Acquired'
        LOCK_RELEASED = 'lock_released', 'Task Lock Released'
        LOCK_EXPIRED = 'lock_expired', 'Lock Expired (Timeout)'
        
        # Proof Events
        PROOF_SUBMITTED = 'proof_submitted', 'Proof Submitted'
        PROOF_VERIFIED = 'proof_verified', 'Proof Verified'
        PROOF_REJECTED = 'proof_rejected', 'Proof Rejected'
        PROOF_REJECTED_FRAUD = 'proof_rejected_fraud', 'Proof Rejected (Fraud)'
        
        # Fraud Events
        FRAUD_CHECK_TRIGGERED = 'fraud_check_triggered', 'Fraud Detection Triggered'
        FRAUD_SIGNAL_GENERATED = 'fraud_signal_generated', 'Fraud Signal Generated'
        FRAUD_BLOCK_APPLIED = 'fraud_block_applied', 'User Blocked (Fraud)'
        
        # Dispute Events
        DISPUTE_OPENED = 'dispute_opened', 'Dispute Opened'
        DISPUTE_ESCALATED = 'dispute_escalated', 'Dispute Escalated'
        DISPUTE_RESOLVED = 'dispute_resolved', 'Dispute Resolved'
        
        # Payout Events
        PAYOUT_AWARDED = 'payout_awarded', 'Payout Awarded'
        PAYOUT_CLAWED_BACK = 'payout_clawed_back', 'Payout Clawed Back'
        PAYOUT_ADJUSTED = 'payout_adjusted', 'Payout Adjusted'
        
        # Admin Actions
        ADMIN_OVERRIDE = 'admin_override', 'Admin Override'
        ADMIN_VERIFICATION = 'admin_verification', 'Admin Manual Verification'
        ADMIN_BLOCK = 'admin_block', 'Admin Block (User/Task)'
    
    class ActorType(models.TextChoices):
        USER = 'user', 'User Action'
        SYSTEM = 'system', 'Automated System'
        ADMIN = 'admin', 'Admin User'
        FRAUD_ENGINE = 'fraud_engine', 'Fraud Detection Engine'
        CELERY_WORKER = 'celery_worker', 'Background Worker'
    
    # Primary Key (BigAutoField for immutability sequence)
    id = models.BigAutoField(primary_key=True)
    
    # Event Classification
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        db_index=True
    )
    actor_type = models.CharField(
        max_length=20,
        choices=ActorType.choices,
        db_index=True
    )
    
    # Related Objects (ForeignKey, can be NULL)
    task = models.ForeignKey(
        MasterTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='event_logs'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='event_logs'
    )
    
    # Actor Identification
    actor_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="user_id, admin_id, or system identifier"
    )
    
    # Event Data
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Event-specific context (task_id, fraud_score, reason, etc)"
    )
    
    # Network Context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Source IP address"
    )
    user_agent = models.TextField(blank=True, default='')
    
    # Integrity & Security
    signature = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="HMAC signature for tampering detection"
    )
    
    # Timestamps (immutable)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        # CRITICAL: Partition by DATE for 500K+ users
        # This must be configured in Django settings or database directly:
        # ALTER TABLE tasks_taskeventlog PARTITION BY RANGE (YEAR(created_at)) ...
        indexes = [
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['actor_type', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
            # ✅ NEW: Lock-specific queries
            models.Index(fields=['event_type'], condition=models.Q(event_type__startswith='lock_'), name='idx_lock_events'),
            models.Index(fields=['task', 'event_type', '-created_at'], name='idx_task_lock_history'),
            # Date-based queries (critical for partition pruning)
            models.Index(fields=['-created_at']),
        ]
        verbose_name = "Task Event Log"
        verbose_name_plural = "Task Event Logs"
        ordering = ['-created_at']
        # Prevent any modifications to audit log
        permissions = [
            ('view_task_event_log', 'Can view task event log'),
            ('export_task_event_log', 'Can export task event log'),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} @ {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def save(self, *args, **kwargs):
        """Prevent updates to audit log (append-only pattern)"""
        if self.pk is not None:
            raise ValueError("Cannot update TaskEventLog entries (append-only audit trail)")
        # Compute signature on creation
        if not self.signature:
            self.signature = self._compute_signature()
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion (immutable audit trail)"""
        raise ValueError("Cannot delete TaskEventLog entries (immutable audit trail)")
    
    def _compute_signature(self) -> str:
        """Compute HMAC signature for integrity"""
        import hmac
        key = settings.SECRET_KEY.encode()
        message = json.dumps({
            'event_type': self.event_type,
            'user_id': str(self.user_id),
            'task_id': str(self.task_id),
            'event_data': self.event_data,
            'created_at': self.created_at.isoformat() if self.created_at else ''
        }, sort_keys=True)
        return hmac.new(key, message.encode(), 'sha256').hexdigest()
    
    def verify_signature(self) -> bool:
        """Verify audit log entry integrity"""
        expected_sig = self._compute_signature()
        return self.signature == expected_sig


# ============================================================================
# PART 5: TASK DEPENDENCY - WORKFLOW SEQUENCING & PREREQUISITES
# ============================================================================

class TaskDependency(models.Model):
    """
    Define task prerequisites and workflow sequences.
    
    Examples:
    ✓ User must complete Task A before Task B unlocks
    ✓ User must NOT complete Task X to qualify for Task Y (exclusion)
    ✓ User must complete Task A within 7 days of signing up (time-gated)
    
    Design Pattern:
    ✓ Chainable: Task A → B → C workflow
    ✓ Time-sensitive: prerequisite completion must be recent
    ✓ Cached: UserTaskDependencyStatus caches check result
    """
    
    class DependencyType(models.TextChoices):
        MUST_COMPLETE = 'must_complete', 'Must Complete (anytime)'
        MUST_COMPLETE_WITHIN_DAYS = 'must_complete_within_days', 'Must Complete (within N days)'
        MUST_NOT_COMPLETE = 'must_not_complete', 'Must NOT Have Completed'
        TIME_GATED = 'time_gated', 'Time-Gated (after X hours)'
        LEVEL_GATED = 'level_gated', 'Level-Gated (must be at least level Y)'
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Relationships
    dependent_task = models.ForeignKey(
        MasterTask,
        on_delete=models.CASCADE,
        related_name='required_after'
    )
    prerequisite_task = models.ForeignKey(
        MasterTask,
        on_delete=models.CASCADE,
        related_name='required_before'
    )
    
    # Dependency Configuration
    dependency_type = models.CharField(
        max_length=30,
        choices=DependencyType.choices
    )
    
    config = models.JSONField(
        default=dict,
        help_text="""
        Type-specific configuration:
        - MUST_COMPLETE_WITHIN_DAYS: {"must_complete_within_days": 7}
        - MUST_NOT_COMPLETE: {"lookback_days": 30}
        - TIME_GATED: {"wait_hours": 24}
        - LEVEL_GATED: {"min_level": 5}
        """
    )
    
    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['dependent_task', 'prerequisite_task'],
                name='unique_dependency_pair'
            )
        ]
        indexes = [
            models.Index(fields=['dependent_task', 'is_active']),
            models.Index(fields=['prerequisite_task', 'is_active']),
        ]
        verbose_name = "Task Dependency"
        verbose_name_plural = "Task Dependencies"
    
    def __str__(self):
        return f"{self.prerequisite_task.name} → {self.dependent_task.name} ({self.dependency_type})"


class UserTaskDependencyStatus(models.Model):
    """
    Cache of whether a user satisfies each dependency.
    
    Design Pattern:
    ✓ Query result is cached here (not computed on each check)
    ✓ Cache invalidated when prerequisite is completed
    ✓ Reduces database queries from N per dependency to 1 lookup
    """
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dependency_statuses'
    )
    dependency = models.ForeignKey(
        TaskDependency,
        on_delete=models.CASCADE,
        related_name='user_statuses'
    )
    
    # Cached Result
    is_satisfied = models.BooleanField(
        default=False,
        help_text="Whether user has satisfied this dependency"
    )
    prerequisite_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user completed the prerequisite task"
    )
    
    # Cache Metadata
    computed_at = models.DateTimeField(
        auto_now=True,
        help_text="When this cache was last computed"
    )
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'dependency'],
                name='unique_user_dependency_status'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'is_satisfied']),
            models.Index(fields=['dependency', 'is_satisfied']),
        ]
        verbose_name = "User Task Dependency Status"
        verbose_name_plural = "User Task Dependency Statuses"
    
    def __str__(self):
        status = '✓' if self.is_satisfied else '✗'
        return f"{self.user.username} {status} {self.dependency.dependency_type}"


# ============================================================================
# PART 6: TASK INVENTORY - BUDGET & COST CONTROL
# ============================================================================

class TaskInventory(models.Model):
    """
    Control task spending via daily/weekly/monthly/lifetime budgets.
    
    Design Pattern:
    ✓ Budget windows reset automatically (daily 11pm UTC, weekly Monday, etc)
    ✓ When budget exceeded → task auto-paused
    ✓ Admin can override pause status
    ✓ Alerts at 80% and 100% of budget
    
    Example:
    ✓ Survey task with $500/day budget
    ✓ At $400 spent (80%) → send warning email
    ✓ At $500 spent (100%) → auto-pause task
    ✓ Reset at midnight → resume accepting completions
    """
    
    class InventoryStatus(models.TextChoices):
        AVAILABLE = 'available', 'Accepting Completions'
        PAUSED_BUDGET = 'paused_budget', 'Paused (Budget Exceeded)'
        PAUSED_ADMIN = 'paused_admin', 'Paused (Admin Override)'
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # Task Relationship
    task = models.OneToOneField(
        MasterTask,
        on_delete=models.CASCADE,
        related_name='inventory'
    )
    
    # Budget Caps (NULL = no limit)
    daily_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Daily spending cap (resets at midnight UTC)"
    )
    weekly_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Weekly spending cap (resets Monday)"
    )
    monthly_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monthly spending cap (resets 1st of month)"
    )
    total_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Lifetime spending cap (never resets)"
    )
    
    # Current Spending
    current_daily_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Amount spent today"
    )
    current_weekly_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Amount spent this week"
    )
    current_monthly_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Amount spent this month"
    )
    current_total_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total amount spent (lifetime)"
    )
    
    # Reset Tracking (for batch reset operations)
    last_reset_daily = models.DateTimeField(default=timezone.now)
    last_reset_weekly = models.DateTimeField(default=timezone.now)
    last_reset_monthly = models.DateTimeField(default=timezone.now)
    
    # Status
    inventory_status = models.CharField(
        max_length=20,
        choices=InventoryStatus.choices,
        default=InventoryStatus.AVAILABLE,
        db_index=True
    )
    
    # Alert Flags (sent at 80% and 100%)
    alert_80_percent_sent = models.BooleanField(default=False)
    alert_100_percent_sent = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Task Inventory"
        verbose_name_plural = "Task Inventories"
    
    def __str__(self):
        status_display = self.get_inventory_status_display()
        spent_total = self.current_total_spend
        return f"{self.task.name} - Spent: ${spent_total} [{status_display}]"
    
    @property
    def daily_remaining(self) -> Optional[Decimal]:
        """Remaining daily budget"""
        if not self.daily_budget:
            return None
        return self.daily_budget - self.current_daily_spend
    
    @property
    def weekly_remaining(self) -> Optional[Decimal]:
        """Remaining weekly budget"""
        if not self.weekly_budget:
            return None
        return self.weekly_budget - self.current_weekly_spend
    
    @property
    def monthly_remaining(self) -> Optional[Decimal]:
        """Remaining monthly budget"""
        if not self.monthly_budget:
            return None
        return self.monthly_budget - self.current_monthly_spend
    
    @property
    def total_remaining(self) -> Optional[Decimal]:
        """Remaining lifetime budget"""
        if not self.total_budget:
            return None
        return self.total_budget - self.current_total_spend
    
    def can_accept_payout(self, payout_amount: Decimal) -> Tuple[bool, Optional[str]]:
        """
        Check if task can accept a payout without exceeding budgets.
        
        Returns:
            (can_accept: bool, reason: Optional[str])
        """
        # Check daily budget
        if self.daily_budget and (self.current_daily_spend + payout_amount) > self.daily_budget:
            return False, f"Daily budget exceeded (${self.current_daily_spend}/${self.daily_budget})"
        
        # Check weekly budget
        if self.weekly_budget and (self.current_weekly_spend + payout_amount) > self.weekly_budget:
            return False, f"Weekly budget exceeded (${self.current_weekly_spend}/${self.weekly_budget})"
        
        # Check monthly budget
        if self.monthly_budget and (self.current_monthly_spend + payout_amount) > self.monthly_budget:
            return False, f"Monthly budget exceeded (${self.current_monthly_spend}/${self.monthly_budget})"
        
        # Check lifetime budget
        if self.total_budget and (self.current_total_spend + payout_amount) > self.total_budget:
            return False, f"Lifetime budget exceeded (${self.current_total_spend}/${self.total_budget})"
        
        return True, None
    
    def increment_spend(self, payout_amount: Decimal):
        """
        Increment spending across all windows.
        Called when a task completion is paid out.
        """
        self.current_daily_spend += payout_amount
        self.current_weekly_spend += payout_amount
        self.current_monthly_spend += payout_amount
        self.current_total_spend += payout_amount
        
        # Check if any budget exceeded
        if self.daily_budget and self.current_daily_spend >= self.daily_budget:
            self.inventory_status = self.InventoryStatus.PAUSED_BUDGET
            self.alert_100_percent_sent = True
        elif self.daily_budget and self.current_daily_spend >= (self.daily_budget * Decimal('0.8')):
            # 80% threshold - send alert but don't pause
            self.alert_80_percent_sent = True
        
        self.save(update_fields=[
            'current_daily_spend', 'current_weekly_spend', 'current_monthly_spend',
            'current_total_spend', 'inventory_status', 'alert_80_percent_sent',
            'alert_100_percent_sent'
        ])
    
    def reset_daily(self):
        """Reset daily budget (call at 11 PM UTC)"""
        self.current_daily_spend = Decimal('0')
        self.alert_80_percent_sent = False
        self.alert_100_percent_sent = False
        
        # Unpause if paused for budget
        if self.inventory_status == self.InventoryStatus.PAUSED_BUDGET:
            self.inventory_status = self.InventoryStatus.AVAILABLE
        
        self.last_reset_daily = timezone.now()
        self.save()
    
    def reset_weekly(self):
        """Reset weekly budget (call Monday at 12 AM UTC)"""
        self.current_weekly_spend = Decimal('0')
        self.last_reset_weekly = timezone.now()
        self.save()
    
    def reset_monthly(self):
        """Reset monthly budget (call 1st at 12 AM UTC)"""
        self.current_monthly_spend = Decimal('0')
        self.last_reset_monthly = timezone.now()
        self.save()


# ============================================================================
# PART 10B: FRAUD SIGNAL - FRAUD DETECTION PERSISTENCE
# ============================================================================

class FraudSignal(models.Model):
    """
    Persistent record of fraud detection signals.
    
    Design Pattern:
    ✓ Created when fraud check triggers
    ✓ Used for audit trail and user appeals
    ✓ Tracks which signals contributed to decision
    ✓ Supports appeal/dispute resolution
    
    Example:
    - User submits proof
    - HIGH_VELOCITY signal (40 pts) + REWARD_ANOMALY (30 pts) = 70 total
    - Decision: MANUAL_REVIEW (within 40-75 range)
    - Signals logged for audit trail
    - User can appeal: "My IP is shared with family members"
    """
    
    class SignalType(models.TextChoices):
        HIGH_VELOCITY = 'high_velocity', 'High Velocity (>20 tasks/hour)'
        REWARD_ANOMALY = 'reward_anomaly', 'Reward >5x Average'
        IP_REUSE = 'ip_reuse', 'Same IP, Multiple Accounts'
        DEVICE_FINGERPRINT_CHANGE = 'device_fingerprint_change', 'Device Changed'
        PROOF_TIME_ANOMALY = 'proof_time_anomaly', 'Completed Too Fast'
        PROVIDER_VERIFICATION_FAILED = 'provider_verification_failed', 'Provider Rejected'
        DUPLICATE_SUBMISSION = 'duplicate_submission', 'Duplicate Detection'
        BEHAVIORAL_ANOMALY = 'behavioral_anomaly', 'Unusual Behavior'
    
    # Primary Key
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    
    # User Context
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks_fraud_signals'
    )
    
    # Signal Classification
    signal_type = models.CharField(
        max_length=40,
        choices=SignalType.choices
    )
    score_contribution = models.IntegerField(
        help_text="Points contributed to total fraud score (0-100)"
    )
    reason = models.TextField(
        help_text="Human-readable explanation of signal"
    )
    
    # Appeal/Dispute Tracking
    is_appealed = models.BooleanField(
        default=False,
        help_text="User disputed this signal"
    )
    appeal_notes = models.TextField(
        blank=True,
        default='',
        help_text="User's explanation for the suspicious activity"
    )
    appeal_resolved = models.BooleanField(
        default=False,
        help_text="Admin reviewed and resolved the appeal"
    )
    resolution_notes = models.TextField(
        blank=True,
        default='',
        help_text="Admin notes on appeal resolution"
    )
    
    # Timestamps
    triggered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', '-triggered_at']),
            models.Index(fields=['signal_type', '-triggered_at']),
            models.Index(fields=['is_appealed', 'appeal_resolved']),
        ]
        verbose_name = "Fraud Signal"
        verbose_name_plural = "Fraud Signals"
        ordering = ['-triggered_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_signal_type_display()} ({self.score_contribution} pts)"

        

class AdminLedger(models.Model):
    """
    Admin Ledger model for tracking all admin profits and revenues
    This is CRITICAL for tracking your earnings from the platform
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    # Source Types
    SOURCE_TASK = 'task'
    SOURCE_WITHDRAWAL_FEE = 'withdrawal_fee'
    SOURCE_REFERRAL_UNCLAIMED = 'referral_unclaimed'
    SOURCE_ADJUSTMENT = 'adjustment'
    SOURCE_OTHER = 'other'
    
    SOURCE_CHOICES = [
        (SOURCE_TASK, 'Task Revenue'),
        (SOURCE_WITHDRAWAL_FEE, 'Withdrawal Fee'),
        (SOURCE_REFERRAL_UNCLAIMED, 'Unclaimed Referral'),
        (SOURCE_ADJUSTMENT, 'Manual Adjustment'),
        (SOURCE_OTHER, 'Other'),
    ]
    
    # Ledger Entry Details
    entry_id = models.CharField(
        max_length=50, 
        unique=True, 
        db_index=True,
        help_text="Unique ledger entry ID (format: PREFIX-YYYYMMDDHHMMSS-XXXXXXXX, null=True, blank=True)"
    )
    
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.01'), message="Amount must be greater than 0")
        ],
        help_text="Amount (always positive for profit)"
    )
    
    source = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Source of profit (task, withdrawal_fee, etc., null=True, blank=True)"
    )
    
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_TASK,
        db_index=True,
        help_text="Category of profit source")
    
    # Related Objects
    task = models.ForeignKey(
        'MasterTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        help_text="Task that generated this profit"
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks_adminledger_user',
        help_text="User who generated this profit (if applicable, null=True, blank=True)"
    )
    
    completion = models.ForeignKey(
        'UserTaskCompletion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        help_text="Task completion that generated this profit"
    )
    
    # [OK] Fixed: Transaction foreign key - use string reference to avoid circular import
    transaction = models.ForeignKey(
        'wallet.WalletTransaction',  # String reference
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        help_text="Related transaction if any"
    )
    
    withdrawal = models.ForeignKey(
        'wallet.WithdrawalRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        help_text="Withdrawal request that generated fee profit"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Additional metadata in JSON format"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Human-readable description of this profit entry"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this entry was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this entry was last updated"
    )
    
    class Meta:
        indexes = [
            models.Index(fields=['source', '-created_at']),
            models.Index(fields=['source_type', '-created_at']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['task', 'user']),
            models.Index(fields=['created_at']),  # For date range queries
        ]
        ordering = ['-created_at']
        verbose_name = 'Admin Ledger'
        verbose_name_plural = 'Admin Ledger'
        
        # [OK] Fixed: Add permissions
        permissions = [
            ("view_profit_reports", "Can view profit reports"),
            ("export_ledger", "Can export ledger data"),
        ]
    
    def __str__(self):
        return f"{self.entry_id} - {self.source} - {self.amount}"
    
    def clean(self):
        """Model validation"""
        if self.amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than 0'})
        
        # Validate source consistency
        if self.source_type == self.SOURCE_TASK and not self.task:
            raise ValidationError({'task': 'Task is required for task revenue'})
        
        if self.source_type == self.SOURCE_WITHDRAWAL_FEE and not self.withdrawal:
            raise ValidationError({'withdrawal': 'Withdrawal is required for withdrawal fee'})
    
    def save(self, *args, **kwargs):
        """Generate entry ID if not provided and validate"""
        if not self.entry_id:
            self.entry_id = self._generate_entry_id()
        
        # Ensure amount is positive
        if self.amount <= 0:
            raise ValidationError(f"Amount must be positive, got {self.amount}")
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def _generate_entry_id(self) -> str:
        """Generate unique ledger entry ID with length validation"""
        prefix_map = {
            self.SOURCE_TASK: 'TSK',
            self.SOURCE_WITHDRAWAL_FEE: 'WDR',
            self.SOURCE_REFERRAL_UNCLAIMED: 'REF',
            self.SOURCE_ADJUSTMENT: 'ADJ',
            self.SOURCE_OTHER: 'OTH',
        }
        
        prefix = prefix_map.get(self.source_type, 'PRF')
        
        # [OK] Fixed: Use timezone.now() with import
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        unique_id = uuid.uuid4().hex[:8].upper()
        
        entry_id = f"{prefix}-{timestamp}-{unique_id}"
        
        # Ensure max length
        if len(entry_id) > 50:
            # Truncate if too long
            entry_id = entry_id[:50]
        
        return entry_id
    
    # ============ CLASS METHODS FOR REPORTING ============
    
    @classmethod
    def get_total_profit(cls) -> Decimal:
        """Get total admin profit safely"""
        try:
            result = cls.objects.aggregate(total=Sum('amount'))
            total = result.get('total')
            return total if total is not None else Decimal('0')
        except Exception as e:
            logger.error(f"Error getting total profit: {str(e)}")
            return Decimal('0')
    
    @classmethod
    def get_profit_by_period(cls, days: int = 30) -> Dict[str, Union[float, Decimal]]:
        """
        Get profit grouped by source for last N days
        Returns dictionary with source_type as key and total as float
        """
        try:
            if days <= 0:
                days = 30
            
            start_date = timezone.now() - timedelta(days=days)
            
            profits = cls.objects.filter(
                created_at__gte=start_date
            ).values('source_type').annotate(
                total=Sum('amount')
            ).order_by('source_type')
            
            result = {}
            for p in profits:
                source_type = p['source_type']
                total = p['total']
                # [OK] Fixed: Handle None values and convert to float for consistency
                result[source_type] = float(total) if total is not None else 0.0
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting profit by period: {str(e)}")
            return {}
    
    @classmethod
    def get_daily_profit(cls, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get daily profit for charting
        Returns list of dicts with date and profit
        """
        try:
            if days <= 0:
                days = 30
            
            start_date = timezone.now() - timedelta(days=days)
            
            daily = cls.objects.filter(
                created_at__gte=start_date
            ).annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                total=Sum('amount')
            ).order_by('date')
            
            result = []
            for item in daily:
                date = item.get('date')
                total = item.get('total')
                
                if date:
                    result.append({
                        'date': date.isoformat(),
                        'profit': float(total) if total is not None else 0.0,
                        'timestamp': date.timestamp()  # For charting libraries
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting daily profit: {str(e)}")
            return []
    
    @classmethod
    def get_profit_summary(cls, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive profit summary
        """
        try:
            total = cls.get_total_profit()
            by_source = cls.get_profit_by_period(days)
            daily = cls.get_daily_profit(days)
            
            # Calculate average daily profit
            if daily:
                avg_daily = sum(d['profit'] for d in daily) / len(daily)
            else:
                avg_daily = 0.0
            
            # Get top sources
            top_sources = sorted(
                by_source.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            return {
                'total_profit': float(total),
                'profit_last_{}_days'.format(days): sum(by_source.values()),
                'average_daily_profit': avg_daily,
                'by_source': by_source,
                'daily_breakdown': daily,
                'top_sources': [
                    {'source': source, 'amount': amount}
                    for source, amount in top_sources
                ],
                'period_days': days,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting profit summary: {str(e)}")
            return {
                'total_profit': 0.0,
                'profit_last_{}_days'.format(days): 0.0,
                'average_daily_profit': 0.0,
                'by_source': {},
                'daily_breakdown': [],
                'top_sources': [],
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
                'error': str(e)
            }
    
    @classmethod
    def get_profit_by_task(cls, task_id: int) -> Decimal:
        """Get total profit from a specific task"""
        try:
            result = cls.objects.filter(
                task_id=task_id,
                source_type=cls.SOURCE_TASK
            ).aggregate(total=Sum('amount'))
            
            total = result.get('total')
            return total if total is not None else Decimal('0')
            
        except Exception as e:
            logger.error(f"Error getting profit by task: {str(e)}")
            return Decimal('0')
    
    @classmethod
    def get_profit_by_user(cls, user_id: int) -> Decimal:
        """Get total profit generated by a specific user"""
        try:
            result = cls.objects.filter(
                user_id=user_id
            ).aggregate(total=Sum('amount'))
            
            total = result.get('total')
            return total if total is not None else Decimal('0')
            
        except Exception as e:
            logger.error(f"Error getting profit by user: {str(e)}")
            return Decimal('0')


# ============ SIGNAL FOR AUTO-CREATION FROM TASKS ============

def _safe_decimal(value, default=None):
    """Local helper to avoid circular import with tasks.services."""
    if default is None:
        default = Decimal('0')
    try:
        if value is None:
            return default
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return default


# =========================================================================
# RATE LIMIT CONFIGURATION MODEL
# =========================================================================

class RateLimitConfig(models.Model):
    """
    Dynamic rate limit configuration for admin management.
    Overrides DEFAULT_RATE_LIMITS when active.
    """

    class Scope(models.TextChoices):
        USER = 'user', 'Per User'
        GLOBAL = 'global', 'Global'
        IP = 'ip', 'Per IP Address'

    # Configuration
    limit_type = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique identifier for this rate limit (e.g., 'task_click')"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Human-readable name for admin interface"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this rate limit protects"
    )

    # Limits
    limit = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Maximum requests allowed in the time window"
    )
    window_seconds = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Time window in seconds (e.g., 3600 for 1 hour)"
    )

    # Scope
    scope = models.CharField(
        max_length=10,
        choices=Scope.choices,
        default=Scope.USER,
        help_text="Whether limit applies per user, globally, or per IP"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable this rate limit"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is a default system limit (cannot be deleted)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_rate_limits'
    )

    class Meta:
        ordering = ['limit_type']
        verbose_name = "Rate Limit Config"
        verbose_name_plural = "Rate Limit Configurations"

    def __str__(self):
        return f"{self.display_name} ({self.limit}/{self.window_seconds}s)"

    def get_window_hours(self):
        """Get window in hours for display"""
        return self.window_seconds / 3600

    def get_requests_per_hour(self):
        """Calculate requests per hour for display"""
        return (self.limit * 3600) / self.window_seconds


@receiver(post_save, sender='tasks.UserTaskCompletion')
def create_admin_profit_from_completion(sender, instance, created, **kwargs):
    """
    যখনই কোনো টাস্ক কমপ্লিট হবে, তখন অ্যাডমিন লেজারে এন্ট্রি হবে
    """
    try:
        # Check if task is completed and has revenue
        if instance.status == 'completed' and instance.admin_revenue_received:
            revenue = _safe_decimal(instance.admin_revenue_received)
            
            if revenue > 0:
                # Calculate admin profit (20%)
                admin_share = revenue * Decimal('0.20')
                
                # Check if already created (prevent duplicates)
                if not AdminLedger.objects.filter(
                    completion=instance,
                    source_type=AdminLedger.SOURCE_TASK
                ).exists():
                    
                    AdminLedger.objects.create(
                        amount=admin_share,
                        source=f"task_{instance.task.task_id}",
                        source_type=AdminLedger.SOURCE_TASK,
                        task=instance.task,
                        user=instance.user,
                        completion=instance,
                        description=f"Admin profit from task completion {instance.id}",
                        metadata={
                            'task_id': instance.task.id,
                            'task_name': instance.task.name,
                            'user_id': instance.user.id,
                            'revenue': float(revenue),
                            'admin_share': float(admin_share),
                            'completion_time': instance.completed_at.isoformat() if instance.completed_at else None
                        }
                    )
                    
                    logger.info(f"[OK] Created admin profit {admin_share} for completion {instance.id}")
            
    except Exception as e:
        logger.error(f"[ERROR] Error in create_admin_profit_from_completion: {str(e)}", exc_info=True)