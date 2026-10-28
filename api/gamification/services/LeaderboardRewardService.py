"""
Leaderboard Reward Service — Contest reward distribution functionality.

Handles reward creation, distribution, and management for contest cycles.
All operations are atomic and include comprehensive validation.
"""

from __future__ import annotations
from django.db import models

import logging
from typing import Any, List, Optional, Dict, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api.gamification.models import ContestCycle, ContestReward, UserAchievement, LeaderboardSnapshot
from api.gamification.choices import RewardType, AchievementType
from api.gamification.exceptions import (
    GamificationServiceError,
    ContestCycleNotFoundError,
    ContestCycleStateError,
    RewardAlreadyClaimedError,
    UserNotFoundError,
)
from api.gamification.signals import achievement_awarded

logger = logging.getLogger(__name__)
User = get_user_model()


class LeaderboardRewardService:
    """
    Service class for contest reward operations.
    
    Provides methods for creating rewards, distributing them to winners,
    and managing reward fulfillment.
    """
    
    @staticmethod
    def create_contest_reward(
        contest_cycle_id: Any,
        title: str,
        reward_type: str,
        rank_from: int,
        rank_to: int,
        points_bonus: int = 0,
        total_budget: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContestReward:
        """
        Create a new contest reward.
        
        Args:
            contest_cycle_id: Contest cycle identifier
            title: Reward title
            reward_type: Type of reward
            rank_from: Starting rank for this reward
            rank_to: Ending rank for this reward
            points_bonus: Points to award
            total_budget: Total number of times this reward can be issued
            metadata: Additional reward configuration
            
        Returns:
            Created ContestReward instance
            
        Raises:
            ContestCycleNotFoundError: If contest cycle doesn't exist
            ContestCycleStateError: If contest cycle is not in a valid state
            GamificationServiceError: If validation fails
        """
        try:
            contest_cycle = ContestCycle.objects.get(pk=contest_cycle_id)
        except ContestCycle.DoesNotExist:
            raise ContestCycleNotFoundError(f"Contest cycle {contest_cycle_id} not found")
        
        if not title or not title.strip():
            raise GamificationServiceError("title must be a non-empty string")
        
        if reward_type not in RewardType.values:
            raise GamificationServiceError(
                f"Invalid reward_type '{reward_type}'. Valid choices: {RewardType.values}"
            )
        
        if rank_from < 1 or rank_from > rank_to:
            raise GamificationServiceError("rank_from must be >= 1 and <= rank_to")
        
        if rank_to > 1000000:
            raise GamificationServiceError("rank_to cannot exceed 1,000,000")
        
        if points_bonus < 0 or points_bonus > 10000000:
            raise GamificationServiceError("points_bonus must be between 0 and 10,000,000")
        
        if total_budget is not None and total_budget < 1:
            raise GamificationServiceError("total_budget must be >= 1")
        
        with transaction.atomic():
            reward = ContestReward.objects.create(
                contest_cycle=contest_cycle,
                title=title.strip(),
                reward_type=reward_type,
                rank_from=rank_from,
                rank_to=rank_to,
                points_bonus=points_bonus,
                total_budget=total_budget,
                metadata=metadata or {},
            )
            
            logger.info(
                "LeaderboardRewardService.create_contest_reward: created reward=%s for cycle=%s",
                reward.id,
                contest_cycle_id,
            )
            
            return reward
    
    @staticmethod
    def distribute_rewards_for_cycle(
        contest_cycle_id: Any,
        snapshot_id: Optional[Any] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Distribute all rewards for a completed contest cycle.
        
        Args:
            contest_cycle_id: Contest cycle identifier
            snapshot_id: Specific snapshot to use (uses latest if None)
            dry_run: If True, calculate without actually awarding
            
        Returns:
            Dictionary with distribution results
            
        Raises:
            ContestCycleNotFoundError: If contest cycle doesn't exist
            ContestCycleStateError: If contest cycle is not completed
            GamificationServiceError: If no snapshot available or other errors
        """
        try:
            contest_cycle = ContestCycle.objects.get(pk=contest_cycle_id)
        except ContestCycle.DoesNotExist:
            raise ContestCycleNotFoundError(f"Contest cycle {contest_cycle_id} not found")
        
        if contest_cycle.status != "COMPLETED":
            raise ContestCycleStateError(
                f"Contest cycle {contest_cycle_id} must be completed to distribute rewards"
            )
        
        # Get the leaderboard snapshot
        if snapshot_id:
            try:
                snapshot = LeaderboardSnapshot.objects.get(
                    pk=snapshot_id,
                    contest_cycle=contest_cycle,
                    status="FINALIZED"
                )
            except LeaderboardSnapshot.DoesNotExist:
                raise GamificationServiceError(
                    f"Snapshot {snapshot_id} not found or not finalized for cycle {contest_cycle_id}"
                )
        else:
            # Get the latest finalized snapshot
            snapshot = LeaderboardSnapshot.objects.filter(
                contest_cycle=contest_cycle,
                status="FINALIZED"
            ).order_by('-created_at').first()
            
            if not snapshot:
                raise GamificationServiceError(
                    f"No finalized snapshot found for contest cycle {contest_cycle_id}"
                )
        
        # Get all rewards for this cycle
        rewards = ContestReward.objects.filter(contest_cycle=contest_cycle).order_by('rank_from')
        
        if not rewards.exists():
            return {
                "contest_cycle_id": contest_cycle_id,
                "snapshot_id": snapshot.id,
                "total_rewards": 0,
                "total_distributed": 0,
                "distribution_results": [],
                "dry_run": dry_run,
            }
        
        distribution_results = []
        total_distributed = 0
        
        with transaction.atomic():
            for reward in rewards:
                result = LeaderboardRewardService._distribute_single_reward(
                    reward, snapshot, dry_run
                )
                distribution_results.append(result)
                total_distributed += result["distributed_count"]
        
        logger.info(
            "LeaderboardRewardService.distribute_rewards_for_cycle: cycle=%s distributed %d rewards (dry_run=%s)",
            contest_cycle_id,
            total_distributed,
            dry_run,
        )
        
        return {
            "contest_cycle_id": contest_cycle_id,
            "snapshot_id": snapshot.id,
            "total_rewards": rewards.count(),
            "total_distributed": total_distributed,
            "distribution_results": distribution_results,
            "dry_run": dry_run,
        }
    
    @staticmethod
    def _distribute_single_reward(
        reward: ContestReward,
        snapshot: LeaderboardSnapshot,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Distribute a single reward to eligible users.
        
        Args:
            reward: ContestReward instance
            snapshot: LeaderboardSnapshot instance
            dry_run: If True, calculate without actually awarding
            
        Returns:
            Dictionary with distribution results
        """
        if not snapshot.snapshot_data:
            return {
                "reward_id": reward.id,
                "reward_title": reward.title,
                "rank_range": f"{reward.rank_from}-{reward.rank_to}",
                "distributed_count": 0,
                "skipped_count": 0,
                "budget_exhausted": False,
                "errors": [],
            }
        
        # Find users in the rank range
        eligible_users = []
        for entry in snapshot.snapshot_data:
            user_rank = entry.get("rank")
            if user_rank and reward.rank_from <= user_rank <= reward.rank_to:
                eligible_users.append(entry)
        
        distributed_count = 0
        skipped_count = 0
        errors = []
        budget_exhausted = False
        
        for user_entry in eligible_users:
            user_id = user_entry.get("user_id")
            user_rank = user_entry.get("rank")
            
            if not user_id:
                skipped_count += 1
                continue
            
            # Check budget
            if reward.total_budget and reward.issued_count >= reward.total_budget:
                budget_exhausted = True
                break
            
            # Check if user already received this reward
            if UserAchievement.objects.filter(
                user_id=user_id,
                achievement_type=AchievementType.CONTEST_REWARD,
                contest_cycle=reward.contest_cycle,
                metadata__reward_id=reward.id
            ).exists():
                skipped_count += 1
                continue
            
            if dry_run:
                distributed_count += 1
                continue
            
            try:
                # Create user achievement for the reward
                achievement = UserAchievement.objects.create(
                    user_id=user_id,
                    achievement_type=AchievementType.CONTEST_REWARD,
                    title=reward.title,
                    description=f"Awarded for rank {user_rank} in {reward.contest_cycle.name}",
                    points_awarded=reward.points_bonus,
                    rank_at_award=user_rank,
                    contest_cycle=reward.contest_cycle,
                    metadata={
                        "reward_id": reward.id,
                        "reward_type": reward.reward_type,
                        "rank_from": reward.rank_from,
                        "rank_to": reward.rank_to,
                        "snapshot_id": snapshot.id,
                    },
                )
                
                # Award the achievement
                achievement.award(points=reward.points_bonus, rank=user_rank)
                
                # Increment reward issued count
                reward.increment_issued_count()
                
                # Send achievement awarded signal
                achievement_awarded.send(sender=None, achievement=achievement)
                
                distributed_count += 1
                
            except Exception as exc:
                errors.append(f"Failed to award reward to user {user_id}: {exc}")
                skipped_count += 1
                logger.error(
                    "Failed to distribute reward=%s to user=%s: %s",
                    reward.id,
                    user_id,
                    exc,
                )
        
        return {
            "reward_id": reward.id,
            "reward_title": reward.title,
            "reward_type": reward.reward_type,
            "rank_range": f"{reward.rank_from}-{reward.rank_to}",
            "eligible_users": len(eligible_users),
            "distributed_count": distributed_count,
            "skipped_count": skipped_count,
            "budget_exhausted": budget_exhausted,
            "errors": errors,
        }
    
    @staticmethod
    def get_user_rewards(
        user_id: Any,
        contest_cycle_id: Optional[Any] = None,
        reward_type: Optional[str] = None,
        is_awarded: Optional[bool] = True,
    ) -> List[Dict[str, Any]]:
        """
        Get rewards for a specific user.
        
        Args:
            user_id: User identifier
            contest_cycle_id: Filter by specific contest cycle
            reward_type: Filter by reward type
            is_awarded: Filter by awarded status
            
        Returns:
            List of user reward dictionaries
            
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise UserNotFoundError(f"User {user_id} not found")
        
        queryset = UserAchievement.objects.filter(
            user=user,
            achievement_type=AchievementType.CONTEST_REWARD
        ).select_related('contest_cycle')
        
        if contest_cycle_id is not None:
            queryset = queryset.filter(contest_cycle_id=contest_cycle_id)
        
        if reward_type is not None:
            queryset = queryset.filter(metadata__reward_type=reward_type)
        
        if is_awarded is not None:
            queryset = queryset.filter(is_awarded=is_awarded)
        
        rewards = []
        for achievement in queryset.order_by('-created_at'):
            reward_id = achievement.metadata.get("reward_id")
            reward_info = {}
            
            if reward_id:
                try:
                    reward = ContestReward.objects.get(pk=reward_id)
                    reward_info = {
                        "reward_id": reward.id,
                        "reward_title": reward.title,
                        "reward_type": reward.reward_type,
                        "rank_from": reward.rank_from,
                        "rank_to": reward.rank_to,
                        "points_bonus": reward.points_bonus,
                    }
                except ContestReward.DoesNotExist:
                    pass
            
            rewards.append({
                "achievement_id": achievement.id,
                "contest_cycle_id": achievement.contest_cycle_id,
                "contest_cycle_name": achievement.contest_cycle.name if achievement.contest_cycle else None,
                "title": achievement.title,
                "description": achievement.description,
                "points_awarded": achievement.points_awarded,
                "rank_at_award": achievement.rank_at_award,
                "is_awarded": achievement.is_awarded,
                "awarded_at": achievement.awarded_at,
                "metadata": achievement.metadata,
                **reward_info,
            })
        
        return rewards
    
    @staticmethod
    def get_reward_statistics(
        contest_cycle_id: Optional[Any] = None,
        reward_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive reward statistics.
        
        Args:
            contest_cycle_id: Filter by specific contest cycle
            reward_type: Filter by reward type
            
        Returns:
            Dictionary with reward statistics
        """
        queryset = ContestReward.objects.all()
        
        if contest_cycle_id is not None:
            queryset = queryset.filter(contest_cycle_id=contest_cycle_id)
        
        if reward_type is not None:
            queryset = queryset.filter(reward_type=reward_type)
        
        rewards = list(queryset.select_related('contest_cycle'))
        
        stats = {
            "total_rewards": len(rewards),
            "by_type": {},
            "by_contest": {},
            "total_budget": sum(r.total_budget or 0 for r in rewards),
            "total_issued": sum(r.issued_count for r in rewards),
            "total_points_awarded": 0,
            "budget_utilization": 0.0,
        }
        
        # Count by type
        for reward in rewards:
            reward_type_key = reward.reward_type
            if reward_type_key not in stats["by_type"]:
                stats["by_type"][reward_type_key] = {
                    "count": 0,
                    "total_budget": 0,
                    "total_issued": 0,
                }
            stats["by_type"][reward_type_key]["count"] += 1
            stats["by_type"][reward_type_key]["total_budget"] += reward.total_budget or 0
            stats["by_type"][reward_type_key]["total_issued"] += reward.issued_count
        
        # Count by contest
        for reward in rewards:
            contest_key = reward.contest_cycle.name if reward.contest_cycle else "Unknown"
            if contest_key not in stats["by_contest"]:
                stats["by_contest"][contest_key] = {
                    "count": 0,
                    "total_budget": 0,
                    "total_issued": 0,
                }
            stats["by_contest"][contest_key]["count"] += 1
            stats["by_contest"][contest_key]["total_budget"] += reward.total_budget or 0
            stats["by_contest"][contest_key]["total_issued"] += reward.issued_count
        
        # Calculate total points awarded
        if contest_cycle_id:
            points_awarded = UserAchievement.objects.filter(
                contest_cycle_id=contest_cycle_id,
                achievement_type=AchievementType.CONTEST_REWARD,
                is_awarded=True
            ).aggregate(total=models.Sum('points_awarded'))['total'] or 0
        else:
            points_awarded = UserAchievement.objects.filter(
                achievement_type=AchievementType.CONTEST_REWARD,
                is_awarded=True
            ).aggregate(total=models.Sum('points_awarded'))['total'] or 0
        
        stats["total_points_awarded"] = points_awarded
        stats["budget_utilization"] = (
            (stats["total_issued"] / stats["total_budget"] * 100)
            if stats["total_budget"] > 0 else 0.0
        )
        
        return stats
    
    @staticmethod
    def update_reward_budget(
        reward_id: Any,
        total_budget: int,
    ) -> ContestReward:
        """
        Update the total budget for a reward.
        
        Args:
            reward_id: Reward identifier
            total_budget: New total budget
            
        Returns:
            Updated ContestReward instance
            
        Raises:
            GamificationServiceError: If reward doesn't exist or validation fails
        """
        try:
            reward = ContestReward.objects.get(pk=reward_id)
        except ContestReward.DoesNotExist:
            raise GamificationServiceError(f"Reward {reward_id} not found")
        
        if total_budget < reward.issued_count:
            raise GamificationServiceError(
                f"Cannot reduce budget below already issued count ({reward.issued_count})"
            )
        
        reward.total_budget = total_budget
        reward.save(update_fields=['total_budget', 'updated_at'])
        
        logger.info(
            "LeaderboardRewardService.update_reward_budget: updated reward=%s budget to %d",
            reward_id,
            total_budget,
        )
        
        return reward
    
    @staticmethod
    def get_reward_leaderboard(
        contest_cycle_id: Any,
        reward_id: Optional[Any] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get leaderboard of users who received rewards.
        
        Args:
            contest_cycle_id: Contest cycle identifier
            reward_id: Specific reward to filter by
            limit: Maximum number of users to return
            
        Returns:
            List of user reward statistics
        """
        queryset = UserAchievement.objects.filter(
            contest_cycle_id=contest_cycle_id,
            achievement_type=AchievementType.CONTEST_REWARD,
            is_awarded=True
        )
        
        if reward_id is not None:
            queryset = queryset.filter(metadata__reward_id=reward_id)
        
        # Aggregate by user
        user_stats = {}
        for achievement in queryset:
            user_id = achievement.user_id
            if user_id not in user_stats:
                user_stats[user_id] = {
                    "user_id": user_id,
                    "username": achievement.user.username,
                    "total_points": 0,
                    "reward_count": 0,
                    "best_rank": None,
                    "rewards": [],
                }
            
            user_stats[user_id]["total_points"] += achievement.points_awarded or 0
            user_stats[user_id]["reward_count"] += 1
            
            rank = achievement.rank_at_award
            if rank is not None:
                if user_stats[user_id]["best_rank"] is None or rank < user_stats[user_id]["best_rank"]:
                    user_stats[user_id]["best_rank"] = rank
            
            user_stats[user_id]["rewards"].append({
                "achievement_id": achievement.id,
                "title": achievement.title,
                "points": achievement.points_awarded,
                "rank": rank,
                "awarded_at": achievement.awarded_at,
            })
        
        # Sort by total points, then by best rank
        leaderboard = sorted(
            user_stats.values(),
            key=lambda x: (-x["total_points"], x["best_rank"] if x["best_rank"] else float('inf'))
        )
        
        return leaderboard[:limit]
