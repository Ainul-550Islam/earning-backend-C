"""
Signals for Advertiser Portal

This module contains Django signal handlers for responding to
model events and other system events throughout the application.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.db.models.signals import m2m_changed
from django.dispatch import receiver, Signal
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import *
from .database_models.advertiser_model import Advertiser
from .database_models.campaign_model import Campaign
from .database_models.creative_model import Creative
from .database_models.billing_model import Invoice, PaymentMethod, PaymentTransaction, BillingProfile
from .services import *
from .utils import *
from .cache import *
from .tasks import *
from .constants import *
from .enums import *


logger = logging.getLogger(__name__)

# Custom signals
campaign_status_changed = Signal()
creative_approval_completed = Signal()
budget_threshold_reached = Signal()
fraud_activity_detected = Signal()
payment_processed = Signal()


@receiver(pre_save, sender=Advertiser)
def advertiser_pre_save(sender, instance, **kwargs):
    """Handle advertiser pre-save operations."""
    # Generate API key if not set
    if not instance.api_key:
        from .services import AdvertiserService
        advertiser_service = AdvertiserService()
        instance.api_key = advertiser_service.generate_api_key()
    
    # Set verification date if verified
    if instance.is_verified and not instance.verification_date:
        instance.verification_date = timezone.now()


@receiver(post_save, sender=Advertiser)
def advertiser_post_save(sender, instance, created, **kwargs):
    """Handle advertiser post-save operations."""
    if created:
        # Send welcome email
        try:
            send_mail(
                subject='Welcome to Advertiser Portal',
                message=f'''
                Dear {instance.company_name},
                
                Welcome to Advertiser Portal! Your account has been created successfully.
                
                API Key: {instance.api_key}
                
                Please complete your profile verification to start advertising.
                
                Best regards,
                Advertiser Portal Team
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.contact_email],
                fail_silently=True
            )
            logger.info(f"Welcome email sent to advertiser {instance.id}")
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
        
        # Create default billing profile
        try:
            BillingProfile.objects.create(
                advertiser=instance,
                company_name=instance.company_name,
                contact_email=instance.contact_email,
                created_by=instance.user
            )
            logger.info(f"Default billing profile created for advertiser {instance.id}")
        except Exception as e:
            logger.error(f"Failed to create billing profile: {str(e)}")
    
    # Invalidate cache
    # invalidate_advertiser_cache(instance.id)


@receiver(pre_save, sender=Campaign)
def campaign_pre_save(sender, instance, **kwargs):
    """Handle campaign pre-save operations."""
    # Check if status is changing
    if instance.pk:
        try:
            old_instance = Campaign.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
        except Campaign.DoesNotExist:
            pass


@receiver(post_save, sender=Campaign)
def campaign_post_save(sender, instance, created, **kwargs):
    """Handle campaign post-save operations."""
    # Handle status change
    if hasattr(instance, '_status_changed') and instance._status_changed:
        campaign_status_changed.send(
            sender=Campaign,
            campaign=instance,
            old_status=instance._old_status,
            new_status=instance.status
        )
        
        # Send status change notification
        try:
            status_messages = {
                'active': 'Your campaign has been activated and is now running.',
                'paused': 'Your campaign has been paused.',
                'completed': 'Your campaign has been completed.',
                'suspended': 'Your campaign has been suspended due to policy violations.'
            }
            
            message = status_messages.get(instance.status, f'Campaign status changed to {instance.status}')
            
            send_mail(
                subject=f'Campaign Status Update: {instance.name}',
                message=f'''
                Dear {instance.advertiser.company_name},
                
                {message}
                
                Campaign: {instance.name}
                Status: {instance.status}
                
                Best regards,
                Advertiser Portal Team
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.advertiser.contact_email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send campaign status notification: {str(e)}")
    
    # Invalidate cache
    invalidate_campaign_cache(instance.id)
    
    # Schedule optimization task for active campaigns
    if instance.status == StatusEnum.ACTIVE.value and not created:
        process_campaign_optimization.delay(str(instance.id))


@receiver(pre_save, sender=Creative)
def creative_pre_save(sender, instance, **kwargs):
    """Handle creative pre-save operations."""
    # Check if approval status is changing
    if instance.pk:
        try:
            old_instance = Creative.objects.get(pk=instance.pk)
            if old_instance.is_approved != instance.is_approved:
                instance._approval_changed = True
                instance._old_approval = old_instance.is_approved
        except Creative.DoesNotExist:
            pass


@receiver(post_save, sender=Creative)
def creative_post_save(sender, instance, created, **kwargs):
    """Handle creative post-save operations."""
    # Handle approval change
    if hasattr(instance, '_approval_changed') and instance._approval_changed:
        creative_approval_completed.send(
            sender=Creative,
            creative=instance,
            approved=instance.is_approved,
            old_approval=instance._old_approval
        )
        
        # Send approval notification
        try:
            if instance.is_approved:
                message = f'Your creative "{instance.name}" has been approved and is now active.'
            else:
                message = f'Your creative "{instance.name}" has been rejected. Please review our guidelines.'
            
            send_mail(
                subject=f'Creative Approval Update: {instance.name}',
                message=f'''
                Dear {instance.campaign.advertiser.company_name},
                
                {message}
                
                Creative: {instance.name}
                Campaign: {instance.campaign.name}
                Status: {"Approved" if instance.is_approved else "Rejected"}
                
                Best regards,
                Advertiser Portal Team
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.campaign.advertiser.contact_email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send creative approval notification: {str(e)}")
    
    # Invalidate cache
    invalidate_creative_cache(instance.id)


# @receiver(post_save, sender=BudgetLog)
def budget_log_post_save(sender, instance, created, **kwargs):
    """Handle budget log post-save operations."""
    if created:
        # Check budget thresholds
        campaign = instance.campaign
        utilization = campaign.budget_utilization
        
        # Send alerts at 80% and 100%
        if utilization >= 80 and utilization < 85:
            budget_threshold_reached.send(
            sender=BudgetLog,
            campaign=campaign,
            threshold=80,
            current_utilization=utilization
            )
        elif utilization >= 100:
            budget_threshold_reached.send(
            sender=BudgetLog,
            campaign=campaign,
            threshold=100,
            current_utilization=utilization
            )


@receiver(post_save, sender=PaymentTransaction)
def payment_transaction_post_save(sender, instance, created, **kwargs):
    """Handle payment transaction post-save operations."""
    if created and instance.status == 'completed':
        payment_processed.send(
            sender=PaymentTransaction,
            transaction=instance,
            advertiser=instance.advertiser
        )
        
        # Send payment confirmation
        try:
            send_mail(
                subject='Payment Confirmation',
                message=f'''
                Dear {instance.advertiser.company_name},
                
                Your payment has been processed successfully.
                
                Amount: ${instance.amount}
                Transaction ID: {instance.transaction_id}
                Date: {instance.created_at.strftime('%Y-%m-%d %H:%M:%S')}
                
                Your account balance has been updated.
                
                Best regards,
                Advertiser Portal Team
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.advertiser.contact_email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send payment confirmation: {str(e)}")
    
    # Invalidate billing cache
    # invalidate_advertiser_cache(instance.advertiser.id)


@receiver(post_save, sender=Invoice)
def invoice_post_save(sender, instance, created, **kwargs):
    """Handle invoice post-save operations."""
    if created:
        # Send invoice notification
        try:
            send_mail(
                subject=f'Invoice {instance.invoice_number}',
                message=f'''
                Dear {instance.advertiser.company_name},
                
                A new invoice has been generated for your account.
                
                Invoice Number: {instance.invoice_number}
                Issue Date: {instance.issue_date}
                Due Date: {instance.due_date}
                Total Amount: ${instance.total_amount}
                
                Please ensure payment is made by the due date to avoid service interruption.
                
                Best regards,
                Advertiser Portal Team
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.advertiser.contact_email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send invoice notification: {str(e)}")
    
    # Invalidate billing cache
    # invalidate_advertiser_cache(instance.advertiser.id)


# @receiver(post_save, sender=FraudLog)  # FraudLog model doesn't exist
def fraud_log_post_save(sender, instance, created, **kwargs):
    """Handle fraud log post-save operations."""
    if created:
        fraud_activity_detected.send(
            sender=FraudLog,
            fraud_log=instance,
            fraud_type=instance.fraud_type,
            risk_score=instance.risk_score
        )
        
        # Schedule fraud detection task if high risk
        if instance.risk_score >= 80:
            detect_fraud_activity.delay({
                'time_window': 1,
                'fraud_types': [instance.fraud_type],
                'auto_block': True
            })


@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """Handle user login events."""
    try:
        # Log login event
        AuditLog.objects.create(
            user=user,
            action=AuditActionEnum.LOGIN.value,
            details=f"User logged in from {request.META.get('REMOTE_ADDR', 'unknown')}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Invalidate user cache
        if hasattr(user, 'advertiser'):
            invalidate_user_cache(user.id)
        
        logger.info(f"User {user.username} logged in")
        
    except Exception as e:
        logger.error(f"Failed to handle user login: {str(e)}")


@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """Handle user logout events."""
    try:
        if user:
            # Log logout event
            AuditLog.objects.create(
                user=user,
                action=AuditActionEnum.LOGOUT.value,
                details="User logged out",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            logger.info(f"User {user.username} logged out")
        
    except Exception as e:
        logger.error(f"Failed to handle user logout: {str(e)}")


# @receiver(m2m_changed, sender=Campaign.targeting.through)
def campaign_targeting_changed(sender, instance, action, pk_set, **kwargs):
    """Handle campaign targeting changes."""
    if action in ['post_add', 'post_remove', 'post_clear']:
        # Invalidate campaign cache
        invalidate_campaign_cache(instance.id)
        
        # Schedule optimization if campaign is active
        if instance.status == StatusEnum.ACTIVE.value:
            process_campaign_optimization.delay(str(instance.id))


# Custom signal handlers
@receiver(campaign_status_changed)
def handle_campaign_status_changed(sender, campaign, old_status, new_status, **kwargs):
    """Handle campaign status change events."""
    logger.info(f"Campaign {campaign.id} status changed from {old_status} to {new_status}")
    
    # Update campaign performance tracking
    if new_status == StatusEnum.ACTIVE.value:
        campaign.start_tracking()
    elif new_status in [StatusEnum.PAUSED.value, StatusEnum.COMPLETED.value]:
        campaign.stop_tracking()
    
    # Record status change in audit log
    try:
        AuditLog.objects.create(
            user=getattr(campaign, 'modified_by', None),
            action=AuditActionEnum.UPDATE.value,
            details=f"Campaign status changed from {old_status} to {new_status}",
            content_object=campaign
        )
    except Exception as e:
        logger.error(f"Failed to log campaign status change: {str(e)}")


@receiver(creative_approval_completed)
def handle_creative_approval_completed(sender, creative, approved, old_approval, **kwargs):
    """Handle creative approval completion events."""
    logger.info(f"Creative {creative.id} approval changed from {old_approval} to {approved}")
    
    # Update campaign creative count
    campaign = creative.campaign
    if approved:
        campaign.approved_creatives_count += 1
    else:
        campaign.approved_creatives_count = max(0, campaign.approved_creatives_count - 1)
    campaign.save(update_fields=['approved_creatives_count'])
    
    # Record approval in audit log
    try:
        AuditLog.objects.create(
            user=getattr(creative, 'approved_by', None),
            action='approve' if approved else 'reject',
            details=f"Creative {'approved' if approved else 'rejected'}",
            content_object=creative
        )
    except Exception as e:
        logger.error(f"Failed to log creative approval: {str(e)}")


@receiver(budget_threshold_reached)
def handle_budget_threshold_reached(sender, campaign, threshold, current_utilization, **kwargs):
    """Handle budget threshold reached events."""
    logger.info(f"Campaign {campaign.id} reached {threshold}% budget utilization")
    
    # Send budget alert
    send_budget_alerts.delay({
        'types': ['low_budget'] if threshold < 100 else ['exhausted'],
        'advertiser_ids': [str(campaign.advertiser.id)],
        'threshold_percent': threshold
    })
    
    # Auto-pause campaign if budget exhausted
    if threshold >= 100 and campaign.auto_pause_on_budget_exhaust:
        campaign.status = StatusEnum.PAUSED.value
        campaign.save(update_fields=['status'])
        
        logger.info(f"Campaign {campaign.id} auto-paused due to budget exhaustion")


@receiver(fraud_activity_detected)
def handle_fraud_activity_detected(sender, fraud_log, fraud_type, risk_score, **kwargs):
    """Handle fraud activity detection events."""
    logger.warning(f"Fraud activity detected: {fraud_type} with risk score {risk_score}")
    
    # Block high-risk activities immediately
    if risk_score >= 90:
        try:
            # Block IP address
            IPBlacklist.objects.get_or_create(
                ip_address=fraud_log.ip_address,
                defaults={
                    'reason': f"High fraud risk: {fraud_type}",
                    'risk_score': risk_score,
                    'is_active': True
                }
            )
            
            logger.info(f"IP {fraud_log.ip_address} blocked due to high fraud risk")
            
        except Exception as e:
            logger.error(f"Failed to block IP {fraud_log.ip_address}: {str(e)}")
    
    # Send fraud alert to administrators
    try:
        admin_emails = [user.email for user in User.objects.filter(is_staff=True, is_active=True)]
        
        if admin_emails:
            send_mail(
                subject=f'Fraud Alert: {fraud_type}',
                message=f'''
                Fraud activity has been detected:
                
                Type: {fraud_type}
                Risk Score: {risk_score}
                IP Address: {fraud_log.ip_address}
                User Agent: {fraud_log.user_agent}
                Timestamp: {fraud_log.created_at}
                
                Please review and take appropriate action.
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=True
            )
    except Exception as e:
        logger.error(f"Failed to send fraud alert: {str(e)}")


@receiver(payment_processed)
def handle_payment_processed(sender, transaction, advertiser, **kwargs):
    """Handle payment processed events."""
    logger.info(f"Payment processed: {transaction.amount} for advertiser {advertiser.id}")
    
    # Update advertiser credit
    try:
        AdvertiserCredit.objects.create(
            advertiser=advertiser,
            amount=transaction.amount,
            credit_type=CreditTypeEnum.PAYMENT.value,
            description=f"Payment processed - Transaction ID: {transaction.transaction_id}"
        )
        
        # Update account balance
        advertiser.account_balance += transaction.amount
        advertiser.save(update_fields=['account_balance'])
        
    except Exception as e:
        logger.error(f"Failed to update advertiser credit: {str(e)}")
    
    # Record payment in audit log
    try:
        AuditLog.objects.create(
            user=advertiser.user,
            action='payment',
            details=f"Payment processed: ${transaction.amount}",
            content_object=transaction
        )
    except Exception as e:
        logger.error(f"Failed to log payment: {str(e)}")


# Model signal utility functions
def connect_model_signals():
    """Connect all model signals."""
    # This function can be called in AppConfig.ready()
    pass


def disconnect_model_signals():
    """Disconnect all model signals."""
    # This function can be called for testing
    pass


# Additional Signal Handlers for Main Models
@receiver(pre_save, sender=Advertiser)
def advertiser_pre_save(sender, instance, **kwargs):
    """Handle advertiser pre-save operations."""
    # Generate API key if not set
    if not instance.api_key:
        try:
            from .services import AdvertiserService
        except ImportError:
            AdvertiserService = None
        if AdvertiserService:
            advertiser_service = AdvertiserService()
            instance.api_key = advertiser_service.generate_api_key()
    
    # Set verification status based on profile completion
    if hasattr(instance, 'profile') and instance.profile:
        completion_percentage = instance.profile.calculate_completion_percentage()
        if completion_percentage >= 80 and instance.verification_status == 'pending':
            instance.verification_status = 'ready_for_review'


@receiver(post_save, sender=Advertiser)
def advertiser_post_save(sender, instance, created, **kwargs):
    """Handle advertiser post-save operations."""
    if created:
        # Create related objects
        from .models.billing import AdvertiserWallet
        from .models.notification import NotificationTemplate
        
        # Create wallet
        AdvertiserWallet.objects.get_or_create(
            advertiser=instance,
            defaults={'balance': 0, 'currency': 'USD'}
        )
        
        # Send welcome notification
        try:
            from .services import NotificationService
        except ImportError:
            NotificationService = None
        notification_service = NotificationService()
        notification_service.send_welcome_notification(instance)


@receiver(pre_save, sender=AdCampaign)
def campaign_pre_save(sender, instance, **kwargs):
    """Handle campaign pre-save operations."""
    # Validate budget constraints
    if instance.daily_budget and instance.total_budget:
        if instance.daily_budget > instance.total_budget:
            raise ValueError("Daily budget cannot exceed total budget")
    
    # Set default status if not provided
    if not instance.status:
        instance.status = 'draft'


@receiver(post_save, sender=AdCampaign)
def campaign_post_save(sender, instance, created, **kwargs):
    """Handle campaign post-save operations."""
    if created:
        # Create initial campaign spend record
        from .models.billing import CampaignSpend
        CampaignSpend.objects.get_or_create(
            campaign=instance,
            spend_date=timezone.now().date(),
            defaults={
                'daily_spend': 0,
                'total_spend': 0,
                'impressions': 0,
                'clicks': 0,
                'conversions': 0
            }
        )
    
    # Trigger campaign status change signal
    campaign_status_changed.send(sender=sender, instance=instance)


@receiver(post_save, sender=Conversion)
def conversion_post_save(sender, instance, created, **kwargs):
    """Handle conversion post-save operations."""
    if created:
        # Update campaign spend
        from .models.billing import CampaignSpend
        try:
            from .services import AdvertiserBillingService
        except ImportError:
            AdvertiserBillingService = None
        
        billing_service = AdvertiserBillingService()
        billing_service.update_campaign_spend(instance)
        
        # Update conversion quality score
        try:
            from .services import ConversionQualityService
        except ImportError:
            ConversionQualityService = None
        quality_service = ConversionQualityService()
        quality_service.calculate_conversion_quality_score(instance)
        
        # Send conversion notification
        try:
            from .services import NotificationService
        except ImportError:
            NotificationService = None
        notification_service = NotificationService()
        notification_service.send_conversion_notification(instance)


@receiver(pre_save, sender=TrackingPixel)
def tracking_pixel_pre_save(sender, instance, **kwargs):
    """Handle tracking pixel pre-save operations."""
    # Generate pixel ID if not set
    if not instance.pixel_id:
        try:
            from .services import TrackingPixelService
        except ImportError:
            TrackingPixelService = None
        pixel_service = TrackingPixelService()
        instance.pixel_id = pixel_service.generate_pixel_id(instance)


@receiver(post_save, sender=TrackingPixel)
def tracking_pixel_post_save(sender, instance, created, **kwargs):
    """Handle tracking pixel post-save operations."""
    if created:
        # Clear tracking cache
        try:
            from .services import TrackingPixelService
        except ImportError:
            TrackingPixelService = None
        pixel_service = TrackingPixelService()
        pixel_service.clear_pixel_cache(instance)


@receiver(pre_save, sender=AdvertiserOffer)
def offer_pre_save(sender, instance, **kwargs):
    """Handle offer pre-save operations."""
    # Validate payout amount
    if instance.payout_amount and instance.payout_amount <= 0:
        raise ValueError("Payout amount must be greater than 0")
    
    # Set default status if not provided
    if not instance.status:
        instance.status = 'draft'


@receiver(post_save, sender=AdvertiserOffer)
def offer_post_save(sender, instance, created, **kwargs):
    """Handle offer post-save operations."""
    if created:
        # Create default tracking requirements
        try:
            from .services import OfferService
        except ImportError:
            OfferService = None
        offer_service = OfferService()
        offer_service.create_default_tracking_requirements(instance)


@receiver(pre_save, sender=AdvertiserWallet)
def wallet_pre_save(sender, instance, **kwargs):
    """Handle wallet pre-save operations."""
    # Validate balance
    if instance.balance < 0:
        raise ValueError("Wallet balance cannot be negative")


@receiver(post_save, sender=AdvertiserTransaction)
def transaction_post_save(sender, instance, created, **kwargs):
    """Handle transaction post-save operations."""
    if created:
        # Update wallet balance
        try:
            from .services import AdvertiserBillingService
        except ImportError:
            AdvertiserBillingService = None
        billing_service = AdvertiserBillingService()
        billing_service.update_wallet_balance(instance)
        
        # Check budget thresholds
        if instance.transaction_type == 'spend':
            billing_service.check_budget_thresholds(instance.wallet.advertiser)
            
            # Trigger budget threshold signal if needed
            if billing_service.is_budget_threshold_reached(instance.wallet.advertiser):
                budget_threshold_reached.send(sender=sender, advertiser=instance.wallet.advertiser)


@receiver(post_save, sender=AdvertiserInvoice)
def invoice_post_save(sender, instance, created, **kwargs):
    """Handle invoice post-save operations."""
    if created:
        # Generate invoice number if not set
        if not instance.invoice_number:
            try:
                from .services import AdvertiserBillingService
            except ImportError:
                AdvertiserBillingService = None
            billing_service = AdvertiserBillingService()
            instance.invoice_number = billing_service.generate_invoice_number(instance)
            instance.save()
        
        # Send invoice notification
        try:
            from .services import NotificationService
        except ImportError:
            NotificationService = None
        notification_service = NotificationService()
        notification_service.send_invoice_notification(instance)


@receiver(pre_save, sender=ConversionQualityScore)
def conversion_quality_score_pre_save(sender, instance, **kwargs):
    """Handle conversion quality score pre-save operations."""
    # Validate score ranges
    if not (0 <= instance.overall_score <= 1):
        raise ValueError("Overall score must be between 0 and 1")
    
    if not (0 <= instance.behavioral_score <= 1):
        raise ValueError("Behavioral score must be between 0 and 1")
    
    if not (0 <= instance.technical_score <= 1):
        raise ValueError("Technical score must be between 0 and 1")


@receiver(post_save, sender=ConversionQualityScore)
def conversion_quality_score_post_save(sender, instance, created, **kwargs):
    """Handle conversion quality score post-save operations."""
    if created and instance.is_flagged:
        # Trigger fraud activity signal
        fraud_activity_detected.send(
            sender=sender,
            conversion=instance.conversion,
            score=instance.overall_score,
            fraud_indicators=instance.fraud_indicators
        )


@receiver(pre_save, sender=AdvertiserNotification)
def notification_pre_save(sender, instance, **kwargs):
    """Handle notification pre-save operations."""
    # Set sent time if not set and notification is being marked as sent
    if instance.is_read and not instance.read_at:
        instance.read_at = timezone.now()


@receiver(post_save, sender=AdvertiserNotification)
def notification_post_save(sender, instance, created, **kwargs):
    """Handle notification post-save operations."""
    if created:
        # Send email notification if enabled
        if instance.advertiser.profile and instance.advertiser.profile.email_notifications:
            try:
                from .services import NotificationService
            except ImportError:
                NotificationService = None
            notification_service = NotificationService()
            notification_service.send_email_notification(instance)


@receiver(pre_save, sender=MLModel)
def ml_model_pre_save(sender, instance, **kwargs):
    """Handle ML model pre-save operations."""
    # Validate model file if provided
    if instance.model_file:
        try:
            from .services import MLService
        except ImportError:
            MLService = None
        ml_service = MLService()
        ml_service.validate_model_file(instance.model_file)


@receiver(post_save, sender=MLModel)
def ml_model_post_save(sender, instance, created, **kwargs):
    """Handle ML model post-save operations."""
    if created:
        # Initialize model training
        try:
            from .services import MLService
        except ImportError:
            MLService = None
        ml_service = MLService()
        ml_service.initialize_model_training(instance)


@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """Handle user login events."""
    try:
        advertiser = Advertiser.objects.get(user=user)
        
        # Update last login
        advertiser.user.last_login = timezone.now()
        advertiser.user.save()
        
        # Log login activity
        try:
            from .services import AuditService
        except ImportError:
            AuditService = None
        audit_service = AuditService()
        audit_service.log_user_activity(user, 'login', request)
        
        # Clear user-specific cache
        try:
            from .services import CacheService
        except ImportError:
            CacheService = None
        cache_service = CacheService()
        cache_service.clear_user_cache(user)
        
    except Advertiser.DoesNotExist:
        pass


@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """Handle user logout events."""
    try:
        advertiser = Advertiser.objects.get(user=user)
        
        # Log logout activity
        try:
            from .services import AuditService
        except ImportError:
            AuditService = None
        audit_service = AuditService()
        audit_service.log_user_activity(user, 'logout', request)
        
        # Clear user-specific cache
        try:
            from .services import CacheService
        except ImportError:
            CacheService = None
        cache_service = CacheService()
        cache_service.clear_user_cache(user)
        
    except Advertiser.DoesNotExist:
        pass


# Signal monitoring and debugging
class SignalMonitor:
    """Utility class for monitoring signal performance."""
    
    @staticmethod
    def log_signal_execution(signal_name: str, sender_class: str, execution_time: float):
        """Log signal execution for monitoring."""
        logger.debug(f"Signal {signal_name} from {sender_class} executed in {execution_time:.3f}s")
    
    @staticmethod
    def track_signal_performance(signal_func):
        """Decorator to track signal performance."""
        def wrapper(*args, **kwargs):
            start_time = timezone.now()
            result = signal_func(*args, **kwargs)
            execution_time = (timezone.now() - start_time).total_seconds()
            
            SignalMonitor.log_signal_execution(
                signal_func.__name__,
                str(args[0].__class__) if args else 'unknown',
                execution_time
            )
            
            return result
        return wrapper
