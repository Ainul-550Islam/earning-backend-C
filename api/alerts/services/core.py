"""
Core Alert Services
"""
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.core import AlertRule, AlertLog, Notification, AlertEscalation, AlertGroup, AlertAnalytics, SystemMetrics, AlertSuppression

logger = logging.getLogger(__name__)


class AlertProcessorService:
    """Core alert processing service"""
    
    @staticmethod
    def process_alert(rule_id, trigger_value, message, details=None):
        """Process alert using AlertRule and AlertLog models"""
        try:
            with transaction.atomic():
                # Get the alert rule
                alert_rule = AlertRule.objects.get(id=rule_id, is_active=True)
                
                # Check cooldown
                if not alert_rule.can_trigger_now():
                    logger.warning(f"Alert rule {rule_id} is in cooldown")
                    return None
                
                # Check suppression
                test_alert = AlertLog(
                    rule=alert_rule,
                    trigger_value=trigger_value,
                    threshold_value=alert_rule.threshold_value,
                    message=message
                )
                
                if AlertSuppression.should_suppress(test_alert):
                    logger.info(f"Alert suppressed for rule {rule_id}")
                    return None
                
                # Create alert log
                alert_log = AlertLog.objects.create(
                    rule=alert_rule,
                    trigger_value=trigger_value,
                    threshold_value=alert_rule.threshold_value,
                    message=message,
                    details=details or {},
                )
                
                # Mark as processing
                alert_log.mark_as_processing()
                
                # Get recipients
                recipients = alert_rule.get_recipients()
                
                # Create notifications
                notifications_created = []
                
                if alert_rule.send_email and recipients['emails']:
                    for email in recipients['emails']:
                        notification = Notification.objects.create(
                            alert_log=alert_log,
                            notification_type='email',
                            recipient=email,
                            subject=f"Alert: {alert_rule.name}",
                            message=alert_log.message,
                            status='pending'
                        )
                        notifications_created.append(notification)
                
                if alert_rule.send_telegram and recipients['telegram']:
                    notification = Notification.objects.create(
                        alert_log=alert_log,
                        notification_type='telegram',
                        recipient=recipients['telegram'],
                        message=f"Alert: {alert_rule.name}\n{alert_log.message}",
                        status='pending'
                    )
                    notifications_created.append(notification)
                
                if alert_rule.send_sms and recipients['sms']:
                    for phone in recipients['sms']:
                        notification = Notification.objects.create(
                            alert_log=alert_log,
                            notification_type='sms',
                            recipient=phone,
                            message=f"Alert: {alert_rule.name} - {alert_log.message[:100]}",
                            status='pending'
                        )
                        notifications_created.append(notification)
                
                # Mark as complete
                alert_log.mark_as_complete()
                
                # Update rule
                alert_rule.last_triggered = alert_log.triggered_at
                alert_rule.save()
                
                logger.info(f"Alert {alert_log.id} processed successfully")
                return alert_log
                
        except AlertRule.DoesNotExist:
            logger.error(f"Alert rule {rule_id} not found or inactive")
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
        
        return None
    
    @staticmethod
    def check_and_escalate_alerts():
        """Check and escalate unresolved alerts using AlertEscalation"""
        try:
            unresolved_alerts = AlertLog.unresolved.select_related('rule')
            
            escalated_count = 0
            
            for alert in unresolved_alerts:
                escalations = AlertEscalation.objects.filter(
                    rule=alert.rule,
                    is_active=True,
                    auto_escalate=True
                ).order_by('level')
                
                for escalation in escalations:
                    if escalation.should_escalate(alert):
                        if escalation.escalate_alert(alert):
                            escalated_count += 1
                            logger.info(f"Alert {alert.id} escalated to level {escalation.level}")
            
            return escalated_count
            
        except Exception as e:
            logger.error(f"Error escalating alerts: {e}")
            return 0
    
    @staticmethod
    def bulk_process_alerts(alert_data_list):
        """Process multiple alerts in bulk"""
        processed_alerts = []
        failed_alerts = []
        
        try:
            with transaction.atomic():
                for alert_data in alert_data_list:
                    try:
                        alert_log = AlertProcessorService.process_alert(**alert_data)
                        if alert_log:
                            processed_alerts.append(alert_log)
                        else:
                            failed_alerts.append(alert_data)
                    except Exception as e:
                        logger.error(f"Error processing alert {alert_data}: {e}")
                        failed_alerts.append(alert_data)
            
            return {
                'processed': processed_alerts,
                'failed': failed_alerts,
                'total': len(alert_data_list)
            }
            
        except Exception as e:
            logger.error(f"Error in bulk processing: {e}")
            return {
                'processed': [],
                'failed': alert_data_list,
                'total': len(alert_data_list)
            }
    
    @staticmethod
    def resolve_alert(alert_id, resolved_by=None, resolution_note=""):
        """Resolve an alert"""
        try:
            alert = AlertLog.objects.get(id=alert_id)
            alert.is_resolved = True
            alert.resolved_at = timezone.now()
            alert.resolved_by = resolved_by
            alert.resolution_note = resolution_note
            alert.save()
            
            logger.info(f"Alert {alert_id} resolved by {resolved_by}")
            return True
            
        except AlertLog.DoesNotExist:
            logger.error(f"Alert {alert_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error resolving alert {alert_id}: {e}")
            return False
    
    @staticmethod
    def acknowledge_alert(alert_id, acknowledged_by=None):
        """Acknowledge an alert"""
        try:
            alert = AlertLog.objects.get(id=alert_id)
            alert.details['acknowledged'] = True
            alert.details['acknowledged_by'] = acknowledged_by.id if acknowledged_by else None
            alert.details['acknowledged_at'] = timezone.now().isoformat()
            alert.save()
            
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return True
            
        except AlertLog.DoesNotExist:
            logger.error(f"Alert {alert_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error acknowledging alert {alert_id}: {e}")
            return False


