# engagement/validators.py
"""
Custom validators for engagement system.
Includes field validation, data validation, and business logic validation.
"""
import re
from datetime import datetime, date, timedelta
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from rest_framework import serializers

from .choices import (
    QUEST_STATUS_CHOICES, ACHIEVEMENT_DIFFICULTY_CHOICES,
    SHOP_ITEM_TYPE_CHOICES, USER_STATUS_CHOICES
)
from .constants import (
    CHECKIN_BASE_COINS, CHECKIN_MAX_STREAK_BONUS,
    SPIN_MAX_PER_DAY, MAX_COINS_PER_TRANSACTION
)


# ── Basic Field Validators ─────────────────────────────────────────────────────

class UsernameValidator(RegexValidator):
    """
    Validator for usernames.
    """
    regex = r'^[a-zA-Z0-9_]{3,30}$'
    message = 'Username must be 3-30 characters long and contain only letters, numbers, and underscores.'


class SlugValidator(RegexValidator):
    """
    Validator for slugs.
    """
    regex = r'^[-a-zA-Z0-9_]+$'
    message = 'Slug must contain only letters, numbers, hyphens, and underscores.'


class ColorHexValidator(RegexValidator):
    """
    Validator for hex color codes.
    """
    regex = r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$'
    message = 'Enter a valid hex color code.'


class PhoneNumberValidator(RegexValidator):
    """
    Validator for phone numbers.
    """
    regex = r'^\+?1?-?\.?\s?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$'
    message = 'Enter a valid phone number.'


class URLValidator(RegexValidator):
    """
    Validator for URLs.
    """
    regex = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
    message = 'Enter a valid URL.'


class EmojiValidator(RegexValidator):
    """
    Validator for emoji characters.
    """
    regex = r'^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\s]*$'
    message = 'Only emoji characters are allowed.'


# ── Business Logic Validators ───────────────────────────────────────────────────

def validate_positive_number(value):
    """
    Validate that a number is positive.
    """
    if value <= 0:
        raise ValidationError('Value must be positive.')
    return value


def validate_non_negative_number(value):
    """
    Validate that a number is non-negative.
    """
    if value < 0:
        raise ValidationError('Value cannot be negative.')
    return value


def validate_percentage(value):
    """
    Validate that a value is between 0 and 100.
    """
    if not 0 <= value <= 100:
        raise ValidationError('Percentage must be between 0 and 100.')
    return value


def validate_future_date(value):
    """
    Validate that a date is in the future.
    """
    if value <= timezone.now().date():
        raise ValidationError('Date must be in the future.')
    return value


def validate_past_date(value):
    """
    Validate that a date is in the past.
    """
    if value >= timezone.now().date():
        raise ValidationError('Date must be in the past.')
    return value


def validate_date_range(start_date, end_date):
    """
    Validate that end_date is after start_date.
    """
    if end_date <= start_date:
        raise ValidationError('End date must be after start date.')


def validate_max_length(value, max_length):
    """
    Validate maximum length of a string.
    """
    if len(value) > max_length:
        raise ValidationError(f'Value cannot exceed {max_length} characters.')
    return value


def validate_min_length(value, min_length):
    """
    Validate minimum length of a string.
    """
    if len(value) < min_length:
        raise ValidationError(f'Value must be at least {min_length} characters.')
    return value


def validate_email_domain(value):
    """
    Validate email domain.
    """
    allowed_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
    domain = value.split('@')[-1].lower()
    
    if domain not in allowed_domains:
        raise ValidationError('Email domain is not allowed.')
    return value


def validate_age(value):
    """
    Validate that age is reasonable.
    """
    if not 13 <= value <= 120:
        raise ValidationError('Age must be between 13 and 120.')
    return value


def validate_coins_amount(value):
    """
    Validate coins amount for transactions.
    """
    if value <= 0:
        raise ValidationError('Coins amount must be positive.')
    if value > MAX_COINS_PER_TRANSACTION:
        raise ValidationError(f'Coins amount cannot exceed {MAX_COINS_PER_TRANSACTION}.')
    return value


def validate_xp_amount(value):
    """
    Validate XP amount.
    """
    if value <= 0:
        raise ValidationError('XP amount must be positive.')
    if value > 10000:  # Max XP per transaction
        raise ValidationError('XP amount cannot exceed 10,000.')
    return value


def validate_streak_days(value):
    """
    Validate streak days.
    """
    if value < 0:
        raise ValidationError('Streak days cannot be negative.')
    if value > 3650:  # 10 years max
        raise ValidationError('Streak days cannot exceed 3,650.')
    return value


