"""
Gamification Validators — Validation utilities for gamification data.

This module provides validation functions for various gamification-related data
including points amounts, contest dates, and reward values. All validators
raise ValidationError with descriptive messages for invalid input.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Union

from django.core.exceptions import ValidationError
from django.utils import timezone

from api.gamification.constants import (
    MIN_POINTS_VALUE,
    MAX_POINTS_VALUE,
    MAX_RANK_VALUE,
    DEFAULT_LEADERBOARD_TOP_N,
)
from api.gamification.exceptions import GamificationServiceError

logger = logging.getLogger(__name__)


def validate_points_amount(points: Union[int, float, Decimal, str]) -> Decimal:
    """
    Validate points amount is within acceptable range and format.
    
    Args:
        points: Points value to validate (int, float, Decimal, or string)
        
    Returns:
        Decimal: Validated points amount as Decimal
        
    Raises:
        ValidationError: If points is invalid or out of range
    """
    try:
        # Convert to Decimal for precision
        if isinstance(points, str):
            points_decimal = Decimal(points)
        elif isinstance(points, (int, float)):
            points_decimal = Decimal(str(points))
        elif isinstance(points, Decimal):
            points_decimal = points
        else:
            raise ValidationError(f"Points must be a number, got {type(points).__name__}")
        
        # Check for negative values
        if points_decimal < 0:
            raise ValidationError("Points cannot be negative")
        
        # Check minimum value
        if points_decimal < MIN_POINTS_VALUE:
            raise ValidationError(
                f"Points amount {points_decimal} is below minimum value {MIN_POINTS_VALUE}"
            )
        
        # Check maximum value
        if points_decimal > MAX_POINTS_VALUE:
            raise ValidationError(
                f"Points amount {points_decimal} exceeds maximum value {MAX_POINTS_VALUE}"
            )
        
        # Check for too many decimal places (max 2 for financial precision)
        if points_decimal.as_tuple().exponent < -2:
            raise ValidationError(
                "Points amount cannot have more than 2 decimal places"
            )
        
        return points_decimal
        
    except (InvalidOperation, ValueError) as e:
        raise ValidationError(f"Invalid points format: {e}")
    except ValidationError:
        # Re-raise ValidationError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating points amount: {e}")
        raise ValidationError(f"Error validating points amount: {e}")


def validate_contest_dates(start_time: Any, end_time: Any) -> tuple[datetime, datetime]:
    """
    Validate contest start and end dates.
    
    Args:
        start_time: Contest start time (datetime, date, or string)
        end_time: Contest end time (datetime, date, or string)
        
    Returns:
        tuple: (validated_start_time, validated_end_time) as datetime objects
        
    Raises:
        ValidationError: If dates are invalid or in wrong order
    """
    try:
        # Convert to datetime objects
        validated_start = _convert_to_datetime(start_time, "start_time")
        validated_end = _convert_to_datetime(end_time, "end_time")
        
        # Validate start time is not in the past (unless it's already started)
        now = timezone.now()
        if validated_start < now - timedelta(minutes=1):
            # Allow start times that are slightly in the past (for contests that just started)
            if validated_start < now - timedelta(hours=1):
                raise ValidationError(
                    f"Contest start time {validated_start} is too far in the past"
                )
        
        # Validate end time is after start time
        if validated_end <= validated_start:
            raise ValidationError(
                f"Contest end time {validated_end} must be after start time {validated_start}"
            )
        
        # Validate minimum duration (at least 1 hour)
        min_duration = timedelta(hours=1)
        if validated_end - validated_start < min_duration:
            raise ValidationError(
                f"Contest duration must be at least {min_duration}, "
                f"got {validated_end - validated_start}"
            )
        
        # Validate maximum duration (no more than 1 year)
        max_duration = timedelta(days=365)
        if validated_end - validated_start > max_duration:
            raise ValidationError(
                f"Contest duration cannot exceed {max_duration}, "
                f"got {validated_end - validated_start}"
            )
        
        # Validate end time is not too far in the future (max 2 years)
        max_future = now + timedelta(days=730)
        if validated_end > max_future:
            raise ValidationError(
                f"Contest end time {validated_end} is too far in the future "
                f"(maximum: {max_future})"
            )
        
        return validated_start, validated_end
        
    except ValidationError:
        # Re-raise ValidationError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating contest dates: {e}")
        raise ValidationError(f"Error validating contest dates: {e}")


def validate_reward_value(
    reward_type: str,
    points_bonus: Union[int, float, Decimal, str],
    total_budget: Optional[Union[int, float, Decimal, str]] = None,
    rank_from: Optional[int] = None,
    rank_to: Optional[int] = None,
) -> tuple[Decimal, Optional[Decimal]]:
    """
    Validate reward configuration values.
    
    Args:
        reward_type: Type of reward (e.g., 'POINTS', 'BADGE', 'ITEM')
        points_bonus: Points bonus for the reward
        total_budget: Total budget for the reward (optional)
        rank_from: Starting rank for the reward (optional)
        rank_to: Ending rank for the reward (optional)
        
    Returns:
        tuple: (validated_points_bonus, validated_total_budget)
        
    Raises:
        ValidationError: If reward values are invalid
    """
    try:
        # Validate points bonus
        validated_points_bonus = validate_points_amount(points_bonus)
        
        # Validate total budget if provided
        validated_total_budget = None
        if total_budget is not None:
            validated_total_budget = validate_points_amount(total_budget)
            
            # Budget must be at least as much as points bonus
            if validated_total_budget < validated_points_bonus:
                raise ValidationError(
                    f"Total budget {validated_total_budget} must be at least "
                    f"points bonus {validated_points_bonus}"
                )
        
        # Validate rank range if provided
        if rank_from is not None or rank_to is not None:
            if rank_from is None or rank_to is None:
                raise ValidationError(
                    "Both rank_from and rank_to must be provided when using rank ranges"
                )
            
            if rank_from < 1:
                raise ValidationError("Rank from must be at least 1")
            
            if rank_to < rank_from:
                raise ValidationError(
                    f"Rank to ({rank_to}) must be greater than or equal to rank from ({rank_from})"
                )
            
            if rank_to > MAX_RANK_VALUE:
                raise ValidationError(
                    f"Rank to ({rank_to}) exceeds maximum value {MAX_RANK_VALUE}"
                )
            
            # Validate budget can cover the rank range
            if validated_total_budget is not None:
                rank_count = rank_to - rank_from + 1
                min_budget = validated_points_bonus * rank_count
                
                if validated_total_budget < min_budget:
                    raise ValidationError(
                        f"Total budget {validated_total_budget} insufficient for "
                        f"{rank_count} ranks at {validated_points_bonus} points each "
                        f"(minimum required: {min_budget})"
                    )
        
        # Validate reward type specific rules
        if reward_type.upper() == 'POINTS':
            if validated_points_bonus <= 0:
                raise ValidationError("Points reward must have positive points bonus")
        
        elif reward_type.upper() == 'BADGE':
            # Badge rewards typically don't have points, but can have bonus points
            if validated_points_bonus < 0:
                raise ValidationError("Badge reward cannot have negative points bonus")
        
        elif reward_type.upper() == 'ITEM':
            # Item rewards can have zero or positive points
            if validated_points_bonus < 0:
                raise ValidationError("Item reward cannot have negative points bonus")
        
        else:
            # Allow custom reward types but validate points bonus
            if validated_points_bonus < 0:
                raise ValidationError(f"{reward_type} reward cannot have negative points bonus")
        
        return validated_points_bonus, validated_total_budget
        
    except ValidationError:
        # Re-raise ValidationError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating reward value: {e}")
        raise ValidationError(f"Error validating reward value: {e}")


def validate_leaderboard_scope(scope: str) -> str:
    """
    Validate leaderboard scope value.
    
    Args:
        scope: Leaderboard scope string
        
    Returns:
        str: Validated scope string
        
    Raises:
        ValidationError: If scope is invalid
    """
    valid_scopes = ['ALL_USERS', 'ACTIVE_USERS', 'TOP_N']
    
    if not isinstance(scope, str):
        raise ValidationError(f"Scope must be a string, got {type(scope).__name__}")
    
    scope_upper = scope.upper()
    
    if scope_upper not in valid_scopes:
        raise ValidationError(
            f"Invalid scope '{scope}'. Valid scopes are: {', '.join(valid_scopes)}"
        )
    
    return scope_upper


def validate_top_n_value(top_n: Union[int, str]) -> int:
    """
    Validate top-N value for leaderboards.
    
    Args:
        top_n: Top-N value (int or string)
        
    Returns:
        int: Validated top-N value
        
    Raises:
        ValidationError: If top-N is invalid
    """
    try:
        if isinstance(top_n, str):
            top_n_int = int(top_n)
        elif isinstance(top_n, int):
            top_n_int = top_n
        else:
            raise ValidationError(f"Top-N must be an integer, got {type(top_n).__name__}")
        
        if top_n_int < 1:
            raise ValidationError("Top-N value must be at least 1")
        
        if top_n_int > DEFAULT_LEADERBOARD_TOP_N * 10:  # 10x default max
            raise ValidationError(
                f"Top-N value {top_n_int} is too large "
                f"(maximum: {DEFAULT_LEADERBOARD_TOP_N * 10})"
            )
        
        return top_n_int
        
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Invalid top-N value: {e}")
    except ValidationError:
        # Re-raise ValidationError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating top-N value: {e}")
        raise ValidationError(f"Error validating top-N value: {e}")


def validate_user_achievement_data(
    user_id: Any,
    points_awarded: Union[int, float, Decimal, str],
    achievement_type: str,
    rank: Optional[int] = None,
) -> tuple[Any, Decimal]:
    """
    Validate user achievement data.
    
    Args:
        user_id: User identifier
        points_awarded: Points awarded for achievement
        achievement_type: Type of achievement
        rank: Achievement rank (optional)
        
    Returns:
        tuple: (validated_user_id, validated_points_awarded)
        
    Raises:
        ValidationError: If achievement data is invalid
    """
    try:
        # Validate user_id (basic check - more thorough validation would be in the service)
        if not user_id:
            raise ValidationError("User ID cannot be empty")
        
        # Validate points awarded
        validated_points = validate_points_amount(points_awarded)
        
        # Validate achievement type
        if not isinstance(achievement_type, str) or not achievement_type.strip():
            raise ValidationError("Achievement type must be a non-empty string")
        
        # Validate rank if provided
        if rank is not None:
            if not isinstance(rank, int):
                raise ValidationError(f"Rank must be an integer, got {type(rank).__name__}")
            
            if rank < 1:
                raise ValidationError("Rank must be at least 1")
            
            if rank > MAX_RANK_VALUE:
                raise ValidationError(
                    f"Rank {rank} exceeds maximum value {MAX_RANK_VALUE}"
                )
        
        return user_id, validated_points
        
    except ValidationError:
        # Re-raise ValidationError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating user achievement data: {e}")
        raise ValidationError(f"Error validating user achievement data: {e}")


def validate_badge_criteria(
    criteria_type: str,
    criteria_value: Union[int, float, Decimal, str],
    metadata: Optional[dict] = None,
) -> tuple[str, Union[int, Decimal]]:
    """
    Validate badge criteria configuration.
    
    Args:
        criteria_type: Type of criteria (e.g., 'POINTS_THRESHOLD', 'STREAK_DAYS')
        criteria_value: Value for the criteria
        metadata: Additional metadata (optional)
        
    Returns:
        tuple: (validated_criteria_type, validated_criteria_value)
        
    Raises:
        ValidationError: If criteria is invalid
    """
    try:
        # Validate criteria type
        valid_criteria_types = [
            'POINTS_THRESHOLD',
            'STREAK_DAYS',
            'ACHIEVEMENT_COUNT',
            'CONTEST_WINS',
            'REFERRAL_COUNT',
        ]
        
        if not isinstance(criteria_type, str):
            raise ValidationError(f"Criteria type must be a string, got {type(criteria_type).__name__}")
        
        criteria_type_upper = criteria_type.upper()
        
        if criteria_type_upper not in valid_criteria_types:
            raise ValidationError(
                f"Invalid criteria type '{criteria_type}'. "
                f"Valid types are: {', '.join(valid_criteria_types)}"
            )
        
        # Validate criteria value based on type
        if criteria_type_upper in ['POINTS_THRESHOLD']:
            # Points can be decimal
            validated_value = validate_points_amount(criteria_value)
        else:
            # Other criteria types must be integers
            try:
                if isinstance(criteria_value, str):
                    validated_value = int(criteria_value)
                elif isinstance(criteria_value, (int, float)):
                    validated_value = int(float(criteria_value))
                elif isinstance(criteria_value, Decimal):
                    validated_value = int(criteria_value)
                else:
                    raise ValidationError(
                        f"Criteria value must be numeric, got {type(criteria_value).__name__}"
                    )
                
                if validated_value < 1:
                    raise ValidationError(f"{criteria_type_upper} criteria value must be at least 1")
                
                if validated_value > 1000000:  # Reasonable upper limit
                    raise ValidationError(
                        f"{criteria_type_upper} criteria value {validated_value} is too large"
                    )
                    
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid criteria value for {criteria_type_upper}: {e}")
        
        # Validate metadata if provided
        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValidationError("Metadata must be a dictionary")
            
            # Check metadata size (prevent overly large metadata)
            metadata_str = str(metadata)
            if len(metadata_str) > 10000:  # 10KB limit
                raise ValidationError("Metadata is too large")
        
        return criteria_type_upper, validated_value
        
    except ValidationError:
        # Re-raise ValidationError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error validating badge criteria: {e}")
        raise ValidationError(f"Error validating badge criteria: {e}")


def _convert_to_datetime(value: Any, field_name: str) -> datetime:
    """
    Convert various date/time formats to datetime object.
    
    Args:
        value: Value to convert
        field_name: Name of the field (for error messages)
        
    Returns:
        datetime: Converted datetime object
        
    Raises:
        ValidationError: If conversion fails
    """
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            # Make timezone-aware if naive
            value = timezone.make_aware(value)
        return value
    
    elif isinstance(value, str):
        try:
            # Try ISO format first
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except ValueError:
            # Try other common formats
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d',
                '%Y/%m/%d %H:%M:%S',
                '%Y/%m/%d %H:%M',
                '%Y/%m/%d',
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(value, fmt)
                    if timezone.is_naive(dt):
                        dt = timezone.make_aware(dt)
                    return dt
                except ValueError:
                    continue
            
            raise ValidationError(f"Invalid {field_name} format: {value}")
    
    else:
        raise ValidationError(
            f"{field_name} must be a datetime or string, got {type(value).__name__}"
        )


# Utility function for batch validation
def validate_batch_data(data_list: list, validator_func: callable, *args, **kwargs) -> list:
    """
    Validate a list of data items using a validator function.
    
    Args:
        data_list: List of data items to validate
        validator_func: Validator function to call for each item
        *args: Additional arguments for validator function
        **kwargs: Additional keyword arguments for validator function
        
    Returns:
        list: List of validated data items
        
    Raises:
        ValidationError: If any item fails validation
    """
    validated_list = []
    
    for i, item in enumerate(data_list):
        try:
            validated_item = validator_func(item, *args, **kwargs)
            validated_list.append(validated_item)
        except ValidationError as e:
            raise ValidationError(f"Validation failed for item {i+1}: {e}")
        except Exception as e:
            raise ValidationError(f"Unexpected error validating item {i+1}: {e}")
    
    return validated_list
