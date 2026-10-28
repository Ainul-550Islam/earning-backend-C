# engagement/schemas.py
"""
Schema definitions for engagement system.
Defines data structures for API requests/responses and internal data flow.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
from enum import Enum

from .choices import (
    USER_STATUS_CHOICES, QUEST_STATUS_CHOICES, ACHIEVEMENT_DIFFICULTY_CHOICES,
    SHOP_ITEM_TYPE_CHOICES, NOTIFICATION_TYPE_CHOICES
)


# ── Base Schemas ─────────────────────────────────────────────────────────────

@dataclass
class BaseSchema:
    """Base schema for all engagement schemas."""
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, date):
                result[key] = value.isoformat()
            elif isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value
        return result


@dataclass
class UserSchema(BaseSchema):
    """User schema."""
    id: int
    username: str
    email: str
    status: str = 'active'
    has_premium: bool = False
    tenant_id: Optional[int] = None
    date_joined: Optional[datetime] = None
    last_login: Optional[datetime] = None
    profile_picture_url: Optional[str] = None


@dataclass
class TenantSchema(BaseSchema):
    """Tenant schema."""
    id: int
    name: str
    slug: str
    is_active: bool = True
    created_at: Optional[datetime] = None


# ── Engagement Activity Schemas ───────────────────────────────────────────────

@dataclass
class CheckInSchema(BaseSchema):
    """Check-in schema."""
    user_id: int
    date: date
    coins_earned: float = 10.0
    xp_earned: int = 10
    consecutive_days: int = 1
    bonus_claimed: bool = False
    reward_claimed: bool = False
    streak_shield_used: bool = False
    note: str = ""
    tenant_id: Optional[int] = None


@dataclass
class SpinWheelSchema(BaseSchema):
    """Spin wheel schema."""
    user_id: int
    spun_at: datetime
    coins_won: float = 0.0
    xp_earned: int = 0
    outcome_idx: int = 0
    is_boosted: bool = False
    tenant_id: Optional[int] = None


@dataclass
class UserXPSchema(BaseSchema):
    """User XP schema."""
    user_id: int
    total_xp: int = 0
    level: int = 1
    level_updated_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Quest Schemas ─────────────────────────────────────────────────────────────

@dataclass
class QuestSchema(BaseSchema):
    """Quest schema."""
    name: str
    description: str
    type: str = 'daily'
    difficulty: str = 'easy'
    required_progress: int = 1
    coin_reward: float = 10.0
    xp_reward: int = 10
    is_active: bool = True
    expires_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


@dataclass
class UserQuestSchema(BaseSchema):
    """User quest schema."""
    user_id: int
    quest_id: int
    status: str = 'available'
    progress: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Achievement Schemas ───────────────────────────────────────────────────────

@dataclass
class AchievementSchema(BaseSchema):
    """Achievement schema."""
    name: str
    description: str
    type: str = 'streak'
    difficulty: str = 'easy'
    icon: str = '🏆'
    xp_reward: int = 10
    coin_reward: float = 0.0
    badge: str = ''
    is_active: bool = True
    tenant_id: Optional[int] = None


@dataclass
class UserAchievementSchema(BaseSchema):
    """User achievement schema."""
    user_id: int
    achievement_id: int
    progress: int = 0
    unlocked_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Shop Schemas ─────────────────────────────────────────────────────────────

@dataclass
class ShopItemSchema(BaseSchema):
    """Shop item schema."""
    name: str
    description: str
    type: str = 'coin_pack'
    price: float = 10.0
    quantity: int = 1
    rarity: str = 'common'
    icon: str = '🛍️'
    is_active: bool = True
    stock: Optional[int] = None
    max_purchase_per_user: Optional[int] = None
    tenant_id: Optional[int] = None


@dataclass
class ShopPurchaseSchema(BaseSchema):
    """Shop purchase schema."""
    user_id: int
    item_id: int
    quantity: int = 1
    coins_spent: float = 0.0
    status: str = 'pending'
    purchased_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


@dataclass
class UserInventorySchema(BaseSchema):
    """User inventory schema."""
    user_id: int
    item_id: int
    quantity: int = 0
    expires_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Leaderboard Schemas ───────────────────────────────────────────────────────

@dataclass
class LeaderboardSeasonSchema(BaseSchema):
    """Leaderboard season schema."""
    period: str = 'daily'
    start_date: date
    end_date: date
    is_active: bool = True
    prize_pool: float = 0.0
    tenant_id: Optional[int] = None


@dataclass
class LeaderboardSchema(BaseSchema):
    """Leaderboard schema."""
    user_id: int
    date: date
    total_coins_earned: float = 0.0
    total_xp_earned: int = 0
    rank: int = 0
    reward_distributed: bool = False
    season_id: Optional[int] = None
    tenant_id: Optional[int] = None


@dataclass
class LeaderboardRewardSchema(BaseSchema):
    """Leaderboard reward schema."""
    rank: int
    season_type: str = 'daily'
    reward_coins: float = 0.0
    reward_xp: int = 0
    reward_badge: str = ''
    tenant_id: Optional[int] = None


# ── Notification Schemas ─────────────────────────────────────────────────────

@dataclass
class NotificationSchema(BaseSchema):
    """Notification schema."""
    user_id: int
    type: str = 'system'
    title: str = ''
    body: str = ''
    icon: str = '📢'
    data: Dict[str, Any] = field(default_factory=dict)
    is_read: bool = False
    read_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


@dataclass
class UserPushTokenSchema(BaseSchema):
    """User push token schema."""
    user_id: int
    token: str
    device_type: str = 'web'
    is_active: bool = True
    created_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Social Schemas ───────────────────────────────────────────────────────────

@dataclass
class FeedItemSchema(BaseSchema):
    """Feed item schema."""
    user_id: int
    feed_type: str = 'achievement'
    title: str = ''
    body: str = ''
    image_url: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    tenant_id: Optional[int] = None


@dataclass
class FriendshipSchema(BaseSchema):
    """Friendship schema."""
    user_id: int
    friend_id: int
    status: str = 'pending'
    created_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


@dataclass
class UserFollowSchema(BaseSchema):
    """User follow schema."""
    follower_id: int
    following_id: int
    created_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Referral Schemas ─────────────────────────────────────────────────────────

@dataclass
class ReferralProgramSchema(BaseSchema):
    """Referral program schema."""
    name: str
    description: str
    reward_coins: float = 10.0
    reward_xp: int = 10
    reward_type: str = 'coins'
    is_active: bool = True
    tenant_id: Optional[int] = None


@dataclass
class ReferralSchema(BaseSchema):
    """Referral schema."""
    referrer_id: int
    referred_id: int
    program_id: int
    referral_code: str
    status: str = 'pending'
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    rewarded_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Analytics Schemas ─────────────────────────────────────────────────────

@dataclass
class EngagementEventSchema(BaseSchema):
    """Engagement event schema."""
    user_id: Optional[int] = None
    event_type: str = ''
    properties: Dict[str, Any] = field(default_factory=dict)
    value: Optional[float] = None
    coins_delta: Optional[float] = None
    xp_delta: Optional[int] = None
    tenant_id: Optional[int] = None


@dataclass
class DailyPlatformMetricSchema(BaseSchema):
    """Daily platform metric schema."""
    date: date
    total_users: int = 0
    active_users: int = 0
    new_users: int = 0
    total_checkins: int = 0
    total_spins: int = 0
    total_coins_earned: float = 0.0
    total_xp_earned: int = 0
    total_achievements: int = 0
    tenant_id: Optional[int] = None


# ── API Request/Response Schemas ───────────────────────────────────────────────

@dataclass
class CheckInRequestSchema:
    """Check-in request schema."""
    shield_used: bool = False


@dataclass
class CheckInResponseSchema:
    """Check-in response schema."""
    success: bool
    checkin: CheckInSchema
    user_stats: Dict[str, Any]
    message: str


@dataclass
class SpinRequestSchema:
    """Spin request schema."""
    use_boost: bool = False


@dataclass
class SpinResponseSchema:
    """Spin response schema."""
    success: bool
    spin: SpinWheelSchema
    remaining_spins: int
    message: str


@dataclass
class QuestCompleteRequestSchema:
    """Quest complete request schema."""
    quest_id: int
    progress: int


@dataclass
class QuestCompleteResponseSchema:
    """Quest complete response schema."""
    success: bool
    user_quest: UserQuestSchema
    rewards: Dict[str, Any]
    message: str


@dataclass
class ShopPurchaseRequestSchema:
    """Shop purchase request schema."""
    item_id: int
    quantity: int = 1


@dataclass
class ShopPurchaseResponseSchema:
    """Shop purchase response schema."""
    success: bool
    purchase: ShopPurchaseSchema
    user_balance: float
    message: str


@dataclass
class LeaderboardResponseSchema:
    """Leaderboard response schema."""
    success: bool
    leaderboard: List[LeaderboardSchema]
    user_rank: Optional[int]
    period: str
    date: str


@dataclass
class UserProfileResponseSchema:
    """User profile response schema."""
    success: bool
    user: UserSchema
    stats: Dict[str, Any]
    achievements: List[UserAchievementSchema]
    active_quests: List[UserQuestSchema]
    recent_activity: List[Dict[str, Any]]


# ── Error Schemas ───────────────────────────────────────────────────────────

@dataclass
class ErrorSchema:
    """Error response schema."""
    success: bool = False
    error: str = ''
    code: str = ''
    type: str = ''
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ValidationErrorSchema(ErrorSchema):
    """Validation error schema."""
    field_errors: Dict[str, List[str]] = field(default_factory=dict)
    form_errors: List[str] = field(default_factory=list)


# ── Pagination Schemas ─────────────────────────────────────────────────────

@dataclass
class PaginationSchema:
    """Pagination schema."""
    page: int = 1
    page_size: int = 20
    total_count: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_previous: bool = False


@dataclass
class PaginatedResponseSchema:
    """Paginated response schema."""
    success: bool = True
    data: List[Any] = field(default_factory=list)
    pagination: PaginationSchema = field(default_factory=PaginationSchema)


# ── Filter Schemas ───────────────────────────────────────────────────────────

@dataclass
class DateRangeFilterSchema:
    """Date range filter schema."""
    date_from: Optional[date] = None
    date_to: Optional[date] = None


@dataclass
class UserFilterSchema:
    """User filter schema."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    status: Optional[str] = None
    has_premium: Optional[bool] = None


