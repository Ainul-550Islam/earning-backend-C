"""
Retargeting Engines Integration Layer

This module provides seamless integration between the advertiser_portal
and the retargeting_engines module, enabling advanced retargeting
campaigns and user journey tracking.
"""

import asyncio
import json
import logging
from collections import defaultdict
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from .event_bus import event_bus, Event, EventPriority
from .performance_monitor import performance_monitor
from ..models.campaign import AdCampaign
from ..models.offer import AdvertiserOffer
from ..models.tracking import Conversion, TrackingPixel
from ..exceptions import *
from ..utils import *

logger = logging.getLogger(__name__)


@dataclass
class RetargetingSegment:
    """Retargeting segment data structure."""
    segment_id: str
    campaign_id: str
    segment_name: str
    criteria: Dict[str, Any]
    user_ids: List[str]
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True


@dataclass
class UserJourneyEvent:
    """User journey event data structure."""
    user_id: str
    event_type: str
    campaign_id: Optional[str]
    offer_id: Optional[str]
    timestamp: datetime
    context: Dict[str, Any]
    conversion_value: Optional[Decimal] = None


@dataclass
class RetargetingConfig:
    """Configuration for retargeting campaigns."""
    campaign_id: str
    strategy: str  # 'pixel_based', 'email_based', 'behavioral', 'lookalike'
    lookback_days: int = 30
    frequency_cap: int = 5  # Max impressions per user per day
    bid_adjustment: float = 1.2  # Bid multiplier for retargeting
    exclude_converted: bool = True
    segment_refresh_hours: int = 6
    auto_optimize: bool = True


