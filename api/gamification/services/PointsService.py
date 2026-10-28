"""
Points Service - Comprehensive points management for gamification system.

Handles awarding, deducting, and tracking user points with full audit trail.
Integrates with UserPoints and PointsTransaction models.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.exceptions import ValidationError

from api.gamification.models import UserPoints, PointsTransaction, GamificationConfig
from api.gamification.signals import points_awarded, points_deducted
from api.gamification.exceptions import InsufficientPointsError

logger = logging.getLogger(__name__)
User = get_user_model()


class PointsService:
    """
    Service for managing user points in the gamification system.
    
    Provides methods for awarding, deducting, and querying points
    with full audit trail and business logic enforcement.
    """

    def __init__(self):
        self.logger = logger

    def award_points(
        self,
        user,
        amount: int,
        source: str = "manual",
        source_id: str = "",
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> PointsTransaction:
        """
        Award points to a user.
        
        Args:
            user: User instance or ID
            amount: Positive integer amount of points to award
            source: Source of points (offer, referral, streak, challenge, contest, manual)
            source_id: Reference ID from source system
            description: Human-readable description
            metadata: Additional metadata for the transaction
            
        Returns:
            PointsTransaction: Created transaction record
            
        Raises:
            ValueError: If amount is not positive
            ValidationError: If source is invalid
        """
        if amount <= 0:
            raise ValueError("Points amount must be positive")
        
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                raise ValueError(f"User with ID {user} does not exist")
        
        # Validate source
        valid_sources = ["offer", "referral", "streak", "challenge", "contest", "manual", "bonus", "penalty"]
        if source not in valid_sources:
            raise ValidationError(f"Invalid source. Must be one of: {', '.join(valid_sources)}")
        
        # Get or create UserPoints record
        user_points, created = UserPoints.objects.get_or_create(
            user=user,
            defaults={
                'total_points': 0,
                'lifetime_points': 0,
                'points_this_month': 0,
                'points_this_week': 0,
            }
        )
        
        with transaction.atomic():
            # Update user points
            user_points.total_points += amount
            user_points.lifetime_points += amount
            user_points.points_this_month += amount
            user_points.points_this_week += amount
            user_points.save()
            
            # Create transaction record
            transaction_record = PointsTransaction.objects.create(
                user=user,
                amount=amount,
                source=source,
                source_id=source_id,
                description=description or f"Awarded {amount} points from {source}",
                balance_after=user_points.total_points,
            )
            
            # Add metadata if provided
            if metadata:
                transaction_record.audit_metadata.update(metadata)
                transaction_record.save(update_fields=['audit_metadata'])
            
            # Send signal
            points_awarded.send(
                sender=self.__class__,
                user=user,
                amount=amount,
                source=source,
                transaction=transaction_record,
                metadata=metadata
            )
            
            self.logger.info(
                "Awarded %d points to user %s from %s. New balance: %d",
                amount, user.id, source, user_points.total_points
            )
            
            return transaction_record

    def deduct_points(
        self,
        user,
        amount: int,
        source: str = "manual",
        source_id: str = "",
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        allow_negative: bool = False
    ) -> PointsTransaction:
        """
        Deduct points from a user.
        
        Args:
            user: User instance or ID
            amount: Positive integer amount of points to deduct
            source: Source of deduction (penalty, refund, manual, etc.)
            source_id: Reference ID from source system
            description: Human-readable description
            metadata: Additional metadata for the transaction
            allow_negative: Whether to allow negative balance
            
        Returns:
            PointsTransaction: Created transaction record
            
        Raises:
            ValueError: If amount is not positive
            InsufficientPointsError: If insufficient balance and allow_negative=False
        """
        if amount <= 0:
            raise ValueError("Points amount must be positive")
        
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                raise ValueError(f"User with ID {user} does not exist")
        
        # Get UserPoints record
        try:
            user_points = UserPoints.objects.get(user=user)
        except UserPoints.DoesNotExist:
            # Create with zero balance if doesn't exist
            user_points = UserPoints.objects.create(
                user=user,
                total_points=0,
                lifetime_points=0,
                points_this_month=0,
                points_this_week=0,
            )
        
        # Check sufficient balance
        if not allow_negative and user_points.total_points < amount:
            raise InsufficientPointsError(
                f"Insufficient points. Available: {user_points.total_points}, Required: {amount}"
            )
        
        with transaction.atomic():
            # Update user points
            user_points.total_points -= amount
            # Note: lifetime_points never decreases
            user_points.save()
            
            # Create transaction record (negative amount)
            transaction_record = PointsTransaction.objects.create(
                user=user,
                amount=-amount,
                source=source,
                source_id=source_id,
                description=description or f"Deducted {amount} points for {source}",
                balance_after=user_points.total_points,
            )
            
            # Add metadata if provided
            if metadata:
                transaction_record.audit_metadata.update(metadata)
                transaction_record.save(update_fields=['audit_metadata'])
            
            # Send signal
            points_deducted.send(
                sender=self.__class__,
                user=user,
                amount=amount,
                source=source,
                transaction=transaction_record,
                metadata=metadata
            )
            
            self.logger.info(
                "Deducted %d points from user %s for %s. New balance: %d",
                amount, user.id, source, user_points.total_points
            )
            
            return transaction_record

    def get_balance(self, user) -> int:
        """
        Get current points balance for a user.
        
        Args:
            user: User instance or ID
            
        Returns:
            int: Current total points balance
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return 0
        
        try:
            user_points = UserPoints.objects.get(user=user)
            return user_points.total_points
        except UserPoints.DoesNotExist:
            return 0

    def get_history(
        self,
        user,
        limit: int = 50,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[PointsTransaction]:
        """
        Get points transaction history for a user.
        
        Args:
            user: User instance or ID
            limit: Maximum number of transactions to return
            source: Filter by source type
            start_date: Filter transactions from this date
            end_date: Filter transactions until this date
            
        Returns:
            List[PointsTransaction]: List of transactions
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return []
        
        queryset = PointsTransaction.objects.filter(user=user)
        
        # Apply filters
        if source:
            queryset = queryset.filter(source=source)
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Order by most recent and limit
        return queryset.order_by('-created_at')[:limit]

    def apply_multiplier(self, user, base_points: int) -> int:
        """
        Apply tier-based multiplier to base points.
        
        Args:
            user: User instance or ID
            base_points: Base points before multiplier
            
        Returns:
            int: Points after applying multiplier
        """
        if base_points <= 0:
            return base_points
        
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return base_points
        
        # Get user's level from UserAchievement or similar
        # This is a simplified version - you might want to integrate with LevelUpService
        try:
            from api.gamification.models import UserAchievement
            user_level = UserAchievement.objects.filter(user=user).count()
        except:
            user_level = 0
        
        # Apply multipliers based on level
        multipliers = {
            0: 1.0,    # Level 0: 1x
            1: 1.1,    # Level 1: 1.1x
            2: 1.2,    # Level 2: 1.2x
            3: 1.3,    # Level 3: 1.3x
            4: 1.5,    # Level 4: 1.5x
            5: 1.7,    # Level 5: 1.7x
            10: 2.0,   # Level 10: 2x
            20: 2.5,   # Level 20: 2.5x
            30: 3.0,   # Level 30: 3x
        }
        
        # Find the highest applicable multiplier
        applicable_multiplier = 1.0
        for level_threshold, multiplier in sorted(multipliers.items(), reverse=True):
            if user_level >= level_threshold:
                applicable_multiplier = multiplier
                break
        
        final_points = int(base_points * applicable_multiplier)
        
        self.logger.debug(
            "Applied %.1fx multiplier for user %s (level %d): %d -> %d points",
            applicable_multiplier, user.id, user_level, base_points, final_points
        )
        
        return final_points

    def expire_old_points(self, user, days_to_keep: int = 365) -> int:
        """
        Expire old points based on retention policy.
        
        Args:
            user: User instance or ID
            days_to_keep: Number of days to keep points before expiry
            
        Returns:
            int: Number of points expired
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return 0
        
        # Check if points expiry is enabled
        try:
            config = GamificationConfig.get_for_tenant(user.tenant_id if hasattr(user, 'tenant_id') else 'default')
            if not config.is_points_expiry_enabled:
                return 0
            expiry_days = config.points_expiry_days or days_to_keep
        except:
            expiry_days = days_to_keep
        
        cutoff_date = timezone.now() - timedelta(days=expiry_days)
        
        # Find old transactions
        old_transactions = PointsTransaction.objects.filter(
            user=user,
            created_at__lt=cutoff_date,
            amount__gt=0  # Only expire earned points, not deductions
        )
        
        total_expired = 0
        for transaction in old_transactions:
            expire_amount = min(transaction.amount, self.get_balance(user))
            if expire_amount > 0:
                self.deduct_points(
                    user=user,
                    amount=expire_amount,
                    source="expiry",
                    source_id=str(transaction.id),
                    description=f"Expired points from {transaction.created_at.date()}"
                )
                total_expired += expire_amount
        
        if total_expired > 0:
            self.logger.info(
                "Expired %d points for user %s (older than %d days)",
                total_expired, user.id, expiry_days
            )
        
        return total_expired

    def get_summary(self, user) -> Dict[str, Any]:
        """
        Get comprehensive points summary for a user.
        
        Args:
            user: User instance or ID
            
        Returns:
            Dict with points summary including current balance, history, etc.
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return {
                    'user_id': user,
                    'total_points': 0,
                    'lifetime_points': 0,
                    'points_this_month': 0,
                    'points_this_week': 0,
                    'monthly_rank': None,
                    'weekly_rank': None,
                    'recent_transactions': [],
                    'points_by_source': {},
                }
        
        try:
            user_points = UserPoints.objects.get(user=user)
        except UserPoints.DoesNotExist:
            return {
                'user_id': user.id,
                'total_points': 0,
                'lifetime_points': 0,
                'points_this_month': 0,
                'points_this_week': 0,
                'monthly_rank': None,
                'weekly_rank': None,
                'recent_transactions': [],
                'points_by_source': {},
            }
        
        # Get recent transactions
        recent_transactions = list(self.get_history(user, limit=10))
        
        # Calculate points by source
        points_by_source = {}
        for transaction in recent_transactions:
            source = transaction.source
            if source not in points_by_source:
                points_by_source[source] = {'earned': 0, 'deducted': 0}
            
            if transaction.amount > 0:
                points_by_source[source]['earned'] += transaction.amount
            else:
                points_by_source[source]['deducted'] += abs(transaction.amount)
        
        return {
            'user_id': user.id,
            'total_points': user_points.total_points,
            'lifetime_points': user_points.lifetime_points,
            'points_this_month': user_points.points_this_month,
            'points_this_week': user_points.points_this_week,
            'monthly_rank': user_points.monthly_rank,
            'weekly_rank': user_points.weekly_rank,
            'recent_transactions': [
                {
                    'id': str(t.id),
                    'amount': t.amount,
                    'source': t.source,
                    'description': t.description,
                    'balance_after': t.balance_after,
                    'created_at': t.created_at.isoformat(),
                }
                for t in recent_transactions
            ],
            'points_by_source': points_by_source,
        }

    def reset_periodic_points(self) -> Dict[str, int]:
        """
        Reset monthly and weekly points counters.
        
        This should be called periodically (e.g., daily cron job)
        to reset counters at the appropriate boundaries.
        
        Returns:
            Dict with counts of reset operations
        """
        today = timezone.now().date()
        reset_counts = {'monthly': 0, 'weekly': 0}
        
        # Reset monthly points on first day of month
        if today.day == 1:
            monthly_resets = UserPoints.objects.filter(
                points_this_month__gt=0
            ).update(points_this_month=0)
            reset_counts['monthly'] = monthly_resets
            
            if monthly_resets > 0:
                self.logger.info("Reset monthly points for %d users", monthly_resets)
        
        # Reset weekly points on Monday
        if today.weekday() == 0:  # Monday is 0 in Python
            weekly_resets = UserPoints.objects.filter(
                points_this_week__gt=0
            ).update(points_this_week=0)
            reset_counts['weekly'] = weekly_resets
            
            if weekly_resets > 0:
                self.logger.info("Reset weekly points for %d users", weekly_resets)
        
        return reset_counts

    def bulk_award_points(
        self,
        users: List,
        amount: int,
        source: str = "bulk",
        source_id: str = "",
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[PointsTransaction]:
        """
        Award points to multiple users efficiently.
        
        Args:
            users: List of User instances or IDs
            amount: Points amount to award to each user
            source: Source of points
            source_id: Reference ID
            description: Description
            metadata: Additional metadata
            
        Returns:
            List of created transactions
        """
        transactions = []
        
        with transaction.atomic():
            for user in users:
                try:
                    tx = self.award_points(
                        user=user,
                        amount=amount,
                        source=source,
                        source_id=source_id,
                        description=description,
                        metadata=metadata
                    )
                    transactions.append(tx)
                except Exception as e:
                    self.logger.error(
                        "Failed to award %d points to user %s: %s",
                        amount, str(user), str(e)
                    )
        
        self.logger.info(
            "Bulk awarded %d points to %d users from %s",
            amount, len(transactions), source
        )
        
        return transactions

    def get_leaderboard(self, limit: int = 100, period: str = "total") -> List[Dict[str, Any]]:
        """
        Get points leaderboard.
        
        Args:
            limit: Maximum number of users to return
            period: Period for leaderboard (total, monthly, weekly)
            
        Returns:
            List of leaderboard entries with user info and points
        """
        if period == "monthly":
            queryset = UserPoints.objects.all().order_by('-points_this_month')
            points_field = 'points_this_month'
        elif period == "weekly":
            queryset = UserPoints.objects.all().order_by('-points_this_week')
            points_field = 'points_this_week'
        else:
            queryset = UserPoints.objects.all().order_by('-total_points')
            points_field = 'total_points'
        
        leaderboard = []
        rank = 1
        
        for user_points in queryset[:limit]:
            leaderboard.append({
                'rank': rank,
                'user_id': str(user_points.user.id),
                'username': getattr(user_points.user, 'username', str(user_points.user.id)),
                'points': getattr(user_points, points_field),
                'total_points': user_points.total_points,
                'lifetime_points': user_points.lifetime_points,
            })
            rank += 1
        
        return leaderboard
