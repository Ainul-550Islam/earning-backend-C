# engagement/events.py
"""
Event system for engagement gamification.
Defines custom events and event handling logic.
"""
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

from .services.analytics_service import AnalyticsService
from .services.notification_service import NotificationService
from .services.gamification_engine import GamificationEngine

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for engagement system."""
    USER_REGISTERED = "user_registered"
    CHECKIN_COMPLETED = "checkin_completed"
    SPIN_COMPLETED = "spin_completed"
    QUEST_COMPLETED = "quest_completed"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    LEVEL_UP = "level_up"
    PURCHASE_COMPLETED = "purchase_completed"
    REFERRAL_COMPLETED = "referral_completed"
    SOCIAL_INTERACTION = "social_interaction"
    STREAK_BROKEN = "streak_broken"
    MILESTONE_REACHED = "milestone_reached"
    BATTLE_PASS_TIER_UP = "battle_pass_tier_up"
    GUILD_JOINED = "guild_joined"
    SEASONAL_EVENT_COMPLETED = "seasonal_event_completed"
    WEBHOOK_TRIGGERED = "webhook_triggered"
    ANTI_CHEAT_DETECTED = "anti_cheat_detected"


@dataclass
class EngagementEvent:
    """Base engagement event class."""
    event_type: EventType
    user_id: int
    tenant_id: Optional[int] = None
    timestamp: datetime = None
    properties: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.properties is None:
            self.properties = {}
        if self.metadata is None:
            self.metadata = {}


class EventManager:
    """Manages engagement events and their handling."""
    
    def __init__(self):
        self.event_handlers = {}
        self.event_queue = []
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Setup default event handlers."""
        self.register_handler(EventType.USER_REGISTERED, self._handle_user_registered)
        self.register_handler(EventType.CHECKIN_COMPLETED, self._handle_checkin_completed)
        self.register_handler(EventType.SPIN_COMPLETED, self._handle_spin_completed)
        self.register_handler(EventType.QUEST_COMPLETED, self._handle_quest_completed)
        self.register_handler(EventType.ACHIEVEMENT_UNLOCKED, self._handle_achievement_unlocked)
        self.register_handler(EventType.LEVEL_UP, self._handle_level_up)
        self.register_handler(EventType.PURCHASE_COMPLETED, self._handle_purchase_completed)
        self.register_handler(EventType.REFERRAL_COMPLETED, self._handle_referral_completed)
        self.register_handler(EventType.SOCIAL_INTERACTION, self._handle_social_interaction)
        self.register_handler(EventType.STREAK_BROKEN, self._handle_streak_broken)
        self.register_handler(EventType.MILESTONE_REACHED, self._handle_milestone_reached)
        self.register_handler(EventType.BATTLE_PASS_TIER_UP, self._handle_battle_pass_tier_up)
        self.register_handler(EventType.GUILD_JOINED, self._handle_guild_joined)
        self.register_handler(EventType.SEASONAL_EVENT_COMPLETED, self._handle_seasonal_event_completed)
        self.register_handler(EventType.WEBHOOK_TRIGGERED, self._handle_webhook_triggered)
        self.register_handler(EventType.ANTI_CHEAT_DETECTED, self._handle_anti_cheat_detected)
    
    def register_handler(self, event_type: EventType, handler_func):
        """Register an event handler."""
        self.event_handlers[event_type] = handler_func
    
    def emit_event(self, event: EngagementEvent):
        """Emit an engagement event."""
        try:
            # Add to queue for processing
            self.event_queue.append(event)
            
            # Process immediately
            self._process_event(event)
            
            # Record analytics
            self._record_event_analytics(event)
            
            logger.info(f"Event emitted: {event.event_type.value} for user {event.user_id}")
            
        except Exception as exc:
            logger.error(f"Failed to emit event {event.event_type.value}: {exc}")
    
    def _process_event(self, event: EngagementEvent):
        """Process a single event."""
        handler = self.event_handlers.get(event.event_type)
        if handler:
            try:
                handler(event)
            except Exception as exc:
                logger.error(f"Event handler failed for {event.event_type.value}: {exc}")
    
    def _record_event_analytics(self, event: EngagementEvent):
        """Record event analytics."""
        try:
            # This would record to analytics service
            AnalyticsService.record(
                user_id=event.user_id,
                event_type=event.event_type.value,
                properties=event.properties,
                tenant_id=event.tenant_id
            )
        except Exception as exc:
            logger.error(f"Failed to record event analytics: {exc}")
    
    # ── Event Handlers ───────────────────────────────────────────────────────
    
    def _handle_user_registered(self, event: EngagementEvent):
        """Handle user registration event."""
        try:
            # Send welcome notification
            NotificationService.send(
                user_id=event.user_id,
                notification_type="welcome",
                title="Welcome to Engagement!",
                body="Get started with your first check-in and spin!",
                data={"tutorial_step": 1},
                tenant_id=event.tenant_id
            )
            
            # Trigger gamification engine
            GamificationEngine.on_user_registered(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle user registered event: {exc}")
    
    def _handle_checkin_completed(self, event: EngagementEvent):
        """Handle check-in completion event."""
        try:
            streak = event.properties.get('streak', 1)
            coins_earned = event.properties.get('coins_earned', 0)
            
            # Check for streak milestones
            if streak in [3, 7, 14, 30, 50, 100, 365]:
                self.emit_event(EngagementEvent(
                    event_type=EventType.MILESTONE_REACHED,
                    user_id=event.user_id,
                    tenant_id=event.tenant_id,
                    properties={
                        'milestone_type': 'streak',
                        'value': streak,
                        'coins_earned': coins_earned
                    }
                ))
            
            # Trigger gamification engine
            GamificationEngine.on_checkin(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle checkin completed event: {exc}")
    
    def _handle_spin_completed(self, event: EngagementEvent):
        """Handle spin completion event."""
        try:
            coins_won = event.properties.get('coins_won', 0)
            is_boosted = event.properties.get('is_boosted', False)
            
            # Check for big wins
            if coins_won >= 100:
                self.emit_event(EngagementEvent(
                    event_type=EventType.MILESTONE_REACHED,
                    user_id=event.user_id,
                    tenant_id=event.tenant_id,
                    properties={
                        'milestone_type': 'big_win',
                        'value': coins_won,
                        'is_boosted': is_boosted
                    }
                ))
            
            # Trigger gamification engine
            GamificationEngine.on_spin(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle spin completed event: {exc}")
    
    def _handle_quest_completed(self, event: EngagementEvent):
        """Handle quest completion event."""
        try:
            quest_type = event.properties.get('quest_type', 'daily')
            difficulty = event.properties.get('difficulty', 'easy')
            
            # Check for achievement milestones
            total_completed = event.properties.get('total_completed', 1)
            if total_completed in [10, 25, 50, 100]:
                self.emit_event(EngagementEvent(
                    event_type=EventType.MILESTONE_REACHED,
                    user_id=event.user_id,
                    tenant_id=event.tenant_id,
                    properties={
                        'milestone_type': 'quests_completed',
                        'value': total_completed,
                        'quest_type': quest_type
                    }
                ))
            
            # Trigger gamification engine
            GamificationEngine.on_quest_complete(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle quest completed event: {exc}")
    
    def _handle_achievement_unlocked(self, event: EngagementEvent):
        """Handle achievement unlock event."""
        try:
            achievement_name = event.properties.get('achievement_name', 'Unknown')
            difficulty = event.properties.get('difficulty', 'easy')
            
            # Send achievement notification
            NotificationService.send(
                user_id=event.user_id,
                notification_type="achievement",
                title=f"🏆 {achievement_name} Unlocked!",
                body=f"Congratulations! You've unlocked {achievement_name}!",
                data=event.properties,
                tenant_id=event.tenant_id
            )
            
            # Trigger gamification engine
            GamificationEngine.on_achievement_unlock(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle achievement unlocked event: {exc}")
    
    def _handle_level_up(self, event: EngagementEvent):
        """Handle level up event."""
        try:
            old_level = event.properties.get('old_level', 1)
            new_level = event.properties.get('new_level', 2)
            
            # Check for level milestones
            if new_level in [5, 10, 25, 50, 100]:
                self.emit_event(EngagementEvent(
                    event_type=EventType.MILESTONE_REACHED,
                    user_id=event.user_id,
                    tenant_id=event.tenant_id,
                    properties={
                        'milestone_type': 'level',
                        'value': new_level,
                        'old_level': old_level
                    }
                ))
            
            # Trigger gamification engine
            GamificationEngine.on_level_up(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle level up event: {exc}")
    
    def _handle_purchase_completed(self, event: EngagementEvent):
        """Handle purchase completion event."""
        try:
            item_type = event.properties.get('item_type', 'unknown')
            coins_spent = event.properties.get('coins_spent', 0)
            
            # Trigger gamification engine
            GamificationEngine.on_purchase(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle purchase completed event: {exc}")
    
    def _handle_referral_completed(self, event: EngagementEvent):
        """Handle referral completion event."""
        try:
            referral_id = event.properties.get('referral_id', None)
            
            # Trigger gamification engine
            GamificationEngine.on_referral(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle referral completed event: {exc}")
    
    def _handle_social_interaction(self, event: EngagementEvent):
        """Handle social interaction event."""
        try:
            interaction_type = event.properties.get('interaction_type', 'like')
            
            # Trigger gamification engine
            GamificationEngine.on_social_interaction(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle social interaction event: {exc}")
    
    def _handle_streak_broken(self, event: EngagementEvent):
        """Handle streak broken event."""
        try:
            old_streak = event.properties.get('old_streak', 0)
            
            # Send streak broken notification
            NotificationService.send(
                user_id=event.user_id,
                notification_type="streak_broken",
                title=f"💔 Streak Broken",
                body=f"Your {old_streak}-day streak has been broken. Check in tomorrow to start a new one!",
                data=event.properties,
                tenant_id=event.tenant_id
            )
            
        except Exception as exc:
            logger.error(f"Failed to handle streak broken event: {exc}")
    
    def _handle_milestone_reached(self, event: EngagementEvent):
        """Handle milestone reached event."""
        try:
            milestone_type = event.properties.get('milestone_type', 'unknown')
            value = event.properties.get('value', 0)
            
            # Send milestone notification
            NotificationService.send(
                user_id=event.user_id,
                notification_type="milestone",
                title=f"🎯 Milestone Reached!",
                body=f"You've reached a {milestone_type} milestone: {value}!",
                data=event.properties,
                tenant_id=event.tenant_id
            )
            
        except Exception as exc:
            logger.error(f"Failed to handle milestone reached event: {exc}")
    
    def _handle_battle_pass_tier_up(self, event: EngagementEvent):
        """Handle battle pass tier up event."""
        try:
            new_tier = event.properties.get('new_tier', 1)
            
            # Trigger gamification engine
            GamificationEngine.on_battle_pass_tier_up(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle battle pass tier up event: {exc}")
    
    def _handle_guild_joined(self, event: EngagementEvent):
        """Handle guild joined event."""
        try:
            guild_id = event.properties.get('guild_id', None)
            
            # Trigger gamification engine
            GamificationEngine.on_guild_join(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle guild joined event: {exc}")
    
    def _handle_seasonal_event_completed(self, event: EngagementEvent):
        """Handle seasonal event completion event."""
        try:
            event_type = event.properties.get('event_type', 'unknown')
            
            # Trigger gamification engine
            GamificationEngine.on_seasonal_event_complete(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle seasonal event completed event: {exc}")
    
    def _handle_webhook_triggered(self, event: EngagementEvent):
        """Handle webhook triggered event."""
        try:
            webhook_type = event.properties.get('webhook_type', 'unknown')
            
            # Trigger gamification engine
            GamificationEngine.on_webhook_trigger(event.user_id, event.properties)
            
        except Exception as exc:
            logger.error(f"Failed to handle webhook triggered event: {exc}")
    
    def _handle_anti_cheat_detected(self, event: EngagementEvent):
        """Handle anti-cheat detection event."""
        try:
            risk_level = event.properties.get('risk_level', 'low')
            rule_type = event.properties.get('rule_type', 'unknown')
            
            # Send security alert
            NotificationService.send(
                user_id=event.user_id,
                notification_type="security_alert",
                title="Security Alert",
                body="Suspicious activity detected on your account.",
                data=event.properties,
                tenant_id=event.tenant_id
            )
            
        except Exception as exc:
            logger.error(f"Failed to handle anti cheat detected event: {exc}")
    
    # ── Event Queue Management ───────────────────────────────────────────────
    
    def process_queue(self):
        """Process all events in the queue."""
        while self.event_queue:
            event = self.event_queue.pop(0)
            self._process_event(event)
    
    def clear_queue(self):
        """Clear the event queue."""
        self.event_queue.clear()
    
    def get_queue_size(self):
        """Get the current queue size."""
        return len(self.event_queue)


# Global event manager instance
event_manager = EventManager()


# ── Event Emitter Functions ─────────────────────────────────────────────────

def emit_user_registered(user_id: int, tenant_id: Optional[int] = None, **properties):
    """Emit user registered event."""
    event = EngagementEvent(
        event_type=EventType.USER_REGISTERED,
        user_id=user_id,
        tenant_id=tenant_id,
        properties=properties
    )
    event_manager.emit_event(event)


def emit_checkin_completed(user_id: int, streak: int, coins_earned: float, 
                          tenant_id: Optional[int] = None, **properties):
    """Emit check-in completed event."""
    event_properties = {
        'streak': streak,
        'coins_earned': coins_earned,
        **properties
    }
    
    event = EngagementEvent(
        event_type=EventType.CHECKIN_COMPLETED,
        user_id=user_id,
        tenant_id=tenant_id,
        properties=event_properties
    )
    event_manager.emit_event(event)


def emit_spin_completed(user_id: int, coins_won: float, xp_earned: int,
                       is_boosted: bool = False, tenant_id: Optional[int] = None, **properties):
    """Emit spin completed event."""
    event_properties = {
        'coins_won': coins_won,
        'xp_earned': xp_earned,
        'is_boosted': is_boosted,
        **properties
    }
    
    event = EngagementEvent(
        event_type=EventType.SPIN_COMPLETED,
        user_id=user_id,
        tenant_id=tenant_id,
        properties=event_properties
    )
    event_manager.emit_event(event)


def emit_quest_completed(user_id: int, quest_id: int, quest_type: str,
                        difficulty: str, tenant_id: Optional[int] = None, **properties):
    """Emit quest completed event."""
    event_properties = {
        'quest_id': quest_id,
        'quest_type': quest_type,
        'difficulty': difficulty,
        **properties
    }
    
    event = EngagementEvent(
        event_type=EventType.QUEST_COMPLETED,
        user_id=user_id,
        tenant_id=tenant_id,
        properties=event_properties
    )
    event_manager.emit_event(event)


def emit_achievement_unlocked(user_id: int, achievement_id: int, achievement_name: str,
                            difficulty: str, tenant_id: Optional[int] = None, **properties):
    """Emit achievement unlocked event."""
    event_properties = {
        'achievement_id': achievement_id,
        'achievement_name': achievement_name,
        'difficulty': difficulty,
        **properties
    }
    
    event = EngagementEvent(
        event_type=EventType.ACHIEVEMENT_UNLOCKED,
        user_id=user_id,
        tenant_id=tenant_id,
        properties=event_properties
    )
    event_manager.emit_event(event)


def emit_level_up(user_id: int, old_level: int, new_level: int,
                  tenant_id: Optional[int] = None, **properties):
    """Emit level up event."""
    event_properties = {
        'old_level': old_level,
        'new_level': new_level,
        **properties
    }
    
    event = EngagementEvent(
        event_type=EventType.LEVEL_UP,
        user_id=user_id,
        tenant_id=tenant_id,
        properties=event_properties
    )
    event_manager.emit_event(event)


def emit_streak_broken(user_id: int, old_streak: int,
                     tenant_id: Optional[int] = None, **properties):
    """Emit streak broken event."""
    event_properties = {
        'old_streak': old_streak,
        **properties
    }
    
    event = EngagementEvent(
        event_type=EventType.STREAK_BROKEN,
        user_id=user_id,
        tenant_id=tenant_id,
        properties=event_properties
    )
    event_manager.emit_event(event)


# ── Event Listeners ───────────────────────────────────────────────────────

class EventListener:
    """Base class for event listeners."""
    
    def __init__(self, event_types: List[EventType]):
        self.event_types = event_types
        self.setup_listeners()
    
    def setup_listeners(self):
        """Setup event listeners."""
        for event_type in self.event_types:
            event_manager.register_handler(event_type, self.handle_event)
    
    def handle_event(self, event: EngagementEvent):
        """Handle event - to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement handle_event")


class NotificationEventListener(EventListener):
    """Event listener for notifications."""
    
    def __init__(self):
        super().__init__([
            EventType.ACHIEVEMENT_UNLOCKED,
            EventType.LEVEL_UP,
            EventType.MILESTONE_REACHED,
            EventType.STREAK_BROKEN,
        ])
    
    def handle_event(self, event: EngagementEvent):
        """Handle notification events."""
        # Notification handling is already done in event handlers
        pass


class AnalyticsEventListener(EventListener):
    """Event listener for analytics."""
    
    def __init__(self):
        super().__init__(list(EventType))  # Listen to all events
    
    def handle_event(self, event: EngagementEvent):
        """Handle analytics events."""
        # Analytics recording is already done in event manager
        pass


# ── Event Decorators ───────────────────────────────────────────────────────

def event_handler(event_type: EventType):
    """Decorator to register event handlers."""
    def decorator(func):
        event_manager.register_handler(event_type, func)
        return func
    return decorator


def emit_event(event_type: EventType):
    """Decorator to emit events automatically."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Extract user_id and other properties from function result or kwargs
            user_id = kwargs.get('user_id')
            if user_id:
                event_properties = {k: v for k, v in kwargs.items() if k != 'user_id'}
                
                event = EngagementEvent(
                    event_type=event_type,
                    user_id=user_id,
                    properties=event_properties
                )
                event_manager.emit_event(event)
            
            return result
        return wrapper
    return decorator
