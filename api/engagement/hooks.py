# engagement/hooks.py
"""
Hook system for engagement gamification.
Provides extensible hook points for custom logic.
"""
import logging
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class HookPoint(Enum):
    """Hook points in the engagement system."""
    BEFORE_CHECKIN = "before_checkin"
    AFTER_CHECKIN = "after_checkin"
    BEFORE_SPIN = "before_spin"
    AFTER_SPIN = "after_spin"
    BEFORE_QUEST_COMPLETE = "before_quest_complete"
    AFTER_QUEST_COMPLETE = "after_quest_complete"
    BEFORE_ACHIEVEMENT_UNLOCK = "before_achievement_unlock"
    AFTER_ACHIEVEMENT_UNLOCK = "after_achievement_unlock"
    BEFORE_LEVEL_UP = "before_level_up"
    AFTER_LEVEL_UP = "after_level_up"
    BEFORE_PURCHASE = "before_purchase"
    AFTER_PURCHASE = "after_purchase"
    BEFORE_REFERRAL = "before_referral"
    AFTER_REFERRAL = "after_referral"
    USER_REGISTERED = "user_registered"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    STREAK_BROKEN = "streak_broken"
    MILESTONE_REACHED = "milestone_reached"
    BATTLE_PASS_TIER_UP = "battle_pass_tier_up"
    GUILD_JOINED = "guild_joined"
    GUILD_LEFT = "guild_left"
    SEASONAL_EVENT_START = "seasonal_event_start"
    SEASONAL_EVENT_END = "seasonal_event_end"
    WEBHOOK_SENT = "webhook_sent"
    ANTI_CHEAT_DETECTED = "anti_cheat_detected"


@dataclass
class HookContext:
    """Context object passed to hook functions."""
    hook_point: HookPoint
    user_id: int
    tenant_id: Optional[int] = None
    data: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.metadata is None:
            self.metadata = {}


class HookResult:
    """Result object returned by hook functions."""
    
    def __init__(self, success: bool = True, data: Dict[str, Any] = None, 
                 modified_data: Dict[str, Any] = None, stop_execution: bool = False):
        self.success = success
        self.data = data or {}
        self.modified_data = modified_data or {}
        self.stop_execution = stop_execution


