"""
Gamification Interactors — Service interaction layer for gamification system.

This module provides interactor classes that mediate between use cases and
repositories/services, handling complex business logic and orchestrating
multiple service interactions.
"""

from __future__ import annotations
from django.core.cache import cache
from django.db.models import ExpressionWrapper
from django.db.models import F
from django.db.models import FloatField
from django.db.models import Q

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, LeaderboardSnapshot,
    ContestReward, UserAchievement, WebhookEndpoint, WebhookEvent, WebhookDelivery
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction, ChallengeStatus,
    StreakStatus, ContestCycleStatus, LeaderboardScope, SnapshotStatus,
    RewardType, AchievementType, WebhookStatus, WebhookEventType
)
from api.gamification.services import (
    BadgeService, DailyChallengeService, StreakService, LevelUpService
)
from api.gamification.repositories import (
    BadgeRepository, UserBadgeRepository, DailyChallengeRepository,
    UserDailyChallengeRepository, StreakRepository, LevelConfigRepository,
    ContestCycleRepository, UserAchievementRepository, WebhookEventRepository,
    WebhookDeliveryRepository
)
from api.gamification.use_cases import (
    BadgeUseCase, StreakUseCase, ChallengeUseCase, LevelUseCase,
    ContestUseCase, GamificationSummaryUseCase
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.helpers import (
    PointsCalculator, BadgeHelper, StreakHelper, ChallengeHelper,
    LevelHelper, UserHelper, CacheHelper, ValidationHelper
)
from api.gamification.webhooks import WebhookService

User = get_user_model()
logger = logging.getLogger(__name__)


class BaseInteractor:
    """Base class for all interactors."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def validate_input(self, **kwargs) -> None:
        """Validate input parameters."""
        pass
    
    def execute(self, **kwargs) -> Any:
        """Execute the interactor."""
        raise NotImplementedError("Subclasses must implement execute method")


class BadgeInteractor(BaseInteractor):
    """Interactor for badge-related operations."""
    
    def __init__(self):
        super().__init__()
        self.badge_use_case = BadgeUseCase()
        self.badge_repository = BadgeRepository()
        self.user_badge_repository = UserBadgeRepository()
        self.webhook_service = WebhookService()
    
    def award_badges_with_notifications(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Award badges and send notifications."""
        try:
            self.validate_input(user_id=user_id, metadata=metadata)
            
            with transaction.atomic():
                # Award badges
                awarded_badges = self.badge_use_case.award_badges_to_user(user_id, metadata)
                
                # Process each awarded badge
                results = []
                for user_badge in awarded_badges:
                    # Create webhook event
                    webhook_data = {
                        'user_id': user_id,
                        'badge_id': str(user_badge.badge.id),
                        'badge_name': user_badge.badge.name,
                        'badge_rarity': user_badge.badge.rarity,
                        'points_bonus': user_badge.badge.points_bonus,
                        'earned_at': user_badge.earned_at.isoformat(),
                        'metadata': metadata or {}
                    }
                    
                    # Trigger webhook
                    self.webhook_service.trigger_webhook_event(
                        event_type=WebhookEventType.BADGE_EARNED,
                        user_id=user_id,
                        data=webhook_data
                    )
                    
                    results.append({
                        'badge_id': str(user_badge.badge.id),
                        'badge_name': user_badge.badge.name,
                        'points_bonus': user_badge.badge.points_bonus,
                        'earned_at': user_badge.earned_at.isoformat()
                    })
                
                return {
                    'awarded_badges': results,
                    'total_awarded': len(results),
                    'total_points': sum(b['points_bonus'] for b in results)
                }
                
        except Exception as e:
            self.logger.error(f"Error awarding badges with notifications for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to award badges with notifications: {e}")
    
    def process_badge_eligibility_batch(self, user_ids: List[str]) -> Dict[str, Any]:
        """Process badge eligibility for multiple users."""
        try:
            self.validate_input(user_ids=user_ids)
            
            results = {}
            total_awarded = 0
            
            for user_id in user_ids:
                try:
                    awarded_badges = self.badge_use_case.award_badges_to_user(user_id)
                    results[user_id] = {
                        'awarded_count': len(awarded_badges),
                        'awarded_badges': [
                            {
                                'badge_id': str(badge.badge.id),
                                'badge_name': badge.badge.name,
                                'points_bonus': badge.badge.points_bonus
                            }
                            for badge in awarded_badges
                        ]
                    }
                    total_awarded += len(awarded_badges)
                    
                except Exception as e:
                    self.logger.error(f"Error processing badge eligibility for user {user_id}: {e}")
                    results[user_id] = {
                        'error': str(e),
                        'awarded_count': 0,
                        'awarded_badges': []
                    }
            
            return {
                'results': results,
                'total_users_processed': len(user_ids),
                'total_badges_awarded': total_awarded,
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error processing badge eligibility batch: {e}")
            raise GamificationServiceError(f"Failed to process badge eligibility batch: {e}")
    
    def get_user_badge_recommendations(self, user_id: str, count: int = 5) -> List[Dict[str, Any]]:
        """Get personalized badge recommendations."""
        try:
            self.validate_input(user_id=user_id, count=count)
            
            # Get user stats
            user_stats = UserHelper.get_user_gamification_stats(user_id)
            
            # Get available badges
            available_badges = self.badge_use_case.get_available_badges(user_id)
            
            # Filter unearned badges and sort by recommendation score
            unearned_badges = [
                badge for badge in available_badges
                if not self.user_badge_repository.check_user_has_badge(user_id, badge['id'])
            ]
            
            # Calculate recommendation scores
            for badge in unearned_badges:
                badge['recommendation_score'] = BadgeHelper.calculate_badge_score(
                    self.badge_repository.get_by_id(badge['id']),
                    user_stats['total_points']
                )
            
            # Sort by recommendation score and return top results
            unearned_badges.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            return unearned_badges[:count]
            
        except Exception as e:
            self.logger.error(f"Error getting badge recommendations for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get badge recommendations: {e}")


class StreakInteractor(BaseInteractor):
    """Interactor for streak-related operations."""
    
    def __init__(self):
        super().__init__()
        self.streak_use_case = StreakUseCase()
        self.streak_repository = StreakRepository()
        self.webhook_service = WebhookService()
    
    def update_streak_with_milestones(self, user_id: str, activity_date: Optional[datetime.date] = None,
                                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update streak and process milestone rewards."""
        try:
            self.validate_input(user_id=user_id, activity_date=activity_date, metadata=metadata)
            
            with transaction.atomic():
                # Update streak
                streak_result = self.streak_use_case.update_user_activity(
                    user_id=user_id,
                    activity_date=activity_date,
                    metadata=metadata
                )
                
                # Check for milestone rewards
                milestone_rewards = []
                if streak_result['was_extended']:
                    milestone_rewards = streak_result['milestone_rewards']
                    
                    # Process milestone rewards
                    for reward in milestone_rewards:
                        # Create webhook event for milestone
                        webhook_data = {
                            'user_id': user_id,
                            'streak_days': streak_result['streak']['current_days'],
                            'reward_title': reward['title'],
                            'reward_description': reward['description'],
                            'points_bonus': reward['points_bonus'],
                            'badge_id': str(reward['badge_id']) if reward.get('badge_id') else None,
                            'activity_date': activity_date.isoformat() if activity_date else None,
                            'metadata': metadata or {}
                        }
                        
                        self.webhook_service.trigger_webhook_event(
                            event_type=WebhookEventType.STREAK_MILESTONE,
                            user_id=user_id,
                            data=webhook_data
                        )
                
                return {
                    'streak': streak_result['streak'],
                    'was_extended': streak_result['was_extended'],
                    'days_added': streak_result['days_added'],
                    'milestone_rewards': milestone_rewards,
                    'total_milestone_points': sum(r['points_bonus'] for r in milestone_rewards)
                }
                
        except Exception as e:
            self.logger.error(f"Error updating streak with milestones for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to update streak with milestones: {e}")
    
    def process_streak_expirations(self) -> Dict[str, Any]:
        """Process streak expirations and send notifications."""
        try:
            # Get streaks that will expire today
            expiring_streaks = self.streak_repository.get_expiring_soon(days=0)
            
            results = []
            for streak in expiring_streaks:
                # Create webhook event for streak expiration
                webhook_data = {
                    'user_id': str(streak.user.id),
                    'current_days': streak.current_days,
                    'longest_days': streak.longest_days,
                    'last_activity_date': streak.last_activity_date.isoformat(),
                    'expired_at': timezone.now().isoformat()
                }
                
                self.webhook_service.trigger_webhook_event(
                    event_type=WebhookEventType.STREAK_EXPIRED,
                    user_id=str(streak.user.id),
                    data=webhook_data
                )
                
                # Update streak status
                streak.is_active = False
                streak.save()
                
                results.append({
                    'user_id': str(streak.user.id),
                    'current_days': streak.current_days,
                    'longest_days': streak.longest_days,
                    'expired_at': timezone.now().isoformat()
                })
            
            return {
                'expired_streaks': results,
                'total_expired': len(results),
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error processing streak expirations: {e}")
            raise GamificationServiceError(f"Failed to process streak expirations: {e}")
    
    def get_streak_leaderboard_with_rewards(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get streak leaderboard with reward calculations."""
        try:
            self.validate_input(limit=limit)
            
            # Get leaderboard
            leaderboard = self.streak_use_case.get_streak_leaderboard(limit)
            
            # Calculate rewards for each position
            enriched_leaderboard = []
            for entry in leaderboard:
                # Calculate streak bonus
                streak_bonus = PointsCalculator.calculate_streak_bonus_points(entry['current_days'])
                
                # Get milestone rewards
                milestone_rewards = StreakHelper.get_streak_milestone_rewards(entry['current_days'])
                milestone_bonus = sum(r['points_bonus'] for r in milestone_rewards)
                
                enriched_entry = entry.copy()
                enriched_entry.update({
                    'streak_bonus': streak_bonus,
                    'milestone_bonus': milestone_bonus,
                    'total_bonus': streak_bonus + milestone_bonus,
                    'milestone_count': len(milestone_rewards)
                })
                
                enriched_leaderboard.append(enriched_entry)
            
            return enriched_leaderboard
            
        except Exception as e:
            self.logger.error(f"Error getting streak leaderboard with rewards: {e}")
            raise GamificationServiceError(f"Failed to get streak leaderboard with rewards: {e}")


class ChallengeInteractor(BaseInteractor):
    """Interactor for challenge-related operations."""
    
    def __init__(self):
        super().__init__()
        self.challenge_use_case = ChallengeUseCase()
        self.user_challenge_repository = UserDailyChallengeRepository()
        self.webhook_service = WebhookService()
    
    def complete_challenge_with_rewards(self, user_id: str, challenge_id: str,
                                     increment_amount: int = 1, action_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Complete challenge and process rewards."""
        try:
            self.validate_input(user_id=user_id, challenge_id=challenge_id, increment_amount=increment_amount)
            
            with transaction.atomic():
                # Update challenge progress
                challenge_result = self.challenge_use_case.update_challenge_progress(
                    user_id=user_id,
                    challenge_id=challenge_id,
                    increment_amount=increment_amount,
                    action_metadata=action_metadata
                )
                
                # Process completion rewards
                if challenge_result['completed']:
                    # Create webhook event for challenge completion
                    webhook_data = {
                        'user_id': user_id,
                        'challenge_id': challenge_id,
                        'challenge_title': challenge_result['user_challenge']['challenge_title'],
                        'bonus_points': challenge_result['bonus_points'],
                        'completed_at': timezone.now().isoformat(),
                        'action_metadata': action_metadata or {}
                    }
                    
                    self.webhook_service.trigger_webhook_event(
                        event_type=WebhookEventType.CHALLENGE_COMPLETED,
                        user_id=user_id,
                        data=webhook_data
                    )
                
                return challenge_result
                
        except Exception as e:
            self.logger.error(f"Error completing challenge with rewards for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to complete challenge with rewards: {e}")
    
    def process_daily_challenge_reset(self) -> Dict[str, Any]:
        """Process daily challenge reset and create new challenges."""
        try:
            from api.gamification.services import DailyChallengeService
            
            # Get yesterday's date
            yesterday = timezone.now().date() - timedelta(days=1)
            
            # Get yesterday's challenges
            yesterday_challenges = DailyChallengeService.get_active_challenges(yesterday)
            
            # Create webhook events for uncompleted challenges
            uncompleted_count = 0
            for challenge in yesterday_challenges:
                # Count uncompleted participants
                uncompleted_participants = (
                    self.user_challenge_repository.get_for_challenge(str(challenge.id))
                    .filter(is_completed=False)
                    .count()
                )
                
                if uncompleted_participants > 0:
                    # Create webhook event for challenge expiry
                    webhook_data = {
                        'challenge_id': str(challenge.id),
                        'challenge_title': challenge.title,
                        'uncompleted_participants': uncompleted_participants,
                        'challenge_date': yesterday.isoformat()
                    }
                    
                    self.webhook_service.trigger_webhook_event(
                        event_type=WebhookEventType.CHALLENGE_EXPIRED,
                        data=webhook_data
                    )
                    
                    uncompleted_count += 1
            
            # Create new challenges for today
            today = timezone.now().date()
            new_challenges = DailyChallengeService.generate_daily_challenges(today)
            
            return {
                'processed_date': yesterday.isoformat(),
                'yesterday_challenges': len(yesterday_challenges),
                'uncompleted_challenges': uncompleted_count,
                'new_challenges_created': len(new_challenges),
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error processing daily challenge reset: {e}")
            raise GamificationServiceError(f"Failed to process daily challenge reset: {e}")
    
    def get_challenge_completion_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get challenge completion analytics."""
        try:
            self.validate_input(days=days)
            
            # Get challenge statistics
            from django.db.models import Count, Avg, Sum
            
            since = timezone.now().date() - timedelta(days=days)
            
            # Challenge completion rates
            challenge_stats = (
                DailyChallenge.objects
                .filter(date__gte=since)
                .annotate(
                    total_participants=Count('userdailychallenge'),
                    completed_participants=Count(
                        'userdailychallenge',
                        filter=Q(userdailychallenge__is_completed=True)
                    )
                )
                .aggregate(
                    avg_completion_rate=Avg(
                        ExpressionWrapper(
                            F('completed_participants') * 100.0 / F('total_participants'),
                            output_field=FloatField()
                        )
                    ),
                    total_challenges=Count('id'),
                    total_participants=Sum('total_participants'),
                    total_completions=Sum('completed_participants')
                )
            )
            
            # Action type distribution
            action_distribution = dict(
                UserDailyChallenge.objects
                .filter(challenge__date__gte=since, is_completed=True)
                .values('challenge__target_action')
                .annotate(count=Count('id'))
                .values_list('challenge__target_action', 'count')
            )
            
            return {
                'period_days': days,
                'analytics': {
                    'average_completion_rate': float(challenge_stats['avg_completion_rate'] or 0),
                    'total_challenges': challenge_stats['total_challenges'],
                    'total_participants': challenge_stats['total_participants'] or 0,
                    'total_completions': challenge_stats['total_completions'] or 0,
                    'action_distribution': action_distribution
                },
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting challenge completion analytics: {e}")
            raise GamificationServiceError(f"Failed to get challenge completion analytics: {e}")


class LevelInteractor(BaseInteractor):
    """Interactor for level-related operations."""
    
    def __init__(self):
        super().__init__()
        self.level_use_case = LevelUseCase()
        self.level_repository = LevelConfigRepository()
        self.webhook_service = WebhookService()
    
    def process_level_up_with_perks(self, user_id: str) -> Dict[str, Any]:
        """Process level up and distribute perks."""
        try:
            self.validate_input(user_id=user_id)
            
            with transaction.atomic():
                # Check eligibility
                eligibility = self.level_use_case.check_level_up_eligibility(user_id)
                
                if not eligibility['can_level_up']:
                    return {
                        'can_level_up': False,
                        'current_level': eligibility['current_level'],
                        'points_to_next': eligibility['points_to_next_level']
                    }
                
                # Get current level info
                old_level_info = self.level_use_case.get_user_level_info(user_id)
                
                # Get next level
                next_level = eligibility['next_level']
                if not next_level:
                    raise GamificationServiceError("No next level available")
                
                # Process level up
                level_up_result = self.level_use_case.level_up_user(user_id)
                
                # Create webhook event for level up
                webhook_data = {
                    'user_id': user_id,
                    'old_level': level_up_result['old_level']['level_number'],
                    'new_level': level_up_result['new_level']['level_number'],
                    'new_level_title': level_up_result['new_level']['title'],
                    'perks_received': level_up_result['perks_received'],
                    'level_up_at': level_up_result['level_up_at']
                }
                
                self.webhook_service.trigger_webhook_event(
                    event_type=WebhookEventType.LEVEL_UP,
                    user_id=user_id,
                    data=webhook_data
                )
                
                return level_up_result
                
        except Exception as e:
            self.logger.error(f"Error processing level up with perks for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to process level up with perks: {e}")
    
    def get_level_progress_analytics(self) -> Dict[str, Any]:
        """Get level progress analytics for all users."""
        try:
            from django.db.models import Count, Avg, Max
            
            # Get level distribution
            level_distribution = self.level_repository.get_level_distribution()
            
            # Calculate statistics
            total_users = User.objects.count()
            users_with_levels = sum(level_distribution.values())
            
            # Average level
            if level_distribution:
                avg_level = sum(level * count for level, count in level_distribution.items()) / users_with_levels
            else:
                avg_level = 0
            
            # Max level achieved
            max_level = max(level_distribution.keys()) if level_distribution else 0
            
            return {
                'total_users': total_users,
                'users_with_levels': users_with_levels,
                'level_distribution': level_distribution,
                'average_level': avg_level,
                'max_level_achieved': max_level,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting level progress analytics: {e}")
            raise GamificationServiceError(f"Failed to get level progress analytics: {e}")


class ContestInteractor(BaseInteractor):
    """Interactor for contest-related operations."""
    
    def __init__(self):
        super().__init__()
        self.contest_use_case = ContestUseCase()
        self.contest_repository = ContestCycleRepository()
        self.achievement_repository = UserAchievementRepository()
        self.webhook_service = WebhookService()
    
    def finalize_contest_with_rewards(self, contest_id: str) -> Dict[str, Any]:
        """Finalize contest and distribute rewards."""
        try:
            self.validate_input(contest_id=contest_id)
            
            with transaction.atomic():
                # Get contest
                contest = self.contest_repository.get_by_id(contest_id)
                if not contest:
                    raise GamificationServiceError("Contest not found")
                
                # Calculate rewards
                calculated_rewards = self.contest_use_case.calculate_contest_rewards(contest_id)
                
                # Distribute rewards
                distributed_rewards = []
                for reward_data in calculated_rewards:
                    # Create webhook event for reward distribution
                    webhook_data = {
                        'contest_id': contest_id,
                        'contest_name': contest.name,
                        'user_id': reward_data['user_id'],
                        'username': reward_data['username'],
                        'rank': reward_data['rank'],
                        'reward_type': reward_data['reward_type'],
                        'points_bonus': reward_data['points_bonus'],
                        'reward_title': reward_data['reward_title'],
                        'reward_description': reward_data['reward_description']
                    }
                    
                    self.webhook_service.trigger_webhook_event(
                        event_type=WebhookEventType.CONTEST_REWARD,
                        user_id=reward_data['user_id'],
                        data=webhook_data
                    )
                    
                    distributed_rewards.append(reward_data)
                
                # Update contest status
                contest.status = ContestCycleStatus.COMPLETED
                contest.save()
                
                return {
                    'contest_id': contest_id,
                    'contest_name': contest.name,
                    'total_participants': len(set(r['user_id'] for r in distributed_rewards)),
                    'total_rewards_distributed': len(distributed_rewards),
                    'total_points_awarded': sum(r['points_bonus'] for r in distributed_rewards),
                    'distributed_rewards': distributed_rewards,
                    'finalized_at': timezone.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error finalizing contest with rewards for {contest_id}: {e}")
            raise GamificationServiceError(f"Failed to finalize contest with rewards: {e}")
    
    def generate_contest_leaderboard_snapshot(self, contest_id: str) -> Dict[str, Any]:
        """Generate leaderboard snapshot for contest."""
        try:
            self.validate_input(contest_id=contest_id)
            
            with transaction.atomic():
                # Get contest leaderboard
                leaderboard = self.contest_use_case.get_contest_leaderboard(contest_id)
                
                # Get contest details
                contest = self.contest_repository.get_by_id(contest_id)
                
                # Create snapshot
                snapshot_data = {
                    'contest_id': contest_id,
                    'contest_name': contest.name,
                    'generated_at': timezone.now().isoformat(),
                    'leaderboard': leaderboard,
                    'total_participants': len(leaderboard),
                    'contest_duration': {
                        'start_time': contest.start_time.isoformat(),
                        'end_time': contest.end_time.isoformat(),
                        'duration_hours': (contest.end_time - contest.start_time).total_seconds() / 3600
                    }
                }
                
                # Save snapshot
                snapshot = LeaderboardSnapshot.objects.create(
                    contest_cycle_id=contest_id,
                    scope=LeaderboardScope.CONTEST,
                    status=SnapshotStatus.FINALIZED,
                    snapshot_data=snapshot_data
                )
                
                return {
                    'snapshot_id': str(snapshot.id),
                    'contest_id': contest_id,
                    'contest_name': contest.name,
                    'total_participants': len(leaderboard),
                    'generated_at': snapshot_data['generated_at']
                }
                
        except Exception as e:
            self.logger.error(f"Error generating contest leaderboard snapshot for {contest_id}: {e}")
            raise GamificationServiceError(f"Failed to generate contest leaderboard snapshot: {e}")


class GamificationInteractor(BaseInteractor):
    """Main interactor for comprehensive gamification operations."""
    
    def __init__(self):
        super().__init__()
        self.badge_interactor = BadgeInteractor()
        self.streak_interactor = StreakInteractor()
        self.challenge_interactor = ChallengeInteractor()
        self.level_interactor = LevelInteractor()
        self.contest_interactor = ContestInteractor()
        self.summary_use_case = GamificationSummaryUseCase()
        self.webhook_service = WebhookService()
    
    def process_user_activity(self, user_id: str, activity_type: str, activity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process user activity and trigger appropriate gamification actions."""
        try:
            self.validate_input(user_id=user_id, activity_type=activity_type, activity_data=activity_data)
            
            with transaction.atomic():
                results = {
                    'user_id': user_id,
                    'activity_type': activity_type,
                    'processed_actions': [],
                    'total_points_awarded': 0,
                    'total_badges_awarded': 0,
                    'processed_at': timezone.now().isoformat()
                }
                
                # Process different activity types
                if activity_type == 'login':
                    # Update streak
                    streak_result = self.streak_interactor.update_streak_with_milestones(user_id)
                    if streak_result['was_extended']:
                        results['processed_actions'].append({
                            'type': 'streak_updated',
                            'data': streak_result
                        })
                        results['total_points_awarded'] += streak_result.get('total_milestone_points', 0)
                
                elif activity_type == 'challenge_progress':
                    challenge_id = activity_data.get('challenge_id')
                    increment_amount = activity_data.get('increment_amount', 1)
                    
                    if challenge_id:
                        challenge_result = self.challenge_interactor.complete_challenge_with_rewards(
                            user_id, challenge_id, increment_amount
                        )
                        results['processed_actions'].append({
                            'type': 'challenge_completed',
                            'data': challenge_result
                        })
                        results['total_points_awarded'] += challenge_result.get('bonus_points', 0)
                
                elif activity_type == 'achievement_earned':
                    # Award badges based on achievement
                    badge_result = self.badge_interactor.award_badges_with_notifications(
                        user_id, activity_data.get('metadata', {})
                    )
                    results['processed_actions'].append({
                        'type': 'badges_awarded',
                        'data': badge_result
                    })
                    results['total_badges_awarded'] += badge_result.get('total_awarded', 0)
                    results['total_points_awarded'] += badge_result.get('total_points', 0)
                    
                    # Check for level up
                    level_result = self.level_interactor.process_level_up_with_perks(user_id)
                    if level_result.get('can_level_up'):
                        results['processed_actions'].append({
                            'type': 'level_up',
                            'data': level_result
                        })
                
                # Create webhook event for activity processing
                webhook_data = {
                    'user_id': user_id,
                    'activity_type': activity_type,
                    'activity_data': activity_data,
                    'results': results
                }
                
                self.webhook_service.trigger_webhook_event(
                    event_type=WebhookEventType.USER_ACTIVITY,
                    user_id=user_id,
                    data=webhook_data
                )
                
                return results
                
        except Exception as e:
            self.logger.error(f"Error processing user activity for user {user_id}: {e}")
            raise GamificationServiceError(f"Failed to process user activity: {e}")
    
    def get_comprehensive_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive user gamification profile."""
        try:
            self.validate_input(user_id=user_id)
            
            # Get user summary
            summary = self.summary_use_case.get_user_gamification_summary(user_id)
            
            # Add recommendations
            badge_recommendations = self.badge_interactor.get_user_badge_recommendations(user_id)
            challenge_recommendations = self.challenge_interactor.challenge_use_case.get_challenge_recommendations(user_id)
            
            # Add analytics
            user_stats = UserHelper.get_user_gamification_stats(user_id)
            
            return {
                'user_id': user_id,
                'summary': summary,
                'recommendations': {
                    'badges': badge_recommendations,
                    'challenges': challenge_recommendations
                },
                'analytics': user_stats,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting comprehensive user profile for {user_id}: {e}")
            raise GamificationServiceError(f"Failed to get comprehensive user profile: {e}")
    
    def run_daily_maintenance_tasks(self) -> Dict[str, Any]:
        """Run daily maintenance tasks for gamification system."""
        try:
            maintenance_results = {}
            
            # Process streak expirations
            streak_expirations = self.streak_interactor.process_streak_expirations()
            maintenance_results['streak_expirations'] = streak_expirations
            
            # Process daily challenge reset
            challenge_reset = self.challenge_interactor.process_daily_challenge_reset()
            maintenance_results['challenge_reset'] = challenge_reset
            
            # Get system analytics
            system_stats = self.summary_use_case.get_system_gamification_stats()
            maintenance_results['system_stats'] = system_stats
            
            # Clean up old webhook events
            self.webhook_service.cleanup_old_events()
            
            maintenance_results['maintenance_completed_at'] = timezone.now().isoformat()
            
            return maintenance_results
            
        except Exception as e:
            self.logger.error(f"Error running daily maintenance tasks: {e}")
            raise GamificationServiceError(f"Failed to run daily maintenance tasks: {e}")
    
    def generate_system_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive system health report."""
        try:
            health_report = {
                'generated_at': timezone.now().isoformat(),
                'system_status': 'healthy',
                'alerts': [],
                'metrics': {}
            }
            
            # Check webhook system health
            webhook_health = self.webhook_service.get_system_health()
            health_report['metrics']['webhooks'] = webhook_health
            
            # Check database connectivity
            try:
                User.objects.count()
                health_report['metrics']['database'] = {'status': 'connected', 'response_time': 'fast'}
            except Exception as e:
                health_report['metrics']['database'] = {'status': 'error', 'error': str(e)}
                health_report['system_status'] = 'degraded'
                health_report['alerts'].append('Database connectivity issue')
            
            # Check cache connectivity
            try:
                cache.set('health_check', 'test', 1)
                cache.get('health_check')
                health_report['metrics']['cache'] = {'status': 'connected', 'response_time': 'fast'}
            except Exception as e:
                health_report['metrics']['cache'] = {'status': 'error', 'error': str(e)}
                health_report['system_status'] = 'degraded'
                health_report['alerts'].append('Cache connectivity issue')
            
            # Get system statistics
            system_stats = self.summary_use_case.get_system_gamification_stats()
            health_report['metrics']['gamification'] = system_stats
            
            return health_report
            
        except Exception as e:
            self.logger.error(f"Error generating system health report: {e}")
            raise GamificationServiceError(f"Failed to generate system health report: {e}")


# Interactor factory for creating interactors
class InteractorFactory:
    """Factory for creating interactors."""
    
    @staticmethod
    def create_badge_interactor() -> BadgeInteractor:
        """Create badge interactor."""
        return BadgeInteractor()
    
    @staticmethod
    def create_streak_interactor() -> StreakInteractor:
        """Create streak interactor."""
        return StreakInteractor()
    
    @staticmethod
    def create_challenge_interactor() -> ChallengeInteractor:
        """Create challenge interactor."""
        return ChallengeInteractor()
    
    @staticmethod
    def create_level_interactor() -> LevelInteractor:
        """Create level interactor."""
        return LevelInteractor()
    
    @staticmethod
    def create_contest_interactor() -> ContestInteractor:
        """Create contest interactor."""
        return ContestInteractor()
    
    @staticmethod
    def create_gamification_interactor() -> GamificationInteractor:
        """Create main gamification interactor."""
        return GamificationInteractor()


# Convenience functions for common interactor operations
def process_user_gamification_activity(user_id: str, activity_type: str, activity_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process user gamification activity."""
    interactor = InteractorFactory.create_gamification_interactor()
    return interactor.process_user_activity(user_id, activity_type, activity_data)


def get_user_gamification_profile(user_id: str) -> Dict[str, Any]:
    """Get user's gamification profile."""
    interactor = InteractorFactory.create_gamification_interactor()
    return interactor.get_comprehensive_user_profile(user_id)


def run_gamification_maintenance() -> Dict[str, Any]:
    """Run gamification maintenance tasks."""
    interactor = InteractorFactory.create_gamification_interactor()
    return interactor.run_daily_maintenance_tasks()


def get_gamification_system_health() -> Dict[str, Any]:
    """Get gamification system health report."""
    interactor = InteractorFactory.create_gamification_interactor()
    return interactor.generate_system_health_report()
