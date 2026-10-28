# =============================================================================
# auto_mod/analytics.py
# =============================================================================

"""
Analytics and reporting for auto moderation system.
Provides comprehensive analytics, insights, and reporting capabilities.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min, Q, F
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal,
    ModerationQueue, TaskBot, AutoApprovalRule, ContentSignal
)
from .selectors import SelectorFactory
from .exceptions import ModerationError

logger = logging.getLogger(__name__)

User = get_user_model()


class AnalyticsEngine:
    """
    Analytics engine for auto moderation system.
    """
    
    def __init__(self):
        self.selectors = SelectorFactory()
        self.cache_timeout = 900  # 15 minutes
    
    def get_dashboard_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive dashboard analytics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dashboard analytics data
        """
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            return {
                'overview': self._get_overview_stats(start_date),
                'submissions': self._get_submission_analytics(start_date),
                'decisions': self._get_decision_analytics(start_date),
                'appeals': self._get_appeal_analytics(start_date),
                'queue': self._get_queue_analytics(),
                'bots': self._get_bot_analytics(),
                'performance': self._get_performance_analytics(start_date),
                'trends': self._get_trend_analytics(start_date),
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as exc:
            logger.error(f"Get dashboard analytics failed: {exc}")
            raise ModerationError(f"Failed to get analytics: {exc}")
    
    def _get_overview_stats(self, start_date: datetime) -> Dict[str, Any]:
        """Get overview statistics."""
        try:
            # Submission stats
            total_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).count()
            
            pending_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date,
                status='pending'
            ).count()
            
            # Decision stats
            total_decisions = ModerationDecision.objects.filter(
                decided_at__gte=start_date
            ).count()
            
            automated_decisions = ModerationDecision.objects.filter(
                decided_at__gte=start_date,
                is_automated=True
            ).count()
            
            # Appeal stats
            total_appeals = ModerationAppeal.objects.filter(
                created_at__gte=start_date
            ).count()
            
            approved_appeals = ModerationAppeal.objects.filter(
                created_at__gte=start_date,
                status='approved'
            ).count()
            
            # Calculate rates
            automation_rate = (automated_decisions / total_decisions * 100) if total_decisions > 0 else 0
            appeal_success_rate = (approved_appeals / total_appeals * 100) if total_appeals > 0 else 0
            
            return {
                'total_submissions': total_submissions,
                'pending_submissions': pending_submissions,
                'total_decisions': total_decisions,
                'automated_decisions': automated_decisions,
                'total_appeals': total_appeals,
                'approved_appeals': approved_appeals,
                'automation_rate': round(automation_rate, 2),
                'appeal_success_rate': round(appeal_success_rate, 2),
            }
            
        except Exception as exc:
            logger.error(f"Get overview stats failed: {exc}")
            return {}
    
    def _get_submission_analytics(self, start_date: datetime) -> Dict[str, Any]:
        """Get submission analytics."""
        try:
            # Status breakdown
            status_breakdown = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).values('status').annotate(count=Count('id')).order_by('-count')
            
            # Type breakdown
            type_breakdown = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).values('submission_type').annotate(count=Count('id')).order_by('-count')
            
            # Risk score distribution
            risk_distribution = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).aggregate(
                avg_risk_score=Avg('risk_score'),
                max_risk_score=Max('risk_score'),
                min_risk_score=Min('risk_score'),
            )
            
            # Daily submission trends
            daily_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).extra({
                'day': "date(created_at)"
            }).values('day').annotate(count=Count('id')).order_by('day')
            
            # Top flag reasons
            top_flag_reasons = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date,
                flag_reason__isnull=False
            ).values('flag_reason').annotate(count=Count('id')).order_by('-count')[:10]
            
            return {
                'status_breakdown': list(status_breakdown),
                'type_breakdown': list(type_breakdown),
                'risk_distribution': {
                    'average': risk_distribution['avg_risk_score'] or 0,
                    'maximum': risk_distribution['max_risk_score'] or 0,
                    'minimum': risk_distribution['min_risk_score'] or 0,
                },
                'daily_trends': [
                    {
                        'date': item['day'].isoformat(),
                        'count': item['count']
                    }
                    for item in daily_submissions
                ],
                'top_flag_reasons': list(top_flag_reasons),
            }
            
        except Exception as exc:
            logger.error(f"Get submission analytics failed: {exc}")
            return {}
    
    def _get_decision_analytics(self, start_date: datetime) -> Dict[str, Any]:
        """Get decision analytics."""
        try:
            # Decision type breakdown
            decision_breakdown = ModerationDecision.objects.filter(
                decided_at__gte=start_date
            ).values('decision_type').annotate(count=Count('id')).order_by('-count')
            
            # Automated vs manual
            automation_breakdown = ModerationDecision.objects.filter(
                decided_at__gte=start_date
            ).values('is_automated').annotate(count=Count('id'))
            
            # Confidence distribution
            confidence_distribution = ModerationDecision.objects.filter(
                decided_at__gte=start_date
            ).aggregate(
                avg_confidence=Avg('confidence'),
                max_confidence=Max('confidence'),
                min_confidence=Min('confidence'),
            )
            
            # Daily decision trends
            daily_decisions = ModerationDecision.objects.filter(
                decided_at__gte=start_date
            ).extra({
                'day': "date(decided_at)"
            }).values('day').annotate(count=Count('id')).order_by('day')
            
            # Top deciders
            top_deciders = ModerationDecision.objects.filter(
                decided_at__gte=start_date,
                decided_by__isnull=False
            ).values('decided_by__username').annotate(count=Count('id')).order_by('-count')[:10]
            
            return {
                'decision_breakdown': list(decision_breakdown),
                'automation_breakdown': list(automation_breakdown),
                'confidence_distribution': {
                    'average': confidence_distribution['avg_confidence'] or 0,
                    'maximum': confidence_distribution['max_confidence'] or 0,
                    'minimum': confidence_distribution['min_confidence'] or 0,
                },
                'daily_trends': [
                    {
                        'date': item['day'].isoformat(),
                        'count': item['count']
                    }
                    for item in daily_decisions
                ],
                'top_deciders': list(top_deciders),
            }
            
        except Exception as exc:
            logger.error(f"Get decision analytics failed: {exc}")
            return {}
    
    def _get_appeal_analytics(self, start_date: datetime) -> Dict[str, Any]:
        """Get appeal analytics."""
        try:
            # Appeal status breakdown
            status_breakdown = ModerationAppeal.objects.filter(
                created_at__gte=start_date
            ).values('status').annotate(count=Count('id')).order_by('-count')
            
            # Appeal type breakdown
            type_breakdown = ModerationAppeal.objects.filter(
                created_at__gte=start_date
            ).values('appeal_type').annotate(count=Count('id')).order_by('-count')
            
            # Appeal success rate by type
            appeal_success_by_type = ModerationAppeal.objects.filter(
                created_at__gte=start_date
            ).values('appeal_type').annotate(
                total=Count('id'),
                approved=Count('id', filter=Q(status='approved'))
            ).order_by('-total')
            
            # Daily appeal trends
            daily_appeals = ModerationAppeal.objects.filter(
                created_at__gte=start_date
            ).extra({
                'day': "date(created_at)"
            }).values('day').annotate(count=Count('id')).order_by('day')
            
            # Average processing time
            avg_processing_time = ModerationAppeal.objects.filter(
                created_at__gte=start_date,
                reviewed_at__isnull=False
            ).annotate(
                processing_time=F('reviewed_at') - F('created_at')
            ).aggregate(avg_time=Avg('processing_time'))
            
            return {
                'status_breakdown': list(status_breakdown),
                'type_breakdown': list(type_breakdown),
                'success_by_type': [
                    {
                        'appeal_type': item['appeal_type'],
                        'total': item['total'],
                        'approved': item['approved'],
                        'success_rate': round((item['approved'] / item['total'] * 100), 2) if item['total'] > 0 else 0
                    }
                    for item in appeal_success_by_type
                ],
                'daily_trends': [
                    {
                        'date': item['day'].isoformat(),
                        'count': item['count']
                    }
                    for item in daily_appeals
                ],
                'avg_processing_time_hours': (
                    avg_processing_time['avg_time'].total_seconds() / 3600
                    if avg_processing_time['avg_time'] else 0
                ),
            }
            
        except Exception as exc:
            logger.error(f"Get appeal analytics failed: {exc}")
            return {}
    
    def _get_queue_analytics(self) -> Dict[str, Any]:
        """Get queue analytics."""
        try:
            # Queue status breakdown
            status_breakdown = ModerationQueue.objects.all().values('status').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Priority breakdown
            priority_breakdown = ModerationQueue.objects.all().values('priority').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Assignment breakdown
            assignment_breakdown = ModerationQueue.objects.all().aggregate(
                total=Count('id'),
                assigned=Count('id', filter=Q(assigned_to__isnull=False)),
                unassigned=Count('id', filter=Q(assigned_to__isnull=True))
            )
            
            # Overdue items
            overdue_count = ModerationQueue.objects.filter(
                due_date__lt=timezone.now()
            ).count()
            
            # Average time in queue
            avg_queue_time = ModerationQueue.objects.filter(
                status='completed'
            ).annotate(
                queue_time=F('updated_at') - F('created_at')
            ).aggregate(avg_time=Avg('queue_time'))
            
            return {
                'status_breakdown': list(status_breakdown),
                'priority_breakdown': list(priority_breakdown),
                'assignment_breakdown': {
                    'total': assignment_breakdown['total'],
                    'assigned': assignment_breakdown['assigned'],
                    'unassigned': assignment_breakdown['unassigned'],
                    'assignment_rate': round(
                        (assignment_breakdown['assigned'] / assignment_breakdown['total'] * 100), 2
                    ) if assignment_breakdown['total'] > 0 else 0
                },
                'overdue_items': overdue_count,
                'avg_queue_time_hours': (
                    avg_queue_time['avg_time'].total_seconds() / 3600
                    if avg_queue_time['avg_time'] else 0
                ),
            }
            
        except Exception as exc:
            logger.error(f"Get queue analytics failed: {exc}")
            return {}
    
    def _get_bot_analytics(self) -> Dict[str, Any]:
        """Get bot analytics."""
        try:
            # Bot status breakdown
            status_breakdown = TaskBot.objects.all().values('status').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Bot type breakdown
            type_breakdown = TaskBot.objects.all().values('bot_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Performance metrics
            performance_metrics = TaskBot.objects.all().aggregate(
                avg_performance_score=Avg('performance_score'),
                max_performance_score=Max('performance_score'),
                min_performance_score=Min('performance_score'),
            )
            
            # Active vs inactive
            activity_breakdown = TaskBot.objects.all().aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(is_active=True)),
                inactive=Count('id', filter=Q(is_active=False))
            )
            
            return {
                'status_breakdown': list(status_breakdown),
                'type_breakdown': list(type_breakdown),
                'performance_metrics': {
                    'average': performance_metrics['avg_performance_score'] or 0,
                    'maximum': performance_metrics['max_performance_score'] or 0,
                    'minimum': performance_metrics['min_performance_score'] or 0,
                },
                'activity_breakdown': {
                    'total': activity_breakdown['total'],
                    'active': activity_breakdown['active'],
                    'inactive': activity_breakdown['inactive'],
                    'activity_rate': round(
                        (activity_breakdown['active'] / activity_breakdown['total'] * 100), 2
                    ) if activity_breakdown['total'] > 0 else 0
                },
            }
            
        except Exception as exc:
            logger.error(f"Get bot analytics failed: {exc}")
            return {}
    
    def _get_performance_analytics(self, start_date: datetime) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            # Processing time trends
            processing_times = ModerationDecision.objects.filter(
                decided_at__gte=start_date
            ).extra({
                'day': "date(decided_at)"
            }).values('day').annotate(
                avg_processing_time=Avg('processing_time')
            ).order_by('day')
            
            # Throughput metrics
            daily_throughput = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).extra({
                'day': "date(created_at)"
            }).values('day').annotate(
                throughput=Count('id')
            ).order_by('day')
            
            # Error rates
            error_rates = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).extra({
                'day': "date(created_at)"
            }).values('day').annotate(
                total=Count('id'),
                errors=Count('id', filter=Q(status='error'))
            ).order_by('day')
            
            return {
                'processing_time_trends': [
                    {
                        'date': item['day'].isoformat(),
                        'avg_processing_time': item['avg_processing_time'] or 0
                    }
                    for item in processing_times
                ],
                'throughput_trends': [
                    {
                        'date': item['day'].isoformat(),
                        'throughput': item['throughput']
                    }
                    for item in daily_throughput
                ],
                'error_rate_trends': [
                    {
                        'date': item['day'].isoformat(),
                        'total': item['total'],
                        'errors': item['errors'],
                        'error_rate': round((item['errors'] / item['total'] * 100), 2) if item['total'] > 0 else 0
                    }
                    for item in error_rates
                ],
            }
            
        except Exception as exc:
            logger.error(f"Get performance analytics failed: {exc}")
            return {}
    
    def _get_trend_analytics(self, start_date: datetime) -> Dict[str, Any]:
        """Get trend analytics."""
        try:
            # Week-over-week growth
            week_ago = timezone.now() - timedelta(weeks=1)
            two_weeks_ago = timezone.now() - timedelta(weeks=2)
            
            current_week_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=week_ago
            ).count()
            
            previous_week_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=two_weeks_ago,
                created_at__lt=week_ago
            ).count()
            
            week_over_week_growth = (
                ((current_week_submissions - previous_week_submissions) / previous_week_submissions * 100)
                if previous_week_submissions > 0 else 0
            )
            
            # Month-over-month growth
            month_ago = timezone.now() - timedelta(days=30)
            two_months_ago = timezone.now() - timedelta(days=60)
            
            current_month_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=month_ago
            ).count()
            
            previous_month_submissions = SuspiciousSubmission.objects.filter(
                created_at__gte=two_months_ago,
                created_at__lt=month_ago
            ).count()
            
            month_over_month_growth = (
                ((current_month_submissions - previous_month_submissions) / previous_month_submissions * 100)
                if previous_month_submissions > 0 else 0
            )
            
            return {
                'week_over_week_growth': round(week_over_week_growth, 2),
                'month_over_month_growth': round(month_over_month_growth, 2),
                'current_week_submissions': current_week_submissions,
                'previous_week_submissions': previous_week_submissions,
                'current_month_submissions': current_month_submissions,
                'previous_month_submissions': previous_month_submissions,
            }
            
        except Exception as exc:
            logger.error(f"Get trend analytics failed: {exc}")
            return {}
    
    def get_user_analytics(self, user_id: Union[str, int], days: int = 30) -> Dict[str, Any]:
        """
        Get analytics for a specific user.
        
        Args:
            user_id: User ID
            days: Number of days to analyze
            
        Returns:
            User analytics data
        """
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            # User submission stats
            user_submissions = SuspiciousSubmission.objects.filter(
                user_id=user_id,
                created_at__gte=start_date
            )
            
            total_submissions = user_submissions.count()
            approved_submissions = user_submissions.filter(status='approved').count()
            rejected_submissions = user_submissions.filter(status='rejected').count()
            
            # User decision stats (if user is a moderator)
            user_decisions = ModerationDecision.objects.filter(
                decided_by_id=user_id,
                decided_at__gte=start_date
            )
            
            total_decisions = user_decisions.count()
            automated_decisions = user_decisions.filter(is_automated=True).count()
            
            # User appeal stats
            user_appeals = ModerationAppeal.objects.filter(
                user_id=user_id,
                created_at__gte=start_date
            )
            
            total_appeals = user_appeals.count()
            approved_appeals = user_appeals.filter(status='approved').count()
            
            return {
                'user_id': str(user_id),
                'period_days': days,
                'submissions': {
                    'total': total_submissions,
                    'approved': approved_submissions,
                    'rejected': rejected_submissions,
                    'approval_rate': round((approved_submissions / total_submissions * 100), 2) if total_submissions > 0 else 0,
                },
                'decisions': {
                    'total': total_decisions,
                    'automated': automated_decisions,
                    'manual': total_decisions - automated_decisions,
                    'automation_rate': round((automated_decisions / total_decisions * 100), 2) if total_decisions > 0 else 0,
                },
                'appeals': {
                    'total': total_appeals,
                    'approved': approved_appeals,
                    'success_rate': round((approved_appeals / total_appeals * 100), 2) if total_appeals > 0 else 0,
                },
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as exc:
            logger.error(f"Get user analytics failed: {exc}")
            raise ModerationError(f"Failed to get user analytics: {exc}")
    
    def get_content_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get content-specific analytics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Content analytics data
        """
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            # Content signal analytics
            signal_analytics = ContentSignal.objects.filter(
                created_at__gte=start_date
            ).values('signal_type', 'severity').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence')
            ).order_by('-count')
            
            # Risk score distribution
            risk_distribution = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).extra({
                'risk_bucket': "CASE "
                              "WHEN risk_score < 0.3 THEN 'low' "
                              "WHEN risk_score < 0.6 THEN 'medium' "
                              "WHEN risk_score < 0.8 THEN 'high' "
                              "ELSE 'critical' END"
            }).values('risk_bucket').annotate(count=Count('id')).order_by('risk_bucket')
            
            # Content type performance
            content_type_performance = SuspiciousSubmission.objects.filter(
                created_at__gte=start_date
            ).values('submission_type').annotate(
                total=Count('id'),
                approved=Count('id', filter=Q(status='approved')),
                rejected=Count('id', filter=Q(status='rejected')),
                avg_risk_score=Avg('risk_score'),
                avg_confidence=Avg('ai_confidence')
            ).order_by('-total')
            
            return {
                'signal_analytics': list(signal_analytics),
                'risk_distribution': list(risk_distribution),
                'content_type_performance': [
                    {
                        'content_type': item['submission_type'],
                        'total': item['total'],
                        'approved': item['approved'],
                        'rejected': item['rejected'],
                        'approval_rate': round((item['approved'] / item['total'] * 100), 2) if item['total'] > 0 else 0,
                        'avg_risk_score': item['avg_risk_score'] or 0,
                        'avg_confidence': item['avg_confidence'] or 0,
                    }
                    for item in content_type_performance
                ],
                'period_days': days,
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as exc:
            logger.error(f"Get content analytics failed: {exc}")
            raise ModerationError(f"Failed to get content analytics: {exc}")
    
    def export_analytics_report(self, report_type: str, days: int = 30, 
                              format: str = 'json') -> Dict[str, Any]:
        """
        Export analytics report in specified format.
        
        Args:
            report_type: Type of report (dashboard, user, content)
            days: Number of days to analyze
            format: Export format (json, csv, excel)
            
        Returns:
            Exported report data
        """
        try:
            if report_type == 'dashboard':
                data = self.get_dashboard_analytics(days)
            elif report_type == 'content':
                data = self.get_content_analytics(days)
            else:
                raise ValueError(f"Unknown report type: {report_type}")
            
            # Add export metadata
            export_data = {
                'report_type': report_type,
                'period_days': days,
                'format': format,
                'exported_at': timezone.now().isoformat(),
                'data': data
            }
            
            return export_data
            
        except Exception as exc:
            logger.error(f"Export analytics report failed: {exc}")
            raise ModerationError(f"Failed to export report: {exc}")


# Global analytics engine
analytics_engine = AnalyticsEngine()


# Utility functions
def get_dashboard_analytics(days: int = 30) -> Dict[str, Any]:
    """Get dashboard analytics."""
    return analytics_engine.get_dashboard_analytics(days)


def get_user_analytics(user_id: Union[str, int], days: int = 30) -> Dict[str, Any]:
    """Get user analytics."""
    return analytics_engine.get_user_analytics(user_id, days)


def get_content_analytics(days: int = 30) -> Dict[str, Any]:
    """Get content analytics."""
    return analytics_engine.get_content_analytics(days)


def export_analytics_report(report_type: str, days: int = 30, 
                          format: str = 'json') -> Dict[str, Any]:
    """Export analytics report."""
    return analytics_engine.export_analytics_report(report_type, days, format)


# Initialize logging
logger.info("Analytics module initialized with comprehensive reporting capabilities")