def validate_rank(value):
    """
    Validate leaderboard rank.
    """
    if value <= 0:
        raise ValidationError('Rank must be positive.')
    if value > 1000000:  # Reasonable max rank
        raise ValidationError('Rank cannot exceed 1,000,000.')
    return value


def validate_quest_progress(progress, max_progress):
    """
    Validate quest progress.
    """
    if progress < 0:
        raise ValidationError('Progress cannot be negative.')
    if progress > max_progress:
        raise ValidationError('Progress cannot exceed maximum progress.')
    return progress


def validate_achievement_requirements(value, user):
    """
    Validate that user meets achievement requirements.
    """
    # This would need to be implemented based on achievement type
    # For now, just basic validation
    if not isinstance(value, (int, float)):
        raise ValidationError('Achievement value must be a number.')
    return value


def validate_shop_item_price(value):
    """
    Validate shop item price.
    """
    if value <= 0:
        raise ValidationError('Price must be positive.')
    if value > 100000:  # Max price
        raise ValidationError('Price cannot exceed 100,000 coins.')
    return value


def validate_referral_code(value):
    """
    Validate referral code format.
    """
    if not re.match(r'^[A-Z0-9]{6,12}$', value):
        raise ValidationError('Referral code must be 6-12 uppercase letters and numbers.')
    return value


def validate_webhook_url(value):
    """
    Validate webhook URL.
    """
    if not value.startswith(('http://', 'https://')):
        raise ValidationError('Webhook URL must start with http:// or https://')
    return value


def validate_webhook_secret(value):
    """
    Validate webhook secret.
    """
    if len(value) < 16:
        raise ValidationError('Webhook secret must be at least 16 characters.')
    return value


def validate_feature_flag_key(value):
    """
    Validate feature flag key.
    """
    if not re.match(r'^[a-z0-9_]+$', value):
        raise ValidationError('Feature flag key must contain only lowercase letters, numbers, and underscores.')
    return value


def validate_experiment_key(value):
    """
    Validate A/B test experiment key.
    """
    if not re.match(r'^[a-z0-9_-]+$', value):
        raise ValidationError('Experiment key must contain only lowercase letters, numbers, hyphens, and underscores.')
    return value


# ── Model Field Validators ─────────────────────────────────────────────────────

def validate_user_status(value):
    """
    Validate user status.
    """
    valid_statuses = [choice[0] for choice in USER_STATUS_CHOICES]
    if value not in valid_statuses:
        raise ValidationError(f'Invalid status. Valid choices are: {valid_statuses}')
    return value


def validate_quest_status(value):
    """
    Validate quest status.
    """
    valid_statuses = [choice[0] for choice in QUEST_STATUS_CHOICES]
    if value not in valid_statuses:
        raise ValidationError(f'Invalid quest status. Valid choices are: {valid_statuses}')
    return value


def validate_achievement_difficulty(value):
    """
    Validate achievement difficulty.
    """
    valid_difficulties = [choice[0] for choice in ACHIEVEMENT_DIFFICULTY_CHOICES]
    if value not in valid_difficulties:
        raise ValidationError(f'Invalid difficulty. Valid choices are: {valid_difficulties}')
    return value


def validate_shop_item_type(value):
    """
    Validate shop item type.
    """
    valid_types = [choice[0] for choice in SHOP_ITEM_TYPE_CHOICES]
    if value not in valid_types:
        raise ValidationError(f'Invalid item type. Valid choices are: {valid_types}')
    return value


# ── Custom Validation Classes ───────────────────────────────────────────────────

class CheckInValidator:
    """
    Validator for check-in operations.
    """
    
    @staticmethod
    def validate_daily_checkin(user, checkin_date):
        """
        Validate that user can check in on given date.
        """
        if checkin_date > timezone.now().date():
            raise ValidationError('Cannot check in for future dates.')
        
        # Check if already checked in today
        from .models.checkin import DailyCheckIn
        
        if DailyCheckIn.objects.filter(user=user, date=checkin_date).exists():
            raise ValidationError('Already checked in today.')
        
        return True
    
    @staticmethod
    def validate_streak_calculation(current_streak, previous_streak, shield_used):
        """
        Validate streak calculation logic.
        """
        if shield_used and current_streak != previous_streak + 1:
            raise ValidationError('Invalid streak calculation with shield.')
        
        if not shield_used and current_streak != 1 and previous_streak > 1:
            raise ValidationError('Invalid streak calculation without shield.')
        
        return True


