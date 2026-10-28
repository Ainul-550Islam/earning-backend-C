"""
Email Alert Service — Enhanced HTML email with rich formatting, attachments, and error handling
"""
import logging
from ._shared import get_effective_alert_log
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.conf import settings
from django.core.cache import cache
import time

logger = logging.getLogger(__name__)

SEVERITY_COLORS = {
    'low': '#28a745',
    'medium': '#ffc107',
    'high': '#fd7e14',
    'critical': '#dc3545',
}

SEVERITY_ICONS = {
    'low': '🟢',
    'medium': '🟡',
    'high': '🟠',
    'critical': '🔴',
}


class EmailAlertService:
    """Enhanced email alert service with rich formatting, attachments, and retry logic"""

    def __init__(self):
        self.rate_limit_cache_key = "email_rate_limit"
        self.max_retries = 3
        self.timeout = 30

    def _check_rate_limit(self, recipient: str) -> bool:
        """Check if we're rate limited for this recipient"""
        cache_key = f"{self.rate_limit_cache_key}_{hash(recipient)}"
        rate_limit_until = cache.get(cache_key)
        
        if rate_limit_until and time.time() < rate_limit_until:
            logger.warning(f"Email rate limited for {recipient} until {rate_limit_until}")
            return False
        
        return True

    def _handle_rate_limit(self, recipient: str, retry_after: int):
        """Handle rate limiting by setting cache"""
        cache_key = f"{self.rate_limit_cache_key}_{hash(recipient)}"
        cache.set(cache_key, time.time() + retry_after, timeout=retry_after + 10)

    def _validate_email_address(self, email: str) -> bool:
        """Validate email address format"""
        if not email:
            return False
        
        # Basic email validation
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _build_html_template(self, context: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Build rich HTML email template"""
        severity = context['severity']
        color = SEVERITY_COLORS.get(severity, '#6c757d')
        icon = SEVERITY_ICONS.get(severity, '⚠️')
        
        # Create HTML template
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Alert: {context['rule_name']}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .alert-container {{
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .alert-header {{
                    background: {color};
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .alert-header h1 {{
                    margin: 0;
                    font-size: 24px;
                    font-weight: 600;
                }}
                .alert-body {{
                    padding: 30px;
                }}
                .severity-badge {{
                    display: inline-block;
                    background: {color};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    text-transform: uppercase;
                    margin-bottom: 20px;
                }}
                .alert-details {{
                    background: #f8f9fa;
                    border-radius: 6px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .detail-row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }}
                .detail-label {{
                    font-weight: 600;
                    color: #666;
                }}
                .detail-value {{
                    font-family: monospace;
                    background: #e9ecef;
                    padding: 2px 6px;
                    border-radius: 3px;
                }}
                .alert-message {{
                    background: #fff3cd;
                    border-left: 4px solid {color};
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 0 6px 6px 0;
                }}
                .alert-footer {{
                    background: #f8f9fa;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                    border-top: 1px solid #dee2e6;
                }}
                @media (max-width: 600px) {{
                    .detail-row {{
                        flex-direction: column;
                    }}
                    .detail-value {{
                        margin-top: 5px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="alert-container">
                <div class="alert-header">
                    <h1>{icon} {context['rule_name']}</h1>
                </div>
                <div class="alert-body">
                    <div class="severity-badge">
                        {severity.upper()}
                    </div>
                    
                    <div class="alert-message">
                        <strong>Message:</strong><br>
                        {context['message']}
                    </div>
                    
                    <div class="alert-details">
                        <div class="detail-row">
                            <span class="detail-label">Triggered Value:</span>
                            <span class="detail-value">{context['trigger_value']}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Threshold:</span>
                            <span class="detail-value">{context['threshold_value']}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Triggered At:</span>
                            <span class="detail-value">{context['triggered_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}</span>
                        </div>
                    </div>
                </div>
                <div class="alert-footer">
                    <p>This alert was generated by the Alert System</p>
                    <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template

    def _build_text_template(self, context: Dict[str, Any]) -> str:
        """Build plain text email template"""
        severity = context['severity']
        icon = SEVERITY_ICONS.get(severity, '⚠️')
        
        text_template = f"""
{icon} {context['rule_name']}
{'=' * 50}

SEVERITY: {severity.upper()}

MESSAGE:
{context['message']}

DETAILS:
- Triggered Value: {context['trigger_value']}
- Threshold: {context['threshold_value']}
- Triggered At: {context['triggered_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}

{'=' * 50}
This alert was generated by the Alert System
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
        """.strip()
        
        return text_template

    def _build_context(self, notification, channel) -> Dict[str, Any]:
        """Build context for email templates"""
        alert_log = get_effective_alert_log(notification)
        
        context = {
            'rule_name': alert_log.rule.name,
            'severity': alert_log.rule.severity,
            'message': notification.message,
            'trigger_value': alert_log.trigger_value,
            'threshold_value': alert_log.threshold_value,
            'triggered_at': alert_log.triggered_at,
        }
        
        # Add optional fields
        if hasattr(alert_log, 'source') and alert_log.source:
            context['source'] = alert_log.source
        
        if hasattr(alert_log, 'tags') and alert_log.tags:
            context['tags'] = alert_log.tags
        
        if hasattr(alert_log, 'context') and alert_log.context:
            context['context'] = alert_log.context
        
        return context

    def _get_recipients(self, notification, config) -> List[str]:
        """Get list of email recipients"""
        recipients = []
        
        # Primary recipient
        if notification.recipient:
            if isinstance(notification.recipient, list):
                recipients.extend([r for r in notification.recipient if self._validate_email_address(r)])
            elif self._validate_email_address(notification.recipient):
                recipients.append(notification.recipient)
        
        # Additional recipients from config
        additional_recipients = config.get('additional_recipients', [])
        if additional_recipients:
            if isinstance(additional_recipients, list):
                recipients.extend([r for r in additional_recipients if self._validate_email_address(r)])
            elif isinstance(additional_recipients, str):
                recipients.extend([r for r in additional_recipients.split(',') if self._validate_email_address(r.strip())])
        
        # CC recipients
        cc_recipients = config.get('cc_recipients', [])
        if cc_recipients:
            if isinstance(cc_recipients, list):
                cc_list = [r for r in cc_recipients if self._validate_email_address(r)]
            else:
                cc_list = [r for r in cc_recipients.split(',') if self._validate_email_address(r.strip())]
        else:
            cc_list = []
        
        return recipients, cc_list

    def send(self, notification, channel, use_custom_template: bool = False) -> bool:
        """
        Enhanced send method with retry logic and error handling
        
        Args:
            notification: Notification object
            channel: Channel object
            use_custom_template: Whether to use custom HTML template
        
        Returns:
            bool: Success status
        """
        config = channel.config
        
        # Get recipients
        recipients, cc_list = self._get_recipients(notification, config)
        
        if not recipients:
            logger.error("No valid email recipients found")
            return False

        # Check rate limiting for each recipient
        for recipient in recipients:
            if not self._check_rate_limit(recipient):
                logger.warning(f"Rate limited for recipient: {recipient}")
                return False

        # Build context
        context = self._build_context(notification, channel)
        
        # Generate subject
        severity = context['severity']
        icon = SEVERITY_ICONS.get(severity, '⚠️')
        subject = config.get('subject_template', f"{icon} [{severity.upper()}] {context['rule_name']}")
        if notification.subject:
            subject = notification.subject

        # Build email body
        if use_custom_template or config.get('use_custom_template', False):
            try:
                html_body = render_to_string('alerts/alert_notification.html', context)
            except Exception as e:
                logger.warning(f"Custom template failed, using default HTML: {e}")
                html_body = self._build_html_template(context, config)
        else:
            html_body = self._build_html_template(context, config)
        
        text_body = self._build_text_template(context)

        # Get email configuration
        from_email = config.get('from_email', settings.DEFAULT_FROM_EMAIL)
        reply_to = config.get('reply_to', from_email)
        if isinstance(reply_to, str):
            reply_to = [reply_to]
        
        # Configure email backend
        email_config = {
            'host': config.get('smtp_host', settings.EMAIL_HOST),
            'port': config.get('smtp_port', settings.EMAIL_PORT),
            'username': config.get('smtp_username', settings.EMAIL_HOST_USER),
            'password': config.get('smtp_password', settings.EMAIL_HOST_PASSWORD),
            'use_tls': config.get('use_tls', settings.EMAIL_USE_TLS),
            'use_ssl': config.get('use_ssl', settings.EMAIL_USE_SSL),
            'timeout': self.timeout
        }

        try:
            # Create email connection
            connection = get_connection(**email_config)
            
            # Create email message
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=formataddr((config.get('from_name', 'Alert System'), from_email)),
                to=recipients,
                cc=cc_list,
                reply_to=reply_to,
                connection=connection
            )
            
            # Attach HTML version
            msg.attach_alternative(html_body, "text/html")
            
            # Add attachments if configured
            attachments = config.get('attachments', [])
            if attachments:
                for attachment in attachments:
                    if isinstance(attachment, dict):
                        file_path = attachment.get('path')
                        file_name = attachment.get('name', file_path.split('/')[-1] if file_path else 'attachment')
                        
                        if file_path:
                            try:
                                with open(file_path, 'rb') as f:
                                    part = MIMEBase('application', 'octet-stream')
                                    part.set_payload(f.read())
                                encoders.encode_base64(part)
                                part.add_header(
                                    'Content-Disposition',
                                    f'attachment; filename="{file_name}"'
                                )
                                msg.attach(part)
                            except Exception as e:
                                logger.warning(f"Failed to attach file {file_path}: {e}")
            
            # Send email
            msg.send()
            
            # Record success
            channel.record_success()
            logger.info(f"Email sent successfully to {len(recipients)} recipients")
            
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error("Email SMTP authentication failed")
            channel.record_failure()
            return False
            
        except smtplib.SMTPConnectError:
            logger.error("Email SMTP connection failed")
            channel.record_failure()
            return False
            
        except smtplib.SMTPRecipientsRefused:
            logger.error("Email recipients refused by SMTP server")
            channel.record_failure()
            return False
            
        except smtplib.SMTPServerDisconnected:
            logger.error("Email SMTP server disconnected")
            channel.record_failure()
            return False
            
        except Exception as e:
            logger.error(f"EmailAlertService unexpected error: {e}")
            channel.record_failure()
            return False

    def send_test_message(self, recipient: str, config: Dict[str, Any] = None) -> bool:
        """
        Send a test message to verify email connectivity
        
        Args:
            recipient: Email recipient
            config: Optional channel configuration
        
        Returns:
            bool: Success status
        """
        if not recipient or not self._validate_email_address(recipient):
            logger.error("Valid email recipient required for test message")
            return False

        # Default test configuration
        test_config = config or {}
        
        # Create test context
        test_context = {
            'rule_name': 'Test Alert',
            'severity': 'low',
            'message': 'This is a test message to verify email connectivity.',
            'trigger_value': 'N/A',
            'threshold_value': 'N/A',
            'triggered_at': datetime.now(timezone.utc),
        }
        
        # Build test email
        html_body = self._build_html_template(test_context, test_config)
        text_body = self._build_text_template(test_context)
        
        subject = "🧪 Test Message from Alert System"
        from_email = test_config.get('from_email', settings.DEFAULT_FROM_FROM_EMAIL)
        
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[recipient]
            )
            msg.attach_alternative(html_body, "text/html")
            
            msg.send()
            logger.info(f"Email test message sent successfully to {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Email test message error: {e}")
            return False

    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate email configuration
        
        Args:
            config: Channel configuration
        
        Returns:
            Dict with validation results
        """
        errors = []
        warnings = []
        
        # Validate SMTP settings
        if not config.get('smtp_host') and not settings.EMAIL_HOST:
            errors.append("SMTP host is required")
        
        if not config.get('smtp_port') and not settings.EMAIL_PORT:
            errors.append("SMTP port is required")
        
        # Validate from email
        from_email = config.get('from_email', settings.DEFAULT_FROM_EMAIL)
        if not from_email or not self._validate_email_address(from_email):
            errors.append("Valid from email is required")
        
        # Check for potential issues
        if config.get('use_tls') and config.get('use_ssl'):
            warnings.append("Both TLS and SSL are enabled - TLS will be used")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def get_email_stats(self, recipient: str = None) -> Dict[str, Any]:
        """
        Get email statistics
        
        Args:
            recipient: Optional recipient to filter stats
        
        Returns:
            Dict with email statistics
        """
        # This is a placeholder for future implementation
        # Could integrate with email service APIs or database tracking
        return {
            'total_sent': 0,
            'total_failed': 0,
            'success_rate': 0.0,
            'last_sent': None,
            'recipient': recipient
        }
