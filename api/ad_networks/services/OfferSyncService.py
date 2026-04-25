"""
api/ad_networks/services/OfferSyncService.py
Service for syncing offers from network APIs
SaaS-ready with tenant support
"""

import logging
import json
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from api.ad_networks.models import AdNetwork, Offer, NetworkAPILog, NetworkHealthCheck
from api.ad_networks.choices import OfferStatus, NetworkStatus
from api.ad_networks.constants import (
    API_TIMEOUT_SECONDS,
    API_RETRY_ATTEMPTS,
    OFFER_CACHE_TTL,
    CACHE_KEY_PATTERNS
)

logger = logging.getLogger(__name__)


class OfferSyncService:
    """
    Service for syncing offers from network APIs
    """
    
    def __init__(self, network=None, tenant_id=None):
        self.network = network
        self.tenant_id = tenant_id
        self.session = requests.Session()
        self.session.timeout = API_TIMEOUT_SECONDS
        
        # Setup session headers
        self.session.headers.update({
            'User-Agent': 'AdNetworks-Sync/1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def sync_all_offers(self) -> Dict:
        """
        Sync all offers from the network
        """
        if not self.network:
            raise ValueError("Network is required for sync")
        
        logger.info(f"Starting offer sync for network: {self.network.name}")
        
        try:
            # Check network health first
            if not self._check_network_health():
                return {
                    'success': False,
                    'error': 'Network health check failed',
                    'offers_synced': 0
                }
            
            # Get offers from network API
            offers_data = self._fetch_offers_from_api()
            
            if not offers_data:
                return {
                    'success': True,
                    'message': 'No offers available',
                    'offers_synced': 0
                }
            
            # Process offers
            result = self._process_offers_data(offers_data)
            
            # Update network sync status
            self._update_network_sync_status(result['offers_synced'])
            
            # Clear caches
            self._clear_relevant_caches()
            
            logger.info(f"Offer sync completed for {self.network.name}: {result['offers_synced']} offers")
            
            return result
            
        except Exception as e:
            logger.error(f"Offer sync failed for {self.network.name}: {str(e)}")
            self._log_api_error('sync_all_offers', str(e))
            
            return {
                'success': False,
                'error': str(e),
                'offers_synced': 0
            }
    
    def sync_single_offer(self, external_id: str) -> Dict:
        """
        Sync a single offer by external ID
        """
        try:
            offer_data = self._fetch_single_offer_from_api(external_id)
            
            if not offer_data:
                return {
                    'success': False,
                    'error': f'Offer {external_id} not found in API'
                }
            
            # Process single offer
            result = self._process_single_offer_data(offer_data)
            
            logger.info(f"Single offer sync completed: {external_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Single offer sync failed for {external_id}: {str(e)}")
            self._log_api_error('sync_single_offer', str(e))
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _check_network_health(self) -> bool:
        """
        Check if network is healthy
        """
        try:
            health_url = self._get_health_check_url()
            if not health_url:
                return True  # Assume healthy if no health check URL
            
            response = self.session.get(health_url)
            is_healthy = response.status_code == 200
            
            # Log health check
            NetworkHealthCheck.objects.create(
                network=self.network,
                is_healthy=is_healthy,
                check_type='api_call',
                endpoint_checked=health_url,
                response_time_ms=int(response.elapsed.total_seconds() * 1000),
                error=None if is_healthy else f"HTTP {response.status_code}"
            )
            
            return is_healthy
            
        except Exception as e:
            logger.warning(f"Health check failed for {self.network.name}: {str(e)}")
            
            # Log failed health check
            NetworkHealthCheck.objects.create(
                network=self.network,
                is_healthy=False,
                check_type='api_call',
                endpoint_checked=health_url or 'unknown',
                error=str(e)
            )
            
            return False
    
    def _fetch_offers_from_api(self) -> Optional[List[Dict]]:
        """
        Fetch offers from network API
        """
        offers_url = self._get_offers_url()
        if not offers_url:
            logger.warning(f"No offers URL configured for {self.network.name}")
            return None
        
        for attempt in range(API_RETRY_ATTEMPTS):
            try:
                response = self.session.get(offers_url)
                
                # Log API call
                NetworkAPILog.objects.create(
                    network=self.network,
                    endpoint='offers',
                    method='GET',
                    request_data={},
                    response_data={'offers_count': len(response.json()) if response.status_code == 200 else 0},
                    status_code=response.status_code,
                    is_success=response.status_code == 200,
                    latency_ms=int(response.elapsed.total_seconds() * 1000),
                    tenant_id=self.tenant_id
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"API returned status {response.status_code} for {self.network.name}")
                    
            except Exception as e:
                logger.warning(f"API attempt {attempt + 1} failed for {self.network.name}: {str(e)}")
                if attempt == API_RETRY_ATTEMPTS - 1:
                    raise
        
        return None
    
    def _fetch_single_offer_from_api(self, external_id: str) -> Optional[Dict]:
        """
        Fetch single offer from network API
        """
        offer_url = self._get_single_offer_url(external_id)
        if not offer_url:
            return None
        
        try:
            response = self.session.get(offer_url)
            
            # Log API call
            NetworkAPILog.objects.create(
                network=self.network,
                endpoint=f'offers/{external_id}',
                method='GET',
                request_data={},
                response_data=response.json() if response.status_code == 200 else {},
                status_code=response.status_code,
                is_success=response.status_code == 200,
                latency_ms=int(response.elapsed.total_seconds() * 1000),
                tenant_id=self.tenant_id
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Single offer API returned status {response.status_code}")
                
        except Exception as e:
            logger.error(f"Single offer API failed for {external_id}: {str(e)}")
            self._log_api_error('fetch_single_offer', str(e))
        
        return None
    
    def _process_offers_data(self, offers_data: List[Dict]) -> Dict:
        """
        Process offers data and update database
        """
        if not offers_data:
            return {
                'success': True,
                'offers_synced': 0,
                'offers_updated': 0,
                'offers_created': 0,
                'offers_failed': 0
            }
        
        offers_synced = 0
        offers_updated = 0
        offers_created = 0
        offers_failed = 0
        
        with transaction.atomic():
            for offer_data in offers_data:
                try:
                    result = self._process_single_offer_data(offer_data)
                    
                    if result['success']:
                        offers_synced += 1
                        if result.get('created'):
                            offers_created += 1
                        elif result.get('updated'):
                            offers_updated += 1
                    else:
                        offers_failed += 1
                        
                except Exception as e:
                    logger.error(f"Failed to process offer: {str(e)}")
                    offers_failed += 1
                    continue
        
        return {
            'success': True,
            'offers_synced': offers_synced,
            'offers_updated': offers_updated,
            'offers_created': offers_created,
            'offers_failed': offers_failed
        }
    
    def _process_single_offer_data(self, offer_data: Dict) -> Dict:
        """
        Process single offer data
        """
        try:
            external_id = offer_data.get('external_id')
            if not external_id:
                return {
                    'success': False,
                    'error': 'Missing external_id'
                }
            
            # Find existing offer
            offer = Offer.objects.filter(
                ad_network=self.network,
                external_id=external_id
            ).first()
            
            # Prepare offer fields
            offer_fields = self._prepare_offer_fields(offer_data)
            
            if offer:
                # Update existing offer
                created = False
                updated = False
                
                for field, value in offer_fields.items():
                    if getattr(offer, field) != value:
                        setattr(offer, field, value)
                        updated = True
                
                if updated:
                    offer.save()
                
                return {
                    'success': True,
                    'created': False,
                    'updated': updated,
                    'offer_id': offer.id
                }
            else:
                # Create new offer
                offer_fields.update({
                    'ad_network': self.network,
                    'external_id': external_id,
                })
                
                offer = Offer.objects.create(**offer_fields)
                
                return {
                    'success': True,
                    'created': True,
                    'updated': False,
                    'offer_id': offer.id
                }
                
        except Exception as e:
            logger.error(f"Failed to process offer data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _prepare_offer_fields(self, offer_data: Dict) -> Dict:
        """
        Prepare offer fields from API data
        """
        return {
            'title': offer_data.get('title', '')[:255],
            'description': offer_data.get('description', ''),
            'reward_amount': Decimal(str(offer_data.get('reward_amount', 0))),
            'network_payout': Decimal(str(offer_data.get('payout', 0))),
            'click_url': offer_data.get('click_url', ''),
            'tracking_url': offer_data.get('tracking_url', ''),
            'preview_url': offer_data.get('preview_url', ''),
            'thumbnail': offer_data.get('thumbnail', ''),
            'preview_images': offer_data.get('preview_images', []),
            'countries': offer_data.get('countries', []),
            'platforms': offer_data.get('platforms', ['android', 'ios', 'web']),
            'device_type': offer_data.get('device_type', 'any'),
            'difficulty': offer_data.get('difficulty', 'easy'),
            'estimated_time': offer_data.get('estimated_time', 5),
            'steps_required': offer_data.get('steps_required', 1),
            'max_conversions': offer_data.get('max_conversions'),
            'max_daily_conversions': offer_data.get('max_daily_conversions'),
            'user_daily_limit': offer_data.get('user_daily_limit', 1),
            'user_lifetime_limit': offer_data.get('user_lifetime_limit', 1),
            'terms_url': offer_data.get('terms_url', ''),
            'privacy_url': offer_data.get('privacy_url', ''),
            'status': 'active' if offer_data.get('is_available', True) else 'paused',
            'is_featured': offer_data.get('is_featured', False),
            'is_hot': offer_data.get('is_hot', False),
            'is_new': offer_data.get('is_new', True),
            'is_exclusive': offer_data.get('is_exclusive', False),
            'requires_approval': offer_data.get('requires_approval', False),
            'expires_at': self._parse_datetime(offer_data.get('expires_at')),
            'starts_at': self._parse_datetime(offer_data.get('starts_at')),
            'metadata': offer_data.get('metadata', {}),
            'tags': offer_data.get('tags', []),
            'requirements': offer_data.get('requirements', []),
        }
    
    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """
        Parse datetime string from API
        """
        if not datetime_str:
            return None
        
        try:
            # Try ISO format first
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try Unix timestamp
                return datetime.fromtimestamp(float(datetime_str))
            except (ValueError, OSError):
                logger.warning(f"Could not parse datetime: {datetime_str}")
                return None
    
    def _update_network_sync_status(self, offers_synced: int):
        """
        Update network sync status
        """
        try:
            self.network.last_sync = timezone.now()
            self.network.next_sync = timezone.now() + timedelta(hours=1)
            self.network.save(update_fields=['last_sync', 'next_sync'])
            
            logger.info(f"Updated sync status for {self.network.name}: {offers_synced} offers")
            
        except Exception as e:
            logger.error(f"Failed to update network sync status: {str(e)}")
    
    def _clear_relevant_caches(self):
        """
        Clear relevant caches after sync
        """
        try:
            # Clear network offers cache
            cache.delete(f'network_{self.network.id}_offers')
            
            # Clear offer list cache
            cache.delete_pattern('offer_list_*')
            
            # Clear category offers cache
            cache.delete_pattern('category_*_offers')
            
            logger.info(f"Cleared caches for network {self.network.name}")
            
        except Exception as e:
            logger.error(f"Failed to clear caches: {str(e)}")
    
    def _get_offers_url(self) -> Optional[str]:
        """
        Get offers URL for network
        """
        if not self.network.base_url:
            return None
        
        # Network-specific URL patterns
        url_patterns = {
            'adscend': f'{self.network.base_url}/v1/offers',
            'offertoro': f'{self.network.base_url}/v1/offers',
            'adgem': f'{self.network.base_url}/v1/offers',
            'ayetstudios': f'{self.network.base_url}/v1/offers',
            'pollfish': f'{self.network.base_url}/v1/surveys',
            'cpxresearch': f'{self.network.base_url}/v1/surveys',
        }
        
        return url_patterns.get(self.network.network_type)
    
    def _get_single_offer_url(self, external_id: str) -> Optional[str]:
        """
        Get single offer URL for network
        """
        offers_url = self._get_offers_url()
        if not offers_url:
            return None
        
        return f"{offers_url.rstrip('/')}/{external_id}"
    
    def _get_health_check_url(self) -> Optional[str]:
        """
        Get health check URL for network
        """
        if not self.network.base_url:
            return None
        
        # Network-specific health check URLs
        health_patterns = {
            'adscend': f'{self.network.base_url}/v1/ping',
            'offertoro': f'{self.network.base_url}/v1/ping',
            'adgem': f'{self.network.base_url}/v1/ping',
            'ayetstudios': f'{self.network.base_url}/v1/ping',
            'pollfish': f'{self.network.base_url}/v1/ping',
            'cpxresearch': f'{self.network.base_url}/v1/ping',
        }
        
        return health_patterns.get(self.network.network_type)
    
    def _log_api_error(self, operation: str, error_message: str):
        """
        Log API error
        """
        try:
            NetworkAPILog.objects.create(
                network=self.network,
                endpoint=operation,
                method='SYNC_SERVICE',
                request_data={},
                response_data={'error': error_message},
                status_code=500,
                is_success=False,
                error_message=error_message,
                error_type='SYNC_SERVICE_ERROR',
                tenant_id=self.tenant_id
            )
        except Exception as e:
            logger.error(f"Failed to log API error: {str(e)}")
    
    @classmethod
    def sync_network_by_type(cls, network_type: str, tenant_id: str = None) -> Dict:
        """
        Sync all networks of a specific type
        """
        networks = AdNetwork.objects.filter(
            network_type=network_type,
            is_active=True
        )
        
        if tenant_id:
            networks = networks.filter(tenant_id=tenant_id)
        
        results = []
        total_synced = 0
        
        for network in networks:
            service = cls(network=network, tenant_id=tenant_id)
            result = service.sync_all_offers()
            results.append({
                'network_id': network.id,
                'network_name': network.name,
                'result': result
            })
            total_synced += result.get('offers_synced', 0)
        
        return {
            'success': True,
            'network_type': network_type,
            'networks_processed': len(results),
            'total_offers_synced': total_synced,
            'results': results
        }
    
    @classmethod
    def get_sync_status(cls, network_id: int) -> Dict:
        """
        Get sync status for a network
        """
        try:
            network = AdNetwork.objects.get(id=network_id)
            
            return {
                'network_id': network.id,
                'network_name': network.name,
                'last_sync': network.last_sync,
                'next_sync': network.next_sync,
                'is_sync_due': network.next_sync and network.next_sync <= timezone.now(),
                'sync_overdue_minutes': int((timezone.now() - network.next_sync).total_seconds() / 60) if network.next_sync and network.next_sync < timezone.now() else 0
            }
            
        except AdNetwork.DoesNotExist:
            return {
                'error': f'Network with ID {network_id} not found'
            }
