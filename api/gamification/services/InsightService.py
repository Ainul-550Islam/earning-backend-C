"""
Insight Service - Comprehensive analytics and insights for gamification system.

Handles daily metrics collection, analytics calculations, and reporting.
Integrates with GamificationInsight model and related analytics.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Max, Min, Q, F

from api.gamification.models import (
    GamificationInsight, UserPoints, PointsTransaction, UserAchievement,
    ContestParticipant, Streak, ContestCycle, DailyChallenge, UserDailyChallenge
)
from api.gamification.choices import ContestCycleStatus, ChallengeStatus

logger = logging.getLogger(__name__)
User = get_user_model()


class InsightService:
    """
    Service for collecting and analyzing gamification insights.
    
    Provides methods for daily metrics collection, trend analysis,
    and comprehensive reporting on gamification system performance.
    """

    def __init__(self):
        self.logger = logger

    def collect_daily_insights(self, target_date: Optional[date] = None) -> GamificationInsight:
        """
        Collect daily gamification insights and metrics.
        
        Args:
            target_date: Date to collect insights for (defaults to today)
            
        Returns:
            GamificationInsight: Created or updated insight record
        """
        if target_date is None:
            target_date = timezone.now().date()
        
        # Get or create insight record for the date
        insight, created = GamificationInsight.objects.get_or_create(
            date=target_date,
            defaults={}
        )
        
        # Calculate active users (users who earned points)
        insight.active_users = self._calculate_active_users(target_date)
        
        # Calculate badges awarded
        insight.badges_awarded = self._calculate_badges_awarded(target_date)
        
        # Calculate challenges completed
        insight.challenges_completed = self._calculate_challenges_completed(target_date)
        
        # Calculate total points issued
        insight.total_points_issued = self._calculate_total_points_issued(target_date)
        
        # Calculate contest participants
        insight.contest_participants = self._calculate_contest_participants(target_date)
        
        # Calculate streak milestones
        insight.streak_milestones = self._calculate_streak_milestones(target_date)
        
        insight.save()
        
        action = "created" if created else "updated"
        self.logger.info(
            "%s daily insights for %s: %d active users, %d badges, %d points",
            action.title(), target_date, insight.active_users,
            insight.badges_awarded, insight.total_points_issued
        )
        
        return insight

    def _calculate_active_users(self, target_date: date) -> int:
        """Calculate number of active users for a given date."""
        return PointsTransaction.objects.filter(
            created_at__date=target_date,
            amount__gt=0
        ).values('user').distinct().count()

    def _calculate_badges_awarded(self, target_date: date) -> int:
        """Calculate number of badges awarded for a given date."""
        return UserAchievement.objects.filter(
            created_at__date=target_date
        ).count()

    def _calculate_challenges_completed(self, target_date: date) -> int:
        """Calculate number of challenges completed for a given date."""
        return UserDailyChallenge.objects.filter(
            completed_at__date=target_date,
            status=ChallengeStatus.COMPLETED
        ).count()

    def _calculate_total_points_issued(self, target_date: date) -> int:
        """Calculate total points issued for a given date."""
        result = PointsTransaction.objects.filter(
            created_at__date=target_date,
            amount__gt=0
        ).aggregate(total=Sum('amount'))
        return result['total'] or 0

    def _calculate_contest_participants(self, target_date: date) -> int:
        """Calculate number of contest participants for a given date."""
        return ContestParticipant.objects.filter(
            joined_at__date=target_date
        ).count()

    def _calculate_streak_milestones(self, target_date: date) -> int:
        """Calculate number of streak milestones reached for a given date."""
        milestone_days = [7, 14, 30, 60, 90, 180, 365]
        
        return Streak.objects.filter(
            updated_at__date=target_date,
            current_days__in=milestone_days
        ).count()

    def get_summary(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get comprehensive summary for a date range.
        
        Args:
            start_date: Start date for summary
            end_date: End date for summary
            
        Returns:
            Dict with comprehensive summary data
        """
        insights = GamificationInsight.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        if not insights.exists():
            return {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': (end_date - start_date).days + 1
                },
                'total_metrics': {
                    'active_users': 0,
                    'badges_awarded': 0,
                    'challenges_completed': 0,
                    'total_points_issued': 0,
                    'contest_participants': 0,
                    'streak_milestones': 0
                },
                'daily_averages': {
                    'active_users': 0,
                    'badges_awarded': 0,
                    'challenges_completed': 0,
                    'total_points_issued': 0,
                    'contest_participants': 0,
                    'streak_milestones': 0
                },
                'trends': {},
                'top_performing_days': []
            }
        
        # Calculate totals
        totals = insights.aggregate(
            total_active_users=Sum('active_users'),
            total_badges_awarded=Sum('badges_awarded'),
            total_challenges_completed=Sum('challenges_completed'),
            total_points_issued=Sum('total_points_issued'),
            total_contest_participants=Sum('contest_participants'),
            total_streak_milestones=Sum('streak_milestones')
        )
        
        # Calculate averages
        days_count = insights.count()
        averages = {
            'active_users': round((totals['total_active_users'] or 0) / days_count, 2),
            'badges_awarded': round((totals['total_badges_awarded'] or 0) / days_count, 2),
            'challenges_completed': round((totals['total_challenges_completed'] or 0) / days_count, 2),
            'total_points_issued': round((totals['total_points_issued'] or 0) / days_count, 2),
            'contest_participants': round((totals['total_contest_participants'] or 0) / days_count, 2),
            'streak_milestones': round((totals['total_streak_milestones'] or 0) / days_count, 2),
        }
        
        # Calculate trends (comparison with previous period)
        previous_start = start_date - timedelta(days=(end_date - start_date).days + 1)
        previous_end = start_date - timedelta(days=1)
        trends = self._calculate_trends(start_date, end_date, previous_start, previous_end)
        
        # Find top performing days
        top_days = insights.order_by('-total_points_issued')[:5]
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days_count
            },
            'total_metrics': {
                'active_users': totals['total_active_users'] or 0,
                'badges_awarded': totals['total_badges_awarded'] or 0,
                'challenges_completed': totals['total_challenges_completed'] or 0,
                'total_points_issued': totals['total_points_issued'] or 0,
                'contest_participants': totals['total_contest_participants'] or 0,
                'streak_milestones': totals['total_streak_milestones'] or 0
            },
            'daily_averages': averages,
            'trends': trends,
            'top_performing_days': [
                {
                    'date': insight.date.isoformat(),
                    'points_issued': insight.total_points_issued,
                    'active_users': insight.active_users,
                    'badges_awarded': insight.badges_awarded
                }
                for insight in top_days
            ],
            'engagement_metrics': self._calculate_engagement_metrics(insights)
        }

    def _calculate_trends(self, current_start: date, current_end: date, 
                         previous_start: date, previous_end: date) -> Dict[str, Any]:
        """Calculate trend comparisons between current and previous periods."""
        current_insights = GamificationInsight.objects.filter(
            date__gte=current_start,
            date__lte=current_end
        )
        
        previous_insights = GamificationInsight.objects.filter(
            date__gte=previous_start,
            date__lte=previous_end
        )
        
        if not previous_insights.exists():
            return {'status': 'no_previous_data'}
        
        current_totals = current_insights.aggregate(
            active_users=Sum('active_users'),
            badges_awarded=Sum('badges_awarded'),
            challenges_completed=Sum('challenges_completed'),
            total_points_issued=Sum('total_points_issued')
        )
        
        previous_totals = previous_insights.aggregate(
            active_users=Sum('active_users'),
            badges_awarded=Sum('badges_awarded'),
            challenges_completed=Sum('challenges_completed'),
            total_points_issued=Sum('total_points_issued')
        )
        
        trends = {}
        for metric in ['active_users', 'badges_awarded', 'challenges_completed', 'total_points_issued']:
            current_val = current_totals[metric] or 0
            previous_val = previous_totals[metric] or 0
            
            if previous_val == 0:
                change_percent = 100 if current_val > 0 else 0
            else:
                change_percent = ((current_val - previous_val) / previous_val) * 100
            
            trends[metric] = {
                'current': current_val,
                'previous': previous_val,
                'change': current_val - previous_val,
                'change_percent': round(change_percent, 2),
                'trend': 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable'
            }
        
        return trends

    def _calculate_engagement_metrics(self, insights) -> Dict[str, Any]:
        """Calculate detailed engagement metrics."""
        if not insights.exists():
            return {}
        
        # Points per active user
        total_points = insights.aggregate(Sum('total_points_issued'))['total_points_issued__sum'] or 0
        total_active_users = insights.aggregate(Sum('active_users'))['active_users__sum'] or 0
        
        points_per_user = total_points / total_active_users if total_active_users > 0 else 0
        
        # Badge completion rate
        total_badges = insights.aggregate(Sum('badges_awarded'))['badges_awarded__sum'] or 0
        badge_rate = total_badges / total_active_users if total_active_users > 0 else 0
        
        # Challenge completion rate
        total_challenges = insights.aggregate(Sum('challenges_completed'))['challenges_completed__sum'] or 0
        challenge_rate = total_challenges / total_active_users if total_active_users > 0 else 0
        
        # Contest participation rate
        total_participants = insights.aggregate(Sum('contest_participants'))['contest_participants__sum'] or 0
        participation_rate = total_participants / total_active_users if total_active_users > 0 else 0
        
        return {
            'points_per_active_user': round(points_per_user, 2),
            'badges_per_active_user': round(badge_rate, 2),
            'challenges_per_active_user': round(challenge_rate, 2),
            'contest_participation_rate': round(participation_rate, 2),
            'overall_engagement_score': self._calculate_engagement_score(
                points_per_user, badge_rate, challenge_rate, participation_rate
            )
        }

    def _calculate_engagement_score(self, points_per_user: float, 
                                 badge_rate: float, challenge_rate: float, 
                                 participation_rate: float) -> float:
        """Calculate overall engagement score (0-100)."""
        # Normalize each metric to 0-25 points
        points_score = min(25, points_per_user / 10)  # 10 points per user = max score
        badge_score = min(25, badge_rate * 5)  # 5 badges per user = max score
        challenge_score = min(25, challenge_rate * 2)  # 2 challenges per user = max score
        participation_score = min(25, participation_rate * 10)  # 10% participation = max score
        
        return round(points_score + badge_score + challenge_score + participation_score, 2)

    def get_user_analytics(self, user, days: int = 30) -> Dict[str, Any]:
        """
        Get analytics for a specific user.
        
        Args:
            user: User instance or ID
            days: Number of days to analyze
            
        Returns:
            Dict with user analytics
        """
        # Convert user ID to User instance if needed
        if isinstance(user, (str, int)):
            try:
                user = User.objects.get(pk=user)
            except User.DoesNotExist:
                return {}
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Points analytics
        points_earned = PointsTransaction.objects.filter(
            user=user,
            created_at__gte=start_date,
            amount__gt=0
        ).aggregate(
            total=Sum('amount'),
            count=Count('id'),
            avg=Avg('amount')
        )
        
        points_lost = PointsTransaction.objects.filter(
            user=user,
            created_at__gte=start_date,
            amount__lt=0
        ).aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Badges earned
        badges_earned = UserAchievement.objects.filter(
            user=user,
            created_at__gte=start_date
        ).count()
        
        # Challenges completed
        challenges_completed = UserDailyChallenge.objects.filter(
            user=user,
            completed_at__gte=start_date,
            status=ChallengeStatus.COMPLETED
        ).count()
        
        # Contest participation
        contest_participations = ContestParticipant.objects.filter(
            user=user,
            joined_at__gte=start_date
        ).count()
        
        # Current streak
        try:
            current_streak = Streak.objects.get(user=user)
            streak_info = {
                'current_days': current_streak.current_days,
                'longest_days': current_streak.longest_days,
                'is_active': current_streak.is_active
            }
        except Streak.DoesNotExist:
            streak_info = {
                'current_days': 0,
                'longest_days': 0,
                'is_active': False
            }
        
        # Activity pattern
        daily_activity = self._get_user_daily_activity(user, days)
        
        return {
            'user_id': str(user.id),
            'period_days': days,
            'points': {
                'earned': points_earned['total'] or 0,
                'earned_transactions': points_earned['count'] or 0,
                'average_per_transaction': round(points_earned['avg'] or 0, 2),
                'lost': abs(points_lost['total'] or 0),
                'lost_transactions': points_lost['count'] or 0,
                'net': (points_earned['total'] or 0) + (points_lost['total'] or 0)
            },
            'achievements': {
                'badges_earned': badges_earned,
                'challenges_completed': challenges_completed,
                'contest_participations': contest_participations
            },
            'streak': streak_info,
            'activity_pattern': daily_activity,
            'engagement_score': self._calculate_user_engagement_score(
                points_earned['total'] or 0, badges_earned, 
                challenges_completed, contest_participations
            )
        }

    def _get_user_daily_activity(self, user, days: int) -> List[Dict[str, Any]]:
        """Get daily activity pattern for a user."""
        start_date = timezone.now() - timedelta(days=days)
        
        # Group transactions by date
        daily_points = PointsTransaction.objects.filter(
            user=user,
            created_at__gte=start_date
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            points_earned=Sum('amount', filter=Q(amount__gt=0)),
            points_lost=Sum('amount', filter=Q(amount__lt=0)),
            transaction_count=Count('id')
        ).order_by('day')
        
        return [
            {
                'date': day['day'].isoformat(),
                'points_earned': day['points_earned'] or 0,
                'points_lost': abs(day['points_lost'] or 0),
                'transaction_count': day['transaction_count']
            }
            for day in daily_points
        ]

    def _calculate_user_engagement_score(self, points: int, badges: int, 
                                      challenges: int, contests: int) -> float:
        """Calculate engagement score for a user (0-100)."""
        # Normalize each metric to 0-25 points
        points_score = min(25, points / 100)  # 100 points = max score
        badge_score = min(25, badges * 5)  # 5 badges = max score
        challenge_score = min(25, challenges * 2)  # 2 challenges = max score
        contest_score = min(25, contests * 10)  # 1 contest = max score
        
        return round(points_score + badge_score + challenge_score + contest_score, 2)

    def get_leaderboard_insights(self, days: int = 7) -> Dict[str, Any]:
        """
        Get insights about leaderboard performance.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict with leaderboard insights
        """
        start_date = timezone.now() - timedelta(days=days)
        
        # Top performers
        top_performers = UserPoints.objects.filter(
            updated_at__gte=start_date
        ).select_related('user').order_by('-total_points')[:10]
        
        # Most improved users
        most_improved = self._get_most_improved_users(start_date)
        
        # Points distribution
        points_distribution = self._get_points_distribution()
        
        return {
            'period_days': days,
            'top_performers': [
                {
                    'user_id': str(up.user.id),
                    'username': getattr(up.user, 'username', str(up.user.id)),
                    'total_points': up.total_points,
                    'lifetime_points': up.lifetime_points,
                    'monthly_points': up.points_this_month,
                    'weekly_points': up.points_this_week
                }
                for up in top_performers
            ],
            'most_improved': most_improved,
            'points_distribution': points_distribution,
            'participation_metrics': self._get_participation_metrics(start_date)
        }

    def _get_most_improved_users(self, start_date: datetime) -> List[Dict[str, Any]]:
        """Get users with most points improvement in the period."""
        # Calculate points gained in the period
        points_gained = PointsTransaction.objects.filter(
            created_at__gte=start_date,
            amount__gt=0
        ).values('user').annotate(
            gained=Sum('amount')
        ).order_by('-gained')[:10]
        
        improved_users = []
        for item in points_gained:
            try:
                user = User.objects.get(id=item['user'])
                user_points = UserPoints.objects.get(user=user)
                
                improved_users.append({
                    'user_id': str(user.id),
                    'username': getattr(user, 'username', str(user.id)),
                    'points_gained': item['gained'] or 0,
                    'current_total': user_points.total_points,
                    'improvement_percentage': round(
                        ((item['gained'] or 0) / max(1, user_points.total_points - (item['gained'] or 0))) * 100, 2
                    )
                })
            except (User.DoesNotExist, UserPoints.DoesNotExist):
                continue
        
        return improved_users

    def _get_points_distribution(self) -> Dict[str, Any]:
        """Get distribution of points across users."""
        users_with_points = UserPoints.objects.all()
        
        if not users_with_points.exists():
            return {'ranges': [], 'percentiles': {}}
        
        total_users = users_with_points.count()
        
        # Define point ranges
        ranges = [
            {'name': '0-100', 'min': 0, 'max': 100},
            {'name': '101-500', 'min': 101, 'max': 500},
            {'name': '501-1000', 'min': 501, 'max': 1000},
            {'name': '1001-5000', 'min': 1001, 'max': 5000},
            {'name': '5000+', 'min': 5001, 'max': 999999}
        ]
        
        distribution = []
        for range_def in ranges:
            count = users_with_points.filter(
                total_points__gte=range_def['min'],
                total_points__lte=range_def['max']
            ).count()
            
            percentage = (count / total_users) * 100 if total_users > 0 else 0
            
            distribution.append({
                'range': range_def['name'],
                'count': count,
                'percentage': round(percentage, 2)
            })
        
        # Calculate percentiles
        points_values = list(users_with_points.values_list('total_points', flat=True).order_by('total_points'))
        
        percentiles = {}
        for percentile in [25, 50, 75, 90, 95, 99]:
            if points_values:
                index = int((percentile / 100) * len(points_values))
                percentiles[f'p{percentile}'] = points_values[min(index, len(points_values) - 1)]
            else:
                percentiles[f'p{percentile}'] = 0
        
        return {
            'ranges': distribution,
            'percentiles': percentiles,
            'total_users': total_users
        }

    def _get_participation_metrics(self, start_date: datetime) -> Dict[str, Any]:
        """Get participation metrics for the period."""
        # Contest participation
        contest_participants = ContestParticipant.objects.filter(
            joined_at__gte=start_date
        ).count()
        
        total_users = User.objects.count()
        
        # Challenge completion
        challenge_completions = UserDailyChallenge.objects.filter(
            completed_at__gte=start_date,
            status=ChallengeStatus.COMPLETED
        ).count()
        
        # Badge earning
        badges_earned = UserAchievement.objects.filter(
            created_at__gte=start_date
        ).count()
        
        return {
            'contest_participation_rate': round(
                (contest_participants / total_users * 100) if total_users > 0 else 0, 2
            ),
            'challenges_completed': challenge_completions,
            'badges_earned': badges_earned,
            'active_users': PointsTransaction.objects.filter(
                created_at__gte=start_date,
                amount__gt=0
            ).values('user').distinct().count()
        }

    def generate_report(self, report_type: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Generate comprehensive reports.
        
        Args:
            report_type: Type of report (daily, weekly, monthly, custom)
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Dict with comprehensive report data
        """
        base_summary = self.get_summary(start_date, end_date)
        
        if report_type == 'daily':
            return base_summary
        elif report_type == 'weekly':
            return self._generate_weekly_report(start_date, end_date, base_summary)
        elif report_type == 'monthly':
            return self._generate_monthly_report(start_date, end_date, base_summary)
        else:
            return self._generate_custom_report(start_date, end_date, base_summary)

    def _generate_weekly_report(self, start_date: date, end_date: date, 
                               base_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Generate weekly report with additional metrics."""
        # Add weekly-specific metrics
        weekly_metrics = {
            'weekday_performance': self._get_weekday_performance(start_date, end_date),
            'week_over_week_growth': self._get_week_over_week_growth(start_date, end_date)
        }
        
        return {**base_summary, 'weekly_metrics': weekly_metrics}

    def _generate_monthly_report(self, start_date: date, end_date: date, 
                                base_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Generate monthly report with additional metrics."""
        # Add monthly-specific metrics
        monthly_metrics = {
            'weekly_breakdown': self._get_weekly_breakdown(start_date, end_date),
            'month_over_month_growth': self._get_month_over_month_growth(start_date, end_date)
        }
        
        return {**base_summary, 'monthly_metrics': monthly_metrics}

    def _generate_custom_report(self, start_date: date, end_date: date, 
                               base_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Generate custom report with all available metrics."""
        # Add comprehensive metrics
        custom_metrics = {
            'leaderboard_insights': self.get_leaderboard_insights(
                days=(end_date - start_date).days + 1
            ),
            'user_segmentation': self._get_user_segmentation(),
            'retention_metrics': self._get_retention_metrics(start_date, end_date)
        }
        
        return {**base_summary, 'custom_metrics': custom_metrics}

    def _get_weekday_performance(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get performance breakdown by weekday."""
        insights = GamificationInsight.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        )
        
        weekday_stats = {}
        for insight in insights:
            weekday = insight.date.strftime('%A')
            if weekday not in weekday_stats:
                weekday_stats[weekday] = {
                    'active_users': [],
                    'points_issued': [],
                    'badges_awarded': []
                }
            
            weekday_stats[weekday]['active_users'].append(insight.active_users)
            weekday_stats[weekday]['points_issued'].append(insight.total_points_issued)
            weekday_stats[weekday]['badges_awarded'].append(insight.badges_awarded)
        
        # Calculate averages for each weekday
        for weekday, stats in weekday_stats.items():
            stats['avg_active_users'] = round(sum(stats['active_users']) / len(stats['active_users']), 2)
            stats['avg_points_issued'] = round(sum(stats['points_issued']) / len(stats['points_issued']), 2)
            stats['avg_badges_awarded'] = round(sum(stats['badges_awarded']) / len(stats['badges_awarded']), 2)
        
        return weekday_stats

    def _get_week_over_week_growth(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate week-over-week growth metrics."""
        # This would compare current week with previous week
        # Implementation depends on specific requirements
        return {'status': 'not_implemented'}

    def _get_weekly_breakdown(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get weekly breakdown for monthly report."""
        # Implementation for weekly breakdown
        return []

    def _get_month_over_month_growth(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate month-over-month growth metrics."""
        # Implementation for month-over-month comparison
        return {'status': 'not_implemented'}

    def _get_user_segmentation(self) -> Dict[str, Any]:
        """Segment users based on engagement levels."""
        # Implementation for user segmentation
        return {'status': 'not_implemented'}

    def _get_retention_metrics(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Calculate user retention metrics."""
        # Implementation for retention metrics
        return {'status': 'not_implemented'}