class HookManager:
    """Manages engagement hooks and their execution."""
    
    def __init__(self):
        self.hooks: Dict[HookPoint, List[Callable]] = {}
        self.global_hooks: List[Callable] = []
        self._setup_default_hooks()
    
    def _setup_default_hooks(self):
        """Setup default hooks."""
        # Register default analytics hook
        self.register_hook(HookPoint.BEFORE_CHECKIN, self._analytics_hook)
        self.register_hook(HookPoint.AFTER_CHECKIN, self._analytics_hook)
        self.register_hook(HookPoint.USER_REGISTERED, self._welcome_hook)
        self.register_hook(HookPoint.AFTER_LEVEL_UP, self._level_up_hook)
        self.register_hook(HookPoint.AFTER_ACHIEVEMENT_UNLOCK, self._achievement_hook)
    
    def register_hook(self, hook_point: HookPoint, hook_func: Callable, priority: int = 0):
        """Register a hook function for a specific hook point."""
        if hook_point not in self.hooks:
            self.hooks[hook_point] = []
        
        # Insert hook based on priority (higher priority = executed first)
        hook_info = {'func': hook_func, 'priority': priority}
        self.hooks[hook_point].append(hook_info)
        self.hooks[hook_point].sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"Hook registered: {hook_point.value} with priority {priority}")
    
    def register_global_hook(self, hook_func: Callable, priority: int = 0):
        """Register a global hook that runs for all hook points."""
        hook_info = {'func': hook_func, 'priority': priority}
        self.global_hooks.append(hook_info)
        self.global_hooks.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"Global hook registered with priority {priority}")
    
    def execute_hooks(self, hook_point: HookPoint, context: HookContext) -> HookResult:
        """Execute all hooks for a specific hook point."""
        result = HookResult()
        
        try:
            # Execute global hooks first
            for hook_info in self.global_hooks:
                hook_result = self._execute_hook(hook_info['func'], context)
                if not hook_result.success:
                    logger.error(f"Global hook failed: {hook_info['func'].__name__}")
                    result.success = False
                
                if hook_result.stop_execution:
                    logger.info(f"Global hook stopped execution: {hook_info['func'].__name__}")
                    result.stop_execution = True
                    break
                
                # Merge modified data
                result.modified_data.update(hook_result.modified_data)
            
            # Execute specific hooks
            if hook_point in self.hooks:
                for hook_info in self.hooks[hook_point]:
                    if result.stop_execution:
                        break
                    
                    hook_result = self._execute_hook(hook_info['func'], context)
                    if not hook_result.success:
                        logger.error(f"Hook failed for {hook_point.value}: {hook_info['func'].__name__}")
                        result.success = False
                    
                    if hook_result.stop_execution:
                        logger.info(f"Hook stopped execution: {hook_info['func'].__name__}")
                        result.stop_execution = True
                        break
                    
                    # Merge modified data
                    result.modified_data.update(hook_result.modified_data)
            
            logger.info(f"Hooks executed for {hook_point.value}: success={result.success}")
            
        except Exception as exc:
            logger.error(f"Error executing hooks for {hook_point.value}: {exc}")
            result.success = False
        
        return result
    
    def _execute_hook(self, hook_func: Callable, context: HookContext) -> HookResult:
        """Execute a single hook function."""
        try:
            result = hook_func(context)
            
            # Ensure result is a HookResult
            if not isinstance(result, HookResult):
                if isinstance(result, bool):
                    result = HookResult(success=result)
                elif isinstance(result, dict):
                    result = HookResult(success=True, data=result)
                else:
                    result = HookResult(success=True)
            
            return result
            
        except Exception as exc:
            logger.error(f"Hook function {hook_func.__name__} failed: {exc}")
            return HookResult(success=False)
    
    def remove_hook(self, hook_point: HookPoint, hook_func: Callable):
        """Remove a hook function."""
        if hook_point in self.hooks:
            self.hooks[hook_point] = [
                hook_info for hook_info in self.hooks[hook_point]
                if hook_info['func'] != hook_func
            ]
            logger.info(f"Hook removed: {hook_point.value}")
    
    def clear_hooks(self, hook_point: Optional[HookPoint] = None):
        """Clear hooks for a specific hook point or all hooks."""
        if hook_point:
            self.hooks[hook_point] = []
            logger.info(f"Hooks cleared for: {hook_point.value}")
        else:
            self.hooks.clear()
            self.global_hooks.clear()
            logger.info("All hooks cleared")
    
    def get_hook_count(self, hook_point: Optional[HookPoint] = None) -> int:
        """Get the number of registered hooks."""
        if hook_point:
            return len(self.hooks.get(hook_point, []))
        else:
            total = len(self.global_hooks)
            for hooks in self.hooks.values():
                total += len(hooks)
            return total
    
    # ── Default Hook Functions ───────────────────────────────────────────────
    
    def _analytics_hook(self, context: HookContext) -> HookResult:
        """Default analytics hook."""
        try:
            from .services.analytics_service import AnalyticsService
            
            AnalyticsService.record(
                user_id=context.user_id,
                event_type=f"hook_{context.hook_point.value}",
                properties=context.data,
                tenant_id=context.tenant_id
            )
            
            return HookResult(success=True)
            
        except Exception as exc:
            logger.error(f"Analytics hook failed: {exc}")
            return HookResult(success=False)
    
    def _welcome_hook(self, context: HookPoint) -> HookResult:
        """Default welcome hook for new users."""
        try:
            from .services.notification_service import NotificationService
            
            NotificationService.send(
                user_id=context.user_id,
                notification_type="welcome",
                title="Welcome to Engagement!",
                body="Get started with your first check-in and spin!",
                data={"tutorial_step": 1},
                tenant_id=context.tenant_id
            )
            
            return HookResult(success=True)
            
        except Exception as exc:
            logger.error(f"Welcome hook failed: {exc}")
            return HookResult(success=False)
    
    def _level_up_hook(self, context: HookPoint) -> HookResult:
        """Default level up hook."""
        try:
            from .services.notification_service import NotificationService
            
            old_level = context.data.get('old_level', 1)
            new_level = context.data.get('new_level', 2)
            
            NotificationService.send(
                user_id=context.user_id,
                notification_type="level_up",
                title=f"Level {new_level}!",
                body=f"Congratulations! You've reached level {new_level}.",
                data={"old_level": old_level, "new_level": new_level},
                tenant_id=context.tenant_id
            )
            
            return HookResult(success=True)
            
        except Exception as exc:
            logger.error(f"Level up hook failed: {exc}")
            return HookResult(success=False)
    
    def _achievement_hook(self, context: HookPoint) -> HookResult:
        """Default achievement hook."""
        try:
            from .services.notification_service import NotificationService
            
            achievement_name = context.data.get('achievement_name', 'Unknown')
            
            NotificationService.send(
                user_id=context.user_id,
                notification_type="achievement",
                title=f"🏆 {achievement_name} Unlocked!",
                body=f"Congratulations! You've unlocked {achievement_name}!",
                data=context.data,
                tenant_id=context.tenant_id
            )
            
            return HookResult(success=True)
            
        except Exception as exc:
            logger.error(f"Achievement hook failed: {exc}")
            return HookResult(success=False)


