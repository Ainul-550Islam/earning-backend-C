"""
postback_insight_service.py – PostbackInsight analytics service.

Provides high-level operations for managing postback analytics and insights.
Handles daily aggregation, health scoring, and anomaly detection.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db import models, transaction
from django.utils import timezone

from api.postback.models import NetworkPostbackConfig, PostbackInsight, PostbackLog
from api.postback.choices import PostbackStatus

logger = logging.getLogger(__name__)


class PostbackInsightService:
    """Service for managing postback analytics and insights."""

    @staticmethod
    def get_daily_insight(network: NetworkPostbackConfig, target_date: date) -> PostbackInsight:
        """Get or create daily insight for a specific network and date."""
        insight, created = PostbackInsight.objects.get_or_create(
            network=network,
            date=target_date,
            defaults={
                'received_count': 0,
                'validated_count': 0,
                'rewarded_count': 0,
                'rejected_count': 0,
                'duplicate_count': 0,
                'failed_count': 0,
                'total_payout': 0,
                'total_points_awarded': 0,
                'health_score': 0,
                'average_processing_time': 0,
            }
        )
        
        if created:
            # Generate initial integrity hash
            insight.integrity_hash = insight.generate_integrity_hash()
            insight.save()
        
        return insight

    @staticmethod
    def recalculate_daily_insight(network: NetworkPostbackConfig, target_date: date) -> PostbackInsight:
        """
        Recalculate daily insight from scratch by processing all postback logs for the date.
        This is useful for data correction or backfilling.
        """
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = start_datetime + timedelta(days=1)
        
        # Get all postback logs for the date
        logs = PostbackLog.objects.filter(
            network=network,
            received_at__gte=start_datetime,
            received_at__lt=end_datetime
        )
        
        # Calculate aggregates
        received_count = logs.count()
        validated_count = logs.filter(status=PostbackStatus.VALIDATED).count()
        rewarded_count = logs.filter(status=PostbackStatus.REWARDED).count()
        rejected_count = logs.filter(status=PostbackStatus.REJECTED).count()
        duplicate_count = logs.filter(status=PostbackStatus.DUPLICATE).count()
        failed_count = logs.filter(status=PostbackStatus.FAILED).count()
        
        # Financial aggregates
        rewarded_logs = logs.filter(status=PostbackStatus.REWARDED)
        total_payout = rewarded_logs.aggregate(
            total=models.Sum('payout')
        )['total'] or 0
        total_points_awarded = rewarded_logs.aggregate(
            total=models.Sum('points_awarded')
        )['total'] or 0
        
        # Calculate average processing time
        processed_logs = logs.filter(
            processed_at__isnull=False,
            received_at__isnull=False
        )
        avg_processing_time = 0
        if processed_logs.exists():
            total_time = sum(
                (log.processed_at - log.received_at).total_seconds()
                for log in processed_logs
            )
            avg_processing_time = total_time / processed_logs.count()
        
        # Create or update insight
        insight, created = PostbackInsight.objects.update_or_create(
            network=network,
            date=target_date,
            defaults={
                'received_count': received_count,
                'validated_count': validated_count,
                'rewarded_count': rewarded_count,
                'rejected_count': rejected_count,
                'duplicate_count': duplicate_count,
                'failed_count': failed_count,
                'total_payout': total_payout,
                'total_points_awarded': total_points_awarded,
                'average_processing_time': avg_processing_time,
            }
        )
        
        # Calculate health score
        insight.health_score = insight.calculate_health_score()
        
        # Generate integrity hash
        insight.integrity_hash = insight.generate_integrity_hash()
        insight.save()
        
        logger.info(
            "Recalculated insight for network %s on %s: %d received, %d rewarded",
            network.network_key, target_date, received_count, rewarded_count
        )
        
        return insight

    @staticmethod
    def get_network_health_trend(
        network: NetworkPostbackConfig, 
        days: int = 30
    ) -> List[Dict]:
        """Get health score trend for a network over the specified number of days."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        insights = PostbackInsight.objects.filter(
            network=network,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        return [
            {
                'date': insight.date.isoformat(),
                'health_score': float(insight.health_score),
                'received_count': insight.received_count,
                'rewarded_count': insight.rewarded_count,
                'rejected_count': insight.rejected_count,
                'total_payout': float(insight.total_payout),
            }
            for insight in insights
        ]

    @staticmethod
    def detect_anomalies(network: NetworkPostbackConfig, target_date: date) -> Dict:
        """
        Detect anomalies in postback patterns for a specific date.
        Returns anomaly details and updates the insight record.
        """
        insight = PostbackInsightService.get_daily_insight(network, target_date)
        
        anomalies = {}
        
        # Get historical baseline (last 7 days excluding current)
        baseline_end = target_date - timedelta(days=1)
        baseline_start = baseline_end - timedelta(days=6)
        
        baseline_insights = PostbackInsight.objects.filter(
            network=network,
            date__gte=baseline_start,
            date__lte=baseline_end
        )
        
        if baseline_insights.count() >= 3:  # Need at least 3 days for baseline
            avg_received = sum(i.received_count for i in baseline_insights) / baseline_insights.count()
            avg_health = sum(float(i.health_score) for i in baseline_insights) / baseline_insights.count()
            
            # Check for volume anomalies (>50% deviation)
            if avg_received > 0:
                volume_deviation = (insight.received_count - avg_received) / avg_received
                if abs(volume_deviation) > 0.5:
                    anomalies['volume_spike'] = {
                        'type': 'volume_spike' if volume_deviation > 0 else 'volume_drop',
                        'deviation_percent': round(abs(volume_deviation) * 100, 2),
                        'current': insight.received_count,
                        'baseline_avg': round(avg_received, 2),
                    }
            
            # Check for health anomalies (>20% deviation)
            if avg_health > 0:
                health_deviation = (float(insight.health_score) - avg_health) / avg_health
                if abs(health_deviation) > 0.2:
                    anomalies['health_drop'] = {
                        'type': 'health_drop' if health_deviation < 0 else 'health_improvement',
                        'deviation_percent': round(abs(health_deviation) * 100, 2),
                        'current': float(insight.health_score),
                        'baseline_avg': round(avg_health, 2),
                    }
        
        # Check for high rejection rates (>30%)
        if insight.received_count > 0:
            rejection_rate = (insight.rejected_count + insight.failed_count) / insight.received_count
            if rejection_rate > 0.3:
                anomalies['high_rejection_rate'] = {
                    'type': 'high_rejection_rate',
                    'rejection_rate_percent': round(rejection_rate * 100, 2),
                    'rejected_count': insight.rejected_count + insight.failed_count,
                    'total_count': insight.received_count,
                }
        
        # Check for high duplicate rates (>25%)
        if insight.received_count > 0:
            duplicate_rate = insight.duplicate_count / insight.received_count
            if duplicate_rate > 0.25:
                anomalies['high_duplicate_rate'] = {
                    'type': 'high_duplicate_rate',
                    'duplicate_rate_percent': round(duplicate_rate * 100, 2),
                    'duplicate_count': insight.duplicate_count,
                    'total_count': insight.received_count,
                }
        
        # Update insight with anomaly data
        if anomalies:
            insight.anomaly_detected = True
            insight.anomaly_details = anomalies
            insight.integrity_hash = insight.generate_integrity_hash()
            insight.save()
            
            logger.warning(
                "Anomalies detected for network %s on %s: %s",
                network.network_key, target_date, list(anomalies.keys())
            )
        else:
            # Clear anomalies if none detected
            if insight.anomaly_detected:
                insight.anomaly_detected = False
                insight.anomaly_details = {}
                insight.integrity_hash = insight.generate_integrity_hash()
                insight.save()
        
        return anomalies

    @staticmethod
    def get_network_summary(network: NetworkPostbackConfig, days: int = 30) -> Dict:
        """Get comprehensive summary for a network over the specified period."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        insights = PostbackInsight.objects.filter(
            network=network,
            date__gte=start_date,
            date__lte=end_date
        )
        
        if not insights.exists():
            return {
                'network_key': network.network_key,
                'period_days': days,
                'total_received': 0,
                'total_rewarded': 0,
                'total_rejected': 0,
                'total_duplicates': 0,
                'total_failed': 0,
                'total_payout': 0,
                'total_points_awarded': 0,
                'avg_health_score': 0,
                'avg_processing_time': 0,
                'anomaly_days': 0,
                'daily_breakdown': []
            }
        
        # Calculate aggregates
        total_received = sum(i.received_count for i in insights)
        total_rewarded = sum(i.rewarded_count for i in insights)
        total_rejected = sum(i.rejected_count for i in insights)
        total_duplicates = sum(i.duplicate_count for i in insights)
        total_failed = sum(i.failed_count for i in insights)
        total_payout = sum(i.total_payout for i in insights)
        total_points_awarded = sum(i.total_points_awarded for i in insights)
        
        # Calculate averages
        avg_health_score = sum(float(i.health_score) for i in insights) / insights.count()
        avg_processing_time = sum(i.average_processing_time for i in insights) / insights.count()
        
        # Count anomaly days
        anomaly_days = insights.filter(anomaly_detected=True).count()
        
        # Daily breakdown
        daily_breakdown = [
            {
                'date': i.date.isoformat(),
                'received': i.received_count,
                'rewarded': i.rewarded_count,
                'health_score': float(i.health_score),
                'anomaly_detected': i.anomaly_detected,
            }
            for i in insights.order_by('date')
        ]
        
        return {
            'network_key': network.network_key,
            'period_days': days,
            'total_received': total_received,
            'total_rewarded': total_rewarded,
            'total_rejected': total_rejected,
            'total_duplicates': total_duplicates,
            'total_failed': total_failed,
            'total_payout': float(total_payout),
            'total_points_awarded': total_points_awarded,
            'avg_health_score': round(avg_health_score, 2),
            'avg_processing_time': round(avg_processing_time, 2),
            'anomaly_days': anomaly_days,
            'daily_breakdown': daily_breakdown,
        }

    @staticmethod
    @transaction.atomic
    def backfill_missing_insights(network: NetworkPostbackConfig, start_date: date, end_date: date) -> int:
        """
        Backfill missing insight records for a date range.
        Returns the number of days processed.
        """
        current_date = start_date
        processed_count = 0
        
        while current_date <= end_date:
            try:
                PostbackInsightService.recalculate_daily_insight(network, current_date)
                processed_count += 1
            except Exception as exc:
                logger.error(
                    "Failed to backfill insight for network %s on %s: %s",
                    network.network_key, current_date, exc
                )
            
            current_date += timedelta(days=1)
        
        logger.info(
            "Backfilled %d days of insights for network %s",
            processed_count, network.network_key
        )
        
        return processed_count
