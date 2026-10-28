"""
logic.py – Business logic layer for postback module.

Provides comprehensive business logic including:
- Postback processing logic
- Validation logic
- Analytics calculations
- Business rules engine
"""
from django.db import models
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig
from .choices import PostbackStatus, RejectionReason
from .exceptions import PostbackException

logger = logging.getLogger(__name__)


class BusinessRuleType(Enum):
    """Business rule type enumeration."""
    VALIDATION = "validation"
    PROCESSING = "processing"
    REWARD = "reward"
    NOTIFICATION = "notification"
    ANALYTICS = "analytics"


class BusinessRule:
    """
    Business rule definition and execution.
    
    Provides framework for defining and executing business
    rules with conditions, actions, and priorities.
    """
    
    def __init__(self, name: str, rule_type: BusinessRuleType, priority: int = 50):
        self.name = name
        self.rule_type = rule_type
        self.priority = priority
        self.conditions = []
        self.actions = []
        self.enabled = True
        self.execution_count = 0
        self.success_count = 0
    
    def add_condition(self, condition_func: callable):
        """Add a condition function."""
        self.conditions.append(condition_func)
    
    def add_action(self, action_func: callable):
        """Add an action function."""
        self.actions.append(action_func)
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate all conditions.
        
        Args:
            context: Evaluation context
            
        Returns:
            True if all conditions are met
        """
        if not self.enabled:
            return False
        
        for condition in self.conditions:
            try:
                if not condition(context):
                    return False
            except Exception as e:
                logger.error(f"Error in condition for rule {self.name}: {str(e)}")
                return False
        
        return True
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all actions.
        
        Args:
            context: Execution context
            
        Returns:
            Execution results
        """
        self.execution_count += 1
        
        results = []
        
        for action in self.actions:
            try:
                result = action(context)
                results.append(result)
                self.success_count += 1
            except Exception as e:
                logger.error(f"Error in action for rule {self.name}: {str(e)}")
                results.append({'error': str(e)})
        
        return {
            'rule_name': self.name,
            'results': results,
            'success_count': self.success_count,
            'execution_count': self.execution_count,
        }


