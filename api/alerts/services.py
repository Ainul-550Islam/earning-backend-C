# ============================================
# SERVICES (তোমার models এর business logic)
# ============================================

# alerts/services.py
from django.core.cache import cache
from django.db import GatewayTransaction
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AlertProcessorService:
    """তোমার AlertLog model process করার service"""
    
    @staticmethod
    def process_alert(rule_id, trigger_value, message, details=None):
        """তোমার AlertRule এবং AlertLog models ব্যবহার করে alert process"""
        try:
            with GatewayTransaction.atomic():
                # তোমার AlertRule model থেকে rule fetch
                alert_rule = AlertRule.objects.get(id=rule_id, is_active=True)
                
                # তোমার AlertRule method ব্যবহার করে cooldown check
                if not alert_rule.can_trigger_now():
                    logger.warning(f"Alert rule {rule_id} is in cooldown")
                    return None
                
                # তোমার AlertSuppression class method ব্যবহার করে suppression check
                test_alert = AlertLog(
                    rule=alert_rule,
                    trigger_value=trigger_value,
                    threshold_value=alert_rule.threshold_value,
                    message=message
                )
                
                if AlertSuppression.should_suppress(test_alert):
                    logger.info(f"Alert suppressed for rule {rule_id}")
                    return None
                
                # তোমার AlertLog model create
                alert_log = AlertLog.objects.create(
                    rule=alert_rule,
                    trigger_value=trigger_value,
                    threshold_value=alert_rule.threshold_value,
                    message=message,
                    details=details or {},
                )
                
                # তোমার AlertLog methods ব্যবহার
                alert_log.mark_as_processing()
                
                # তোমার AlertRule method থেকে recipients
                recipients = alert_rule.get_recipients()
                
                # তোমার Notification model create
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
                        message=f"🚨 {alert_rule.name}\n{alert_log.message}",
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
                
                # তোমার AlertLog mark as complete
                alert_log.mark_as_complete()
                
                # তোমার AlertRule update
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
        """তোমার AlertEscalation model ব্যবহার করে alerts escalate"""
        try:
            # তোমার AlertLog unresolved manager ব্যবহার
            unresolved_alerts = AlertLog.unresolved().select_related('rule')
            
            escalated_count = 0
            
            for alert in unresolved_alerts:
                # তোমার AlertRule থেকে escalations fetch
                escalations = AlertEscalation.objects.filter(
                    rule=alert.rule,
                    is_active=True,
                    auto_escalate=True
                ).order_by('level')
                
                for escalation in escalations:
                    # তোমার AlertEscalation method ব্যবহার
                    if escalation.should_escalate(alert):
                        if escalation.escalate_alert(alert):
                            escalated_count += 1
                            logger.info(f"Alert {alert.id} escalated to level {escalation.level}")
            
            return escalated_count
            
        except Exception as e:
            logger.error(f"Error escalating alerts: {e}")
            return 0


class NotificationService:
    """তোমার Notification model process করার service"""
    
    @staticmethod
    def send_pending_notifications():
        """তোমার Notification model থেকে pending notifications send"""
        try:
            pending_notifications = Notification.objects.filter(
                status='pending'
            ).select_related('alert_log', 'alert_log__rule')[:50]
            
            sent_count = 0
            failed_count = 0
            
            for notification in pending_notifications:
                try:
                    # তোমার Notification method ব্যবহার করে retry check
                    if notification.retry_count > 0 and notification.last_retry_at:
                        retry_delay = notification.get_retry_delay()
                        time_since_retry = (timezone.now() - notification.last_retry_at).total_seconds()
                        
                        if time_since_retry < retry_delay:
                            continue
                    
                    # তোমার Notification type অনুযায়ী send
                    success = NotificationService._send_notification(notification)
                    
                    if success:
                        # তোমার Notification method ব্যবহার
                        notification.mark_as_sent(
                            message_id=f"msg_{notification.id}",
                            response_time_ms=100  # Example response time
                        )
                        sent_count += 1
                    else:
                        notification.mark_as_failed("Failed to send")
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error sending notification {notification.id}: {e}")
                    notification.mark_as_failed(str(e))
                    failed_count += 1
            
            return {
                'sent': sent_count,
                'failed': failed_count,
                'total': len(pending_notifications)
            }
            
        except Exception as e:
            logger.error(f"Error in send_pending_notifications: {e}")
            return {'sent': 0, 'failed': 0, 'total': 0}
    
    @staticmethod
    def _send_notification(notification):
        """তোমার Notification model অনুযায়ী actual send logic"""
        # This would integrate with actual email/SMS/telegram services
        # For now, simulate sending
        
        import random
        success_rate = 0.95  # 95% success rate for simulation
        
        if random.random() < success_rate:
            return True
        return False
    
    @staticmethod
    def retry_failed_notifications():
        """তোমার Notification model থেকে failed notifications retry"""
        try:
            failed_notifications = Notification.objects.filter(
                status='failed'
            )
            
            retry_count = 0
            
            for notification in failed_notifications:
                # তোমার Notification method ব্যবহার
                if notification.can_retry():
                    notification.status = 'pending'
                    notification.save()
                    retry_count += 1
            
            return retry_count
            
        except Exception as e:
            logger.error(f"Error retrying notifications: {e}")
            return 0


class AnalyticsService:
    """তোমার AlertAnalytics model generate করার service"""
    
    @staticmethod
    def generate_daily_analytics(date=None):
        """তোমার AlertAnalytics model generate"""
        try:
            if date is None:
                date = timezone.now().date()
            
            # তোমার AlertAnalytics class method ব্যবহার
            analytics = AlertAnalytics.generate_for_date(date, force_regenerate=True)
            
            logger.info(f"Generated analytics for {date}")
            return analytics
            
        except Exception as e:
            logger.error(f"Error generating analytics: {e}")
            return None
    
    @staticmethod
    def get_system_metrics():
        """তোমার SystemMetrics model থেকে metrics"""
        try:
            metrics = SystemMetrics.get_latest()
            
            if not metrics:
                # তোমার SystemMetrics model create করি
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


class AlertGroupService:
    """তোমার AlertGroup model manage করার service"""
    
    @staticmethod
    def check_and_send_group_alerts():
        """তোমার AlertGroup model থেকে group alerts send"""
        try:
            active_groups = AlertGroup.objects.filter(
                is_active=True,
                group_notification_enabled=True
            ).prefetch_related('rules')
            
            alerts_sent = 0
            
            for group in active_groups:
                # তোমার AlertGroup method ব্যবহার
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
        """তোমার AlertGroup model cache update"""
        try:
            group = AlertGroup.objects.get(id=group_id)
            # তোমার AlertGroup method ব্যবহার
            group.update_cache()
            return True
        except AlertGroup.DoesNotExist:
            logger.error(f"Group {group_id} not found")
            return False