# =============================================================================
# fraud_detection/signals_kb.py
# =============================================================================
"""
Knowledge Base Signals for Fraud Detection System.

Provides Django signals for knowledge base operations,
learning systems, and adaptive fraud detection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import Signal, receiver
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.fraud_detection.models import (
    FraudCase, FraudAlert, FraudRule, FraudRiskProfile
)
from api.fraud_detection.services import (
    fraud_detection_service
)
from api.fraud_detection.events import (
    create_knowledge_updated_event, create_pattern_learned_event,
    create_model_trained_event
)
from api.fraud_detection.exceptions import FraudDetectionError


logger = logging.getLogger(__name__)

User = get_user_model()


# Custom knowledge base signals
knowledge_base_updated = Signal(
)

pattern_learned = Signal(
)

model_trained = Signal(
)

fraud_pattern_discovered = Signal(
)

knowledge_gap_identified = Signal(
)

rule_performance_updated = Signal(
)

user_behavior_analyzed = Signal(
)

threat_intelligence_updated = Signal(
)


@receiver(post_save, sender=FraudCase)
def fraud_case_knowledge_update(sender, instance: FraudCase, created: bool, **kwargs):
    """
    Update knowledge base when fraud case is created or updated.
    
    Args:
        sender: Model class
        instance: FraudCase instance
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    try:
        if created:
            # Learn from new fraud case
            _learn_from_fraud_case(instance)
            
            # Update pattern knowledge
            _update_pattern_knowledge(instance)
            
            # Identify knowledge gaps
            _identify_knowledge_gaps(instance)
        else:
            # Update from case changes
            _update_from_case_changes(instance)
            
            # Track rule performance
            _track_rule_performance(instance)
        
        # Send knowledge base updated signal
        knowledge_base_updated.send(
            sender=sender,
            instance=instance,
            knowledge_type='fraud_case',
            changes={'created': created, 'updated': not created}
        )
        
    except Exception as e:
        logger.error(f"Error in fraud case knowledge update: {e}")


@receiver(post_save, sender=FraudAlert)
def fraud_alert_pattern_learning(sender, instance: FraudAlert, created: bool, **kwargs):
    """
    Learn patterns from fraud alerts.
    
    Args:
        sender: Model class
        instance: FraudAlert instance
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    try:
        if created:
            # Analyze alert patterns
            patterns = _analyze_alert_patterns(instance)
            
            if patterns:
                for pattern in patterns:
                    pattern_learned.send(
                        sender=sender,
                        pattern=pattern,
                        confidence=pattern.get('confidence', 0.5),
                        source='fraud_alert',
                        metadata={'alert_id': str(instance.pk)}
                    )
            
            # Update user behavior analysis
            _update_user_behavior_analysis(instance)
        
    except Exception as e:
        logger.error(f"Error in fraud alert pattern learning: {e}")


@receiver(post_save, sender=FraudRule)
def fraud_rule_performance_tracking(sender, instance: FraudRule, created: bool, **kwargs):
    """
    Track fraud rule performance and update knowledge.
    
    Args:
        sender: Model class
        instance: FraudRule instance
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    try:
        if not created:
            # Calculate rule performance metrics
            old_metrics = getattr(instance, '_old_metrics', {})
            new_metrics = _calculate_rule_metrics(instance)
            
            if old_metrics and new_metrics:
                improvement = _calculate_improvement(old_metrics, new_metrics)
                
                rule_performance_updated.send(
                    sender=sender,
                    rule=instance,
                    old_metrics=old_metrics,
                    new_metrics=new_metrics,
                    improvement=improvement
                )
            
            # Update rule knowledge
            _update_rule_knowledge(instance)
        
    except Exception as e:
        logger.error(f"Error in fraud rule performance tracking: {e}")


@receiver(post_save, sender=FraudRiskProfile)
def risk_profile_knowledge_update(sender, instance: FraudRiskProfile, created: bool, **kwargs):
    """
    Update knowledge from risk profile changes.
    
    Args:
        sender: Model class
        instance: FraudRiskProfile instance
        created: Whether this is a new instance
        **kwargs: Additional keyword arguments
    """
    try:
        if not created:
            # Analyze risk changes
            risk_changes = _analyze_risk_changes(instance)
            
            if risk_changes['significant']:
                # Update user behavior knowledge
                user_behavior_analyzed.send(
                    sender=sender,
                    user_id=instance.user_id,
                    behavior_patterns=risk_changes['patterns'],
                    risk_indicators=risk_changes['indicators'],
                    recommendations=risk_changes['recommendations']
                )
            
            # Update risk knowledge base
            _update_risk_knowledge(instance)
        
    except Exception as e:
        logger.error(f"Error in risk profile knowledge update: {e}")


