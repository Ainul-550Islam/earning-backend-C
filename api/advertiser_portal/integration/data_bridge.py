"""
Data Bridge Utility for Legacy System Integration

This module provides seamless communication between the legacy system
and the new advertiser_portal, handling data transformation and
synchronization for shared entities.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.core.cache import cache
from django.db import transaction, connections
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

from .performance_monitor import PerformanceMonitor
from .event_bus import EventBus
from ..models.advertiser import Advertiser, AdvertiserProfile
from ..models.billing import AdvertiserWallet
from ..models.campaign import AdCampaign
from ..models.offer import AdvertiserOffer
from ..models.tracking import Conversion
from ..exceptions import *
from ..utils import *

logger = logging.getLogger(__name__)


@dataclass
class DataSyncResult:
    """Result of data synchronization operation."""
    success: bool
    entity_type: str
    entity_id: str
    legacy_id: Optional[str] = None
    new_id: Optional[str] = None
    synced_fields: List[str] = None
    errors: List[str] = None
    sync_time: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.synced_fields is None:
            self.synced_fields = []
        if self.errors is None:
            self.errors = []
        if self.timestamp is None:
            self.timestamp = timezone.now()


class DataBridge:
    """
    High-performance data bridge for legacy system integration.
    
    Handles bidirectional data synchronization with <50ms latency goal
    for critical operations and comprehensive monitoring.
    """
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.event_bus = EventBus()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.sync_mappings = self._initialize_sync_mappings()
        self.field_transformers = self._initialize_field_transformers()
        self.validation_rules = self._initialize_validation_rules()
        
        # Performance targets
        self.CRITICAL_LATENCY_MS = 50
        self.STANDARD_LATENCY_MS = 200
        self.BATCH_SIZE = 100
        
    def _initialize_sync_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize field mappings between legacy and new systems."""
        return {
            'advertiser': {
                'legacy_id': 'id',
                'company_name': 'company_name',
                'industry': 'industry',
                'website': 'website',
                'contact_email': 'contact_email',
                'contact_phone': 'contact_phone',
                'description': 'description',
                'status': 'verification_status',
                'created_at': 'created_at',
                'updated_at': 'updated_at'
            },
            'advertiser_profile': {
                'legacy_id': 'id',
                'advertiser_id': 'advertiser_id',
                'logo_url': 'logo_url',
                'company_address': 'company_address',
                'company_phone': 'company_phone',
                'company_size': 'company_size',
                'annual_revenue': 'annual_revenue',
                'target_audience': 'target_audience',
                'marketing_budget': 'marketing_budget'
            },
            'wallet': {
                'legacy_id': 'id',
                'advertiser_id': 'advertiser_id',
                'balance': 'balance',
                'currency': 'currency',
                'auto_refill_enabled': 'auto_refill_enabled',
                'auto_refill_threshold': 'auto_refill_threshold',
                'auto_refill_amount': 'auto_refill_amount'
            },
            'campaign': {
                'legacy_id': 'id',
                'advertiser_id': 'advertiser_id',
                'name': 'name',
                'description': 'description',
                'status': 'status',
                'start_date': 'start_date',
                'end_date': 'end_date',
                'total_budget': 'total_budget',
                'daily_budget': 'daily_budget'
            },
            'offer': {
                'legacy_id': 'id',
                'advertiser_id': 'advertiser_id',
                'name': 'name',
                'description': 'description',
                'offer_type': 'offer_type',
                'pricing_model': 'pricing_model',
                'payout_amount': 'payout_amount',
                'status': 'status'
            }
        }
    
    def _initialize_field_transformers(self) -> Dict[str, Dict[str, Callable]]:
        """Initialize field transformers for data conversion."""
        return {
            'advertiser': {
                'status': lambda x: self._transform_status(x),
                'created_at': lambda x: self._parse_datetime(x),
                'updated_at': lambda x: self._parse_datetime(x)
            },
            'wallet': {
                'balance': lambda x: Decimal(str(x)) if x else Decimal('0'),
                'auto_refill_threshold': lambda x: Decimal(str(x)) if x else None,
                'auto_refill_amount': lambda x: Decimal(str(x)) if x else None
            },
            'campaign': {
                'total_budget': lambda x: Decimal(str(x)) if x else None,
                'daily_budget': lambda x: Decimal(str(x)) if x else None,
                'start_date': lambda x: self._parse_date(x),
                'end_date': lambda x: self._parse_date(x)
            },
            'offer': {
                'payout_amount': lambda x: Decimal(str(x)) if x else None
            }
        }
    
    def _initialize_validation_rules(self) -> Dict[str, List[Callable]]:
        """Initialize validation rules for entities."""
        return {
            'advertiser': [
                self._validate_required_fields(['company_name', 'contact_email']),
                self._validate_email_format('contact_email'),
                self._validate_url_format('website')
            ],
            'wallet': [
                self._validate_required_fields(['advertiser_id', 'balance']),
                self._validate_positive_amount('balance')
            ],
            'campaign': [
                self._validate_required_fields(['advertiser_id', 'name']),
                self._validate_date_range('start_date', 'end_date'),
                self._validate_positive_amount('total_budget', 'daily_budget')
            ],
            'offer': [
                self._validate_required_fields(['advertiser_id', 'name', 'offer_type']),
                self._validate_positive_amount('payout_amount')
            ]
        }
    
    async def sync_advertiser_profile(self, legacy_data: Dict[str, Any]) -> DataSyncResult:
        """
        Sync advertiser profile between legacy and new systems.
        
        Critical operation with <50ms latency target.
        """
        start_time = time.time()
        result = DataSyncResult(entity_type='advertiser_profile')
        
        try:
            with self.performance_monitor.measure('sync_advertiser_profile'):
                # Transform legacy data
                transformed_data = await self._transform_data('advertiser_profile', legacy_data)
                
                # Validate data
                validation_errors = await self._validate_data('advertiser_profile', transformed_data)
                if validation_errors:
                    result.errors.extend(validation_errors)
                    return result
                
                # Check if advertiser exists
                advertiser = await self._get_advertiser_by_legacy_id(legacy_data.get('id'))
                if not advertiser:
                    result.errors.append("Advertiser not found")
                    return result
                
                # Sync profile
                profile, created = await self._sync_profile(advertiser, transformed_data)
                
                result.success = True
                result.entity_id = str(profile.id)
                result.legacy_id = legacy_data.get('id')
                result.synced_fields = list(transformed_data.keys())
                
                # Emit sync event
                await self.event_bus.emit('advertiser_profile_synced', {
                    'profile_id': str(profile.id),
                    'advertiser_id': str(advertiser.id),
                    'sync_type': 'legacy_to_new'
                })
                
        except Exception as e:
            logger.error(f"Error syncing advertiser profile: {e}")
            result.errors.append(str(e))
        
        result.sync_time = (time.time() - start_time) * 1000
        return result
    
    async def sync_wallet_balance(self, legacy_data: Dict[str, Any]) -> DataSyncResult:
        """
        Sync wallet balance between legacy and new systems.
        
        Critical operation with <50ms latency target.
        """
        start_time = time.time()
        result = DataSyncResult(entity_type='wallet')
        
        try:
            with self.performance_monitor.measure('sync_wallet_balance'):
                # Transform legacy data
                transformed_data = await self._transform_data('wallet', legacy_data)
                
                # Validate data
                validation_errors = await self._validate_data('wallet', transformed_data)
                if validation_errors:
                    result.errors.extend(validation_errors)
                    return result
                
                # Get advertiser
                advertiser = await self._get_advertiser_by_legacy_id(legacy_data.get('advertiser_id'))
                if not advertiser:
                    result.errors.append("Advertiser not found")
                    return result
                
                # Sync wallet
                wallet, updated = await self._sync_wallet_balance(advertiser, transformed_data)
                
                result.success = True
                result.entity_id = str(wallet.id)
                result.legacy_id = legacy_data.get('id')
                result.synced_fields = ['balance'] if updated else []
                
                # Emit sync event
                if updated:
                    await self.event_bus.emit('wallet_balance_updated', {
                        'wallet_id': str(wallet.id),
                        'advertiser_id': str(advertiser.id),
                        'new_balance': float(wallet.balance),
                        'sync_type': 'legacy_to_new'
                    })
                
        except Exception as e:
            logger.error(f"Error syncing wallet balance: {e}")
            result.errors.append(str(e))
        
        result.sync_time = (time.time() - start_time) * 1000
        return result
    
    async def sync_campaign_data(self, legacy_data: Dict[str, Any]) -> DataSyncResult:
        """
        Sync campaign data between legacy and new systems.
        
        Standard operation with <200ms latency target.
        """
        start_time = time.time()
        result = DataSyncResult(entity_type='campaign')
        
        try:
            with self.performance_monitor.measure('sync_campaign_data'):
                # Transform legacy data
                transformed_data = await self._transform_data('campaign', legacy_data)
                
                # Validate data
                validation_errors = await self._validate_data('campaign', transformed_data)
                if validation_errors:
                    result.errors.extend(validation_errors)
                    return result
                
                # Get advertiser
                advertiser = await self._get_advertiser_by_legacy_id(legacy_data.get('advertiser_id'))
                if not advertiser:
                    result.errors.append("Advertiser not found")
                    return result
                
                # Sync campaign
                campaign, created = await self._sync_campaign(advertiser, transformed_data)
                
                result.success = True
                result.entity_id = str(campaign.id)
                result.legacy_id = legacy_data.get('id')
                result.synced_fields = list(transformed_data.keys())
                
                # Emit sync event
                event_type = 'campaign_created' if created else 'campaign_updated'
                await self.event_bus.emit(event_type, {
                    'campaign_id': str(campaign.id),
                    'advertiser_id': str(advertiser.id),
                    'sync_type': 'legacy_to_new'
                })
                
        except Exception as e:
            logger.error(f"Error syncing campaign data: {e}")
            result.errors.append(str(e))
        
        result.sync_time = (time.time() - start_time) * 1000
        return result
    
    async def sync_offer_data(self, legacy_data: Dict[str, Any]) -> DataSyncResult:
        """
        Sync offer data between legacy and new systems.
        
        Standard operation with <200ms latency target.
        """
        start_time = time.time()
        result = DataSyncResult(entity_type='offer')
        
        try:
            with self.performance_monitor.measure('sync_offer_data'):
                # Transform legacy data
                transformed_data = await self._transform_data('offer', legacy_data)
                
                # Validate data
                validation_errors = await self._validate_data('offer', transformed_data)
                if validation_errors:
                    result.errors.extend(validation_errors)
                    return result
                
                # Get advertiser
                advertiser = await self._get_advertiser_by_legacy_id(legacy_data.get('advertiser_id'))
                if not advertiser:
                    result.errors.append("Advertiser not found")
                    return result
                
                # Sync offer
                offer, created = await self._sync_offer(advertiser, transformed_data)
                
                result.success = True
                result.entity_id = str(offer.id)
                result.legacy_id = legacy_data.get('id')
                result.synced_fields = list(transformed_data.keys())
                
                # Emit sync event
                event_type = 'offer_created' if created else 'offer_updated'
                await self.event_bus.emit(event_type, {
                    'offer_id': str(offer.id),
                    'advertiser_id': str(advertiser.id),
                    'sync_type': 'legacy_to_new'
                })
                
        except Exception as e:
            logger.error(f"Error syncing offer data: {e}")
            result.errors.append(str(e))
        
        result.sync_time = (time.time() - start_time) * 1000
        return result
    
    async def batch_sync(self, sync_requests: List[Dict[str, Any]]) -> List[DataSyncResult]:
        """
        Batch sync multiple entities for improved performance.
        
        Processes entities in parallel while maintaining performance targets.
        """
        results = []
        
        # Group by entity type for optimized processing
        grouped_requests = {}
        for request in sync_requests:
            entity_type = request.get('entity_type')
            if entity_type not in grouped_requests:
                grouped_requests[entity_type] = []
            grouped_requests[entity_type].append(request)
        
        # Process each group
        for entity_type, requests in grouped_requests.items():
            if entity_type in ['advertiser_profile', 'wallet']:
                # Critical operations - process individually for latency
                for request in requests:
                    if entity_type == 'advertiser_profile':
                        result = await self.sync_advertiser_profile(request)
                    elif entity_type == 'wallet':
                        result = await self.sync_wallet_balance(request)
                    results.append(result)
            else:
                # Standard operations - process in parallel
                tasks = []
                for request in requests:
                    if entity_type == 'campaign':
                        task = self.sync_campaign_data(request)
                    elif entity_type == 'offer':
                        task = self.sync_offer_data(request)
                    else:
                        continue
                    tasks.append(task)
                
                if tasks:
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for batch_result in batch_results:
                        if isinstance(batch_result, Exception):
                            error_result = DataSyncResult(
                                entity_type=entity_type,
                                success=False,
                                errors=[str(batch_result)]
                            )
                            results.append(error_result)
                        else:
                            results.append(batch_result)
        
        return results
    
    async def get_sync_status(self, entity_type: str, legacy_id: str) -> Optional[Dict[str, Any]]:
        """Get synchronization status for an entity."""
        cache_key = f"sync_status_{entity_type}_{legacy_id}"
        cached_status = cache.get(cache_key)
        
        if cached_status:
            return cached_status
        
        # Determine sync status based on entity existence
        try:
            if entity_type == 'advertiser_profile':
                advertiser = await self._get_advertiser_by_legacy_id(legacy_id)
                if advertiser and hasattr(advertiser, 'advertiserprofile'):
                    status = {
                        'synced': True,
                        'entity_id': str(advertiser.advertiserprofile.id),
                        'last_sync': advertiser.advertiserprofile.updated_at,
                        'sync_type': 'profile'
                    }
                else:
                    status = {'synced': False}
            
            elif entity_type == 'wallet':
                advertiser = await self._get_advertiser_by_legacy_id(legacy_id)
                if advertiser and hasattr(advertiser, 'wallet'):
                    status = {
                        'synced': True,
                        'entity_id': str(advertiser.wallet.id),
                        'last_sync': advertiser.wallet.updated_at,
                        'sync_type': 'wallet'
                    }
                else:
                    status = {'synced': False}
            
            else:
                status = {'synced': False, 'error': f'Unknown entity type: {entity_type}'}
            
            # Cache for 5 minutes
            cache.set(cache_key, status, 300)
            return status
            
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {'synced': False, 'error': str(e)}
    
    # Private helper methods
    
    async def _transform_data(self, entity_type: str, legacy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform legacy data to new system format."""
        mapping = self.sync_mappings.get(entity_type, {})
        transformers = self.field_transformers.get(entity_type, {})
        
        transformed = {}
        for legacy_field, new_field in mapping.items():
            value = legacy_data.get(legacy_field)
            if value is not None:
                # Apply field transformer if available
                if new_field in transformers:
                    try:
                        value = transformers[new_field](value)
                    except Exception as e:
                        logger.warning(f"Error transforming field {new_field}: {e}")
                        continue
                
                transformed[new_field] = value
        
        return transformed
    
    async def _validate_data(self, entity_type: str, data: Dict[str, Any]) -> List[str]:
        """Validate data according to entity rules."""
        rules = self.validation_rules.get(entity_type, [])
        errors = []
        
        for rule in rules:
            try:
                rule_errors = rule(data)
                if rule_errors:
                    errors.extend(rule_errors)
            except Exception as e:
                logger.warning(f"Error in validation rule: {e}")
        
        return errors
    
    async def _get_advertiser_by_legacy_id(self, legacy_id: str) -> Optional[Advertiser]:
        """Get advertiser by legacy ID with caching."""
        cache_key = f"advertiser_legacy_{legacy_id}"
        advertiser = cache.get(cache_key)
        
        if not advertiser:
            try:
                # Assuming legacy_id is stored in a custom field or through mapping
                advertiser = Advertiser.objects.filter(
                    metadata__legacy_id=legacy_id
                ).first()
                
                if advertiser:
                    cache.set(cache_key, advertiser, 300)  # Cache for 5 minutes
            except Exception as e:
                logger.error(f"Error getting advertiser by legacy ID: {e}")
        
        return advertiser
    
    async def _sync_profile(self, advertiser: Advertiser, data: Dict[str, Any]) -> tuple[AdvertiserProfile, bool]:
        """Sync advertiser profile."""
        profile, created = AdvertiserProfile.objects.get_or_create(
            advertiser=advertiser,
            defaults=data
        )
        
        if not created:
            # Update existing profile
            for field, value in data.items():
                if hasattr(profile, field):
                    setattr(profile, field, value)
            profile.save()
        
        return profile, created
    
    async def _sync_wallet_balance(self, advertiser: Advertiser, data: Dict[str, Any]) -> tuple[AdvertiserWallet, bool]:
        """Sync wallet balance."""
        wallet, created = AdvertiserWallet.objects.get_or_create(
            advertiser=advertiser,
            defaults={'balance': data.get('balance', 0)}
        )
        
        updated = False
        if 'balance' in data and wallet.balance != data['balance']:
            wallet.balance = data['balance']
            wallet.save()
            updated = True
        
        # Update other wallet fields if provided
        for field in ['currency', 'auto_refill_enabled', 'auto_refill_threshold', 'auto_refill_amount']:
            if field in data and hasattr(wallet, field):
                setattr(wallet, field, data[field])
                wallet.save()
                updated = True
        
        return wallet, updated
    
    async def _sync_campaign(self, advertiser: Advertiser, data: Dict[str, Any]) -> tuple[AdCampaign, bool]:
        """Sync campaign data."""
        campaign, created = AdCampaign.objects.get_or_create(
            advertiser=advertiser,
            name=data.get('name'),
            defaults=data
        )
        
        if not created:
            # Update existing campaign
            for field, value in data.items():
                if hasattr(campaign, field):
                    setattr(campaign, field, value)
            campaign.save()
        
        return campaign, created
    
    async def _sync_offer(self, advertiser: Advertiser, data: Dict[str, Any]) -> tuple[AdvertiserOffer, bool]:
        """Sync offer data."""
        offer, created = AdvertiserOffer.objects.get_or_create(
            advertiser=advertiser,
            name=data.get('name'),
            defaults=data
        )
        
        if not created:
            # Update existing offer
            for field, value in data.items():
                if hasattr(offer, field):
                    setattr(offer, field, value)
            offer.save()
        
        return offer, created
    
    # Field transformation helpers
    
    def _transform_status(self, legacy_status: str) -> str:
        """Transform legacy status to new system format."""
        status_mapping = {
            'active': 'verified',
            'pending': 'pending',
            'inactive': 'rejected',
            'suspended': 'suspended'
        }
        return status_mapping.get(legacy_status.lower(), 'pending')
    
    def _parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Parse datetime string."""
        if not datetime_str:
            return None
        
        try:
            return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string."""
        if not date_str:
            return None
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, AttributeError):
            return None
    
    # Validation helpers
    
    def _validate_required_fields(self, required_fields: List[str]) -> Callable:
        """Create validator for required fields."""
        def validator(data: Dict[str, Any]) -> List[str]:
            errors = []
            for field in required_fields:
                if field not in data or data[field] is None or data[field] == '':
                    errors.append(f"Field '{field}' is required")
            return errors
        return validator
    
    def _validate_email_format(self, field: str) -> Callable:
        """Create validator for email format."""
        def validator(data: Dict[str, Any]) -> List[str]:
            errors = []
            if field in data and data[field]:
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, data[field]):
                    errors.append(f"Field '{field}' must be a valid email")
            return errors
        return validator
    
    def _validate_url_format(self, field: str) -> Callable:
        """Create validator for URL format."""
        def validator(data: Dict[str, Any]) -> List[str]:
            errors = []
            if field in data and data[field]:
                import re
                url_pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
                if not re.match(url_pattern, data[field]):
                    errors.append(f"Field '{field}' must be a valid URL")
            return errors
        return validator
    
    def _validate_positive_amount(self, *fields: str) -> Callable:
        """Create validator for positive amounts."""
        def validator(data: Dict[str, Any]) -> List[str]:
            errors = []
            for field in fields:
                if field in data and data[field] is not None:
                    try:
                        amount = Decimal(str(data[field]))
                        if amount < 0:
                            errors.append(f"Field '{field}' must be positive")
                    except (ValueError, TypeError):
                        errors.append(f"Field '{field}' must be a valid number")
            return errors
        return validator
    
    def _validate_date_range(self, start_field: str, end_field: str) -> Callable:
        """Create validator for date range."""
        def validator(data: Dict[str, Any]) -> List[str]:
            errors = []
            start_date = data.get(start_field)
            end_date = data.get(end_field)
            
            if start_date and end_date:
                if start_date > end_date:
                    errors.append(f"'{start_field}' must be before '{end_field}'")
            return errors
        return validator


# Global data bridge instance
data_bridge = DataBridge()


# Export main classes
__all__ = [
    'DataBridge',
    'DataSyncResult',
    'data_bridge',
]