class SpinValidator:
    """
    Validator for spin operations.
    """
    
    @staticmethod
    def validate_spin_permission(user):
        """
        Validate that user can spin.
        """
        from .models.spinwheel import SpinWheel
        from datetime import date
        
        today = date.today()
        spins_today = SpinWheel.objects.filter(user=user, spun_at__date=today).count()
        
        if spins_today >= SPIN_MAX_PER_DAY:
            raise ValidationError(f'Daily spin limit reached ({SPIN_MAX_PER_DAY}).')
        
        return True
    
    @staticmethod
    def validate_spin_result(coins_won, xp_earned, outcome_idx):
        """
        Validate spin result consistency.
        """
        if coins_won < 0:
            raise ValidationError('Coins won cannot be negative.')
        
        if xp_earned < 0:
            raise ValidationError('XP earned cannot be negative.')
        
        if outcome_idx < 0:
            raise ValidationError('Outcome index cannot be negative.')
        
        return True


class QuestValidator:
    """
    Validator for quest operations.
    """
    
    @staticmethod
    def validate_quest_assignment(user, quest):
        """
        Validate that quest can be assigned to user.
        """
        # Check if user already has active quest of same type
        from .models.quest import UserQuest
        
        active_quest = UserQuest.objects.filter(
            user=user,
            quest__type=quest.type,
            status__in=['available', 'active']
        ).first()
        
        if active_quest:
            raise ValidationError(f'User already has active {quest.type} quest.')
        
        return True
    
    @staticmethod
    def validate_quest_completion(user_quest, progress):
        """
        Validate quest completion.
        """
        if user_quest.status != 'active':
            raise ValidationError('Quest is not active.')
        
        if user_quest.expires_at and user_quest.expires_at < timezone.now():
            raise ValidationError('Quest has expired.')
        
        if progress < user_quest.quest.required_progress:
            raise ValidationError('Insufficient progress for completion.')
        
        return True


class AchievementValidator:
    """
    Validator for achievement operations.
    """
    
    @staticmethod
    def validate_achievement_unlock(user, achievement):
        """
        Validate that achievement can be unlocked.
        """
        from .models.achievement import UserAchievement
        
        # Check if already unlocked
        if UserAchievement.objects.filter(
            user=user, 
            achievement=achievement,
            unlocked_at__isnull=False
        ).exists():
            raise ValidationError('Achievement already unlocked.')
        
        # Check if requirements are met
        if not AchievementValidator._check_requirements(user, achievement):
            raise ValidationError('Achievement requirements not met.')
        
        return True
    
    @staticmethod
    def _check_requirements(user, achievement):
        """
        Check if user meets achievement requirements.
        """
        # This would need to be implemented based on achievement type
        # For now, return True as a placeholder
        return True


class ShopValidator:
    """
    Validator for shop operations.
    """
    
    @staticmethod
    def validate_purchase(user, item, quantity):
        """
        Validate that user can purchase item.
        """
        total_cost = item.price * quantity
        
        # Check if user has enough coins
        user_balance = getattr(user, 'coin_balance', 0)
        if user_balance < total_cost:
            raise ValidationError('Insufficient coins.')
        
        # Check item stock
        if item.stock is not None and item.stock < quantity:
            raise ValidationError('Insufficient stock.')
        
        # Check purchase limits
        if item.max_purchase_per_user:
            from .models.shop import ShopPurchase
            
            user_purchases = ShopPurchase.objects.filter(
                user=user, 
                item=item,
                status='completed'
            ).count()
            
            if user_purchases + quantity > item.max_purchase_per_user:
                raise ValidationError('Purchase limit exceeded.')
        
        return True


class LeaderboardValidator:
    """
    Validator for leaderboard operations.
    """
    
    @staticmethod
    def validate_leaderboard_entry(user, date, season):
        """
        Validate leaderboard entry creation.
        """
        from .models.leaderboard import Leaderboard
        
        # Check if entry already exists
        if Leaderboard.objects.filter(
            user=user, 
            date=date, 
            season=season
        ).exists():
            raise ValidationError('Leaderboard entry already exists for this date/season.')
        
        return True
    
    @staticmethod
    def validate_reward_distribution(rank, total_players):
        """
        Validate reward distribution logic.
        """
        if rank < 1 or rank > total_players:
            raise ValidationError('Invalid rank for reward distribution.')
        
        # Check if rank qualifies for rewards
        reward_tiers = {
            1: 'gold',
            2: 'silver', 
            3: 'bronze',
            10: 'participation'
        }
        
        qualifying_ranks = [r for r in reward_tiers.keys() if r <= total_players]
        
        if rank not in qualifying_ranks:
            raise ValidationError('Rank does not qualify for rewards.')
        
        return True


# ── Serializer Validators ─────────────────────────────────────────────────────