@dataclass
class QuestFilterSchema:
    """Quest filter schema."""
    type: Optional[str] = None
    difficulty: Optional[str] = None
    status: Optional[str] = None
    expires_soon: bool = False


@dataclass
class AchievementFilterSchema:
    """Achievement filter schema."""
    type: Optional[str] = None
    difficulty: Optional[str] = None
    is_unlocked: Optional[bool] = None


# ── Statistics Schemas ─────────────────────────────────────────────────────

@dataclass
class UserStatsSchema:
    """User statistics schema."""
    user_id: int
    total_checkins: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    total_spins: int = 0
    total_coins: float = 0.0
    total_xp: int = 0
    level: int = 1
    achievements_count: int = 0
    quests_completed: int = 0
    referrals_count: int = 0
    last_checkin: Optional[date] = None


@dataclass
class PlatformStatsSchema:
    """Platform statistics schema."""
    total_users: int = 0
    active_users_today: int = 0
    active_users_week: int = 0
    active_users_month: int = 0
    total_checkins_today: int = 0
    total_spins_today: int = 0
    total_coins_earned_today: float = 0.0
    total_xp_earned_today: int = 0
    new_users_today: int = 0
    top_achievements: List[Dict[str, Any]] = field(default_factory=list)
    top_items: List[Dict[str, Any]] = field(default_factory=list)


