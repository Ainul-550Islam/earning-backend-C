"""
Advertiser Service

Comprehensive service for managing advertiser accounts,
including CRUD operations, verification flows, and onboarding.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification, AdvertiserAgreement
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserService:
    """
    Service for managing advertiser accounts.
    
    Handles CRUD operations, verification workflows,
    and business logic for advertiser management.
    """
    
    def __init__(self):
        self.logger = logger
    
    def create_advertiser(self, user: User, data: Dict[str, Any]) -> Advertiser:
        """
        Create a new advertiser account.
        
        Args:
            user: User account for the advertiser
            data: Advertiser creation data
            
        Returns:
            Advertiser: Created advertiser instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Create advertiser
                advertiser = Advertiser.objects.create(
                    user=user,
                    company_name=data.get('company_name'),
                    website=data.get('website', ''),
                    business_type=data.get('business_type', 'other'),
                    contact_email=data.get('contact_email', user.email),
                    contact_phone=data.get('contact_phone', ''),
                    tax_id=data.get('tax_id', ''),
                    account_manager=data.get('account_manager'),
                    verification_status='pending',
                    status='active',
                    notes=data.get('notes', '')
                )
                
                # Create advertiser profile
                AdvertiserProfile.objects.create(
                    advertiser=advertiser,
                    address=data.get('address', ''),
                    city=data.get('city', ''),
                    state=data.get('state', ''),
                    country=data.get('country', ''),
                    postal_code=data.get('postal_code', ''),
                    contact_name=data.get('contact_name', ''),
                    contact_phone=data.get('contact_phone', ''),
                    logo=data.get('logo'),
                    industry=data.get('industry', ''),
                    company_size=data.get('company_size', ''),
                    annual_revenue=data.get('annual_revenue', ''),
                    metadata=data.get('metadata', {})
                )
                
                # Create initial verification record
                AdvertiserVerification.objects.create(
                    advertiser=advertiser,
                    document_type='business_registration',
                    status='pending',
                    submitted_at=timezone.now()
                )
                
                # Send welcome notification
                self._send_welcome_notification(advertiser)
                
                self.logger.info(f"Created advertiser: {advertiser.company_name}")
                return advertiser
                
        except Exception as e:
            self.logger.error(f"Error creating advertiser: {e}")
            raise ValidationError(f"Failed to create advertiser: {str(e)}")
    
    def update_advertiser(self, advertiser: Advertiser, data: Dict[str, Any]) -> Advertiser:
        """
        Update advertiser information.
        
        Args:
            advertiser: Advertiser instance to update
            data: Update data
            
        Returns:
            Advertiser: Updated advertiser instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Update advertiser fields
                allowed_fields = [
                    'company_name', 'website', 'business_type', 'contact_email',
                    'contact_phone', 'tax_id', 'account_manager', 'notes'
                ]
                
                for field in allowed_fields:
                    if field in data:
                        setattr(advertiser, field, data[field])
                
                advertiser.save()
                
                # Update profile if provided
                if 'profile' in data:
                    profile_data = data['profile']
                    profile = advertiser.profile
                    
                    profile_fields = [
                        'address', 'city', 'state', 'country', 'postal_code',
                        'contact_name', 'contact_phone', 'logo', 'industry',
                        'company_size', 'annual_revenue'
                    ]
                    
                    for field in profile_fields:
                        if field in profile_data:
                            setattr(profile, field, profile_data[field])
                    
                    if 'metadata' in profile_data:
                        profile.metadata.update(profile_data['metadata'])
                    
                    profile.save()
                
                self.logger.info(f"Updated advertiser: {advertiser.company_name}")
                return advertiser
                
        except Exception as e:
            self.logger.error(f"Error updating advertiser: {e}")
            raise ValidationError(f"Failed to update advertiser: {str(e)}")
    
    def get_advertiser(self, advertiser_id: int) -> Optional[Advertiser]:
        """
        Get advertiser by ID.
        
        Args:
            advertiser_id: Advertiser ID
            
        Returns:
            Advertiser: Advertiser instance or None
        """
        try:
            return Advertiser.objects.select_related(
                'user', 'profile', 'account_manager'
            ).prefetch_related(
                'campaigns', 'offers', 'notifications'
            ).get(id=advertiser_id)
        except Advertiser.DoesNotExist:
            return None
    
    def get_advertisers(self, filters: Dict[str, Any] = None) -> List[Advertiser]:
        """
        Get advertisers with optional filtering.
        
        Args:
            filters: Filter criteria
            
        Returns:
            List[Advertiser]: List of advertisers
        """
        queryset = Advertiser.objects.select_related(
            'user', 'profile', 'account_manager'
        ).order_by('-created_at')
        
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            
            if 'verification_status' in filters:
                queryset = queryset.filter(verification_status=filters['verification_status'])
            
            if 'business_type' in filters:
                queryset = queryset.filter(business_type=filters['business_type'])
            
            if 'account_manager' in filters:
                queryset = queryset.filter(account_manager=filters['account_manager'])
            
            if 'search' in filters:
                search_term = filters['search']
                queryset = queryset.filter(
                    models.Q(company_name__icontains=search_term) |
                    models.Q(contact_email__icontains=search_term) |
                    models.Q(website__icontains=search_term)
                )
        
        return list(queryset)
    
    def delete_advertiser(self, advertiser: Advertiser) -> bool:
        """
        Delete advertiser account.
        
        Args:
            advertiser: Advertiser to delete
            
        Returns:
            bool: True if successful
        """
        try:
            with transaction.atomic():
                # Check if advertiser has active campaigns or offers
                active_campaigns = advertiser.campaigns.filter(status='active').exists()
                active_offers = advertiser.offers.filter(status='active').exists()
                
                if active_campaigns or active_offers:
                    raise ValidationError("Cannot delete advertiser with active campaigns or offers")
                
                # Send notification
                self._send_account_deletion_notification(advertiser)
                
                # Delete advertiser (cascade will delete related records)
                advertiser.delete()
                
                self.logger.info(f"Deleted advertiser: {advertiser.company_name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error deleting advertiser: {e}")
            raise ValidationError(f"Failed to delete advertiser: {str(e)}")
    
    def suspend_advertiser(self, advertiser: Advertiser, reason: str) -> Advertiser:
        """
        Suspend advertiser account.
        
        Args:
            advertiser: Advertiser to suspend
            reason: Suspension reason
            
        Returns:
            Advertiser: Updated advertiser instance
        """
        try:
            with transaction.atomic():
                # Pause all active campaigns
                advertiser.campaigns.filter(status='active').update(status='paused')
                
                # Pause all active offers
                advertiser.offers.filter(status='active').update(status='paused')
                
                # Update advertiser status
                advertiser.status = 'suspended'
                advertiser.notes = f"Suspended: {reason}\n{advertiser.notes or ''}"
                advertiser.save()
                
                # Send notification
                self._send_suspension_notification(advertiser, reason)
                
                self.logger.info(f"Suspended advertiser: {advertiser.company_name}")
                return advertiser
                
        except Exception as e:
            self.logger.error(f"Error suspending advertiser: {e}")
            raise ValidationError(f"Failed to suspend advertiser: {str(e)}")
    
    def reactivate_advertiser(self, advertiser: Advertiser) -> Advertiser:
        """
        Reactivate suspended advertiser account.
        
        Args:
            advertiser: Advertiser to reactivate
            
        Returns:
            Advertiser: Updated advertiser instance
        """
        try:
            with transaction.atomic():
                # Update advertiser status
                advertiser.status = 'active'
                advertiser.save()
                
                # Send notification
                self._send_reactivation_notification(advertiser)
                
                self.logger.info(f"Reactivated advertiser: {advertiser.company_name}")
                return advertiser
                
        except Exception as e:
            self.logger.error(f"Error reactivating advertiser: {e}")
            raise ValidationError(f"Failed to reactivate advertiser: {str(e)}")
    
    def get_advertiser_stats(self, advertiser: Advertiser) -> Dict[str, Any]:
        """
        Get advertiser statistics.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Advertiser statistics
        """
        from ...models.campaign import AdCampaign
        from ...models.offer import AdvertiserOffer
        from ...models.billing import AdvertiserWallet, AdvertiserDeposit
        
        # Basic counts
        total_campaigns = AdCampaign.objects.filter(advertiser=advertiser).count()
        active_campaigns = AdCampaign.objects.filter(advertiser=advertiser, status='active').count()
        total_offers = AdvertiserOffer.objects.filter(advertiser=advertiser).count()
        active_offers = AdvertiserOffer.objects.filter(advertiser=advertiser, status='active').count()
        
        # Financial data
        wallet = AdvertiserWallet.objects.filter(advertiser=advertiser).first()
        balance = wallet.balance if wallet else 0
        credit_limit = wallet.credit_limit if wallet else 0
        
        total_deposits = AdvertiserDeposit.objects.filter(
            advertiser=advertiser,
            status='completed'
        ).aggregate(
            total=models.Sum('net_amount')
        )['total'] or 0
        
        # Recent activity
        recent_campaigns = AdCampaign.objects.filter(
            advertiser=advertiser
        ).order_by('-created_at')[:5]
        
        recent_offers = AdvertiserOffer.objects.filter(
            advertiser=advertiser
        ).order_by('-created_at')[:5]
        
        return {
            'basic_stats': {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'total_offers': total_offers,
                'active_offers': active_offers,
            },
            'financial_stats': {
                'balance': float(balance),
                'credit_limit': float(credit_limit),
                'total_deposits': float(total_deposits),
                'available_credit': float(credit_limit - balance),
            },
            'recent_activity': {
                'recent_campaigns': [
                    {
                        'id': campaign.id,
                        'name': campaign.name,
                        'status': campaign.status,
                        'created_at': campaign.created_at.isoformat(),
                    }
                    for campaign in recent_campaigns
                ],
                'recent_offers': [
                    {
                        'id': offer.id,
                        'title': offer.title,
                        'status': offer.status,
                        'created_at': offer.created_at.isoformat(),
                    }
                    for offer in recent_offers
                ],
            },
            'verification_status': advertiser.verification_status,
            'account_status': advertiser.status,
            'created_at': advertiser.created_at.isoformat(),
        }
    
    def search_advertisers(self, query: str, limit: int = 50) -> List[Advertiser]:
        """
        Search advertisers by name, email, or website.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List[Advertiser]: Matching advertisers
        """
        return list(
            Advertiser.objects.filter(
                models.Q(company_name__icontains=query) |
                models.Q(contact_email__icontains=query) |
                models.Q(website__icontains=query)
            ).select_related('profile', 'account_manager')[:limit]
        )
    
    def get_advertisers_by_account_manager(self, account_manager: User) -> List[Advertiser]:
        """
        Get advertisers assigned to an account manager.
        
        Args:
            account_manager: Account manager user
            
        Returns:
            List[Advertiser]: Assigned advertisers
        """
        return list(
            Advertiser.objects.filter(
                account_manager=account_manager
            ).select_related('profile').order_by('company_name')
        )
    
    def _send_welcome_notification(self, advertiser: Advertiser):
        """Send welcome notification to advertiser."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='welcome',
            title=_('Welcome to the Advertiser Portal!'),
            message=_(
                'Welcome to our Advertiser Portal! Your account has been created successfully. '
                'Please complete your profile and submit verification documents to get started.'
            ),
            priority='high',
            action_url='/advertiser/profile',
            action_text=_('Complete Profile')
        )
    
    def _send_account_deletion_notification(self, advertiser: Advertiser):
        """Send account deletion notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='account_suspended',
            title=_('Account Deleted'),
            message=_('Your advertiser account has been deleted as requested.'),
            priority='high'
        )
    
    def _send_suspension_notification(self, advertiser: Advertiser, reason: str):
        """Send suspension notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='account_suspended',
            title=_('Account Suspended'),
            message=_('Your account has been suspended. Reason: {reason}').format(reason=reason),
            priority='critical'
        )
    
    def _send_reactivation_notification(self, advertiser: Advertiser):
        """Send reactivation notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='account_reactivated',
            title=_('Account Reactivated'),
            message=_('Your account has been reactivated and is now fully functional.'),
            priority='high'
        )
