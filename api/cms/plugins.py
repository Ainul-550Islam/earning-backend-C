# api/cms/plugins.py
"""CMS Plugin system — extend CMS without modifying core code."""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
from django.utils import timezone

logger = logging.getLogger(__name__)


class CMSPlugin(ABC):
    """Base class for all CMS plugins."""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.version = getattr(self, 'version', '1.0.0')
        self.description = getattr(self, 'description', '')
        self.author = getattr(self, 'author', '')
        self.enabled = True
        self.config = {}
        
    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None):
        """Initialize plugin with configuration."""
        pass
    
    @abstractmethod
    def activate(self):
        """Activate plugin."""
        pass
    
    @abstractmethod
    def deactivate(self):
        """Deactivate plugin."""
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'enabled': self.enabled,
            'initialized': hasattr(self, '_initialized')
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        return True
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema for this plugin."""
        return {}


# ── Survey Plugins ─────────────────────────────────────────────

class SurveyAnalyticsPlugin(CMSPlugin):
    """Plugin for advanced survey analytics."""
    
    version = '1.0.0'
    description = 'Advanced survey analytics and reporting'
    author = 'CMS Team'
    
    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.analytics_enabled = self.config.get('analytics_enabled', True)
        self.report_interval = self.config.get('report_interval', 3600)  # 1 hour
        
    def activate(self):
        """Activate survey analytics."""
        if self.analytics_enabled:
            # Register hooks
            from .hooks import CMSHooks
            CMSHooks.on('survey_completed', self.on_survey_completed)
            CMSHooks.on('survey_started', self.on_survey_started)
            logger.info(f"[{self.name}] Survey analytics activated")
    
    def deactivate(self):
        """Deactivate survey analytics."""
        logger.info(f"[{self.name}] Survey analytics deactivated")
    
    def on_survey_completed(self, user, survey, completion, quality_score):
        """Handle survey completion."""
        # Track completion metrics
        logger.info(f"[{self.name}] Survey completed: {survey.title} by {user.username}")
        
        # Could integrate with external analytics service
        # self.send_to_analytics_service('survey_completed', {
        #     'user_id': user.id,
        #     'survey_id': survey.id,
        #     'quality_score': quality_score,
        #     'completion_time': completion.completed_at
        # })
    
    def on_survey_started(self, user, survey, completion):
        """Handle survey start."""
        logger.info(f"[{self.name}] Survey started: {survey.title} by {user.username}")


class SurveyQualityPlugin(CMSPlugin):
    """Plugin for survey quality assessment."""
    
    version = '1.0.0'
    description = 'Advanced survey quality assessment algorithms'
    author = 'CMS Team'
    
    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.quality_threshold = self.config.get('quality_threshold', 0.7)
        self.time_factor_weight = self.config.get('time_factor_weight', 0.3)
        self.consistency_weight = self.config.get('consistency_weight', 0.4)
        self.completeness_weight = self.config.get('completeness_weight', 0.3)
        
    def activate(self):
        """Activate survey quality assessment."""
        from .hooks import CMSHooks
        CMSHooks.on('survey_response_submitted', self.on_survey_response_submitted)
        CMSHooks.filter('survey_quality_calculation', self.calculate_quality)
        logger.info(f"[{self.name}] Survey quality assessment activated")
    
    def deactivate(self):
        """Deactivate survey quality assessment."""
        logger.info(f"[{self.name}] Survey quality assessment deactivated")
    
    def on_survey_response_submitted(self, user, survey, responses, completion):
        """Handle survey response submission."""
        # Analyze response patterns
        quality_metrics = self._analyze_responses(responses, survey)
        logger.info(f"[{self.name}] Analyzed responses: quality_score={quality_metrics['score']:.2f}")
    
    def calculate_quality(self, base_quality, survey, responses, context):
        """Calculate enhanced quality score."""
        # Apply custom quality calculation logic
        time_factor = self._calculate_time_factor(context)
        consistency_factor = self._calculate_consistency_factor(responses)
        completeness_factor = self._calculate_completeness_factor(responses, survey)
        
        enhanced_quality = (
            base_quality * 0.5 +
            time_factor * self.time_factor_weight +
            consistency_factor * self.consistency_weight +
            completeness_factor * self.completeness_weight
        )
        
        return {'quality_score': min(enhanced_quality, 1.0)}
    
    def _analyze_responses(self, responses, survey):
        """Analyze response patterns."""
        return {
            'score': 0.8,  # Placeholder
            'time_consistency': 0.9,
            'answer_consistency': 0.7,
            'completeness': 0.95
        }
    
    def _calculate_time_factor(self, context):
        """Calculate time-based quality factor."""
        return 0.8  # Placeholder
    
    def _calculate_consistency_factor(self, responses):
        """Calculate response consistency factor."""
        return 0.7  # Placeholder
    
    def _calculate_completeness_factor(self, responses, survey):
        """Calculate response completeness factor."""
        return 0.9  # Placeholder


# ── Reward Plugins ─────────────────────────────────────────────

class RewardCalculationPlugin(CMSPlugin):
    """Plugin for custom reward calculation logic."""
    
    version = '1.0.0'
    description = 'Custom reward calculation algorithms'
    author = 'CMS Team'
    
    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.multiplier = self.config.get('multiplier', 1.0)
        self.bonus_threshold = self.config.get('bonus_threshold', 10)
        self.bonus_amount = self.config.get('bonus_amount', 0.5)
        
    def activate(self):
        """Activate reward calculation plugin."""
        from .hooks import CMSHooks
        CMSHooks.filter('survey_reward_calculation', self.calculate_reward)
        CMSHooks.on('reward_earned', self.on_reward_earned)
        logger.info(f"[{self.name}] Reward calculation activated")
    
    def deactivate(self):
        """Deactivate reward calculation plugin."""
        logger.info(f"[{self.name}] Reward calculation deactivated")
    
    def calculate_reward(self, base_reward, user, survey, quality_score):
        """Custom reward calculation logic."""
        # Apply multiplier
        adjusted_reward = base_reward * self.multiplier
        
        # Apply bonus for high quality
        if quality_score >= 0.9:
            adjusted_reward += self.bonus_amount
        
        # Apply loyalty bonus
        user_completions = getattr(user, 'survey_completions_count', 0)
        if user_completions >= self.bonus_threshold:
            adjusted_reward *= 1.1  # 10% loyalty bonus
        
        return {'base_reward': adjusted_reward}
    
    def on_reward_earned(self, user, transaction, amount, source_type):
        """Handle reward earned event."""
        logger.info(f"[{self.name}] Reward earned: ${amount:.2f} by {user.username} from {source_type}")


class RewardPoolPlugin(CMSPlugin):
    """Plugin for reward pool management."""
    
    version = '1.0.0'
    description = 'Advanced reward pool management and monitoring'
    author = 'CMS Team'
    
    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.auto_refill = self.config.get('auto_refill', True)
        self.low_balance_threshold = self.config.get('low_balance_threshold', 100)
        self.refill_amount = self.config.get('refill_amount', 500)
        
    def activate(self):
        """Activate reward pool management."""
        from .hooks import CMSHooks
        CMSHooks.on('reward_pool_low', self.on_pool_low)
        CMSHooks.on('reward_transaction_created', self.on_transaction_created)
        logger.info(f"[{self.name}] Reward pool management activated")
    
    def deactivate(self):
        """Deactivate reward pool management."""
        logger.info(f"[{self.name}] Reward pool management deactivated")
    
    def on_pool_low(self, pool, utilization_percentage, remaining_amount):
        """Handle low pool balance."""
        if self.auto_refill and remaining_amount < self.low_balance_threshold:
            logger.info(f"[{self.name}] Auto-refilling pool {pool.name} with ${self.refill_amount}")
            # Would trigger pool refill logic here
    
    def on_transaction_created(self, user, transaction, amount, transaction_type, status):
        """Handle transaction creation."""
        logger.info(f"[{self.name}] Transaction created: {transaction_type} ${amount:.2f} for {user.username}")


# ── Task Management Plugins ─────────────────────────────────────

class TaskAutomationPlugin(CMSPlugin):
    """Plugin for task automation and scheduling."""
    
    version = '1.0.0'
    description = 'Automated task management and scheduling'
    author = 'CMS Team'
    
    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.auto_cleanup = self.config.get('auto_cleanup', True)
        self.cleanup_interval = self.config.get('cleanup_interval', 86400)  # 24 hours
        self.auto_retry = self.config.get('auto_retry', True)
        self.max_retries = self.config.get('max_retries', 3)
        
    def activate(self):
        """Activate task automation."""
        from .hooks import CMSHooks
        CMSHooks.on('task_failed', self.on_task_failed)
        CMSHooks.on('task_completed', self.on_task_completed)
        CMSHooks.on('task_started', self.on_task_started)
        logger.info(f"[{self.name}] Task automation activated")
    
    def deactivate(self):
        """Deactivate task automation."""
        logger.info(f"[{self.name}] Task automation deactivated")
    
    def on_task_failed(self, task, execution, error_message, retry_count):
        """Handle task failure."""
        if self.auto_retry and retry_count < self.max_retries:
            logger.info(f"[{self.name}] Auto-retrying task {task.task_name} (attempt {retry_count + 1})")
            
            # Schedule retry
            # This would integrate with task scheduling system
            # schedule_task_retry(str(task.uuid), retry_count + 1)
    
    def on_task_completed(self, task, execution, runtime_seconds, success):
        """Handle task completion."""
        if success:
            logger.info(f"[{self.name}] Task {task.task_name} completed successfully in {runtime_seconds:.2f}s")
        else:
            logger.warning(f"[{self.name}] Task {task.task_name} completed with issues")
    
    def on_task_started(self, task, execution, worker_id):
        """Handle task start."""
        logger.info(f"[{self.name}] Task {task.task_name} started by worker {worker_id}")


class TaskMonitoringPlugin(CMSPlugin):
    """Plugin for task monitoring and alerting."""
    
    version = '1.0.0'
    description = 'Task monitoring and performance alerting'
    author = 'CMS Team'
    
    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.performance_threshold = self.config.get('performance_threshold', 300)  # 5 minutes
        self.alert_on_failure = self.config.get('alert_on_failure', True)
        self.alert_on_timeout = self.config.get('alert_on_timeout', True)
        
    def activate(self):
        """Activate task monitoring."""
        from .hooks import CMSHooks
        CMSHooks.on('task_started', self.on_task_started)
        CMSHooks.on('task_failed', self.on_task_failed)
        CMSHooks.on('task_timeout', self.on_task_timeout)
        logger.info(f"[{self.name}] Task monitoring activated")
    
    def deactivate(self):
        """Deactivate task monitoring."""
        logger.info(f"[{self.name}] Task monitoring deactivated")
    
    def on_task_started(self, task, execution, worker_id):
        """Monitor task start."""
        # Record start time for performance monitoring
        logger.info(f"[{self.name}] Monitoring task {task.task_name} started at {execution.started_at}")
    
    def on_task_failed(self, task, execution, error_message, retry_count):
        """Alert on task failure."""
        if self.alert_on_failure:
            logger.warning(f"[{self.name}] ALERT: Task {task.task_name} failed: {error_message}")
            # Would send alert notification
    
    def on_task_timeout(self, task, execution, timeout_duration):
        """Alert on task timeout."""
        if self.alert_on_timeout:
            logger.warning(f"[{self.name}] ALERT: Task {task.task_name} timed out after {timeout_duration}s")
            # Would send alert notification


# ── User Profile Plugins ─────────────────────────────────────────

class UserProfilePlugin(CMSPlugin):
    """Plugin for enhanced user profile management."""
    
    version = '1.0.0'
    description = 'Enhanced user profile management and validation'
    author = 'CMS Team'
    
    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.auto_segment = self.config.get('auto_segment', True)
        self.profile_validation = self.config.get('profile_validation', True)
        
    def activate(self):
        """Activate user profile enhancements."""
        from .hooks import CMSHooks
        CMSHooks.on('profile_updated', self.on_profile_updated)
        CMSHooks.on('user_registered', self.on_user_registered)
        CMSHooks.filter('user_profile_validation', self.validate_profile)
        logger.info(f"[{self.name}] User profile enhancements activated")
    
    def deactivate(self):
        """Deactivate user profile enhancements."""
        logger.info(f"[{self.name}] User profile enhancements deactivated")
    
    def on_profile_updated(self, user, profile, changed_fields):
        """Handle profile update."""
        if self.auto_segment:
            self._update_user_segments(user, profile)
        
        logger.info(f"[{self.name}] Profile updated for {user.username}: {changed_fields}")
    
    def on_user_registered(self, user, registration_method):
        """Handle user registration."""
        if self.auto_segment:
            self._assign_initial_segments(user)
        
        logger.info(f"[{self.name}] User registered: {user.username} via {registration_method}")
    
    def validate_profile(self, profile_data, context):
        """Enhanced profile validation."""
        validation_result = {'valid': True, 'errors': []}
        
        # Add custom validation logic
        if self.profile_validation:
            # Check for required fields
            required_fields = ['first_name', 'last_name', 'email']
            for field in required_fields:
                if not profile_data.get(field):
                    validation_result['errors'].append(f'{field} is required')
                    validation_result['valid'] = False
        
        return validation_result
    
    def _update_user_segments(self, user, profile):
        """Update user segments based on profile."""
        # Would implement segment assignment logic
        pass
    
    def _assign_initial_segments(self, user):
        """Assign initial segments to new user."""
        # Would implement initial segment assignment
        pass


# ── Notification Plugins ─────────────────────────────────────

class NotificationPlugin(CMSPlugin):
    """Plugin for enhanced notifications."""
    
    version = '1.0.0'
    description = 'Enhanced notification system with multiple channels'
    author = 'CMS Team'
    
    def initialize(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.channels = self.config.get('channels', ['email', 'push'])
        self.email_enabled = 'email' in self.channels
        self.push_enabled = 'push' in self.channels
        
    def activate(self):
        """Activate notification enhancements."""
        from .hooks import CMSHooks
        CMSHooks.on('notification_created', self.on_notification_created)
        CMSHooks.on('reward_earned', self.on_reward_earned)
        CMSHooks.on('survey_completed', self.on_survey_completed)
        logger.info(f"[{self.name}] Notification enhancements activated")
    
    def deactivate(self):
        """Deactivate notification enhancements."""
        logger.info(f"[{self.name}] Notification enhancements deactivated")
    
    def on_notification_created(self, user, notification, recipients):
        """Handle notification creation."""
        if self.email_enabled:
            self._send_email_notification(user, notification)
        
        if self.push_enabled:
            self._send_push_notification(user, notification)
    
    def on_reward_earned(self, user, transaction, amount, source_type):
        """Handle reward earned notification."""
        notification_data = {
            'title': 'Reward Earned!',
            'message': f'You earned ${amount:.2f} from {source_type}',
            'type': 'reward'
        }
        
        # Create notification
        from .models_new.notifications import Notification
        notification = Notification.objects.create(
            user=user,
            title=notification_data['title'],
            message=notification_data['message'],
            type=notification_data['type'],
            data={'transaction_id': str(transaction.uuid)}
        )
        
        # Send notification
        self.on_notification_created(user, notification, [user])
    
    def on_survey_completed(self, user, survey, completion, quality_score):
        """Handle survey completion notification."""
        notification_data = {
            'title': 'Survey Completed!',
            'message': f'You completed "{survey.title}" with quality score {quality_score:.1%}',
            'type': 'survey'
        }
        
        # Create notification
        from .models_new.notifications import Notification
        notification = Notification.objects.create(
            user=user,
            title=notification_data['title'],
            message=notification_data['message'],
            type=notification_data['type'],
            data={'completion_id': str(completion.uuid)}
        )
        
        # Send notification
        self.on_notification_created(user, notification, [user])
    
    def _send_email_notification(self, user, notification):
        """Send email notification."""
        # Implementation would depend on email service
        logger.info(f"[{self.name}] Email notification sent to {user.email}: {notification.title}")
    
    def _send_push_notification(self, user, notification):
        """Send push notification."""
        # Implementation would depend on push service
        logger.info(f"[{self.name}] Push notification sent to {user.username}: {notification.title}")


# ── Plugin Registry (Enhanced) ─────────────────────────────────

class PluginRegistry:
    """Registry for CMS plugins."""
    _plugins: dict = {}
    _enabled: set = set()
    _hooks: dict = {}

    @classmethod
    def register(cls, plugin: CMSPlugin):
        cls._plugins[plugin.name] = plugin
        logger.info(f"[Plugin] Registered: {plugin.name} v{plugin.version}")

    @classmethod
    def enable(cls, name: str) -> bool:
        plugin = cls._plugins.get(name)
        if not plugin:
            return False
        try:
            plugin.activate()
            cls._enabled.add(name)
            return True
        except Exception as e:
            logger.error(f"[Plugin] Enable failed for {name}: {e}")
            return False

    @classmethod
    def disable(cls, name: str) -> bool:
        plugin = cls._plugins.get(name)
        if not plugin:
            return False
        try:
            plugin.on_disable()
            cls._enabled.discard(name)
            return True
        except Exception as e:
            logger.error(f"[Plugin] Disable failed for {name}: {e}")
            return False

    @classmethod
    def get(cls, name: str):
        return cls._plugins.get(name)

    @classmethod
    def is_enabled(cls, name: str) -> bool:
        return name in cls._enabled

    @classmethod
    def all_plugins(cls) -> dict:
        return {
            name: {
                'version': p.version,
                'description': p.description,
                'enabled': name in cls._enabled,
            }
            for name, p in cls._plugins.items()
        }


# ── Built-in Plugins ──────────────────────────────────────────────

class ReferralPlugin(CMSPlugin):
    name = 'referral'
    version = '1.0.0'
    description = 'CPAlead 5% referral bonus system'

    def register_hooks(self):
        from api.cms.hooks import CMSHooks
        def on_offer_completed(user, amount, lead_id='', **kwargs):
            try:
                from api.cms.services_new.ReferralService import ReferralService
                from decimal import Decimal
                ReferralService.award_referral_bonus(user, Decimal(str(amount)), lead_id=lead_id)
            except Exception as e:
                logger.warning(f"[ReferralPlugin] {e}")
        CMSHooks.on('offer_completed', on_offer_completed, priority=20)


class LeaderboardPlugin(CMSPlugin):
    name = 'leaderboard'
    version = '1.0.0'
    description = 'Weekly/monthly leaderboard with streak bonuses'

    def register_hooks(self):
        from api.cms.hooks import CMSHooks
        def on_reward_earned(user, amount, currency='USD', **kwargs):
            try:
                from api.cms.services_new.LeaderboardService import LeaderboardService, StreakService
                from decimal import Decimal
                LeaderboardService.update_score(user, Decimal(str(amount)), 'earnings', 'weekly')
                StreakService.record_earn(user)
            except Exception as e:
                logger.warning(f"[LeaderboardPlugin] {e}")
        CMSHooks.on('reward_earned', on_reward_earned, priority=10)


# Auto-register built-in plugins
PluginRegistry.register(ReferralPlugin())
PluginRegistry.register(LeaderboardPlugin())
