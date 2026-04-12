"""
Advertiser Management Services

This module contains service classes for managing advertiser accounts,
verification, users, and settings.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from ..database_models.advertiser_model import Advertiser, AdvertiserVerification, AdvertiserCredit
from ..database_models.user_model import AdvertiserUser
from ..database_models.billing_model import BillingProfile
from ..database_models.notification_model import Notification
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *

User = get_user_model()


class AdvertiserService:
    """Service for managing advertiser accounts."""
    
    @staticmethod
    def create_advertiser(data: Dict[str, Any], created_by: Optional[User] = None) -> Advertiser:
        """Create a new advertiser account."""
        try:
            with transaction.atomic():
                # Create user account first
                user_data = data.get('user', {})
                user = AdvertiserUser.objects.create_user(
                    username=user_data.get('username'),
                    email=user_data.get('email'),
                    password=user_data.get('password'),
                    first_name=user_data.get('first_name', ''),
                    last_name=user_data.get('last_name', ''),
                    phone_number=user_data.get('phone_number', '')
                )
                
                # Create advertiser
                advertiser = Advertiser.objects.create(
                    user=user,
                    company_name=data['company_name'],
                    trade_name=data.get('trade_name', ''),
                    industry=data.get('industry', ''),
                    sub_industry=data.get('sub_industry', ''),
                    contact_email=data['contact_email'],
                    contact_phone=data.get('contact_phone', ''),
                    contact_name=data.get('contact_name', ''),
                    contact_title=data.get('contact_title', ''),
                    website=data.get('website', ''),
                    description=data.get('description', ''),
                    company_size=data.get('company_size', '1-10'),
                    annual_revenue=data.get('annual_revenue', ''),
                    billing_address=data.get('billing_address', ''),
                    billing_city=data.get('billing_city', ''),
                    billing_state=data.get('billing_state', ''),
                    billing_country=data.get('billing_country', ''),
                    billing_postal_code=data.get('billing_postal_code', ''),
                    account_type=data.get('account_type', 'business'),
                    timezone=data.get('timezone', 'UTC'),
                    currency=data.get('currency', 'USD'),
                    language=data.get('language', 'en'),
                    created_by=created_by
                )
                
                # Create billing profile
                BillingProfile.objects.create(
                    advertiser=advertiser,
                    company_name=data['company_name'],
                    trade_name=data.get('trade_name', ''),
                    billing_email=data['contact_email'],
                    billing_phone=data.get('contact_phone', ''),
                    billing_contact=data.get('contact_name', ''),
                    billing_title=data.get('contact_title', ''),
                    billing_address_line1=data.get('billing_address', ''),
                    billing_city=data.get('billing_city', ''),
                    billing_state=data.get('billing_state', ''),
                    billing_country=data.get('billing_country', ''),
                    billing_postal_code=data.get('billing_postal_code', ''),
                    default_currency=data.get('currency', 'USD'),
                    created_by=created_by
                )
                
                # Send verification email
                AdvertiserVerificationService.send_verification_email(advertiser)
                
                # Create welcome notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=user,
                    title='Welcome to Advertiser Portal',
                    message=f'Welcome {advertiser.company_name}! Your account has been created successfully.',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app', 'email']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    advertiser,
                    created_by,
                    description=f"Created advertiser account: {advertiser.company_name}"
                )
                
                return advertiser
                
        except Exception as e:
            logger.error(f"Error creating advertiser: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create advertiser: {str(e)}")
    
    @staticmethod
    def update_advertiser(advertiser_id: UUID, data: Dict[str, Any], 
                          updated_by: Optional[User] = None) -> Advertiser:
        """Update advertiser account."""
        try:
            advertiser = Advertiser.objects.get(id=advertiser_id)
            
            with transaction.atomic():
                # Track changes for audit log
                changed_fields = {}
                
                # Update basic information
                for field in ['company_name', 'trade_name', 'industry', 'sub_industry',
                             'contact_email', 'contact_phone', 'contact_name', 'contact_title',
                             'website', 'description', 'company_size', 'annual_revenue',
                             'billing_address', 'billing_city', 'billing_state',
                             'billing_country', 'billing_postal_code', 'timezone',
                             'currency', 'language']:
                    if field in data:
                        old_value = getattr(advertiser, field)
                        new_value = data[field]
                        if old_value != new_value:
                            setattr(advertiser, field, new_value)
                            changed_fields[field] = {'old': old_value, 'new': new_value}
                
                advertiser.modified_by = updated_by
                advertiser.save()
                
                # Update billing profile if provided
                billing_data = data.get('billing_profile', {})
                if billing_data:
                    billing_profile = advertiser.get_billing_profile()
                    if billing_profile:
                        for field in ['company_name', 'trade_name', 'billing_email',
                                     'billing_phone', 'billing_contact', 'billing_title',
                                     'billing_address_line1', 'billing_city',
                                     'billing_state', 'billing_country',
                                     'billing_postal_code', 'default_currency']:
                            if field in billing_data:
                                old_value = getattr(billing_profile, field)
                                new_value = billing_data[field]
                                if old_value != new_value:
                                    setattr(billing_profile, field, new_value)
                                    changed_fields[f'billing_{field}'] = {'old': old_value, 'new': new_value}
                        
                        billing_profile.modified_by = updated_by
                        billing_profile.save()
                
                # Log changes
                if changed_fields:
                    from ..database_models.audit_model import AuditLog
                    AuditLog.log_update(
                        advertiser,
                        changed_fields,
                        updated_by,
                        description=f"Updated advertiser account: {advertiser.company_name}"
                    )
                
                return advertiser
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error updating advertiser {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to update advertiser: {str(e)}")
    
    @staticmethod
    def delete_advertiser(advertiser_id: UUID, deleted_by: Optional[User] = None) -> bool:
        """Delete advertiser account (soft delete)."""
        try:
            advertiser = Advertiser.objects.get(id=advertiser_id)
            
            with transaction.atomic():
                # Log deletion
                from ..database_models.audit_model import AuditLog
                AuditLog.log_deletion(
                    advertiser,
                    deleted_by,
                    description=f"Deleted advertiser account: {advertiser.company_name}"
                )
                
                # Soft delete
                advertiser.soft_delete()
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=deleted_by,
                    title='Account Deleted',
                    message=f'Advertiser account {advertiser.company_name} has been deleted.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app']
                )
                
                return True
                
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
        except Exception as e:
            logger.error(f"Error deleting advertiser {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to delete advertiser: {str(e)}")
    
    @staticmethod
    def get_advertiser(advertiser_id: UUID) -> Advertiser:
        """Get advertiser by ID."""
        try:
            return Advertiser.objects.get(id=advertiser_id, is_deleted=False)
        except Advertiser.DoesNotExist:
            raise AdvertiserNotFoundError(f"Advertiser {advertiser_id} not found")
    
    @staticmethod
    def list_advertisers(filters: Optional[Dict[str, Any]] = None,
                          page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """List advertisers with filtering and pagination."""
        try:
            queryset = Advertiser.objects.filter(is_deleted=False)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'is_verified' in filters:
                    queryset = queryset.filter(is_verified=filters['is_verified'])
                if 'account_type' in filters:
                    queryset = queryset.filter(account_type=filters['account_type'])
                if 'industry' in filters:
                    queryset = queryset.filter(industry=filters['industry'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(company_name__icontains=search) |
                        Q(contact_email__icontains=search) |
                        Q(trade_name__icontains=search)
                    )
            
            # Count total
            total_count = queryset.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            advertisers = queryset[offset:offset + page_size]
            
            return {
                'advertisers': advertisers,
                'total_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Error listing advertisers: {str(e)}")
            raise AdvertiserServiceError(f"Failed to list advertisers: {str(e)}")
    
    @staticmethod
    def get_advertiser_performance(advertiser_id: UUID) -> Dict[str, Any]:
        """Get advertiser performance summary."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            return advertiser.get_performance_summary()
        except Exception as e:
            logger.error(f"Error getting advertiser performance {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get advertiser performance: {str(e)}")
    
    @staticmethod
    def add_credit(advertiser_id: UUID, amount: Decimal, credit_type: str = 'payment',
                   description: str = '', created_by: Optional[User] = None) -> bool:
        """Add credit to advertiser account."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            return advertiser.add_credit(amount, credit_type, description)
        except Exception as e:
            logger.error(f"Error adding credit to advertiser {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to add credit: {str(e)}")
    
    @staticmethod
    def can_create_campaign(advertiser_id: UUID) -> bool:
        """Check if advertiser can create new campaigns."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            return advertiser.can_create_campaign()
        except Exception as e:
            logger.error(f"Error checking campaign creation permission {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to check campaign creation permission: {str(e)}")