# Global hook manager instance
hook_manager = HookManager()


# ── Hook Decorators ───────────────────────────────────────────────────────

def hook(hook_point: HookPoint, priority: int = 0):
    """Decorator to register a hook function."""
    def decorator(func):
        hook_manager.register_hook(hook_point, func, priority)
        return func
    return decorator


def global_hook(priority: int = 0):
    """Decorator to register a global hook function."""
    def decorator(func):
        hook_manager.register_global_hook(func, priority)
        return func
    return decorator


# ── Hook Execution Functions ─────────────────────────────────────────────────

def execute_hooks(hook_point: HookPoint, user_id: int, **data) -> HookResult:
    """Execute hooks for a specific hook point."""
    context = HookContext(
        hook_point=hook_point,
        user_id=user_id,
        data=data,
        tenant_id=data.get('tenant_id')
    )
    return hook_manager.execute_hooks(hook_point, context)


def execute_hooks_with_context(context: HookContext) -> HookResult:
    """Execute hooks with a pre-built context."""
    return hook_manager.execute_hooks(context.hook_point, context)


# ── Custom Hook Examples ───────────────────────────────────────────────────

@hook(HookPoint.BEFORE_CHECKIN, priority=100)
def checkin_validation_hook(context: HookContext) -> HookResult:
    """Hook to validate check-in data before processing."""
    try:
        # Check if user can check in today
        from .models.checkin import DailyCheckIn
        from datetime import date
        
        today = date.today()
        if DailyCheckIn.objects.filter(user_id=context.user_id, date=today).exists():
            return HookResult(success=False, stop_execution=True)
        
        return HookResult(success=True)
        
    except Exception as exc:
        logger.error(f"Checkin validation hook failed: {exc}")
        return HookResult(success=False)


@hook(HookPoint.AFTER_CHECKIN, priority=100)
def checkin_reward_hook(context: HookContext) -> HookResult:
    """Hook to grant additional rewards after check-in."""
    try:
        streak = context.data.get('streak', 1)
        
        # Grant bonus coins for streak milestones
        if streak in [7, 14, 30, 50, 100]:
            bonus_coins = streak * 10
            context.data['bonus_coins'] = bonus_coins
            
            return HookResult(
                success=True,
                modified_data={'bonus_coins': bonus_coins}
            )
        
        return HookResult(success=True)
        
    except Exception as exc:
        logger.error(f"Checkin reward hook failed: {exc}")
        return HookResult(success=False)


