"""
Gamification Analytics — Comprehensive analytics tracking and reporting.

This module provides analytics capabilities for the gamification system,
including user behavior tracking, performance metrics, engagement analysis,
and comprehensive reporting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.db.models import Q, F, Func, Value, Case, When, Sum, Count, Avg, Max, Min
from django.utils import timezone

from api.gamification.models import (
    Badge, UserBadge, DailyChallenge, UserDailyChallenge,
    Streak, LevelConfig, ContestCycle, UserAchievement,
    WebhookEndpoint, WebhookEvent, WebhookDelivery
)
from api.gamification.choices import (
    BadgeRarity, BadgeCriteriaType, ChallengeAction,
    ContestCycleStatus, AchievementType
)
from api.gamification.repositories import (
    BadgeRepository, UserBadgeRepository, StreakRepository,
    UserAchievementRepository, WebhookDeliveryRepository
)
from api.gamification.exceptions import GamificationServiceError
from api.gamification.helpers import CacheHelper

User = get_user_model()
logger = logging.getLogger(__name__)


class AnalyticsEvent:
    """Represents an analytics event."""
    
    def __init__(self, event_type: str, user_id: Optional[str] = None,
                 properties: Optional[Dict[str, Any]] = None,
                 timestamp: Optional[datetime] = None):
        self.event_type = event_type
        self.user_id = user_id
        self.properties = properties or {}
        self.timestamp = timestamp or timezone.now()
        self.id = f"{event_type}_{user_id}_{int(self.timestamp.timestamp())}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            'id': self.id,
            'event_type': self.event_type,
            'user_id': self.user_id,
            'properties': self.properties,
            'timestamp': self.timestamp.isoformat()
        }


class AnalyticsTracker:
    """Tracker for gamification analytics events."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.events_cache_key = "gamification_analytics_events"
        self.cache_timeout = 3600  # 1 hour
    
    def track_event(self, event_type: str, user_id: Optional[str] = None,
                   properties: Optional[Dict[str, Any]] = None) -> None:
        """Track an analytics event."""
        try:
            event = AnalyticsEvent(event_type, user_id, properties)
            
            # Store event in cache (in production, this would go to a proper analytics system)
            existing_events = cache.get(self.events_cache_key, [])
            existing_events.append(event.to_dict())
            
            # Keep only recent events (last 1000)
            if len(existing_events) > 1000:
                existing_events = existing_events[-1000:]
            
            cache.set(self.events_cache_key, existing_events, self.cache_timeout)
            
            self.logger.debug(f"Tracked event: {event_type} for user {user_id}")
            
        except Exception as e:
            self.logger.error(f"Error tracking event {event_type}: {e}")
    
    def track_badge_earned(self, user_id: str, badge_id: str, badge_name: str,
                         badge_rarity: str, points_bonus: int) -> None:
        """Track badge earned event."""
        self.track_event('badge_earned', user_id, {
            'badge_id': badge_id,
            'badge_name': badge_name,
            'badge_rarity': badge_rarity,
            'points_bonus': points_bonus
        })
    
    def track_challenge_completed(self, user_id: str, challenge_id: str,
                               challenge_title: str, bonus_points: int) -> None:
        """Track challenge completed event."""
        self.track_event('challenge_completed', user_id, {
            'challenge_id': challenge_id,
            'challenge_title': challenge_title,
            'bonus_points': bonus_points
        })
    
    def track_streak_updated(self, user_id: str, current_days: int,
                           was_extended: bool) -> None:
        """Track streak updated event."""
        self.track_event('streak_updated', user_id, {
            'current_days': current_days,
            'was_extended': was_extended
        })
    
    def track_level_up(self, user_id: str, old_level: int, new_level: int) -> None:
        """Track level up event."""
        self.track_event('level_up', user_id, {
            'old_level': old_level,
            'new_level': new_level
        })
    
    def track_achievement_earned(self, user_id: str, achievement_type: str,
                               points_awarded: int, rank: Optional[int] = None) -> None:
        """Track achievement earned event."""
        self.track_event('achievement_earned', user_id, {
            'achievement_type': achievement_type,
            'points_awarded': points_awarded,
            'rank': rank
        })
    
    def track_contest_participation(self, user_id: str, contest_id: str,
                                  contest_name: str) -> None:
        """Track contest participation event."""
        self.track_event('contest_participation', user_id, {
            'contest_id': contest_id,
            'contest_name': contest_name
        })
    
    def get_events(self, event_type: Optional[str] = None, user_id: Optional[str] = None,
                  limit: int = 100) -> List[Dict[str, Any]]:
        """Get tracked events."""
        try:
            events = cache.get(self.events_cache_key, [])
            
            # Filter events
            filtered_events = events
            if event_type:
                filtered_events = [e for e in filtered_events if e['event_type'] == event_type]
            if user_id:
                filtered_events = [e for e in filtered_events if e['user_id'] == user_id]
            
            # Sort by timestamp (most recent first) and limit
            filtered_events.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return filtered_events[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting events: {e}")
            return []


class UserAnalytics:
    """Analytics for individual users."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tracker = AnalyticsTracker()
    
    def get_user_engagement_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get user engagement summary."""
        try:
            since = timezone.now() - timedelta(days=days)
            
            # Get user's gamification activity
            user_badges = UserBadge.objects.filter(
                user_id=self.user_id,
                earned_at__gte=since
            ).count()
            
            completed_challenges = UserDailyChallenge.objects.filter(
                user_id=self.user_id,
                is_completed=True,
                completed_at__gte=since
            ).count()
            
            achievements = UserAchievement.objects.filter(
                user_id=self.user_id,
                awarded_at__gte=since
            ).count()
            
            # Get streak information
            streak = Streak.objects.filter(user_id=self.user_id).first()
            current_streak = streak.current_days if streak else 0
            longest_streak = streak.longest_days if streak else 0
            
            # Calculate engagement score
            engagement_score = self._calculate_engagement_score(
                user_badges, completed_challenges, achievements, current_streak
            )
            
            return {
                'user_id': self.user_id,
                'period_days': days,
                'badges_earned': user_badges,
                'challenges_completed': completed_challenges,
                'achievements_earned': achievements,
                'current_streak': current_streak,
                'longest_streak': longest_streak,
                'engagement_score': engagement_score,
                'engagement_tier': self._get_engagement_tier(engagement_score),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user engagement summary: {e}")
            return {'error': str(e)}
    
    def get_user_progression_analysis(self) -> Dict[str, Any]:
        """Get user progression analysis."""
        try:
            # Badge progression
            user_badges = UserBadge.objects.filter(user_id=self.user_id).order_by('earned_at')
            badge_progression = []
            for badge in user_badges:
                badge_progression.append({
                    'badge_name': badge.badge.name,
                    'badge_rarity': badge.badge.rarity,
                    'earned_at': badge.earned_at.isoformat(),
                    'points_bonus': badge.badge.points_bonus
                })
            
            # Streak progression
            streak = Streak.objects.filter(user_id=self.user_id).first()
            streak_progression = {
                'current_days': streak.current_days if streak else 0,
                'longest_days': streak.longest_days if streak else 0,
                'last_activity': streak.last_activity_date.isoformat() if streak else None,
                'is_active': streak.is_active if streak else False
            }
            
            # Achievement progression
            achievements = UserAchievement.objects.filter(
                user_id=self.user_id,
                is_awarded=True
            ).order_by('awarded_at')
            
            achievement_progression = []
            for achievement in achievements:
                achievement_progression.append({
                    'achievement_type': achievement.achievement_type,
                    'points_awarded': achievement.points_awarded,
                    'rank': achievement.rank,
                    'awarded_at': achievement.awarded_at.isoformat()
                })
            
            # Calculate progression metrics
            total_points = sum(a['points_awarded'] for a in achievement_progression)
            progression_velocity = self._calculate_progression_velocity(achievement_progression)
            
            return {
                'user_id': self.user_id,
                'badge_progression': badge_progression,
                'streak_progression': streak_progression,
                'achievement_progression': achievement_progression,
                'total_points': total_points,
                'progression_velocity': progression_velocity,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting user progression analysis: {e}")
            return {'error': str(e)}
    
    def get_user_behavior_patterns(self) -> Dict[str, Any]:
        """Analyze user behavior patterns."""
        try:
            # Activity patterns
            recent_activities = self.tracker.get_events(user_id=self.user_id, limit=500)
            
            # Time-based patterns
            hourly_activity = {}
            daily_activity = {}
            
            for activity in recent_activities:
                timestamp = datetime.fromisoformat(activity['timestamp'])
                hour = timestamp.hour
                day = timestamp.strftime('%A')
                
                hourly_activity[hour] = hourly_activity.get(hour, 0) + 1
                daily_activity[day] = daily_activity.get(day, 0) + 1
            
            # Event type patterns
            event_patterns = {}
            for activity in recent_activities:
                event_type = activity['event_type']
                event_patterns[event_type] = event_patterns.get(event_type, 0) + 1
            
            # Identify peak activity times
            peak_hour = max(hourly_activity.items(), key=lambda x: x[1])[0] if hourly_activity else None
            peak_day = max(daily_activity.items(), key=lambda x: x[1])[0] if daily_activity else None
            
            # Calculate consistency score
            consistency_score = self._calculate_consistency_score(hourly_activity, daily_activity)
            
            return {
                'user_id': self.user_id,
                'hourly_activity': hourly_activity,
                'daily_activity': daily_activity,
                'event_patterns': event_patterns,
                'peak_activity_hour': peak_hour,
                'peak_activity_day': peak_day,
                'consistency_score': consistency_score,
                'total_analyzed_events': len(recent_activities),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing user behavior patterns: {e}")
            return {'error': str(e)}
    
    def _calculate_engagement_score(self, badges: int, challenges: int,
                                  achievements: int, streak: int) -> float:
        """Calculate engagement score."""
        # Weight different activities
        badge_weight = 10
        challenge_weight = 5
        achievement_weight = 15
        streak_weight = 2
        
        score = (
            badges * badge_weight +
            challenges * challenge_weight +
            achievements * achievement_weight +
            streak * streak_weight
        )
        
        return min(100.0, score)  # Cap at 100
    
    def _get_engagement_tier(self, score: float) -> str:
        """Get engagement tier based on score."""
        if score >= 80:
            return 'highly_engaged'
        elif score >= 60:
            return 'engaged'
        elif score >= 40:
            return 'moderately_engaged'
        elif score >= 20:
            return 'minimally_engaged'
        else:
            return 'not_engaged'
    
    def _calculate_progression_velocity(self, achievements: List[Dict[str, Any]]) -> float:
        """Calculate progression velocity (achievements per week)."""
        if len(achievements) < 2:
            return 0.0
        
        first_achievement = achievements[0]
        last_achievement = achievements[-1]
        
        first_date = datetime.fromisoformat(first_achievement['awarded_at'])
        last_date = datetime.fromisoformat(last_achievement['awarded_at'])
        
        weeks_elapsed = (last_date - first_date).days / 7.0
        if weeks_elapsed <= 0:
            return 0.0
        
        return len(achievements) / weeks_elapsed
    
    def _calculate_consistency_score(self, hourly_activity: Dict[int, int],
                                   daily_activity: Dict[str, int]) -> float:
        """Calculate consistency score based on activity distribution."""
        if not hourly_activity or not daily_activity:
            return 0.0
        
        # Calculate standard deviation for hourly activity
        hourly_values = list(hourly_activity.values())
        hourly_mean = sum(hourly_values) / len(hourly_values)
        hourly_variance = sum((x - hourly_mean) ** 2 for x in hourly_values) / len(hourly_values)
        hourly_std = hourly_variance ** 0.5
        
        # Calculate standard deviation for daily activity
        daily_values = list(daily_activity.values())
        daily_mean = sum(daily_values) / len(daily_values)
        daily_variance = sum((x - daily_mean) ** 2 for x in daily_values) / len(daily_values)
        daily_std = daily_variance ** 0.5
        
        # Consistency score based on lower standard deviation (more consistent)
        max_possible_std = max(hourly_mean, daily_mean)
        normalized_std = (hourly_std + daily_std) / (2 * max_possible_std) if max_possible_std > 0 else 0
        
        return max(0.0, 100.0 - (normalized_std * 100))


class SystemAnalytics:
    """Analytics for the entire gamification system."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tracker = AnalyticsTracker()
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get system overview analytics."""
        try:
            # User statistics
            total_users = User.objects.count()
            active_users_today = User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=1)
            ).count()
            active_users_week = User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Gamification statistics
            total_badges = Badge.objects.count()
            total_user_badges = UserBadge.objects.count()
            unique_users_with_badges = UserBadge.objects.values('user').distinct().count()
            
            total_challenges = DailyChallenge.objects.count()
            total_user_challenges = UserDailyChallenge.objects.count()
            completed_challenges = UserDailyChallenge.objects.filter(is_completed=True).count()
            
            total_streaks = Streak.objects.count()
            active_streaks = Streak.objects.filter(is_active=True).count()
            
            total_achievements = UserAchievement.objects.count()
            total_points_awarded = UserAchievement.objects.filter(is_awarded=True).aggregate(
                total=Sum('points_awarded')
            )['total'] or 0
            
            # Calculate system health metrics
            badge_adoption_rate = (unique_users_with_badges / total_users * 100) if total_users > 0 else 0
            challenge_completion_rate = (completed_challenges / total_user_challenges * 100) if total_user_challenges > 0 else 0
            streak_participation_rate = (active_streaks / total_users * 100) if total_users > 0 else 0
            
            return {
                'user_statistics': {
                    'total_users': total_users,
                    'active_users_today': active_users_today,
                    'active_users_week': active_users_week,
                    'daily_active_rate': (active_users_today / total_users * 100) if total_users > 0 else 0
                },
                'badge_statistics': {
                    'total_badges': total_badges,
                    'total_user_badges': total_user_badges,
                    'unique_users_with_badges': unique_users_with_badges,
                    'badge_adoption_rate': badge_adoption_rate,
                    'badges_per_user': (total_user_badges / unique_users_with_badges) if unique_users_with_badges > 0 else 0
                },
                'challenge_statistics': {
                    'total_challenges': total_challenges,
                    'total_user_challenges': total_user_challenges,
                    'completed_challenges': completed_challenges,
                    'challenge_completion_rate': challenge_completion_rate
                },
                'streak_statistics': {
                    'total_streaks': total_streaks,
                    'active_streaks': active_streaks,
                    'streak_participation_rate': streak_participation_rate,
                    'average_streak_length': Streak.objects.aggregate(
                        avg=Avg('current_days')
                    )['avg'] or 0
                },
                'achievement_statistics': {
                    'total_achievements': total_achievements,
                    'total_points_awarded': total_points_awarded,
                    'average_points_per_achievement': (total_points_awarded / total_achievements) if total_achievements > 0 else 0
                },
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system overview: {e}")
            return {'error': str(e)}
    
    def get_engagement_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get engagement analytics."""
        try:
            since = timezone.now() - timedelta(days=days)
            
            # Daily engagement metrics
            daily_engagement = []
            for i in range(days):
                date = timezone.now().date() - timedelta(days=i)
                
                # Count activities for this date
                daily_badges = UserBadge.objects.filter(
                    earned_at__date=date
                ).count()
                
                daily_challenges = UserDailyChallenge.objects.filter(
                    completed_at__date=date,
                    is_completed=True
                ).count()
                
                daily_achievements = UserAchievement.objects.filter(
                    awarded_at__date=date,
                    is_awarded=True
                ).count()
                
                daily_engagement.append({
                    'date': date.isoformat(),
                    'badges_earned': daily_badges,
                    'challenges_completed': daily_challenges,
                    'achievements_earned': daily_achievements,
                    'total_activities': daily_badges + daily_challenges + daily_achievements
                })
            
            # Sort by date
            daily_engagement.sort(key=lambda x: x['date'])
            
            # Calculate trends
            total_activities = sum(day['total_activities'] for day in daily_engagement)
            average_daily_activities = total_activities / days
            
            # Peak activity day
            peak_day = max(daily_engagement, key=lambda x: x['total_activities'])
            
            # Engagement distribution
            engagement_distribution = {
                'highly_engaged': 0,
                'engaged': 0,
                'moderately_engaged': 0,
                'minimally_engaged': 0,
                'not_engaged': 0
            }
            
            # This would typically involve calculating engagement scores for all users
            # For now, we'll use a simplified approach
            
            return {
                'period_days': days,
                'daily_engagement': daily_engagement,
                'summary': {
                    'total_activities': total_activities,
                    'average_daily_activities': average_daily_activities,
                    'peak_activity_day': peak_day['date'],
                    'peak_activity_count': peak_day['total_activities']
                },
                'engagement_distribution': engagement_distribution,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting engagement analytics: {e}")
            return {'error': str(e)}
    
    def get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            # Badge performance
            badge_performance = Badge.objects.annotate(
                user_count=Count('userbadge', distinct=True)
            ).order_by('-user_count')[:10]
            
            top_badges = [
                {
                    'badge_name': badge.name,
                    'badge_rarity': badge.rarity,
                    'user_count': badge.user_count,
                    'adoption_rate': (badge.user_count / User.objects.count() * 100) if User.objects.count() > 0 else 0
                }
                for badge in badge_performance
            ]
            
            # Challenge performance
            challenge_performance = DailyChallenge.objects.annotate(
                total_participants=Count('userdailychallenge', distinct=True),
                completed_participants=Count(
                    'userdailychallenge',
                    filter=Q(userdailychallenge__is_completed=True)
                )
            ).order_by('-completed_participants')[:10]
            
            top_challenges = []
            for challenge in challenge_performance:
                completion_rate = (challenge.completed_participants / challenge.total_participants * 100) if challenge.total_participants > 0 else 0
                top_challenges.append({
                    'challenge_title': challenge.title,
                    'target_action': challenge.target_action,
                    'bonus_points': challenge.bonus_points,
                    'total_participants': challenge.total_participants,
                    'completed_participants': challenge.completed_participants,
                    'completion_rate': completion_rate
                })
            
            # User performance leaderboard
            user_performance = UserAchievement.objects.filter(
                is_awarded=True
            ).values('user_id').annotate(
                total_points=Sum('points_awarded'),
                achievement_count=Count('id')
            ).order_by('-total_points')[:10]
            
            top_users = []
            for i, user_data in enumerate(user_performance, 1):
                user = User.objects.get(id=user_data['user_id'])
                top_users.append({
                    'rank': i,
                    'username': user.username,
                    'total_points': user_data['total_points'],
                    'achievement_count': user_data['achievement_count']
                })
            
            return {
                'top_badges': top_badges,
                'top_challenges': top_challenges,
                'top_users': top_users,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting performance analytics: {e}")
            return {'error': str(e)}
    
    def get_retention_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get retention analytics."""
        try:
            # Cohort analysis (simplified)
            cohorts = []
            
            for i in range(7):  # Last 7 cohorts
                cohort_date = timezone.now().date() - timedelta(days=i)
                cohort_users = User.objects.filter(date_joined__date=cohort_date)
                
                if cohort_users.exists():
                    # Calculate retention rates for different periods
                    retention_rates = {}
                    
                    for period in [1, 7, 14, 30]:
                        if period <= days:
                            retention_date = cohort_date + timedelta(days=period)
                            retained_users = cohort_users.filter(
                                last_login__date__lte=retention_date
                            ).count()
                            
                            retention_rate = (retained_users / cohort_users.count() * 100) if cohort_users.count() > 0 else 0
                            retention_rates[f'day_{period}'] = retention_rate
                    
                    cohorts.append({
                        'cohort_date': cohort_date.isoformat(),
                        'cohort_size': cohort_users.count(),
                        'retention_rates': retention_rates
                    })
            
            # Calculate average retention rates
            average_retention = {}
            if cohorts:
                for period in [1, 7, 14, 30]:
                    period_key = f'day_{period}'
                    rates = [c['retention_rates'].get(period_key, 0) for c in cohorts if period_key in c['retention_rates']]
                    average_retention[period_key] = sum(rates) / len(rates) if rates else 0
            
            return {
                'period_days': days,
                'cohorts': cohorts,
                'average_retention_rates': average_retention,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting retention analytics: {e}")
            return {'error': str(e)}


class ReportGenerator:
    """Generator for gamification reports."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.system_analytics = SystemAnalytics()
    
    def generate_daily_report(self, date: Optional[datetime.date] = None) -> Dict[str, Any]:
        """Generate daily gamification report."""
        try:
            report_date = date or timezone.now().date()
            
            # Get daily metrics
            daily_badges = UserBadge.objects.filter(earned_at__date=report_date).count()
            daily_challenges = UserDailyChallenge.objects.filter(
                completed_at__date=report_date,
                is_completed=True
            ).count()
            daily_achievements = UserAchievement.objects.filter(
                awarded_at__date=report_date,
                is_awarded=True
            ).count()
            
            # Get top performers
            top_performers = UserAchievement.objects.filter(
                awarded_at__date=report_date,
                is_awarded=True
            ).values('user_id').annotate(
                daily_points=Sum('points_awarded')
            ).order_by('-daily_points')[:5]
            
            # Get most popular badges
            popular_badges = UserBadge.objects.filter(
                earned_at__date=report_date
            ).values('badge__name').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            return {
                'report_date': report_date.isoformat(),
                'report_type': 'daily',
                'summary': {
                    'badges_earned': daily_badges,
                    'challenges_completed': daily_challenges,
                    'achievements_earned': daily_achievements,
                    'total_activities': daily_badges + daily_challenges + daily_achievements
                },
                'top_performers': [
                    {
                        'username': User.objects.get(id=perf['user_id']).username,
                        'daily_points': perf['daily_points']
                    }
                    for perf in top_performers
                ],
                'popular_badges': [
                    {
                        'badge_name': badge['badge__name'],
                        'count': badge['count']
                    }
                    for badge in popular_badges
                ],
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating daily report: {e}")
            return {'error': str(e)}
    
    def generate_weekly_report(self, start_date: Optional[datetime.date] = None) -> Dict[str, Any]:
        """Generate weekly gamification report."""
        try:
            if start_date is None:
                start_date = timezone.now().date() - timedelta(days=6)
            
            end_date = start_date + timedelta(days=6)
            
            # Get weekly metrics
            weekly_badges = UserBadge.objects.filter(
                earned_at__date__gte=start_date,
                earned_at__date__lte=end_date
            ).count()
            
            weekly_challenges = UserDailyChallenge.objects.filter(
                completed_at__date__gte=start_date,
                completed_at__date__lte=end_date,
                is_completed=True
            ).count()
            
            weekly_achievements = UserAchievement.objects.filter(
                awarded_at__date__gte=start_date,
                awarded_at__date__lte=end_date,
                is_awarded=True
            ).count()
            
            # Get engagement trends
            engagement_trends = []
            for i in range(7):
                date = start_date + timedelta(days=i)
                daily_activities = (
                    UserBadge.objects.filter(earned_at__date=date).count() +
                    UserDailyChallenge.objects.filter(
                        completed_at__date=date,
                        is_completed=True
                    ).count() +
                    UserAchievement.objects.filter(
                        awarded_at__date=date,
                        is_awarded=True
                    ).count()
                )
                
                engagement_trends.append({
                    'date': date.isoformat(),
                    'activities': daily_activities
                })
            
            return {
                'report_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'duration_days': 7
                },
                'report_type': 'weekly',
                'summary': {
                    'badges_earned': weekly_badges,
                    'challenges_completed': weekly_challenges,
                    'achievements_earned': weekly_achievements,
                    'total_activities': weekly_badges + weekly_challenges + weekly_achievements,
                    'average_daily_activities': (weekly_badges + weekly_challenges + weekly_achievements) / 7
                },
                'engagement_trends': engagement_trends,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating weekly report: {e}")
            return {'error': str(e)}
    
    def generate_monthly_report(self, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        """Generate monthly gamification report."""
        try:
            if year is None:
                year = timezone.now().year
            if month is None:
                month = timezone.now().month
            
            start_date = datetime(year, month, 1).date()
            if month == 12:
                end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
            
            # Get monthly metrics
            monthly_badges = UserBadge.objects.filter(
                earned_at__date__gte=start_date,
                earned_at__date__lte=end_date
            ).count()
            
            monthly_challenges = UserDailyChallenge.objects.filter(
                completed_at__date__gte=start_date,
                completed_at__date__lte=end_date,
                is_completed=True
            ).count()
            
            monthly_achievements = UserAchievement.objects.filter(
                awarded_at__date__gte=start_date,
                awarded_at__date__lte=end_date,
                is_awarded=True
            ).count()
            
            # Get user growth
            new_users = User.objects.filter(
                date_joined__date__gte=start_date,
                date_joined__date__lte=end_date
            ).count()
            
            active_users = User.objects.filter(
                last_login__date__gte=start_date,
                last_login__date__lte=end_date
            ).count()
            
            # Get top performers
            top_performers = UserAchievement.objects.filter(
                awarded_at__date__gte=start_date,
                awarded_at__date__lte=end_date,
                is_awarded=True
            ).values('user_id').annotate(
                monthly_points=Sum('points_awarded')
            ).order_by('-monthly_points')[:10]
            
            return {
                'report_period': {
                    'year': year,
                    'month': month,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'duration_days': (end_date - start_date).days + 1
                },
                'report_type': 'monthly',
                'summary': {
                    'badges_earned': monthly_badges,
                    'challenges_completed': monthly_challenges,
                    'achievements_earned': monthly_achievements,
                    'total_activities': monthly_badges + monthly_challenges + monthly_achievements,
                    'new_users': new_users,
                    'active_users': active_users
                },
                'top_performers': [
                    {
                        'username': User.objects.get(id=perf['user_id']).username,
                        'monthly_points': perf['monthly_points']
                    }
                    for perf in top_performers
                ],
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating monthly report: {e}")
            return {'error': str(e)}


# Global instances
analytics_tracker = AnalyticsTracker()
system_analytics = SystemAnalytics()
report_generator = ReportGenerator()


# Convenience functions
def track_gamification_event(event_type: str, user_id: Optional[str] = None,
                           properties: Optional[Dict[str, Any]] = None) -> None:
    """Track a gamification analytics event."""
    analytics_tracker.track_event(event_type, user_id, properties)


def get_user_analytics(user_id: str) -> UserAnalytics:
    """Get analytics for a specific user."""
    return UserAnalytics(user_id)


def get_system_analytics() -> SystemAnalytics:
    """Get system analytics instance."""
    return system_analytics


def generate_report(report_type: str, **kwargs) -> Dict[str, Any]:
    """Generate a gamification report."""
    if report_type == 'daily':
        return report_generator.generate_daily_report(kwargs.get('date'))
    elif report_type == 'weekly':
        return report_generator.generate_weekly_report(kwargs.get('start_date'))
    elif report_type == 'monthly':
        return report_generator.generate_monthly_report(
            kwargs.get('year'),
            kwargs.get('month')
        )
    else:
        raise ValueError(f"Unknown report type: {report_type}")
