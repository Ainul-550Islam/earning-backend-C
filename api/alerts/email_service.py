"""
Email Service Integration for alerts app - Advanced email management
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
import asyncio
import logging
import json
import uuid
import time
from enum import Enum

logger = logging.getLogger(__name__)


class EmailStatus(Enum):
    """Email status enumeration"""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
    OPENED = "opened"
    CLICKED = "clicked"


class EmailTemplate:
    """Email template management"""
    
    def __init__(self, name: str, subject_template: str, html_template: str, 
                 text_template: str = None, metadata: Dict[str, Any] = None):
        self.name = name
        self.subject_template = subject_template
        self.html_template = html_template
        self.text_template = text_template
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        
    def render(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Render email template with context"""
        try:
            subject = render_to_string(self.subject_template, context).strip()
            html_content = render_to_string(self.html_template, context)
            text_content = render_to_string(self.text_template, context) if self.text_template else None
            
            return {
                'subject': subject,
                'html_content': html_content,
                'text_content': text_content
            }
        except Exception as e:
            logger.error(f"Error rendering template {self.name}: {e}")
            return {
                'subject': 'Template Error',
                'html_content': 'Error rendering template',
                'text_content': 'Error rendering template'
            }


class EmailMessage:
    """Represents an email message"""
    
    def __init__(self, to_email: str, subject: str, html_content: str,
                 from_email: str = None, cc: List[str] = None, bcc: List[str] = None,
                 reply_to: str = None, attachments: List[Dict[str, Any]] = None,
                 metadata: Dict[str, Any] = None):
        self.id = str(uuid.uuid4())
        self.to_email = to_email
        self.subject = subject
        self.html_content = html_content
        self.from_email = from_email or settings.DEFAULT_FROM_EMAIL
        self.cc = cc or []
        self.bcc = bcc or []
        self.reply_to = reply_to
        self.attachments = attachments or []
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        self.status = EmailStatus.PENDING
        self.sent_at = None
        self.error_message = None
        self.attempts = 0
        self.opened_at = None
        self.clicked_at = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'to_email': self.to_email,
            'subject': self.subject,
            'from_email': self.from_email,
            'cc': self.cc,
            'bcc': self.bcc,
            'reply_to': self.reply_to,
            'attachments': self.attachments,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'status': self.status.value,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error_message': self.error_message,
            'attempts': self.attempts,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None
        }