@receiver(knowledge_base_updated)
def handle_knowledge_base_update(sender, instance, knowledge_type: str, changes: Dict[str, Any], **kwargs):
    """
    Handle knowledge base updates.
    
    Args:
        sender: Signal sender
        instance: Model instance
        knowledge_type: Type of knowledge
        changes: Changes made
        **kwargs: Additional keyword arguments
    """
    try:
        # Create knowledge update event
        create_knowledge_updated_event(
            entity_id=str(instance.pk),
            entity_type=knowledge_type,
            description=f"Knowledge base updated for {knowledge_type}",
            changes=changes,
            metadata={
                'timestamp': timezone.now().isoformat(),
                'knowledge_type': knowledge_type
            }
        )
        
        # Trigger model retraining if needed
        if _should_trigger_retraining(knowledge_type, changes):
            _schedule_model_retraining(knowledge_type)
        
    except Exception as e:
        logger.error(f"Error handling knowledge base update: {e}")


@receiver(pattern_learned)
def handle_pattern_learned(sender, pattern: Dict[str, Any], confidence: float, 
                         source: str, metadata: Dict[str, Any], **kwargs):
    """
    Handle learned patterns.
    
    Args:
        sender: Signal sender
        pattern: Learned pattern
        confidence: Pattern confidence
        source: Pattern source
        metadata: Additional metadata
        **kwargs: Additional keyword arguments
    """
    try:
        # Create pattern learned event
        create_pattern_learned_event(
            pattern_type=pattern.get('type', 'unknown'),
            confidence=confidence,
            description=f"Pattern learned from {source}",
            pattern_data=pattern,
            metadata={
                'source': source,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        # Update pattern database
        _update_pattern_database(pattern, confidence, source)
        
        # Consider creating new rule if pattern is strong
        if confidence > 0.8 and pattern.get('actionable', False):
            _suggest_new_rule(pattern)
        
    except Exception as e:
        logger.error(f"Error handling pattern learned: {e}")


@receiver(model_trained)
def handle_model_trained(sender, model_type: str, performance_metrics: Dict[str, Any], 
                        training_data_size: int, **kwargs):
    """
    Handle model training completion.
    
    Args:
        sender: Signal sender
        model_type: Type of model trained
        performance_metrics: Performance metrics
        training_data_size: Size of training data
        **kwargs: Additional keyword arguments
    """
    try:
        # Create model trained event
        create_model_trained_event(
            model_type=model_type,
            performance=performance_metrics,
            training_data_size=training_data_size,
            description=f"Model {model_type} training completed",
            metadata={
                'timestamp': timezone.now().isoformat(),
                'training_data_size': training_data_size
            }
        )
        
        # Update model knowledge base
        _update_model_knowledge(model_type, performance_metrics)
        
        # Deploy model if performance is good
        if _should_deploy_model(performance_metrics):
            _deploy_trained_model(model_type)
        
    except Exception as e:
        logger.error(f"Error handling model trained: {e}")


# Knowledge base helper functions
def _learn_from_fraud_case(case: FraudCase):
    """Learn from fraud case data."""
    try:
        # Extract features from case
        features = _extract_case_features(case)
        
        # Update feature knowledge
        _update_feature_knowledge(features)
        
        # Update pattern knowledge
        _update_case_pattern_knowledge(case)
        
        logger.info(f"Learned from fraud case {case.pk}")
        
    except Exception as e:
        logger.error(f"Error learning from fraud case {case.pk}: {e}")


def _update_pattern_knowledge(case: FraudCase):
    """Update pattern knowledge from case."""
    try:
        # Identify patterns in case
        patterns = _identify_case_patterns(case)
        
        for pattern in patterns:
            pattern_learned.send(
                sender=FraudCase,
                pattern=pattern,
                confidence=pattern.get('confidence', 0.5),
                source='fraud_case',
                metadata={'case_id': str(case.pk)}
            )
        
    except Exception as e:
        logger.error(f"Error updating pattern knowledge: {e}")


def _identify_knowledge_gaps(case: FraudCase):
    """Identify knowledge gaps from case."""
    try:
        gaps = []
        
        # Check for missing detection methods
        if case.detection_method == 'manual_review':
            gaps.append({
                'gap_type': 'detection_method',
                'description': 'Case detected manually - need automated detection',
                'priority': 'high',
                'suggested_actions': ['create_automated_rule', 'enhance_ml_model']
            })
        
        # Check for unknown patterns
        if not case.evidence_summary or len(case.evidence_summary) < 2:
            gaps.append({
                'gap_type': 'pattern_recognition',
                'description': 'Insufficient evidence patterns identified',
                'priority': 'medium',
                'suggested_actions': ['improve_evidence_collection', 'enhance_pattern_detection']
            })
        
        # Send signals for identified gaps
        for gap in gaps:
            knowledge_gap_identified.send(
                sender=FraudCase,
                gap_type=gap['gap_type'],
                description=gap['description'],
                priority=gap['priority'],
                suggested_actions=gap['suggested_actions']
            )
        
    except Exception as e:
        logger.error(f"Error identifying knowledge gaps: {e}")


def _analyze_alert_patterns(alert: FraudAlert) -> List[Dict[str, Any]]:
    """Analyze patterns in fraud alert."""
    patterns = []
    
    try:
        # Analyze trigger data patterns
        if alert.trigger_data:
            trigger_patterns = _analyze_trigger_data_patterns(alert.trigger_data)
            patterns.extend(trigger_patterns)
        
        # Analyze context patterns
        if alert.context:
            context_patterns = _analyze_context_patterns(alert.context)
            patterns.extend(context_patterns)
        
        # Analyze temporal patterns
        temporal_patterns = _analyze_temporal_patterns(alert)
        patterns.extend(temporal_patterns)
        
    except Exception as e:
        logger.error(f"Error analyzing alert patterns: {e}")
    
    return patterns


def _update_user_behavior_analysis(alert: FraudAlert):
    """Update user behavior analysis from alert."""
    try:
        # Get user's historical behavior
        user_id = alert.user_id
        
        # Analyze behavior patterns
        behavior_patterns = _analyze_user_behavior(user_id)
        
        # Identify risk indicators
        risk_indicators = _identify_risk_indicators(user_id, alert)
        
        # Generate recommendations
        recommendations = _generate_behavior_recommendations(user_id, behavior_patterns, risk_indicators)
        
        # Send signal
        user_behavior_analyzed.send(
            sender=FraudAlert,
            user_id=user_id,
            behavior_patterns=behavior_patterns,
            risk_indicators=risk_indicators,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Error updating user behavior analysis: {e}")


def _calculate_rule_metrics(rule: FraudRule) -> Dict[str, Any]:
    """Calculate performance metrics for fraud rule."""
    try:
        # Get rule performance data
        from api.fraud_detection.selectors import fraud_case_selector
        
        # Calculate metrics (simplified)
        metrics = {
            'trigger_count': 0,  # Would be calculated from actual data
            'true_positive_rate': 0.0,
            'false_positive_rate': 0.0,
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0
        }
        
        # In production, this would query actual performance data
        # For now, return placeholder metrics
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating rule metrics: {e}")
        return {}


def _calculate_improvement(old_metrics: Dict[str, Any], new_metrics: Dict[str, Any]) -> Dict[str, float]:
    """Calculate improvement between metric sets."""
    improvement = {}
    
    try:
        for metric in ['precision', 'recall', 'f1_score']:
            old_val = old_metrics.get(metric, 0)
            new_val = new_metrics.get(metric, 0)
            
            if old_val > 0:
                improvement[metric] = (new_val - old_val) / old_val
            else:
                improvement[metric] = 0.0 if new_val == 0 else 1.0
        
    except Exception as e:
        logger.error(f"Error calculating improvement: {e}")
    
    return improvement


def _update_rule_knowledge(rule: FraudRule):
    """Update knowledge base with rule information."""
    try:
        # Extract rule patterns
        rule_patterns = _extract_rule_patterns(rule)
        
        # Update pattern database
        for pattern in rule_patterns:
            _update_pattern_database(pattern, rule.confidence_score, 'fraud_rule')
        
    except Exception as e:
        logger.error(f"Error updating rule knowledge: {e}")


def _analyze_risk_changes(profile: FraudRiskProfile) -> Dict[str, Any]:
    """Analyze changes in risk profile."""
    try:
        changes = {
            'significant': False,
            'patterns': [],
            'indicators': [],
            'recommendations': []
        }
        
        # Check for significant risk score change
        if profile.previous_risk_score:
            score_change = abs(profile.current_risk_score - profile.previous_risk_score)
            if score_change >= 20:  # Significant change threshold
                changes['significant'] = True
                changes['indicators'].append({
                    'type': 'risk_score_change',
                    'value': score_change,
                    'direction': 'increasing' if profile.current_risk_score > profile.previous_risk_score else 'decreasing'
                })
        
        # Analyze risk factors
        if profile.risk_factors:
            factor_patterns = _analyze_risk_factors(profile.risk_factors)
            changes['patterns'].extend(factor_patterns)
        
        # Generate recommendations
        if profile.current_risk_score >= 70:
            changes['recommendations'].append('enhanced_monitoring')
        if profile.risk_trend == 'increasing':
            changes['recommendations'].append('investigation_required')
        
        return changes
        
    except Exception as e:
        logger.error(f"Error analyzing risk changes: {e}")
        return {'significant': False, 'patterns': [], 'indicators': [], 'recommendations': []}


def _should_trigger_retraining(knowledge_type: str, changes: Dict[str, Any]) -> bool:
    """Determine if model retraining should be triggered."""
    try:
        # Retraining triggers
        retraining_triggers = {
            'fraud_case': changes.get('created', False),
            'fraud_alert': changes.get('created', False),
            'fraud_rule': changes.get('updated', False)
        }
        
        return retraining_triggers.get(knowledge_type, False)
        
    except Exception as e:
        logger.error(f"Error determining retraining trigger: {e}")
        return False


def _schedule_model_retraining(model_type: str):
    """Schedule model retraining."""
    try:
        from api.fraud_detection.background_jobs import fraud_detection_job_manager
        
        # Schedule retraining task
        job_data = {
            'model_type': model_type,
            'retraining_reason': 'knowledge_base_update',
            'scheduled_at': timezone.now().isoformat()
        }
        
        fraud_detection_job_manager.submit_task(
            'model_retraining',
            job_data,
            priority='high'
        )
        
        logger.info(f"Scheduled model retraining for {model_type}")
        
    except Exception as e:
        logger.error(f"Error scheduling model retraining: {e}")


def _update_pattern_database(pattern: Dict[str, Any], confidence: float, source: str):
    """Update pattern database with new pattern."""
    try:
        # This would update a pattern database or machine learning model
        # For now, just log the pattern
        logger.info(f"Pattern updated: {pattern.get('type', 'unknown')} (confidence: {confidence}, source: {source})")
        
    except Exception as e:
        logger.error(f"Error updating pattern database: {e}")


def _suggest_new_rule(pattern: Dict[str, Any]):
    """Suggest creation of new rule from pattern."""
    try:
        # Create suggestion for new rule
        suggestion = {
            'pattern': pattern,
            'suggested_rule': {
                'name': f"Auto-generated rule for {pattern.get('type', 'unknown')}",
                'description': f"Automatically generated rule based on learned pattern",
                'conditions': pattern.get('conditions', []),
                'actions': pattern.get('suggested_actions', ['flag_user']),
                'priority': 'medium',
                'enabled': False  # Start disabled for review
            }
        }
        
        # Send suggestion to administrators
        _send_rule_suggestion_to_admins(suggestion)
        
    except Exception as e:
        logger.error(f"Error suggesting new rule: {e}")


def _should_deploy_model(performance_metrics: Dict[str, Any]) -> bool:
    """Determine if trained model should be deployed."""
    try:
        # Deployment criteria
        min_precision = 0.8
        min_recall = 0.7
        min_f1_score = 0.75
        
        precision = performance_metrics.get('precision', 0)
        recall = performance_metrics.get('recall', 0)
        f1_score = performance_metrics.get('f1_score', 0)
        
        return (precision >= min_precision and 
                recall >= min_recall and 
                f1_score >= min_f1_score)
        
    except Exception as e:
        logger.error(f"Error determining model deployment: {e}")
        return False


def _deploy_trained_model(model_type: str):
    """Deploy trained model."""
    try:
        # This would deploy the model to production
        logger.info(f"Deploying trained model: {model_type}")
        
        # Create deployment event
        from api.fraud_detection.events import create_model_deployed_event
        create_model_deployed_event(
            model_type=model_type,
            description=f"Model {model_type} deployed to production",
            metadata={
                'deployment_time': timezone.now().isoformat(),
                'deployed_by': 'system'
            }
        )
        
    except Exception as e:
        logger.error(f"Error deploying trained model: {e}")


# Helper functions for pattern analysis
def _extract_case_features(case: FraudCase) -> Dict[str, Any]:
    """Extract features from fraud case."""
    return {
        'case_type': case.case_type,
        'severity': case.severity,
        'risk_score': case.risk_score,
        'detection_method': case.detection_method,
        'financial_impact': case.financial_impact,
        'regulatory_impact': case.regulatory_impact
    }


def _identify_case_patterns(case: FraudCase) -> List[Dict[str, Any]]:
    """Identify patterns in fraud case."""
    patterns = []
    
    # Simple pattern identification
    if case.financial_impact and case.financial_impact > 10000:
        patterns.append({
            'type': 'high_financial_impact',
            'confidence': 0.8,
            'features': {'amount_range': 'high'},
            'actionable': True
        })
    
    if case.severity == 'critical':
        patterns.append({
            'type': 'critical_severity',
            'confidence': 0.9,
            'features': {'severity': 'critical'},
            'actionable': True
        })
    
    return patterns


def _analyze_trigger_data_patterns(trigger_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Analyze patterns in trigger data."""
    patterns = []
    
    # Analyze amount patterns
    amount = trigger_data.get('amount')
    if amount and float(amount) > 5000:
        patterns.append({
            'type': 'high_amount_trigger',
            'confidence': 0.7,
            'features': {'amount_threshold': 5000},
            'actionable': True
        })
    
    return patterns


def _analyze_context_patterns(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Analyze patterns in context data."""
    patterns = []
    
    # Analyze location patterns
    location = context.get('location', {})
    country = location.get('country')
    if country and country in ['CN', 'RU', 'IR']:
        patterns.append({
            'type': 'high_risk_location',
            'confidence': 0.6,
            'features': {'country': country},
            'actionable': True
        })
    
    return patterns


def _analyze_temporal_patterns(alert: FraudAlert) -> List[Dict[str, Any]]:
    """Analyze temporal patterns in alert."""
    patterns = []
    
    # Check for unusual time
    hour = alert.created_at.hour
    if hour < 6 or hour > 22:
        patterns.append({
            'type': 'unusual_time',
            'confidence': 0.5,
            'features': {'hour': hour},
            'actionable': False
        })
    
    return patterns


def _analyze_user_behavior(user_id: Union[int, str]) -> Dict[str, Any]:
    """Analyze user behavior patterns."""
    # This would analyze user's historical behavior
    return {
        'transaction_frequency': 'normal',
        'amount_patterns': 'consistent',
        'location_patterns': 'stable',
        'time_patterns': 'regular'
    }


def _identify_risk_indicators(user_id: Union[int, str], alert: FraudAlert) -> List[Dict[str, Any]]:
    """Identify risk indicators for user."""
    indicators = []
    
    if alert.severity_score >= 70:
        indicators.append({
            'type': 'high_severity_alert',
            'severity': 'high',
            'description': 'User triggered high severity alert'
        })
    
    return indicators


def _generate_behavior_recommendations(user_id: Union[int, str], 
                                     behavior_patterns: Dict[str, Any],
                                     risk_indicators: List[Dict[str, Any]]) -> List[str]:
    """Generate behavior-based recommendations."""
    recommendations = []
    
    if risk_indicators:
        recommendations.append('enhanced_monitoring')
    
    if behavior_patterns.get('transaction_frequency') == 'unusual':
        recommendations.append('transaction_limit_review')
    
    return recommendations


# Export all signals and functions
__all__ = [
    # Custom signals
    'knowledge_base_updated',
    'pattern_learned',
    'model_trained',
    'fraud_pattern_discovered',
    'knowledge_gap_identified',
    'rule_performance_updated',
    'user_behavior_analyzed',
    'threat_intelligence_updated',
    
    # Signal receivers
    'fraud_case_knowledge_update',
    'fraud_alert_pattern_learning',
    'fraud_rule_performance_tracking',
    'risk_profile_knowledge_update',
    'handle_knowledge_base_update',
    'handle_pattern_learned',
    'handle_model_trained',
]
