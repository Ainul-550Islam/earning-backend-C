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
    task_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    
    # Categorization
    system_type = models.CharField(
        max_length=20, 
        choices=SystemType.choices,
        db_index=True
    )
    category = models.CharField(
        max_length=20, 
        choices=TaskCategory.choices,
        db_index=True
    )
    
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
        Validate task metadata based on system type
        Returns dictionary of errors
        """
        errors = {}
        
        if not self.task_metadata:
            errors['task_metadata'] = "Task metadata cannot be empty"
            return errors
        
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
        
        return errors
    
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
        wall_providers = ['adgem', 'offertoro', 'fyber', 'pollfish', 'bitlabs']
        
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


class UserTaskCompletion(models.Model):
    """
    Track user task completions with proper ForeignKey to User model
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
        db_index=True
    )
    task = models.ForeignKey(
        MasterTask, 
        on_delete=models.CASCADE, 
        related_name='%(app_label)s_%(class)s_tenant'
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
    admin_revenue_received = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    
    class Meta:
        unique_together = ['user', 'task', 'started_at']
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
        help_text="Unique ledger entry ID (format: PREFIX-YYYYMMDDHHMMSS-XXXXXXXX)"
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
        help_text="Source of profit (task, withdrawal_fee, etc.)"
    )
    
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_TASK,
        db_index=True,
        help_text="Category of profit source"
    )
    
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
        help_text="User who generated this profit (if applicable)"
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