# ── Configuration Schemas ───────────────────────────────────────────────────

@dataclass
class FeatureFlagSchema(BaseSchema):
    """Feature flag schema."""
    key: str
    name: str
    description: str
    is_enabled: bool = False
    environment: str = 'production'
    rollout_percentage: int = 0
    user_ids: List[int] = field(default_factory=list)
    tenant_ids: List[int] = field(default_factory=list)


@dataclass
class ABTestSchema(BaseSchema):
    """A/B test schema."""
    key: str
    name: str
    description: str
    status: str = 'draft'
    variants: List[Dict[str, Any]] = field(default_factory=list)
    traffic_split: Dict[str, int] = field(default_factory=dict)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Webhook Schemas ─────────────────────────────────────────────────────────

@dataclass
class WebhookEndpointSchema(BaseSchema):
    """Webhook endpoint schema."""
    name: str
    url: str
    events: List[str] = field(default_factory=list)
    secret: str = ''
    is_active: bool = True
    retry_count: int = 3
    success_count: int = 0
    failure_count: int = 0
    last_triggered: Optional[datetime] = None
    tenant_id: Optional[int] = None


@dataclass
class WebhookDeliverySchema(BaseSchema):
    """Webhook delivery schema."""
    endpoint_id: int
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = 'pending'
    attempt_count: int = 0
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    tenant_id: Optional[int] = None