class PostbackProcessingLogic:
    """
    Core postback processing business logic.
    
    Provides comprehensive logic for processing postbacks
    including validation, reward calculation, and analytics.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.business_rules = {}
        self.processing_stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'rejected': 0,
        }
    
    def process_postback(self, postback_data: Dict[str, Any], network_config: NetworkPostbackConfig) -> Dict[str, Any]:
        """
        Process postback through complete business logic pipeline.
        
        Args:
            postback_data: Postback data to process
            network_config: Network configuration
            
        Returns:
            Processing result
        """
        start_time = timezone.now()
        
        try:
            # Step 1: Validation
            validation_result = self._validate_postback(postback_data, network_config)
            if not validation_result['is_valid']:
                self.processing_stats['rejected'] += 1
                return {
                    'status': PostbackStatus.REJECTED.value,
                    'rejection_reason': validation_result['reason'],
                    'processing_time': (timezone.now() - start_time).total_seconds(),
                }
            
            # Step 2: Duplicate check
            duplicate_result = self._check_duplicates(postback_data, network_config)
            if duplicate_result['is_duplicate']:
                self.processing_stats['rejected'] += 1
                return {
                    'status': PostbackStatus.REJECTED.value,
                    'rejection_reason': RejectionReason.DUPLICATE_LEAD.value,
                    'processing_time': (timezone.now() - start_time).total_seconds(),
                }
            
            # Step 3: Business rules processing
            rules_result = self._apply_business_rules(postback_data, network_config)
            
            # Step 4: Reward calculation
            reward_result = self._calculate_reward(postback_data, network_config, rules_result)
            
            # Step 5: Analytics update
            analytics_result = self._update_analytics(postback_data, network_config, reward_result)
            
            # Step 6: Notifications
            notification_result = self._send_notifications(postback_data, network_config, reward_result)
            
            self.processing_stats['successful'] += 1
            
            return {
                'status': PostbackStatus.REWARDED.value,
                'payout': reward_result['payout'],
                'reward_points': reward_result['reward_points'],
                'processing_time': (timezone.now() - start_time).total_seconds(),
                'rules_applied': rules_result['applied_rules'],
                'analytics_updated': analytics_result['updated'],
                'notifications_sent': notification_result['sent'],
            }
            
        except Exception as e:
            self.processing_stats['failed'] += 1
            self.logger.error(f"Error processing postback: {str(e)}")
            
            return {
                'status': PostbackStatus.FAILED.value,
                'error': str(e),
                'processing_time': (timezone.now() - start_time).total_seconds(),
            }
        finally:
            self.processing_stats['total_processed'] += 1
    
    def _validate_postback(self, postback_data: Dict[str, Any], network_config: NetworkPostbackConfig) -> Dict[str, Any]:
        """Validate postback data."""
        # Check network status
        if not network_config.is_active:
            return {'is_valid': False, 'reason': 'Network inactive'}
        
        # Check required fields
        required_fields = network_config.required_fields or ['lead_id']
        for field in required_fields:
            if field not in postback_data or not postback_data[field]:
                return {'is_valid': False, 'reason': f'Missing required field: {field}'}
        
        # Check IP whitelist
        if network_config.ip_whitelist:
            source_ip = postback_data.get('source_ip')
            if not source_ip or source_ip not in network_config.ip_whitelist:
                return {'is_valid': False, 'reason': 'IP not whitelisted'}
        
        # Check signature if required
        if network_config.signature_algorithm != 'none':
            signature = postback_data.get('signature')
            if not signature:
                return {'is_valid': False, 'reason': 'Missing signature'}
            
            # Verify signature (simplified)
            if not self._verify_signature(postback_data, network_config):
                return {'is_valid': False, 'reason': 'Invalid signature'}
        
        return {'is_valid': True}
    
    def _check_duplicates(self, postback_data: Dict[str, Any], network_config: NetworkPostbackConfig) -> Dict[str, Any]:
        """Check for duplicate leads."""
        lead_id = postback_data.get('lead_id')
        
        if not lead_id:
            return {'is_duplicate': False}
        
        # Check if lead ID already exists for this network
        existing_postback = PostbackLog.objects.filter(
            network=network_config,
            lead_id=lead_id,
            status__in=[PostbackStatus.REWARDED, PostbackStatus.RECEIVED]
        ).first()
        
        return {'is_duplicate': existing_postback is not None}
    
    def _apply_business_rules(self, postback_data: Dict[str, Any], network_config: NetworkPostbackConfig) -> Dict[str, Any]:
        """Apply business rules."""
        context = {
            'postback_data': postback_data,
            'network_config': network_config,
            'timestamp': timezone.now(),
        }
        
        applied_rules = []
        
        # Get rules for this network
        rules = self.business_rules.get(network_config.network_key, [])
        
        # Sort by priority (highest first)
        rules.sort(key=lambda r: r.priority, reverse=True)
        
        for rule in rules:
            if rule.evaluate(context):
                result = rule.execute(context)
                applied_rules.append(result['rule_name'])
        
        return {'applied_rules': applied_rules}
    
    def _calculate_reward(self, postback_data: Dict[str, Any], network_config: NetworkPostbackConfig, rules_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate reward for postback."""
        # Default reward
        payout = postback_data.get('payout', network_config.default_reward_points or 0)
        reward_points = network_config.default_reward_points or 0
        
        # Apply reward rules
        context = {
            'postback_data': postback_data,
            'network_config': network_config,
            'base_payout': payout,
            'base_points': reward_points,
        }
        
        reward_rules = [r for r in self.business_rules.get(network_config.network_key, []) 
                      if r.rule_type == BusinessRuleType.REWARD]
        
        for rule in reward_rules:
            if rule.evaluate(context):
                result = rule.execute(context)
                # Update payout based on rule results
                for rule_result in result['results']:
                    if isinstance(rule_result, dict) and 'payout_adjustment' in rule_result:
                        payout += rule_result['payout_adjustment']
                    if isinstance(rule_result, dict) and 'points_adjustment' in rule_result:
                        reward_points += rule_result['points_adjustment']
        
        # Apply maximum payout limit
        if network_config.max_payout and payout > network_config.max_payout:
            payout = network_config.max_payout
        
        return {
            'payout': float(payout),
            'reward_points': int(reward_points),
        }
    
    def _update_analytics(self, postback_data: Dict[str, Any], network_config: NetworkPostbackConfig, reward_result: Dict[str, Any]) -> Dict[str, Any]:
        """Update analytics data."""
        try:
            # Update daily insight
            today = timezone.now().date()
            insight, created = PostbackInsight.objects.get_or_create(
                network=network_config,
                date=today,
                defaults={
                    'received_count': 0,
                    'rewarded_count': 0,
                    'rejected_count': 0,
                    'total_payout': 0,
                }
            )
            
            insight.received_count += 1
            insight.rewarded_count += 1
            insight.total_payout += Decimal(str(reward_result['payout']))
            insight.save()
            
            return {'updated': True, 'insight_id': str(insight.id)}
            
        except Exception as e:
            self.logger.error(f"Error updating analytics: {str(e)}")
            return {'updated': False, 'error': str(e)}
    
    def _send_notifications(self, postback_data: Dict[str, Any], network_config: NetworkPostbackConfig, reward_result: Dict[str, Any]) -> Dict[str, Any]:
        """Send notifications."""
        sent_notifications = []
        
        # Get notification rules
        notification_rules = [r for r in self.business_rules.get(network_config.network_key, []) 
                             if r.rule_type == BusinessRuleType.NOTIFICATION]
        
        context = {
            'postback_data': postback_data,
            'network_config': network_config,
            'reward_result': reward_result,
        }
        
        for rule in notification_rules:
            if rule.evaluate(context):
                result = rule.execute(context)
                sent_notifications.append(result['rule_name'])
        
        return {'sent': sent_notifications}
    
    def _verify_signature(self, postback_data: Dict[str, Any], network_config: NetworkPostbackConfig) -> bool:
        """Verify postback signature."""
        # Simplified signature verification
        # In production, this would implement proper HMAC verification
        signature = postback_data.get('signature')
        return bool(signature)
    
    def add_business_rule(self, network_key: str, rule: BusinessRule):
        """Add business rule for a network."""
        if network_key not in self.business_rules:
            self.business_rules[network_key] = []
        
        self.business_rules[network_key].append(rule)
        self.logger.info(f"Added business rule {rule.name} for network {network_key}")
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        total = self.processing_stats['total_processed']
        success_rate = (self.processing_stats['successful'] / total * 100) if total > 0 else 0
        
        return {
            **self.processing_stats,
            'success_rate': f"{success_rate:.2f}%",
            'total_rules': sum(len(rules) for rules in self.business_rules.values()),
        }


