"""
Contest Service - Comprehensive contest management for gamification system.

Handles contest cycles, participants, leaderboards, and reward distribution.
Integrates with ContestCycle, ContestParticipant, and related models.
"""

from __future__ import annotations
from django.db.models import Max
from django.db.models import Min

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, F, Count, Sum, Avg

from api.gamification.models import (
    ContestCycle, ContestParticipant, ContestReward, LeaderboardSnapshot,
    UserPoints, PointsTransaction
)
from api.gamification.choices import ContestCycleStatus, RewardType
from api.gamification.signals import (
    contest_started, contest_ended, user_joined_contest,
    leaderboard_position_changed
)
from api.gamification.exceptions import ContestCycleStateError

logger = logging.getLogger(__name__)
User = get_user_model()


class ContestService:
    """
    Service for managing contest cycles and participants.
    
    Provides methods for creating contests, managing participants,
    updating rankings, and distributing rewards.
    """

    def __init__(self):
        self.logger = logger

    def create_cycle(
        self,
        name: str,
        start_date: datetime,
        end_date: datetime,
        max_winners: int = 10,
        points_multiplier: float = 1.0,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        created_by=None
    ) -> ContestCycle:
        """
        Create a new contest cycle.
        
        Args:
            name: Contest name
            start_date: Start date and time
            end_date: End date and time
            max_winners: Maximum number of winners
            points_multiplier: Points multiplier for this contest
            description: Contest description
            metadata: Additional configuration
            created_by: User who created the contest
            
        Returns:
            ContestCycle: Created contest cycle
            
        Raises:
            ValidationError: If dates are invalid or conflict with existing contests
        """
        # Validate dates
        if start_date >= end_date:
            raise ValidationError("Start date must be before end date")
        
        # Check for conflicting active contests
        conflicting = ContestCycle.objects.filter(
            status=ContestCycleStatus.ACTIVE,
            start_date__lt=end_date,
            end_date__gt=start_date
        ).exists()
        
        if conflicting:
            raise ValidationError("Contest dates conflict with an existing active contest")
        
        with transaction.atomic():
            contest = ContestCycle.objects.create(
                name=name,
                start_date=start_date,
                end_date=end_date,
                points_multiplier=points_multiplier,
                description=description,
                metadata=metadata or {},
                created_by=created_by
            )
            
            self.logger.info(
                "Created contest cycle '%s' (%s) from %s to %s",
                name, contest.id, start_date, end_date
            )
            
            return contest

    def activate_cycle(self, cycle_id: str) -> ContestCycle:
        """
        Activate a contest cycle.
        
        Args:
            cycle_id: Contest cycle ID
            
        Returns:
            ContestCycle: Activated contest cycle
            
        Raises:
            ContestCycleStateError: If contest cannot be activated
        """
        try:
            contest = ContestCycle.objects.get(id=cycle_id)
        except ContestCycle.DoesNotExist:
            raise ValueError(f"Contest cycle with ID {cycle_id} does not exist")
        
        # Check if any other contest is currently active
        active_contest = ContestCycle.objects.filter(
            status=ContestCycleStatus.ACTIVE
        ).first()
        
        if active_contest and active_contest.id != contest.id:
            raise ValidationError("Another contest is already active")
        
        contest.transition_to(ContestCycleStatus.ACTIVE)
        
        # Send signal
        contest_started.send(
            sender=self.__class__,
            contest=contest
        )
        
        self.logger.info("Activated contest cycle '%s'", contest.name)
        return contest

    def end_cycle(self, cycle_id: str, finalize_rewards: bool = True) -> ContestCycle:
        """
        End a contest cycle and optionally finalize rewards.
        
        Args:
            cycle_id: Contest cycle ID
            finalize_rewards: Whether to automatically distribute rewards
            
        Returns:
            ContestCycle: Ended contest cycle
        """
        try:
            contest = ContestCycle.objects.get(id=cycle_id)
        except ContestCycle.DoesNotExist:
            raise ValueError(f"Contest cycle with ID {cycle_id} does not exist")
        
        if contest.status != ContestCycleStatus.ACTIVE:
            raise ContestCycleStateError("Only active contests can be ended")
        
        # Generate final leaderboard snapshot
        self.generate_leaderboard_snapshot(contest)
        
        # Mark contest as completed
        contest.transition_to(ContestCycleStatus.COMPLETED)
        
        # Send signal
        contest_ended.send(
            sender=self.__class__,
            contest=contest
        )
        
        # Distribute rewards if requested
        if finalize_rewards:
            self.distribute_rewards(contest.id)
        
        self.logger.info("Ended contest cycle '%s'", contest.name)
        return contest

    def add_participant(self, user, cycle_id: str) -> ContestParticipant:
        """
        Add a user to a contest cycle.
        
        Args:
            user: User instance or ID
            cycle_id: Contest cycle ID
            
        Returns:
            ContestParticipant: Created participant record
            
        Raises:
            ValidationError: If user cannot join the contest
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                raise ValueError(f"User with ID {user} does not exist")
        
        try:
            contest = ContestCycle.objects.get(id=cycle_id)
        except ContestCycle.DoesNotExist:
            raise ValueError(f"Contest cycle with ID {cycle_id} does not exist")
        
        # Check if contest is active
        if contest.status != ContestCycleStatus.ACTIVE:
            raise ValidationError("Can only join active contests")
        
        # Check if contest has expired
        if timezone.now() >= contest.end_date:
            raise ValidationError("Contest has already ended")
        
        # Check max participants limit
        if contest.max_participants:
            current_participants = ContestParticipant.objects.filter(
                contest_cycle=contest
            ).count()
            if current_participants >= contest.max_participants:
                raise ValidationError("Contest has reached maximum participants")
        
        # Check if user is already participating
        if ContestParticipant.objects.filter(
            contest_cycle=contest,
            user=user
        ).exists():
            raise ValidationError("User is already participating in this contest")
        
        with transaction.atomic():
            participant = ContestParticipant.objects.create(
                contest_cycle=contest,
                user=user
            )
            
            # Send signal
            user_joined_contest.send(
                sender=self.__class__,
                contest=contest,
                user=user,
                participant=participant
            )
            
            self.logger.info(
                "User %s joined contest '%s'",
                user.id, contest.name
            )
            
            return participant

    def update_participant_points(self, user, cycle_id: str, points: int) -> None:
        """
        Update points for a contest participant.
        
        Args:
            user: User instance or ID
            cycle_id: Contest cycle ID
            points: Points to add (must be positive)
        """
        if points <= 0:
            raise ValueError("Points must be positive")
        
        try:
            participant = ContestParticipant.objects.get(
                contest_cycle_id=cycle_id,
                user=user
            )
        except ContestParticipant.DoesNotExist:
            raise ValueError("User is not participating in this contest")
        
        old_rank = participant.current_rank
        
        # Add points to participant
        participant.add_points(points)
        
        # Recalculate rankings
        self.recalculate_rankings(participant.contest_cycle)
        
        # Check if rank changed and send signal
        participant.refresh_from_db()
        new_rank = participant.current_rank
        
        if old_rank != new_rank:
            leaderboard_position_changed.send(
                sender=self.__class__,
                contest=participant.contest_cycle,
                user=user,
                participant=participant,
                old_rank=old_rank,
                new_rank=new_rank
            )

    def get_leaderboard(self, cycle_id: str, top_n: int = 50) -> List[Dict[str, Any]]:
        """
        Get current leaderboard for a contest cycle.
        
        Args:
            cycle_id: Contest cycle ID
            top_n: Number of top participants to return
            
        Returns:
            List of leaderboard entries
        """
        try:
            contest = ContestCycle.objects.get(id=cycle_id)
        except ContestCycle.DoesNotExist:
            raise ValueError(f"Contest cycle with ID {cycle_id} does not exist")
        
        participants = ContestParticipant.objects.filter(
            contest_cycle=contest,
            is_disqualified=False
        ).order_by('-current_points', 'joined_at')
        
        leaderboard = []
        rank = 1
        
        for participant in participants[:top_n]:
            leaderboard.append({
                'rank': rank,
                'user_id': str(participant.user.id),
                'username': getattr(participant.user, 'username', str(participant.user.id)),
                'points': participant.current_points,
                'joined_at': participant.joined_at.isoformat(),
                'days_in_contest': participant.days_in_contest,
            })
            rank += 1
        
        return leaderboard

    def recalculate_rankings(self, contest: ContestCycle) -> None:
        """
        Recalculate rankings for all participants in a contest.
        
        Args:
            contest: ContestCycle instance
        """
        participants = ContestParticipant.objects.filter(
            contest_cycle=contest,
            is_disqualified=False
        ).order_by('-current_points', 'joined_at')
        
        rank = 1
        for participant in participants:
            old_rank = participant.current_rank
            participant.update_rank(rank)
            
            # Send signal for rank changes
            if old_rank != rank:
                leaderboard_position_changed.send(
                    sender=self.__class__,
                    contest=contest,
                    user=participant.user,
                    participant=participant,
                    old_rank=old_rank,
                    new_rank=rank
                )
            
            rank += 1

    def distribute_rewards(self, cycle_id: str) -> Dict[str, Any]:
        """
        Distribute rewards to contest winners.
        
        Args:
            cycle_id: Contest cycle ID
            
        Returns:
            Dict with reward distribution summary
        """
        try:
            contest = ContestCycle.objects.get(id=cycle_id)
        except ContestCycle.DoesNotExist:
            raise ValueError(f"Contest cycle with ID {cycle_id} does not exist")
        
        if contest.status != ContestCycleStatus.COMPLETED:
            raise ValidationError("Can only distribute rewards for completed contests")
        
        # Get top participants
        winners = ContestParticipant.objects.filter(
            contest_cycle=contest,
            is_disqualified=False,
            current_rank__isnull=False
        ).order_by('current_rank')
        
        rewards_distributed = []
        total_reward_value = 0
        
        for winner in winners:
            # Get reward configuration for this rank
            try:
                reward = ContestReward.objects.get(
                    contest_cycle=contest,
                    rank=winner.current_rank
                )
            except ContestReward.DoesNotExist:
                # No reward configured for this rank
                continue
            
            # Award reward based on type
            if reward.reward_type == RewardType.POINTS:
                from .PointsService import PointsService
                points_service = PointsService()
                
                tx = points_service.award_points(
                    user=winner.user,
                    amount=reward.reward_value,
                    source="contest",
                    source_id=str(contest.id),
                    description=f"Contest reward: {contest.name} - Rank #{winner.current_rank}"
                )
                
                rewards_distributed.append({
                    'user_id': str(winner.user.id),
                    'rank': winner.current_rank,
                    'reward_type': 'points',
                    'amount': reward.reward_value,
                    'transaction_id': str(tx.id)
                })
                total_reward_value += reward.reward_value
            
            elif reward.reward_type == RewardType.BADGE:
                # Award badge logic here
                rewards_distributed.append({
                    'user_id': str(winner.user.id),
                    'rank': winner.current_rank,
                    'reward_type': 'badge',
                    'badge_id': str(reward.reward_value) if isinstance(reward.reward_value, str) else None,
                })
        
        summary = {
            'contest_id': str(contest.id),
            'contest_name': contest.name,
            'total_winners': len(rewards_distributed),
            'total_reward_value': total_reward_value,
            'rewards': rewards_distributed
        }
        
        self.logger.info(
            "Distributed rewards for contest '%s': %d winners, total value: %d",
            contest.name, len(rewards_distributed), total_reward_value
        )
        
        return summary

    def generate_leaderboard_snapshot(self, contest: ContestCycle) -> LeaderboardSnapshot:
        """
        Generate a leaderboard snapshot for a contest.
        
        Args:
            contest: ContestCycle instance
            
        Returns:
            LeaderboardSnapshot: Created snapshot
        """
        from api.gamification.models import LeaderboardSnapshot, SnapshotStatus
        
        # Create snapshot record
        snapshot = LeaderboardSnapshot.objects.create(
            contest_cycle=contest,
            scope="contest",
            status=SnapshotStatus.PENDING
        )
        
        try:
            # Get current leaderboard data
            leaderboard = self.get_leaderboard(str(contest.id), top_n=1000)
            
            # Format for snapshot
            snapshot_data = []
            for entry in leaderboard:
                snapshot_data.append({
                    'rank': entry['rank'],
                    'user_id': entry['user_id'],
                    'display_name': entry['username'],
                    'points': entry['points'],
                    'delta_rank': None,  # Could calculate from previous snapshot
                })
            
            # Update snapshot
            snapshot.snapshot_data = snapshot_data
            snapshot.status = SnapshotStatus.FINALIZED
            snapshot.generated_at = timezone.now()
            snapshot.save()
            
            self.logger.info(
                "Generated leaderboard snapshot for contest '%s': %d entries",
                contest.name, len(snapshot_data)
            )
            
        except Exception as e:
            snapshot.status = SnapshotStatus.FAILED
            snapshot.error_message = str(e)
            snapshot.save()
            
            self.logger.error(
                "Failed to generate leaderboard snapshot for contest '%s': %s",
                contest.name, str(e)
            )
            raise
        
        return snapshot

    def get_user_participation(self, user, cycle_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's participation details for a contest.
        
        Args:
            user: User instance or ID
            cycle_id: Contest cycle ID
            
        Returns:
            Dict with participation details or None if not participating
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return None
        
        try:
            participant = ContestParticipant.objects.get(
                contest_cycle_id=cycle_id,
                user=user
            )
        except ContestParticipant.DoesNotExist:
            return None
        
        # Get user's rank in the full leaderboard
        leaderboard = self.get_leaderboard(cycle_id, top_n=1000)
        user_rank = None
        for entry in leaderboard:
            if entry['user_id'] == str(user.id):
                user_rank = entry['rank']
                break
        
        return {
            'participant_id': str(participant.id),
            'joined_at': participant.joined_at.isoformat(),
            'current_points': participant.current_points,
            'current_rank': participant.current_rank,
            'global_rank': user_rank,
            'is_disqualified': participant.is_disqualified,
            'days_in_contest': participant.days_in_contest,
        }

    def get_contest_stats(self, cycle_id: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a contest.
        
        Args:
            cycle_id: Contest cycle ID
            
        Returns:
            Dict with contest statistics
        """
        try:
            contest = ContestCycle.objects.get(id=cycle_id)
        except ContestCycle.DoesNotExist:
            raise ValueError(f"Contest cycle with ID {cycle_id} does not exist")
        
        participants = ContestParticipant.objects.filter(contest_cycle=contest)
        
        # Basic stats
        total_participants = participants.count()
        active_participants = participants.filter(is_disqualified=False).count()
        disqualified_participants = participants.filter(is_disqualified=True).count()
        
        # Points stats
        points_stats = participants.aggregate(
            total_points=Sum('current_points'),
            avg_points=Avg('current_points'),
            max_points=Max('current_points'),
            min_points=Min('current_points')
        )
        
        # Participation over time
        participation_by_day = participants.extra(
            select={'day': 'date(joined_at)'}
        ).values('day').annotate(count=Count('id')).order_by('day')
        
        return {
            'contest_id': str(contest.id),
            'contest_name': contest.name,
            'status': contest.status,
            'start_date': contest.start_date.isoformat(),
            'end_date': contest.end_date.isoformat(),
            'total_participants': total_participants,
            'active_participants': active_participants,
            'disqualified_participants': disqualified_participants,
            'points_stats': {
                'total': points_stats['total_points'] or 0,
                'average': points_stats['avg_points'] or 0,
                'maximum': points_stats['max_points'] or 0,
                'minimum': points_stats['min_points'] or 0,
            },
            'participation_by_day': list(participation_by_day),
            'leaderboard_top_10': self.get_leaderboard(cycle_id, top_n=10),
        }

    def cleanup_expired_contests(self) -> int:
        """
        Archive contests that have ended more than 30 days ago.
        
        Returns:
            Number of contests archived
        """
        cutoff_date = timezone.now() - timedelta(days=30)
        
        expired_contests = ContestCycle.objects.filter(
            status=ContestCycleStatus.COMPLETED,
            end_date__lt=cutoff_date
        )
        
        archived_count = 0
        for contest in expired_contests:
            contest.transition_to(ContestCycleStatus.ARCHIVED)
            archived_count += 1
        
        if archived_count > 0:
            self.logger.info("Archived %d expired contests", archived_count)
        
        return archived_count

    def get_user_contest_history(self, user, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get contest participation history for a user.
        
        Args:
            user: User instance or ID
            limit: Maximum number of contests to return
            
        Returns:
            List of contest participation records
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return []
        
        participations = ContestParticipant.objects.filter(
            user=user
        ).select_related('contest_cycle').order_by('-joined_at')[:limit]
        
        history = []
        for participation in participations:
            contest = participation.contest_cycle
            history.append({
                'contest_id': str(contest.id),
                'contest_name': contest.name,
                'status': contest.status,
                'joined_at': participation.joined_at.isoformat(),
                'final_points': participation.current_points,
                'final_rank': participation.current_rank,
                'is_disqualified': participation.is_disqualified,
                'duration_days': contest.duration_days,
            })
        
        return history
