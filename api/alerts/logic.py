"""
Business logic for alerts app
"""
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Avg, F, Window
from django.db.models.functions import TruncHour, TruncDate
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AlertLogic:
    """Core business logic for alert processing"""
    
    @staticmethod
    def evaluate_threshold(rule, current_value: float) -> Tuple[bool, float]:
        """Evaluate if threshold is breached"""
        threshold_value = rule.threshold_value
        breach_percentage = 0
        
        if current_value > threshold_value:
            breach_percentage = ((current_value - threshold_value) / threshold_value) * 100
            return True, breach_percentage
        
        return False, breach_percentage
    
    @staticmethod
    def check_cooldown(rule) -> bool:
        """Check if alert rule is in cooldown"""
        if not rule.last_triggered:
            return False
        
        if not rule.cooldown_minutes:
            return False
        
        cooldown_end = rule.last_triggered + timedelta(minutes=rule.cooldown_minutes)
        return timezone.now() < cooldown_end
    
    @staticmethod
    def calculate_severity_score(alert_log) -> float:
        """Calculate severity score for alert"""
        base_scores = {
            'low': 1.0,
            'medium': 2.0,
            'high': 3.0,
            'critical': 4.0
        }
        
        base_score = base_scores.get(alert_log.rule.severity, 2.0)
        
        # Adjust based on breach percentage
        if hasattr(alert_log, 'exceed_percentage'):
            breach_multiplier = 1 + (alert_log.exceed_percentage / 100)
            base_score *= breach_multiplier
        
        # Adjust based on age
        age_minutes = (timezone.now() - alert_log.triggered_at).total_seconds() / 60
        if age_minutes > 60:  # Older than 1 hour
            age_multiplier = 1 + (age_minutes / 60) * 0.1
            base_score *= age_multiplier
        
        return round(base_score, 2)
    
    @staticmethod
    def determine_escalation_level(alert_log) -> int:
        """Determine escalation level for alert"""
        if alert_log.is_resolved:
            return 0
        
        age_minutes = (timezone.now() - alert_log.triggered_at).total_seconds() / 60
        
        # Escalation based on age and severity
        severity_escalation_times = {
            'critical': {'level_1': 15, 'level_2': 30, 'level_3': 60, 'level_4': 120},
            'high': {'level_1': 30, 'level_2': 60, 'level_3': 120, 'level_4': 240},
            'medium': {'level_1': 60, 'level_2': 120, 'level_3': 240, 'level_4': 480},
            'low': {'level_1': 120, 'level_2': 240, 'level_3': 480, 'level_4': 960}
        }
        
        escalation_times = severity_escalation_times.get(alert_log.rule.severity, {})
        
        for level, time_limit in escalation_times.items():
            level_num = int(level.split('_')[1])
            if age_minutes >= time_limit:
                return level_num
        
        return 0
    
    @staticmethod
    def aggregate_alerts(alerts, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Aggregate alerts within time window"""
        if not alerts:
            return {
                'total_count': 0,
                'by_severity': {},
                'by_type': {},
                'by_rule': {},
                'average_resolution_time': 0,
                'unresolved_count': 0
            }
        
        cutoff_time = timezone.now() - timedelta(minutes=time_window_minutes)
        recent_alerts = [a for a in alerts if a.triggered_at >= cutoff_time]
        
        # Aggregate by severity
        by_severity = {}
        for alert in recent_alerts:
            severity = alert.rule.severity
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        # Aggregate by type
        by_type = {}
        for alert in recent_alerts:
            alert_type = alert.rule.alert_type
            by_type[alert_type] = by_type.get(alert_type, 0) + 1
        
        # Aggregate by rule
        by_rule = {}
        for alert in recent_alerts:
            rule_name = alert.rule.name
            by_rule[rule_name] = by_rule.get(rule_name, 0) + 1
        
        # Calculate average resolution time
        resolved_alerts = [a for a in recent_alerts if a.is_resolved and a.resolved_at]
        avg_resolution_time = 0
        if resolved_alerts:
            total_resolution_time = sum(
                (a.resolved_at - a.triggered_at).total_seconds() / 60
                for a in resolved_alerts
            )
            avg_resolution_time = total_resolution_time / len(resolved_alerts)
        
        unresolved_count = len([a for a in recent_alerts if not a.is_resolved])
        
        return {
            'total_count': len(recent_alerts),
            'by_severity': by_severity,
            'by_type': by_type,
            'by_rule': by_rule,
            'average_resolution_time': round(avg_resolution_time, 2),
            'unresolved_count': unresolved_count
        }
    
    @staticmethod
    def detect_alert_storm(alerts, threshold: int = 10, time_window_minutes: int = 5) -> bool:
        """Detect if there's an alert storm"""
        cutoff_time = timezone.now() - timedelta(minutes=time_window_minutes)
        recent_alerts = [a for a in alerts if a.triggered_at >= cutoff_time]
        
        return len(recent_alerts) >= threshold
    
    @staticmethod
    def calculate_mttr(alerts, days: int = 30) -> float:
        """Calculate Mean Time To Resolution (MTTR)"""
        cutoff_date = timezone.now() - timedelta(days=days)
        resolved_alerts = [
            a for a in alerts 
            if a.is_resolved and a.resolved_at and a.triggered_at >= cutoff_date
        ]
        
        if not resolved_alerts:
            return 0
        
        total_resolution_time = sum(
            (a.resolved_at - a.triggered_at).total_seconds() / 60
            for a in resolved_alerts
        )
        
        return round(total_resolution_time / len(resolved_alerts), 2)
    
    @staticmethod
    def calculate_mttd(alerts, days: int = 30) -> float:
        """Calculate Mean Time To Detection (MTTD)"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # For MTTD, we need to know when the underlying issue started
        # This is a simplified calculation using trigger time as detection time
        recent_alerts = [
            a for a in alerts 
            if a.triggered_at >= cutoff_date
        ]
        
        if not recent_alerts:
            return 0
        
        # This is a placeholder - real MTTD would need more context
        # about when the actual issue started vs when it was detected
        return round(sum(1 for _ in recent_alerts) / len(recent_alerts), 2)


class NotificationLogic:
    """Business logic for notification processing"""
    
    @staticmethod
    def determine_notification_channels(alert_log) -> List[str]:
        """Determine which notification channels to use"""
        channels = []
        rule = alert_log.rule
        
        if rule.send_email and rule.email_recipients:
            channels.append('email')
        
        if rule.send_telegram and rule.telegram_chat_id:
            channels.append('telegram')
        
        if rule.send_sms and rule.sms_recipients:
            channels.append('sms')
        
        if rule.send_webhook and rule.webhook_url:
            channels.append('webhook')
        
        return channels
    
    @staticmethod
    def prioritize_notifications(notifications) -> List[Dict[str, Any]]:
        """Prioritize notifications based on urgency and channel"""
        priority_map = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }
        
        prioritized = []
        for notification in notifications:
            alert_log = notification.alert_log
            severity = alert_log.rule.severity
            
            priority = priority_map.get(severity, 2)
            
            # Channel priority
            channel_priority = {
                'sms': 4,
                'webhook': 3,
                'telegram': 2,
                'email': 1
            }
            
            channel_priority_score = channel_priority.get(notification.notification_type, 1)
            
            # Age factor
            age_minutes = (timezone.now() - notification.created_at).total_seconds() / 60
            age_factor = min(age_minutes / 60, 2)  # Max 2x priority
            
            final_priority = priority * channel_priority_score * (1 + age_factor)
            
            prioritized.append({
                'notification': notification,
                'priority': final_priority,
                'severity': severity,
                'channel': notification.notification_type
            })
        
        # Sort by priority (highest first)
        prioritized.sort(key=lambda x: x['priority'], reverse=True)
        return prioritized
    
    @staticmethod
    def should_retry_notification(notification) -> bool:
        """Determine if notification should be retried"""
        if notification.status != 'failed':
            return False
        
        if notification.retry_count >= notification.max_retries:
            return False
        
        # Exponential backoff
        retry_delay = notification.get_retry_delay()
        time_since_last_retry = (
            timezone.now() - notification.last_retry_at
        ).total_seconds() if notification.last_retry_at else float('inf')
        
        return time_since_last_retry >= retry_delay
    
    @staticmethod
    def format_notification_message(alert_log, channel_type: str) -> Tuple[str, str]:
        """Format notification message for specific channel"""
        rule = alert_log.rule
        
        # Base message
        base_message = f"Alert: {rule.name}"
        if rule.description:
            base_message += f"\n{rule.description}"
        
        base_message += f"\nSeverity: {rule.severity.upper()}"
        base_message += f"\nValue: {alert_log.trigger_value} (Threshold: {alert_log.threshold_value})"
        base_message += f"\nTime: {alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Channel-specific formatting
        if channel_type == 'email':
            subject = f"[{rule.severity.upper()}] {rule.name}"
            message = base_message + f"\n\nDetails:\n{alert_log.message}"
            
        elif channel_type == 'sms':
            subject = None  # SMS doesn't have subject
            # Truncate for SMS
            message = f"[{rule.severity.upper()}] {rule.name}: {alert_log.trigger_value} > {alert_log.threshold_value}"
            
        elif channel_type == 'telegram':
            subject = None
            message = f"🚨 *{rule.severity.upper()} Alert*\n\n"
            message += f"*{rule.name}*\n"
            message += f"Value: `{alert_log.trigger_value}` (Threshold: `{alert_log.threshold_value}`)\n"
            message += f"Time: `{alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
            message += f"```{alert_log.message}```"
            
        elif channel_type == 'webhook':
            subject = f"Alert: {rule.name}"
            message = alert_log.message
            
        else:
            subject = f"Alert: {rule.name}"
            message = base_message
        
        return subject, message


class EscalationLogic:
    """Business logic for alert escalation"""
    
    @staticmethod
    def should_escalate(alert_log, escalation_config) -> bool:
        """Determine if alert should be escalated"""
        if alert_log.is_resolved:
            return False
        
        if alert_log.escalation_level >= escalation_config.level:
            return False
        
        age_minutes = (timezone.now() - alert_log.triggered_at).total_seconds() / 60
        return age_minutes >= escalation_config.delay_minutes
    
    @staticmethod
    def get_escalation_recipients(escalation_config) -> Dict[str, List[str]]:
        """Get escalation recipients"""
        recipients = {
            'emails': [],
            'phones': [],
            'users': []
        }
        
        if escalation_config.escalate_to_email:
            recipients['emails'] = [
                email.strip() for email in escalation_config.escalate_to_email.split(',')
                if email.strip()
            ]
        
        if escalation_config.escalate_to_sms:
            recipients['phones'] = [
                phone.strip() for phone in escalation_config.escalate_to_sms.split(',')
                if phone.strip()
            ]
        
        if escalation_config.escalate_to_user:
            recipients['users'] = [escalation_config.escalate_to_user]
        
        return recipients
    
    @staticmethod
    def format_escalation_message(alert_log, escalation_config) -> str:
        """Format escalation message"""
        context = {
            'alert_id': alert_log.id,
            'rule_name': alert_log.rule.name,
            'triggered_at': alert_log.triggered_at.strftime('%Y-%m-%d %H:%M:%S'),
            'delay': escalation_config.delay_minutes,
            'trigger_value': alert_log.trigger_value,
            'threshold_value': alert_log.threshold_value,
            'severity': alert_log.rule.severity,
            'age_minutes': int((timezone.now() - alert_log.triggered_at).total_seconds() / 60)
        }
        
        try:
            return escalation_config.message_template.format(**context)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            return f"Alert {alert_log.id} for rule '{alert_log.rule.name}' requires escalation."


class AnalyticsLogic:
    """Business logic for analytics processing"""
    
    @staticmethod
    def calculate_alert_trends(alerts, days: int = 7) -> Dict[str, Any]:
        """Calculate alert trends over time"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Group by day
        daily_data = {}
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            day_alerts = [
                a for a in alerts 
                if a.triggered_at.date() == current_date
            ]
            
            daily_data[current_date.isoformat()] = {
                'total': len(day_alerts),
                'resolved': len([a for a in day_alerts if a.is_resolved]),
                'by_severity': {}
            }
            
            # Count by severity
            for alert in day_alerts:
                severity = alert.rule.severity
                daily_data[current_date.isoformat()]['by_severity'][severity] = \
                    daily_data[current_date.isoformat()]['by_severity'].get(severity, 0) + 1
            
            current_date += timedelta(days=1)
        
        return {
            'period': f"{days} days",
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'daily_data': daily_data,
            'trend': AnalyticsLogic._calculate_trend_direction(daily_data)
        }
    
    @staticmethod
    def _calculate_trend_direction(daily_data) -> str:
        """Calculate trend direction from daily data"""
        if len(daily_data) < 2:
            return 'insufficient_data'
        
        values = [data['total'] for data in daily_data.values()]
        
        # Simple linear regression to determine trend
        n = len(values)
        x_values = list(range(n))
        
        sum_x = sum(x_values)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(x_values, values))
        sum_x2 = sum(x * x for x in x_values)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        if slope > 0.5:
            return 'increasing'
        elif slope < -0.5:
            return 'decreasing'
        else:
            return 'stable'
    
    @staticmethod
    def calculate_sla_compliance(alerts, sla_minutes: int = 60) -> Dict[str, Any]:
        """Calculate SLA compliance metrics"""
        resolved_alerts = [
            a for a in alerts 
            if a.is_resolved and a.resolved_at
        ]
        
        if not resolved_alerts:
            return {
                'total_alerts': len(alerts),
                'resolved_alerts': 0,
                'sla_compliant': 0,
                'sla_compliance_rate': 0,
                'average_resolution_time': 0
            }
        
        compliant_alerts = []
        total_resolution_time = 0
        
        for alert in resolved_alerts:
            resolution_time = (alert.resolved_at - alert.triggered_at).total_seconds() / 60
            total_resolution_time += resolution_time
            
            if resolution_time <= sla_minutes:
                compliant_alerts.append(alert)
        
        return {
            'total_alerts': len(alerts),
            'resolved_alerts': len(resolved_alerts),
            'sla_compliant': len(compliant_alerts),
            'sla_compliance_rate': round(
                (len(compliant_alerts) / len(resolved_alerts)) * 100, 2
            ),
            'average_resolution_time': round(total_resolution_time / len(resolved_alerts), 2)
        }
    
    @staticmethod
    def identify_top_alert_rules(alerts, limit: int = 10) -> List[Dict[str, Any]]:
        """Identify top alert rules by frequency"""
        rule_counts = {}
        
        for alert in alerts:
            rule_name = alert.rule.name
            rule_counts[rule_name] = rule_counts.get(rule_name, 0) + 1
        
        # Sort by count (descending)
        sorted_rules = sorted(
            rule_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {
                'rule_name': rule_name,
                'alert_count': count,
                'percentage': round((count / len(alerts)) * 100, 2)
            }
            for rule_name, count in sorted_rules[:limit]
        ]