@hook(HookPoint.BEFORE_SPIN, priority=100)
def spin_limit_hook(context: HookContext) -> HookResult:
    """Hook to check spin limits before processing."""
    try:
        from .models.spinwheel import SpinWheel
        from .constants import SPIN_MAX_PER_DAY
        from datetime import date
        
        today = date.today()
        spins_today = SpinWheel.objects.filter(
            user_id=context.user_id,
            spun_at__date=today
        ).count()
        
        if spins_today >= SPIN_MAX_PER_DAY:
            return HookResult(success=False, stop_execution=True)
        
        return HookResult(success=True)
        
    except Exception as exc:
        logger.error(f"Spin limit hook failed: {exc}")
        return HookResult(success=False)


@hook(HookPoint.AFTER_SPIN, priority=100)
def spin_analytics_hook(context: HookContext) -> HookResult:
    """Hook to record spin analytics."""
    try:
        coins_won = context.data.get('coins_won', 0)
        
        # Record big wins
        if coins_won >= 100:
            context.data['is_big_win'] = True
            
            return HookResult(
                success=True,
                modified_data={'is_big_win': True}
            )
        
        return HookResult(success=True)
        
    except Exception as exc:
        logger.error(f"Spin analytics hook failed: {exc}")
        return HookResult(success=False)


@hook(HookPoint.USER_REGISTERED, priority=200)
def referral_setup_hook(context: HookContext) -> HookResult:
    """Hook to setup referral system for new users."""
    try:
        # Generate referral code for new user
        import random
        import string
        
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        context.data['referral_code'] = referral_code
        
        return HookResult(
            success=True,
            modified_data={'referral_code': referral_code}
        )
        
    except Exception as exc:
        logger.error(f"Referral setup hook failed: {exc}")
        return HookResult(success=False)


@hook(HookPoint.AFTER_PURCHASE, priority=100)
def purchase_analytics_hook(context: HookContext) -> HookResult:
    """Hook to record purchase analytics."""
    try:
        item_type = context.data.get('item_type', 'unknown')
        coins_spent = context.data.get('coins_spent', 0)
        
        # Track spending patterns
        if coins_spent >= 1000:
            context.data['is_big_spender'] = True
            
            return HookResult(
                success=True,
                modified_data={'is_big_spender': True}
            )
        
        return HookResult(success=True)
        
    except Exception as exc:
        logger.error(f"Purchase analytics hook failed: {exc}")
        return HookResult(success=False)


@global_hook(priority=50)
def logging_hook(context: HookPoint) -> HookResult:
    """Global hook to log all hook executions."""
    try:
        logger.info(
            f"Hook executed: {context.hook_point.value} for user {context.user_id}"
        )
        return HookResult(success=True)
        
    except Exception as exc:
        logger.error(f"Logging hook failed: {exc}")
        return HookResult(success=False)


@global_hook(priority=100)
def performance_hook(context: HookPoint) -> HookResult:
    """Global hook to monitor performance."""
    try:
        import time
        
        start_time = context.metadata.get('start_time', time.time())
        execution_time = time.time() - start_time
        
        if execution_time > 1.0:  # Log slow operations
            logger.warning(
                f"Slow hook execution: {context.hook_point.value} took {execution_time:.2f}s"
            )
        
        return HookResult(success=True)
        
    except Exception as exc:
        logger.error(f"Performance hook failed: {exc}")
        return HookResult(success=False)


# ── Hook Management Functions ─────────────────────────────────────────────

def register_custom_hook(hook_point: HookPoint, hook_func: Callable, priority: int = 0):
    """Register a custom hook."""
    hook_manager.register_hook(hook_point, hook_func, priority)


def remove_custom_hook(hook_point: HookPoint, hook_func: Callable):
    """Remove a custom hook."""
    hook_manager.remove_hook(hook_point, hook_func)


def get_hook_statistics() -> Dict[str, Any]:
    """Get statistics about registered hooks."""
    stats = {
        'total_hooks': hook_manager.get_hook_count(),
        'global_hooks': len(hook_manager.global_hooks),
        'hook_points': {}
    }
    
    for hook_point in HookPoint:
        count = hook_manager.get_hook_count(hook_point)
        if count > 0:
            stats['hook_points'][hook_point.value] = count
    
    return stats


def clear_all_hooks():
    """Clear all registered hooks."""
    hook_manager.clear_hooks()
