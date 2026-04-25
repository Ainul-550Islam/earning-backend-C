"""
Bidding Optimization Integration Layer

This module provides seamless integration between the advertiser_portal
and the bidding_optimization module, enabling real-time bid optimization
and automated bidding strategies.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
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
from ..models.billing import CampaignSpend
from ..exceptions import *
from ..utils import *

logger = logging.getLogger(__name__)


@dataclass
class BidRequest:
    """Bid request data structure."""
    request_id: str
    campaign_id: str
    user_id: str
    context: Dict[str, Any]
    floor_price: Decimal
    max_bid: Decimal
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


@dataclass
class BidResponse:
    """Bid response data structure."""
    request_id: str
    bid_amount: Decimal
    confidence: float
    optimization_model: str
    reasoning: str
    processing_time_ms: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


@dataclass
class OptimizationConfig:
    """Configuration for bid optimization."""
    campaign_id: str
    strategy: str  # 'manual_cpc', 'target_cpa', 'target_roas', 'maximize_conversions'
    target_value: Optional[Decimal] = None  # Target CPA, ROAS, etc.
    daily_budget: Optional[Decimal] = None
    bid_ceiling: Optional[Decimal] = None
    bid_floor: Optional[Decimal] = None
    learning_period_days: int = 7
    auto_optimize: bool = True
    min_confidence: float = 0.7


class BiddingOptimizationIntegration:
    """
    Integration layer for bidding optimization functionality.
    
    Provides real-time bid optimization with <50ms latency for
    critical bid requests and comprehensive performance tracking.
    """
    
    def __init__(self):
        self.active_optimizations: Dict[str, OptimizationConfig] = {}
        self.bid_models: Dict[str, Any] = {}
        self.performance_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Performance targets
        self.BID_REQUEST_LATENCY_MS = 50
        self.OPTIMIZATION_UPDATE_LATENCY_MS = 200
        
        # Initialize ML models
        self._initialize_models()
        
        # Register event handlers
        self._register_event_handlers()
    
    def _initialize_models(self):
        """Initialize ML models for bid optimization."""
        # In production, these would be actual ML models
        self.bid_models = {
            'cpc_model': {'type': 'regression', 'features': ['device_type', 'time_of_day', 'user_segment']},
            'cpa_model': {'type': 'classification', 'features': ['user_history', 'campaign_performance']},
            'roas_model': {'type': 'regression', 'features': ['conversion_value', 'user_ltv']}
        }
    
    def _register_event_handlers(self):
        """Register event handlers for bidding optimization."""
        event_bus.register_handler(
            'campaign_created',
            self.handle_campaign_created,
            priority=EventPriority.HIGH
        )
        
        event_bus.register_handler(
            'conversion_received',
            self.handle_conversion_received,
            priority=EventPriority.HIGH
        )
        
        event_bus.register_handler(
            'campaign_spend_updated',
            self.handle_spend_updated,
            priority=EventPriority.NORMAL
        )
        
        event_bus.register_handler(
            'bid_model_updated',
            self.handle_model_updated,
            priority=EventPriority.NORMAL
        )
    
    async def optimize_bid(self, bid_request: BidRequest) -> BidResponse:
        """
        Optimize bid amount for a bid request.
        
        Critical operation with <50ms latency target.
        
        Args:
            bid_request: Bid request data
            
        Returns:
            Optimized bid response
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('optimize_bid'):
                # Get optimization configuration
                config = self.active_optimizations.get(bid_request.campaign_id)
                if not config:
                    # Use default configuration
                    config = OptimizationConfig(
                        campaign_id=bid_request.campaign_id,
                        strategy='manual_cpc',
                        auto_optimize=False
                    )
                
                # Extract features for ML model
                features = await self._extract_features(bid_request, config)
                
                # Get bid prediction from ML model
                prediction = await self._get_bid_prediction(config.strategy, features)
                
                # Apply business rules and constraints
                optimized_bid = await self._apply_bid_constraints(
                    prediction, bid_request, config
                )
                
                # Calculate confidence
                confidence = await self._calculate_bid_confidence(
                    prediction, features, config
                )
                
                # Create response
                response = BidResponse(
                    request_id=bid_request.request_id,
                    bid_amount=optimized_bid,
                    confidence=confidence,
                    optimization_model=config.strategy,
                    reasoning=self._generate_reasoning(prediction, config),
                    processing_time_ms=(time.time() - start_time) * 1000
                )
                
                # Log bid request for learning
                await self._log_bid_request(bid_request, response, features)
                
                processing_time = (time.time() - start_time) * 1000
                
                # Log slow requests
                if processing_time > self.BID_REQUEST_LATENCY_MS:
                    logger.warning(f"Slow bid optimization: {bid_request.request_id} took {processing_time:.2f}ms")
                
                return response
                
        except Exception as e:
            logger.error(f"Error optimizing bid: {e}")
            
            # Return fallback bid
            return BidResponse(
                request_id=bid_request.request_id,
                bid_amount=bid_request.floor_price,
                confidence=0.5,
                optimization_model='fallback',
                reasoning=f"Error in optimization: {str(e)}",
                processing_time_ms=(time.time() - start_time) * 1000
            )
    
    async def setup_optimization(self, config: OptimizationConfig) -> Dict[str, Any]:
        """
        Set up bid optimization for a campaign.
        
        Args:
            config: Optimization configuration
            
        Returns:
            Setup result
        """
        start_time = time.time()
        
        try:
            with performance_monitor.measure('setup_optimization'):
                # Validate configuration
                validation_result = await self._validate_optimization_config(config)
                if not validation_result['valid']:
                    raise ValidationError(validation_result['errors'])
                
                # Store configuration
                self.active_optimizations[config.campaign_id] = config
                
                # Initialize performance tracking
                self.performance_data[config.campaign_id] = []
                
                # Setup optimization in bidding_optimization module
                setup_data = {
                    'campaign_id': config.campaign_id,
                    'strategy': config.strategy,
                    'target_value': float(config.target_value) if config.target_value else None,
                    'daily_budget': float(config.daily_budget) if config.daily_budget else None,
                    'bid_ceiling': float(config.bid_ceiling) if config.bid_ceiling else None,
                    'bid_floor': float(config.bid_floor) if config.bid_floor else None,
                    'learning_period_days': config.learning_period_days,
                    'auto_optimize': config.auto_optimize,
                    'min_confidence': config.min_confidence
                }
                
                # Emit setup event
                success = await event_bus.emit(
                    'optimization_setup',
                    setup_data,
                    source='advertiser_portal',
                    priority=EventPriority.HIGH
                )
                
                if not success:
                    raise IntegrationError("Failed to emit optimization_setup event")
                
                processing_time = (time.time() - start_time) * 1000
                
                return {
                    'success': True,
                    'campaign_id': config.campaign_id,
                    'strategy': config.strategy,
                    'status': 'active',
                    'processing_time_ms': processing_time
                }
                
        except Exception as e:
            logger.error(f"Error setting up optimization: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_time_ms': (time.time() - start_time) * 1000
            }
    
    async def update_optimization_performance(self, campaign_id: str, 
                                             performance_data: Dict[str, Any]) -> bool:
        """
        Update performance data for optimization learning.
        
        Args:
            campaign_id: Campaign ID
            performance_data: Performance data
            
        Returns:
            True if updated successfully
        """
        try:
            with performance_monitor.measure('update_performance'):
                # Store performance data
                self.performance_data[campaign_id].append({
                    'timestamp': timezone.now(),
                    'data': performance_data
                })
                
                # Limit performance data size
                if len(self.performance_data[campaign_id]) > 1000:
                    self.performance_data[campaign_id] = self.performance_data[campaign_id][-1000:]
                
                # Check if auto-optimization should be triggered
                config = self.active_optimizations.get(campaign_id)
                if config and config.auto_optimize:
                    await self._trigger_auto_optimization(campaign_id, config)
                
                # Emit performance update event
                await event_bus.emit(
                    'optimization_performance_updated',
                    {
                        'campaign_id': campaign_id,
                        'performance_data': performance_data
                    },
                    source='advertiser_portal'
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating performance: {e}")
            return False
    
    async def get_optimization_status(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get optimization status for a campaign."""
        config = self.active_optimizations.get(campaign_id)
        if not config:
            return None
        
        # Calculate recent performance metrics
        recent_performance = self.performance_data[campaign_id][-100:]  # Last 100 records
        
        return {
            'campaign_id': campaign_id,
            'strategy': config.strategy,
            'target_value': float(config.target_value) if config.target_value else None,
            'auto_optimize': config.auto_optimize,
            'min_confidence': config.min_confidence,
            'performance_records': len(recent_performance),
            'last_updated': timezone.now().isoformat()
        }
    
    async def handle_campaign_created(self, event: Event):
        """Handle campaign creation event."""
        campaign_data = event.data
        
        # Check if campaign should have bid optimization
        if self._should_enable_optimization(campaign_data):
            # Create default optimization configuration
            config = await self._create_default_optimization(campaign_data)
            if config:
                await self.setup_optimization(config)
    
    async def handle_conversion_received(self, event: Event):
        """Handle conversion event."""
        conversion_data = event.data
        campaign_id = conversion_data.get('campaign_id')
        
        if campaign_id:
            # Update performance data
            await self.update_optimization_performance(campaign_id, {
                'conversion_value': float(conversion_data.get('revenue', 0)),
                'timestamp': conversion_data.get('created_at'),
                'user_id': conversion_data.get('user_id')
            })
    
    async def handle_spend_updated(self, event: Event):
        """Handle spend update event."""
        spend_data = event.data
        campaign_id = spend_data.get('campaign_id')
        
        if campaign_id:
            # Update performance data
            await self.update_optimization_performance(campaign_id, {
                'spend': float(spend_data.get('total_spend', 0)),
                'impressions': spend_data.get('impressions', 0),
                'clicks': spend_data.get('clicks', 0),
                'conversions': spend_data.get('conversions', 0)
            })
    
    async def handle_model_updated(self, event: Event):
        """Handle ML model update event."""
        model_data = event.data
        model_name = model_data.get('model_name')
        
        if model_name in self.bid_models:
            # Update model configuration
            self.bid_models[model_name].update(model_data)
            
            logger.info(f"Updated bid model: {model_name}")
    
    async def _extract_features(self, bid_request: BidRequest, 
                              config: OptimizationConfig) -> Dict[str, Any]:
        """Extract features for ML model prediction."""
        context = bid_request.context
        
        features = {
            # Time-based features
            'hour_of_day': bid_request.timestamp.hour,
            'day_of_week': bid_request.timestamp.weekday(),
            'is_weekend': bid_request.timestamp.weekday() >= 5,
            
            # Context features
            'device_type': context.get('device_type', 'unknown'),
            'os': context.get('os', 'unknown'),
            'browser': context.get('browser', 'unknown'),
            'country': context.get('country', 'unknown'),
            
            # Campaign features
            'campaign_id': bid_request.campaign_id,
            'strategy': config.strategy,
            'target_value': float(config.target_value) if config.target_value else 0,
            
            # Bid constraints
            'floor_price': float(bid_request.floor_price),
            'max_bid': float(bid_request.max_bid),
            'bid_ceiling': float(config.bid_ceiling) if config.bid_ceiling else 0,
            'bid_floor': float(config.bid_floor) if config.bid_floor else 0
        }
        
        return features
    
    async def _get_bid_prediction(self, strategy: str, 
                              features: Dict[str, Any]) -> Dict[str, Any]:
        """Get bid prediction from ML model."""
        # In production, this would call actual ML models
        # For now, return a simple prediction
        
        if strategy == 'manual_cpc':
            # Simple CPC prediction based on features
            base_bid = features['floor_price']
            
            # Adjust based on device type
            if features['device_type'] == 'mobile':
                base_bid *= 1.2
            elif features['device_type'] == 'desktop':
                base_bid *= 1.0
            
            # Adjust based on time
            if features['hour_of_day'] in [19, 20, 21]:  # Prime time
                base_bid *= 1.1
            
            return {
                'predicted_bid': base_bid,
                'model_confidence': 0.8,
                'features_used': list(features.keys())
            }
        
        elif strategy == 'target_cpa':
            # CPA-based prediction
            target_cpa = features['target_value']
            conversion_rate = 0.02  # Default conversion rate
            
            predicted_bid = target_cpa * conversion_rate
            
            return {
                'predicted_bid': predicted_bid,
                'model_confidence': 0.7,
                'features_used': list(features.keys())
            }
        
        else:
            # Default prediction
            return {
                'predicted_bid': features['floor_price'] * 1.5,
                'model_confidence': 0.6,
                'features_used': list(features.keys())
            }
    
    async def _apply_bid_constraints(self, prediction: Dict[str, Any], 
                                   bid_request: BidRequest, 
                                   config: OptimizationConfig) -> Decimal:
        """Apply business rules and constraints to predicted bid."""
        predicted_bid = prediction['predicted_bid']
        
        # Apply floor and ceiling
        if config.bid_floor:
            predicted_bid = max(predicted_bid, config.bid_floor)
        
        if config.bid_ceiling:
            predicted_bid = min(predicted_bid, config.bid_ceiling)
        
        # Apply request constraints
        predicted_bid = max(predicted_bid, bid_request.floor_price)
        predicted_bid = min(predicted_bid, bid_request.max_bid)
        
        return predicted_bid
    
    async def _calculate_bid_confidence(self, prediction: Dict[str, Any], 
                                       features: Dict[str, Any], 
                                       config: OptimizationConfig) -> float:
        """Calculate confidence in bid prediction."""
        model_confidence = prediction['model_confidence']
        
        # Adjust confidence based on data quality
        if features.get('device_type') == 'unknown':
            model_confidence *= 0.8
        
        if features.get('country') == 'unknown':
            model_confidence *= 0.9
        
        # Ensure minimum confidence
        return max(model_confidence, config.min_confidence)
    
    def _generate_reasoning(self, prediction: Dict[str, Any], 
                          config: OptimizationConfig) -> str:
        """Generate reasoning for bid decision."""
        confidence = prediction['model_confidence']
        model_used = prediction.get('model_confidence', 'unknown')
        
        reasoning = f"Bid calculated using {config.strategy} strategy with {confidence:.2%} confidence."
        
        if confidence > 0.8:
            reasoning += " High confidence in prediction."
        elif confidence > 0.6:
            reasoning += " Moderate confidence in prediction."
        else:
            reasoning += " Low confidence in prediction."
        
        return reasoning
    
    async def _log_bid_request(self, bid_request: BidResponse, 
                            response: BidResponse, 
                            features: Dict[str, Any]):
        """Log bid request for model learning."""
        log_data = {
            'request_id': bid_request.request_id,
            'campaign_id': bid_request.campaign_id,
            'features': features,
            'predicted_bid': float(response.bid_amount),
            'confidence': response.confidence,
            'model': response.optimization_model,
            'processing_time_ms': response.processing_time_ms,
            'timestamp': timezone.now().isoformat()
        }
        
        # Store in cache for learning
        cache_key = f"bid_log_{bid_request.request_id}"
        cache.set(cache_key, log_data, timeout=86400)  # Keep for 24 hours
    
    async def _validate_optimization_config(self, config: OptimizationConfig) -> Dict[str, Any]:
        """Validate optimization configuration."""
        errors = []
        
        # Check required fields
        if not config.campaign_id:
            errors.append("Campaign ID is required")
        
        if not config.strategy:
            errors.append("Strategy is required")
        
        # Validate strategy
        valid_strategies = ['manual_cpc', 'target_cpa', 'target_roas', 'maximize_conversions']
        if config.strategy not in valid_strategies:
            errors.append(f"Invalid strategy. Must be one of: {', '.join(valid_strategies)}")
        
        # Validate target value for strategies that require it
        if config.strategy in ['target_cpa', 'target_roas'] and not config.target_value:
            errors.append(f"Target value is required for {config.strategy} strategy")
        
        # Validate budget constraints
        if config.daily_budget and config.daily_budget <= 0:
            errors.append("Daily budget must be positive")
        
        if config.bid_ceiling and config.bid_floor and config.bid_ceiling <= config.bid_floor:
            errors.append("Bid ceiling must be greater than bid floor")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    async def _trigger_auto_optimization(self, campaign_id: str, config: OptimizationConfig):
        """Trigger automatic optimization if conditions are met."""
        try:
            # Check if we have enough data
            performance_data = self.performance_data[campaign_id]
            if len(performance_data) < 50:  # Need at least 50 data points
                return
            
            # Calculate performance metrics
            recent_data = performance_data[-50:]
            
            # Emit optimization event
            await event_bus.emit(
                'auto_optimization_triggered',
                {
                    'campaign_id': campaign_id,
                    'strategy': config.strategy,
                    'data_points': len(recent_data),
                    'performance_data': recent_data
                },
                source='advertiser_portal',
                priority=EventPriority.NORMAL
            )
            
        except Exception as e:
            logger.error(f"Error triggering auto-optimization: {e}")
    
    def _should_enable_optimization(self, campaign_data: Dict[str, Any]) -> bool:
        """Determine if campaign should have bid optimization."""
        # Business logic for when to enable optimization
        campaign_type = campaign_data.get('campaign_type')
        budget = campaign_data.get('total_budget', 0)
        bidding_strategy = campaign_data.get('bidding_strategy')
        
        # Enable for campaigns with specific bidding strategies
        if bidding_strategy in ['enhanced_cpc', 'target_cpa', 'target_roas', 'maximize_conversions']:
            return True
        
        # Enable for high-budget campaigns
        if budget > 5000:
            return True
        
        # Enable for specific campaign types
        if campaign_type in ['search', 'social', 'display']:
            return True
        
        return False
    
    async def _create_default_optimization(self, campaign_data: Dict[str, Any]) -> Optional[OptimizationConfig]:
        """Create default optimization configuration."""
        try:
            campaign_id = campaign_data.get('id')
            bidding_strategy = campaign_data.get('bidding_strategy', 'manual_cpc')
            daily_budget = campaign_data.get('daily_budget')
            
            # Map bidding strategies to optimization strategies
            strategy_mapping = {
                'manual_cpc': 'manual_cpc',
                'enhanced_cpc': 'manual_cpc',
                'target_cpa': 'target_cpa',
                'target_roas': 'target_roas',
                'maximize_clicks': 'maximize_conversions',
                'maximize_conversions': 'maximize_conversions'
            }
            
            strategy = strategy_mapping.get(bidding_strategy, 'manual_cpc')
            
            config = OptimizationConfig(
                campaign_id=campaign_id,
                strategy=strategy,
                daily_budget=Decimal(str(daily_budget)) if daily_budget else None,
                learning_period_days=7,
                auto_optimize=True,
                min_confidence=0.7
            )
            
            return config
            
        except Exception as e:
            logger.error(f"Error creating default optimization: {e}")
            return None


# Global integration instance
bidding_optimization_integration = BiddingOptimizationIntegration()


# Export main classes
__all__ = [
    'BiddingOptimizationIntegration',
    'BidRequest',
    'BidResponse',
    'OptimizationConfig',
    'bidding_optimization_integration',
]
