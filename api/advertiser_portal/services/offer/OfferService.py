"""
Offer Service

Comprehensive service for managing advertising offers,
including CRUD operations, approval workflows, and publishing.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.offer import AdvertiserOffer, OfferRequirement, OfferCreative, OfferBlacklist
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferService:
    """
    Service for managing advertising offers.
    
    Handles offer creation, lifecycle management,
    approval workflows, and publishing.
    """
    
    def __init__(self):
        self.logger = logger
    
    def create_offer(self, advertiser, data: Dict[str, Any]) -> AdvertiserOffer:
        """
        Create a new advertising offer.
        
        Args:
            advertiser: Advertiser instance
            data: Offer creation data
            
        Returns:
            AdvertiserOffer: Created offer instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate advertiser status
                if advertiser.verification_status != 'verified':
                    raise ValidationError("Advertiser must be verified to create offers")
                
                if advertiser.status != 'active':
                    raise ValidationError("Advertiser account must be active")
                
                # Create offer
                offer = AdvertiserOffer.objects.create(
                    advertiser=advertiser,
                    campaign=data.get('campaign'),
                    title=data.get('title'),
                    description=data.get('description', ''),
                    payout_type=data.get('payout_type', 'cpa'),
                    payout_amount=data.get('payout_amount'),
                    currency=data.get('currency', 'USD'),
                    tracking_url=data.get('tracking_url'),
                    preview_url=data.get('preview_url', ''),
                    test_mode=data.get('test_mode', False),
                    deduplication_window=data.get('deduplication_window', 24),
                    status='draft',
                    is_private=data.get('is_private', False),
                    allowed_countries=data.get('allowed_countries', []),
                    blocked_countries=data.get('blocked_countries', []),
                    allowed_devices=data.get('allowed_devices', []),
                    blocked_devices=data.get('blocked_devices', []),
                    quality_score=data.get('quality_score', 0.00),
                    conversion_rate=data.get('conversion_rate', 0.00),
                    daily_budget=data.get('daily_budget'),
                    total_budget=data.get('total_budget'),
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date'),
                    metadata=data.get('metadata', {})
                )
                
                # Create offer requirements if provided
                if 'requirements' in data:
                    self._create_offer_requirements(offer, data['requirements'])
                
                # Create offer creatives if provided
                if 'creatives' in data:
                    self._create_offer_creatives(offer, data['creatives'])
                
                # Create offer blacklists if provided
                if 'blacklists' in data:
                    self._create_offer_blacklists(offer, data['blacklists'])
                
                # Send notification
                self._send_offer_created_notification(advertiser, offer)
                
                self.logger.info(f"Created offer: {offer.title} for {advertiser.company_name}")
                return offer
                
        except Exception as e:
            self.logger.error(f"Error creating offer: {e}")
            raise ValidationError(f"Failed to create offer: {str(e)}")
    
    def update_offer(self, offer: AdvertiserOffer, data: Dict[str, Any]) -> AdvertiserOffer:
        """
        Update offer information.
        
        Args:
            offer: Offer instance to update
            data: Update data
            
        Returns:
            AdvertiserOffer: Updated offer instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Check if offer can be updated
                if offer.status == 'expired':
                    raise ValidationError("Cannot update expired offer")
                
                # Update offer fields
                allowed_fields = [
                    'title', 'description', 'payout_type', 'payout_amount', 'currency',
                    'tracking_url', 'preview_url', 'test_mode', 'deduplication_window',
                    'is_private', 'allowed_countries', 'blocked_countries',
                    'allowed_devices', 'blocked_devices', 'quality_score',
                    'conversion_rate', 'daily_budget', 'total_budget',
                    'start_date', 'end_date', 'metadata'
                ]
                
                for field in allowed_fields:
                    if field in data:
                        setattr(offer, field, data[field])
                
                offer.save()
                
                # Update requirements if provided
                if 'requirements' in data:
                    self._update_offer_requirements(offer, data['requirements'])
                
                # Update creatives if provided
                if 'creatives' in data:
                    self._update_offer_creatives(offer, data['creatives'])
                
                # Update blacklists if provided
                if 'blacklists' in data:
                    self._update_offer_blacklists(offer, data['blacklists'])
                
                self.logger.info(f"Updated offer: {offer.title}")
                return offer
                
        except Exception as e:
            self.logger.error(f"Error updating offer: {e}")
            raise ValidationError(f"Failed to update offer: {str(e)}")
    
    def submit_for_review(self, offer: Advertiser, notes: str = None) -> AdvertiserOffer:
        """
        Submit offer for review.
        
        Args:
            offer: Offer instance
            notes: Review notes
            
        Returns:
            AdvertiserOffer: Updated offer instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if offer.status not in ['draft', 'rejected']:
                    raise ValidationError("Only draft or rejected offers can be submitted for review")
                
                # Validate offer has required fields
                self._validate_offer_for_review(offer)
                
                # Update offer status
                offer.status = 'pending_review'
                offer.save()
                
                # Send notification to account manager
                self._send_offer_review_notification(offer)
                
                # Send confirmation to advertiser
                self._send_offer_submitted_notification(offer.advertiser, offer, notes)
                
                self.logger.info(f"Submitted offer for review: {offer.title}")
                return offer
                
        except Exception as e:
            self.logger.error(f"Error submitting offer for review: {e}")
            raise ValidationError(f"Failed to submit offer for review: {str(e)}")
    
    def approve_offer(self, offer: AdvertiserOffer, reviewer: User, notes: str = None) -> AdvertiserOffer:
        """
        Approve offer.
        
        Args:
            offer: Offer instance
            reviewer: User approving the offer
            notes: Approval notes
            
        Returns:
            AdvertiserOffer: Updated offer instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if offer.status != 'pending_review':
                    raise ValidationError("Only offers pending review can be approved")
                
                # Update offer status
                offer.status = 'active'
                offer.save()
                
                # Store approval in metadata
                metadata = offer.metadata or {}
                metadata.update({
                    'approved_by': reviewer.id,
                    'approved_at': timezone.now().isoformat(),
                    'approval_notes': notes,
                })
                offer.metadata = metadata
                offer.save()
                
                # Send notification to advertiser
                self._send_offer_approved_notification(offer.advertiser, offer, notes)
                
                self.logger.info(f"Approved offer: {offer.title}")
                return offer
                
        except Exception as e:
            self.logger.error(f"Error approving offer: {e}")
            raise ValidationError(f"Failed to approve offer: {str(e)}")
    
    def reject_offer(self, offer: AdvertiserOffer, reviewer: User, reason: str, notes: str = None) -> AdvertiserOffer:
        """
        Reject offer.
        
        Args:
            offer: Offer instance
            reviewer: User rejecting the offer
            reason: Rejection reason
            notes: Additional notes
            
        Returns:
            AdvertiserOffer: Updated offer instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if offer.status != 'pending_review':
                    raise ValidationError("Only offers pending review can be rejected")
                
                # Update offer status
                offer.status = 'rejected'
                offer.save()
                
                # Store rejection in metadata
                metadata = offer.metadata or {}
                metadata.update({
                    'rejected_by': reviewer.id,
                    'rejected_at': timezone.now().isoformat(),
                    'rejection_reason': reason,
                    'rejection_notes': notes,
                })
                offer.metadata = metadata
                offer.save()
                
                # Send notification to advertiser
                self._send_offer_rejected_notification(offer.advertiser, offer, reason, notes)
                
                self.logger.info(f"Rejected offer: {offer.title}")
                return offer
                
        except Exception as e:
            self.logger.error(f"Error rejecting offer: {e}")
            raise ValidationError(f"Failed to reject offer: {str(e)}")
    
    def pause_offer(self, offer: AdvertiserOffer, reason: str = None) -> AdvertiserOffer:
        """
        Pause offer.
        
        Args:
            offer: Offer instance
            reason: Reason for pausing
            
        Returns:
            AdvertiserOffer: Updated offer instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if offer.status != 'active':
                    raise ValidationError("Only active offers can be paused")
                
                # Update offer status
                offer.status = 'paused'
                offer.save()
                
                # Send notification
                self._send_offer_paused_notification(offer.advertiser, offer, reason)
                
                self.logger.info(f"Paused offer: {offer.title}")
                return offer
                
        except Exception as e:
            self.logger.error(f"Error pausing offer: {e}")
            raise ValidationError(f"Failed to pause offer: {str(e)}")
    
    def resume_offer(self, offer: AdvertiserOffer) -> AdvertiserOffer:
        """
        Resume paused offer.
        
        Args:
            offer: Offer instance
            
        Returns:
            AdvertiserOffer: Updated offer instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if offer.status != 'paused':
                    raise ValidationError("Only paused offers can be resumed")
                
                # Check if offer should still be active
                now = timezone.now()
                if offer.end_date and now.date() > offer.end_date:
                    raise ValidationError("Cannot resume offer past end date")
                
                # Update offer status
                offer.status = 'active'
                offer.save()
                
                # Send notification
                self._send_offer_resumed_notification(offer.advertiser, offer)
                
                self.logger.info(f"Resumed offer: {offer.title}")
                return offer
                
        except Exception as e:
            self.logger.error(f"Error resuming offer: {e}")
            raise ValidationError(f"Failed to resume offer: {str(e)}")
    
    def expire_offer(self, offer: AdvertiserOffer, reason: str = None) -> AdvertiserOffer:
        """
        Expire offer.
        
        Args:
            offer: Offer instance
            reason: Reason for expiration
            
        Returns:
            AdvertiserOffer: Updated offer instance
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if offer.status in ['expired', 'cancelled']:
                    raise ValidationError("Offer is already expired or cancelled")
                
                # Update offer status
                offer.status = 'expired'
                offer.save()
                
                # Send notification
                self._send_offer_expired_notification(offer.advertiser, offer, reason)
                
                self.logger.info(f"Expired offer: {offer.title}")
                return offer
                
        except Exception as e:
            self.logger.error(f"Error expiring offer: {e}")
            raise ValidationError(f"Failed to expire offer: {str(e)}")
    
    def get_offer(self, offer_id: int) -> Optional[AdvertiserOffer]:
        """
        Get offer by ID.
        
        Args:
            offer_id: Offer ID
            
        Returns:
            AdvertiserOffer: Offer instance or None
        """
        try:
            return AdvertiserOffer.objects.select_related(
                'advertiser', 'advertiser__user', 'campaign'
            ).prefetch_related(
                'requirements', 'creatives', 'blacklists'
            ).get(id=offer_id)
        except AdvertiserOffer.DoesNotExist:
            return None
    
    def get_offers(self, advertiser=None, filters: Dict[str, Any] = None) -> List[AdvertiserOffer]:
        """
        Get offers with optional filtering.
        
        Args:
            advertiser: Optional advertiser filter
            filters: Additional filter criteria
            
        Returns:
            List[AdvertiserOffer]: List of offers
        """
        queryset = AdvertiserOffer.objects.select_related('advertiser', 'campaign').order_by('-created_at')
        
        if advertiser:
            queryset = queryset.filter(advertiser=advertiser)
        
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            
            if 'payout_type' in filters:
                queryset = queryset.filter(payout_type=filters['payout_type'])
            
            if 'is_private' in filters:
                queryset = queryset.filter(is_private=filters['is_private'])
            
            if 'start_date_from' in filters:
                queryset = queryset.filter(start_date__gte=filters['start_date_from'])
            
            if 'start_date_to' in filters:
                queryset = queryset.filter(start_date__lte=filters['start_date_to'])
            
            if 'search' in filters:
                search_term = filters['search']
                queryset = queryset.filter(
                    models.Q(title__icontains=search_term) |
                    models.Q(description__icontains=search_term)
                )
        
        return list(queryset)
    
    def get_offer_stats(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """
        Get offer statistics.
        
        Args:
            offer: Offer instance
            
        Returns:
            Dict[str, Any]: Offer statistics
        """
        try:
            # Basic stats
            total_requirements = offer.requirements.count()
            active_requirements = offer.requirements.filter(status='active').count()
            total_creatives = offer.creatives.count()
            active_creatives = offer.creatives.filter(status='active', is_approved=True).count()
            total_blacklists = offer.blacklists.count()
            active_blacklists = offer.blacklists.filter(status='active').count()
            
            # Performance stats (placeholder - would come from tracking data)
            performance_data = {
                'total_impressions': 0,
                'total_clicks': 0,
                'total_conversions': 0,
                'total_spend': 0.0,
                'ctr': 0.0,
                'conversion_rate': 0.0,
                'cpa': 0.0,
            }
            
            return {
                'basic_stats': {
                    'total_requirements': total_requirements,
                    'active_requirements': active_requirements,
                    'total_creatives': total_creatives,
                    'active_creatives': active_creatives,
                    'total_blacklists': total_blacklists,
                    'active_blacklists': active_blacklists,
                    'status': offer.status,
                    'payout_type': offer.payout_type,
                    'is_private': offer.is_private,
                    'created_at': offer.created_at.isoformat(),
                },
                'financial_stats': {
                    'payout_amount': float(offer.payout_amount),
                    'currency': offer.currency,
                    'daily_budget': float(offer.daily_budget or 0),
                    'total_budget': float(offer.total_budget or 0),
                    'quality_score': float(offer.quality_score),
                    'conversion_rate': float(offer.conversion_rate),
                },
                'performance_stats': performance_data,
                'date_info': {
                    'start_date': offer.start_date.isoformat() if offer.start_date else None,
                    'end_date': offer.end_date.isoformat() if offer.end_date else None,
                    'is_active': offer.status == 'active',
                    'days_remaining': offer.days_remaining,
                    'is_expired': offer.is_expired,
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting offer stats: {e}")
            raise ValidationError(f"Failed to get offer stats: {str(e)}")
    
    def search_offers(self, query: str, advertiser=None, limit: int = 50) -> List[AdvertiserOffer]:
        """
        Search offers by title or description.
        
        Args:
            query: Search query
            advertiser: Optional advertiser filter
            limit: Maximum results
            
        Returns:
            List[AdvertiserOffer]: Matching offers
        """
        queryset = AdvertiserOffer.objects.filter(
            models.Q(title__icontains=query) |
            models.Q(description__icontains=query)
        )
        
        if advertiser:
            queryset = queryset.filter(advertiser=advertiser)
        
        return list(queryset.select_related('advertiser', 'campaign')[:limit])
    
    def _create_offer_requirements(self, offer: AdvertiserOffer, requirements_data: List[Dict[str, Any]]):
        """Create offer requirements."""
        for req_data in requirements_data:
            OfferRequirement.objects.create(
                offer=offer,
                requirement_type=req_data.get('requirement_type'),
                instructions=req_data.get('instructions'),
                status=req_data.get('status', 'draft'),
                proof_required=req_data.get('proof_required', True),
                proof_instructions=req_data.get('proof_instructions'),
                validation_rules=req_data.get('validation_rules', {}),
                completion_time_limit=req_data.get('completion_time_limit'),
                retry_attempts=req_data.get('retry_attempts', 3),
                cooldown_period=req_data.get('cooldown_period', 0),
                reward_amount=req_data.get('reward_amount'),
                reward_type=req_data.get('reward_type', 'fixed'),
                start_date=req_data.get('start_date'),
                end_date=req_data.get('end_date')
            )
    
    def _create_offer_creatives(self, offer: AdvertiserOffer, creatives_data: List[Dict[str, Any]]):
        """Create offer creatives."""
        for creative_data in creatives_data:
            OfferCreative.objects.create(
                offer=offer,
                name=creative_data.get('name'),
                creative_type=creative_data.get('creative_type', 'banner'),
                file=creative_data.get('file'),
                file_url=creative_data.get('file_url'),
                width=creative_data.get('width'),
                height=creative_data.get('height'),
                video_duration=creative_data.get('video_duration'),
                video_thumbnail=creative_data.get('video_thumbnail'),
                headline=creative_data.get('headline'),
                description=creative_data.get('description'),
                cta_text=creative_data.get('cta_text'),
                brand_name=creative_data.get('brand_name'),
                status=creative_data.get('status', 'draft'),
                is_approved=creative_data.get('is_approved', False),
                rejection_reason=creative_data.get('rejection_reason')
            )
    
    def _create_offer_blacklists(self, offer: AdvertiserOffer, blacklists_data: List[Dict[str, Any]]):
        """Create offer blacklists."""
        for blacklist_data in blacklists_data:
            OfferBlacklist.objects.create(
                offer=offer,
                blacklist_type=blacklist_data.get('blacklist_type'),
                value=blacklist_data.get('value'),
                status=blacklist_data.get('status', 'active'),
                reason=blacklist_data.get('reason'),
                match_type=blacklist_data.get('match_type', 'exact'),
                case_sensitive=blacklist_data.get('case_sensitive', True),
                expires_at=blacklist_data.get('expires_at'),
                metadata=blacklist_data.get('metadata', {})
            )
    
    def _update_offer_requirements(self, offer: AdvertiserOffer, requirements_data: List[Dict[str, Any]]):
        """Update offer requirements."""
        # Clear existing requirements
        offer.requirements.all().delete()
        
        # Create new requirements
        self._create_offer_requirements(offer, requirements_data)
    
    def _update_offer_creatives(self, offer: AdvertiserOffer, creatives_data: List[Dict[str, Any]]):
        """Update offer creatives."""
        # Clear existing creatives
        offer.creatives.all().delete()
        
        # Create new creatives
        self._create_offer_creatives(offer, creatives_data)
    
    def _update_offer_blacklists(self, offer: AdvertiserOffer, blacklists_data: List[Dict[str, Any]]):
        """Update offer blacklists."""
        # Clear existing blacklists
        offer.blacklists.all().delete()
        
        # Create new blacklists
        self._create_offer_blacklists(offer, blacklists_data)
    
    def _validate_offer_for_review(self, offer: AdvertiserOffer):
        """Validate offer has required fields for review."""
        if not offer.title.strip():
            raise ValidationError("Offer title is required")
        
        if not offer.description.strip():
            raise ValidationError("Offer description is required")
        
        if not offer.tracking_url.strip():
            raise ValidationError("Tracking URL is required")
        
        if offer.payout_amount <= 0:
            raise ValidationError("Payout amount must be positive")
        
        if not offer.requirements.exists():
            raise ValidationError("At least one requirement is required")
        
        if not offer.creatives.exists():
            raise ValidationError("At least one creative is required")
    
    def _send_offer_created_notification(self, advertiser, offer: AdvertiserOffer):
        """Send offer created notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='offer_created',
            title=_('Offer Created'),
            message=_('Your offer "{offer_title}" has been created successfully.').format(
                offer_title=offer.title
            ),
            priority='medium',
            action_url=f'/advertiser/offers/{offer.id}/',
            action_text=_('View Offer')
        )
    
    def _send_offer_review_notification(self, offer: AdvertiserOffer):
        """Send offer review notification to account manager."""
        if offer.advertiser.account_manager:
            AdvertiserNotification.objects.create(
                advertiser=offer.advertiser,
                type='offer_created',
                title=_('Offer Review Required'),
                message=_('Offer "{offer_title}" submitted by {advertiser} requires review.').format(
                    offer_title=offer.title,
                    advertiser=offer.advertiser.company_name
                ),
                priority='high',
                action_url=f'/admin/advertiser/offer/{offer.id}/',
                action_text=_('Review Offer')
            )
    
    def _send_offer_submitted_notification(self, advertiser, offer: AdvertiserOffer, notes: str):
        """Send offer submitted notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='offer_created',
            title=_('Offer Submitted for Review'),
            message=_('Your offer "{offer_title}" has been submitted for review.').format(
                offer_title=offer.title
            ),
            priority='medium',
            action_url=f'/advertiser/offers/{offer.id}/',
            action_text=_('View Offer')
        )
    
    def _send_offer_approved_notification(self, advertiser, offer: AdvertiserOffer, notes: str):
        """Send offer approved notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='offer_approved',
            title=_('Offer Approved'),
            message=_('Your offer "{offer_title}" has been approved and is now active.').format(
                offer_title=offer.title
            ),
            priority='high',
            action_url=f'/advertiser/offers/{offer.id}/',
            action_text=_('View Offer')
        )
    
    def _send_offer_rejected_notification(self, advertiser, offer: AdvertiserOffer, reason: str, notes: str):
        """Send offer rejected notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='offer_rejected',
            title=_('Offer Rejected'),
            message=_('Your offer "{offer_title}" has been rejected. Reason: {reason}').format(
                offer_title=offer.title,
                reason=reason
            ),
            priority='high',
            action_url=f'/advertiser/offers/{offer.id}/',
            action_text=_('View Offer')
        )
    
    def _send_offer_paused_notification(self, advertiser, offer: AdvertiserOffer, reason: str):
        """Send offer paused notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='offer_created',
            title=_('Offer Paused'),
            message=_('Your offer "{offer_title}" has been paused.').format(
                offer_title=offer.title
            ),
            priority='medium',
            action_url=f'/advertiser/offers/{offer.id}/',
            action_text=_('View Offer')
        )
    
    def _send_offer_resumed_notification(self, advertiser, offer: AdvertiserOffer):
        """Send offer resumed notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='offer_approved',
            title=_('Offer Resumed'),
            message=_('Your offer "{offer_title}" has been resumed and is now active.').format(
                offer_title=offer.title
            ),
            priority='medium',
            action_url=f'/advertiser/offers/{offer.id}/',
            action_text=_('View Offer')
        )
    
    def _send_offer_expired_notification(self, advertiser, offer: AdvertiserOffer, reason: str):
        """Send offer expired notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='offer_rejected',
            title=_('Offer Expired'),
            message=_('Your offer "{offer_title}" has expired.').format(
                offer_title=offer.title
            ),
            priority='medium',
            action_url=f'/advertiser/offers/{offer.id}/report/',
            action_text=_('View Report')
        )