class AnalyticsLogic:
    """
    Analytics calculation business logic.
    
    Provides logic for calculating analytics metrics,
    generating reports, and detecting anomalies.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def calculate_daily_insight(self, network_config: NetworkPostbackConfig, date: datetime.date = None) -> Dict[str, Any]:
        """
        Calculate daily insight for a network.
        
        Args:
            network_config: Network configuration
            date: Date to calculate (default: today)
            
        Returns:
            Calculated insight data
        """
        if date is None:
            date = timezone.now().date()
        
        # Get postback logs for the date
        start_datetime = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        end_datetime = start_datetime + timedelta(days=1)
        
        postback_logs = PostbackLog.objects.filter(
            network=network_config,
            received_at__gte=start_datetime,
            received_at__lt=end_datetime
        )
        
        # Calculate metrics
        total_received = postback_logs.count()
        rewarded_count = postback_logs.filter(status=PostbackStatus.REWARDED).count()
        rejected_count = postback_logs.filter(status=PostbackStatus.REJECTED).count()
        
        total_payout = postback_logs.filter(status=PostbackStatus.REWARDED).aggregate(
            total=models.Sum('payout')
        )['total'] or Decimal('0')
        
        # Calculate health score
        if total_received > 0:
            success_rate = (rewarded_count / total_received) * 100
            health_score = min(100, success_rate * 1.2)  # Bonus for high success rates
        else:
            health_score = 0
        
        # Detect anomalies
        anomalies = self._detect_anomalies(network_config, date, {
            'received_count': total_received,
            'rewarded_count': rewarded_count,
            'health_score': health_score,
        })
        
        return {
            'network_key': network_config.network_key,
            'date': date.isoformat(),
            'received_count': total_received,
            'rewarded_count': rewarded_count,
            'rejected_count': rejected_count,
            'total_payout': float(total_payout),
            'health_score': health_score,
            'anomaly_detected': len(anomalies) > 0,
            'anomaly_details': anomalies,
        }
    
    def _detect_anomalies(self, network_config: NetworkPostbackConfig, date: datetime.date, current_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies in metrics."""
        anomalies = []
        
        # Get historical data for comparison (last 7 days)
        end_date = date - timedelta(days=1)
        start_date = end_date - timedelta(days=6)
        
        historical_insights = PostbackInsight.objects.filter(
            network=network_config,
            date__gte=start_date,
            date__lte=end_date
        )
        
        if historical_insights.count() == 0:
            return anomalies  # No historical data for comparison
        
        # Calculate historical averages
        avg_received = historical_insights.aggregate(avg=models.Avg('received_count'))['avg'] or 0
        avg_health = historical_insights.aggregate(avg=models.Avg('health_score'))['avg'] or 0
        
        # Detect anomalies
        current_received = current_metrics['received_count']
        current_health = current_metrics['health_score']
        
        # Volume anomaly (more than 3x average)
        if avg_received > 0 and current_received > avg_received * 3:
            anomalies.append({
                'type': 'volume_spike',
                'description': f"Received count ({current_received}) is {current_received/avg_received:.1f}x higher than 7-day average ({avg_received:.1f})",
                'severity': 'high',
            })
        
        # Health score anomaly (below 50% of average)
        if avg_health > 0 and current_health < avg_health * 0.5:
            anomalies.append({
                'type': 'health_decline',
                'description': f"Health score ({current_health}) is significantly below 7-day average ({avg_health:.1f})",
                'severity': 'medium',
            })
        
        return anomalies
    
    def generate_network_report(self, network_config: NetworkPostbackConfig, start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """
        Generate comprehensive network report.
        
        Args:
            network_config: Network configuration
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Generated report data
        """
        # Get insights for the period
        insights = PostbackInsight.objects.filter(
            network=network_config,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        if not insights:
            return {'error': 'No data available for the specified period'}
        
        # Calculate aggregate metrics
        total_received = sum(insight.received_count for insight in insights)
        total_rewarded = sum(insight.rewarded_count for insight in insights)
        total_rejected = sum(insight.rejected_count for insight in insights)
        total_payout = sum(insight.total_payout for insight in insights)
        avg_health = sum(insight.health_score for insight in insights) / len(insights)
        
        # Find best and worst days
        best_day = max(insights, key=lambda i: i.health_score)
        worst_day = min(insights, key=lambda i: i.health_score)
        
        # Detect anomalies in the period
        period_anomalies = []
        for insight in insights:
            if insight.anomaly_detected:
                period_anomalies.append({
                    'date': insight.date.isoformat(),
                    'anomaly_details': insight.anomaly_details,
                })
        
        return {
            'network_key': network_config.network_key,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': len(insights),
            },
            'summary': {
                'total_received': total_received,
                'total_rewarded': total_rewarded,
                'total_rejected': total_rejected,
                'total_payout': float(total_payout),
                'average_health_score': avg_health,
                'success_rate': f"{(total_rewarded/total_received*100):.2f}%" if total_received > 0 else "0%",
            },
            'performance': {
                'best_day': {
                    'date': best_day.date.isoformat(),
                    'health_score': best_day.health_score,
                    'received_count': best_day.received_count,
                },
                'worst_day': {
                    'date': worst_day.date.isoformat(),
                    'health_score': worst_day.health_score,
                    'received_count': worst_day.received_count,
                },
            },
            'anomalies': {
                'total_anomalies': len(period_anomalies),
                'anomaly_details': period_anomalies,
            },
            'daily_data': [
                {
                    'date': insight.date.isoformat(),
                    'received_count': insight.received_count,
                    'rewarded_count': insight.rewarded_count,
                    'rejected_count': insight.rejected_count,
                    'health_score': insight.health_score,
                    'total_payout': float(insight.total_payout),
                }
                for insight in insights
            ],
        }


# Global logic instances
postback_logic = PostbackProcessingLogic()
analytics_logic = AnalyticsLogic()


# Convenience functions
def process_postback_business_logic(postback_data: Dict[str, Any], network_config: NetworkPostbackConfig) -> Dict[str, Any]:
    """Process postback using business logic."""
    return postback_logic.process_postback(postback_data, network_config)


def calculate_daily_analytics(network_config: NetworkPostbackConfig, date: datetime.date = None) -> Dict[str, Any]:
    """Calculate daily analytics."""
    return analytics_logic.calculate_daily_insight(network_config, date)


def generate_network_report(network_config: NetworkPostbackConfig, start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
    """Generate network report."""
    return analytics_logic.generate_network_report(network_config, start_date, end_date)


def add_business_rule(network_key: str, rule: BusinessRule):
    """Add business rule."""
    postback_logic.add_business_rule(network_key, rule)


def get_processing_statistics() -> Dict[str, Any]:
    """Get processing statistics."""
    return postback_logic.get_processing_statistics()