# ── Anti-Cheat Schemas ─────────────────────────────────────────────────────

@dataclass
class AntiCheatRuleSchema(BaseSchema):
    """Anti-cheat rule schema."""
    name: str
    type: str = 'velocity'
    description: str
    threshold: float = 0.0
    time_window: int = 3600
    action: str = 'flag'
    is_active: bool = True
    tenant_id: Optional[int] = None


@dataclass
class AntiCheatLogSchema(BaseSchema):
    """Anti-cheat log schema."""
    user_id: int
    rule_id: int
    rule_type: str
    risk_level: str = 'medium'
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: str = ''
    user_agent: str = ''
    tenant_id: Optional[int] = None


# ── Utility Schemas ───────────────────────────────────────────────────────────

@dataclass
class CountSchema:
    """Count response schema."""
    count: int


@dataclass
class SuccessSchema:
    """Success response schema."""
    success: bool = True
    message: str = 'Operation completed successfully'


@dataclass
class HealthCheckSchema:
    """Health check response schema."""
    status: str = 'healthy'
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = '1.0.0'
    services: Dict[str, str] = field(default_factory=dict)


# ── Schema Validation Functions ───────────────────────────────────────────────

def validate_schema(schema_class, data: Dict[str, Any]) -> ValidationResult:
    """Validate data against a schema."""
    try:
        # Create schema instance from data
        schema_instance = schema_class(**data)
        return ValidationResult(is_valid=True, data=schema_instance)
    except Exception as e:
        return ValidationResult(is_valid=False, errors=[str(e)])


def serialize_schema(schema_instance: BaseSchema) -> Dict[str, Any]:
    """Serialize schema instance to dictionary."""
    return schema_instance.to_dict()


def deserialize_schema(schema_class, data: Dict[str, Any]) -> BaseSchema:
    """Deserialize dictionary to schema instance."""
    return schema_class(**data)


# ── Schema Registry ─────────────────────────────────────────────────────────

class SchemaRegistry:
    """Registry for all engagement schemas."""
    
    def __init__(self):
        self.schemas = {}
        self._register_schemas()
    
    def _register_schemas(self):
        """Register all schemas."""
        self.schemas.update({
            'user': UserSchema,
            'tenant': TenantSchema,
            'checkin': CheckInSchema,
            'spin_wheel': SpinWheelSchema,
            'user_xp': UserXPSchema,
            'quest': QuestSchema,
            'user_quest': UserQuestSchema,
            'achievement': AchievementSchema,
            'user_achievement': UserAchievementSchema,
            'shop_item': ShopItemSchema,
            'shop_purchase': ShopPurchaseSchema,
            'user_inventory': UserInventorySchema,
            'leaderboard_season': LeaderboardSeasonSchema,
            'leaderboard': LeaderboardSchema,
            'leaderboard_reward': LeaderboardRewardSchema,
            'notification': NotificationSchema,
            'user_push_token': UserPushTokenSchema,
            'feed_item': FeedItemSchema,
            'friendship': FriendshipSchema,
            'user_follow': UserFollowSchema,
            'referral_program': ReferralProgramSchema,
            'referral': ReferralSchema,
            'engagement_event': EngagementEventSchema,
            'daily_platform_metric': DailyPlatformMetricSchema,
            'feature_flag': FeatureFlagSchema,
            'ab_test': ABTestSchema,
            'webhook_endpoint': WebhookEndpointSchema,
            'webhook_delivery': WebhookDeliverySchema,
            'anti_cheat_rule': AntiCheatRuleSchema,
            'anti_cheat_log': AntiCheatLogSchema,
        })
    
    def get_schema(self, name: str) -> Optional[type]:
        """Get schema by name."""
        return self.schemas.get(name)
    
    def list_schemas(self) -> List[str]:
        """List all registered schemas."""
        return list(self.schemas.keys())
    
    def validate(self, schema_name: str, data: Dict[str, Any]) -> ValidationResult:
        """Validate data against a registered schema."""
        schema_class = self.get_schema(schema_name)
        if schema_class is None:
            return ValidationResult(is_valid=False, errors=[f"Unknown schema: {schema_name}"])
        
        return validate_schema(schema_class, data)


# Global schema registry instance
schema_registry = SchemaRegistry()


# ── Validation Result Schema ─────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Validation result schema."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data: Optional[Any] = None
    
    def add_error(self, error: str):
        """Add an error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add a warning."""
        self.warnings.append(warning)