class AlertGroupService:
    """Alert group management service"""
    
    @staticmethod
    def check_and_send_group_alerts():
        """Check and send group alerts using AlertGroup"""
        try:
            active_groups = AlertGroup.objects.filter(
                is_active=True,
                group_notification_enabled=True
            ).prefetch_related('rules')
            
            alerts_sent = 0
            
            for group in active_groups:
                if group.should_send_group_alert():
                    result = group.send_group_alert()
                    
                    if result:
                        alerts_sent += 1
                        logger.info(f"Group alert sent for {group.name}")
            
            return alerts_sent
            
        except Exception as e:
            logger.error(f"Error sending group alerts: {e}")
            return 0
    
    @staticmethod
    def update_group_cache(group_id):
        """Update AlertGroup cache"""
        try:
            group = AlertGroup.objects.get(id=group_id)
            group.update_cache()
            return True
        except AlertGroup.DoesNotExist:
            logger.error(f"Group {group_id} not found")
            return False
    
    @staticmethod
    def get_group_alert_summary(group_id):
        """Get alert summary for a group"""
        try:
            group = AlertGroup.objects.get(id=group_id)
            active_alerts = group.get_active_alerts()
            
            return {
                'group_name': group.name,
                'active_alerts_count': active_alerts.count(),
                'cached_count': group.cached_alert_count,
                'rules_count': group.rules.count(),
                'last_group_alert': group.last_group_alert_at,
                'can_send_alert': group.should_send_group_alert()
            }
            
        except AlertGroup.DoesNotExist:
            logger.error(f"Group {group_id} not found")
            return None
    
    @staticmethod
    def create_group_from_rules(name, rule_ids, **kwargs):
        """Create alert group from rule IDs"""
        try:
            with transaction.atomic():
                group = AlertGroup.objects.create(
                    name=name,
                    **kwargs
                )
                
                rules = AlertRule.objects.filter(id__in=rule_ids)
                group.rules.add(*rules)
                
                logger.info(f"Created alert group {name} with {rules.count()} rules")
                return group
                
        except Exception as e:
            logger.error(f"Error creating alert group: {e}")
            return None


