"""
A/B Testing Integration Layer

This module provides seamless integration between the advertiser_portal
and the a_b_testing module, enabling campaign testing and optimization.
"""

import asyncio
import json
import logging
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
from ..models.tracking import Conversion
from ..exceptions import *
from ..utils import *

logger = logging.getLogger(__name__)


@dataclass
class ABTestConfig:
    """Configuration for A/B test."""
    test_id: str
    campaign_id: str
    test_type: str  # 'creative', 'landing_page', 'offer', 'targeting'
    variants: List[Dict[str, Any]]
    traffic_split: Dict[str, float]  # variant_id -> percentage
    start_date: datetime
    end_date: Optional[datetime] = None
    min_sample_size: int = 1000
    confidence_level: float = 0.95
    auto_optimize: bool = True


@dataclass
class ABTestResult:
    """Results of an A/B test."""
    test_id: str
    variant_results: Dict[str, Dict[str, Any]]
    winner: Optional[str] = None
    confidence: Optional[float] = None
    statistical_significance: bool = False
    recommendation: Optional[str] = None
    test_completed: bool = False
    completion_date: Optional[datetime] = None


class ABTestingIntegration:
    """
    Integration layer for A/B testing functionality.
    
    Provides seamless communication between advertiser_portal and
    the a_b_testing module with real-time data synchronization.
    """
    
    def __init__(self):
        self.active_tests: Dict[str, ABTestConfig] = {}
        self.test_results: Dict[str, ABTestResult] = {}
        self.traffic_assignments: Dict[str, Dict[str, str]] = {}  # user_id -> variant_id
        
        # Performance targets
        self.TRAFFIC_ASSIGNMENT_LATENCY_MS = 50
        self.RESULT_CALCULATION_LATENCY_MS = 200
        
        # Register event handlers
        self._register_event_handlers()
    
    def _register_event_handlers(self):
        """Register event handlers for A/B testing integration."""
        event_bus.register_handler(
            'campaign_created',
            self.handle_campaign_created,
            priority=EventPriority.HIGH
        )
        
        event_bus.register_handler(
            'conversion_received',
            self.handle_conversion_received,
            priority=EventPriority.NORMAL
        )
        
        event_bus.register_handler(
            'ab_test_completed',
            self.handle_test_completed,
            priority=EventPriority.HIGH
        )
    
    async def create_ab_test(self, config: ABTestConfig) -> Dict[str, Any]:
        """
        Create a new A/B test.
        
        Args:
            config: A/B test configuration
            
        Returns:
            Test creation result
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('create_ab_test'):
                # Validate configuration
                validation_result = await self._validate_test_config(config)
                if not validation_result['valid']:
                    raise ValidationError(validation_result['errors'])
                
                # Store test configuration
                self.active_tests[config.test_id] = config
                
                # Initialize traffic assignment
                self.traffic_assignments[config.test_id] = {}
                
                # Create test in a_b_testing module
                test_data = {
                    'test_id': config.test_id,
                    'campaign_id': config.campaign_id,
                    'test_type': config.test_type,
                    'variants': config.variants,
                    'traffic_split': config.traffic_split,
                    'start_date': config.start_date.isoformat(),
                    'end_date': config.end_date.isoformat() if config.end_date else None,
                    'min_sample_size': config.min_sample_size,
                    'confidence_level': config.confidence_level,
                    'auto_optimize': config.auto_optimize
                }
                
                # Emit event to a_b_testing module
                success = await event_bus.emit(
                    'ab_test_created',
                    test_data,
                    source='advertiser_portal',
                    priority=EventPriority.HIGH
                )
                
                if not success:
                    raise IntegrationError("Failed to emit ab_test_created event")
                
                # Initialize result tracking
                self.test_results[config.test_id] = ABTestResult(
                    test_id=config.test_id,
                    variant_results={variant_id: {'conversions': 0, 'impressions': 0, 'revenue': 0} 
                                   for variant_id in config.variants}
                )
                
                processing_time = (time.time() - start_time) * 1000
                
                return {
                    'success': True,
                    'test_id': config.test_id,
                    'status': 'created',
                    'processing_time_ms': processing_time,
                    'start_date': config.start_date.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error creating A/B test: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_time_ms': (time.time() - start_time) * 1000
            }
    
    async def get_variant_assignment(self, test_id: str, user_id: str, 
                                  context: Dict[str, Any] = None) -> Optional[str]:
        """
        Get variant assignment for a user in an A/B test.
        
        Critical operation with <50ms latency target.
        
        Args:
            test_id: A/B test ID
            user_id: User ID
            context: Additional context for assignment
            
        Returns:
            Assigned variant ID or None
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('get_variant_assignment'):
                # Check if test exists and is active
                test_config = self.active_tests.get(test_id)
                if not test_config:
                    return None
                
                # Check if test is still running
                if test_config.end_date and timezone.now() > test_config.end_date:
                    return None
                
                # Check if user already has assignment
                if user_id in self.traffic_assignments.get(test_id, {}):
                    return self.traffic_assignments[test_id][user_id]
                
                # Generate new assignment
                variant_id = await self._assign_variant(test_config, user_id, context)
                
                if variant_id:
                    # Store assignment
                    if test_id not in self.traffic_assignments:
                        self.traffic_assignments[test_id] = {}
                    self.traffic_assignments[test_id][user_id] = variant_id
                    
                    # Emit assignment event
                    await event_bus.emit(
                        'variant_assigned',
                        {
                            'test_id': test_id,
                            'user_id': user_id,
                            'variant_id': variant_id,
                            'context': context or {}
                        },
                        source='advertiser_portal'
                    )
                
                processing_time = (time.time() - start_time) * 1000
                
                # Log slow assignments
                if processing_time > self.TRAFFIC_ASSIGNMENT_LATENCY_MS:
                    logger.warning(f"Slow variant assignment: {test_id} took {processing_time:.2f}ms")
                
                return variant_id
                
        except Exception as e:
            logger.error(f"Error getting variant assignment: {e}")
            return None
    
    async def record_conversion(self, test_id: str, user_id: str, 
                              conversion_data: Dict[str, Any]) -> bool:
        """
        Record a conversion for A/B test analysis.
        
        Args:
            test_id: A/B test ID
            user_id: User ID
            conversion_data: Conversion data
            
        Returns:
            True if conversion was recorded successfully
        """
        try:
            with performance_monitor.measure('record_conversion'):
                # Get user's variant assignment
                variant_id = self.traffic_assignments.get(test_id, {}).get(user_id)
                if not variant_id:
                    return False
                
                # Update test results
                if test_id in self.test_results:
                    result = self.test_results[test_id]
                    if variant_id in result.variant_results:
                        variant_result = result.variant_results[variant_id]
                        variant_result['conversions'] += 1
                        variant_result['revenue'] += float(conversion_data.get('revenue', 0))
                
                # Emit conversion event
                await event_bus.emit(
                    'ab_test_conversion',
                    {
                        'test_id': test_id,
                        'user_id': user_id,
                        'variant_id': variant_id,
                        'conversion_data': conversion_data
                    },
                    source='advertiser_portal'
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error recording conversion: {e}")
            return False
    
    async def calculate_test_results(self, test_id: str) -> Optional[ABTestResult]:
        """
        Calculate A/B test results.
        
        Args:
            test_id: A/B test ID
            
        Returns:
            Test results or None
        """
        try:
            with performance_monitor.measure('calculate_test_results'):
                test_config = self.active_tests.get(test_id)
                if not test_config:
                    return None
                
                result = self.test_results.get(test_id)
                if not result:
                    return None
                
                # Calculate conversion rates and other metrics
                for variant_id, variant_result in result.variant_results.items():
                    impressions = variant_result.get('impressions', 0)
                    conversions = variant_result.get('conversions', 0)
                    revenue = variant_result.get('revenue', 0)
                    
                    variant_result['conversion_rate'] = (conversions / impressions * 100) if impressions > 0 else 0
                    variant_result['revenue_per_conversion'] = (revenue / conversions) if conversions > 0 else 0
                    variant_result['sample_size'] = impressions + conversions
                
                # Determine winner using statistical analysis
                winner = await self._determine_winner(test_config, result)
                
                if winner:
                    result.winner = winner['variant_id']
                    result.confidence = winner['confidence']
                    result.statistical_significance = winner['significant']
                    result.recommendation = winner['recommendation']
                    result.test_completed = winner['completed']
                    result.completion_date = timezone.now()
                
                return result
                
        except Exception as e:
            logger.error(f"Error calculating test results: {e}")
            return None
    
    async def handle_campaign_created(self, event: Event):
        """Handle campaign creation event."""
        campaign_data = event.data
        
        # Check if campaign should have A/B test
        if self._should_create_test(campaign_data):
            # Create default A/B test for campaign
            test_config = await self._create_default_test(campaign_data)
            if test_config:
                await self.create_ab_test(test_config)
    
    async def handle_conversion_received(self, event: Event):
        """Handle conversion event."""
        conversion_data = event.data
        
        # Check if conversion is part of any A/B test
        user_id = conversion_data.get('user_id')
        if not user_id:
            return
        
        # Record conversion for all active tests
        for test_id in self.active_tests:
            await self.record_conversion(test_id, user_id, conversion_data)
    
    async def handle_test_completed(self, event: Event):
        """Handle A/B test completion event."""
        test_data = event.data
        test_id = test_data.get('test_id')
        
        if test_id in self.active_tests:
            # Move test from active to completed
            test_config = self.active_tests.pop(test_id)
            
            # Calculate final results
            results = await self.calculate_test_results(test_id)
            if results:
                self.test_results[test_id] = results
                
                # Apply winner if auto_optimize is enabled
                if test_config.auto_optimize and results.winner:
                    await self._apply_winner(test_config, results.winner)
    
    async def _validate_test_config(self, config: ABTestConfig) -> Dict[str, Any]:
        """Validate A/B test configuration."""
        errors = []
        
        # Check required fields
        if not config.test_id:
            errors.append("Test ID is required")
        
        if not config.campaign_id:
            errors.append("Campaign ID is required")
        
        if not config.variants or len(config.variants) < 2:
            errors.append("At least 2 variants are required")
        
        # Validate traffic split
        total_split = sum(config.traffic_split.values())
        if abs(total_split - 100.0) > 0.01:
            errors.append("Traffic split must sum to 100%")
        
        # Validate dates
        if config.start_date >= timezone.now():
            errors.append("Start date must be in the past")
        
        if config.end_date and config.end_date <= config.start_date:
            errors.append("End date must be after start date")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    async def _assign_variant(self, config: ABTestConfig, user_id: str, 
                           context: Dict[str, Any] = None) -> Optional[str]:
        """Assign variant to user based on traffic split."""
        import random
        
        # Generate hash for consistent assignment
        hash_input = f"{config.test_id}_{user_id}"
        hash_value = hash(hash_input) % 100
        
        cumulative_split = 0
        for variant_id, split_percentage in config.traffic_split.items():
            cumulative_split += split_percentage
            if hash_value < cumulative_split:
                return variant_id
        
        return None
    
    async def _determine_winner(self, config: ABTestConfig, 
                             result: ABTestResult) -> Optional[Dict[str, Any]]:
        """Determine winner using statistical analysis."""
        if len(result.variant_results) < 2:
            return None
        
        # Calculate sample sizes
        sample_sizes = [v['sample_size'] for v in result.variant_results.values()]
        min_size = min(sample_sizes)
        
        if min_size < config.min_sample_size:
            return {
                'variant_id': None,
                'confidence': 0,
                'significant': False,
                'completed': False,
                'recommendation': f"Insufficient sample size. Minimum required: {config.min_sample_size}"
            }
        
        # Simple statistical test (in production, use proper statistical tests)
        best_variant = max(result.variant_results.items(), 
                          key=lambda x: x[1]['conversion_rate'])
        
        second_best = sorted(result.variant_results.items(), 
                           key=lambda x: x[1]['conversion_rate'])[-2]
        
        # Calculate confidence (simplified)
        confidence = min(0.95, (best_variant[1]['conversion_rate'] - second_best[1]['conversion_rate']) / 0.1)
        
        return {
            'variant_id': best_variant[0],
            'confidence': confidence,
            'significant': confidence > 0.8,
            'completed': confidence > 0.9,
            'recommendation': f"Variant {best_variant[0]} wins with {confidence:.2%} confidence"
        }
    
    async def _apply_winner(self, config: ABTestConfig, winner_variant: str):
        """Apply winning variant to campaign."""
        try:
            # Get campaign
            campaign = AdCampaign.objects.get(id=config.campaign_id)
            
            # Apply winner based on test type
            if config.test_type == 'creative':
                # Update campaign creative
                winner_data = next(v for v in config.variants if v['variant_id'] == winner_variant)
                campaign.creative_id = winner_data['creative_id']
                campaign.save()
            
            elif config.test_type == 'landing_page':
                # Update landing page
                winner_data = next(v for v in config.variants if v['variant_id'] == winner_variant)
                campaign.landing_page = winner_data['landing_page']
                campaign.save()
            
            # Emit winner applied event
            await event_bus.emit(
                'ab_test_winner_applied',
                {
                    'test_id': config.test_id,
                    'campaign_id': config.campaign_id,
                    'winner_variant': winner_variant,
                    'test_type': config.test_type
                },
                source='advertiser_portal',
                priority=EventPriority.HIGH
            )
            
        except Exception as e:
            logger.error(f"Error applying winner: {e}")
    
    def _should_create_test(self, campaign_data: Dict[str, Any]) -> bool:
        """Determine if campaign should have A/B test."""
        # Business logic for when to create A/B tests
        campaign_type = campaign_data.get('campaign_type')
        budget = campaign_data.get('total_budget', 0)
        
        # Create test for high-budget campaigns or specific types
        return (budget > 1000 or campaign_type in ['display', 'social'])
    
    async def _create_default_test(self, campaign_data: Dict[str, Any]) -> Optional[ABTestConfig]:
        """Create default A/B test configuration."""
        try:
            campaign_id = campaign_data.get('id')
            test_id = f"auto_test_{campaign_id}_{int(time.time())}"
            
            # Default test configuration
            config = ABTestConfig(
                test_id=test_id,
                campaign_id=campaign_id,
                test_type='creative',
                variants=[
                    {'variant_id': 'control', 'creative_id': campaign_data.get('creative_id')},
                    {'variant_id': 'variant_1', 'creative_id': campaign_data.get('alternative_creative_id')}
                ],
                traffic_split={'control': 50.0, 'variant_1': 50.0},
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=30),
                min_sample_size=1000,
                confidence_level=0.95,
                auto_optimize=True
            )
            
            return config
            
        except Exception as e:
            logger.error(f"Error creating default test: {e}")
            return None
    
    def get_test_status(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get A/B test status."""
        if test_id in self.active_tests:
            config = self.active_tests[test_id]
            result = self.test_results.get(test_id)
            
            return {
                'test_id': test_id,
                'status': 'active',
                'config': asdict(config),
                'results': asdict(result) if result else None,
                'participants': len(self.traffic_assignments.get(test_id, {}))
            }
        elif test_id in self.test_results:
            result = self.test_results[test_id]
            return {
                'test_id': test_id,
                'status': 'completed',
                'results': asdict(result),
                'participants': len(self.traffic_assignments.get(test_id, {}))
            }
        else:
            return None


# Global integration instance
ab_testing_integration = ABTestingIntegration()


# Export main classes
__all__ = [
    'ABTestingIntegration',
    'ABTestConfig',
    'ABTestResult',
    'ab_testing_integration',
]
