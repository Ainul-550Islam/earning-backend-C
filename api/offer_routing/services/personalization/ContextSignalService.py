"""
Context Signal Service

Handles real-time context signals for personalization
in the offer routing system.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.cache import cache
from ....models import (
    OfferRoute, UserOfferHistory, OfferScore, OfferAffinityScore,
    UserPreferenceVector, RoutingDecisionLog, ContextualSignal
)
from ....choices import SignalType
from ....constants import (
    CONTEXT_SIGNAL_CACHE_TIMEOUT, SIGNAL_EXPIRY_HOURS,
    MAX_SIGNALS_PER_USER, SIGNAL_CONFIDENCE_THRESHOLD,
    CONTEXT_WEIGHTS, SIGNAL_PROCESSING_BATCH_SIZE
)
from ....exceptions import PersonalizationError, ContextSignalError
from ....utils import extract_context_features, calculate_signal_strength

User = get_user_model()
logger = logging.getLogger(__name__)


class ContextSignalService:
    """
    Service for real-time context signals in personalization.
    
    Processes and manages real-time signals for personalization:
    - Signal collection and validation
    - Signal aggregation and weighting
    - Context feature extraction
    - Real-time personalization updates
    - Signal decay and expiration
    
    Performance targets:
    - Signal processing: <5ms per signal
    - Context extraction: <10ms per user
    - Signal aggregation: <20ms for 100 signals
    - Cache hit rate: >90%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.signal_stats = {
            'total_signals': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_processing_time_ms': 0.0
        }
        
        # Signal processors
        self._initialize_signal_processors()
        
        # Context feature extractors
        self._initialize_context_extractors()
    
    def _initialize_signal_processors(self):
        """Initialize signal processors for different signal types."""
        self.signal_processors = {
            SignalType.TIME: self._process_time_signal,
            SignalType.LOCATION: self._process_location_signal,
            SignalType.DEVICE: self._process_device_signal,
            SignalType.BEHAVIOR: self._process_behavior_signal,
            SignalType.CONTEXT: self._process_context_signal,
            SignalType.SESSION: self._process_session_signal,
            SignalType.PREFERENCE: self._process_preference_signal,
            SignalType.ENVIRONMENT: self._process_environment_signal
        }
    
    def _initialize_context_extractors(self):
        """Initialize context feature extractors."""
        self.context_extractors = {
            'temporal': self._extract_temporal_features,
            'spatial': self._extract_spatial_features,
            'behavioral': self._extract_behavioral_features,
            'session': self._extract_session_features,
            'device': self._extract_device_features,
            'environmental': self._extract_environmental_features,
            'social': self._extract_social_features,
            'transactional': self._extract_transactional_features
        }
    
    def create_signal(self, user: User, signal_type: str, value: Any, 
                      confidence: float = 1.0, expires_hours: int = None) -> Optional[ContextualSignal]:
        """
        Create a new contextual signal.
        
        Args:
            user: User object
            signal_type: Type of signal
            value: Signal value/data
            confidence: Signal confidence (0.0-1.0)
            expires_hours: Hours until signal expires
            
        Returns:
            Created ContextualSignal or None
        """
        try:
            start_time = timezone.now()
            
            # Validate signal data
            if not self._validate_signal_data(signal_type, value, confidence):
                return None
            
            # Set expiration
            if expires_hours is None:
                expires_hours = SIGNAL_EXPIRY_HOURS
            
            expires_at = timezone.now() + timedelta(hours=expires_hours) if expires_hours > 0 else None
            
            # Create signal
            signal = ContextualSignal.objects.create(
                user=user,
                signal_type=signal_type,
                value=value,
                confidence=confidence,
                expires_at=expires_at
            )
            
            # Process signal immediately
            self._process_signal(signal)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_signal_stats(elapsed_ms)
            
            logger.info(f"Created {signal_type} signal for user {user.id}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating signal for user {user.id}: {e}")
            self.signal_stats['errors'] += 1
            return None
    
    def _validate_signal_data(self, signal_type: str, value: Any, confidence: float) -> bool:
        """Validate signal data before creation."""
        try:
            # Validate signal type
            valid_types = [choice[0] for choice in SignalType.CHOICES]
            if signal_type not in valid_types:
                logger.error(f"Invalid signal type: {signal_type}")
                return False
            
            # Validate confidence
            if not (0.0 <= confidence <= 1.0):
                logger.error(f"Invalid confidence value: {confidence}")
                return False
            
            # Validate value based on signal type
            if signal_type == SignalType.TIME:
                return self._validate_time_signal_value(value)
            elif signal_type == SignalType.LOCATION:
                return self._validate_location_signal_value(value)
            elif signal_type == SignalType.DEVICE:
                return self._validate_device_signal_value(value)
            elif signal_type == SignalType.BEHAVIOR:
                return self._validate_behavior_signal_value(value)
            elif signal_type == SignalType.CONTEXT:
                return self._validate_context_signal_value(value)
            elif signal_type == SignalType.SESSION:
                return self._validate_session_signal_value(value)
            elif signal_type == SignalType.PREFERENCE:
                return self._validate_preference_signal_value(value)
            elif signal_type == SignalType.ENVIRONMENT:
                return self._validate_environment_signal_value(value)
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating signal data: {e}")
            return False
    
    def _validate_time_signal_value(self, value: Any) -> bool:
        """Validate time signal value."""
        try:
            if isinstance(value, dict):
                required_fields = ['hour_of_day']
                return all(field in value for field in required_fields)
            return False
        except Exception:
            return False
    
    def _validate_location_signal_value(self, value: Any) -> bool:
        """Validate location signal value."""
        try:
            if isinstance(value, dict):
                required_fields = ['country']
                return all(field in value for field in required_fields)
            return False
        except Exception:
            return False
    
    def _validate_device_signal_value(self, value: Any) -> bool:
        """Validate device signal value."""
        try:
            if isinstance(value, dict):
                required_fields = ['device_type']
                return all(field in value for field in required_fields)
            return False
        except Exception:
            return False
    
    def _validate_behavior_signal_value(self, value: Any) -> bool:
        """Validate behavior signal value."""
        try:
            if isinstance(value, dict):
                required_fields = ['event_type', 'count']
                return all(field in value for field in required_fields)
            return False
        except Exception:
            return False
    
    def _validate_context_signal_value(self, value: Any) -> bool:
        """Validate context signal value."""
        try:
            # Context signals can be flexible
            return isinstance(value, (dict, str, int, float, bool, list))
        except Exception:
            return False
    
    def _validate_session_signal_value(self, value: Any) -> bool:
        """Validate session signal value."""
        try:
            if isinstance(value, dict):
                required_fields = ['session_id']
                return all(field in value for field in required_fields)
            return False
        except Exception:
            return False
    
    def _validate_preference_signal_value(self, value: Any) -> bool:
        """Validate preference signal value."""
        try:
            if isinstance(value, dict):
                required_fields = ['preference_type', 'preference_value']
                return all(field in value for field in required_fields)
            return False
        except Exception:
            return False
    
    def _validate_environment_signal_value(self, value: Any) -> bool:
        """Validate environment signal value."""
        try:
            # Environment signals can be flexible
            return isinstance(value, (dict, str, int, float, bool))
        except Exception:
            return False
    
    def _process_signal(self, signal: ContextualSignal):
        """Process a newly created signal."""
        try:
            # Get appropriate processor
            processor = self.signal_processors.get(signal.signal_type)
            
            if processor:
                processor(signal)
            else:
                logger.warning(f"No processor for signal type: {signal.signal_type}")
            
            # Update user context cache
            self._update_user_context_cache(signal.user)
            
        except Exception as e:
            logger.error(f"Error processing signal {signal.id}: {e}")
    
    def _process_time_signal(self, signal: ContextualSignal):
        """Process time-based signals."""
        try:
            value = signal.value
            
            if isinstance(value, dict):
                hour_of_day = value.get('hour_of_day')
                day_of_week = value.get('day_of_week')
                
                # Create time-based features
                time_features = {
                    'is_morning': 6 <= hour_of_day <= 11,
                    'is_afternoon': 12 <= hour_of_day <= 17,
                    'is_evening': 18 <= hour_of_day <= 22,
                    'is_night': 23 <= hour_of_day or hour_of_day <= 5,
                    'is_weekend': day_of_week >= 5,  # Saturday=5, Sunday=6
                    'is_business_hours': 9 <= hour_of_day <= 17,
                    'time_of_day_category': self._get_time_category(hour_of_day)
                }
                
                # Cache processed features
                cache_key = f"time_features:{signal.user.id}"
                self.cache_service.set(cache_key, time_features, CONTEXT_SIGNAL_CACHE_TIMEOUT)
                
        except Exception as e:
            logger.error(f"Error processing time signal: {e}")
    
    def _process_location_signal(self, signal: ContextualSignal):
        """Process location-based signals."""
        try:
            value = signal.value
            
            if isinstance(value, dict):
                country = value.get('country')
                region = value.get('region')
                city = value.get('city')
                
                # Create location-based features
                location_features = {
                    'country': country,
                    'region': region,
                    'city': city,
                    'is_high_value_country': country in ['US', 'CA', 'UK', 'AU'],
                    'is_metro_area': self._is_metro_area(city, country),
                    'geographic_cluster': self._get_geographic_cluster(country, region)
                }
                
                # Cache processed features
                cache_key = f"location_features:{signal.user.id}"
                self.cache_service.set(cache_key, location_features, CONTEXT_SIGNAL_CACHE_TIMEOUT)
                
        except Exception as e:
            logger.error(f"Error processing location signal: {e}")
    
    def _process_device_signal(self, signal: ContextualSignal):
        """Process device-based signals."""
        try:
            value = signal.value
            
            if isinstance(value, dict):
                device_type = value.get('device_type')
                os_type = value.get('os_type')
                browser = value.get('browser')
                
                # Create device-based features
                device_features = {
                    'device_type': device_type,
                    'os_type': os_type,
                    'browser': browser,
                    'is_mobile': device_type in ['mobile', 'tablet'],
                    'is_desktop': device_type == 'desktop',
                    'device_category': self._get_device_category(device_type),
                    'browser_category': self._get_browser_category(browser)
                }
                
                # Cache processed features
                cache_key = f"device_features:{signal.user.id}"
                self.cache_service.set(cache_key, device_features, CONTEXT_SIGNAL_CACHE_TIMEOUT)
                
        except Exception as e:
            logger.error(f"Error processing device signal: {e}")
    
    def _process_behavior_signal(self, signal: ContextualSignal):
        """Process behavior-based signals."""
        try:
            value = signal.value
            
            if isinstance(value, dict):
                event_type = value.get('event_type')
                count = value.get('count', 1)
                window_days = value.get('window_days', 30)
                
                # Create behavior-based features
                behavior_features = {
                    'recent_event_type': event_type,
                    'event_frequency': count,
                    'behavioral_intent': self._infer_behavioral_intent(event_type),
                    'engagement_level': self._calculate_engagement_level(event_type, count),
                    'conversion_probability': self._estimate_conversion_probability(event_type)
                }
                
                # Cache processed features
                cache_key = f"behavior_features:{signal.user.id}"
                self.cache_service.set(cache_key, behavior_features, CONTEXT_SIGNAL_CACHE_TIMEOUT)
                
        except Exception as e:
            logger.error(f"Error processing behavior signal: {e}")
    
    def _process_context_signal(self, signal: ContextualSignal):
        """Process general context signals."""
        try:
            value = signal.value
            
            # Create context features
            context_features = {
                'raw_context': value,
                'context_type': self._classify_context_type(value),
                'context_strength': self._calculate_context_strength(value),
                'is_actionable': self._is_actionable_context(value)
            }
            
            # Cache processed features
            cache_key = f"context_features:{signal.user.id}"
            self.cache_service.set(cache_key, context_features, CONTEXT_SIGNAL_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error processing context signal: {e}")
    
    def _process_session_signal(self, signal: ContextualSignal):
        """Process session-based signals."""
        try:
            value = signal.value
            
            if isinstance(value, dict):
                session_id = value.get('session_id')
                session_duration = value.get('session_duration')
                page_views = value.get('page_views', 0)
                
                # Create session-based features
                session_features = {
                    'session_id': session_id,
                    'session_duration': session_duration,
                    'page_views': page_views,
                    'is_long_session': session_duration > 1800,  # 30 minutes
                    'is_engaged_session': page_views > 5,
                    'session_quality': self._calculate_session_quality(session_duration, page_views)
                }
                
                # Cache processed features
                cache_key = f"session_features:{signal.user.id}"
                self.cache_service.set(cache_key, session_features, CONTEXT_SIGNAL_CACHE_TIMEOUT)
                
        except Exception as e:
            logger.error(f"Error processing session signal: {e}")
    
    def _process_preference_signal(self, signal: ContextualSignal):
        """Process preference-based signals."""
        try:
            value = signal.value
            
            if isinstance(value, dict):
                preference_type = value.get('preference_type')
                preference_value = value.get('preference_value')
                
                # Create preference-based features
                preference_features = {
                    'preference_type': preference_type,
                    'preference_value': preference_value,
                    'preference_strength': signal.confidence,
                    'is_strong_preference': signal.confidence > 0.7,
                    'preference_category': self._categorize_preference(preference_type)
                }
                
                # Cache processed features
                cache_key = f"preference_features:{signal.user.id}"
                self.cache_service.set(cache_key, preference_features, CONTEXT_SIGNAL_CACHE_TIMEOUT)
                
        except Exception as e:
            logger.error(f"Error processing preference signal: {e}")
    
    def _process_environment_signal(self, signal: ContextualSignal):
        """Process environment-based signals."""
        try:
            value = signal.value
            
            # Create environment features
            environment_features = {
                'raw_environment': value,
                'environment_type': self._classify_environment_type(value),
                'impact_level': self._assess_environment_impact(value),
                'is_favorable': self._is_favorable_environment(value)
            }
            
            # Cache processed features
            cache_key = f"environment_features:{signal.user.id}"
            self.cache_service.set(cache_key, environment_features, CONTEXT_SIGNAL_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error processing environment signal: {e}")
    
    def get_user_context(self, user: User, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get comprehensive user context for personalization.
        
        Args:
            user: User object
            context: Additional context data
            
        Returns:
            Comprehensive user context
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"user_context:{user.id}"
            cached_context = self.cache_service.get(cache_key)
            
            if cached_context:
                self.signal_stats['cache_hits'] += 1
                return cached_context
            
            # Get active signals
            active_signals = self._get_active_signals(user)
            
            # Extract features from all signal types
            context_features = {}
            
            for extractor_name, extractor in self.context_extractors.items():
                try:
                    features = extractor(user, active_signals, context)
                    if features:
                        context_features[extractor_name] = features
                except Exception as e:
                    logger.warning(f"Error in {extractor_name} extractor: {e}")
                    continue
            
            # Combine features into comprehensive context
            comprehensive_context = self._combine_context_features(context_features, user, context)
            
            # Cache result
            self.cache_service.set(cache_key, comprehensive_context, CONTEXT_SIGNAL_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_signal_stats(elapsed_ms)
            
            return comprehensive_context
            
        except Exception as e:
            logger.error(f"Error getting user context for {user.id}: {e}")
            return {}
    
    def _get_active_signals(self, user: User) -> List[ContextualSignal]:
        """Get active signals for a user."""
        try:
            return ContextualSignal.objects.filter(
                user=user,
                expires_at__gt=timezone.now()
            ).order_by('-created_at')[:MAX_SIGNALS_PER_USER]
            
        except Exception as e:
            logger.error(f"Error getting active signals for user {user.id}: {e}")
            return []
    
    def _extract_temporal_features(self, user: User, signals: List[ContextualSignal], 
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract temporal features."""
        try:
            # Get time signals
            time_signals = [s for s in signals if s.signal_type == SignalType.TIME]
            
            if not time_signals:
                return {}
            
            # Get most recent time signal
            latest_time_signal = time_signals[0]
            
            return {
                'hour_of_day': latest_time_signal.value.get('hour_of_day'),
                'day_of_week': latest_time_signal.value.get('day_of_week'),
                'is_business_hours': latest_time_signal.value.get('is_business_hours', False),
                'time_category': latest_time_signal.value.get('time_category'),
                'signal_confidence': latest_time_signal.confidence
            }
            
        except Exception as e:
            logger.error(f"Error extracting temporal features: {e}")
            return {}
    
    def _extract_spatial_features(self, user: User, signals: List[ContextualSignal], 
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract spatial features."""
        try:
            # Get location signals
            location_signals = [s for s in signals if s.signal_type == SignalType.LOCATION]
            
            if not location_signals:
                return {}
            
            # Get most recent location signal
            latest_location_signal = location_signals[0]
            
            return {
                'country': latest_location_signal.value.get('country'),
                'region': latest_location_signal.value.get('region'),
                'city': latest_location_signal.value.get('city'),
                'is_high_value_country': latest_location_signal.value.get('is_high_value_country', False),
                'geographic_cluster': latest_location_signal.value.get('geographic_cluster'),
                'signal_confidence': latest_location_signal.confidence
            }
            
        except Exception as e:
            logger.error(f"Error extracting spatial features: {e}")
            return {}
    
    def _extract_behavioral_features(self, user: User, signals: List[ContextualSignal], 
                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract behavioral features."""
        try:
            # Get behavior signals
            behavior_signals = [s for s in signals if s.signal_type == SignalType.BEHAVIOR]
            
            if not behavior_signals:
                return {}
            
            # Aggregate behavioral signals
            recent_events = []
            engagement_scores = []
            
            for signal in behavior_signals:
                signal_data = signal.value
                recent_events.append({
                    'event_type': signal_data.get('event_type'),
                    'frequency': signal_data.get('count', 1),
                    'confidence': signal.confidence
                })
                
                engagement = signal_data.get('engagement_level', 0.5)
                if engagement:
                    engagement_scores.append(engagement * signal.confidence)
            
            return {
                'recent_events': recent_events,
                'avg_engagement': sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0.0,
                'behavioral_intent': self._aggregate_behavioral_intents(recent_events),
                'activity_level': self._calculate_activity_level(recent_events)
            }
            
        except Exception as e:
            logger.error(f"Error extracting behavioral features: {e}")
            return {}
    
    def _extract_session_features(self, user: User, signals: List[ContextualSignal], 
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract session features."""
        try:
            # Get session signals
            session_signals = [s for s in signals if s.signal_type == SignalType.SESSION]
            
            if not session_signals:
                return {}
            
            # Get most recent session signal
            latest_session_signal = session_signals[0]
            
            return {
                'session_id': latest_session_signal.value.get('session_id'),
                'session_duration': latest_session_signal.value.get('session_duration'),
                'page_views': latest_session_signal.value.get('page_views', 0),
                'is_long_session': latest_session_signal.value.get('is_long_session', False),
                'session_quality': latest_session_signal.value.get('session_quality', 0.5),
                'signal_confidence': latest_session_signal.confidence
            }
            
        except Exception as e:
            logger.error(f"Error extracting session features: {e}")
            return {}
    
    def _extract_device_features(self, user: User, signals: List[ContextualSignal], 
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract device features."""
        try:
            # Get device signals
            device_signals = [s for s in signals if s.signal_type == SignalType.DEVICE]
            
            if not device_signals:
                return {}
            
            # Get most recent device signal
            latest_device_signal = device_signals[0]
            
            return {
                'device_type': latest_device_signal.value.get('device_type'),
                'os_type': latest_device_signal.value.get('os_type'),
                'browser': latest_device_signal.value.get('browser'),
                'is_mobile': latest_device_signal.value.get('is_mobile', False),
                'device_category': latest_device_signal.value.get('device_category'),
                'signal_confidence': latest_device_signal.confidence
            }
            
        except Exception as e:
            logger.error(f"Error extracting device features: {e}")
            return {}
    
    def _extract_environmental_features(self, user: User, signals: List[ContextualSignal], 
                                      context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract environmental features."""
        try:
            # Get environment signals
            env_signals = [s for s in signals if s.signal_type == SignalType.ENVIRONMENT]
            
            if not env_signals:
                return {}
            
            # Aggregate environment signals
            environmental_factors = []
            
            for signal in env_signals:
                environmental_factors.append({
                    'factor_type': signal.value.get('factor_type'),
                    'impact_level': signal.value.get('impact_level'),
                    'confidence': signal.confidence
                })
            
            return {
                'environmental_factors': environmental_factors,
                'overall_impact': self._calculate_overall_impact(environmental_factors),
                'favorability_score': self._calculate_favorability_score(environmental_factors)
            }
            
        except Exception as e:
            logger.error(f"Error extracting environmental features: {e}")
            return {}
    
    def _extract_social_features(self, user: User, signals: List[ContextualSignal], 
                               context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract social features."""
        try:
            # Social features would come from social media integration
            # For now, return basic social context
            return {
                'social_connections': getattr(user, 'social_connections', 0),
                'social_influence': getattr(user, 'social_influence', 0.0),
                'social_activity': getattr(user, 'social_activity', 0.0)
            }
            
        except Exception as e:
            logger.error(f"Error extracting social features: {e}")
            return {}
    
    def _extract_transactional_features(self, user: User, signals: List[ContextualSignal], 
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract transactional features."""
        try:
            # Get recent transaction data
            thirty_days_ago = timezone.now() - timedelta(days=30)
            
            transaction_data = UserOfferHistory.objects.filter(
                user=user,
                completed_at__gte=thirty_days_ago
            ).aggregate(
                total_transactions=Count('id'),
                total_value=Sum('conversion_value'),
                avg_value=Avg('conversion_value')
            )
            
            return {
                'recent_transactions': transaction_data['total_transactions'],
                'recent_value': float(transaction_data['total_value'] or 0.0),
                'avg_transaction_value': float(transaction_data['avg_value'] or 0.0),
                'transaction_frequency': transaction_data['total_transactions'] / 30.0
            }
            
        except Exception as e:
            logger.error(f"Error extracting transactional features: {e}")
            return {}
    
    def _combine_context_features(self, features: Dict[str, Any], user: User, 
                                context: Dict[str, Any]) -> Dict[str, Any]:
        """Combine all context features into comprehensive context."""
        try:
            combined_context = {
                'user_id': user.id,
                'timestamp': timezone.now().isoformat(),
                'features': features,
                'weights': CONTEXT_WEIGHTS,
                'signal_count': sum(len(f) if isinstance(f, dict) else 0 for f in features.values()),
                'last_updated': timezone.now().isoformat()
            }
            
            # Add additional context
            if context:
                combined_context['additional_context'] = context
            
            # Calculate overall context score
            context_score = self._calculate_context_score(features)
            combined_context['context_score'] = context_score
            
            return combined_context
            
        except Exception as e:
            logger.error(f"Error combining context features: {e}")
            return {}
    
    def _calculate_context_score(self, features: Dict[str, Any]) -> float:
        """Calculate overall context score."""
        try:
            total_score = 0.0
            total_weight = 0.0
            
            for feature_type, feature_data in features.items():
                if feature_type in CONTEXT_WEIGHTS and feature_data:
                    weight = CONTEXT_WEIGHTS[feature_type]
                    
                    # Calculate feature score
                    feature_score = self._calculate_feature_score(feature_type, feature_data)
                    
                    total_score += feature_score * weight
                    total_weight += weight
            
            if total_weight > 0:
                return total_score / total_weight
            else:
                return 0.5  # Default score
                
        except Exception as e:
            logger.error(f"Error calculating context score: {e}")
            return 0.5
    
    def _calculate_feature_score(self, feature_type: str, feature_data: Any) -> float:
        """Calculate score for a specific feature type."""
        try:
            if feature_type == 'temporal':
                return self._score_temporal_features(feature_data)
            elif feature_type == 'spatial':
                return self._score_spatial_features(feature_data)
            elif feature_type == 'behavioral':
                return self._score_behavioral_features(feature_data)
            elif feature_type == 'session':
                return self._score_session_features(feature_data)
            elif feature_type == 'device':
                return self._score_device_features(feature_data)
            elif feature_type == 'environmental':
                return self._score_environmental_features(feature_data)
            else:
                return 0.5  # Default score
                
        except Exception as e:
            logger.error(f"Error calculating feature score for {feature_type}: {e}")
            return 0.5
    
    def _score_temporal_features(self, features: Dict[str, Any]) -> float:
        """Score temporal features."""
        try:
            score = 0.5  # Base score
            
            if features.get('is_business_hours'):
                score += 0.2
            
            if features.get('time_category') == 'peak':
                score += 0.3
            
            return min(1.0, max(0.0, score))
            
        except Exception:
            return 0.5
    
    def _score_spatial_features(self, features: Dict[str, Any]) -> float:
        """Score spatial features."""
        try:
            score = 0.5  # Base score
            
            if features.get('is_high_value_country'):
                score += 0.2
            
            if features.get('geographic_cluster') == 'metro':
                score += 0.1
            
            return min(1.0, max(0.0, score))
            
        except Exception:
            return 0.5
    
    def _score_behavioral_features(self, features: Dict[str, Any]) -> float:
        """Score behavioral features."""
        try:
            avg_engagement = features.get('avg_engagement', 0.5)
            activity_level = features.get('activity_level', 0.5)
            
            return (avg_engagement * 0.6) + (activity_level * 0.4)
            
        except Exception:
            return 0.5
    
    def _score_session_features(self, features: Dict[str, Any]) -> float:
        """Score session features."""
        try:
            session_quality = features.get('session_quality', 0.5)
            is_long_session = features.get('is_long_session', False)
            
            score = session_quality
            if is_long_session:
                score += 0.2
            
            return min(1.0, max(0.0, score))
            
        except Exception:
            return 0.5
    
    def _score_device_features(self, features: Dict[str, Any]) -> float:
        """Score device features."""
        try:
            score = 0.5  # Base score
            
            if features.get('is_mobile'):
                score += 0.1
            
            device_category = features.get('device_category', 'unknown')
            if device_category == 'premium':
                score += 0.2
            
            return min(1.0, max(0.0, score))
            
        except Exception:
            return 0.5
    
    def _score_environmental_features(self, features: Dict[str, Any]) -> float:
        """Score environmental features."""
        try:
            favorability_score = features.get('favorability_score', 0.5)
            overall_impact = features.get('overall_impact', 0.5)
            
            return (favorability_score * 0.7) + (overall_impact * 0.3)
            
        except Exception:
            return 0.5
    
    # Helper methods for signal processing
    def _get_time_category(self, hour: int) -> str:
        """Get time category from hour."""
        if 6 <= hour <= 11:
            return 'morning'
        elif 12 <= hour <= 17:
            return 'afternoon'
        elif 18 <= hour <= 22:
            return 'evening'
        else:
            return 'night'
    
    def _is_metro_area(self, city: str, country: str) -> bool:
        """Check if city is in a metro area."""
        metro_cities = {
            'US': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix'],
            'UK': ['London', 'Manchester', 'Birmingham'],
            'CA': ['Toronto', 'Vancouver', 'Montreal']
        }
        
        return city in metro_cities.get(country, [])
    
    def _get_geographic_cluster(self, country: str, region: str) -> str:
        """Get geographic cluster."""
        if country in ['US', 'CA']:
            return 'north_america'
        elif country in ['UK', 'DE', 'FR', 'IT']:
            return 'europe'
        elif country in ['CN', 'JP', 'KR']:
            return 'asia_pacific'
        else:
            return 'other'
    
    def _get_device_category(self, device_type: str) -> str:
        """Get device category."""
        if device_type in ['mobile', 'tablet']:
            return 'mobile'
        elif device_type == 'desktop':
            return 'desktop'
        else:
            return 'unknown'
    
    def _get_browser_category(self, browser: str) -> str:
        """Get browser category."""
        modern_browsers = ['chrome', 'firefox', 'safari', 'edge']
        
        if browser.lower() in modern_browsers:
            return 'modern'
        else:
            return 'legacy'
    
    def _infer_behavioral_intent(self, event_type: str) -> str:
        """Infer behavioral intent from event type."""
        intent_mapping = {
            'offer_view': 'browsing',
            'offer_click': 'interested',
            'add_to_cart': 'considering',
            'purchase': 'converting',
            'search': 'exploring'
        }
        
        return intent_mapping.get(event_type, 'unknown')
    
    def _calculate_engagement_level(self, event_type: str, count: int) -> float:
        """Calculate engagement level."""
        engagement_weights = {
            'offer_view': 0.1,
            'offer_click': 0.5,
            'add_to_cart': 0.7,
            'purchase': 1.0,
            'search': 0.3
        }
        
        weight = engagement_weights.get(event_type, 0.1)
        return min(1.0, weight * min(count, 10) / 10)
    
    def _estimate_conversion_probability(self, event_type: str) -> float:
        """Estimate conversion probability from event type."""
        conversion_probabilities = {
            'offer_view': 0.02,
            'offer_click': 0.15,
            'add_to_cart': 0.35,
            'search': 0.05
        }
        
        return conversion_probabilities.get(event_type, 0.05)
    
    def _classify_context_type(self, value: Any) -> str:
        """Classify context type."""
        if isinstance(value, dict):
            return 'structured'
        elif isinstance(value, str):
            return 'textual'
        elif isinstance(value, (int, float)):
            return 'numeric'
        else:
            return 'complex'
    
    def _calculate_context_strength(self, value: Any) -> float:
        """Calculate context strength."""
        if isinstance(value, dict):
            return min(1.0, len(value) / 10.0)
        elif isinstance(value, str):
            return min(1.0, len(value) / 100.0)
        else:
            return 0.5
    
    def _is_actionable_context(self, value: Any) -> bool:
        """Check if context is actionable."""
        actionable_keywords = ['urgent', 'important', 'critical', 'immediate']
        
        if isinstance(value, str):
            return any(keyword in value.lower() for keyword in actionable_keywords)
        elif isinstance(value, dict):
            return any(str(v).lower() in actionable_keywords for v in value.values())
        
        return False
    
    def _calculate_session_quality(self, duration: int, page_views: int) -> float:
        """Calculate session quality score."""
        if duration <= 0:
            return 0.0
        
        # Quality based on duration and page views
        duration_score = min(1.0, duration / 1800)  # 30 minutes = 1.0
        page_view_score = min(1.0, page_views / 20)  # 20 pages = 1.0
        
        return (duration_score * 0.6) + (page_view_score * 0.4)
    
    def _categorize_preference(self, preference_type: str) -> str:
        """Categorize preference type."""
        category_mapping = {
            'category': 'content',
            'brand': 'brand',
            'price': 'price',
            'feature': 'feature',
            'style': 'style'
        }
        
        return category_mapping.get(preference_type, 'other')
    
    def _classify_environment_type(self, value: Any) -> str:
        """Classify environment type."""
        if isinstance(value, dict):
            env_type = value.get('type', '').lower()
            
            if env_type in ['weather', 'temperature', 'season']:
                return 'weather'
            elif env_type in ['market', 'economic', 'trend']:
                return 'market'
            elif env_type in ['event', 'holiday', 'promotion']:
                return 'promotional'
        
        return 'general'
    
    def _assess_environment_impact(self, value: Any) -> float:
        """Assess environment impact level."""
        if isinstance(value, dict):
            return value.get('impact_level', 0.5)
        
        return 0.5
    
    def _is_favorable_environment(self, value: Any) -> bool:
        """Check if environment is favorable."""
        if isinstance(value, dict):
            return value.get('is_favorable', False)
        
        return False
    
    def _aggregate_behavioral_intents(self, events: List[Dict[str, Any]]) -> str:
        """Aggregate behavioral intents."""
        if not events:
            return 'unknown'
        
        intent_counts = {}
        for event in events:
            intent = event.get('behavioral_intent', 'unknown')
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # Return most common intent
        return max(intent_counts, key=intent_counts.get) if intent_counts else 'unknown'
    
    def _calculate_activity_level(self, events: List[Dict[str, Any]]) -> float:
        """Calculate activity level."""
        if not events:
            return 0.0
        
        total_activity = 0.0
        for event in events:
            frequency = event.get('frequency', 1)
            confidence = event.get('confidence', 0.5)
            total_activity += frequency * confidence
        
        return min(1.0, total_activity / len(events))
    
    def _calculate_overall_impact(self, factors: List[Dict[str, Any]]) -> float:
        """Calculate overall environmental impact."""
        if not factors:
            return 0.5
        
        total_impact = 0.0
        for factor in factors:
            impact = factor.get('impact_level', 0.5)
            confidence = factor.get('confidence', 0.5)
            total_impact += impact * confidence
        
        return total_impact / len(factors)
    
    def _calculate_favorability_score(self, factors: List[Dict[str, Any]]) -> float:
        """Calculate favorability score."""
        if not factors:
            return 0.5
        
        favorable_count = 0
        for factor in factors:
            if factor.get('is_favorable', False):
                favorable_count += 1
        
        return favorable_count / len(factors)
    
    def _update_user_context_cache(self, user: User):
        """Update user context cache after signal processing."""
        try:
            # Invalidate user context cache to force refresh
            cache_key = f"user_context:{user.id}"
            self.cache_service.delete(cache_key)
            
        except Exception as e:
            logger.error(f"Error updating user context cache: {e}")
    
    def _update_signal_stats(self, elapsed_ms: float):
        """Update signal processing statistics."""
        self.signal_stats['total_signals'] += 1
        
        # Update average time
        current_avg = self.signal_stats['avg_processing_time_ms']
        total_signals = self.signal_stats['total_signals']
        self.signal_stats['avg_processing_time_ms'] = (
            (current_avg * (total_signals - 1) + elapsed_ms) / total_signals
        )
    
    def get_context_signal_stats(self) -> Dict[str, Any]:
        """Get context signal service statistics."""
        total_requests = self.signal_stats['total_signals']
        cache_hit_rate = (
            self.signal_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_signals': total_requests,
            'cache_hits': self.signal_stats['cache_hits'],
            'cache_misses': total_requests - self.signal_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.signal_stats['errors'],
            'error_rate': self.signal_stats['errors'] / max(1, total_requests),
            'avg_processing_time_ms': self.signal_stats['avg_processing_time_ms'],
            'supported_signal_types': list(self.signal_processors.keys()),
            'supported_extractors': list(self.context_extractors.keys())
        }
    
    def clear_cache(self, user_id: int = None):
        """Clear context signal cache."""
        try:
            if user_id:
                # Clear specific user cache
                cache_keys = [
                    f"user_context:{user_id}",
                    f"time_features:{user_id}",
                    f"location_features:{user_id}",
                    f"device_features:{user_id}",
                    f"behavior_features:{user_id}",
                    f"context_features:{user_id}",
                    f"session_features:{user_id}",
                    f"preference_features:{user_id}",
                    f"environment_features:{user_id}"
                ]
                
                for key in cache_keys:
                    self.cache_service.delete(key)
                
                logger.info(f"Cleared context cache for user {user_id}")
            else:
                # Clear all context cache
                logger.info("Cache clearing for all users not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing context cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on context signal service."""
        try:
            # Test signal creation
            test_user = User(id=1, username='test')
            test_signal = self.create_signal(
                test_user, SignalType.TIME, {'hour_of_day': 14}, 0.9
            )
            
            # Test context extraction
            test_context = self.get_user_context(test_user)
            
            return {
                'status': 'healthy',
                'test_signal_creation': test_signal is not None,
                'test_context_extraction': len(test_context) > 0,
                'stats': self.get_context_signal_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