class AdvertiserVerificationService:
    """Service for managing advertiser verification."""
    
    @staticmethod
    def send_verification_email(advertiser: Advertiser) -> bool:
        """Send verification email to advertiser."""
        try:
            # Generate verification token
            import secrets
            token = secrets.token_urlsafe(32)
            
            # Create verification record
            verification = AdvertiserVerification.objects.create(
                advertiser=advertiser,
                verification_type='business',
                status='pending',
                submitted_documents=[],
                verification_notes='Verification email sent'
            )
            
            # Send email (mock implementation)
            subject = f"Verify Your Advertiser Account - {advertiser.company_name}"
            message = f"""
            Dear {advertiser.contact_name},
            
            Please verify your advertiser account by clicking the link below:
            
            {settings.FRONTEND_URL}/verify/{token}
            
            This link will expire in 24 hours.
            
            Best regards,
            Advertiser Portal Team
            """
            
            # In production, use actual email sending
            # send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [advertiser.contact_email])
            
            # Store token (in production, store securely)
            advertiser.verification_token = token
            advertiser.verification_sent_at = timezone.now()
            advertiser.save(update_fields=['verification_token', 'verification_sent_at'])
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            return False
    
    @staticmethod
    def verify_advertiser(advertiser_id: UUID, token: str, verified_by: Optional[User] = None) -> bool:
        """Verify advertiser account."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            
            # Verify token
            if advertiser.verification_token != token:
                return False
            
            # Check if token is expired (24 hours)
            if advertiser.verification_sent_at:
                expiry_time = advertiser.verification_sent_at + timezone.timedelta(hours=24)
                if timezone.now() > expiry_time:
                    return False
            
            with transaction.atomic():
                # Mark as verified
                advertiser.is_verified = True
                advertiser.verification_date = timezone.now()
                advertiser.verified_by = verified_by
                advertiser.verification_token = ''
                advertiser.save(update_fields=[
                    'is_verified', 'verification_date', 'verified_by', 'verification_token'
                ])
                
                # Update verification record
                AdvertiserVerification.objects.filter(
                    advertiser=advertiser,
                    status='pending'
                ).update(
                    status='approved',
                    verified_by=verified_by,
                    reviewed_at=timezone.now()
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=advertiser.user,
                    title='Account Verified',
                    message='Your advertiser account has been successfully verified.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log verification
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='verify',
                    object_type='Advertiser',
                    object_id=str(advertiser.id),
                    user=verified_by,
                    advertiser=advertiser,
                    description=f"Verified advertiser account: {advertiser.company_name}"
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error verifying advertiser {advertiser_id}: {str(e)}")
            return False
    
    @staticmethod
    def submit_verification_documents(advertiser_id: UUID, documents: List[str],
                                     submitted_by: Optional[User] = None) -> AdvertiserVerification:
        """Submit verification documents."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            
            verification = AdvertiserVerification.objects.create(
                advertiser=advertiser,
                verification_type='business',
                status='in_review',
                submitted_documents=documents,
                verification_notes='Documents submitted for review'
            )
            
            # Send notification
            Notification.objects.create(
                advertiser=advertiser,
                user=submitted_by,
                title='Verification Documents Submitted',
                message='Your verification documents have been submitted for review.',
                notification_type='system',
                priority='medium',
                channels=['in_app']
            )
            
            return verification
            
        except Exception as e:
            logger.error(f"Error submitting verification documents {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to submit verification documents: {str(e)}")
    
    @staticmethod
    def review_verification(verification_id: UUID, status: str, notes: str = '',
                           reviewed_by: Optional[User] = None) -> bool:
        """Review verification request."""
        try:
            verification = AdvertiserVerification.objects.get(id=verification_id)
            
            with transaction.atomic():
                verification.status = status
                verification.verification_notes = notes
                verification.reviewed_by = reviewed_by
                verification.reviewed_at = timezone.now()
                verification.save()
                
                # Update advertiser status if approved
                if status == 'approved':
                    verification.advertiser.is_verified = True
                    verification.advertiser.verification_date = timezone.now()
                    verification.advertiser.verified_by = reviewed_by
                    verification.advertiser.save(update_fields=[
                        'is_verified', 'verification_date', 'verified_by'
                    ])
                
                # Send notification
                Notification.objects.create(
                    advertiser=verification.advertiser,
                    user=verification.advertiser.user,
                    title=f'Verification {status.title()}',
                    message=f'Your verification request has been {status}. {notes}',
                    notification_type='system',
                    priority='high' if status == 'approved' else 'medium',
                    channels=['in_app', 'email']
                )
                
                return True
                
        except AdvertiserVerification.DoesNotExist:
            raise AdvertiserNotFoundError(f"Verification {verification_id} not found")
        except Exception as e:
            logger.error(f"Error reviewing verification {verification_id}: {str(e)}")
            return False


