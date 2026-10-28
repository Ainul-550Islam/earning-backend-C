"""
Backup Notification Service
Comprehensive notification service for backup events and alerts
"""

import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Backup, BackupAlert, BackupNotificationConfig

logger = logging.getLogger(__name__)


class BackupNotificationService:
    """
    Service for sending notifications for backup events
    Supports multiple notification channels and templates
    """
    
    SUPPORTED_CHANNELS = [
        'email',
        'webhook',
        'slack',
        'teams',
        'sms',
        'push'
    ]
    
    def __init__(self, notification_config=None):
        """
        Initialize notification service
        
        Args:
            notification_config: BackupNotificationConfig instance or dict
        """
        self.config = notification_config
        self.channels = self._parse_channels()
    
    def _parse_channels(self):
        """Parse notification channels from config"""
        if not self.config:
            # Use default channels from settings
            return getattr(settings, 'BACKUP_DEFAULT_CHANNELS', ['email'])
        
        if hasattr(self.config, 'channels'):
            if isinstance(self.config.channels, str):
                return self.config.channels.split(',')
            elif isinstance(self.config.channels, list):
                return self.config.channels
        
        return ['email']  # Default to email
    
    def send_backup_notification(self, backup, event_type, message=None, extra_data=None):
        """
        Send notification for backup event
        
        Args:
            backup: Backup model instance
            event_type (str): Type of event (success, failure, warning, etc.)
            message (str): Custom message (optional)
            extra_data (dict): Additional data for notification
            
        Returns:
            dict: Notification results
        """
        try:
            # Prepare notification data
            notification_data = self._prepare_backup_notification_data(
                backup, event_type, message, extra_data
            )
            
            # Send through all configured channels
            results = {}
            for channel in self.channels:
                if channel in self.SUPPORTED_CHANNELS:
                    results[channel] = self._send_to_channel(
                        channel, notification_data
                    )
                else:
                    results[channel] = {
                        'success': False,
                        'error': f'Unsupported channel: {channel}'
                    }
            
            # Log notification
            self._log_notification(notification_data, results)
            
            return {
                'success': all(r.get('success', False) for r in results.values()),
                'results': results,
                'notification_data': notification_data
            }
            
        except Exception as e:
            logger.error(f"Failed to send backup notification: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_alert_notification(self, alert, message=None, extra_data=None):
        """
        Send notification for backup alert
        
        Args:
            alert: BackupAlert model instance
            message (str): Custom message (optional)
            extra_data (dict): Additional data for notification
            
        Returns:
            dict: Notification results
        """
        try:
            # Prepare notification data
            notification_data = self._prepare_alert_notification_data(
                alert, message, extra_data
            )
            
            # Send through all configured channels
            results = {}
            for channel in self.channels:
                if channel in self.SUPPORTED_CHANNELS:
                    results[channel] = self._send_to_channel(
                        channel, notification_data
                    )
                else:
                    results[channel] = {
                        'success': False,
                        'error': f'Unsupported channel: {channel}'
                    }
            
            # Log notification
            self._log_notification(notification_data, results)
            
            return {
                'success': all(r.get('success', False) for r in results.values()),
                'results': results,
                'notification_data': notification_data
            }
            
        except Exception as e:
            logger.error(f"Failed to send alert notification: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_schedule_notification(self, schedule, event_type, message=None, extra_data=None):
        """
        Send notification for backup schedule event
        
        Args:
            schedule: BackupSchedule model instance
            event_type (str): Type of event (created, updated, executed, missed)
            message (str): Custom message (optional)
            extra_data (dict): Additional data for notification
            
        Returns:
            dict: Notification results
        """
        try:
            # Prepare notification data
            notification_data = self._prepare_schedule_notification_data(
                schedule, event_type, message, extra_data
            )
            
            # Send through all configured channels
            results = {}
            for channel in self.channels:
                if channel in self.SUPPORTED_CHANNELS:
                    results[channel] = self._send_to_channel(
                        channel, notification_data
                    )
                else:
                    results[channel] = {
                        'success': False,
                        'error': f'Unsupported channel: {channel}'
                    }
            
            # Log notification
            self._log_notification(notification_data, results)
            
            return {
                'success': all(r.get('success', False) for r in results.values()),
                'results': results,
                'notification_data': notification_data
            }
            
        except Exception as e:
            logger.error(f"Failed to send schedule notification: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _prepare_backup_notification_data(self, backup, event_type, message, extra_data):
        """Prepare notification data for backup events"""
        data = {
            'type': 'backup',
            'event_type': event_type,
            'backup_id': str(backup.backup_id),
            'backup_name': backup.name,
            'backup_type': backup.backup_type,
            'status': backup.status,
            'database_name': backup.database_name,
            'file_size': backup.file_size,
            'created_at': backup.created_at.isoformat(),
            'created_by': str(backup.created_by) if backup.created_by else None,
            'timestamp': timezone.now().isoformat()
        }
        
        # Add event-specific data
        if event_type == 'success':
            data.update({
                'title': f'Backup Successful: {backup.name}',
                'severity': 'info',
                'duration': backup.duration,
                'compression_ratio': self._calculate_compression_ratio(backup)
            })
        elif event_type == 'failure':
            data.update({
                'title': f'Backup Failed: {backup.name}',
                'severity': 'critical',
                'error_message': backup.error_message,
                'failed_at': backup.end_time.isoformat() if backup.end_time else None
            })
        elif event_type == 'warning':
            data.update({
                'title': f'Backup Warning: {backup.name}',
                'severity': 'warning',
                'warning_message': message
            })
        elif event_type == 'started':
            data.update({
                'title': f'Backup Started: {backup.name}',
                'severity': 'info',
                'started_at': backup.start_time.isoformat() if backup.start_time else None
            })
        
        # Add custom message
        if message:
            data['message'] = message
        
        # Add extra data
        if extra_data:
            data.update(extra_data)
        
        return data
    
    def _prepare_alert_notification_data(self, alert, message, extra_data):
        """Prepare notification data for alert events"""
        data = {
            'type': 'alert',
            'alert_type': alert.alert_type,
            'alert_id': str(alert.id),
            'severity': alert.severity,
            'message': alert.message,
            'created_at': alert.created_at.isoformat(),
            'is_resolved': alert.is_resolved,
            'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
            'resolved_by': str(alert.resolved_by) if alert.resolved_by else None,
            'backup_id': str(alert.backup.backup_id) if alert.backup else None,
            'backup_name': alert.backup.name if alert.backup else None,
            'timestamp': timezone.now().isoformat()
        }
        
        # Set title based on alert type
        alert_titles = {
            'failed': 'Backup Failed',
            'size_exceeded': 'Backup Size Exceeded',
            'schedule_missed': 'Backup Schedule Missed',
            'storage_full': 'Storage Full',
            'verification_failed': 'Backup Verification Failed',
            'retention_expired': 'Backup Retention Expired',
            'security': 'Backup Security Alert'
        }
        
        data['title'] = alert_titles.get(alert.alert_type, f'Backup Alert: {alert.alert_type}')
        
        # Add custom message
        if message:
            data['custom_message'] = message
        
        # Add extra data
        if extra_data:
            data.update(extra_data)
        
        return data
    
    def _prepare_schedule_notification_data(self, schedule, event_type, message, extra_data):
        """Prepare notification data for schedule events"""
        data = {
            'type': 'schedule',
            'event_type': event_type,
            'schedule_id': str(schedule.id),
            'schedule_name': schedule.name,
            'backup_type': schedule.backup_type,
            'frequency': schedule.frequency,
            'cron_expression': schedule.cron_expression,
            'is_active': schedule.is_active,
            'next_run': schedule.next_run.isoformat() if schedule.next_run else None,
            'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
            'timestamp': timezone.now().isoformat()
        }
        
        # Set title based on event type
        schedule_titles = {
            'created': 'Backup Schedule Created',
            'updated': 'Backup Schedule Updated',
            'executed': 'Backup Schedule Executed',
            'missed': 'Backup Schedule Missed',
            'paused': 'Backup Schedule Paused',
            'resumed': 'Backup Schedule Resumed'
        }
        
        data['title'] = schedule_titles.get(event_type, f'Backup Schedule: {event_type}')
        
        # Add custom message
        if message:
            data['message'] = message
        
        # Add extra data
        if extra_data:
            data.update(extra_data)
        
        return data
    
    def _send_to_channel(self, channel, notification_data):
        """Send notification to specific channel"""
        if channel == 'email':
            return self._send_email_notification(notification_data)
        elif channel == 'webhook':
            return self._send_webhook_notification(notification_data)
        elif channel == 'slack':
            return self._send_slack_notification(notification_data)
        elif channel == 'teams':
            return self._send_teams_notification(notification_data)
        elif channel == 'sms':
            return self._send_sms_notification(notification_data)
        elif channel == 'push':
            return self._send_push_notification(notification_data)
        else:
            return {
                'success': False,
                'error': f'Unsupported channel: {channel}'
            }
    
    def _send_email_notification(self, notification_data):
        """Send email notification"""
        try:
            # Get email settings
            from_email = getattr(settings, 'BACKUP_EMAIL_FROM', settings.DEFAULT_FROM_EMAIL)
            recipient_emails = self._get_recipient_emails(notification_data)
            
            if not recipient_emails:
                return {
                    'success': False,
                    'error': 'No recipient emails configured'
                }
            
            # Prepare email content
            subject = notification_data.get('title', 'Backup Notification')
            
            # Render email template
            context = {
                'notification': notification_data,
                'site_name': getattr(settings, 'SITE_NAME', 'Backup System'),
                'site_url': getattr(settings, 'SITE_URL', '')
            }
            
            html_content = render_to_string(
                'backup/email/notification.html',
                context
            )
            
            text_content = render_to_string(
                'backup/email/notification.txt',
                context
            )
            
            # Send email
            send_mail(
                subject=subject,
                message=text_content,
                from_email=from_email,
                recipient_list=recipient_emails,
                html_message=html_content,
                fail_silently=False
            )
            
            return {
                'success': True,
                'channel': 'email',
                'recipients': recipient_emails
            }
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_webhook_notification(self, notification_data):
        """Send webhook notification"""
        try:
            import requests
            
            webhook_url = getattr(settings, 'BACKUP_WEBHOOK_URL', None)
            if not webhook_url:
                return {
                    'success': False,
                    'error': 'Webhook URL not configured'
                }
            
            # Prepare webhook payload
            payload = {
                'event': 'backup_notification',
                'timestamp': timezone.now().isoformat(),
                'data': notification_data
            }
            
            # Send webhook
            response = requests.post(
                webhook_url,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': f'BackupService/{getattr(settings, "VERSION", "1.0.0")}'
                },
                timeout=getattr(settings, 'BACKUP_WEBHOOK_TIMEOUT', 30)
            )
            
            response.raise_for_status()
            
            return {
                'success': True,
                'channel': 'webhook',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_slack_notification(self, notification_data):
        """Send Slack notification"""
        try:
            import requests
            
            slack_webhook_url = getattr(settings, 'BACKUP_SLACK_WEBHOOK_URL', None)
            if not slack_webhook_url:
                return {
                    'success': False,
                    'error': 'Slack webhook URL not configured'
                }
            
            # Prepare Slack message
            color = self._get_slack_color(notification_data.get('severity', 'info'))
            
            slack_payload = {
                'text': notification_data.get('title', 'Backup Notification'),
                'attachments': [
                    {
                        'color': color,
                        'fields': [
                            {
                                'title': 'Event Type',
                                'value': notification_data.get('event_type', 'N/A'),
                                'short': True
                            },
                            {
                                'title': 'Message',
                                'value': notification_data.get('message', 'N/A'),
                                'short': False
                            },
                            {
                                'title': 'Timestamp',
                                'value': notification_data.get('timestamp', timezone.now().isoformat()),
                                'short': True
                            }
                        ]
                    }
                ]
            }
            
            # Send to Slack
            response = requests.post(
                slack_webhook_url,
                json=slack_payload,
                timeout=getattr(settings, 'BACKUP_SLACK_TIMEOUT', 30)
            )
            
            return {
                'success': True,
                'channel': 'slack',
                'status_code': response.status_code
            }
            
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_teams_notification(self, notification_data):
        """Send Microsoft Teams notification"""
        try:
            import requests
            
            teams_webhook_url = getattr(settings, 'BACKUP_TEAMS_WEBHOOK_URL', None)
            if not teams_webhook_url:
                return {
                    'success': False,
                    'error': 'Teams webhook URL not configured'
                }
            
            # Prepare Teams message
            color = self._get_teams_color(notification_data.get('severity', 'info'))
            
            teams_payload = {
                '@type': 'MessageCard',
                '@context': 'http://schema.org/extensions',
                'themeColor': color,
                'summary': notification_data.get('title', 'Backup Notification'),
                'sections': [
                    {
                        'activityTitle': notification_data.get('title', 'Backup Notification'),
                        'activitySubtitle': notification_data.get('event_type', 'N/A'),
                        'facts': [
                            {
                                'name': 'Message',
                                'value': notification_data.get('message', 'N/A')
                            },
                            {
                                'name': 'Timestamp',
                                'value': notification_data.get('timestamp', timezone.now().isoformat())
                            }
                        ],
                        'markdown': True
                    }
                ]
            }
            
            # Send to Teams
            response = requests.post(
                teams_webhook_url,
                json=teams_payload,
                headers={'Content-Type': 'application/json'},
                timeout=getattr(settings, 'BACKUP_TEAMS_TIMEOUT', 30)
            )
            
            return {
                'success': True,
                'channel': 'teams',
                'status_code': response.status_code
            }
            
        except Exception as e:
            logger.error(f"Failed to send Teams notification: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_sms_notification(self, notification_data):
        """Send SMS notification (placeholder implementation)"""
        # This would integrate with SMS service like Twilio, AWS SNS, etc.
        logger.warning("SMS notifications not implemented")
        return {
            'success': False,
            'error': 'SMS notifications not implemented'
        }
    
    def _send_push_notification(self, notification_data):
        """Send push notification (placeholder implementation)"""
        # This would integrate with push notification service like Firebase, APNS, etc.
        logger.warning("Push notifications not implemented")
        return {
            'success': False,
            'error': 'Push notifications not implemented'
        }
    
    def _get_recipient_emails(self, notification_data):
        """Get recipient emails based on notification data"""
        recipients = []
        
        # Get recipients from settings
        default_recipients = getattr(settings, 'BACKUP_NOTIFICATION_RECIPIENTS', [])
        recipients.extend(default_recipients)
        
        # Add backup creator if available
        if notification_data.get('created_by'):
            # This would need User model import and email field access
            pass
        
        # Add recipients based on severity
        severity = notification_data.get('severity', 'info')
        if severity in ['critical', 'high']:
            critical_recipients = getattr(settings, 'BACKUP_CRITICAL_RECIPIENTS', [])
            recipients.extend(critical_recipients)
        
        # Remove duplicates
        return list(set(recipients))
    
    def _get_slack_color(self, severity):
        """Get Slack color based on severity"""
        colors = {
            'critical': '#ff0000',  # Red
            'high': '#ff6600',     # Orange
            'medium': '#ffaa00',   # Yellow
            'low': '#36a64f',      # Blue
            'info': '#36a64f'       # Blue
        }
        
        return colors.get(severity, '#36a64f')
    
    def _get_teams_color(self, severity):
        """Get Teams color based on severity"""
        colors = {
            'critical': '#FF0000',  # Red
            'high': '#FF6600',     # Orange
            'medium': '#FFAA00',   # Yellow
            'low': '#0078D7',      # Blue
            'info': '#0078D7'       # Blue
        }
        
        return colors.get(severity, '#0078D7')
    
    def _calculate_compression_ratio(self, backup):
        """Calculate compression ratio for backup"""
        if not backup.compression_enabled or not backup.original_size or not backup.file_size:
            return None
        
        ratio = backup.file_size / backup.original_size if backup.original_size > 0 else 0
        return f"{ratio:.2%}"
    
    def _log_notification(self, notification_data, results):
        """Log notification for audit trail"""
        try:
            # Create notification log entry
            from .models import BackupLog
            
            # Determine log level based on severity
            severity = notification_data.get('severity', 'info')
            log_level = {
                'critical': 'critical',
                'high': 'error',
                'medium': 'warning',
                'low': 'info',
                'info': 'info'
            }.get(severity, 'info')
            
            # Create log entry
            BackupLog.objects.create(
                category='notification',
                action='send',
                level=log_level,
                message=f"Sent {notification_data.get('type', 'unknown')} notification",
                details={
                    'notification_data': notification_data,
                    'results': results,
                    'channels': self.channels
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to log notification: {str(e)}")
    
    def test_notification_channels(self):
        """
        Test all configured notification channels
        
        Returns:
            dict: Test results for each channel
        """
        results = {}
        
        for channel in self.channels:
            if channel in self.SUPPORTED_CHANNELS:
                # Send test notification
                test_data = {
                    'type': 'test',
                    'event_type': 'test',
                    'title': f'Backup Notification Test - {channel.title()}',
                    'message': 'This is a test notification from the backup system.',
                    'severity': 'info',
                    'timestamp': timezone.now().isoformat()
                }
                
                results[channel] = self._send_to_channel(channel, test_data)
            else:
                results[channel] = {
                    'success': False,
                    'error': f'Unsupported channel: {channel}'
                }
        
        return {
            'success': all(r.get('success', False) for r in results.values()),
            'results': results,
            'channels_tested': self.channels
        }
    
    def get_notification_history(self, backup=None, event_type=None, limit=50):
        """
        Get notification history
        
        Args:
            backup: Filter by specific backup
            event_type: Filter by specific event type
            limit: Maximum number of records to return
            
        Returns:
            list: Notification history
        """
        try:
            from .models import BackupLog
            
            # Query notification logs
            queryset = BackupLog.objects.filter(category='notification')
            
            if backup:
                # Filter by backup (would need backup_id in details)
                pass
            
            if event_type:
                # Filter by event type
                queryset = queryset.filter(details__event_type=event_type)
            
            # Order by timestamp and limit
            notifications = queryset.order_by('-timestamp')[:limit]
            
            return [
                {
                    'timestamp': notification.timestamp.isoformat(),
                    'level': notification.level,
                    'message': notification.message,
                    'details': notification.details,
                    'event_type': notification.details.get('event_type'),
                    'channel': notification.details.get('channel'),
                    'success': notification.details.get('results', {}).get('success', False)
                }
                for notification in notifications
            ]
            
        except Exception as e:
            logger.error(f"Failed to get notification history: {str(e)}")
            return []
