# =============================================================================
# auto_mod/services/AutoApprovalService.py
# =============================================================================

"""
Service for managing auto-approval of low-risk content.
Handles rule evaluation, risk assessment, and automatic decision making.
"""

from __future__ import annotations
from django.db.models import Avg
from django.db.models import Max
from django.db.models import Min

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..choices import ModerationStatus, RiskLevel, RuleAction
from ..constants import (
    AUTO_APPROVE_THRESHOLD,
    AUTO_REJECT_THRESHOLD,
    HUMAN_REVIEW_LOWER,
    HUMAN_REVIEW_UPPER,
    CONFIDENCE_MIN,
    CONFIDENCE_MAX,
)
from ..exceptions import (
    InvalidRuleConfigError,
    RuleEvaluationError,
    SubmissionAlreadyProcessedError,
    InvalidSubmissionError,
)
from ..models import AutoApprovalRule, SuspiciousSubmission, ModerationDecision, ContentSignal
from ..signals import rule_matched, moderation_decision_made

logger = logging.getLogger(__name__)
User = get_user_model()


class AutoApprovalService:
    """
    Service for managing auto-approval of low-risk content.
    """
    
    def __init__(self):
        self.logger = logger

    # ---------------------------------------------------------------------------
    # Auto-Approval Evaluation
    # ---------------------------------------------------------------------------

    @transaction.atomic
    def evaluate_submission_for_auto_approval(
        self,
        submission: SuspiciousSubmission,
        force_evaluation: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluate a submission for automatic approval/rejection.
        
        Args:
            submission: The submission to evaluate
            force_evaluation: Force evaluation even if already processed
            
        Returns:
            Evaluation results with recommendation
            
        Raises:
            SubmissionAlreadyProcessedError: If submission already processed
            InvalidSubmissionError: If submission is invalid
        """
        try:
            # Check if already processed
            if not force_evaluation and submission.status != ModerationStatus.PENDING:
                raise SubmissionAlreadyProcessedError(
                    f"Submission already processed: {submission.status}"
                )
            
            # Validate submission
            if not self._validate_submission(submission):
                raise InvalidSubmissionError("Submission validation failed")
            
            # Get applicable rules
            rules = AutoApprovalRule.objects.for_evaluation(submission.submission_type)
            
            if not rules.exists():
                return {
                    "submission_id": str(submission.pk),
                    "recommendation": "human_review",
                    "confidence": 0.0,
                    "reason": "No applicable rules found",
                    "matched_rules": [],
                    "risk_score": submission.risk_score,
                    "auto_approvable": False
                }
            
            # Evaluate rules
            evaluation_results = []
            for rule in rules:
                try:
                    result = self._evaluate_rule(submission, rule)
                    if result["matched"]:
                        evaluation_results.append(result)
                except Exception as exc:
                    self.logger.warning(f"rule_evaluation.failed rule={rule.pk}: {exc}")
                    continue
            
            # Get aggregated signals if available
            signal_aggregation = self._get_signal_aggregation(submission)
            
            # Calculate overall confidence and recommendation
            recommendation, confidence, reason = self._calculate_recommendation(
                evaluation_results,
                signal_aggregation,
                submission
            )
            
            # Determine if auto-approvable
            auto_approvable = self._is_auto_approvable(recommendation, confidence)
            
            result = {
                "submission_id": str(submission.pk),
                "recommendation": recommendation,
                "confidence": confidence,
                "reason": reason,
                "matched_rules": evaluation_results,
                "signal_aggregation": signal_aggregation,
                "risk_score": submission.risk_score,
                "auto_approvable": auto_approvable,
                "evaluated_at": timezone.now().isoformat()
            }
            
            self.logger.info(
                f"auto_approval_evaluation submission={submission.pk} "
                f"recommendation={recommendation} confidence={confidence:.3f} "
                f"auto_approvable={auto_approvable}"
            )
            
            return result
            
        except (SubmissionAlreadyProcessedError, InvalidSubmissionError):
            raise
        except Exception as exc:
            self.logger.error(f"evaluate_submission_for_auto_approval.failed submission={submission.pk}: {exc}")
            raise RuleEvaluationError(f"Auto-approval evaluation failed: {exc}")

    @transaction.atomic
    def execute_auto_decision(
        self,
        submission: SuspiciousSubmission,
        recommendation: str,
        confidence: float,
        reason: str,
        applied_rules: Optional[List[AutoApprovalRule]] = None
    ) -> ModerationDecision:
        """
        Execute an automatic decision on a submission.
        
        Args:
            submission: The submission to decide on
            recommendation: The recommendation (approve/reject/escalate)
            confidence: Confidence level (0-1)
            reason: Decision reason
            applied_rules: Rules that were applied
            
        Returns:
            Created ModerationDecision instance
            
        Raises:
            RuleEvaluationError: If decision cannot be executed
        """
        try:
            # Validate confidence
            if not (CONFIDENCE_MIN <= confidence <= CONFIDENCE_MAX):
                raise RuleEvaluationError(f"Invalid confidence: {confidence}")
            
            # Map recommendation to decision type
            decision_mapping = {
                "approve_automatically": ModerationStatus.AUTO_APPROVED,
                "reject_automatically": ModerationStatus.AUTO_REJECTED,
                "escalate_priority": ModerationStatus.ESCALATED,
                "human_review_required": ModerationStatus.HUMAN_REVIEW
            }
            
            if recommendation not in decision_mapping:
                raise RuleEvaluationError(f"Invalid recommendation: {recommendation}")
            
            # Create decision
            decision = ModerationDecision.objects.create(
                submission=submission,
                decision_type=decision_mapping[recommendation],
                reason=reason,
                confidence=confidence,
                is_automated=True,
                applied_rule=applied_rules[0] if applied_rules else None
            )
            
            # Update submission status
            submission.status = decision_mapping[recommendation]
            submission.save(update_fields=['status'])
            
            # Send signals
            moderation_decision_made.send(
                sender=SuspiciousSubmission,
                submission=submission,
                decision=decision_mapping[recommendation]
            )
            
            if applied_rules:
                for rule in applied_rules:
                    rule_matched.send(
                        sender=AutoApprovalRule,
                        rule=rule,
                        submission=submission
                    )
            
            self.logger.info(
                f"auto_decision_executed submission={submission.pk} "
                f"decision={decision.decision_type} confidence={confidence:.3f}"
            )
            
            return decision
            
        except RuleEvaluationError:
            raise
        except Exception as exc:
            self.logger.error(f"execute_auto_decision.failed submission={submission.pk}: {exc}")
            raise RuleEvaluationError(f"Failed to execute auto decision: {exc}")

    # ---------------------------------------------------------------------------
    # Batch Processing
    # ---------------------------------------------------------------------------

    def process_pending_submissions(
        self,
        submission_type: Optional[str] = None,
        batch_size: int = 100,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Process pending submissions for auto-approval.
        
        Args:
            submission_type: Filter by submission type
            batch_size: Number of submissions to process
            dry_run: If True, only evaluate without executing decisions
            
        Returns:
            Processing statistics
        """
        try:
            # Get pending submissions
            queryset = SuspiciousSubmission.objects.filter(status=ModerationStatus.PENDING)
            
            if submission_type:
                queryset = queryset.filter(submission_type=submission_type)
            
            queryset = queryset.order_by('created_at')[:batch_size]
            
            processed_count = 0
            approved_count = 0
            rejected_count = 0
            escalated_count = 0
            human_review_count = 0
            errors = 0
            
            for submission in queryset:
                try:
                    # Evaluate submission
                    evaluation = self.evaluate_submission_for_auto_approval(submission)
                    
                    if evaluation["auto_approvable"] and not dry_run:
                        # Execute auto decision
                        decision = self.execute_auto_decision(
                            submission=submission,
                            recommendation=evaluation["recommendation"],
                            confidence=evaluation["confidence"],
                            reason=evaluation["reason"]
                        )
                        
                        # Count by decision type
                        if decision.decision_type == ModerationStatus.AUTO_APPROVED:
                            approved_count += 1
                        elif decision.decision_type == ModerationStatus.AUTO_REJECTED:
                            rejected_count += 1
                        elif decision.decision_type == ModerationStatus.ESCALATED:
                            escalated_count += 1
                        else:
                            human_review_count += 1
                    
                    else:
                        # Mark for human review
                        if not dry_run:
                            submission.status = ModerationStatus.HUMAN_REVIEW
                            submission.save(update_fields=['status'])
                            human_review_count += 1
                    
                    processed_count += 1
                    
                except Exception as exc:
                    self.logger.warning(f"process_pending_submission.failed submission={submission.pk}: {exc}")
                    errors += 1
            
            return {
                "processed": processed_count,
                "approved": approved_count,
                "rejected": rejected_count,
                "escalated": escalated_count,
                "human_review": human_review_count,
                "errors": errors,
                "dry_run": dry_run
            }
            
        except Exception as exc:
            self.logger.error(f"process_pending_submissions.failed: {exc}")
            raise RuleEvaluationError(f"Failed to process pending submissions: {exc}")

    # ---------------------------------------------------------------------------
    # Rule Management
    # ---------------------------------------------------------------------------

    @transaction.atomic
    def create_auto_approval_rule(
        self,
        name: str,
        submission_type: str,
        conditions: List[Dict[str, Any]],
        action: str,
        priority: int = 50,
        confidence_threshold: float = 0.8,
        is_system: bool = False,
        created_by: Optional[User] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AutoApprovalRule:
        """
        Create a new auto-approval rule.
        
        Args:
            name: Rule name
            submission_type: Type of submission this rule applies to
            conditions: List of conditions for the rule
            action: Action to take when rule matches
            priority: Rule priority (higher = more important)
            confidence_threshold: Minimum confidence for auto-approval
            is_system: Whether this is a system rule
            created_by: User creating the rule
            metadata: Additional rule metadata
            
        Returns:
            Created AutoApprovalRule instance
            
        Raises:
            InvalidRuleConfigError: If rule configuration is invalid
        """
        try:
            # Validate action
            if action not in [choice[0] for choice in RuleAction.choices]:
                raise InvalidRuleConfigError(f"Invalid action: {action}")
            
            # Validate conditions
            self._validate_rule_conditions(conditions)
            
            # Create rule
            rule = AutoApprovalRule.objects.create(
                name=name,
                submission_type=submission_type,
                conditions=conditions,
                action=action,
                priority=priority,
                confidence_threshold=confidence_threshold,
                is_system=is_system,
                created_by=created_by,
                metadata=metadata or {}
            )
            
            self.logger.info(
                f"auto_approval_rule_created rule={rule.pk} name={name} "
                f"action={action} priority={priority}"
            )
            
            return rule
            
        except InvalidRuleConfigError:
            raise
        except Exception as exc:
            self.logger.error(f"create_auto_approval_rule.failed: {exc}")
            raise InvalidRuleConfigError(f"Failed to create auto-approval rule: {exc}")

    def get_rule_effectiveness(
        self,
        rule: AutoApprovalRule,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze the effectiveness of an auto-approval rule.
        
        Args:
            rule: The rule to analyze
            days_back: Number of days to look back
            
        Returns:
            Rule effectiveness statistics
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Get decisions made using this rule
        decisions = ModerationDecision.objects.filter(
            applied_rule=rule,
            decided_at__gte=cutoff_date
        )
        
        if not decisions.exists():
            return {
                "rule_id": str(rule.pk),
                "rule_name": rule.name,
                "period_days": days_back,
                "total_decisions": 0,
                "approval_rate": 0,
                "avg_confidence": 0,
                "appeal_rate": 0
            }
        
        # Calculate statistics
        total_decisions = decisions.count()
        approved_decisions = decisions.filter(
            decision_type=ModerationStatus.AUTO_APPROVED
        ).count()
        
        avg_confidence = decisions.aggregate(
            avg_conf=Avg('confidence')
        )['avg_conf'] or 0
        
        # Calculate appeal rate
        appealed_decisions = decisions.filter(
            appeals__isnull=False
        ).distinct().count()
        
        appeal_rate = (appealed_decisions / total_decisions * 100) if total_decisions > 0 else 0
        
        return {
            "rule_id": str(rule.pk),
            "rule_name": rule.name,
            "period_days": days_back,
            "total_decisions": total_decisions,
            "approved_decisions": approved_decisions,
            "approval_rate": (approved_decisions / total_decisions * 100) if total_decisions > 0 else 0,
            "avg_confidence": avg_confidence,
            "appealed_decisions": appealed_decisions,
            "appeal_rate": appeal_rate
        }

    # ---------------------------------------------------------------------------
    # Risk Assessment
    # ---------------------------------------------------------------------------

    def calculate_risk_score(
        self,
        submission: SuspiciousSubmission,
        include_signals: bool = True
    ) -> float:
        """
        Calculate comprehensive risk score for a submission.
        
        Args:
            submission: The submission to score
            include_signals: Whether to include signal analysis
            
        Returns:
            Risk score (0-10, higher = more risky)
        """
        try:
            risk_score = 0.0
            
            # Base risk from submission
            base_risk = submission.risk_score or 0.0
            risk_score += base_risk
            
            # Risk from content signals
            if include_signals:
                signal_risk = self._calculate_signal_risk(submission)
                risk_score += signal_risk
            
            # Risk from submission characteristics
            characteristic_risk = self._calculate_characteristic_risk(submission)
            risk_score += characteristic_risk
            
            # Normalize to 0-10 scale
            risk_score = max(0.0, min(10.0, risk_score))
            
            return risk_score
            
        except Exception as exc:
            self.logger.error(f"calculate_risk_score.failed submission={submission.pk}: {exc}")
            return 5.0  # Default to medium risk

    def get_risk_assessment(
        self,
        submission: SuspiciousSubmission
    ) -> Dict[str, Any]:
        """
        Get comprehensive risk assessment for a submission.
        
        Args:
            submission: The submission to assess
            
        Returns:
            Risk assessment details
        """
        try:
            # Calculate risk score
            risk_score = self.calculate_risk_score(submission)
            
            # Determine risk level
            if risk_score <= 2.0:
                risk_level = RiskLevel.LOW
            elif risk_score <= 5.0:
                risk_level = RiskLevel.MEDIUM
            elif risk_score <= 7.5:
                risk_level = RiskLevel.HIGH
            else:
                risk_level = RiskLevel.CRITICAL
            
            # Get contributing factors
            factors = []
            
            # Base risk factor
            if submission.risk_score and submission.risk_score > 3.0:
                factors.append({
                    "type": "base_risk",
                    "value": submission.risk_score,
                    "description": "High base risk score"
                })
            
            # Signal risk factor
            signal_risk = self._calculate_signal_risk(submission)
            if signal_risk > 2.0:
                factors.append({
                    "type": "signal_risk",
                    "value": signal_risk,
                    "description": "High signal risk indicators"
                })
            
            # Characteristic risk factor
            char_risk = self._calculate_characteristic_risk(submission)
            if char_risk > 1.0:
                factors.append({
                    "type": "characteristic_risk",
                    "value": char_risk,
                    "description": "Suspicious content characteristics"
                })
            
            return {
                "submission_id": str(submission.pk),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "factors": factors,
                "recommendation": self._get_risk_recommendation(risk_score),
                "assessed_at": timezone.now().isoformat()
            }
            
        except Exception as exc:
            self.logger.error(f"get_risk_assessment.failed submission={submission.pk}: {exc}")
            return {
                "submission_id": str(submission.pk),
                "risk_score": 5.0,
                "risk_level": RiskLevel.MEDIUM,
                "factors": [],
                "recommendation": "human_review",
                "error": str(exc)
            }

    # ---------------------------------------------------------------------------
    # Statistics and Monitoring
    # ---------------------------------------------------------------------------

    def get_auto_approval_statistics(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive auto-approval statistics.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            Auto-approval statistics
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_back)
        
        # Get decisions in period
        decisions = ModerationDecision.objects.filter(
            decided_at__gte=cutoff_date,
            is_automated=True
        )
        
        # Decision breakdown
        total_auto_decisions = decisions.count()
        auto_approved = decisions.filter(decision_type=ModerationStatus.AUTO_APPROVED).count()
        auto_rejected = decisions.filter(decision_type=ModerationStatus.AUTO_REJECTED).count()
        auto_escalated = decisions.filter(decision_type=ModerationStatus.ESCALATED).count()
        
        # Confidence statistics
        confidence_stats = decisions.aggregate(
            avg_confidence=Avg('confidence'),
            min_confidence=Min('confidence'),
            max_confidence=Max('confidence')
        )
        
        # Rule effectiveness
        rule_stats = []
        rules = AutoApprovalRule.objects.filter(is_active=True)
        
        for rule in rules:
            effectiveness = self.get_rule_effectiveness(rule, days_back)
            if effectiveness["total_decisions"] > 0:
                rule_stats.append(effectiveness)
        
        # Error rate (appeals)
        appealed_decisions = decisions.filter(
            appeals__isnull=False
        ).distinct().count()
        
        error_rate = (appealed_decisions / total_auto_decisions * 100) if total_auto_decisions > 0 else 0
        
        return {
            "period_days": days_back,
            "total_auto_decisions": total_auto_decisions,
            "decision_breakdown": {
                "approved": auto_approved,
                "rejected": auto_rejected,
                "escalated": auto_escalated
            },
            "approval_rate": (auto_approved / total_auto_decisions * 100) if total_auto_decisions > 0 else 0,
            "confidence_stats": confidence_stats,
            "rule_effectiveness": rule_stats,
            "appealed_decisions": appealed_decisions,
            "error_rate": error_rate
        }

    # ---------------------------------------------------------------------------
    # Helper Methods
    # ---------------------------------------------------------------------------

    def _validate_submission(self, submission: SuspiciousSubmission) -> bool:
        """Validate submission for auto-approval."""
        # Check basic requirements
        if not submission.content_id:
            return False
        
        # Check if content is accessible
        # This would depend on your specific content storage system
        
        return True

    def _evaluate_rule(self, submission: SuspiciousSubmission, rule: AutoApprovalRule) -> Dict[str, Any]:
        """Evaluate a single rule against a submission."""
        try:
            matched = True
            condition_results = []
            
            for condition in rule.conditions:
                result = self._evaluate_condition(submission, condition)
                condition_results.append(result)
                
                # If any condition fails, rule doesn't match
                if not result["matched"]:
                    matched = False
                    break
            
            return {
                "rule_id": str(rule.pk),
                "rule_name": rule.name,
                "matched": matched,
                "action": rule.action,
                "confidence": rule.confidence_threshold,
                "condition_results": condition_results
            }
            
        except Exception as exc:
            self.logger.error(f"_evaluate_rule.failed rule={rule.pk}: {exc}")
            return {
                "rule_id": str(rule.pk),
                "matched": False,
                "error": str(exc)
            }

    def _evaluate_condition(self, submission: SuspiciousSubmission, condition: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a single condition."""
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        
        try:
            # Get actual value from submission
            actual_value = self._get_field_value(submission, field)
            
            # Apply operator
            matched = self._apply_operator(actual_value, operator, value)
            
            return {
                "field": field,
                "operator": operator,
                "expected_value": value,
                "actual_value": actual_value,
                "matched": matched
            }
            
        except Exception as exc:
            return {
                "field": field,
                "matched": False,
                "error": str(exc)
            }

    def _get_field_value(self, submission: SuspiciousSubmission, field: str) -> Any:
        """Get field value from submission."""
        if field == "risk_score":
            return submission.risk_score or 0
        elif field == "ai_confidence":
            return submission.ai_confidence or 0
        elif field == "submission_type":
            return submission.submission_type
        elif field == "flag_reason":
            return submission.flag_reason
        elif field.startswith("metadata."):
            metadata_key = field[9:]  # Remove "metadata." prefix
            metadata = submission.metadata or {}
            return metadata.get(metadata_key)
        else:
            raise ValueError(f"Unknown field: {field}")

    def _apply_operator(self, actual: Any, operator: str, expected: Any) -> bool:
        """Apply comparison operator."""
        if operator == "equals":
            return actual == expected
        elif operator == "not_equals":
            return actual != expected
        elif operator == "greater_than":
            return actual > expected
        elif operator == "less_than":
            return actual < expected
        elif operator == "greater_equal":
            return actual >= expected
        elif operator == "less_equal":
            return actual <= expected
        elif operator == "in":
            return actual in expected
        elif operator == "not_in":
            return actual not in expected
        elif operator == "contains":
            return str(expected).lower() in str(actual).lower()
        elif operator == "not_contains":
            return str(expected).lower() not in str(actual).lower()
        else:
            raise ValueError(f"Unknown operator: {operator}")

    def _get_signal_aggregation(self, submission: SuspiciousSubmission) -> Optional[Dict[str, Any]]:
        """Get signal aggregation for submission."""
        try:
            from .ContentSignalService import ContentSignalService
            signal_service = ContentSignalService()
            return signal_service.aggregate_signals_for_submission(submission)
        except Exception:
            return None

    def _calculate_recommendation(
        self,
        rule_results: List[Dict[str, Any]],
        signal_aggregation: Optional[Dict[str, Any]],
        submission: SuspiciousSubmission
    ) -> Tuple[str, float, str]:
        """Calculate final recommendation from rules and signals."""
        # If no rules matched, default to human review
        if not rule_results:
            return "human_review_required", 0.0, "No matching rules found"
        
        # Get highest confidence matched rule
        matched_rules = [r for r in rule_results if r["matched"]]
        
        if not matched_rules:
            return "human_review_required", 0.0, "No conditions matched"
        
        # Sort by confidence (highest first)
        matched_rules.sort(key=lambda x: x["confidence"], reverse=True)
        best_rule = matched_rules[0]
        
        # Consider signals if available
        signal_confidence = 0.0
        if signal_aggregation:
            signal_score = signal_aggregation.get("aggregate_score", 0)
            # Convert signal score to confidence
            signal_confidence = max(0, min(1, 1 - abs(signal_score) / 10))
        
        # Combine confidences
        rule_confidence = best_rule["confidence"]
        combined_confidence = (rule_confidence * 0.7) + (signal_confidence * 0.3)
        
        # Map rule action to recommendation
        action_mapping = {
            RuleAction.AUTO_APPROVE: "approve_automatically",
            RuleAction.AUTO_REJECT: "reject_automatically",
            RuleAction.ESCALATE: "escalate_priority",
            RuleAction.REQUEST_INFO: "human_review_required"
        }
        
        recommendation = action_mapping.get(best_rule["action"], "human_review_required")
        reason = f"Rule '{best_rule['rule_name']}' matched with confidence {combined_confidence:.3f}"
        
        return recommendation, combined_confidence, reason

    def _is_auto_approvable(self, recommendation: str, confidence: float) -> bool:
        """Determine if recommendation can be auto-executed."""
        if recommendation in ["approve_automatically", "reject_automatically"]:
            return confidence >= AUTO_APPROVE_THRESHOLD
        elif recommendation == "escalate_priority":
            return confidence >= AUTO_REJECT_THRESHOLD
        else:
            return False

    def _validate_rule_conditions(self, conditions: List[Dict[str, Any]]) -> None:
        """Validate rule conditions."""
        if not conditions:
            raise InvalidRuleConfigError("Rules must have at least one condition")
        
        for condition in conditions:
            required_fields = ["field", "operator", "value"]
            for field in required_fields:
                if field not in condition:
                    raise InvalidRuleConfigError(f"Condition missing required field: {field}")

    def _calculate_signal_risk(self, submission: SuspiciousSubmission) -> float:
        """Calculate risk contribution from signals."""
        try:
            signals = ContentSignal.objects.filter(submission=submission)
            
            if not signals.exists():
                return 0.0
            
            total_risk = 0.0
            
            for signal in signals:
                # Negative signals increase risk
                if not signal.is_positive:
                    weight = signal.weight or 1.0
                    confidence = signal.confidence or 0.5
                    
                    # Severity multiplier
                    severity_multipliers = {
                        RiskLevel.LOW: 1.0,
                        RiskLevel.MEDIUM: 1.5,
                        RiskLevel.HIGH: 2.0,
                        RiskLevel.CRITICAL: 3.0
                    }
                    
                    severity_mult = severity_multipliers.get(signal.severity, 1.0)
                    signal_risk = weight * confidence * severity_mult
                    total_risk += signal_risk
            
            return min(5.0, total_risk)  # Cap at 5.0
            
        except Exception:
            return 0.0

    def _calculate_characteristic_risk(self, submission: SuspiciousSubmission) -> float:
        """Calculate risk from submission characteristics."""
        risk = 0.0
        
        # Risk from low AI confidence
        if submission.ai_confidence and submission.ai_confidence < 0.5:
            risk += (0.5 - submission.ai_confidence) * 2
        
        # Risk from flag reasons
        if submission.flag_reason in ["spam", "inappropriate", "fraud"]:
            risk += 2.0
        elif submission.flag_reason in ["suspicious", "unusual"]:
            risk += 1.0
        
        return min(3.0, risk)  # Cap at 3.0

    def _get_risk_recommendation(self, risk_score: float) -> str:
        """Get recommendation based on risk score."""
        if risk_score <= 2.0:
            return "approve_automatically"
        elif risk_score <= 4.0:
            return "proceed_normal"
        elif risk_score <= 6.0:
            return "human_review_required"
        elif risk_score <= 8.0:
            return "escalate_priority"
        else:
            return "reject_automatically"
