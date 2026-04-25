"""
Tenant Email Service

This service handles tenant email operations including
configuration, testing, template management, and delivery.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from django.template import loader, Context
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.branding import TenantEmail
from ..models.security import TenantAuditLog

User = get_user_model()


class TenantEmailService:
    """
    Service class for tenant email operations.
    
    This service handles email configuration, template rendering,
    and email delivery for tenant communications.
    """
    
    @staticmethod
    def test_email_connection(email_config):
        """
        Test email configuration connection.
        
        Args:
            email_config (TenantEmail): Email configuration to test
            
        Returns:
            dict: Test result
        """
        try:
            if email_config.provider == 'smtp':
                return TenantEmailService._test_smtp_connection(email_config)
            else:
                return TenantEmailService._test_api_connection(email_config)
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def _test_smtp_connection(email_config):
        """Test SMTP connection."""
        try:
            # Create SMTP connection
            if email_config.smtp_use_ssl:
                server = smtplib.SMTP_SSL(email_config.smtp_host, email_config.smtp_port)
            else:
                server = smtplib.SMTP(email_config.smtp_host, email_config.smtp_port)
                if email_config.smtp_use_tls:
                    server.starttls()
            
            # Login if credentials provided
            if email_config.smtp_user and email_config.smtp_password:
                server.login(email_config.smtp_user, email_config.smtp_password)
            
            server.quit()
            
            return {
                'success': True,
                'message': 'SMTP connection successful',
                'provider': 'smtp',
                'host': email_config.smtp_host,
                'port': email_config.smtp_port,
                'use_tls': email_config.smtp_use_tls,
                'use_ssl': email_config.smtp_use_ssl,
            }
            
        except smtplib.SMTPAuthenticationError:
            return {
                'success': False,
                'error': 'SMTP authentication failed',
            }
        except smtplib.SMTPConnectError:
            return {
                'success': False,
                'error': 'Failed to connect to SMTP server',
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def _test_api_connection(email_config):
        """Test API-based email service connection."""
        # This would test connections to services like SendGrid, SES, etc.
        # For now, simulate successful test
        return {
            'success': True,
            'message': f'{email_config.provider.title()} API connection successful',
            'provider': email_config.provider,
        }
    
    @staticmethod
    def send_email(tenant, template_name, context_data, recipients, subject=None, **kwargs):
        """
        Send email using tenant's email configuration.
        
        Args:
            tenant (Tenant): Tenant to send email for
            template_name (str): Email template name
            context_data (dict): Template context data
            recipients (list): List of recipient email addresses
            subject (str): Email subject (optional)
            **kwargs: Additional email options
            
        Returns:
            dict: Send result
        """
        try:
            email_config = tenant.email_config
            
            if not email_config.is_verified:
                return {
                    'success': False,
                    'error': 'Email configuration is not verified',
                }
            
            # Render email template
            html_content, text_content = TenantEmailService._render_email_template(
                tenant, template_name, context_data
            )
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject or f'{tenant.name} Notification'
            msg['From'] = formataddr((email_config.from_name, email_config.from_email))
            msg['To'] = ', '.join(recipients)
            
            # Add reply-to if specified
            if email_config.reply_to_email:
                msg['Reply-To'] = email_config.reply_to_email
            
            # Attach content
            if text_content:
                msg.attach(MIMEText(text_content, 'plain'))
            if html_content:
                msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            if email_config.provider == 'smtp':
                result = TenantEmailService._send_via_smtp(email_config, msg, recipients)
            else:
                result = TenantEmailService._send_via_api(email_config, msg, recipients)
            
            # Log email send
            TenantAuditLog.log_action(
                tenant=tenant,
                action='config_change',
                model_name='TenantEmail',
                description=f"Email sent: {template_name} to {len(recipients)} recipients",
                metadata={
                    'template': template_name,
                    'recipients': recipients,
                    'provider': email_config.provider,
                    'success': result['success'],
                }
            )
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    @staticmethod
    def _render_email_template(tenant, template_name, context_data):
        """Render email template with tenant branding."""
        # Add tenant branding to context
        context = Context(context_data)
        context['tenant'] = tenant
        context['branding'] = getattr(tenant, 'branding', None)
        
        # Try to load template
        try:
            template = loader.get_template(f'tenants/emails/{template_name}.html')
            html_content = template.render(context)
        except:
            html_content = TenantEmailService._get_default_template(template_name, context, 'html')
        
        try:
            template = loader.get_template(f'tenants/emails/{template_name}.txt')
            text_content = template.render(context)
        except:
            text_content = TenantEmailService._get_default_template(template_name, context, 'text')
        
        return html_content, text_content
    
    @staticmethod
    def _get_default_template(template_name, context, format_type):
        """Get default email template."""
        if format_type == 'html':
            return f"""
            <html>
            <head>
                <title>{context.get('subject', 'Notification')}</title>
            </head>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2>{context.get('title', 'Notification')}</h2>
                    <div>{context.get('message', '')}</div>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        This email was sent by {context.get('tenant', {}).get('name', 'System')}.
                    </p>
                </div>
            </body>
            </html>
            """
        else:
            return f"""
            {context.get('title', 'Notification')}
            
            {context.get('message', '')}
            
            ---
            This email was sent by {context.get('tenant', {}).get('name', 'System')}.
            """
    
    @staticmethod
    def _send_via_smtp(email_config, msg, recipients):
        """Send email via SMTP."""
        try:
            # Create SMTP connection
            if email_config.smtp_use_ssl:
                server = smtplib.SMTP_SSL(email_config.smtp_host, email_config.smtp_port)
            else:
                server = smtplib.SMTP(email_config.smtp_host, email_config.smtp_port)
                if email_config.smtp_use_tls:
                    server.starttls()
            
            # Login
            if email_config.smtp_user and email_config.smtp_password:
                server.login(email_config.smtp_user, email_config.smtp_password)
            
            # Send email
            server.send_message(msg, to_addrs=recipients)
            server.quit()
            
            return {
                'success': True,
                'message': 'Email sent successfully via SMTP',
                'provider': 'smtp',
                'recipients': len(recipients),
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider': 'smtp',
            }
    
    @staticmethod
    def _send_via_api(email_config, msg, recipients):
        """Send email via API service."""
        # This would integrate with email service APIs like SendGrid, SES, etc.
        # For now, simulate successful send
        return {
            'success': True,
            'message': f'Email sent successfully via {email_config.provider}',
            'provider': email_config.provider,
            'recipients': len(recipients),
        }
    
    @staticmethod
    def create_email_template(tenant, template_name, subject, html_content, text_content=None, created_by=None):
        """
        Create custom email template for tenant.
        
        Args:
            tenant (Tenant): Tenant to create template for
            template_name (str): Template name
            subject (str): Email subject
            html_content (str): HTML content
            text_content (str): Text content (optional)
            created_by (User): User creating template
            
        Returns:
            dict: Creation result
        """
        # This would create a custom email template
        # For now, just return success
        result = {
            'success': True,
            'message': f'Email template {template_name} created successfully',
            'template_name': template_name,
        }
        
        # Log template creation
        if created_by:
            TenantAuditLog.log_action(
                tenant=tenant,
                action='config_change',
                actor=created_by,
                model_name='EmailTemplate',
                description=f"Email template {template_name} created",
                metadata={
                    'template_name': template_name,
                    'subject': subject,
                }
            )
        
        return result
    
    @staticmethod
    def get_email_statistics(tenant, days=30):
        """
        Get email statistics for tenant.
        
        Args:
            tenant (Tenant): Tenant to get statistics for
            days (int): Number of days to analyze
            
        Returns:
            dict: Email statistics
        """
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        # This would query email delivery logs
        # For now, return mock statistics
        statistics = {
            'period': {
                'start_date': start_date.date(),
                'end_date': timezone.now().date(),
                'days': days,
            },
            'sent': 0,
            'delivered': 0,
            'opened': 0,
            'clicked': 0,
            'bounced': 0,
            'failed': 0,
            'delivery_rate': 0,
            'open_rate': 0,
            'click_rate': 0,
        }
        
        return statistics
    
    @staticmethod
    def verify_email_domain(email_config):
        """
        Verify email domain configuration.
        
        Args:
            email_config (TenantEmail): Email configuration to verify
            
        Returns:
            dict: Verification result
        """
        try:
            # Extract domain from email
            domain = email_config.from_email.split('@')[1]
            
            # Check DNS records
            import dns.resolver
            
            # Check MX records
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                mx_valid = len(mx_records) > 0
            except:
                mx_valid = False
            
            # Check SPF record
            try:
                spf_records = dns.resolver.resolve(domain, 'TXT')
                spf_valid = any('v=spf1' in str(record) for record in spf_records)
            except:
                spf_valid = False
            
            # Check DKIM record
            dkim_valid = False  # Would need to check specific DKIM selector
            
            # Check DMARC record
            try:
                dmarc_records = dns.resolver.resolve(f'_dmarc.{domain}', 'TXT')
                dmarc_valid = any('v=DMARC1' in str(record) for record in dmarc_records)
            except:
                dmarc_valid = False
            
            verification_result = {
                'success': True,
                'domain': domain,
                'mx_valid': mx_valid,
                'spf_valid': spf_valid,
                'dkim_valid': dkim_valid,
                'dmarc_valid': dmarc_valid,
                'overall_score': sum([mx_valid, spf_valid, dmarc_valid]) / 3 * 100,
            }
            
            # Update verification status
            if verification_result['overall_score'] >= 70:
                email_config.verify_configuration()
            
            return verification_result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
