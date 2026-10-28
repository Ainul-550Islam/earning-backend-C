# =============================================================================
# auto_mod/management/commands/calibrate_thresholds.py
# =============================================================================

"""
Django management command to calibrate confidence thresholds.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.db.models import Avg, Count, StdDev, Q

from ...models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal, 
    AutoApprovalRule, MLModelVersion
)
from ...choices import ModerationStatus, AppealStatus, AppealOutcome
from ...services import AutoApprovalService
from ...constants import (
    AUTO_APPROVE_THRESHOLD, AUTO_REJECT_THRESHOLD, 
    HUMAN_REVIEW_LOWER, HUMAN_REVIEW_UPPER
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calibrate confidence thresholds based on historical performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold-type',
            type=str,
            choices=['auto_approve', 'auto_reject', 'human_review', 'all'],
            default='all',
            help='Type of threshold to calibrate (default: all)'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=30,
            help='Number of days of historical data to analyze (default: 30)'
        )
        parser.add_argument(
            '--min-samples',
            type=int,
            default=100,
            help='Minimum samples required for calibration (default: 100)'
        )
        parser.add_argument(
            '--target-precision',
            type=float,
            default=0.95,
            help='Target precision for auto-approval (default: 0.95)'
        )
        parser.add_argument(
            '--target-recall',
            type=float,
            default=0.90,
            help='Target recall for auto-rejection (default: 0.90)'
        )
        parser.add_argument(
            '--confidence-tolerance',
            type=float,
            default=0.05,
            help='Tolerance for confidence adjustments (default: 0.05)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show recommended thresholds without applying changes'
        )
        parser.add_argument(
            '--apply-changes',
            action='store_true',
            help='Apply calibrated thresholds to rules/models'
        )
        parser.add_argument(
            '--submission-type',
            type=str,
            action='append',
            help='Filter by submission type (can be used multiple times)'
        )
    
    def handle(self, *args, **options):
        """Execute the calibration command."""
        self.stdout.write(
            self.style.SUCCESS('Starting confidence threshold calibration...')
        )
        
        # Parse parameters
        threshold_type = options.get('threshold_type', 'all')
        days_back = options.get('days_back', 30)
        min_samples = options.get('min_samples', 100)
        target_precision = options.get('target_precision', 0.95)
        target_recall = options.get('target_recall', 0.90)
        confidence_tolerance = options.get('confidence_tolerance', 0.05)
        dry_run = options.get('dry_run', False)
        apply_changes = options.get('apply_changes', False)
        submission_type_filters = options.get('submission_type', [])
        
        try:
            # Validate parameters
            self._validate_parameters(target_precision, target_recall, confidence_tolerance)
            
            # Get historical data
            historical_data = self._get_historical_data(days_back, submission_type_filters)
            
            if not historical_data:
                self.stdout.write(
                    self.style.WARNING('No historical data found for calibration.')
                )
                return
            
            # Analyze current performance
            current_performance = self._analyze_current_performance(historical_data)
            
            # Calculate optimal thresholds
            calibrated_thresholds = self._calculate_optimal_thresholds(
                historical_data, target_precision, target_recall, min_samples
            )
            
            # Show calibration results
            self._show_calibration_results(
                current_performance, calibrated_thresholds, threshold_type
            )
            
            # Apply changes if requested
            if apply_changes and not dry_run:
                results = self._apply_calibrated_thresholds(
                    calibrated_thresholds, threshold_type, confidence_tolerance
                )
                self._show_application_results(results)
            elif dry_run:
                self.stdout.write(
                    self.style.WARNING('DRY RUN - No changes applied. Use --apply-changes to apply.')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('Use --dry-run to preview changes or --apply-changes to apply.')
                )
            
        except Exception as exc:
            logger.error(f"Threshold calibration failed: {exc}")
            raise CommandError(f"Threshold calibration failed: {exc}")
    
    def _validate_parameters(self, target_precision, target_recall, confidence_tolerance):
        """Validate calibration parameters."""
        if not (0.5 <= target_precision <= 1.0):
            raise CommandError("Target precision must be between 0.5 and 1.0")
        
        if not (0.5 <= target_recall <= 1.0):
            raise CommandError("Target recall must be between 0.5 and 1.0")
        
        if not (0.01 <= confidence_tolerance <= 0.2):
            raise CommandError("Confidence tolerance must be between 0.01 and 0.2")
    
    def _get_historical_data(self, days_back, submission_type_filters):
        """Get historical data for calibration."""
        cutoff_date = timezone.now() - timezone.timedelta(days=days_back)
        
        # Get decisions with appeals (ground truth)
        decisions_with_appeals = ModerationDecision.objects.filter(
            decided_at__gte=cutoff_date,
            appeals__isnull=False
        ).select_related('submission', 'decided_by', 'appeals').distinct()
        
        if submission_type_filters:
            decisions_with_appeals = decisions_with_appeals.filter(
                submission__submission_type__in=submission_type_filters
            )
        
        # Get automated decisions
        automated_decisions = ModerationDecision.objects.filter(
            decided_at__gte=cutoff_date,
            is_automated=True
        ).select_related('submission', 'applied_rule')
        
        if submission_type_filters:
            automated_decisions = automated_decisions.filter(
                submission__submission_type__in=submission_type_filters
            )
        
        # Get all submissions with risk scores
        submissions = SuspiciousSubmission.objects.filter(
            created_at__gte=cutoff_date,
            risk_score__isnull=False
        ).select_related('user')
        
        if submission_type_filters:
            submissions = submissions.filter(submission_type__in=submission_type_filters)
        
        return {
            'decisions_with_appeals': decisions_with_appeals,
            'automated_decisions': automated_decisions,
            'submissions': submissions,
            'period_days': days_back
        }
    
    def _analyze_current_performance(self, historical_data):
        """Analyze current threshold performance."""
        decisions = historical_data['decisions_with_appeals']
        automated_decisions = historical_data['automated_decisions']
        
        # Current thresholds from rules
        auto_approve_rules = AutoApprovalRule.objects.filter(
            action='auto_approve',
            is_active=True
        )
        auto_reject_rules = AutoApprovalRule.objects.filter(
            action='auto_reject',
            is_active=True
        )
        
        current_thresholds = {
            'auto_approve': list(auto_approve_rules.values_list('confidence_threshold', flat=True)),
            'auto_reject': list(auto_reject_rules.values_list('confidence_threshold', flat=True))
        }
        
        # Calculate current performance metrics
        performance = {
            'current_thresholds': current_thresholds,
            'auto_approval_metrics': self._calculate_approval_metrics(decisions, automated_decisions),
            'auto_rejection_metrics': self._calculate_rejection_metrics(decisions, automated_decisions),
            'appeal_outcomes': self._calculate_appeal_outcomes(decisions)
        }
        
        return performance
    
    def _calculate_approval_metrics(self, decisions, automated_decisions):
        """Calculate auto-approval performance metrics."""
        # Get automated approvals
        auto_approvals = automated_decisions.filter(decision_type='approve')
        
        if not auto_approvals.exists():
            return {'sample_count': 0}
        
        # Find corresponding appeals
        appealed_approvals = []
        for approval in auto_approvals:
            appeals = approval.appeals.all()
            if appeals.exists():
                latest_appeal = appeals.latest('created_at')
                appealed_approvals.append({
                    'confidence': approval.confidence,
                    'appeal_outcome': latest_appeal.final_outcome,
                    'upheld': latest_appeal.final_outcome == AppealOutcome.UPHELD
                })
        
        total_approvals = auto_approvals.count()
        upheld_appeals = sum(1 for a in appealed_approvals if a['upheld'])
        
        # Calculate precision (correct approvals / total approvals)
        precision = (total_approvals - upheld_appeals) / total_approvals if total_approvals > 0 else 0
        
        # Calculate confidence statistics
        confidences = [a['confidence'] for a in appealed_approvals]
        
        return {
            'sample_count': total_approvals,
            'appealed_count': len(appealed_approvals),
            'upheld_appeals': upheld_appeals,
            'precision': precision,
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0,
            'confidence_std': self._calculate_std(confidences) if confidences else 0
        }
    
    def _calculate_rejection_metrics(self, decisions, automated_decisions):
        """Calculate auto-rejection performance metrics."""
        # Get automated rejections
        auto_rejections = automated_decisions.filter(decision_type='reject')
        
        if not auto_rejections.exists():
            return {'sample_count': 0}
        
        # Find corresponding appeals
        appealed_rejections = []
        for rejection in auto_rejections:
            appeals = rejection.appeals.all()
            if appeals.exists():
                latest_appeal = appeals.latest('created_at')
                appealed_rejections.append({
                    'confidence': rejection.confidence,
                    'appeal_outcome': latest_appeal.final_outcome,
                    'overturned': latest_appeal.final_outcome == AppealOutcome.OVERTURNED
                })
        
        total_rejections = auto_rejections.count()
        overturned_appeals = sum(1 for a in appealed_rejections if a['overturned'])
        
        # Calculate recall (correct rejections / total rejections)
        recall = (total_rejections - overturned_appeals) / total_rejections if total_rejections > 0 else 0
        
        # Calculate confidence statistics
        confidences = [a['confidence'] for a in appealed_rejections]
        
        return {
            'sample_count': total_rejections,
            'appealed_count': len(appealed_rejections),
            'overturned_appeals': overturned_appeals,
            'recall': recall,
            'avg_confidence': sum(confidences) / len(confidences) if confidences else 0,
            'confidence_std': self._calculate_std(confidences) if confidences else 0
        }
    
    def _calculate_appeal_outcomes(self, decisions):
        """Calculate appeal outcome statistics."""
        appeals = ModerationAppeal.objects.filter(
            original_decision__in=decisions,
            status=AppealStatus.RESOLVED
        )
        
        if not appeals.exists():
            return {'sample_count': 0}
        
        total_appeals = appeals.count()
        upheld_appeals = appeals.filter(final_outcome=AppealOutcome.UPHELD).count()
        overturned_appeals = appeals.filter(final_outcome=AppealOutcome.OVERTURNED).count()
        
        return {
            'sample_count': total_appeals,
            'upheld_count': upheld_appeals,
            'overturned_count': overturned_appeals,
            'uphold_rate': upheld_appeals / total_appeals if total_appeals > 0 else 0,
            'overturn_rate': overturned_appeals / total_appeals if total_appeals > 0 else 0
        }
    
    def _calculate_optimal_thresholds(self, historical_data, target_precision, target_recall, min_samples):
        """Calculate optimal thresholds based on historical performance."""
        decisions = historical_data['decisions_with_appeals']
        automated_decisions = historical_data['automated_decisions']
        
        # Get confidence ranges for analysis
        approval_confidences = list(
            automated_decisions.filter(decision_type='approve')
            .values_list('confidence', flat=True)
        )
        rejection_confidences = list(
            automated_decisions.filter(decision_type='reject')
            .values_list('confidence', flat=True)
        )
        
        optimal_thresholds = {}
        
        # Calculate optimal auto-approval threshold
        if approval_confidences and len(approval_confidences) >= min_samples:
            approval_threshold = self._find_optimal_threshold(
                approval_confidences, decisions, 'approve', target_precision
            )
            optimal_thresholds['auto_approve'] = approval_threshold
        else:
            optimal_thresholds['auto_approve'] = AUTO_APPROVE_THRESHOLD
        
        # Calculate optimal auto-rejection threshold
        if rejection_confidences and len(rejection_confidences) >= min_samples:
            rejection_threshold = self._find_optimal_threshold(
                rejection_confidences, decisions, 'reject', target_recall
            )
            optimal_thresholds['auto_reject'] = rejection_threshold
        else:
            optimal_thresholds['auto_reject'] = AUTO_REJECT_THRESHOLD
        
        # Calculate optimal human review thresholds
        risk_scores = list(
            historical_data['submissions'].values_list('risk_score', flat=True)
        )
        if risk_scores and len(risk_scores) >= min_samples:
            review_thresholds = self._calculate_human_review_thresholds(risk_scores)
            optimal_thresholds['human_review'] = review_thresholds
        else:
            optimal_thresholds['human_review'] = {
                'lower': HUMAN_REVIEW_LOWER,
                'upper': HUMAN_REVIEW_UPPER
            }
        
        return optimal_thresholds
    
    def _find_optimal_threshold(self, confidences, decisions, decision_type, target_metric):
        """Find optimal threshold for given decision type."""
        # Group decisions by confidence ranges
        confidence_groups = {}
        for confidence in confidences:
            # Round to 2 decimal places for grouping
            rounded_conf = round(confidence, 2)
            if rounded_conf not in confidence_groups:
                confidence_groups[rounded_conf] = []
            confidence_groups[rounded_conf].append(confidence)
        
        # Calculate performance for each threshold
        threshold_performance = {}
        for threshold in sorted(confidence_groups.keys()):
            performance = self._calculate_threshold_performance(
                threshold, decisions, decision_type
            )
            threshold_performance[threshold] = performance
        
        # Find threshold that meets target metric
        best_threshold = None
        best_diff = float('inf')
        
        for threshold, performance in threshold_performance.items():
            if decision_type == 'approve':
                metric_value = performance.get('precision', 0)
                diff = abs(metric_value - target_metric)
            else:  # reject
                metric_value = performance.get('recall', 0)
                diff = abs(metric_value - target_metric)
            
            if diff < best_diff:
                best_diff = diff
                best_threshold = threshold
        
        return best_threshold or (AUTO_APPROVE_THRESHOLD if decision_type == 'approve' else AUTO_REJECT_THRESHOLD)
    
    def _calculate_threshold_performance(self, threshold, decisions, decision_type):
        """Calculate performance metrics for a given threshold."""
        # Get automated decisions at or above this threshold
        relevant_decisions = decisions.filter(
            confidence__gte=threshold,
            decision_type=decision_type,
            is_automated=True
        )
        
        if not relevant_decisions.exists():
            return {'sample_count': 0}
        
        # Count outcomes
        total_decisions = relevant_decisions.count()
        
        # Count appeals and their outcomes
        upheld_count = 0
        overturned_count = 0
        
        for decision in relevant_decisions:
            appeals = decision.appeals.all()
            if appeals.exists():
                latest_appeal = appeals.latest('created_at')
                if latest_appeal.final_outcome == AppealOutcome.UPHELD:
                    upheld_count += 1
                elif latest_appeal.final_outcome == AppealOutcome.OVERTURNED:
                    overturned_count += 1
        
        # Calculate metrics
        if decision_type == 'approve':
            # Precision: correct approvals / total approvals
            precision = (total_decisions - upheld_count) / total_decisions if total_decisions > 0 else 0
            return {
                'sample_count': total_decisions,
                'precision': precision,
                'upheld_appeals': upheld_count,
                'overturned_appeals': overturned_count
            }
        else:  # reject
            # Recall: correct rejections / total rejections
            recall = (total_decisions - overturned_count) / total_decisions if total_decisions > 0 else 0
            return {
                'sample_count': total_decisions,
                'recall': recall,
                'upheld_appeals': upheld_count,
                'overturned_appeals': overturned_count
            }
    
    def _calculate_human_review_thresholds(self, risk_scores):
        """Calculate optimal human review thresholds based on risk scores."""
        if not risk_scores:
            return {'lower': HUMAN_REVIEW_LOWER, 'upper': HUMAN_REVIEW_UPPER}
        
        # Calculate percentiles
        sorted_scores = sorted(risk_scores)
        n = len(sorted_scores)
        
        # Use 25th and 75th percentiles as default ranges
        lower_percentile = int(0.25 * n)
        upper_percentile = int(0.75 * n)
        
        lower_threshold = sorted_scores[lower_percentile] if n > 0 else HUMAN_REVIEW_LOWER
        upper_threshold = sorted_scores[upper_percentile] if n > 0 else HUMAN_REVIEW_UPPER
        
        return {
            'lower': round(lower_threshold, 2),
            'upper': round(upper_threshold, 2)
        }
    
    def _calculate_std(self, values):
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def _show_calibration_results(self, current_performance, calibrated_thresholds, threshold_type):
        """Display calibration results."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('CALIBRATION RESULTS')
        self.stdout.write('='*50)
        
        # Current performance
        self.stdout.write('\nCurrent Performance:')
        if 'auto_approval_metrics' in current_performance:
            metrics = current_performance['auto_approval_metrics']
            if metrics['sample_count'] > 0:
                self.stdout.write(f"  Auto-approval precision: {metrics['precision']:.3f}")
                self.stdout.write(f"  Avg confidence: {metrics['avg_confidence']:.3f}")
                self.stdout.write(f"  Sample count: {metrics['sample_count']}")
        
        if 'auto_rejection_metrics' in current_performance:
            metrics = current_performance['auto_rejection_metrics']
            if metrics['sample_count'] > 0:
                self.stdout.write(f"  Auto-rejection recall: {metrics['recall']:.3f}")
                self.stdout.write(f"  Avg confidence: {metrics['avg_confidence']:.3f}")
                self.stdout.write(f"  Sample count: {metrics['sample_count']}")
        
        # Recommended thresholds
        self.stdout.write('\nRecommended Thresholds:')
        
        if threshold_type in ['auto_approve', 'all']:
            current_approve = current_performance['current_thresholds']['auto_approve']
            recommended_approve = calibrated_thresholds['auto_approve']
            
            self.stdout.write(f"  Auto-approval:")
            self.stdout.write(f"    Current: {current_approve}")
            self.stdout.write(f"    Recommended: {recommended_approve}")
            
            if current_approve:
                change = recommended_approve - current_approve[0] if current_approve else 0
                self.stdout.write(f"    Change: {change:+.3f}")
        
        if threshold_type in ['auto_reject', 'all']:
            current_reject = current_performance['current_thresholds']['auto_reject']
            recommended_reject = calibrated_thresholds['auto_reject']
            
            self.stdout.write(f"  Auto-rejection:")
            self.stdout.write(f"    Current: {current_reject}")
            self.stdout.write(f"    Recommended: {recommended_reject}")
            
            if current_reject:
                change = recommended_reject - current_reject[0] if current_reject else 0
                self.stdout.write(f"    Change: {change:+.3f}")
        
        if threshold_type in ['human_review', 'all']:
            current_review = {'lower': HUMAN_REVIEW_LOWER, 'upper': HUMAN_REVIEW_UPPER}
            recommended_review = calibrated_thresholds['human_review']
            
            self.stdout.write(f"  Human review:")
            self.stdout.write(f"    Current: {current_review['lower']} - {current_review['upper']}")
            self.stdout.write(f"    Recommended: {recommended_review['lower']} - {recommended_review['upper']}")
            
            lower_change = recommended_review['lower'] - current_review['lower']
            upper_change = recommended_review['upper'] - current_review['upper']
            self.stdout.write(f"    Changes: {lower_change:+.3f} / {upper_change:+.3f}")
        
        self.stdout.write('='*50)
    
    def _apply_calibrated_thresholds(self, calibrated_thresholds, threshold_type, confidence_tolerance):
        """Apply calibrated thresholds to rules and models."""
        results = {
            'rules_updated': 0,
            'models_updated': 0,
            'errors': []
        }
        
        try:
            with transaction.atomic():
                # Update auto-approval rules
                if threshold_type in ['auto_approve', 'all']:
                    approve_threshold = calibrated_thresholds['auto_approve']
                    rules_updated = self._update_approval_rules('auto_approve', approve_threshold, confidence_tolerance)
                    results['rules_updated'] += rules_updated
                
                # Update auto-rejection rules
                if threshold_type in ['auto_reject', 'all']:
                    reject_threshold = calibrated_thresholds['auto_reject']
                    rules_updated = self._update_approval_rules('auto_reject', reject_threshold, confidence_tolerance)
                    results['rules_updated'] += rules_updated
                
                # Update ML models if needed
                if threshold_type in ['all']:
                    models_updated = self._update_model_thresholds(calibrated_thresholds, confidence_tolerance)
                    results['models_updated'] += models_updated
        
        except Exception as exc:
            results['errors'].append(str(exc))
            logger.error(f"Failed to apply thresholds: {exc}")
        
        return results
    
    def _update_approval_rules(self, action, new_threshold, tolerance):
        """Update approval rules with new threshold."""
        rules = AutoApprovalRule.objects.filter(action=action, is_active=True)
        updated_count = 0
        
        for rule in rules:
            current_threshold = rule.confidence_threshold
            threshold_diff = abs(new_threshold - current_threshold)
            
            # Only update if difference is significant
            if threshold_diff >= tolerance:
                rule.confidence_threshold = new_threshold
                rule.save(update_fields=['confidence_threshold', 'updated_at'])
                updated_count += 1
                
                self.stdout.write(
                    f"Updated rule '{rule.name}': {current_threshold:.3f} → {new_threshold:.3f}"
                )
        
        return updated_count
    
    def _update_model_thresholds(self, calibrated_thresholds, tolerance):
        """Update ML model thresholds if applicable."""
        # This would update model configuration or constants
        # For now, return 0 as models don't have configurable thresholds in this implementation
        return 0
    
    def _show_application_results(self, results):
        """Display threshold application results."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('THRESHOLD APPLICATION RESULTS')
        self.stdout.write('='*50)
        
        self.stdout.write(f"Rules updated: {results['rules_updated']}")
        self.stdout.write(f"Models updated: {results['models_updated']}")
        
        if results['errors']:
            self.stdout.write('\nErrors:')
            for error in results['errors']:
                self.stdout.write(f"  {error}")
        
        self.stdout.write('='*50)
        
        # Log summary
        logger.info(
            f"Threshold calibration applied: {results['rules_updated']} rules updated, "
            f"{results['models_updated']} models updated"
        )