class HealthLogic:
    """Business logic for system health monitoring"""
    
    @staticmethod
    def calculate_system_health_score(health_checks) -> float:
        """Calculate overall system health score"""
        if not health_checks:
            return 0.0
        
        total_score = 0
        weight_sum = 0
        
        # Weight health checks by importance
        weights = {
            'critical': 3.0,
            'high': 2.0,
            'medium': 1.0,
            'low': 0.5
        }
        
        for check in health_checks:
            status_scores = {
                'healthy': 100,
                'degraded': 50,
                'unhealthy': 0,
                'unknown': 25
            }
            
            score = status_scores.get(check.status, 25)
            weight = weights.get(check.priority, 1.0)
            
            total_score += score * weight
            weight_sum += weight
        
        return round(total_score / weight_sum, 2) if weight_sum > 0 else 0
    
    @staticmethod
    def determine_health_status(score: float) -> str:
        """Determine health status from score"""
        if score >= 90:
            return 'healthy'
        elif score >= 70:
            return 'degraded'
        elif score >= 50:
            return 'unhealthy'
        else:
            return 'critical'
    
    @staticmethod
    def check_response_time_health(response_time_ms: float) -> str:
        """Check response time health"""
        if response_time_ms <= 100:
            return 'excellent'
        elif response_time_ms <= 500:
            return 'good'
        elif response_time_ms <= 1000:
            return 'degraded'
        else:
            return 'poor'