class AdvertiserUserService:
    """Service for managing advertiser users."""
    
    @staticmethod
    def create_user(advertiser_id: UUID, data: Dict[str, Any],
                    created_by: Optional[User] = None) -> AdvertiserUser:
        """Create a new user for advertiser."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            
            with transaction.atomic():
                user = AdvertiserUser.objects.create_user(
                    username=data['username'],
                    email=data['email'],
                    password=data['password'],
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                    phone_number=data.get('phone_number', ''),
                    job_title=data.get('job_title', ''),
                    department=data.get('department', ''),
                    advertiser=advertiser,
                    role=data.get('role', 'viewer'),
                    created_by=created_by
                )
                
                # Set permissions based on role
                AdvertiserUserService._set_role_permissions(user, data.get('role', 'viewer'))
                
                # Create notification preferences
                from ..database_models.notification_model import NotificationPreference
                NotificationPreference.objects.create(
                    user=user,
                    advertiser=advertiser
                )
                
                # Send notification
                Notification.objects.create(
                    advertiser=advertiser,
                    user=user,
                    title='User Account Created',
                    message=f'Your user account has been created with role: {user.role}',
                    notification_type='system',
                    priority='medium',
                    channels=['in_app', 'email']
                )
                
                # Log creation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_creation(
                    user,
                    created_by,
                    description=f"Created user: {user.username}"
                )
                
                return user
                
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise AdvertiserServiceError(f"Failed to create user: {str(e)}")
    
    @staticmethod
    def _set_role_permissions(user: AdvertiserUser, role: str) -> None:
        """Set user permissions based on role."""
        role_permissions = {
            'owner': ['*'],
            'admin': ['campaign.create', 'campaign.edit', 'billing.view', 'billing.manage', 'users.manage', 'reports.view', 'data.export'],
            'manager': ['campaign.create', 'campaign.edit', 'billing.view', 'reports.view', 'data.export'],
            'analyst': ['campaign.view', 'reports.view', 'data.export'],
            'viewer': ['campaign.view', 'reports.view']
        }
        
        if role in role_permissions:
            user.permissions = role_permissions[role]
            user.save(update_fields=['permissions'])
    
    @staticmethod
    def update_user_permissions(user_id: UUID, permissions: List[str],
                                updated_by: Optional[User] = None) -> bool:
        """Update user permissions."""
        try:
            user = AdvertiserUser.objects.get(id=user_id)
            
            with transaction.atomic():
                old_permissions = user.permissions.copy()
                user.permissions = permissions
                user.modified_by = updated_by
                user.save(update_fields=['permissions', 'modified_by'])
                
                # Log change
                from ..database_models.audit_model import AuditLog
                AuditLog.log_update(
                    user,
                    {'permissions': {'old': old_permissions, 'new': permissions}},
                    updated_by,
                    description=f"Updated permissions for user: {user.username}"
                )
                
                return True
                
        except AdvertiserUser.DoesNotExist:
            raise AdvertiserNotFoundError(f"User {user_id} not found")
        except Exception as e:
            logger.error(f"Error updating user permissions {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def deactivate_user(user_id: UUID, deactivated_by: Optional[User] = None) -> bool:
        """Deactivate user account."""
        try:
            user = AdvertiserUser.objects.get(id=user_id)
            
            with transaction.atomic():
                user.is_active = False
                user.save(update_fields=['is_active'])
                
                # Send notification
                Notification.objects.create(
                    advertiser=user.advertiser,
                    user=user,
                    title='Account Deactivated',
                    message='Your account has been deactivated.',
                    notification_type='system',
                    priority='high',
                    channels=['in_app', 'email']
                )
                
                # Log deactivation
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='deactivate',
                    object_type='User',
                    object_id=str(user.id),
                    user=deactivated_by,
                    advertiser=user.advertiser,
                    description=f"Deactivated user: {user.username}"
                )
                
                return True
                
        except AdvertiserUser.DoesNotExist:
            raise AdvertiserNotFoundError(f"User {user_id} not found")
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {str(e)}")
            return False


class AdvertiserSettingsService:
    """Service for managing advertiser settings."""
    
    @staticmethod
    def get_settings(advertiser_id: UUID) -> Dict[str, Any]:
        """Get all settings for advertiser."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            
            # Get configuration settings
            from ..database_models.configuration_model import Configuration
            configs = Configuration.objects.filter(
                advertiser=advertiser,
                is_active=True
            )
            
            settings = {}
            for config in configs:
                settings[config.key] = config.get_typed_value()
            
            return settings
            
        except Exception as e:
            logger.error(f"Error getting settings for advertiser {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to get settings: {str(e)}")
    
    @staticmethod
    def update_settings(advertiser_id: UUID, settings: Dict[str, Any],
                        updated_by: Optional[User] = None) -> bool:
        """Update advertiser settings."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            
            with transaction.atomic():
                from ..database_models.configuration_model import Configuration
                
                for key, value in settings.items():
                    config, created = Configuration.objects.get_or_create(
                        advertiser=advertiser,
                        key=key,
                        defaults={
                            'value': str(value),
                            'value_type': 'string',
                            'category': 'custom'
                        }
                    )
                    
                    if not created:
                        config.set_value(value)
                        config.modified_by = updated_by
                        config.save(update_fields=['value', 'modified_by'])
                
                # Log settings update
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='update',
                    object_type='Configuration',
                    object_id=str(advertiser.id),
                    user=updated_by,
                    advertiser=advertiser,
                    description=f"Updated settings for advertiser: {advertiser.company_name}",
                    details={'updated_settings': settings}
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating settings for advertiser {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to update settings: {str(e)}")
    
    @staticmethod
    def reset_settings(advertiser_id: UUID, reset_by: Optional[User] = None) -> bool:
        """Reset advertiser settings to defaults."""
        try:
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            
            with transaction.atomic():
                from ..database_models.configuration_model import Configuration
                
                # Delete custom configurations
                Configuration.objects.filter(
                    advertiser=advertiser,
                    category='custom'
                ).delete()
                
                # Log reset
                from ..database_models.audit_model import AuditLog
                AuditLog.log_action(
                    action='reset',
                    object_type='Configuration',
                    object_id=str(advertiser.id),
                    user=reset_by,
                    advertiser=advertiser,
                    description=f"Reset settings for advertiser: {advertiser.company_name}"
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error resetting settings for advertiser {advertiser_id}: {str(e)}")
            raise AdvertiserServiceError(f"Failed to reset settings: {str(e)}")
