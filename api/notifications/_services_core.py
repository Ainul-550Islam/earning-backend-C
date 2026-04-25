# earning_backend/api/notifications/services.py
import json
import logging
import hashlib
import uuid
import time
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from collections import defaultdict
from django.db import transaction, models
from django.db.models import Q, Count, Sum, Avg, Max, Min, F, Value, Case, When
from django.db.models.functions import TruncDate, TruncHour, Coalesce
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
import requests
from twilio.rest import Client as TwilioClient
from telegram import Bot
import firebase_admin
from firebase_admin import messaging, credentials
import boto3
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content, To, From, Personalization
import nexmo

from ._models_core import (
    Notification, NotificationTemplate, NotificationPreference,
    DeviceToken, NotificationCampaign, NotificationRule,
    NotificationFeedback, NotificationLog, NotificationAnalytics
)
from .utils import TemplateRenderer, NotificationValidator, EncryptionService

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Core service for notification operations
    """
    
    # Cache keys
    CACHE_PREFIX = 'notification_'
    USER_PREFS_CACHE_KEY = 'user_prefs_{}'
    DEVICE_TOKENS_CACHE_KEY = 'device_tokens_{}'
    TEMPLATE_CACHE_KEY = 'template_{}'
    USER_STATS_CACHE_KEY = 'user_stats_{}'
    SYSTEM_STATS_CACHE_KEY = 'system_stats'
    
    # Rate limiting
    RATE_LIMIT_KEY = 'rate_limit_{}_{}'
    RATE_LIMIT_WINDOW = 3600  # 1 hour
    RATE_LIMIT_MAX = 100
    
    # Delivery providers
    PROVIDERS = {
        'fcm': 'firebase',
        'apns': 'apple',
        'webpush': 'web',
        'email_smtp': 'smtp',
        'email_sendgrid': 'sendgrid',
        'sms_twilio': 'twilio',
        'sms_nexmo': 'nexmo',
        'telegram': 'telegram',
        'whatsapp_twilio': 'whatsapp',
    }
    
    def __init__(self):
        # Initialize providers
        self._initialize_providers()
        
    def _initialize_providers(self):
        """Initialize notification providers"""
        # Firebase
        if hasattr(settings, 'FIREBASE_CREDENTIALS'):
            try:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
                firebase_admin.initialize_app(cred)
            except Exception as e:
                logger.warning(f"Failed to initialize Firebase: {e}")
        
        # Twilio
        self.twilio_client = None
        if hasattr(settings, 'TWILIO_ACCOUNT_SID') and hasattr(settings, 'TWILIO_AUTH_TOKEN'):
            try:
                self.twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            except Exception as e:
                logger.warning(f"Failed to initialize Twilio: {e}")
        
        # SendGrid
        self.sendgrid_client = None
        if hasattr(settings, 'SENDGRID_API_KEY'):
            try:
                self.sendgrid_client = SendGridAPIClient(settings.SENDGRID_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize SendGrid: {e}")
        
        # Nexmo
        self.nexmo_client = None
        if hasattr(settings, 'NEXMO_API_KEY') and hasattr(settings, 'NEXMO_API_SECRET'):
            try:
                self.nexmo_client = nexmo.Client(
                    key=settings.NEXMO_API_KEY,
                    secret=settings.NEXMO_API_SECRET
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Nexmo: {e}")
        
        
        
        # api/notifications/services.py এর 114-120 line replace করো:

        # Telegram
        self.telegram_bot = None
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if token and token not in ('your_actual_token_here', 'your_token_here', ''):
            try:
                self.telegram_bot = Bot(token=token)
            except Exception as e:
                logger.debug(f"Telegram bot not initialized: {e}")  # warning -> debug
        else:
            logger.debug("Telegram bot token not configured, skipping")  # warning -> debug
        # # Telegram
        # self.telegram_bot = None
        # if hasattr(settings, 'TELEGRAM_BOT_TOKEN'):
        #     try:
        #         self.telegram_bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        #     except Exception as e:
        #         logger.warning(f"Failed to initialize Telegram bot: {e}")
        
        # # AWS SNS for push
        # self.sns_client = None
        # if hasattr(settings, 'AWS_ACCESS_KEY_ID') and hasattr(settings, 'AWS_SECRET_ACCESS_KEY'):
        #     try:
        #         self.sns_client = boto3.client(
        #             'sns',
        #             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        #             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        #             region_name=getattr(settings, 'AWS_REGION', 'us-east-1')
        #         )
        #     except Exception as e:
        #         logger.warning(f"Failed to initialize AWS SNS: {e}")
    
    # ==================== NOTIFICATION CREATION ====================
    
    @transaction.atomic
    def create_notification(
        self,
        user,
        title: str,
        message: str,
        notification_type: str = 'general',
        priority: str = 'medium',
        channel: str = 'in_app',
        metadata: Optional[Dict] = None,
        image_url: Optional[str] = None,
        icon_url: Optional[str] = None,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
        deep_link: Optional[str] = None,
        expire_date: Optional[datetime] = None,
        scheduled_for: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        campaign_id: Optional[str] = None,
        campaign_name: Optional[str] = None,
        group_id: Optional[str] = None,
        is_pinned: bool = False,
        sound_enabled: bool = True,
        vibration_enabled: bool = True,
        badge_count: int = 1,
        rich_content: Optional[Dict] = None,
        custom_fields: Optional[Dict] = None,
        created_by: Optional[Any] = None,
        check_duplicate: bool = True,
        send_immediately: bool = True,
        **kwargs
    ) -> Optional[Notification]:
        """
        Create a new notification with validation and delivery logic
        """
        try:
            # Check rate limit
            if not self._check_rate_limit(user, channel):
                logger.warning(f"Rate limit exceeded for user {user.id} on channel {channel}")
                return None
            
            # Check for duplicates
            if check_duplicate and self._is_duplicate_notification(user, title, message):
                logger.info(f"Duplicate notification detected for user {user.id}")
                return None
            
            # Get user preferences
            preferences = self.get_user_preferences(user)
            
            # Check if user wants this notification
            if not self._can_send_notification(preferences, notification_type, channel, priority):
                logger.info(f"User {user.id} has disabled {notification_type} notifications on {channel}")
                return None
            
            # Validate notification data
            validator = NotificationValidator()
            validation_errors = validator.validate_notification_data({
                'user': user,
                'title': title,
                'message': message,
                'notification_type': notification_type,
                'priority': priority,
                'channel': channel,
                'expire_date': expire_date,
                'scheduled_for': scheduled_for,
            })
            
            if validation_errors:
                logger.error(f"Notification validation failed: {validation_errors}")
                raise ValidationError(validation_errors)
            
            # Prepare metadata
            if metadata is None:
                metadata = {}
            
            # Add system metadata
            metadata.update({
                'created_by': str(created_by.id) if created_by else 'system',
                'created_at': timezone.now().isoformat(),
                'version': '1.0',
            })
            
            # Set status based on schedule
            status = 'pending'
            if scheduled_for and scheduled_for > timezone.now():
                status = 'scheduled'
            
            # Create notification
            notification = Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                channel=channel,
                status=status,
                metadata=metadata,
                image_url=image_url,
                icon_url=icon_url,
                action_url=action_url,
                action_text=action_text,
                deep_link=deep_link,
                expire_date=expire_date,
                scheduled_for=scheduled_for,
                tags=tags or [],
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                group_id=group_id or str(uuid.uuid4()),
                is_pinned=is_pinned,
                sound_enabled=sound_enabled,
                vibration_enabled=vibration_enabled,
                badge_count=badge_count,
                rich_content=rich_content or {},
                custom_fields=custom_fields or {},
                created_by=created_by,
                **kwargs
            )
            
            # Log creation
            NotificationLog.objects.create(
                notification=notification,
                user=user,
                log_type='info',
                message=f"Notification created: {title}",
                details={
                    'notification_id': str(notification.id),
                    'type': notification_type,
                    'channel': channel,
                    'priority': priority,
                }
            )
            
            # Update user preferences analytics
            preferences.total_notifications_received += 1
            preferences.save()
            
            # Clear cache
            self._clear_user_cache(user)
            
            # Send immediately if requested and not scheduled
            if send_immediately and status == 'pending':
                self.send_notification(notification)
            
            return notification
            
        except Exception as e:
            logger.error(f"Failed to create notification: {e}", exc_info=True)
            # Log the error
            NotificationLog.objects.create(
                user=user,
                log_type='error',
                log_level='error',
                message=f"Failed to create notification: {str(e)}",
                details={
                    'title': title,
                    'type': notification_type,
                    'channel': channel,
                    'error': str(e),
                }
            )
            return None
    
    def create_from_template(
        self,
        template_name: str,
        user,
        context: Optional[Dict] = None,
        language: str = 'en',
        **kwargs
    ) -> Optional[Notification]:
        """
        Create notification from template
        """
        try:
            # Get template
            template = self.get_template(template_name)
            if not template or not template.is_active:
                logger.error(f"Template not found or inactive: {template_name}")
                return None
            
            # Check if user has access to template
            if not template.is_public and not self._user_can_access_template(user, template):
                logger.warning(f"User {user.id} cannot access template {template_name}")
                return None
            
            # Render template
            renderer = TemplateRenderer()
            rendered = renderer.render_template(template, context or {}, language)
            
            if not rendered:
                logger.error(f"Failed to render template: {template_name}")
                return None
            
            # Validate variables
            try:
                template.validate_variables(context or {})
            except ValidationError as e:
                logger.error(f"Template variable validation failed: {e}")
                return None
            
            # Create notification
            notification = self.create_notification(
                user=user,
                title=rendered['title'],
                message=rendered['message'],
                notification_type=template.template_type,
                priority=rendered.get('priority', template.default_priority),
                channel=rendered.get('channel', template.default_channel),
                icon_url=rendered.get('icon_url', template.icon_url),
                image_url=rendered.get('image_url', template.image_url),
                action_url=rendered.get('action_url'),
                action_text=rendered.get('action_text'),
                deep_link=rendered.get('deep_link'),
                metadata=rendered.get('metadata', {}),
                tags=rendered.get('tags', []),
                sound_enabled=rendered.get('sound_enabled', True),
                vibration_enabled=rendered.get('vibration_enabled', True),
                badge_count=rendered.get('badge_count', 1),
                **kwargs
            )
            
            if notification:
                # Update template usage
                template.increment_usage()
                
                # Add template metadata
                notification.metadata.update({
                    'template': template_name,
                    'template_version': template.version,
                    'rendered_context': context or {},
                    'language': language,
                })
                notification.save()
            
            return notification
            
        except Exception as e:
            logger.error(f"Failed to create notification from template: {e}", exc_info=True)
            return None
    
    def create_bulk_notifications(
        self,
        users: List[Any],
        title: str,
        message: str,
        batch_id: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Create notifications for multiple users
        """
        if not batch_id:
            batch_id = str(uuid.uuid4())
        
        results = {
            'batch_id': batch_id,
            'total_users': len(users),
            'successful': 0,
            'failed': 0,
            'notifications': [],
            'errors': []
        }
        
        for user in users:
            try:
                notification = self.create_notification(
                    user=user,
                    title=title,
                    message=message,
                    batch_id=batch_id,
                    **kwargs
                )
                
                if notification:
                    results['successful'] += 1
                    results['notifications'].append(str(notification.id))
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'user_id': user.id,
                        'error': 'Notification creation failed'
                    })
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'user_id': user.id,
                    'error': str(e)
                })
                logger.error(f"Failed to create notification for user {user.id}: {e}")
        
        # Log bulk creation
        NotificationLog.objects.create(
            log_type='info',
            message=f"Bulk notifications created: {results['successful']} successful, {results['failed']} failed",
            details=results
        )
        
        return results
    
    # ==================== NOTIFICATION DELIVERY ====================
    
    def send_notification(self, notification: Notification) -> bool:
        """
        Send notification through appropriate channels
        """
        try:
            # Check if notification can be sent
            if not self._can_send_notification_now(notification):
                logger.info(f"Notification {notification.id} cannot be sent now")
                return False
            
            # Mark as sending
            notification.status = 'sending'
            notification.save()
            
            # Get delivery channels
            channels = notification.get_delivery_channels()
            
            # Track delivery results
            delivery_results = {}
            
            # Send through each channel
            for channel in channels:
                try:
                    result = self._send_via_channel(notification, channel)
                    delivery_results[channel] = result
                    
                    if result['success']:
                        logger.info(f"Notification {notification.id} sent via {channel}")
                    else:
                        logger.error(f"Notification {notification.id} failed via {channel}: {result.get('error')}")
                        
                except Exception as e:
                    delivery_results[channel] = {
                        'success': False,
                        'error': str(e)
                    }
                    logger.error(f"Error sending notification {notification.id} via {channel}: {e}", exc_info=True)
            
            # Update notification status based on results
            any_success = any(result.get('success', False) for result in delivery_results.values())
            
            if any_success:
                notification.mark_as_sent()
                notification.cost = notification.estimate_cost()
                
                # Mark as delivered for in-app notifications
                if 'in_app' in channels:
                    notification.mark_as_delivered()
            else:
                notification.mark_as_failed(
                    error_message=json.dumps(delivery_results)
                )
            
            notification.metadata['delivery_results'] = delivery_results
            notification.save()
            
            # Update user preferences analytics
            preferences = self.get_user_preferences(notification.user)
            preferences.update_analytics(notification)
            
            # Log delivery
            NotificationLog.log_delivery(
                notification,
                success=any_success,
                details=delivery_results
            )
            
            return any_success
            
        except Exception as e:
            logger.error(f"Failed to send notification {notification.id}: {e}", exc_info=True)
            
            notification.mark_as_failed(error_message=str(e))
            notification.save()
            
            NotificationLog.log_error(
                f"Failed to send notification: {str(e)}",
                notification=notification,
                details={'error': str(e)}
            )
            
            return False
    
    def _send_via_channel(self, notification: Notification, channel: str) -> Dict:
        """
        Send notification via specific channel
        """
        result = {
            'success': False,
            'channel': channel,
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            if channel == 'in_app':
                result.update(self._send_in_app(notification))
            elif channel == 'push':
                result.update(self._send_push(notification))
            elif channel == 'email':
                result.update(self._send_email(notification))
            elif channel == 'sms':
                result.update(self._send_sms(notification))
            elif channel == 'telegram':
                result.update(self._send_telegram(notification))
            elif channel == 'whatsapp':
                result.update(self._send_whatsapp(notification))
            elif channel == 'browser':
                result.update(self._send_browser_push(notification))
            else:
                result['error'] = f"Unsupported channel: {channel}"
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def _send_in_app(self, notification: Notification) -> Dict:
        """
        Send in-app notification
        """
        # In-app notifications are created in the database
        # No external service needed
        
        notification.mark_as_delivered()
        notification.save()
        
        return {
            'success': True,
            'provider': 'database',
            'message': 'Notification stored in database'
        }
    
    def _send_push(self, notification: Notification) -> Dict:
        """
        Send push notification
        """
        # Get user's device tokens
        device_tokens = self.get_user_device_tokens(notification.user)
        
        if not device_tokens:
            return {
                'success': False,
                'error': 'No device tokens found',
                'provider': 'none'
            }
        
        # Track results per device
        device_results = []
        any_success = False
        
        for device_token in device_tokens:
            if not device_token.is_active or not device_token.push_enabled:
                continue
            
            try:
                # Get appropriate push token
                token = device_token.get_push_token()
                if not token:
                    continue
                
                # Build message based on platform
                message = self._build_push_message(notification, device_token)
                
                # Send based on platform
                if device_token.platform in ['android_app', 'ios_app']:
                    if self.twilio_client:
                        # Use Twilio for mobile push
                        result = self._send_via_twilio_push(token, message, device_token)
                    elif self.sns_client:
                        # Use AWS SNS
                        result = self._send_via_sns(token, message, device_token)
                    else:
                        # Use Firebase
                        result = self._send_via_firebase(token, message, device_token)
                else:
                    result = {
                        'success': False,
                        'error': f'Unsupported platform: {device_token.platform}'
                    }
                
                # Update device token stats
                if result.get('success'):
                    device_token.increment_push_delivered()
                    any_success = True
                else:
                    device_token.increment_push_failed()
                
                device_results.append({
                    'device_id': str(device_token.id),
                    'platform': device_token.platform,
                    'success': result.get('success', False),
                    'error': result.get('error'),
                    'message_id': result.get('message_id')
                })
                
            except Exception as e:
                device_token.increment_push_failed()
                device_results.append({
                    'device_id': str(device_token.id),
                    'platform': device_token.platform,
                    'success': False,
                    'error': str(e)
                })
                logger.error(f"Failed to send push to device {device_token.id}: {e}")
        
        return {
            'success': any_success,
            'device_results': device_results,
            'total_devices': len(device_tokens),
            'successful_devices': sum(1 for r in device_results if r.get('success'))
        }
    
    def _send_email(self, notification: Notification) -> Dict:
        """
        Send email notification
        """
        user = notification.user
        
        # Check if user has email
        if not user.email:
            return {
                'success': False,
                'error': 'User has no email address',
                'provider': 'none'
            }
        
        # Build email
        subject = notification.title
        html_content = self._build_email_content(notification)
        text_content = notification.message
        
        try:
            # Try SendGrid first
            if self.sendgrid_client:
                result = self._send_via_sendgrid(user.email, subject, html_content, text_content)
                if result['success']:
                    return result
            
            # Fallback to SMTP
            result = self._send_via_smtp(user.email, subject, html_content, text_content)
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider': 'none'
            }
    
    def _send_sms(self, notification: Notification) -> Dict:
        """
        Send SMS notification
        """
        # This requires user's phone number in profile
        # For now, return not implemented
        return {
            'success': False,
            'error': 'SMS not implemented',
            'provider': 'none'
        }
    
    def _send_telegram(self, notification: Notification) -> Dict:
        """
        Send Telegram notification
        """
        # This requires user's Telegram chat ID
        # For now, return not implemented
        return {
            'success': False,
            'error': 'Telegram not implemented',
            'provider': 'none'
        }
    
    def _send_whatsapp(self, notification: Notification) -> Dict:
        """
        Send WhatsApp notification
        """
        # This requires user's WhatsApp number
        # For now, return not implemented
        return {
            'success': False,
            'error': 'WhatsApp not implemented',
            'provider': 'none'
        }
    
    def _send_browser_push(self, notification: Notification) -> Dict:
        """
        Send browser push notification
        """
        # This requires user's browser push subscription
        # For now, return not implemented
        return {
            'success': False,
            'error': 'Browser push not implemented',
            'provider': 'none'
        }
    
    # ==================== PROVIDER METHODS ====================
    
    def _send_via_firebase(self, token: str, message: messaging.Message, device_token) -> Dict:
        """
        Send via Firebase Cloud Messaging
        """
        try:
            response = messaging.send(message)
            
            return {
                'success': True,
                'provider': 'firebase',
                'message_id': response,
                'details': {'token': token[:10] + '...'}  # Hide full token
            }
            
        except Exception as e:
            return {
                'success': False,
                'provider': 'firebase',
                'error': str(e)
            }
    
    def _send_via_twilio_push(self, token: str, message: Dict, device_token) -> Dict:
        """
        Send via Twilio Push
        """
        # Implementation depends on Twilio setup
        return {
            'success': False,
            'provider': 'twilio',
            'error': 'Not implemented'
        }
    
    def _send_via_sns(self, token: str, message: Dict, device_token) -> Dict:
        """
        Send via AWS SNS
        """
        # Implementation depends on AWS setup
        return {
            'success': False,
            'provider': 'sns',
            'error': 'Not implemented'
        }
    
    def _send_via_sendgrid(self, to_email: str, subject: str, html_content: str, text_content: str) -> Dict:
        """
        Send via SendGrid
        """
        try:
            from_email = From(getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'))
            to_email = To(to_email)
            content = Content("text/html", html_content)
            
            mail = Mail(from_email, to_email, subject, text_content)
            mail.add_content(content)
            
            response = self.sendgrid_client.client.mail.send.post(request_body=mail.get())
            
            return {
                'success': True,
                'provider': 'sendgrid',
                'message_id': response.headers.get('X-Message-Id'),
                'status_code': response.status_code
            }
            
        except Exception as e:
            return {
                'success': False,
                'provider': 'sendgrid',
                'error': str(e)
            }
    
    def _send_via_smtp(self, to_email: str, subject: str, html_content: str, text_content: str) -> Dict:
        """
        Send via SMTP
        """
        try:
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[to_email],
                headers={'X-Notification-ID': str(uuid.uuid4())}
            )
            email.attach_alternative(html_content, "text/html")
            
            email.send()
            
            return {
                'success': True,
                'provider': 'smtp',
                'message_id': str(uuid.uuid4())  # Generate our own ID
            }
            
        except Exception as e:
            return {
                'success': False,
                'provider': 'smtp',
                'error': str(e)
            }
    
    # ==================== MESSAGE BUILDING ====================
    
    def _build_push_message(self, notification: Notification, device_token) -> messaging.Message:
        """
        Build push message for specific device
        """
        # Base notification
        android_notification = messaging.AndroidNotification(
            title=notification.title,
            body=notification.message,
            icon=notification.icon_url or 'default',
            color='#FF0000',  # Red color
            sound='default' if notification.sound_enabled else None,
            tag=notification.group_id,
            click_action=notification.action_url or notification.deep_link,
            body_loc_key=None,
            body_loc_args=None,
            title_loc_key=None,
            title_loc_args=None,
            channel_id='default',
        )
        
        android_config = messaging.AndroidConfig(
            priority='high' if notification.is_high_priority() else 'normal',
            ttl=timedelta(days=1),
            collapse_key=notification.group_id,
            notification=android_notification,
        )
        
        # APNS (iOS) config
        apns_headers = {
            'apns-priority': '10' if notification.is_high_priority() else '5',
            'apns-topic': getattr(settings, 'APNS_TOPIC', 'com.example.app'),
        }
        
        apns_payload = messaging.APNSPayload(
            aps=messaging.Aps(
                alert=messaging.ApsAlert(
                    title=notification.title,
                    body=notification.message,
                ),
                sound='default' if notification.sound_enabled else None,
                badge=notification.badge_count,
                category=notification.notification_type,
                thread_id=notification.group_id,
            ),
        )
        
        apns_config = messaging.APNSConfig(
            headers=apns_headers,
            payload=apns_payload,
        )
        
        # Web push config
        webpush_headers = {
            'TTL': '86400',  # 24 hours
        }
        
        webpush_notification = messaging.WebpushNotification(
            title=notification.title,
            body=notification.message,
            icon=notification.icon_url,
            badge=notification.icon_url,
            data={
                'action_url': notification.action_url or '',
                'deep_link': notification.deep_link or '',
            },
            actions=[
                {
                    'action': 'open',
                    'title': notification.action_text or 'Open',
                }
            ] if notification.action_url else [],
        )
        
        webpush_config = messaging.WebpushConfig(
            headers=webpush_headers,
            notification=webpush_notification,
        )
        
        # Build message
        message = messaging.Message(
            notification=messaging.Notification(
                title=notification.title,
                body=notification.message,
                image=notification.image_url,
            ),
            data={
                'notification_id': str(notification.id),
                'type': notification.notification_type,
                'priority': notification.priority,
                'action_url': notification.action_url or '',
                'deep_link': notification.deep_link or '',
                'metadata': json.dumps(notification.metadata),
                'created_at': notification.created_at.isoformat(),
            },
            token=device_token.get_push_token(),
            android=android_config,
            apns=apns_config,
            webpush=webpush_config,
        )
        
        return message
    
    def _build_email_content(self, notification: Notification) -> str:
        """
        Build HTML email content
        """
        context = {
            'notification': notification,
            'user': notification.user,
            'site_url': getattr(settings, 'SITE_URL', 'https://example.com'),
            'site_name': getattr(settings, 'SITE_NAME', 'Example Site'),
            'current_year': timezone.now().year,
        }
        
        # Try to render template
        try:
            return render_to_string('notifications/email_template.html', context)
        except:
            # Fallback template
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>{notification.title}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 30px; background-color: #f9f9f9; }}
                    .footer {{ margin-top: 20px; text-align: center; color: #666; font-size: 12px; }}
                    .button {{ display: inline-block; padding: 10px 20px; background-color: #4CAF50; 
                              color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>{notification.title}</h1>
                    </div>
                    <div class="content">
                        <p>Hello {notification.user.username},</p>
                        <p>{notification.message}</p>
                        {f'<p><a href="{notification.action_url}" class="button">{notification.action_text or "View Details"}</a></p>' if notification.action_url else ''}
                        <p>Thank you,<br>The {context['site_name']} Team</p>
                    </div>
                    <div class="footer">
                        <p>This email was sent by {context['site_name']}.</p>
                        <p>© {context['current_year']} {context['site_name']}. All rights reserved.</p>
                        <p><a href="{context['site_url']}/unsubscribe">Unsubscribe</a> | 
                           <a href="{context['site_url']}/preferences">Notification Preferences</a></p>
                    </div>
                </div>
            </body>
            </html>
            """
    
    # ==================== HELPER METHODS ====================
    
    def _check_rate_limit(self, user, channel: str) -> bool:
        """
        Check rate limit for user and channel
        """
        cache_key = self.RATE_LIMIT_KEY.format(user.id, channel)
        count = cache.get(cache_key, 0)
        
        if count >= self.RATE_LIMIT_MAX:
            return False
        
        # Increment count
        cache.set(cache_key, count + 1, self.RATE_LIMIT_WINDOW)
        return True
    
    def _is_duplicate_notification(self, user, title: str, message: str) -> bool:
        """
        Check for duplicate notifications in last 24 hours
        """
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        return Notification.objects.filter(
            user=user,
            title=title,
            message=message,
            created_at__gte=cutoff_time,
            is_deleted=False
        ).exists()
    
    def _can_send_notification(self, preferences, notification_type: str, channel: str, priority: str) -> bool:
        """
        Check if notification can be sent based on preferences
        """
        if not preferences:
            return True
        
        return preferences.can_receive_notification(notification_type, channel, priority)
    
    def _can_send_notification_now(self, notification: Notification) -> bool:
        """
        Check if notification can be sent now
        """
        # Check if already sent
        if notification.is_sent and notification.status not in ['failed', 'pending']:
            return False
        
        # Check if expired
        if notification.is_expired():
            notification.status = 'expired'
            notification.save()
            return False
        
        # Check if scheduled for future
        if notification.scheduled_for and notification.scheduled_for > timezone.now():
            return False
        
        # Check if deleted or archived
        if notification.is_deleted or notification.is_archived:
            return False
        
        # Get user preferences
        preferences = self.get_user_preferences(notification.user)
        if not preferences:
            return True
        
        # Check preferences
        return preferences.can_receive_notification(
            notification.notification_type,
            notification.channel,
            notification.priority
        )
    
    def _user_can_access_template(self, user, template) -> bool:
        """
        Check if user can access template
        """
        # Superusers can access all templates
        if user.is_superuser:
            return True
        
        # Check groups
        if template.allowed_groups and user.groups.filter(name__in=template.allowed_groups).exists():
            return True
        
        # Check roles (custom implementation)
        # This depends on your user role system
        if template.allowed_roles:
            # Implement role checking based on your system
            pass
        
        return False
    
    def _clear_user_cache(self, user):
        """
        Clear cache for user
        """
        cache_keys = [
            self.USER_PREFS_CACHE_KEY.format(user.id),
            self.DEVICE_TOKENS_CACHE_KEY.format(user.id),
            self.USER_STATS_CACHE_KEY.format(user.id),
        ]
        
        for key in cache_keys:
            cache.delete(key)
    
    # ==================== GETTER METHODS ====================
    
    def get_user_preferences(self, user, force_refresh: bool = False) -> Optional[NotificationPreference]:
        """
        Get user notification preferences
        """
        cache_key = self.USER_PREFS_CACHE_KEY.format(user.id)
        
        if not force_refresh:
            preferences = cache.get(cache_key)
            if preferences:
                return preferences
        
        try:
            preferences, created = NotificationPreference.objects.get_or_create(user=user)
            cache.set(cache_key, preferences, 3600)  # Cache for 1 hour
            return preferences
        except Exception as e:
            logger.error(f"Failed to get user preferences: {e}")
            return None
    
    def get_user_device_tokens(self, user, active_only: bool = True) -> List[DeviceToken]:
        """
        Get user's device tokens
        """
        cache_key = self.DEVICE_TOKENS_CACHE_KEY.format(user.id)
        
        tokens = cache.get(cache_key)
        if tokens is None:
            queryset = DeviceToken.objects.filter(user=user)
            if active_only:
                queryset = queryset.filter(is_active=True, push_enabled=True)
            tokens = list(queryset)
            cache.set(cache_key, tokens, 300)  # Cache for 5 minutes
        
        return tokens
    
    def get_template(self, template_name: str) -> Optional[NotificationTemplate]:
        """
        Get notification template
        """
        cache_key = self.TEMPLATE_CACHE_KEY.format(template_name)
        
        template = cache.get(cache_key)
        if template is None:
            try:
                template = NotificationTemplate.objects.get(name=template_name, is_active=True)
                cache.set(cache_key, template, 3600)  # Cache for 1 hour
            except NotificationTemplate.DoesNotExist:
                return None
        
        return template
    
    def get_user_notifications(
        self,
        user,
        filters: Optional[Dict] = None,
        page: int = 1,
        per_page: int = 20,
        order_by: str = '-created_at'
    ) -> Dict:
        """
        Get notifications for user with pagination
        """
        if filters is None:
            filters = {}
        
        queryset = Notification.get_user_notifications(user, filters, order_by)
        
        # Calculate pagination
        total = queryset.count()
        total_pages = (total + per_page - 1) // per_page
        
        # Apply pagination
        start = (page - 1) * per_page
        end = start + per_page
        notifications = list(queryset[start:end])
        
        # Calculate unread count
        unread_count = Notification.get_unread_count(user)
        
        return {
            'notifications': notifications,
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'unread_count': unread_count,
        }
    
    def get_user_stats(self, user, force_refresh: bool = False) -> Dict:
        """
        Get user notification statistics
        """
        cache_key = self.USER_STATS_CACHE_KEY.format(user.id)
        
        if not force_refresh:
            stats = cache.get(cache_key)
            if stats:
                return stats
        
        # Get from database
        stats = Notification.get_stats(user=user)
        
        # Add preference stats
        preferences = self.get_user_preferences(user)
        if preferences:
            stats.update(preferences.get_stats())
        
        # Cache for 5 minutes
        cache.set(cache_key, stats, 300)
        
        return stats
    
    def get_system_stats(self, force_refresh: bool = False) -> Dict:
        """
        Get system-wide notification statistics
        """
        cache_key = self.SYSTEM_STATS_CACHE_KEY
        
        if not force_refresh:
            stats = cache.get(cache_key)
            if stats:
                return stats
        
        # Get from database
        stats = Notification.get_stats()
        
        # Add user counts
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        stats.update({
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'users_with_notifications': User.objects.filter(notifications__isnull=False).distinct().count(),
        })
        
        # Cache for 15 minutes
        cache.set(cache_key, stats, 900)
        
        return stats
    
    # ==================== BATCH OPERATIONS ====================
    
    def mark_all_as_read(self, user) -> Dict:
        """
        Mark all notifications as read for user
        """
        try:
            count = Notification.mark_all_as_read(user)
            
            # Clear cache
            self._clear_user_cache(user)
            
            # Log the action
            NotificationLog.objects.create(
                user=user,
                log_type='info',
                message=f'Marked all notifications as read ({count} notifications)'
            )
            
            return {
                'success': True,
                'count': count,
                'message': f'Marked {count} notifications as read'
            }
            
        except Exception as e:
            logger.error(f"Failed to mark all as read for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_expired_notifications(self) -> Dict:
        """
        Delete expired notifications
        """
        try:
            count = Notification.delete_expired()
            
            # Log the action
            NotificationLog.objects.create(
                log_type='info',
                message=f'Deleted {count} expired notifications'
            )
            
            return {
                'success': True,
                'count': count,
                'message': f'Deleted {count} expired notifications'
            }
            
        except Exception as e:
            logger.error(f"Failed to delete expired notifications: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_notifications(self, days: int = 90) -> Dict:
        """
        Cleanup old notifications
        """
        try:
            count = Notification.cleanup_old_notifications(days)
            
            # Log the action
            NotificationLog.objects.create(
                log_type='info',
                message=f'Cleaned up {count} old notifications (older than {days} days)'
            )
            
            return {
                'success': True,
                'count': count,
                'message': f'Cleaned up {count} old notifications'
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup old notifications: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def retry_failed_notifications(self, max_retries: int = 3) -> Dict:
        """
        Retry failed notifications
        """
        try:
            failed_notifications = Notification.objects.filter(
                status='failed',
                delivery_attempts__lt=max_retries,
                is_deleted=False
            )
            
            results = {
                'total': failed_notifications.count(),
                'successful': 0,
                'failed': 0,
                'details': []
            }
            
            for notification in failed_notifications:
                if notification.can_retry_delivery():
                    notification.prepare_for_retry()
                    success = self.send_notification(notification)
                    
                    if success:
                        results['successful'] += 1
                        results['details'].append({
                            'notification_id': str(notification.id),
                            'status': 'retry_successful'
                        })
                    else:
                        results['failed'] += 1
                        results['details'].append({
                            'notification_id': str(notification.id),
                            'status': 'retry_failed'
                        })
            
            # Log the action
            NotificationLog.objects.create(
                log_type='info',
                message=f'Retried {results["total"]} failed notifications ({results["successful"]} successful)',
                details=results
            )
            
            return {
                'success': True,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Failed to retry failed notifications: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ==================== CAMPAIGN MANAGEMENT ====================
    
    def create_campaign(
        self,
        name: str,
        target_segment: Dict,
        title_template: str,
        message_template: str,
        channel: str = 'in_app',
        campaign_type: str = 'promotional',
        created_by=None,
        **kwargs
    ) -> Optional[NotificationCampaign]:
        """
        Create a notification campaign
        """
        try:
            campaign = NotificationCampaign.objects.create(
                name=name,
                description=kwargs.get('description', ''),
                campaign_type=campaign_type,
                target_segment=target_segment,
                title_template=title_template,
                message_template=message_template,
                channel=channel,
                priority=kwargs.get('priority', 'medium'),
                scheduled_for=kwargs.get('scheduled_for'),
                status='draft',
                created_by=created_by,
                **{k: v for k, v in kwargs.items() if k in [
                    'send_limit', 'daily_limit', 'ab_test_enabled',
                    'ab_test_variants'
                ]}
            )
            
            # Calculate target count
            campaign.calculate_target_count()
            
            # Log creation
            NotificationLog.objects.create(
                log_type='info',
                message=f'Campaign created: {name}',
                details={
                    'campaign_id': str(campaign.id),
                    'target_count': campaign.target_count,
                    'type': campaign_type,
                    'channel': channel,
                }
            )
            
            return campaign
            
        except Exception as e:
            logger.error(f"Failed to create campaign: {e}", exc_info=True)
            return None
    
    def start_campaign(self, campaign_id: str) -> Dict:
        """
        Start a notification campaign
        """
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
            campaign.start()
            
            return {
                'success': True,
                'campaign_id': str(campaign.id),
                'message': 'Campaign started successfully'
            }
            
        except NotificationCampaign.DoesNotExist:
            return {
                'success': False,
                'error': 'Campaign not found'
            }
        except Exception as e:
            logger.error(f"Failed to start campaign {campaign_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_campaign(self, campaign_id: str, batch_size: int = 100) -> Dict:
        """
        Process a campaign (send notifications)
        """
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
            
            if campaign.status != 'running':
                return {
                    'success': False,
                    'error': f'Campaign is not running (status: {campaign.status})'
                }
            
            # Get target users
            users = self._get_campaign_target_users(campaign)
            
            if not users:
                campaign.complete()
                return {
                    'success': True,
                    'message': 'No target users found, campaign completed',
                    'notifications_sent': 0
                }
            
            # Process in batches
            total_sent = 0
            batch_number = 1
            
            for i in range(0, len(users), batch_size):
                batch_users = users[i:i + batch_size]
                
                # Check daily limit
                if campaign.daily_limit and campaign.total_sent >= campaign.daily_limit:
                    logger.info(f"Daily limit reached for campaign {campaign_id}")
                    break
                
                # Check total limit
                if campaign.send_limit and campaign.total_sent >= campaign.send_limit:
                    logger.info(f"Send limit reached for campaign {campaign_id}")
                    break
                
                # Send notifications to batch
                batch_results = self.create_bulk_notifications(
                    users=batch_users,
                    title=campaign.title_template,
                    message=campaign.message_template,
                    batch_id=str(campaign.id),
                    notification_type=campaign.campaign_type,
                    channel=campaign.channel,
                    priority=campaign.priority,
                    campaign_id=str(campaign.id),
                    campaign_name=campaign.name,
                )
                
                total_sent += batch_results['successful']
                
                # Update campaign progress
                campaign.update_progress()
                
                logger.info(f"Campaign {campaign_id} batch {batch_number}: "
                           f"{batch_results['successful']} successful, "
                           f"{batch_results['failed']} failed")
                
                batch_number += 1
            
            # Check if campaign is complete
            if campaign.total_sent >= campaign.target_count or \
               (campaign.send_limit and campaign.total_sent >= campaign.send_limit):
                campaign.complete()
            
            return {
                'success': True,
                'campaign_id': str(campaign.id),
                'total_sent': total_sent,
                'campaign_status': campaign.status
            }
            
        except NotificationCampaign.DoesNotExist:
            return {
                'success': False,
                'error': 'Campaign not found'
            }
        except Exception as e:
            logger.error(f"Failed to process campaign {campaign_id}: {e}", exc_info=True)
            
            # Mark campaign as failed
            try:
                campaign.status = 'failed'
                campaign.save()
            except:
                pass
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_campaign_target_users(self, campaign: NotificationCampaign):
        """
        Get target users for campaign
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        queryset = User.objects.filter(is_active=True)
        
        # Apply filters from target_segment
        filters = campaign.target_segment.get('filters', {})
        
        # Registration date filter
        if filters.get('registration_date'):
            reg_filter = filters['registration_date']
            if reg_filter.get('start'):
                queryset = queryset.filter(date_joined__gte=reg_filter['start'])
            if reg_filter.get('end'):
                queryset = queryset.filter(date_joined__lte=reg_filter['end'])
        
        # Country filter (assuming user profile model)
        if filters.get('country'):
            queryset = queryset.filter(profile__country__in=filters['country'])
        
        # Language filter
        if filters.get('language'):
            queryset = queryset.filter(profile__language__in=filters['language'])
        
        # User type filter
        if filters.get('user_type'):
            queryset = queryset.filter(profile__user_type__in=filters['user_type'])
        
        # Has made purchase filter (custom implementation)
        if filters.get('has_made_purchase'):
            # This would depend on your order/payment models
            pass
        
        # Exclude users who have already received this campaign
        existing_user_ids = Notification.objects.filter(
            campaign_id=str(campaign.id)
        ).values_list('user_id', flat=True).distinct()
        
        if existing_user_ids:
            queryset = queryset.exclude(id__in=existing_user_ids)
        
        return list(queryset)
    
    # ==================== RULE ENGINE ====================
    
    def execute_rule(self, rule_id: str, context: Optional[Dict] = None) -> Dict:
        """
        Execute a notification rule
        """
        try:
            rule = NotificationRule.objects.get(id=rule_id)
            
            if not rule.is_active or not rule.is_enabled:
                return {
                    'success': False,
                    'error': 'Rule is not active or enabled'
                }
            
            if not rule.can_execute():
                return {
                    'success': False,
                    'error': 'Rule cannot execute at this time'
                }
            
            # Evaluate conditions
            if context and not rule.evaluate_conditions(context):
                return {
                    'success': False,
                    'error': 'Conditions not met'
                }
            
            # Get target users
            users = self._get_rule_target_users(rule)
            
            if not users:
                return {
                    'success': False,
                    'error': 'No target users found'
                }
            
            # Execute action
            result = self._execute_rule_action(rule, users, context)
            
            # Update rule stats
            rule.trigger_count += 1
            rule.last_triggered = timezone.now()
            
            if result.get('success'):
                rule.success_count += 1
            else:
                rule.failure_count += 1
            
            rule.save()
            
            # Log execution
            NotificationLog.objects.create(
                log_type='info',
                message=f'Rule executed: {rule.name}',
                details={
                    'rule_id': str(rule.id),
                    'trigger_count': rule.trigger_count,
                    'users_targeted': len(users),
                    'result': result
                }
            )
            
            return result
            
        except NotificationRule.DoesNotExist:
            return {
                'success': False,
                'error': 'Rule not found'
            }
        except Exception as e:
            logger.error(f"Failed to execute rule {rule_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_rule_target_users(self, rule: NotificationRule):
        """
        Get target users for rule
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        target_type = rule.target_type
        target_config = rule.target_config
        
        if target_type == 'user':
            # Specific user
            user_id = target_config.get('user_id')
            if user_id:
                try:
                    return [User.objects.get(id=user_id)]
                except User.DoesNotExist:
                    return []
        
        elif target_type == 'user_group':
            # User group
            group_name = target_config.get('group_name')
            if group_name:
                return list(User.objects.filter(groups__name=group_name, is_active=True))
        
        elif target_type == 'all_users':
            # All active users
            return list(User.objects.filter(is_active=True))
        
        elif target_type == 'dynamic':
            # Dynamic query based on config
            queryset = User.objects.filter(is_active=True)
            
            # Apply filters
            filters = target_config.get('filters', {})
            
            # Add your filter logic here
            # This would depend on your user model structure
            
            return list(queryset)
        
        return []
    
    def _execute_rule_action(self, rule: NotificationRule, users, context: Optional[Dict] = None) -> Dict:
        """
        Execute rule action
        """
        action_type = rule.action_type
        action_config = rule.action_config
        
        if action_type == 'send_notification':
            # Send notification
            title = action_config.get('title', '')
            message = action_config.get('message', '')
            
            if not title or not message:
                return {
                    'success': False,
                    'error': 'Title and message are required'
                }
            
            # Render template variables if present
            if context:
                from .utils import TemplateRenderer
                renderer = TemplateRenderer()
                
                try:
                    title = renderer.render_string(title, context)
                    message = renderer.render_string(message, context)
                except Exception as e:
                    logger.error(f"Failed to render template strings: {e}")
            
            # Send notifications
            results = self.create_bulk_notifications(
                users=users,
                title=title,
                message=message,
                notification_type=action_config.get('notification_type', 'general'),
                priority=action_config.get('priority', 'medium'),
                channel=action_config.get('channel', 'in_app'),
                **{k: v for k, v in action_config.items() if k not in [
                    'title', 'message', 'notification_type', 'priority', 'channel'
                ]}
            )
            
            return {
                'success': results['successful'] > 0,
                'results': results
            }
        
        elif action_type == 'update_notification':
            # Update existing notifications
            # Implementation depends on your requirements
            pass
        
        elif action_type == 'delete_notification':
            # Delete notifications
            # Implementation depends on your requirements
            pass
        
        elif action_type == 'archive_notification':
            # Archive notifications
            # Implementation depends on your requirements
            pass
        
        elif action_type == 'send_email':
            # Send email
            # Implementation depends on your email system
            pass
        
        elif action_type == 'call_webhook':
            # Call webhook
            webhook_url = action_config.get('url')
            if webhook_url:
                try:
                    response = requests.post(
                        webhook_url,
                        json={
                            'rule_id': str(rule.id),
                            'rule_name': rule.name,
                            'users_count': len(users),
                            'context': context or {},
                            'timestamp': timezone.now().isoformat()
                        },
                        timeout=10
                    )
                    
                    return {
                        'success': response.status_code == 200,
                        'status_code': response.status_code,
                        'response': response.text[:500]  # Limit response size
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': str(e)
                    }
        
        return {
            'success': False,
            'error': f'Unsupported action type: {action_type}'
        }
    
    # ==================== ANALYTICS & REPORTING ====================
    
    def generate_analytics_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = 'day'
    ) -> Dict:
        """
        Generate analytics report
        """
        if start_date is None:
            start_date = timezone.now() - timedelta(days=30)
        if end_date is None:
            end_date = timezone.now()
        
        # Generate daily reports for the period
        current_date = start_date.date()
        end_date_date = end_date.date()
        
        reports = []
        
        while current_date <= end_date_date:
            report = NotificationAnalytics.generate_daily_report(current_date)
            if report:
                reports.append(report.get_summary())
            current_date += timedelta(days=1)
        
        # Calculate summary
        if reports:
            total_notifications = sum(r['total_notifications'] for r in reports)
            total_sent = sum(r['total_sent'] for r in reports)
            total_delivered = sum(r['total_delivered'] for r in reports)
            total_read = sum(r['total_read'] for r in reports)
            total_clicked = sum(r['total_clicked'] for r in reports)
            
            summary = {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                },
                'total_notifications': total_notifications,
                'total_sent': total_sent,
                'total_delivered': total_delivered,
                'total_read': total_read,
                'total_clicked': total_clicked,
                'average_delivery_rate': (
                    sum(r['delivery_rate'] for r in reports) / len(reports)
                    if reports else 0
                ),
                'average_open_rate': (
                    sum(r['open_rate'] for r in reports) / len(reports)
                    if reports else 0
                ),
                'average_click_through_rate': (
                    sum(r['click_through_rate'] for r in reports) / len(reports)
                    if reports else 0
                ),
                'total_active_users': sum(r['active_users'] for r in reports),
                'total_engaged_users': sum(r['engaged_users'] for r in reports),
                'total_cost': sum(r['total_cost'] for r in reports),
            }
        else:
            summary = {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                },
                'message': 'No data available for this period'
            }
        
        return {
            'summary': summary,
            'daily_reports': reports,
            'group_by': group_by,
        }
    
    def get_user_engagement_report(self, user) -> Dict:
        """
        Get user engagement report
        """
        # Get user notifications
        notifications = Notification.objects.filter(
            user=user,
            is_deleted=False,
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        
        # Calculate engagement metrics
        total_notifications = notifications.count()
        read_notifications = notifications.filter(is_read=True).count()
        clicked_notifications = notifications.filter(click_count__gt=0).count()
        
        # Calculate average time to read
        read_times = []
        for notification in notifications.filter(is_read=True, sent_at__isnull=False):
            if notification.read_at and notification.sent_at:
                read_time = (notification.read_at - notification.sent_at).total_seconds()
                read_times.append(read_time)
        
        avg_read_time = sum(read_times) / len(read_times) if read_times else 0
        
        # Calculate most engaged notification types
        type_engagement = notifications.values('notification_type').annotate(
            total=Count('id'),
            read=Count('id', filter=Q(is_read=True)),
            clicked=Sum('click_count'),
            avg_read_time=Avg(
                Case(
                    When(is_read=True, sent_at__isnull=False, read_at__isnull=False,
                         then=F('read_at') - F('sent_at')),
                    output_field=models.DurationField()
                )
            )
        ).order_by('-read')
        
        return {
            'user_id': user.id,
            'username': user.username,
            'period_days': 30,
            'total_notifications': total_notifications,
            'read_notifications': read_notifications,
            'clicked_notifications': clicked_notifications,
            'read_rate': (read_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'click_rate': (clicked_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'average_read_time_seconds': avg_read_time,
            'type_engagement': list(type_engagement),
            'preferences': self.get_user_preferences(user).get_stats() if self.get_user_preferences(user) else {},
        }
    
    # ==================== TESTING & DEBUGGING ====================
    
    def send_test_notification(self, user, channel: str = 'in_app') -> Dict:
        """
        Send test notification to user
        """
        try:
            notification = self.create_notification(
                user=user,
                title='Test Notification',
                message='This is a test notification to verify that the notification system is working properly.',
                notification_type='system',
                priority='medium',
                channel=channel,
                metadata={'test': True, 'timestamp': timezone.now().isoformat()},
                tags=['test', 'debug'],
                check_duplicate=False
            )
            
            if notification:
                return {
                    'success': True,
                    'notification_id': str(notification.id),
                    'message': 'Test notification created successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to create test notification'
                }
                
        except Exception as e:
            logger.error(f"Failed to send test notification: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_notification_system(self) -> Dict:
        """
        Validate the notification system
        """
        checks = []
        
        # Check 1: Database connectivity
        try:
            Notification.objects.count()
            checks.append({
                'name': 'Database Connectivity',
                'status': 'pass',
                'message': 'Database connection successful'
            })
        except Exception as e:
            checks.append({
                'name': 'Database Connectivity',
                'status': 'fail',
                'message': f'Database connection failed: {str(e)}'
            })
        
        # Check 2: Cache connectivity
        try:
            cache.set('test_key', 'test_value', 1)
            cache.get('test_key')
            checks.append({
                'name': 'Cache Connectivity',
                'status': 'pass',
                'message': 'Cache connection successful'
            })
        except Exception as e:
            checks.append({
                'name': 'Cache Connectivity',
                'status': 'fail',
                'message': f'Cache connection failed: {str(e)}'
            })
        
        # Check 3: Template system
        try:
            # Create a test template
            template, created = NotificationTemplate.objects.get_or_create(
                name='_system_test_template',
                defaults={
                    'title_en': 'Test Title',
                    'message_en': 'Test Message',
                    'template_type': 'system',
                    'default_priority': 'low',
                    'default_channel': 'in_app',
                    'is_active': True,
                    'is_public': False,
                }
            )
            
            # Test rendering
            from .utils import TemplateRenderer
            renderer = TemplateRenderer()
            rendered = renderer.render_template(template, {})
            
            if rendered:
                checks.append({
                    'name': 'Template System',
                    'status': 'pass',
                    'message': 'Template system working correctly'
                })
            else:
                checks.append({
                    'name': 'Template System',
                    'status': 'fail',
                    'message': 'Template rendering failed'
                })
            
            # Cleanup
            if created:
                template.delete()
                
        except Exception as e:
            checks.append({
                'name': 'Template System',
                'status': 'fail',
                'message': f'Template system check failed: {str(e)}'
            })
        
        # Check 4: Service providers
        provider_checks = []
        
        # Check Firebase
        try:
            if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
                provider_checks.append({
                    'provider': 'Firebase',
                    'status': 'ready',
                    'message': 'Firebase initialized'
                })
            else:
                provider_checks.append({
                    'provider': 'Firebase',
                    'status': 'not_configured',
                    'message': 'Firebase not configured'
                })
        except:
            provider_checks.append({
                'provider': 'Firebase',
                'status': 'error',
                'message': 'Firebase check failed'
            })
        
        # Check SendGrid
        if self.sendgrid_client:
            provider_checks.append({
                'provider': 'SendGrid',
                'status': 'ready',
                'message': 'SendGrid initialized'
            })
        else:
            provider_checks.append({
                'provider': 'SendGrid',
                'status': 'not_configured',
                'message': 'SendGrid not configured'
            })
        
        # Check Twilio
        if self.twilio_client:
            provider_checks.append({
                'provider': 'Twilio',
                'status': 'ready',
                'message': 'Twilio initialized'
            })
        else:
            provider_checks.append({
                'provider': 'Twilio',
                'status': 'not_configured',
                'message': 'Twilio not configured'
            })
        
        checks.append({
            'name': 'Service Providers',
            'status': 'partial' if any(p['status'] == 'ready' for p in provider_checks) else 'fail',
            'message': 'Service provider status',
            'details': provider_checks
        })
        
        # Calculate overall status
        overall_status = 'pass'
        if any(check['status'] == 'fail' for check in checks):
            overall_status = 'fail'
        elif any(check['status'] == 'partial' for check in checks):
            overall_status = 'partial'
        
        return {
            'timestamp': timezone.now().isoformat(),
            'overall_status': overall_status,
            'checks': checks
        }


class NotificationTemplateService:
    """
    Service for template operations
    """
    
    @staticmethod
    def create_template(
        name: str,
        title_en: str,
        message_en: str,
        template_type: str = 'general',
        created_by=None,
        **kwargs
    ) -> Optional[NotificationTemplate]:
        """
        Create a notification template
        """
        try:
            template = NotificationTemplate.objects.create(
                name=name,
                title_en=title_en,
                message_en=message_en,
                title_bn=kwargs.get('title_bn', ''),
                message_bn=kwargs.get('message_bn', ''),
                template_type=template_type,
                description=kwargs.get('description', ''),
                default_priority=kwargs.get('default_priority', 'medium'),
                default_channel=kwargs.get('default_channel', 'in_app'),
                default_language=kwargs.get('default_language', 'en'),
                variables=kwargs.get('variables', []),
                sample_data=kwargs.get('sample_data', {}),
                icon_url=kwargs.get('icon_url'),
                image_url=kwargs.get('image_url'),
                action_url_template=kwargs.get('action_url_template', ''),
                action_text_en=kwargs.get('action_text_en', ''),
                action_text_bn=kwargs.get('action_text_bn', ''),
                deep_link_template=kwargs.get('deep_link_template', ''),
                metadata_template=kwargs.get('metadata_template', {}),
                category=kwargs.get('category', 'general'),
                tags=kwargs.get('tags', []),
                is_active=kwargs.get('is_active', True),
                is_public=kwargs.get('is_public', False),
                allowed_groups=kwargs.get('allowed_groups', []),
                allowed_roles=kwargs.get('allowed_roles', []),
                created_by=created_by,
            )
            
            # Clear template cache
            cache_key = NotificationService.TEMPLATE_CACHE_KEY.format(name)
            cache.delete(cache_key)
            
            # Log creation
            NotificationLog.objects.create(
                log_type='info',
                message=f'Template created: {name}',
                details={
                    'template_id': str(template.id),
                    'type': template_type,
                    'created_by': str(created_by.id) if created_by else 'system'
                }
            )
            
            return template
            
        except Exception as e:
            logger.error(f"Failed to create template: {e}", exc_info=True)
            return None
    
    @staticmethod
    def update_template(
        template_id: str,
        updated_by=None,
        **kwargs
    ) -> Optional[NotificationTemplate]:
        """
        Update a notification template
        """
        try:
            template = NotificationTemplate.objects.get(id=template_id)
            
            # Update fields
            updatable_fields = [
                'title_en', 'title_bn', 'message_en', 'message_bn',
                'description', 'default_priority', 'default_channel',
                'default_language', 'variables', 'sample_data',
                'icon_url', 'image_url', 'action_url_template',
                'action_text_en', 'action_text_bn', 'deep_link_template',
                'metadata_template', 'category', 'tags', 'is_active',
                'is_public', 'allowed_groups', 'allowed_roles'
            ]
            
            for field in updatable_fields:
                if field in kwargs:
                    setattr(template, field, kwargs[field])
            
            # Increment version
            template.version += 1
            template.updated_by = updated_by
            template.save()
            
            # Clear template cache
            cache_key = NotificationService.TEMPLATE_CACHE_KEY.format(template.name)
            cache.delete(cache_key)
            
            # Log update
            NotificationLog.objects.create(
                log_type='info',
                message=f'Template updated: {template.name} (v{template.version})',
                details={
                    'template_id': str(template.id),
                    'updated_by': str(updated_by.id) if updated_by else 'system',
                    'updated_fields': list(kwargs.keys())
                }
            )
            
            return template
            
        except NotificationTemplate.DoesNotExist:
            logger.error(f"Template not found: {template_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to update template: {e}", exc_info=True)
            return None
    
    @staticmethod
    def delete_template(template_id: str, deleted_by=None) -> bool:
        """
        Delete a notification template
        """
        try:
            template = NotificationTemplate.objects.get(id=template_id)
            template_name = template.name
            
            # Soft delete by deactivating
            template.is_active = False
            template.save()
            
            # Clear template cache
            cache_key = NotificationService.TEMPLATE_CACHE_KEY.format(template_name)
            cache.delete(cache_key)
            
            # Log deletion
            NotificationLog.objects.create(
                log_type='info',
                message=f'Template deleted: {template_name}',
                details={
                    'template_id': str(template.id),
                    'deleted_by': str(deleted_by.id) if deleted_by else 'system'
                }
            )
            
            return True
            
        except NotificationTemplate.DoesNotExist:
            logger.error(f"Template not found: {template_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete template: {e}", exc_info=True)
            return False
    
    @staticmethod
    def get_templates(
        filters: Optional[Dict] = None,
        page: int = 1,
        per_page: int = 20,
        order_by: str = 'name'
    ) -> Dict:
        """
        Get templates with pagination
        """
        if filters is None:
            filters = {}
        
        queryset = NotificationTemplate.objects.filter(is_active=True)
        
        # Apply filters
        if filters.get('template_type'):
            queryset = queryset.filter(template_type=filters['template_type'])
        
        if filters.get('category'):
            queryset = queryset.filter(category=filters['category'])
        
        if filters.get('is_public') is not None:
            queryset = queryset.filter(is_public=filters['is_public'])
        
        if filters.get('search'):
            search_term = filters['search']
            queryset = queryset.filter(
                Q(name__icontains=search_term) |
                Q(description__icontains=search_term) |
                Q(title_en__icontains=search_term) |
                Q(title_bn__icontains=search_term)
            )
        
        # Calculate pagination
        total = queryset.count()
        total_pages = (total + per_page - 1) // per_page
        
        # Apply ordering and pagination
        queryset = queryset.order_by(order_by)
        start = (page - 1) * per_page
        end = start + per_page
        templates = list(queryset[start:end])
        
        return {
            'templates': templates,
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
        }
    
    @staticmethod
    def render_template(
        template: NotificationTemplate,
        context: Dict,
        language: str = 'en'
    ) -> Dict:
        """
        Render template with context
        """
        try:
            from .utils import TemplateRenderer
            renderer = TemplateRenderer()
            
            rendered = renderer.render_template(template, context, language)
            
            if not rendered:
                raise ValueError("Template rendering failed")
            
            return rendered
            
        except Exception as e:
            logger.error(f"Failed to render template: {e}", exc_info=True)
            raise
    
    @staticmethod
    def validate_template_variables(
        template: NotificationTemplate,
        context: Dict
    ) -> List[str]:
        """
        Validate template variables in context
        """
        errors = []
        
        for variable in template.variables:
            var_name = variable.get('name')
            required = variable.get('required', False)
            
            if required and var_name not in context:
                errors.append(f"Required variable '{var_name}' not found in context")
            
            # Type validation
            if var_name in context:
                expected_type = variable.get('type', 'string')
                value = context[var_name]
                
                try:
                    if expected_type == 'number' and not isinstance(value, (int, float)):
                        errors.append(f"Variable '{var_name}' should be a number")
                    elif expected_type == 'boolean' and not isinstance(value, bool):
                        errors.append(f"Variable '{var_name}' should be a boolean")
                    elif expected_type == 'array' and not isinstance(value, list):
                        errors.append(f"Variable '{var_name}' should be an array")
                    elif expected_type == 'object' and not isinstance(value, dict):
                        errors.append(f"Variable '{var_name}' should be an object")
                except:
                    errors.append(f"Type validation failed for variable '{var_name}'")
        
        return errors


class NotificationRuleService:
    """
    Service for rule operations
    """
    
    @staticmethod
    def execute_rule(rule: NotificationRule, context: Optional[Dict] = None) -> bool:
        """
        Execute a notification rule
        """
        service = NotificationService()
        return service.execute_rule(str(rule.id), context)
    
    @staticmethod
    def evaluate_conditions(conditions: List[Dict], context: Dict) -> bool:
        """
        Evaluate rule conditions
        """
        if not conditions:
            return True
        
        for condition in conditions:
            if not NotificationRuleService._evaluate_condition(condition, context):
                return False
        
        return True
    
    @staticmethod
    def _evaluate_condition(condition: Dict, context: Dict) -> bool:
        """
        Evaluate a single condition
        """
        condition_type = condition.get('type', 'equals')
        field = condition.get('field')
        value = condition.get('value')
        
        if field not in context:
            return False
        
        field_value = context[field]
        
        if condition_type == 'equals':
            return field_value == value
        elif condition_type == 'not_equals':
            return field_value != value
        elif condition_type == 'contains':
            return value in field_value if isinstance(field_value, str) else False
        elif condition_type == 'not_contains':
            return value not in field_value if isinstance(field_value, str) else False
        elif condition_type == 'greater_than':
            return field_value > value
        elif condition_type == 'less_than':
            return field_value < value
        elif condition_type == 'greater_than_or_equal':
            return field_value >= value
        elif condition_type == 'less_than_or_equal':
            return field_value <= value
        elif condition_type == 'in':
            return field_value in value if isinstance(value, list) else False
        elif condition_type == 'not_in':
            return field_value not in value if isinstance(value, list) else False
        elif condition_type == 'exists':
            return field is not None
        elif condition_type == 'not_exists':
            return field is None
        elif condition_type == 'regex':
            import re
            return bool(re.match(value, str(field_value)))
        
        return False
    
    @staticmethod
    def get_target_users(rule: NotificationRule):
        """
        Get target users for rule
        """
        service = NotificationService()
        return service._get_rule_target_users(rule)
    
    @staticmethod
    def test_rule(rule: NotificationRule, test_context: Optional[Dict] = None) -> Dict:
        """
        Test rule execution
        """
        try:
            # Check if rule can execute
            if not rule.can_execute():
                return {
                    'success': False,
                    'error': 'Rule cannot execute at this time',
                    'can_execute': False
                }
            
            # Evaluate conditions
            if test_context:
                conditions_met = NotificationRuleService.evaluate_conditions(
                    rule.conditions,
                    test_context
                )
            else:
                conditions_met = True
            
            # Get target users (without actually executing)
            target_users = NotificationRuleService.get_target_users(rule)
            
            # Simulate action
            action_details = {
                'type': rule.action_type,
                'config': rule.action_config,
                'estimated_users': len(target_users),
                'conditions_met': conditions_met,
            }
            
            return {
                'success': True,
                'can_execute': True,
                'conditions_met': conditions_met,
                'target_users_count': len(target_users),
                'action_details': action_details,
                'test_context': test_context or {},
            }
            
        except Exception as e:
            logger.error(f"Failed to test rule: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'can_execute': False
            }


class NotificationAnalyticsService:
    """
    Service for analytics operations
    """
    
    @staticmethod
    def generate_daily_report(date=None) -> Optional[NotificationAnalytics]:
        """
        Generate daily analytics report
        """
        return NotificationAnalytics.generate_daily_report(date)
    
    @staticmethod
    def get_performance_metrics(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get performance metrics for period
        """
        if start_date is None:
            start_date = timezone.now() - timedelta(days=7)
        if end_date is None:
            end_date = timezone.now()
        
        # Get notifications for period
        notifications = Notification.objects.filter(
            created_at__range=[start_date, end_date],
            is_deleted=False
        )
        
        # Calculate metrics
        total = notifications.count()
        sent = notifications.filter(is_sent=True).count()
        delivered = notifications.filter(is_delivered=True).count()
        read = notifications.filter(is_read=True).count()
        clicked = notifications.aggregate(total=Sum('click_count'))['total'] or 0
        
        # Calculate rates
        delivery_rate = (delivered / sent * 100) if sent > 0 else 0
        open_rate = (read / sent * 100) if sent > 0 else 0
        click_through_rate = (clicked / sent * 100) if sent > 0 else 0
        
        # Calculate by channel
        by_channel = notifications.values('channel').annotate(
            count=Count('id'),
            delivered=Count('id', filter=Q(is_delivered=True)),
            read=Count('id', filter=Q(is_read=True)),
            clicks=Sum('click_count')
        ).order_by('-count')
        
        # Calculate by type
        by_type = notifications.values('notification_type').annotate(
            count=Count('id'),
            read_rate=Avg(
                Case(
                    When(is_read=True, then=Value(100)),
                    default=Value(0),
                    output_field=models.FloatField()
                )
            ),
            click_rate=Avg(
                Case(
                    When(click_count__gt=0, then=Value(100)),
                    default=Value(0),
                    output_field=models.FloatField()
                )
            )
        ).order_by('-count')
        
        # Calculate cost
        cost_data = notifications.aggregate(
            total=Sum('cost'),
            average=Avg('cost')
        )
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'metrics': {
                'total_notifications': total,
                'sent': sent,
                'delivered': delivered,
                'read': read,
                'clicked': clicked,
                'delivery_rate': round(delivery_rate, 2),
                'open_rate': round(open_rate, 2),
                'click_through_rate': round(click_through_rate, 2),
                'total_cost': float(cost_data['total'] or 0),
                'average_cost': float(cost_data['average'] or 0),
            },
            'by_channel': list(by_channel),
            'by_type': list(by_type),
        }
    
    @staticmethod
    def get_user_engagement_report(user_id: str) -> Dict:
        """
        Get user engagement report
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.get(id=user_id)
            service = NotificationService()
            return service.get_user_engagement_report(user)
        except User.DoesNotExist:
            return {
                'error': 'User not found',
                'user_id': user_id
            }
        except Exception as e:
            logger.error(f"Failed to get user engagement report: {e}")
            return {
                'error': str(e),
                'user_id': user_id
            }
    
    @staticmethod
    def get_campaign_performance(campaign_id: str) -> Dict:
        """
        Get campaign performance report
        """
        try:
            campaign = NotificationCampaign.objects.get(id=campaign_id)
            
            # Get campaign notifications
            notifications = Notification.objects.filter(campaign_id=campaign_id)
            
            # Calculate additional metrics
            total_cost = notifications.aggregate(total=Sum('cost'))['total'] or 0
            average_engagement = notifications.aggregate(avg=Avg('engagement_score'))['avg'] or 0
            
            # Get timeline data
            timeline = notifications.extra({
                'date': "DATE(created_at)"
            }).values('date').annotate(
                sent=Count('id'),
                delivered=Count('id', filter=Q(is_delivered=True)),
                read=Count('id', filter=Q(is_read=True)),
                clicks=Sum('click_count')
            ).order_by('date')
            
            return {
                'campaign': campaign.get_performance_summary(),
                'additional_metrics': {
                    'total_cost': float(total_cost),
                    'average_engagement_score': round(average_engagement, 2),
                    'cost_per_delivery': float(total_cost / campaign.total_delivered) if campaign.total_delivered > 0 else 0,
                    'cost_per_read': float(total_cost / campaign.total_read) if campaign.total_read > 0 else 0,
                    'cost_per_click': float(total_cost / campaign.total_clicked) if campaign.total_clicked > 0 else 0,
                },
                'timeline': list(timeline),
                'notifications_count': notifications.count(),
            }
            
        except NotificationCampaign.DoesNotExist:
            return {
                'error': 'Campaign not found',
                'campaign_id': campaign_id
            }
        except Exception as e:
            logger.error(f"Failed to get campaign performance: {e}")
            return {
                'error': str(e),
                'campaign_id': campaign_id
            }


class NotificationPreferencesService:
    """
    Service for preferences operations
    """
    
    @staticmethod
    def update_preferences(
        user,
        updates: Dict,
        updated_by=None
    ) -> Optional[NotificationPreference]:
        """
        Update user notification preferences
        """
        try:
            preferences = NotificationPreference.objects.get(user=user)
            
            # Update fields
            updatable_fields = [
                'enable_in_app', 'enable_push', 'enable_email', 'enable_sms',
                'enable_telegram', 'enable_whatsapp', 'enable_browser',
                'enable_system_notifications', 'enable_financial_notifications',
                'enable_task_notifications', 'enable_security_notifications',
                'enable_marketing_notifications', 'enable_social_notifications',
                'enable_support_notifications', 'enable_achievement_notifications',
                'enable_gamification_notifications',
                'enable_lowest_priority', 'enable_low_priority',
                'enable_medium_priority', 'enable_high_priority',
                'enable_urgent_priority', 'enable_critical_priority',
                'sound_enabled', 'vibration_enabled', 'led_enabled', 'badge_enabled',
                'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
                'do_not_disturb', 'do_not_disturb_until',
                'preferred_language', 'prefer_in_app', 'group_notifications',
                'show_previews', 'auto_delete_read', 'auto_delete_after_days',
                'max_notifications_per_day', 'max_push_per_day',
                'max_email_per_day', 'max_sms_per_day',
            ]
            
            for field in updatable_fields:
                if field in updates:
                    setattr(preferences, field, updates[field])
            
            preferences.save()
            
            # Clear cache
            cache_key = NotificationService.USER_PREFS_CACHE_KEY.format(user.id)
            cache.delete(cache_key)
            
            # Log update
            NotificationLog.objects.create(
                user=user,
                log_type='info',
                message='Notification preferences updated',
                details={
                    'updated_by': str(updated_by.id) if updated_by else 'user',
                    'updated_fields': list(updates.keys())
                }
            )
            
            return preferences
            
        except NotificationPreference.DoesNotExist:
            logger.error(f"Preferences not found for user {user.id}")
            return None
        except Exception as e:
            logger.error(f"Failed to update preferences: {e}", exc_info=True)
            return None
    
    @staticmethod
    def export_preferences(user) -> Dict:
        """
        Export user preferences as JSON
        """
        try:
            preferences = NotificationPreference.objects.get(user=user)
            
            # Convert to dict
            data = {}
            for field in preferences._meta.fields:
                if field.name not in ['id', 'user', 'created_at', 'updated_at']:
                    value = getattr(preferences, field.name)
                    # Convert datetime to string
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    data[field.name] = value
            
            return {
                'success': True,
                'user_id': user.id,
                'username': user.username,
                'export_date': timezone.now().isoformat(),
                'preferences': data
            }
            
        except NotificationPreference.DoesNotExist:
            return {
                'success': False,
                'error': 'Preferences not found'
            }
        except Exception as e:
            logger.error(f"Failed to export preferences: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def import_preferences(user, data: Dict) -> bool:
        """
        Import user preferences from JSON
        """
        try:
            preferences, created = NotificationPreference.objects.get_or_create(user=user)
            
            # Update fields from data
            for key, value in data.items():
                if hasattr(preferences, key):
                    # Convert string to datetime if needed
                    field = preferences._meta.get_field(key)
                    if isinstance(field, models.DateTimeField) and isinstance(value, str):
                        try:
                            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        except:
                            value = timezone.now()
                    
                    setattr(preferences, key, value)
            
            preferences.save()
            
            # Clear cache
            cache_key = NotificationService.USER_PREFS_CACHE_KEY.format(user.id)
            cache.delete(cache_key)
            
            # Log import
            NotificationLog.objects.create(
                user=user,
                log_type='info',
                message='Notification preferences imported',
                details={
                    'imported_fields': list(data.keys())
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to import preferences: {e}")
            return False
    
    @staticmethod
    def reset_to_defaults(user) -> bool:
        """
        Reset user preferences to defaults
        """
        try:
            preferences, created = NotificationPreference.objects.get_or_create(user=user)
            
            # Create new preferences with defaults
            default_preferences = NotificationPreference(user=user)
            
            # Copy default values
            for field in preferences._meta.fields:
                if field.name not in ['id', 'user', 'created_at', 'updated_at',
                                     'total_notifications_received', 'total_notifications_read',
                                     'total_notifications_clicked', 'average_open_time',
                                     'average_click_time']:
                    setattr(preferences, field.name, getattr(default_preferences, field.name))
            
            preferences.save()
            
            # Clear cache
            cache_key = NotificationService.USER_PREFS_CACHE_KEY.format(user.id)
            cache.delete(cache_key)
            
            # Log reset
            NotificationLog.objects.create(
                user=user,
                log_type='info',
                message='Notification preferences reset to defaults'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset preferences: {e}")
            return False


class NotificationDeviceService:
    """
    Service for device token operations
    """
    
    @staticmethod
    def register_device(
        user,
        token: str,
        device_type: str,
        platform: str,
        **kwargs
    ) -> Optional[DeviceToken]:
        """
        Register a device token for push notifications
        """
        try:
            # Check if token already exists
            existing = DeviceToken.objects.filter(token=token).first()
            if existing:
                # Update existing token
                existing.user = user
                existing.device_type = device_type
                existing.platform = platform
                existing.app_version = kwargs.get('app_version', '')
                existing.os_version = kwargs.get('os_version', '')
                existing.device_model = kwargs.get('device_model', '')
                existing.device_name = kwargs.get('device_name', '')
                existing.manufacturer = kwargs.get('manufacturer', '')
                existing.is_active = True
                existing.push_enabled = kwargs.get('push_enabled', True)
                existing.save()
                
                # Clear cache
                cache_key = NotificationService.DEVICE_TOKENS_CACHE_KEY.format(user.id)
                cache.delete(cache_key)
                
                return existing
            
            # Create new device token
            device_token = DeviceToken.objects.create(
                user=user,
                token=token,
                device_type=device_type,
                platform=platform,
                app_version=kwargs.get('app_version', ''),
                os_version=kwargs.get('os_version', ''),
                device_model=kwargs.get('device_model', ''),
                device_name=kwargs.get('device_name', ''),
                manufacturer=kwargs.get('manufacturer', ''),
                fcm_token=kwargs.get('fcm_token', ''),
                apns_token=kwargs.get('apns_token', ''),
                web_push_token=kwargs.get('web_push_token', {}),
                ip_address=kwargs.get('ip_address'),
                country=kwargs.get('country', ''),
                city=kwargs.get('city', ''),
                timezone=kwargs.get('timezone', ''),
                language=kwargs.get('language', 'en'),
                push_enabled=kwargs.get('push_enabled', True),
                sound_enabled=kwargs.get('sound_enabled', True),
                vibration_enabled=kwargs.get('vibration_enabled', True),
            )
            
            # Clear cache
            cache_key = NotificationService.DEVICE_TOKENS_CACHE_KEY.format(user.id)
            cache.delete(cache_key)
            
            # Log registration
            NotificationLog.objects.create(
                user=user,
                log_type='info',
                message=f'Device registered: {device_type} ({platform})',
                details={
                    'device_id': str(device_token.id),
                    'device_type': device_type,
                    'platform': platform,
                }
            )
            
            return device_token
            
        except Exception as e:
            logger.error(f"Failed to register device: {e}", exc_info=True)
            return None
    
    @staticmethod
    def unregister_device(token: str) -> bool:
        """
        Unregister a device token
        """
        try:
            device_token = DeviceToken.objects.get(token=token)
            user_id = device_token.user_id
            
            # Deactivate token
            device_token.is_active = False
            device_token.save()
            
            # Clear cache
            cache_key = NotificationService.DEVICE_TOKENS_CACHE_KEY.format(user_id)
            cache.delete(cache_key)
            
            # Log unregistration
            NotificationLog.objects.create(
                user=device_token.user,
                log_type='info',
                message=f'Device unregistered: {device_token.device_type}',
                details={
                    'device_id': str(device_token.id),
                    'device_type': device_token.device_type,
                    'platform': device_token.platform,
                }
            )
            
            return True
            
        except DeviceToken.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Failed to unregister device: {e}")
            return False
    
    @staticmethod
    def get_user_devices(user, active_only: bool = True) -> List[DeviceToken]:
        """
        Get user's devices
        """
        service = NotificationService()
        return service.get_user_device_tokens(user, active_only)
    
    @staticmethod
    def update_device_settings(
        token: str,
        updates: Dict
    ) -> Optional[DeviceToken]:
        """
        Update device settings
        """
        try:
            device_token = DeviceToken.objects.get(token=token)
            
            # Update fields
            updatable_fields = [
                'push_enabled', 'sound_enabled', 'vibration_enabled',
                'app_version', 'os_version', 'device_name', 'language'
            ]
            
            for field in updatable_fields:
                if field in updates:
                    setattr(device_token, field, updates[field])
            
            device_token.save()
            
            # Clear cache
            cache_key = NotificationService.DEVICE_TOKENS_CACHE_KEY.format(device_token.user_id)
            cache.delete(cache_key)
            
            return device_token
            
        except DeviceToken.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Failed to update device settings: {e}")
            return None


class NotificationFeedbackService:
    """
    Service for feedback operations
    """
    
    @staticmethod
    def submit_feedback(
        notification_id: str,
        user,
        rating: Optional[int] = None,
        feedback: str = '',
        feedback_type: str = 'neutral',
        **kwargs
    ) -> Optional[NotificationFeedback]:
        """
        Submit feedback for a notification
        """
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            
            # Check if feedback already exists
            existing_feedback = NotificationFeedback.objects.filter(
                notification=notification,
                user=user
            ).first()
            
            if existing_feedback:
                # Update existing feedback
                if rating is not None:
                    existing_feedback.rating = rating
                existing_feedback.feedback = feedback
                existing_feedback.feedback_type = feedback_type
                existing_feedback.is_helpful = kwargs.get('is_helpful')
                existing_feedback.would_like_more = kwargs.get('would_like_more')
                existing_feedback.metadata.update(kwargs.get('metadata', {}))
                existing_feedback.save()
                return existing_feedback
            
            # Create new feedback
            feedback_obj = NotificationFeedback.objects.create(
                notification=notification,
                user=user,
                rating=rating,
                feedback=feedback,
                feedback_type=feedback_type,
                is_helpful=kwargs.get('is_helpful'),
                would_like_more=kwargs.get('would_like_more'),
                metadata=kwargs.get('metadata', {})
            )
            
            # Update notification engagement score
            notification.calculate_engagement_score()
            notification.save()
            
            # Log feedback
            NotificationLog.objects.create(
                notification=notification,
                user=user,
                log_type='info',
                message='Feedback submitted for notification',
                details={
                    'feedback_id': str(feedback_obj.id),
                    'rating': rating,
                    'feedback_type': feedback_type,
                }
            )
            
            return feedback_obj
            
        except Notification.DoesNotExist:
            logger.error(f"Notification not found: {notification_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}", exc_info=True)
            return None
    
    @staticmethod
    def get_notification_feedback(
        notification_id: str,
        page: int = 1,
        per_page: int = 20
    ) -> Dict:
        """
        Get feedback for a notification
        """
        try:
            notification = Notification.objects.get(id=notification_id)
            
            queryset = NotificationFeedback.objects.filter(
                notification=notification
            ).order_by('-created_at')
            
            # Calculate pagination
            total = queryset.count()
            total_pages = (total + per_page - 1) // per_page
            
            # Apply pagination
            start = (page - 1) * per_page
            end = start + per_page
            feedbacks = list(queryset[start:end])
            
            # Calculate summary
            ratings = [f.rating for f in feedbacks if f.rating is not None]
            average_rating = sum(ratings) / len(ratings) if ratings else 0
            
            feedback_types = {}
            for feedback in feedbacks:
                ftype = feedback.feedback_type
                feedback_types[ftype] = feedback_types.get(ftype, 0) + 1
            
            return {
                'notification_id': str(notification_id),
                'notification_title': notification.title,
                'feedbacks': feedbacks,
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
                'summary': {
                    'average_rating': round(average_rating, 2),
                    'total_feedbacks': total,
                    'feedback_types': feedback_types,
                    'helpful_count': sum(1 for f in feedbacks if f.is_helpful),
                    'would_like_more_count': sum(1 for f in feedbacks if f.would_like_more),
                }
            }
            
        except Notification.DoesNotExist:
            return {
                'error': 'Notification not found',
                'notification_id': notification_id
            }
        except Exception as e:
            logger.error(f"Failed to get notification feedback: {e}")
            return {
                'error': str(e),
                'notification_id': notification_id
            }
    
    @staticmethod
    def get_user_feedback(
        user,
        page: int = 1,
        per_page: int = 20
    ) -> Dict:
        """
        Get feedback submitted by user
        """
        queryset = NotificationFeedback.objects.filter(
            user=user
        ).order_by('-created_at')
        
        # Calculate pagination
        total = queryset.count()
        total_pages = (total + per_page - 1) // per_page
        
        # Apply pagination
        start = (page - 1) * per_page
        end = start + per_page
        feedbacks = list(queryset[start:end])
        
        return {
            'user_id': user.id,
            'username': user.username,
            'feedbacks': feedbacks,
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
        }


# Global service instance
notification_service = NotificationService()
template_service = NotificationTemplateService()
rule_service = NotificationRuleService()
analytics_service = NotificationAnalyticsService()
preferences_service = NotificationPreferencesService()
device_service = NotificationDeviceService()
feedback_service = NotificationFeedbackService()