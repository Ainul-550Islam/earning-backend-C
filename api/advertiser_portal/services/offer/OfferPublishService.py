"""
Offer Publish Service

Service for publishing offers to the offer network,
including distribution, visibility management, and syndication.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.offer import AdvertiserOffer
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class OfferPublishService:
    """
    Service for publishing offers to the offer network.
    
    Handles offer distribution, visibility management,
    and network syndication.
    """
    
    def __init__(self):
        self.logger = logger
    
    def publish_offer(self, offer: AdvertiserOffer, publisher: User, publish_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Publish offer to the offer network.
        
        Args:
            offer: Offer instance to publish
            publisher: User publishing the offer
            publish_config: Publishing configuration
            
        Returns:
            Dict[str, Any]: Publishing results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate offer can be published
                self._validate_offer_for_publishing(offer)
                
                # Get or create publish configuration
                config = publish_config or self._get_default_publish_config()
                
                # Publish to network
                publish_result = self._publish_to_network(offer, config)
                
                # Update offer status
                offer.status = 'active'
                offer.save()
                
                # Store publishing metadata
                metadata = offer.metadata or {}
                metadata['publishing'] = {
                    'published_by': publisher.id,
                    'published_at': timezone.now().isoformat(),
                    'config': config,
                    'result': publish_result,
                }
                offer.metadata = metadata
                offer.save()
                
                # Send notifications
                self._send_published_notification(offer, publish_result)
                
                self.logger.info(f"Published offer to network: {offer.title}")
                return publish_result
                
        except Exception as e:
            self.logger.error(f"Error publishing offer: {e}")
            raise ValidationError(f"Failed to publish offer: {str(e)}")
    
    def unpublish_offer(self, offer: AdvertiserOffer, unpublisher: User, reason: str = None) -> Dict[str, Any]:
        """
        Unpublish offer from the offer network.
        
        Args:
            offer: Offer instance to unpublish
            unpublisher: User unpublishing the offer
            reason: Reason for unpublishing
            
        Returns:
            Dict[str, Any]: Unpublishing results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                if offer.status != 'active':
                    raise ValidationError("Only active offers can be unpublished")
                
                # Unpublish from network
                unpublish_result = self._unpublish_from_network(offer)
                
                # Update offer status
                offer.status = 'paused'
                offer.save()
                
                # Store unpublishing metadata
                metadata = offer.metadata or {}
                metadata['unpublishing'] = {
                    'unpublished_by': unpublisher.id,
                    'unpublished_at': timezone.now().isoformat(),
                    'reason': reason,
                    'result': unpublish_result,
                }
                offer.metadata = metadata
                offer.save()
                
                # Send notifications
                self._send_unpublished_notification(offer, reason)
                
                self.logger.info(f"Unpublished offer from network: {offer.title}")
                return unpublish_result
                
        except Exception as e:
            self.logger.error(f"Error unpublishing offer: {e}")
            raise ValidationError(f"Failed to unpublish offer: {str(e)}")
    
    def update_offer_visibility(self, offer: AdvertiserOffer, visibility_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update offer visibility settings.
        
        Args:
            offer: Offer instance
            visibility_config: Visibility configuration
            
        Returns:
            Dict[str, Any]: Update results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate visibility config
                self._validate_visibility_config(visibility_config)
                
                # Update visibility in network
                update_result = self._update_network_visibility(offer, visibility_config)
                
                # Store visibility metadata
                metadata = offer.metadata or {}
                metadata['visibility'] = {
                    'updated_at': timezone.now().isoformat(),
                    'config': visibility_config,
                    'result': update_result,
                }
                offer.metadata = metadata
                offer.save()
                
                # Send notification if significant changes
                if self._is_significant_visibility_change(visibility_config):
                    self._send_visibility_updated_notification(offer, visibility_config)
                
                self.logger.info(f"Updated offer visibility: {offer.title}")
                return update_result
                
        except Exception as e:
            self.logger.error(f"Error updating offer visibility: {e}")
            raise ValidationError(f"Failed to update offer visibility: {str(e)}")
    
    def get_publishing_status(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """
        Get publishing status for offer.
        
        Args:
            offer: Offer instance
            
        Returns:
            Dict[str, Any]: Publishing status
        """
        try:
            publishing_metadata = offer.metadata.get('publishing', {}) if offer.metadata else {}
            
            return {
                'offer_id': offer.id,
                'offer_title': offer.title,
                'is_published': offer.status == 'active',
                'published_at': publishing_metadata.get('published_at'),
                'published_by': publishing_metadata.get('published_by'),
                'publish_config': publishing_metadata.get('config', {}),
                'publish_result': publishing_metadata.get('result', {}),
                'network_reach': self._calculate_network_reach(offer),
                'visibility_score': self._calculate_visibility_score(offer),
                'distribution_channels': self._get_distribution_channels(offer),
                'performance_metrics': self._get_publishing_performance(offer),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting publishing status: {e}")
            raise ValidationError(f"Failed to get publishing status: {str(e)}")
    
    def get_published_offers(self, advertiser=None, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get published offers with filtering.
        
        Args:
            advertiser: Optional advertiser filter
            filters: Additional filter criteria
            
        Returns:
            List[Dict[str, Any]]: Published offers
        """
        try:
            queryset = AdvertiserOffer.objects.filter(status='active')
            
            if advertiser:
                queryset = queryset.filter(advertiser=advertiser)
            
            if filters:
                if 'payout_type' in filters:
                    queryset = queryset.filter(payout_type=filters['payout_type'])
                
                if 'is_private' in filters:
                    queryset = queryset.filter(is_private=filters['is_private'])
                
                if 'min_payout' in filters:
                    queryset = queryset.filter(payout_amount__gte=filters['min_payout'])
                
                if 'max_payout' in filters:
                    queryset = queryset.filter(payout_amount__lte=filters['max_payout'])
                
                if 'countries' in filters:
                    queryset = queryset.filter(
                        models.Q(allowed_countries__overlap=filters['countries']) |
                        models.Q(allowed_countries__len=0)
                    )
            
            offers = queryset.select_related('advertiser').order_by('-created_at')
            
            published_offers = []
            for offer in offers:
                offer_data = {
                    'id': offer.id,
                    'title': offer.title,
                    'description': offer.description,
                    'advertiser': offer.advertiser.company_name,
                    'payout_type': offer.payout_type,
                    'payout_amount': float(offer.payout_amount),
                    'currency': offer.currency,
                    'is_private': offer.is_private,
                    'allowed_countries': offer.allowed_countries,
                    'blocked_countries': offer.blocked_countries,
                    'allowed_devices': offer.allowed_devices,
                    'blocked_devices': offer.blocked_devices,
                    'quality_score': float(offer.quality_score),
                    'conversion_rate': float(offer.conversion_rate),
                    'created_at': offer.created_at.isoformat(),
                    'start_date': offer.start_date.isoformat() if offer.start_date else None,
                    'end_date': offer.end_date.isoformat() if offer.end_date else None,
                    'requirements_count': offer.requirements.count(),
                    'creatives_count': offer.creatives.count(),
                    'publishing_status': self.get_publishing_status(offer),
                }
                published_offers.append(offer_data)
            
            return published_offers
            
        except Exception as e:
            self.logger.error(f"Error getting published offers: {e}")
            return []
    
    def syndicate_offer(self, offer: AdvertiserOffer, syndication_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Syndicate offer to external networks.
        
        Args:
            offer: Offer instance to syndicate
            syndication_config: Syndication configuration
            
        Returns:
            Dict[str, Any]: Syndication results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate syndication config
                self._validate_syndication_config(syndication_config)
                
                # Syndicate to networks
                syndication_results = self._syndicate_to_networks(offer, syndication_config)
                
                # Store syndication metadata
                metadata = offer.metadata or {}
                metadata['syndication'] = {
                    'syndicated_at': timezone.now().isoformat(),
                    'config': syndication_config,
                    'results': syndication_results,
                }
                offer.metadata = metadata
                offer.save()
                
                # Send notification
                self._send_syndicated_notification(offer, syndication_results)
                
                self.logger.info(f"Syndicated offer: {offer.title}")
                return syndication_results
                
        except Exception as e:
            self.logger.error(f"Error syndicating offer: {e}")
            raise ValidationError(f"Failed to syndicate offer: {str(e)}")
    
    def get_syndication_status(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """
        Get syndication status for offer.
        
        Args:
            offer: Offer instance
            
        Returns:
            Dict[str, Any]: Syndication status
        """
        try:
            syndication_metadata = offer.metadata.get('syndication', {}) if offer.metadata else {}
            
            return {
                'offer_id': offer.id,
                'offer_title': offer.title,
                'is_syndicated': bool(syndication_metadata),
                'syndicated_at': syndication_metadata.get('syndicated_at'),
                'syndication_config': syndication_metadata.get('config', {}),
                'syndication_results': syndication_metadata.get('results', {}),
                'active_networks': self._get_active_syndication_networks(offer),
                'syndication_performance': self._get_syndication_performance(offer),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting syndication status: {e}")
            raise ValidationError(f"Failed to get syndication status: {str(e)}")
    
    def _validate_offer_for_publishing(self, offer: AdvertiserOffer):
        """Validate offer can be published."""
        if offer.status not in ['draft', 'pending_review', 'rejected']:
            raise ValidationError("Offer must be in draft, pending review, or rejected status")
        
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
        
        # Check advertiser status
        if offer.advertiser.verification_status != 'verified':
            raise ValidationError("Advertiser must be verified to publish offers")
        
        if offer.advertiser.status != 'active':
            raise ValidationError("Advertiser account must be active")
    
    def _get_default_publish_config(self) -> Dict[str, Any]:
        """Get default publishing configuration."""
        return {
            'visibility': 'public',
            'geographic_restriction': 'allowed_countries',
            'device_restriction': 'all',
            'category_restriction': 'none',
            'quality_threshold': 50,
            'auto_approve_publishers': False,
            'max_daily_budget': None,
            'enable_syndication': False,
            'syndication_networks': [],
        }
    
    def _publish_to_network(self, offer: AdvertiserOffer, config: Dict[str, Any]) -> Dict[str, Any]:
        """Publish offer to network (placeholder implementation)."""
        # This would implement actual network publishing logic
        return {
            'success': True,
            'network_id': f'network_{offer.id}',
            'published_at': timezone.now().isoformat(),
            'visibility': config.get('visibility', 'public'),
            'estimated_reach': self._estimate_reach(offer, config),
            'distribution_channels': ['web', 'mobile', 'api'],
        }
    
    def _unpublish_from_network(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Unpublish offer from network (placeholder implementation)."""
        return {
            'success': True,
            'unpublished_at': timezone.now().isoformat(),
            'reason': 'Manual unpublish',
        }
    
    def _update_network_visibility(self, offer: AdvertiserOffer, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update offer visibility in network (placeholder implementation)."""
        return {
            'success': True,
            'updated_at': timezone.now().isoformat(),
            'visibility': config.get('visibility', 'public'),
            'changes_applied': True,
        }
    
    def _validate_visibility_config(self, config: Dict[str, Any]):
        """Validate visibility configuration."""
        valid_visibilities = ['public', 'private', 'restricted']
        if config.get('visibility') not in valid_visibilities:
            raise ValidationError(f"Invalid visibility: {config.get('visibility')}")
    
    def _is_significant_visibility_change(self, config: Dict[str, Any]) -> bool:
        """Check if visibility change is significant."""
        # This would implement logic to determine significance
        return config.get('visibility') in ['public', 'private']
    
    def _calculate_network_reach(self, offer: AdvertiserOffer) -> int:
        """Calculate network reach for offer."""
        # This would implement actual reach calculation
        base_reach = 10000
        
        # Adjust for quality score
        quality_multiplier = offer.quality_score / 100
        
        # Adjust for payout amount
        payout_multiplier = min(offer.payout_amount / 10, 3)
        
        return int(base_reach * quality_multiplier * payout_multiplier)
    
    def _calculate_visibility_score(self, offer: AdvertiserOffer) -> float:
        """Calculate visibility score for offer."""
        score = 50.0  # Base score
        
        # Quality score impact
        score += offer.quality_score * 0.3
        
        # Conversion rate impact
        score += offer.conversion_rate * 0.2
        
        # Payout amount impact
        score += min(offer.payout_amount / 100, 20)
        
        return min(score, 100.0)
    
    def _get_distribution_channels(self, offer: AdvertiserOffer) -> List[str]:
        """Get distribution channels for offer."""
        channels = ['web', 'mobile']
        
        if offer.creatives.filter(creative_type='video').exists():
            channels.append('video')
        
        if not offer.is_private:
            channels.append('api')
        
        return channels
    
    def _get_publishing_performance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Get publishing performance metrics."""
        # This would implement actual performance tracking
        return {
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'revenue': 0.0,
            'ctr': 0.0,
            'conversion_rate': 0.0,
        }
    
    def _validate_syndication_config(self, config: Dict[str, Any]):
        """Validate syndication configuration."""
        valid_networks = ['network_a', 'network_b', 'network_c']
        
        networks = config.get('networks', [])
        for network in networks:
            if network not in valid_networks:
                raise ValidationError(f"Invalid syndication network: {network}")
    
    def _syndicate_to_networks(self, offer: AdvertiserOffer, config: Dict[str, Any]) -> Dict[str, Any]:
        """Syndicate offer to external networks (placeholder implementation)."""
        results = {}
        
        for network in config.get('networks', []):
            results[network] = {
                'success': True,
                'syndicated_at': timezone.now().isoformat(),
                'network_offer_id': f'{network}_{offer.id}',
                'estimated_reach': self._estimate_network_reach(network, offer),
            }
        
        return {
            'total_networks': len(results),
            'successful_networks': len([r for r in results.values() if r['success']]),
            'results': results,
        }
    
    def _estimate_reach(self, offer: AdvertiserOffer, config: Dict[str, Any]) -> int:
        """Estimate reach for offer."""
        base_reach = 5000
        
        # Adjust for visibility
        if config.get('visibility') == 'public':
            base_reach *= 2
        elif config.get('visibility') == 'private':
            base_reach *= 0.5
        
        return int(base_reach)
    
    def _estimate_network_reach(self, network: str, offer: AdvertiserOffer) -> int:
        """Estimate reach for specific network."""
        # This would implement network-specific reach estimation
        network_multipliers = {
            'network_a': 1.5,
            'network_b': 1.2,
            'network_c': 0.8,
        }
        
        base_reach = 2000
        multiplier = network_multipliers.get(network, 1.0)
        
        return int(base_reach * multiplier)
    
    def _get_active_syndication_networks(self, offer: AdvertiserOffer) -> List[str]:
        """Get active syndication networks for offer."""
        syndication_metadata = offer.metadata.get('syndication', {}) if offer.metadata else {}
        results = syndication_metadata.get('results', {})
        
        return [network for network, result in results.items() if result.get('success')]
    
    def _get_syndication_performance(self, offer: AdvertiserOffer) -> Dict[str, Any]:
        """Get syndication performance metrics."""
        # This would implement actual syndication performance tracking
        return {
            'total_impressions': 0,
            'total_clicks': 0,
            'total_conversions': 0,
            'total_revenue': 0.0,
            'network_performance': {},
        }
    
    def _send_published_notification(self, offer: AdvertiserOffer, publish_result: Dict[str, Any]):
        """Send offer published notification."""
        AdvertiserNotification.objects.create(
            advertiser=offer.advertiser,
            type='offer_approved',
            title=_('Offer Published'),
            message=_('Your offer "{offer_title}" has been published to the network.').format(
                offer_title=offer.title
            ),
            priority='high',
            action_url=f'/advertiser/offers/{offer.id}/',
            action_text=_('View Offer')
        )
    
    def _send_unpublished_notification(self, offer: AdvertiserOffer, reason: str):
        """Send offer unpublished notification."""
        AdvertiserNotification.objects.create(
            advertiser=offer.advertiser,
            type='offer_rejected',
            title=_('Offer Unpublished'),
            message=_('Your offer "{offer_title}" has been unpublished from the network.').format(
                offer_title=offer.title
            ),
            priority='medium',
            action_url=f'/advertiser/offers/{offer.id}/',
            action_text=_('View Offer')
        )
    
    def _send_visibility_updated_notification(self, offer: AdvertiserOffer, config: Dict[str, Any]):
        """Send visibility updated notification."""
        AdvertiserNotification.objects.create(
            advertiser=offer.advertiser,
            type='offer_approved',
            title=_('Offer Visibility Updated'),
            message=_('Your offer "{offer_title}" visibility has been updated.').format(
                offer_title=offer.title
            ),
            priority='low',
            action_url=f'/advertiser/offers/{offer.id}/visibility/',
            action_text=_('View Settings')
        )
    
    def _send_syndicated_notification(self, offer: AdvertiserOffer, syndication_results: Dict[str, Any]):
        """Send offer syndicated notification."""
        successful_networks = syndication_results.get('successful_networks', 0)
        
        AdvertiserNotification.objects.create(
            advertiser=offer.advertiser,
            type='offer_approved',
            title=_('Offer Syndicated'),
            message=_('Your offer "{offer_title}" has been syndicated to {networks} networks.').format(
                offer_title=offer.title,
                networks=successful_networks
            ),
            priority='medium',
            action_url=f'/advertiser/offers/{offer.id}/syndication/',
            action_text=_('View Syndication')
        )
