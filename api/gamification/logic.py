"""
Gamification Logic — Business logic and rule engine for gamification module.

This module provides comprehensive business logic, rule evaluation, and
decision-making functionality for gamification operations.
"""

from __future__ import annotations
from django.db import models

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Type, Union, Callable
from decimal import Decimal
from enum import Enum

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.gamification.exceptions import GamificationServiceError
from api.gamification.models import (
    ContestCycle, ContestReward, UserAchievement, Badge, UserBadge,
    DailyChallenge, UserDailyChallenge, Streak, StreakReward, LevelConfig
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule Engine
# ---------------------------------------------------------------------------

class RuleType(Enum):
    """Types of rules."""
    POINTS_THRESHOLD = "points_threshold"
    ACHIEVEMENT_COUNT = "achievement_count"
    STREAK_DAYS = "streak_days"
    BADGE_COLLECTION = "badge_collection"
    TIME_BASED = "time_based"
    CUSTOM = "custom"


@dataclass
class Rule:
    """Rule definition for gamification logic."""
    
    id: str
    name: str
    description: str
    rule_type: RuleType
    conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    priority: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate rule conditions against context."""
        try:
            if self.rule_type == RuleType.POINTS_THRESHOLD:
                return self._evaluate_points_threshold(context)
            elif self.rule_type == RuleType.ACHIEVEMENT_COUNT:
                return self._evaluate_achievement_count(context)
            elif self.rule_type == RuleType.STREAK_DAYS:
                return self._evaluate_streak_days(context)
            elif self.rule_type == RuleType.BADGE_COLLECTION:
                return self._evaluate_badge_collection(context)
            elif self.rule_type == RuleType.TIME_BASED:
                return self._evaluate_time_based(context)
            elif self.rule_type == RuleType.CUSTOM:
                return self._evaluate_custom(context)
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error evaluating rule {self.id}: {e}")
            return False
    
    def _evaluate_points_threshold(self, context: Dict[str, Any]) -> bool:
        """Evaluate points threshold rule."""
        threshold = self.conditions.get('threshold', 0)
        operator = self.conditions.get('operator', '>=')
        points = context.get('points', 0)
        
        if operator == '>=':
            return points >= threshold
        elif operator == '>':
            return points > threshold
        elif operator == '==':
            return points == threshold
        elif operator == '<=':
            return points <= threshold
        elif operator == '<':
            return points < threshold
        else:
            return False
    
    def _evaluate_achievement_count(self, context: Dict[str, Any]) -> bool:
        """Evaluate achievement count rule."""
        threshold = self.conditions.get('threshold', 0)
        operator = self.conditions.get('operator', '>=')
        count = context.get('achievement_count', 0)
        
        if operator == '>=':
            return count >= threshold
        elif operator == '>':
            return count > threshold
        elif operator == '==':
            return count == threshold
        else:
            return False
    
    def _evaluate_streak_days(self, context: Dict[str, Any]) -> bool:
        """Evaluate streak days rule."""
        threshold = self.conditions.get('threshold', 0)
        operator = self.conditions.get('operator', '>=')
        streak_days = context.get('streak_days', 0)
        
        if operator == '>=':
            return streak_days >= threshold
        elif operator == '>':
            return streak_days > threshold
        elif operator == '==':
            return streak_days == threshold
        else:
            return False
    
    def _evaluate_badge_collection(self, context: Dict[str, Any]) -> bool:
        """Evaluate badge collection rule."""
        required_badges = self.conditions.get('required_badges', [])
        user_badges = context.get('user_badges', [])
        
        return all(badge in user_badges for badge in required_badges)
    
    def _evaluate_time_based(self, context: Dict[str, Any]) -> bool:
        """Evaluate time-based rule."""
        start_time = self.conditions.get('start_time')
        end_time = self.conditions.get('end_time')
        current_time = context.get('current_time', timezone.now())
        
        if start_time and current_time < start_time:
            return False
        
        if end_time and current_time > end_time:
            return False
        
        return True
    
    def _evaluate_custom(self, context: Dict[str, Any]) -> bool:
        """Evaluate custom rule."""
        # This would need to be implemented based on specific requirements
        return True


class RuleEngine:
    """Engine for evaluating and executing gamification rules."""
    
    def __init__(self):
        self.rules: List[Rule] = []
        self.logger = logging.getLogger(__name__)
    
    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self.rules.append(rule)
        # Sort by priority
        self.rules.sort(key=lambda r: r.priority)
        self.logger.info(f"Added rule: {rule.name}")
    
    def remove_rule(self, rule_id: str) -> None:
        """Remove a rule from the engine."""
        self.rules = [rule for rule in self.rules if rule.id != rule_id]
        self.logger.info(f"Removed rule: {rule_id}")
    
    def evaluate_rules(self, context: Dict[str, Any]) -> List[Rule]:
        """Evaluate all rules against context."""
        matching_rules = []
        
        for rule in self.rules:
            if rule.enabled and rule.evaluate(context):
                matching_rules.append(rule)
        
        return matching_rules
    
    def execute_rule_actions(self, rule: Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute actions for a matching rule."""
        results = []
        
        for action in rule.actions:
            try:
                result = self._execute_action(action, context)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error executing action {action}: {e}")
                results.append({'error': str(e)})
        
        return results
    
    def _execute_action(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action."""
        action_type = action.get('type')
        
        if action_type == 'award_points':
            return self._award_points_action(action, context)
        elif action_type == 'award_badge':
            return self._award_badge_action(action, context)
        elif action_type == 'send_notification':
            return self._send_notification_action(action, context)
        elif action_type == 'update_level':
            return self._update_level_action(action, context)
        else:
            return {'error': f'Unknown action type: {action_type}'}
    
    def _award_points_action(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute award points action."""
        points = action.get('points', 0)
        user_id = context.get('user_id')
        
        if not user_id:
            return {'error': 'User ID required for award points action'}
        
        # This would integrate with the points service
        return {'action': 'award_points', 'points': points, 'user_id': user_id}
    
    def _award_badge_action(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute award badge action."""
        badge_id = action.get('badge_id')
        user_id = context.get('user_id')
        
        if not user_id or not badge_id:
            return {'error': 'User ID and badge ID required for award badge action'}
        
        # This would integrate with the badge service
        return {'action': 'award_badge', 'badge_id': badge_id, 'user_id': user_id}
    
    def _send_notification_action(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute send notification action."""
        message = action.get('message', '')
        user_id = context.get('user_id')
        
        if not user_id:
            return {'error': 'User ID required for send notification action'}
        
        # This would integrate with the notification service
        return {'action': 'send_notification', 'message': message, 'user_id': user_id}
    
    def _update_level_action(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute update level action."""
        level = action.get('level')
        user_id = context.get('user_id')
        
        if not user_id:
            return {'error': 'User ID required for update level action'}
        
        # This would integrate with the level service
        return {'action': 'update_level', 'level': level, 'user_id': user_id}


# ---------------------------------------------------------------------------
# Business Logic Classes
# ---------------------------------------------------------------------------

class PointsLogic:
    """Business logic for points calculations and management."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_contest_points(self, rank: int, contest_data: Dict[str, Any]) -> int:
        """Calculate points for contest ranking."""
        base_points = contest_data.get('base_points', 100)
        decay_rate = contest_data.get('decay_rate', 0.1)
        
        # Apply exponential decay based on rank
        points = int(base_points * math.exp(-decay_rate * (rank - 1)))
        
        # Ensure minimum points
        min_points = contest_data.get('min_points', 10)
        points = max(points, min_points)
        
        return points
    
    def calculate_challenge_points(self, challenge_data: Dict[str, Any], 
                                 completion_data: Dict[str, Any]) -> int:
        """Calculate points for challenge completion."""
        base_points = challenge_data.get('points_reward', 50)
        
        # Bonus for early completion
        if 'completion_time' in completion_data:
            completion_time = completion_data['completion_time']
            expected_time = challenge_data.get('expected_time', 24)  # hours
            
            if completion_time < expected_time:
                bonus_ratio = min(0.5, (expected_time - completion_time) / expected_time)
                bonus_points = int(base_points * bonus_ratio)
                base_points += bonus_points
        
        return base_points
    
    def calculate_streak_bonus(self, streak_days: int, base_points: int) -> int:
        """Calculate streak bonus points."""
        if streak_days < 7:
            return 0
        
        # 10% bonus per week, max 50%
        weeks = streak_days // 7
        bonus_ratio = min(0.5, weeks * 0.1)
        
        return int(base_points * bonus_ratio)
    
    def calculate_level_bonus(self, user_level: int, base_points: int) -> int:
        """Calculate level bonus points."""
        # Higher levels get more points
        level_multiplier = 1 + (user_level - 1) * 0.05
        level_multiplier = min(level_multiplier, 2.0)  # Max 2x multiplier
        
        return int(base_points * level_multiplier)
    
    def validate_points_transaction(self, user_id: str, points: int, 
                                  source: str) -> Dict[str, Any]:
        """Validate a points transaction."""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check points range
        if points < 0:
            validation_result['errors'].append("Points cannot be negative")
            validation_result['valid'] = False
        
        # Check source
        valid_sources = ['contest', 'challenge', 'streak', 'bonus', 'penalty', 'adjustment']
        if source not in valid_sources:
            validation_result['warnings'].append(f"Unknown source: {source}")
        
        # Check user exists
        try:
            User.objects.get(id=user_id)
        except User.DoesNotExist:
            validation_result['errors'].append("User not found")
            validation_result['valid'] = False
        
        return validation_result


class BadgeLogic:
    """Business logic for badge earning and management."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def check_badge_eligibility(self, user_id: str, badge: Badge) -> Dict[str, Any]:
        """Check if user is eligible for a badge."""
        eligibility_result = {
            'eligible': False,
            'reason': '',
            'progress': 0
        }
        
        try:
            user = User.objects.get(id=user_id)
            
            # Check if user already has the badge
            if UserBadge.objects.filter(user=user, badge=badge).exists():
                eligibility_result['reason'] = 'Badge already earned'
                return eligibility_result
            
            # Check based on badge criteria
            if badge.criteria_type == 'POINTS_THRESHOLD':
                return self._check_points_badge_eligibility(user, badge)
            elif badge.criteria_type == 'ACHIEVEMENT_COUNT':
                return self._check_achievement_badge_eligibility(user, badge)
            elif badge.criteria_type == 'STREAK_DAYS':
                return self._check_streak_badge_eligibility(user, badge)
            elif badge.criteria_type == 'BADGE_COLLECTION':
                return self._check_collection_badge_eligibility(user, badge)
            else:
                eligibility_result['reason'] = 'Unknown criteria type'
                
        except User.DoesNotExist:
            eligibility_result['reason'] = 'User not found'
        
        return eligibility_result
    
    def _check_points_badge_eligibility(self, user: User, badge: Badge) -> Dict[str, Any]:
        """Check points-based badge eligibility."""
        total_points = UserAchievement.objects.filter(
            user=user, is_awarded=True
        ).aggregate(total=models.Sum('points_awarded'))['total'] or 0
        
        eligibility_result = {
            'eligible': total_points >= badge.criteria_value,
            'reason': f'Need {badge.criteria_value} points, have {total_points}',
            'progress': min(100, (total_points / badge.criteria_value) * 100) if badge.criteria_value > 0 else 0
        }
        
        return eligibility_result
    
    def _check_achievement_badge_eligibility(self, user: User, badge: Badge) -> Dict[str, Any]:
        """Check achievement-based badge eligibility."""
        achievement_count = UserAchievement.objects.filter(
            user=user, is_awarded=True
        ).count()
        
        eligibility_result = {
            'eligible': achievement_count >= badge.criteria_value,
            'reason': f'Need {badge.criteria_value} achievements, have {achievement_count}',
            'progress': min(100, (achievement_count / badge.criteria_value) * 100) if badge.criteria_value > 0 else 0
        }
        
        return eligibility_result
    
    def _check_streak_badge_eligibility(self, user: User, badge: Badge) -> Dict[str, Any]:
        """Check streak-based badge eligibility."""
        streak = Streak.objects.filter(user=user).first()
        streak_days = streak.current_days if streak else 0
        
        eligibility_result = {
            'eligible': streak_days >= badge.criteria_value,
            'reason': f'Need {badge.criteria_value} streak days, have {streak_days}',
            'progress': min(100, (streak_days / badge.criteria_value) * 100) if badge.criteria_value > 0 else 0
        }
        
        return eligibility_result
    
    def _check_collection_badge_eligibility(self, user: User, badge: Badge) -> Dict[str, Any]:
        """Check collection-based badge eligibility."""
        required_badges = badge.metadata.get('required_badges', [])
        user_badges = UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
        
        earned_badges = sum(1 for badge_id in required_badges if str(badge_id) in user_badges)
        
        eligibility_result = {
            'eligible': earned_badges == len(required_badges),
            'reason': f'Need {len(required_badges)} specific badges, have {earned_badges}',
            'progress': min(100, (earned_badges / len(required_badges)) * 100) if required_badges else 0
        }
        
        return eligibility_result


class LevelLogic:
    """Business logic for level progression and rewards."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_user_level(self, total_points: int) -> Optional[LevelConfig]:
        """Calculate user's level based on total points."""
        return LevelConfig.get_level_for_points(total_points)
    
    def calculate_level_progress(self, user_id: str) -> Dict[str, Any]:
        """Calculate user's level progress."""
        try:
            user = User.objects.get(id=user_id)
            
            # Get total points
            total_points = UserAchievement.objects.filter(
                user=user, is_awarded=True
            ).aggregate(total=models.Sum('points_awarded'))['total'] or 0
            
            # Get current level
            current_level = self.calculate_user_level(total_points)
            if not current_level:
                return {
                    'current_level': 0,
                    'next_level': None,
                    'points_to_next': 0,
                    'progress_percentage': 0
                }
            
            # Get next level
            next_level = LevelConfig.objects.filter(
                level_number=current_level.level_number + 1,
                is_active=True
            ).first()
            
            if next_level:
                points_to_next = next_level.points_required - total_points
                points_in_current = total_points - current_level.points_required
                points_for_current = next_level.points_required - current_level.points_required
                progress_percentage = (points_in_current / points_for_current) * 100
            else:
                points_to_next = 0
                progress_percentage = 100
            
            return {
                'current_level': current_level.level_number,
                'next_level': next_level.level_number if next_level else None,
                'points_to_next': max(0, points_to_next),
                'progress_percentage': min(100, progress_percentage)
            }
            
        except User.DoesNotExist:
            return {
                'current_level': 0,
                'next_level': None,
                'points_to_next': 0,
                'progress_percentage': 0
            }
    
    def should_level_up(self, user_id: str, new_points: int) -> bool:
        """Check if user should level up with new points."""
        try:
            user = User.objects.get(id=user_id)
            
            # Get current total points
            current_points = UserAchievement.objects.filter(
                user=user, is_awarded=True
            ).aggregate(total=models.Sum('points_awarded'))['total'] or 0
            
            # Calculate new total
            new_total = current_points + new_points
            
            # Get current and new levels
            current_level = self.calculate_user_level(current_points)
            new_level = self.calculate_user_level(new_total)
            
            # Check if level increased
            if current_level and new_level:
                return new_level.level_number > current_level.level_number
            elif new_level and not current_level:
                return True
            
            return False
            
        except User.DoesNotExist:
            return False


class StreakLogic:
    """Business logic for streak calculations and management."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_streak_reset_time(self, last_activity: datetime) -> datetime:
        """Calculate when streak should reset."""
        # Streak resets at midnight of the day after last activity
        next_day = last_activity.date() + timedelta(days=1)
        reset_time = timezone.make_aware(
            datetime.combine(next_day, datetime.min.time())
        )
        return reset_time
    
    def is_streak_active(self, streak: Streak) -> bool:
        """Check if streak is currently active."""
        if not streak.last_activity_date:
            return False
        
        reset_time = self.calculate_streak_reset_time(streak.last_activity_date)
        return timezone.now() < reset_time
    
    def calculate_streak_bonus_multiplier(self, streak_days: int) -> float:
        """Calculate bonus multiplier based on streak days."""
        if streak_days < 7:
            return 1.0
        elif streak_days < 30:
            return 1.1  # 10% bonus
        elif streak_days < 100:
            return 1.25  # 25% bonus
        elif streak_days < 365:
            return 1.5   # 50% bonus
        else:
            return 2.0   # 100% bonus
    
    def get_streak_milestone_rewards(self, streak_days: int) -> List[StreakReward]:
        """Get milestone rewards for current streak."""
        return StreakReward.objects.filter(
            is_active=True,
            streak_days__lte=streak_days
        ).order_by('-streak_days')


class ContestLogic:
    """Business logic for contest operations and calculations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_contest_duration(self, contest: ContestCycle) -> timedelta:
        """Calculate contest duration."""
        return contest.end_date - contest.start_date
    
    def is_contest_active(self, contest: ContestCycle) -> bool:
        """Check if contest is currently active."""
        now = timezone.now()
        return (contest.status == 'ACTIVE' and 
                contest.start_date <= now <= contest.end_date)
    
    def calculate_user_contest_rank(self, user_id: str, contest_id: str) -> Optional[int]:
        """Calculate user's rank in a contest."""
        try:
            # This would need to be implemented based on your ranking logic
            # For now, return a placeholder
            return 1
        except Exception as e:
            self.logger.error(f"Error calculating contest rank: {e}")
            return None
    
    def calculate_reward_distribution(self, contest: ContestCycle) -> Dict[str, Any]:
        """Calculate reward distribution for a contest."""
        distribution = {
            'total_rewards': 0,
            'points_distributed': 0,
            'badges_awarded': 0,
            'rewards_by_type': {}
        }
        
        # Get all rewards for the contest
        rewards = ContestReward.objects.filter(contest_cycle=contest, is_active=True)
        
        for reward in rewards:
            if reward.reward_type == 'POINTS':
                total_points = reward.points_value * reward.issued_count
                distribution['points_distributed'] += total_points
            elif reward.reward_type == 'BADGE':
                distribution['badges_awarded'] += reward.issued_count
            
            distribution['total_rewards'] += reward.issued_count
            
            reward_type = reward.reward_type
            if reward_type not in distribution['rewards_by_type']:
                distribution['rewards_by_type'][reward_type] = 0
            distribution['rewards_by_type'][reward_type] += reward.issued_count
        
        return distribution


# ---------------------------------------------------------------------------
# Decision Engine
# ---------------------------------------------------------------------------

class DecisionEngine:
    """Engine for making gamification decisions."""
    
    def __init__(self):
        self.points_logic = PointsLogic()
        self.badge_logic = BadgeLogic()
        self.level_logic = LevelLogic()
        self.streak_logic = StreakLogic()
        self.contest_logic = ContestLogic()
        self.rule_engine = RuleEngine()
        self.logger = logging.getLogger(__name__)
    
    def evaluate_user_action(self, user_id: str, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a user action and determine gamification outcomes."""
        try:
            user = User.objects.get(id=user_id)
            
            # Get user context
            user_context = self._build_user_context(user)
            user_context.update(context)
            user_context['action'] = action
            
            # Evaluate rules
            matching_rules = self.rule_engine.evaluate_rules(user_context)
            
            # Execute rule actions
            results = []
            for rule in matching_rules:
                rule_results = self.rule_engine.execute_rule_actions(rule, user_context)
                results.extend(rule_results)
            
            return {
                'success': True,
                'user_id': user_id,
                'action': action,
                'matching_rules': [rule.name for rule in matching_rules],
                'results': results,
                'context': user_context
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found'
            }
        except Exception as e:
            self.logger.error(f"Error evaluating user action: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_user_context(self, user: User) -> Dict[str, Any]:
        """Build context data for a user."""
        # Get total points
        total_points = UserAchievement.objects.filter(
            user=user, is_awarded=True
        ).aggregate(total=models.Sum('points_awarded'))['total'] or 0
        
        # Get achievement count
        achievement_count = UserAchievement.objects.filter(
            user=user, is_awarded=True
        ).count()
        
        # Get badge count
        badge_count = UserBadge.objects.filter(user=user).count()
        
        # Get streak
        streak = Streak.objects.filter(user=user).first()
        streak_days = streak.current_days if streak else 0
        
        # Get level
        level = self.level_logic.calculate_user_level(total_points)
        current_level = level.level_number if level else 1
        
        return {
            'user_id': str(user.id),
            'username': user.username,
            'points': total_points,
            'achievement_count': achievement_count,
            'badge_count': badge_count,
            'streak_days': streak_days,
            'current_level': current_level,
            'current_time': timezone.now()
        }
    
    def should_award_badge(self, user_id: str, badge_id: str) -> Dict[str, Any]:
        """Determine if a badge should be awarded to a user."""
        try:
            badge = Badge.objects.get(id=badge_id)
            eligibility = self.badge_logic.check_badge_eligibility(user_id, badge)
            
            return {
                'should_award': eligibility['eligible'],
                'reason': eligibility['reason'],
                'progress': eligibility['progress']
            }
            
        except Badge.DoesNotExist:
            return {
                'should_award': False,
                'reason': 'Badge not found',
                'progress': 0
            }
    
    def calculate_reward_for_rank(self, contest_id: str, rank: int) -> Dict[str, Any]:
        """Calculate reward for a specific rank in a contest."""
        try:
            contest = ContestCycle.objects.get(id=contest_id)
            
            # Find matching reward
            reward = ContestReward.objects.filter(
                contest_cycle=contest,
                rank_from__lte=rank,
                rank_to__gte=rank,
                is_active=True
            ).first()
            
            if not reward:
                return {
                    'reward_found': False,
                    'message': 'No reward found for this rank'
                }
            
            # Calculate points
            points = self.points_logic.calculate_contest_points(rank, {
                'base_points': reward.points_value or 100,
                'decay_rate': 0.1
            })
            
            return {
                'reward_found': True,
                'reward': {
                    'title': reward.title,
                    'type': reward.reward_type,
                    'points': points,
                    'badge_id': reward.badge_id
                }
            }
            
        except ContestCycle.DoesNotExist:
            return {
                'reward_found': False,
                'message': 'Contest not found'
            }


# Global decision engine instance
decision_engine = DecisionEngine()


# Initialize logging
logger.info("Gamification logic module initialized")
