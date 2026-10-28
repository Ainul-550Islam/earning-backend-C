# =============================================================================
# auto_mod/services/ContentSignalService.py
# =============================================================================

"""
Service for managing content signals in the moderation system.
Handles signal detection, aggregation, processing, and decision support.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db import transaction
from django.utils import timezone
from django.db.models import Case, When, F, Avg, Sum, Count, Q

from ..choices import RiskLevel, SignalType
from ..constants import (
    SIGNAL_CONFIDENCE_THRESHOLD,
    SIGNAL_DEFAULT_WEIGHT,
    SIGNAL_MAX_WEIGHT,
    SIGNAL_PROCESSING_BATCH_SIZE,
    SIGNAL_RETENTION_DAYS,
)
from ..exceptions import (
    SignalProcessingError,
    SignalAggregationError,
    SignalThresholdExceededError,
    InvalidSignalTypeError,
)
from ..models import ContentSignal, SuspiciousSubmission
from ..signals import signal_detected, signals_aggregated, signals_processed

logger = logging.getLogger(__name__)


class ContentSignalService:
    """
    Service for managing content signals in the moderation system.
    """
    
    def __init__(self):
        self.logger = logger

    # ---------------------------------------------------------------------------
    # Signal Creation and Detection
    # ---------------------------------------------------------------------------

    @transaction.atomic
    def create_signal(
        self,
        submission: SuspiciousSubmission,
        signal_type: str,
        value: str,
        weight: float = SIGNAL_DEFAULT_WEIGHT,
        confidence: Optional[float] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_positive: bool = True,
        severity: str = RiskLevel.LOW
    ) -> ContentSignal:
        """
        Create a new content signal.
        
        Args:
            submission: The submission the signal is for
            signal_type: Type of signal
            value: Signal value/data
            weight: Signal weight (importance)
            confidence: Signal confidence (0-1)
            source: Signal source
            metadata: Additional signal metadata
            is_positive: Whether signal indicates positive/negative content
            severity: Signal severity level
            
        Returns:
            Created ContentSignal instance
            
        Raises:
            SignalProcessingError: If signal cannot be created
            InvalidSignalTypeError: If signal type is invalid
        """
        try:
            # Validate signal type
            if signal_type not in [choice[0] for choice in SignalType.choices]:
                raise InvalidSignalTypeError(f"Invalid signal type: {signal_type}")
            
            # Validate weight
            if not (0 <= weight <= SIGNAL_MAX_WEIGHT):
                raise SignalProcessingError(f"Weight must be between 0 and {SIGNAL_MAX_WEIGHT}")
            
            # Validate confidence
            if confidence is not None and not (0 <= confidence <= 1):
                raise SignalProcessingError("Confidence must be between 0 and 1")
            
            # Validate severity
            if severity not in [choice[0] for choice in RiskLevel.choices]:
                severity = RiskLevel.LOW
            
            # Create signal
            signal = ContentSignal.objects.create(
                submission=submission,
                signal_type=signal_type,
                value=value,
                weight=weight,
                confidence=confidence,
                source=source or "",
                metadata=metadata or {},
                is_positive=is_positive,
                severity=severity
            )
            
            # Send signal
            signal_detected.send(
                sender=ContentSignal,
                signal=signal,
                submission=submission,
                signal_type=signal_type
            )
            
            self.logger.info(
                f"signal_detected type={signal_type} submission={submission.pk} "
                f"weight={weight} confidence={confidence} signal={signal.pk}"
            )
            
            return signal
            
        except (InvalidSignalTypeError, SignalProcessingError):
            raise
        except Exception as exc:
            self.logger.error(f"create_signal.failed submission={submission.pk}: {exc}")
            raise SignalProcessingError(f"Failed to create signal: {exc}")

    @transaction.atomic
    def create_bulk_signals(
        self,
        signals_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create multiple signals in bulk.
        
        Args:
            signals_data: List of signal data dictionaries
            
        Returns:
            Bulk creation statistics
        """
        try:
            created_signals = []
            errors = []
            
            for signal_data in signals_data:
                try:
                    submission_id = signal_data.get("submission_id")
                    signal_type = signal_data.get("signal_type")
                    value = signal_data.get("value")
                    
                    if not all([submission_id, signal_type, value]):
                        errors.append({
                            "error": "Missing required fields",
                            "data": signal_data
                        })
                        continue
                    
                    # Get submission
                    submission = SuspiciousSubmission.objects.get(pk=submission_id)
                    
                    # Create signal
                    signal = self.create_signal(
                        submission=submission,
                        signal_type=signal_type,
                        value=value,
                        weight=signal_data.get("weight", SIGNAL_DEFAULT_WEIGHT),
                        confidence=signal_data.get("confidence"),
                        source=signal_data.get("source", ""),
                        metadata=signal_data.get("metadata", {}),
                        is_positive=signal_data.get("is_positive", True),
                        severity=signal_data.get("severity", RiskLevel.LOW)
                    )
                    
                    created_signals.append(str(signal.pk))
                    
                except Exception as exc:
                    errors.append({
                        "error": str(exc),
                        "data": signal_data
                    })
            
            return {
                "created": len(created_signals),
                "signal_ids": created_signals,
                "errors": errors
            }
            
        except Exception as exc:
            self.logger.error(f"create_bulk_signals.failed: {exc}")
            raise SignalProcessingError(f"Failed to create bulk signals: {exc}")

    # ---------------------------------------------------------------------------
    # Signal Aggregation and Processing
    # ---------------------------------------------------------------------------

    def aggregate_signals_for_submission(
        self,
        submission: SuspiciousSubmission
    ) -> Dict[str, Any]:
        """
        Aggregate all signals for a submission.
        
        Args:
            submission: The submission to aggregate signals for
            
        Returns:
            Aggregated signal data
        """
        try:
            # Get all signals for submission
            signals = ContentSignal.objects.filter(
                submission=submission
            ).order_by('-weight', '-confidence')
            
            if not signals.exists():
                return {
                    "submission_id": str(submission.pk),
                    "total_signals": 0,
                    "aggregate_score": 0.0,
                    "signal_breakdown": {},
                    "recommendation": "no_signals"
                }
            
            # Calculate aggregate score
            aggregate_score = 0.0
            signal_breakdown = {}
            
            # Severity multipliers
            severity_multipliers = {
                RiskLevel.LOW: 1.0,
                RiskLevel.MEDIUM: 1.5,
                RiskLevel.HIGH: 2.0,
                RiskLevel.CRITICAL: 3.0
            }
            
            for signal in signals:
                # Calculate signal impact
                confidence = signal.confidence or SIGNAL_CONFIDENCE_THRESHOLD
                severity_multiplier = severity_multipliers.get(signal.severity, 1.0)
                
                # Positive signals reduce risk, negative signals increase risk
                if signal.is_positive:
                    impact = -signal.weight * confidence * severity_multiplier
                else:
                    impact = signal.weight * confidence * severity_multiplier
                
                aggregate_score += impact
                
                # Update breakdown
                signal_type = signal.signal_type
                if signal_type not in signal_breakdown:
                    signal_breakdown[signal_type] = {
                        "count": 0,
                        "total_weight": 0.0,
                        "avg_confidence": 0.0,
                        "impact": 0.0
                    }
                
                breakdown = signal_breakdown[signal_type]
                breakdown["count"] += 1
                breakdown["total_weight"] += signal.weight
                breakdown["avg_confidence"] += confidence
                breakdown["impact"] += impact
            
            # Calculate averages in breakdown
            for signal_type, breakdown in signal_breakdown.items():
                if breakdown["count"] > 0:
                    breakdown["avg_confidence"] /= breakdown["count"]
            
            # Determine recommendation
            recommendation = self._get_recommendation_from_score(aggregate_score)
            
            result = {
                "submission_id": str(submission.pk),
                "total_signals": signals.count(),
                "aggregate_score": aggregate_score,
                "signal_breakdown": signal_breakdown,
                "recommendation": recommendation,
                "calculated_at": timezone.now().isoformat()
            }
            
            # Send aggregation signal
            signals_aggregated.send(
                sender=ContentSignal,
                submission=submission,
                signals=list(signals),
                aggregate_score=aggregate_score
            )
            
            self.logger.info(
                f"signals_aggregated submission={submission.pk} "
                f"signals={signals.count()} score={aggregate_score:.2f}"
            )
            
            return result
            
        except Exception as exc:
            self.logger.error(f"aggregate_signals_for_submission.failed submission={submission.pk}: {exc}")
            raise SignalAggregationError(f"Failed to aggregate signals: {exc}")

    @transaction.atomic
    def process_signals_for_submission(
        self,
        submission: SuspiciousSubmission,
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Process all unprocessed signals for a submission.
        
        Args:
            submission: The submission to process signals for
            force_reprocess: Whether to reprocess already processed signals
            
        Returns:
            Processing statistics
        """
        try:
            # Get signals to process
            queryset = ContentSignal.objects.filter(submission=submission)
            
            if not force_reprocess:
                queryset = queryset.filter(processed=False)
            
            signals = list(queryset)
            
            if not signals:
                return {
                    "submission_id": str(submission.pk),
                    "processed": 0,
                    "skipped": 0,
                    "errors": 0
                }
            
            processed_count = 0
            skipped_count = 0
            error_count = 0
            
            for signal in signals:
                try:
                    # Mark as processed
                    signal.mark_processed()
                    processed_count += 1
                except Exception as exc:
                    self.logger.warning(f"process_signal.failed signal={signal.pk}: {exc}")
                    error_count += 1
            
            # Send processing signal
            signals_processed.send(
                sender=ContentSignal,
                submission=submission,
                processed_signals=signals[:processed_count],
                decision=None  # Decision will be created separately
            )
            
            self.logger.info(
                f"signals_processed submission={submission.pk} "
                f"processed={processed_count} skipped={skipped_count} errors={error_count}"
            )
            
            return {
                "submission_id": str(submission.pk),
                "processed": processed_count,
                "skipped": skipped_count,
                "errors": error_count
            }
            
        except Exception as exc:
            self.logger.error(f"process_signals_for_submission.failed submission={submission.pk}: {exc}")
            raise SignalProcessingError(f"Failed to process signals: {exc}")

    # ---------------------------------------------------------------------------
    # Signal Analysis and Insights
    # ---------------------------------------------------------------------------

    def get_signal_patterns(
        self,
        days_back: int = 30,
        signal_type: Optional[str] = None,
        submission_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze signal patterns over time.
        
        Args:
            days_back: Number of days to analyze
            signal_type: Filter by signal type
            submission_type: Filter by submission type
            
        Returns:
            Signal pattern analysis
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Base queryset
        queryset = ContentSignal.objects.filter(created_at__gte=cutoff_date)
        
        if signal_type:
            queryset = queryset.filter(signal_type=signal_type)
        
        if submission_type:
            queryset = queryset.filter(submission__submission_type=submission_type)
        
        # Signal type breakdown
        signal_type_stats = (
            queryset.values('signal_type')
            .annotate(
                count=Count('id'),
                avg_weight=Avg('weight'),
                avg_confidence=Avg('confidence')
            )
            .order_by('-count')
        )
        
        # Severity breakdown
        severity_stats = (
            queryset.values('severity')
            .annotate(count=Count('id'))
            .order_by('severity')
        )
        
        # Positive vs negative breakdown
        polarity_stats = (
            queryset.values('is_positive')
            .annotate(count=Count('id'))
            .order_by('is_positive')
        )
        
        # Time series data (daily)
        daily_stats = []
        for i in range(days_back):
            date = timezone.now() - timedelta(days=i)
            day_count = queryset.filter(
                created_at__date=date.date()
            ).count()
            
            daily_stats.append({
                "date": date.date().isoformat(),
                "count": day_count
            })
        
        # Top signal sources
        source_stats = (
            queryset.values('source')
            .annotate(count=Count('id'))
            .exclude(source='')
            .order_by('-count')[:10]
        )
        
        # Average impact scores
        severity_multipliers = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 1.5,
            RiskLevel.HIGH: 2.0,
            RiskLevel.CRITICAL: 3.0
        }
        
        annotated_signals = queryset.annotate(
            impact_score=Case(
                When(severity=RiskLevel.LOW, then=F('weight') * F('confidence') * severity_multipliers[RiskLevel.LOW]),
                When(severity=RiskLevel.MEDIUM, then=F('weight') * F('confidence') * severity_multipliers[RiskLevel.MEDIUM]),
                When(severity=RiskLevel.HIGH, then=F('weight') * F('confidence') * severity_multipliers[RiskLevel.HIGH]),
                When(severity=RiskLevel.CRITICAL, then=F('weight') * F('confidence') * severity_multipliers[RiskLevel.CRITICAL]),
                default=F('weight') * F('confidence')
            )
        )
        
        avg_impact = annotated_signals.aggregate(
            avg_impact=Avg('impact_score')
        )['avg_impact'] or 0
        
        return {
            "period_days": days_back,
            "total_signals": queryset.count(),
            "signal_type_breakdown": list(signal_type_stats),
            "severity_breakdown": list(severity_stats),
            "polarity_breakdown": list(polarity_stats),
            "daily_trends": daily_stats,
            "top_sources": list(source_stats),
            "avg_impact_score": avg_impact
        }

    def get_high_impact_signals(
        self,
        hours_back: int = 24,
        min_impact_score: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Get high impact signals from recent period.
        
        Args:
            hours_back: Number of hours to look back
            min_impact_score: Minimum impact score threshold
            
        Returns:
            List of high impact signal data
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=hours_back)
        
        # Severity multipliers
        severity_multipliers = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 1.5,
            RiskLevel.HIGH: 2.0,
            RiskLevel.CRITICAL: 3.0
        }
        
        # Annotate with impact score
        signals = ContentSignal.objects.filter(
            created_at__gte=cutoff_time
        ).annotate(
            impact_score=Case(
                When(severity=RiskLevel.LOW, then=F('weight') * F('confidence') * severity_multipliers[RiskLevel.LOW]),
                When(severity=RiskLevel.MEDIUM, then=F('weight') * F('confidence') * severity_multipliers[RiskLevel.MEDIUM]),
                When(severity=RiskLevel.HIGH, then=F('weight') * F('confidence') * severity_multipliers[RiskLevel.HIGH]),
                When(severity=RiskLevel.CRITICAL, then=F('weight') * F('confidence') * severity_multipliers[RiskLevel.CRITICAL]),
                default=F('weight') * F('confidence')
            )
        ).filter(impact_score__gte=min_impact_score).order_by('-impact_score')
        
        high_impact_signals = []
        for signal in signals:
            high_impact_signals.append({
                "signal_id": str(signal.pk),
                "submission_id": str(signal.submission.pk),
                "signal_type": signal.signal_type,
                "value": signal.value[:100] + "..." if len(signal.value) > 100 else signal.value,
                "weight": signal.weight,
                "confidence": signal.confidence,
                "severity": signal.severity,
                "is_positive": signal.is_positive,
                "impact_score": signal.impact_score,
                "source": signal.source,
                "created_at": signal.created_at.isoformat()
            })
        
        return high_impact_signals

    def get_signal_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive signal statistics.
        
        Returns:
            Signal statistics dictionary
        """
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(weeks=1)
        
        # Base stats
        total_signals = ContentSignal.objects.count()
        processed_signals = ContentSignal.objects.filter(processed=True).count()
        unprocessed_signals = total_signals - processed_signals
        
        # Recent activity
        signals_last_hour = ContentSignal.objects.filter(created_at__gte=hour_ago).count()
        signals_last_day = ContentSignal.objects.filter(created_at__gte=day_ago).count()
        signals_last_week = ContentSignal.objects.filter(created_at__gte=week_ago).count()
        
        # Signal type breakdown
        signal_type_stats = {}
        for signal_type_choice in SignalType.choices:
            signal_type = signal_type_choice[0]
            count = ContentSignal.objects.filter(signal_type=signal_type).count()
            signal_type_stats[signal_type] = count
        
        # Severity breakdown
        severity_stats = {}
        for severity_choice in RiskLevel.choices:
            severity = severity_choice[0]
            count = ContentSignal.objects.filter(severity=severity).count()
            severity_stats[severity] = count
        
        # Polarity breakdown
        positive_signals = ContentSignal.objects.filter(is_positive=True).count()
        negative_signals = ContentSignal.objects.filter(is_positive=False).count()
        
        # Average metrics
        avg_metrics = ContentSignal.objects.aggregate(
            avg_weight=Avg('weight'),
            avg_confidence=Avg('confidence')
        )
        
        return {
            "total_signals": total_signals,
            "processed_signals": processed_signals,
            "unprocessed_signals": unprocessed_signals,
            "processing_rate": (processed_signals / total_signals * 100) if total_signals > 0 else 0,
            "recent_activity": {
                "last_hour": signals_last_hour,
                "last_day": signals_last_day,
                "last_week": signals_last_week
            },
            "signal_type_breakdown": signal_type_stats,
            "severity_breakdown": severity_stats,
            "polarity_breakdown": {
                "positive": positive_signals,
                "negative": negative_signals
            },
            "avg_metrics": {
                "weight": avg_metrics['avg_weight'] or 0,
                "confidence": avg_metrics['avg_confidence'] or 0
            }
        }

    # ---------------------------------------------------------------------------
    # Signal Maintenance
    # ---------------------------------------------------------------------------

    def cleanup_old_signals(self, days_old: int = SIGNAL_RETENTION_DAYS) -> Dict[str, Any]:
        """
        Clean up old processed signals.
        
        Args:
            days_old: Age in days for signals to delete
            
        Returns:
            Cleanup statistics
        """
        try:
            from django.utils import timezone
            from datetime import timedelta
            
            cutoff_date = timezone.now() - timedelta(days=days_old)
            
            # Delete old processed signals
            old_signals = ContentSignal.objects.filter(
                processed=True,
                created_at__lt=cutoff_date
            )
            
            deleted_count = old_signals.count()[0]  # Delete returns tuple
            
            self.logger.info(f"cleanup_old_signals.completed deleted={deleted_count}")
            
            return {
                "deleted": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as exc:
            self.logger.error(f"cleanup_old_signals.failed: {exc}")
            return {
                "deleted": 0,
                "error": str(exc)
            }

    # ---------------------------------------------------------------------------
    # Helper Methods
    # ---------------------------------------------------------------------------

    def _get_recommendation_from_score(self, score: float) -> str:
        """Get recommendation based on aggregate score."""
        if score >= 10.0:
            return "reject_automatically"
        elif score >= 5.0:
            return "escalate_priority"
        elif score >= 2.0:
            return "human_review_required"
        elif score >= 0.5:
            return "monitor_closely"
        elif score <= -2.0:
            return "approve_automatically"
        else:
            return "proceed_normal"

    def get_signals_for_submission(
        self,
        submission: SuspiciousSubmission,
        signal_type: Optional[str] = None,
        processed_only: bool = False,
        limit: int = 100
    ) -> List[ContentSignal]:
        """
        Get signals for a specific submission.
        
        Args:
            submission: The submission
            signal_type: Filter by signal type
            processed_only: Only return processed signals
            limit: Maximum number of signals
            
        Returns:
            List of ContentSignal instances
        """
        queryset = ContentSignal.objects.filter(submission=submission)
        
        if signal_type:
            queryset = queryset.filter(signal_type=signal_type)
        
        if processed_only:
            queryset = queryset.filter(processed=True)
        
        return list(queryset.order_by('-created_at')[:limit])

    def reprocess_signals(
        self,
        submission: Optional[SuspiciousSubmission] = None,
        signal_type: Optional[str] = None,
        batch_size: int = SIGNAL_PROCESSING_BATCH_SIZE
    ) -> Dict[str, Any]:
        """
        Reprocess signals (mark as unprocessed and process again).
        
        Args:
            submission: Specific submission to reprocess (None for all)
            signal_type: Specific signal type to reprocess
            batch_size: Batch size for processing
            
        Returns:
            Reprocessing statistics
        """
        try:
            # Get signals to reprocess
            queryset = ContentSignal.objects.all()
            
            if submission:
                queryset = queryset.filter(submission=submission)
            
            if signal_type:
                queryset = queryset.filter(signal_type=signal_type)
            
            # Mark as unprocessed
            updated_count = queryset.update(processed=False, processed_at=None)
            
            # Process in batches
            total_processed = 0
            total_errors = 0
            
            # Get submissions with signals to process
            submissions_with_signals = queryset.values_list('submission_id', flat=True).distinct()
            
            for submission_id in submissions_with_signals:
                try:
                    sub = SuspiciousSubmission.objects.get(pk=submission_id)
                    result = self.process_signals_for_submission(sub, force_reprocess=True)
                    total_processed += result["processed"]
                    total_errors += result["errors"]
                except Exception as exc:
                    self.logger.warning(f"reprocess_signals.failed submission={submission_id}: {exc}")
                    total_errors += 1
            
            return {
                "signals_marked": updated_count,
                "submissions_processed": len(submissions_with_signals),
                "total_processed": total_processed,
                "total_errors": total_errors
            }
            
        except Exception as exc:
            self.logger.error(f"reprocess_signals.failed: {exc}")
            raise SignalProcessingError(f"Failed to reprocess signals: {exc}")

    def detect_signal_anomalies(
        self,
        hours_back: int = 24,
        threshold_multiplier: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalous signal patterns.
        
        Args:
            hours_back: Time window to analyze
            threshold_multiplier: Multiplier for anomaly detection
            
        Returns:
            List of anomaly detections
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(hours=hours_back)
        
        anomalies = []
        
        # Check each signal type for anomalies
        for signal_type_choice in SignalType.choices:
            signal_type = signal_type_choice[0]
            
            # Get hourly counts for this signal type
            recent_signals = ContentSignal.objects.filter(
                signal_type=signal_type,
                created_at__gte=cutoff_time
            )
            
            if recent_signals.count() == 0:
                continue
            
            # Calculate baseline (previous period)
            baseline_start = cutoff_time - timedelta(hours=hours_back)
            baseline_signals = ContentSignal.objects.filter(
                signal_type=signal_type,
                created_at__gte=baseline_start,
                created_at__lt=cutoff_time
            )
            
            baseline_avg = baseline_signals.count() / hours_back
            recent_avg = recent_signals.count() / hours_back
            
            # Detect anomaly
            if baseline_avg > 0 and recent_avg > baseline_avg * threshold_multiplier:
                anomalies.append({
                    "signal_type": signal_type,
                    "anomaly_type": "spike",
                    "baseline_avg": baseline_avg,
                    "recent_avg": recent_avg,
                    "multiplier": recent_avg / baseline_avg if baseline_avg > 0 else 0,
                    "period_hours": hours_back
                })
            elif baseline_avg > 0 and recent_avg < baseline_avg / threshold_multiplier:
                anomalies.append({
                    "signal_type": signal_type,
                    "anomaly_type": "drop",
                    "baseline_avg": baseline_avg,
                    "recent_avg": recent_avg,
                    "multiplier": recent_avg / baseline_avg if baseline_avg > 0 else 0,
                    "period_hours": hours_back
                })
        
        return anomalies