class RetargetingEnginesIntegration:
    """
    Integration layer for retargeting engines functionality.
    
    Provides seamless communication between advertiser_portal and
    retargeting_engines module with real-time user tracking and
    segment management.
    """
    
    def __init__(self):
        self.active_segments: Dict[str, RetargetingSegment] = {}
        self.user_journeys: Dict[str, List[UserJourneyEvent]] = defaultdict(list)
        self.retention_configs: Dict[str, RetargetingConfig] = {}
        self.segment_performance: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Performance targets
        self.SEGMENT_LOOKUP_LATENCY_MS = 50
        self.JOURNEY_TRACKING_LATENCY_MS = 100

        # Register event handlers
        self._register_event_handlers()

        # Background tasks — only start when event loop is already running
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._segment_refresh_loop())
            loop.create_task(self._performance_monitoring_loop())
        except RuntimeError:
            pass  # No event loop at import time; tasks deferred
    
    def _register_event_handlers(self):
        """Register event handlers for retargeting integration."""
        event_bus.register_handler(
            'conversion_received',
            self.handle_conversion_received,
            priority=EventPriority.HIGH
        )
        
        event_bus.register_handler(
            'pixel_fired',
            self.handle_pixel_fired,
            priority=EventPriority.HIGH
        )
        
        event_bus.register_handler(
            'user_journey_updated',
            self.handle_journey_updated,
            priority=EventPriority.NORMAL
        )
        
        event_bus.register_handler(
            'retargeting_segment_created',
            self.handle_segment_created,
            priority=EventPriority.NORMAL
        )
    
    async def track_user_journey(self, event: UserJourneyEvent) -> bool:
        """
        Track user journey event for retargeting.
        
        Critical operation with <100ms latency target.
        
        Args:
            event: User journey event
            
        Returns:
            True if tracked successfully
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('track_user_journey'):
                # Store journey event
                self.user_journeys[event.user_id].append(event)
                
                # Limit journey history per user
                if len(self.user_journeys[event.user_id]) > 1000:
                    self.user_journeys[event.user_id] = self.user_journeys[event.user_id][-1000:]
                
                # Check if user should be added to any retargeting segments
                await self._evaluate_segment_eligibility(event)
                
                # Emit journey tracking event
                await event_bus.emit(
                    'user_journey_tracked',
                    {
                        'user_id': event.user_id,
                        'event_type': event.event_type,
                        'campaign_id': event.campaign_id,
                        'offer_id': event.offer_id,
                        'timestamp': event.timestamp.isoformat(),
                        'context': event.context
                    },
                    source='advertiser_portal'
                )
                
                processing_time = (time.time() - start_time) * 1000
                
                # Log slow tracking
                if processing_time > self.JOURNEY_TRACKING_LATENCY_MS:
                    logger.warning(f"Slow journey tracking: {event.user_id} took {processing_time:.2f}ms")
                
                return True
                
        except Exception as e:
            logger.error(f"Error tracking user journey: {e}")
            return False
    
    async def get_retargeting_segments(self, user_id: str) -> List[RetargetingSegment]:
        """
        Get retargeting segments for a user.
        
        Critical operation with <50ms latency target.
        
        Args:
            user_id: User ID
            
        Returns:
            List of retargeting segments
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('get_retargeting_segments'):
                segments = []
                
                # Check all active segments for user eligibility
                for segment in self.active_segments.values():
                    if segment.is_active and user_id in segment.user_ids:
                        # Check if segment hasn't expired
                        if not segment.expires_at or segment.expires_at > timezone.now():
                            segments.append(segment)
                
                processing_time = (time.time() - start_time) * 1000
                
                # Log slow lookups
                if processing_time > self.SEGMENT_LOOKUP_LATENCY_MS:
                    logger.warning(f"Slow segment lookup: {user_id} took {processing_time:.2f}ms")
                
                return segments
                
        except Exception as e:
            logger.error(f"Error getting retargeting segments: {e}")
            return []
    
    async def create_retargeting_config(self, config: RetargetingConfig) -> Dict[str, Any]:
        """
        Create retargeting configuration for a campaign.
        
        Args:
            config: Retargeting configuration
            
        Returns:
            Configuration creation result
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('create_retargeting_config'):
                # Validate configuration
                validation_result = await self._validate_retargeting_config(config)
                if not validation_result['valid']:
                    raise ValidationError(validation_result['errors'])
                
                # Store configuration
                self.retention_configs[config.campaign_id] = config
                
                # Create initial segments based on strategy
                await self._create_initial_segments(config)
                
                # Emit configuration event
                await event_bus.emit(
                    'retargeting_config_created',
                    {
                        'campaign_id': config.campaign_id,
                        'strategy': config.strategy,
                        'lookback_days': config.lookback_days,
                        'frequency_cap': config.frequency_cap,
                        'bid_adjustment': config.bid_adjustment
                    },
                    source='advertiser_portal',
                    priority=EventPriority.HIGH
                )
                
                processing_time = (time.time() - start_time) * 1000
                
                return {
                    'success': True,
                    'campaign_id': config.campaign_id,
                    'strategy': config.strategy,
                    'status': 'active',
                    'processing_time_ms': processing_time
                }
                
        except Exception as e:
            logger.error(f"Error creating retargeting config: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_time_ms': (time.time() - start_time) * 1000
            }
    
    async def update_segment_performance(self, segment_id: str, 
                                       performance_data: Dict[str, Any]) -> bool:
        """
        Update performance data for a retargeting segment.
        
        Args:
            segment_id: Segment ID
            performance_data: Performance data
            
        Returns:
            True if updated successfully
        """
        try:
            with performance_monitor.measure('update_segment_performance'):
                # Store performance data
                self.segment_performance[segment_id].update(performance_data)
                
                # Check if auto-optimization should be triggered
                segment = self.active_segments.get(segment_id)
                if segment and segment.is_active:
                    config = self.retention_configs.get(segment.campaign_id)
                    if config and config.auto_optimize:
                        await self._trigger_segment_optimization(segment_id, config)
                
                # Emit performance update event
                await event_bus.emit(
                    'segment_performance_updated',
                    {
                        'segment_id': segment_id,
                        'performance_data': performance_data
                    },
                    source='advertiser_portal'
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating segment performance: {e}")
            return False
    
    async def handle_conversion_received(self, event: Event):
        """Handle conversion event for retargeting."""
        conversion_data = event.data
        user_id = conversion_data.get('user_id')
        
        if user_id:
            # Track conversion in user journey
            journey_event = UserJourneyEvent(
                user_id=user_id,
                event_type='conversion',
                campaign_id=conversion_data.get('campaign_id'),
                offer_id=conversion_data.get('offer_id'),
                timestamp=timezone.now(),
                context=conversion_data,
                conversion_value=Decimal(str(conversion_data.get('revenue', 0)))
            )
            
            await self.track_user_journey(journey_event)
            
            # Remove from retargeting segments if configured
            await self._handle_conversion_exclusion(user_id, conversion_data)
    
    async def handle_pixel_fired(self, event: Event):
        """Handle pixel firing event for retargeting."""
        pixel_data = event.data
        user_id = pixel_data.get('user_id')
        
        if user_id:
            # Track pixel event in user journey
            journey_event = UserJourneyEvent(
                user_id=user_id,
                event_type='pixel_fire',
                campaign_id=pixel_data.get('campaign_id'),
                offer_id=pixel_data.get('offer_id'),
                timestamp=timezone.now(),
                context=pixel_data
            )
            
            await self.track_user_journey(journey_event)
    
    async def handle_journey_updated(self, event: Event):
        """Handle user journey update event."""
        journey_data = event.data
        user_id = journey_data.get('user_id')
        
        if user_id and journey_data.get('events'):
            # Process journey events
            for event_data in journey_data['events']:
                journey_event = UserJourneyEvent(
                    user_id=user_id,
                    event_type=event_data.get('event_type'),
                    campaign_id=event_data.get('campaign_id'),
                    offer_id=event_data.get('offer_id'),
                    timestamp=timezone.now(),
                    context=event_data.get('context', {}),
                    conversion_value=Decimal(str(event_data.get('conversion_value', 0))) if event_data.get('conversion_value') else None
                )
                
                await self.track_user_journey(journey_event)
    
    async def handle_segment_created(self, event: Event):
        """Handle retargeting segment creation event."""
        segment_data = event.data
        
        # Create segment object
        segment = RetargetingSegment(
            segment_id=segment_data['segment_id'],
            campaign_id=segment_data['campaign_id'],
            segment_name=segment_data['segment_name'],
            criteria=segment_data['criteria'],
            user_ids=segment_data.get('user_ids', []),
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=segment_data.get('expires_days', 30))
        )
        
        self.active_segments[segment.segment_id] = segment
    
    async def _evaluate_segment_eligibility(self, event: UserJourneyEvent):
        """Evaluate if user should be added to retargeting segments."""
        user_journey = self.user_journeys[event.user_id]
        
        # Check each active segment
        for segment in self.active_segments.values():
            if not segment.is_active:
                continue
            
            # Check if user is already in segment
            if event.user_id in segment.user_ids:
                continue
            
            # Evaluate segment criteria
            if await self._meets_segment_criteria(event.user_id, user_journey, segment.criteria):
                # Add user to segment
                segment.user_ids.append(event.user_id)
                
                # Emit segment addition event
                await event_bus.emit(
                    'user_added_to_segment',
                    {
                        'segment_id': segment.segment_id,
                        'user_id': event.user_id,
                        'campaign_id': segment.campaign_id,
                        'criteria_met': segment.criteria
                    },
                    source='advertiser_portal'
                )
    
    async def _meets_segment_criteria(self, user_id: str, 
                                    user_journey: List[UserJourneyEvent], 
                                    criteria: Dict[str, Any]) -> bool:
        """Check if user meets segment criteria."""
        try:
            # Time-based criteria
            lookback_days = criteria.get('lookback_days', 30)
            cutoff_date = timezone.now() - timedelta(days=lookback_days)
            recent_events = [e for e in user_journey if e.timestamp > cutoff_date]
            
            # Event type criteria
            required_events = criteria.get('required_events', [])
            if required_events:
                user_event_types = {e.event_type for e in recent_events}
                if not all(event_type in user_event_types for event_type in required_events):
                    return False
            
            # Campaign criteria
            campaign_ids = criteria.get('campaign_ids', [])
            if campaign_ids:
                user_campaigns = {e.campaign_id for e in recent_events if e.campaign_id}
                if not any(campaign_id in user_campaigns for campaign_id in campaign_ids):
                    return False
            
            # Conversion criteria
            min_conversion_value = criteria.get('min_conversion_value')
            if min_conversion_value:
                total_value = sum(e.conversion_value or 0 for e in recent_events if e.conversion_value)
                if total_value < Decimal(str(min_conversion_value)):
                    return False
            
            # Frequency criteria
            min_events = criteria.get('min_events', 0)
            if len(recent_events) < min_events:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating segment criteria: {e}")
            return False
    
    async def _create_initial_segments(self, config: RetargetingConfig):
        """Create initial retargeting segments based on strategy."""
        try:
            if config.strategy == 'pixel_based':
                # Create segment for users who fired pixels
                await self._create_pixel_based_segment(config)
            
            elif config.strategy == 'email_based':
                # Create segment for email subscribers
                await self._create_email_based_segment(config)
            
            elif config.strategy == 'behavioral':
                # Create segments based on user behavior
                await self._create_behavioral_segments(config)
            
            elif config.strategy == 'lookalike':
                # Create lookalike segments
                await self._create_lookalike_segments(config)
            
        except Exception as e:
            logger.error(f"Error creating initial segments: {e}")
    
    async def _create_pixel_based_segment(self, config: RetargetingConfig):
        """Create pixel-based retargeting segment."""
        segment_id = f"pixel_{config.campaign_id}_{int(time.time())}"
        
        # Find users who fired tracking pixels
        pixel_users = set()
        cutoff_date = timezone.now() - timedelta(days=config.lookback_days)
        
        for user_id, journey in self.user_journeys.items():
            recent_events = [e for e in journey if e.timestamp > cutoff_date]
            if any(e.event_type == 'pixel_fire' for e in recent_events):
                pixel_users.add(user_id)
        
        # Create segment
        segment = RetargetingSegment(
            segment_id=segment_id,
            campaign_id=config.campaign_id,
            segment_name="Pixel Retargeting",
            criteria={
                'required_events': ['pixel_fire'],
                'lookback_days': config.lookback_days
            },
            user_ids=list(pixel_users),
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        self.active_segments[segment_id] = segment
        
        # Emit segment creation event
        await event_bus.emit(
            'retargeting_segment_created',
            {
                'segment_id': segment_id,
                'campaign_id': config.campaign_id,
                'segment_name': segment.segment_name,
                'criteria': segment.criteria,
                'user_ids': segment.user_ids,
                'expires_days': 30
            },
            source='advertiser_portal'
        )
    
    async def _create_behavioral_segments(self, config: RetargetingConfig):
        """Create behavioral retargeting segments."""
        # High-value users segment
        high_value_segment_id = f"high_value_{config.campaign_id}_{int(time.time())}"
        
        high_value_users = set()
        cutoff_date = timezone.now() - timedelta(days=config.lookback_days)
        
        for user_id, journey in self.user_journeys.items():
            recent_events = [e for e in journey if e.timestamp > cutoff_date]
            
            # Calculate total conversion value
            total_value = sum(e.conversion_value or 0 for e in recent_events if e.conversion_value)
            
            # High-value threshold (e.g., > $100 in conversions)
            if total_value > 100:
                high_value_users.add(user_id)
        
        if high_value_users:
            segment = RetargetingSegment(
                segment_id=high_value_segment_id,
                campaign_id=config.campaign_id,
                segment_name="High Value Users",
                criteria={
                    'min_conversion_value': 100,
                    'lookback_days': config.lookback_days
                },
                user_ids=list(high_value_users),
                created_at=timezone.now(),
                expires_at=timezone.now() + timedelta(days=30)
            )
            
            self.active_segments[high_value_segment_id] = segment
    
    async def _handle_conversion_exclusion(self, user_id: str, conversion_data: Dict[str, Any]):
        """Handle user exclusion from segments after conversion."""
        campaign_id = conversion_data.get('campaign_id')
        
        if not campaign_id:
            return
        
        config = self.retention_configs.get(campaign_id)
        if not config or not config.exclude_converted:
            return
        
        # Remove user from all segments for this campaign
        for segment in self.active_segments.values():
            if segment.campaign_id == campaign_id and user_id in segment.user_ids:
                segment.user_ids.remove(user_id)
                
                # Emit exclusion event
                await event_bus.emit(
                    'user_excluded_from_segment',
                    {
                        'segment_id': segment.segment_id,
                        'user_id': user_id,
                        'campaign_id': campaign_id,
                        'reason': 'conversion'
                    },
                    source='advertiser_portal'
                )
    
    async def _trigger_segment_optimization(self, segment_id: str, config: RetargetingConfig):
        """Trigger segment optimization if conditions are met."""
        try:
            performance = self.segment_performance.get(segment_id, {})
            
            # Check if optimization is needed
            ctr = performance.get('ctr', 0)
            conversion_rate = performance.get('conversion_rate', 0)
            
            if ctr < 0.01 or conversion_rate < 0.001:  # Low performance thresholds
                await event_bus.emit(
                    'segment_optimization_triggered',
                    {
                        'segment_id': segment_id,
                        'campaign_id': config.campaign_id,
                        'performance': performance,
                        'optimization_type': 'performance_based'
                    },
                    source='advertiser_portal',
                    priority=EventPriority.NORMAL
                )
                
        except Exception as e:
            logger.error(f"Error triggering segment optimization: {e}")
    
    async def _segment_refresh_loop(self):
        """Background loop for refreshing segments."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Refresh segments based on configurations
                for config in self.retention_configs.values():
                    if config.auto_optimize:
                        await self._refresh_segments(config)
                        
            except Exception as e:
                logger.error(f"Error in segment refresh loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _refresh_segments(self, config: RetargetingConfig):
        """Refresh retargeting segments for a campaign."""
        try:
            # Re-evaluate segment criteria for all users
            for segment in self.active_segments.values():
                if segment.campaign_id == config.campaign_id:
                    # Clear current users
                    segment.user_ids.clear()
                    
                    # Re-evaluate all users
                    for user_id, journey in self.user_journeys.items():
                        if await self._meets_segment_criteria(user_id, journey, segment.criteria):
                            segment.user_ids.append(user_id)
            
        except Exception as e:
            logger.error(f"Error refreshing segments: {e}")
    
    async def _performance_monitoring_loop(self):
        """Background loop for performance monitoring."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Monitor segment performance
                for segment_id, performance in self.segment_performance.items():
                    if performance.get('impressions', 0) > 0:
                        logger.info(f"Segment {segment_id} performance: {performance}")
                        
            except Exception as e:
                logger.error(f"Error in performance monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _validate_retargeting_config(self, config: RetargetingConfig) -> Dict[str, Any]:
        """Validate retargeting configuration."""
        errors = []
        
        # Check required fields
        if not config.campaign_id:
            errors.append("Campaign ID is required")
        
        if not config.strategy:
            errors.append("Strategy is required")
        
        # Validate strategy
        valid_strategies = ['pixel_based', 'email_based', 'behavioral', 'lookalike']
        if config.strategy not in valid_strategies:
            errors.append(f"Invalid strategy. Must be one of: {', '.join(valid_strategies)}")
        
        # Validate parameters
        if config.lookback_days <= 0:
            errors.append("Lookback days must be positive")
        
        if config.frequency_cap <= 0:
            errors.append("Frequency cap must be positive")
        
        if config.bid_adjustment <= 0:
            errors.append("Bid adjustment must be positive")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def get_segment_stats(self, segment_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a retargeting segment."""
        segment = self.active_segments.get(segment_id)
        if not segment:
            return None
        
        performance = self.segment_performance.get(segment_id, {})
        
        return {
            'segment_id': segment_id,
            'campaign_id': segment.campaign_id,
            'segment_name': segment.segment_name,
            'user_count': len(segment.user_ids),
            'is_active': segment.is_active,
            'created_at': segment.created_at.isoformat(),
            'expires_at': segment.expires_at.isoformat() if segment.expires_at else None,
            'performance': performance
        }


# Global integration instance
retargeting_engines_integration = RetargetingEnginesIntegration()


# Export main classes
__all__ = [
    'RetargetingEnginesIntegration',
    'RetargetingSegment',
    'UserJourneyEvent',
    'RetargetingConfig',
    'retargeting_engines_integration',
]