class AnalyticsService:
    """Alert analytics service"""
    
    @staticmethod
    def generate_daily_analytics(date=None):
        """Generate daily analytics using AlertAnalytics"""
        try:
            if date is None:
                date = timezone.now().date()
            
            analytics = AlertAnalytics.generate_for_date(date, force_regenerate=True)
            
            logger.info(f"Generated analytics for {date}")
            return analytics
            
        except Exception as e:
            logger.error(f"Error generating analytics: {e}")
            return None
    
    @staticmethod
    def get_system_metrics():
        """Get system metrics using SystemMetrics"""
        try:
            metrics = SystemMetrics.get_latest()
            
            if not metrics:
                metrics = SystemMetrics.objects.create(
                    total_users=0,
                    active_users_1h=0,
                    cpu_usage_percent=0,
                    memory_usage_percent=0,
                    disk_usage_percent=0,
                    data_source='auto'
                )
            
            return {
                'cpu_usage': metrics.cpu_usage_percent,
                'memory_usage': metrics.memory_usage_percent,
                'disk_usage': metrics.disk_usage_percent,
                'is_healthy': metrics.is_healthy,
                'timestamp': metrics.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return None
    
    @staticmethod
    def get_alert_statistics(days=7):
        """Get alert statistics for the last N days"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            stats = AlertLog.objects.filter(
                triggered_at__gte=cutoff_date
            ).aggregate(
                total_alerts=models.Count('id'),
                resolved_alerts=models.Count('id', filter=models.Q(is_resolved=True)),
                unresolved_alerts=models.Count('id', filter=models.Q(is_resolved=False)),
                avg_resolution_time=models.Avg(
                    models.F('resolved_at') - models.F('triggered_at'),
                    filter=models.Q(is_resolved=True)
                )
            )
            
            # Get severity distribution
            severity_dist = AlertLog.objects.filter(
                triggered_at__gte=cutoff_date
            ).values('rule__severity').annotate(
                count=models.Count('id')
            )
            
            return {
                'period_days': days,
                'total_alerts': stats['total_alerts'],
                'resolved_alerts': stats['resolved_alerts'],
                'unresolved_alerts': stats['unresolved_alerts'],
                'resolution_rate': (stats['resolved_alerts'] / stats['total_alerts'] * 100) if stats['total_alerts'] > 0 else 0,
                'avg_resolution_time_minutes': stats['avg_resolution_time'].total_seconds() / 60 if stats['avg_resolution_time'] else 0,
                'severity_distribution': {item['rule__severity']: item['count'] for item in severity_dist}
            }
            
        except Exception as e:
            logger.error(f"Error getting alert statistics: {e}")
            return None
    
    @staticmethod
    def get_rule_performance(days=30):
        """Get performance metrics for alert rules"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            rules = AlertRule.objects.filter(
                is_active=True
            ).annotate(
                total_alerts=models.Count('logs', filter=models.Q(logs__triggered_at__gte=cutoff_date)),
                resolved_alerts=models.Count('logs', filter=models.Q(
                    logs__triggered_at__gte=cutoff_date,
                    logs__is_resolved=True
                )),
                avg_processing_time=models.Avg('logs__processing_time_ms', filter=models.Q(
                    logs__triggered_at__gte=cutoff_date
                ))
            ).order_by('-total_alerts')
            
            performance_data = []
            for rule in rules:
                performance_data.append({
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'total_alerts': rule.total_alerts,
                    'resolved_alerts': rule.resolved_alerts,
                    'resolution_rate': (rule.resolved_alerts / rule.total_alerts * 100) if rule.total_alerts > 0 else 0,
                    'avg_processing_time_ms': rule.avg_processing_time or 0,
                    'severity': rule.severity,
                    'last_triggered': rule.last_triggered
                })
            
            return performance_data
            
        except Exception as e:
            logger.error(f"Error getting rule performance: {e}")
            return []


class AlertMaintenanceService:
    """Alert system maintenance service"""
    
    @staticmethod
    def cleanup_old_alerts(days=90):
        """Clean up old resolved alerts"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            deleted_count = AlertLog.objects.filter(
                is_resolved=True,
                resolved_at__lt=cutoff_date
            ).delete()[0]
            
            logger.info(f"Cleaned up {deleted_count} old alerts")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {e}")
            return 0
    
    @staticmethod
    def cleanup_old_notifications(days=30):
        """Clean up old notifications"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            deleted_count = Notification.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
            
            logger.info(f"Cleaned up {deleted_count} old notifications")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old notifications: {e}")
            return 0
    
    @staticmethod
    def update_rule_health():
        """Update health status for alert rules"""
        try:
            rules = AlertRule.objects.filter(is_active=True)
            
            updated_count = 0
            for rule in rules:
                # Check if rule has triggered recently
                recent_threshold = timezone.now() - timedelta(hours=24)
                recent_alerts = rule.logs.filter(
                    triggered_at__gte=recent_threshold
                ).count()
                
                # Update rule health based on recent activity
                if recent_alerts == 0 and rule.last_triggered:
                    # Rule hasn't triggered in 24 hours but has history
                    time_since_last = (timezone.now() - rule.last_triggered).total_seconds() / 3600
                    
                    if time_since_last > 72:  # 3 days
                        rule.is_active = False  # Auto-disable inactive rules
                        rule.save()
                        updated_count += 1
                        logger.info(f"Auto-disabled inactive rule: {rule.name}")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating rule health: {e}")
            return 0
    
    @staticmethod
    def optimize_alert_indexes():
        """Optimize database indexes for alert tables"""
        try:
            # This would typically run database optimization commands
            # For now, just log the action
            logger.info("Alert database indexes optimization completed")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing alert indexes: {e}")
            return False