class EmailProvider(ABC):
    """Abstract base class for email providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__
        self.enabled = config.get('enabled', True)
        self.max_retries = config.get('max_retries', 3)
        self.timeout = config.get('timeout', 30)
        
    @abstractmethod
    async def send_email(self, email: EmailMessage) -> Dict[str, Any]:
        """Send email through this provider"""
        pass
    
    @abstractmethod
    def validate_config(self) -> Dict[str, Any]:
        """Validate provider configuration"""
        pass
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'config': self.config
        }


class SMTPEmailProvider(EmailProvider):
    """SMTP email provider"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_host = config.get('smtp_host', 'localhost')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.use_tls = config.get('use_tls', True)
        self.use_ssl = config.get('use_ssl', False)
        
    async def send_email(self, email: EmailMessage) -> Dict[str, Any]:
        """Send email using SMTP"""
        try:
            # Create email message
            msg = EmailMultiAlternatives(
                subject=email.subject,
                body=self._extract_text_from_html(email.html_content),
                from_email=email.from_email,
                to=[email.to_email],
                cc=email.cc,
                bcc=email.bcc,
                reply_to=[email.reply_to] if email.reply_to else None
            )
            
            # Attach HTML content
            msg.attach_alternative(email.html_content, "text/html")
            
            # Add attachments
            for attachment in email.attachments:
                msg.attach(
                    attachment['filename'],
                    attachment['content'],
                    attachment['mimetype']
                )
            
            # Send email
            connection = get_connection(
                host=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                use_tls=self.use_tls,
                use_ssl=self.use_ssl,
                timeout=self.timeout
            )
            
            msg.send()
            
            return {
                'success': True,
                'provider': self.name,
                'message_id': email.id,
                'sent_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"SMTP send error: {e}")
            return {
                'success': False,
                'provider': self.name,
                'error': 'Operation failed',
                'message_id': email.id
            }
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract plain text from HTML content"""
        try:
            import re
            # Simple HTML to text conversion
            text = re.sub(r'<[^>]+>', '', html_content)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except:
            return "Email content"
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate SMTP configuration"""
        errors = []
        
        if not self.smtp_host:
            errors.append("SMTP host is required")
        
        if not self.smtp_username:
            errors.append("SMTP username is required")
        
        if not self.smtp_password:
            errors.append("SMTP password is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class SendGridEmailProvider(EmailProvider):
    """SendGrid email provider"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.from_email = config.get('from_email', settings.DEFAULT_FROM_EMAIL)
        
    async def send_email(self, email: EmailMessage) -> Dict[str, Any]:
        """Send email using SendGrid"""
        try:
            import requests
            
            # Prepare SendGrid payload
            payload = {
                'personalizations': [{
                    'to': [{'email': email.to_email}],
                    'subject': email.subject
                }],
                'from': {'email': email.from_email},
                'content': [{
                    'type': 'text/html',
                    'value': email.html_content
                }]
            }
            
            # Add CC and BCC
            if email.cc:
                payload['personalizations'][0]['cc'] = [{'email': addr} for addr in email.cc]
            
            if email.bcc:
                payload['personalizations'][0]['bcc'] = [{'email': addr} for addr in email.bcc]
            
            # Add reply to
            if email.reply_to:
                payload['reply_to'] = {'email': email.reply_to}
            
            # Add attachments
            if email.attachments:
                payload['attachments'] = []
                for attachment in email.attachments:
                    import base64
                    content = base64.b64encode(attachment['content']).decode()
                    payload['attachments'].append({
                        'content': content,
                        'filename': attachment['filename'],
                        'type': attachment['mimetype']
                    })
            
            # Send to SendGrid
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                'https://api.sendgrid.com/v3/mail/send',
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code in [200, 202]:
                return {
                    'success': True,
                    'provider': self.name,
                    'message_id': email.id,
                    'sendgrid_id': response.headers.get('X-Message-Id'),
                    'sent_at': timezone.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'provider': self.name,
                    'error': f"SendGrid API error: {response.status_code} - {response.text}",
                    'message_id': email.id
                }
                
        except Exception as e:
            logger.error(f"SendGrid send error: {e}")
            return {
                'success': False,
                'provider': self.name,
                'error': 'Operation failed',
                'message_id': email.id
            }
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate SendGrid configuration"""
        errors = []
        
        if not self.api_key:
            errors.append("SendGrid API key is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class MailgunEmailProvider(EmailProvider):
    """Mailgun email provider"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.domain = config.get('domain')
        self.from_email = config.get('from_email', settings.DEFAULT_FROM_EMAIL)
        
    async def send_email(self, email: EmailMessage) -> Dict[str, Any]:
        """Send email using Mailgun"""
        try:
            import requests
            
            # Prepare Mailgun payload
            data = {
                'from': email.from_email,
                'to': email.to_email,
                'subject': email.subject,
                'html': email.html_content,
                'text': self._extract_text_from_html(email.html_content)
            }
            
            # Add CC and BCC
            if email.cc:
                data['cc'] = ', '.join(email.cc)
            
            if email.bcc:
                data['bcc'] = ', '.join(email.bcc)
            
            # Add reply to
            if email.reply_to:
                data['h:Reply-To'] = email.reply_to
            
            # Add attachments
            files = []
            for attachment in email.attachments:
                files.append((
                    ('attachment', (attachment['filename'], attachment['content'], attachment['mimetype']))
                ))
            
            # Send to Mailgun
            auth = ('api', self.api_key)
            url = f"https://api.mailgun.net/v3/{self.domain}/messages"
            
            response = requests.post(
                url,
                auth=auth,
                data=data,
                files=files if files else None,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'provider': self.name,
                    'message_id': email.id,
                    'mailgun_id': result.get('id'),
                    'sent_at': timezone.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'provider': self.name,
                    'error': f"Mailgun API error: {response.status_code} - {response.text}",
                    'message_id': email.id
                }
                
        except Exception as e:
            logger.error(f"Mailgun send error: {e}")
            return {
                'success': False,
                'provider': self.name,
                'error': 'Operation failed',
                'message_id': email.id
            }
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract plain text from HTML content"""
        try:
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except:
            return "Email content"
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate Mailgun configuration"""
        errors = []
        
        if not self.api_key:
            errors.append("Mailgun API key is required")
        
        if not self.domain:
            errors.append("Mailgun domain is required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class EmailService:
    """Main email service management"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers = {}
        self.templates = {}
        self.enabled = config.get('enabled', True)
        self.default_provider = config.get('default_provider', 'smtp')
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 60)
        self.tracking_enabled = config.get('tracking_enabled', True)
        
        # Initialize providers
        self._initialize_providers()
        
        # Load templates
        self._load_templates()
        
    def _initialize_providers(self):
        """Initialize email providers"""
        provider_configs = self.config.get('providers', {})
        
        for provider_name, provider_config in provider_configs.items():
            provider_type = provider_config.get('type', 'smtp')
            
            if provider_type == 'smtp':
                provider = SMTPEmailProvider(provider_config)
            elif provider_type == 'sendgrid':
                provider = SendGridEmailProvider(provider_config)
            elif provider_type == 'mailgun':
                provider = MailgunEmailProvider(provider_config)
            else:
                logger.error(f"Unknown provider type: {provider_type}")
                continue
            
            self.providers[provider_name] = provider
            logger.info(f"Initialized email provider: {provider_name}")
    
    def _load_templates(self):
        """Load email templates"""
        template_configs = self.config.get('templates', {})
        
        for template_name, template_config in template_configs.items():
            template = EmailTemplate(
                name=template_name,
                subject_template=template_config.get('subject_template'),
                html_template=template_config.get('html_template'),
                text_template=template_config.get('text_template'),
                metadata=template_config.get('metadata', {})
            )
            
            self.templates[template_name] = template
            logger.info(f"Loaded email template: {template_name}")
    
    def create_email(self, to_email: str, subject: str, html_content: str,
                    from_email: str = None, cc: List[str] = None, bcc: List[str] = None,
                    reply_to: str = None, attachments: List[Dict[str, Any]] = None,
                    metadata: Dict[str, Any] = None) -> EmailMessage:
        """Create email message"""
        return EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=from_email,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            attachments=attachments,
            metadata=metadata
        )
    
    def create_email_from_template(self, template_name: str, to_email: str,
                                 context: Dict[str, Any], from_email: str = None,
                                 cc: List[str] = None, bcc: List[str] = None,
                                 reply_to: str = None, attachments: List[Dict[str, Any]] = None,
                                 metadata: Dict[str, Any] = None) -> Optional[EmailMessage]:
        """Create email from template"""
        template = self.templates.get(template_name)
        if not template:
            logger.error(f"Template {template_name} not found")
            return None
        
        # Render template
        rendered = template.render(context)
        
        # Add tracking pixel if enabled
        if self.tracking_enabled:
            tracking_pixel = f'<img src="{self._get_tracking_url()}" width="1" height="1" style="display:none;">'
            rendered['html_content'] += tracking_pixel
        
        return EmailMessage(
            to_email=to_email,
            subject=rendered['subject'],
            html_content=rendered['html_content'],
            from_email=from_email,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
            attachments=attachments,
            metadata=metadata
        )
    
    async def send_email(self, email: EmailMessage, provider_name: str = None) -> Dict[str, Any]:
        """Send email"""
        if not self.enabled:
            return {
                'success': False,
                'error': 'Email service is disabled'
            }
        
        # Get provider
        provider_name = provider_name or self.default_provider
        provider = self.providers.get(provider_name)
        
        if not provider:
            return {
                'success': False,
                'error': f'Provider {provider_name} not found'
            }
        
        if not provider.enabled:
            return {
                'success': False,
                'error': f'Provider {provider_name} is disabled'
            }
        
        # Update email status
        email.status = EmailStatus.SENDING
        
        # Send email
        try:
            result = await provider.send_email(email)
            
            if result['success']:
                email.status = EmailStatus.SENT
                email.sent_at = timezone.now()
                logger.info(f"Email {email.id} sent successfully to {email.to_email}")
            else:
                email.status = EmailStatus.FAILED
                email.error_message = result.get('error', 'Unknown error')
                logger.error(f"Email {email.id} failed: {result.get('error')}")
            
            return result
            
        except Exception as e:
            email.status = EmailStatus.FAILED
            email.error_message = str(e)
            logger.error(f"Email {email.id} error: {e}")
            
            return {
                'success': False,
                'error': 'Operation failed',
                'message_id': email.id
            }
    
    async def send_batch(self, emails: List[EmailMessage], provider_name: str = None) -> Dict[str, Any]:
        """Send multiple emails in batch"""
        results = {
            'total': len(emails),
            'sent': 0,
            'failed': 0,
            'results': []
        }
        
        # Send emails concurrently
        tasks = []
        for email in emails:
            task = asyncio.create_task(self.send_email(email, provider_name))
            tasks.append(task)
        
        # Wait for all tasks to complete
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in batch_results:
            if isinstance(result, Exception):
                results['failed'] += 1
                results['results'].append({
                    'success': False,
                    'error': str(result)
                })
            elif result['success']:
                results['sent'] += 1
                results['results'].append(result)
            else:
                results['failed'] += 1
                results['results'].append(result)
        
        return results
    
    def add_template(self, template: EmailTemplate):
        """Add email template"""
        self.templates[template.name] = template
        logger.info(f"Added email template: {template.name}")
    
    def remove_template(self, template_name: str):
        """Remove email template"""
        if template_name in self.templates:
            del self.templates[template_name]
            logger.info(f"Removed email template: {template_name}")
    
    def add_provider(self, provider_name: str, provider: EmailProvider):
        """Add email provider"""
        self.providers[provider_name] = provider
        logger.info(f"Added email provider: {provider_name}")
    
    def remove_provider(self, provider_name: str):
        """Remove email provider"""
        if provider_name in self.providers:
            del self.providers[provider_name]
            logger.info(f"Removed email provider: {provider_name}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get email service status"""
        return {
            'service_enabled': self.enabled,
            'total_providers': len(self.providers),
            'enabled_providers': len([p for p in self.providers.values() if p.enabled]),
            'total_templates': len(self.templates),
            'default_provider': self.default_provider,
            'tracking_enabled': self.tracking_enabled,
            'providers': {
                name: provider.get_provider_info()
                for name, provider in self.providers.items()
            },
            'templates': {
                name: {
                    'name': template.name,
                    'created_at': template.created_at.isoformat(),
                    'metadata': template.metadata
                }
                for name, template in self.templates.items()
            },
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_tracking_url(self) -> str:
        """Get tracking pixel URL"""
        # This would generate a unique tracking URL
        return f"https://your-domain.com/track/email/{uuid.uuid4()}.png"
    
    def track_email_open(self, email_id: str):
        """Track email open event"""
        # This would update email status to OPENED
        logger.info(f"Email {email_id} opened")
    
    def track_email_click(self, email_id: str, url: str):
        """Track email click event"""
        # This would update email status to CLICKED
        logger.info(f"Email {email_id} clicked: {url}")


# Global email service
email_service = None


def get_email_service() -> Optional[EmailService]:
    """Get the global email service"""
    return email_service


def initialize_email_service():
    """Initialize email service from settings"""
    from django.conf import settings
    
    global email_service
    
    config = getattr(settings, 'EMAIL_SERVICE_CONFIG', {
        'enabled': True,
        'default_provider': 'smtp',
        'max_retries': 3,
        'retry_delay': 60,
        'tracking_enabled': True,
        'providers': {
            'smtp': {
                'type': 'smtp',
                'enabled': True,
                'smtp_host': 'smtp.gmail.com',
                'smtp_port': 587,
                'smtp_username': settings.EMAIL_HOST_USER,
                'smtp_password': settings.EMAIL_HOST_PASSWORD,
                'use_tls': True
            }
        },
        'templates': {
            'alert_notification': {
                'subject_template': 'emails/alert_subject.txt',
                'html_template': 'emails/alert_notification.html',
                'text_template': 'emails/alert_notification.txt'
            }
        }
    })
    
    try:
        email_service = EmailService(config)
        logger.info("Email service initialized")
    except Exception as e:
        logger.error(f"Error initializing email service: {e}")


# Initialize on module import
try:
    initialize_email_service()
except Exception as e:
    logger.error(f"Error initializing email service: {e}")