class EngagementSerializerValidator:
    """
    Custom validators for DRF serializers.
    """
    
    @staticmethod
    def validate_unique_user_date(value, serializer_field):
        """
        Validate unique user-date combination.
        """
        user = serializer_field.parent.context['request'].user
        date = value
        
        from .models.checkin import DailyCheckIn
        
        if DailyCheckIn.objects.filter(user=user, date=date).exists():
            raise serializers.ValidationError('User already has an entry for this date.')
        
        return value
    
    @staticmethod
    def validate_sufficient_balance(value, serializer_field):
        """
        Validate user has sufficient balance.
        """
        user = serializer_field.parent.context['request'].user
        amount = value
        
        user_balance = getattr(user, 'coin_balance', 0)
        
        if user_balance < amount:
            raise serializers.ValidationError('Insufficient balance.')
        
        return value
    
    @staticmethod
    def validate_quest_availability(value, serializer_field):
        """
        Validate quest availability.
        """
        user = serializer_field.parent.context['request'].user
        quest = value
        
        # Check if user already has active quest
        from .models.quest import UserQuest
        
        if UserQuest.objects.filter(
            user=user,
            quest__type=quest.type,
            status__in=['available', 'active']
        ).exists():
            raise serializers.ValidationError('User already has active quest of this type.')
        
        return value


# ── Cross-Field Validators ─────────────────────────────────────────────────────

def validate_date_range_consistency(attrs):
    """
    Validate that date range fields are consistent.
    """
    start_date = attrs.get('start_date')
    end_date = attrs.get('end_date')
    
    if start_date and end_date and end_date <= start_date:
        raise ValidationError('End date must be after start date.')
    
    return attrs


def validate_price_quantity_consistency(attrs):
    """
    Validate that price and quantity are consistent.
    """
    price = attrs.get('price')
    quantity = attrs.get('quantity')
    
    if price is not None and quantity is not None:
        total_cost = price * quantity
        
        if total_cost > 100000:  # Max total cost
            raise ValidationError('Total cost cannot exceed 100,000 coins.')
    
    return attrs


def validate_progress_requirements(attrs):
    """
    Validate that progress meets requirements.
    """
    progress = attrs.get('progress')
    required_progress = attrs.get('required_progress')
    
    if progress is not None and required_progress is not None:
        if progress > required_progress:
            raise ValidationError('Progress cannot exceed required progress.')
    
    return attrs


# ── Validation Utilities ───────────────────────────────────────────────────────

class ValidationMixin:
    """
    Mixin for models that need custom validation.
    """
    
    def clean(self):
        """
        Perform model validation.
        """
        super().clean()
        
        # Call custom validation methods
        validation_methods = [
            method for method in dir(self) 
            if method.startswith('validate_') and callable(getattr(self, method))
        ]
        
        for method_name in validation_methods:
            method = getattr(self, method_name)
            method(self)
    
    def validate_fields(self, field_validators):
        """
        Validate specific fields with given validators.
        """
        errors = {}
        
        for field_name, validators in field_validators.items():
            value = getattr(self, field_name)
            
            for validator in validators:
                try:
                    validator(value)
                except ValidationError as e:
                    errors[field_name] = errors.get(field_name, []) + list(e.messages)
        
        if errors:
            raise ValidationError(errors)


def validate_model_unique_together(model_class, instance, fields):
    """
    Validate unique_together constraint for a model instance.
    """
    filter_kwargs = {}
    for field in fields:
        filter_kwargs[field] = getattr(instance, field)
    
    # Exclude current instance if it exists
    if instance.pk:
        filter_kwargs['pk__ne'] = instance.pk
    
    if model_class.objects.filter(**filter_kwargs).exists():
        field_names = ', '.join(fields)
        raise ValidationError(f'This {field_names} combination already exists.')


def validate_business_rules(instance, rules):
    """
    Validate business rules for a model instance.
    """
    for rule_name, rule_func in rules.items():
        try:
            if not rule_func(instance):
                raise ValidationError(f'Business rule "{rule_name}" failed.')
        except Exception as e:
            raise ValidationError(f'Error in business rule "{rule_name}": {str(e)}')


# ── Async Validators ───────────────────────────────────────────────────────────

class AsyncValidator:
    """
    Async validator for complex validation operations.
    """
    
    @staticmethod
    async def validate_user_engagement(user):
        """
        Validate user engagement metrics asynchronously.
        """
        # This would perform async validation operations
        # For example, checking external services, complex calculations, etc.
        pass
    
    @staticmethod
    async def validate_transaction_limits(user, amount, transaction_type):
        """
        Validate transaction limits asynchronously.
        """
        # Check against external services, rate limits, etc.
        pass
