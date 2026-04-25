"""
Postback Service for Offer Routing System

This module provides comprehensive postback handling and conversion tracking,
including validation, fraud detection, and revenue attribution.
"""

import logging
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse

from ..models import (
    UserOfferHistory, RoutingDecisionLog, OfferRoute,
    RoutingConfig, SecurityEvent, UserPreferenceVector
)
from ..utils import get_client_ip, validate_ip_address
from .fraud import FraudDetectionService

User = get_user_model()
logger = logging.getLogger(__name__)


class PostbackService:
    """
    Comprehensive postback service for conversion tracking.
    
    Handles:
    - Postback validation and security
    - Conversion attribution
    - Revenue tracking
    - Fraud detection
    - Multi-network support
    """
    
    def __init__(self):
        self.fraud_service = FraudDetectionService()
        self.cache_timeout = 3600  # 1 hour
        self.postback_timeout = 86400  # 24 hours
        self.max_retries = 3
        self.retry_delay = 60  # seconds
    
    def process_postback(self, postback_data: Dict[str, any]) -> Dict[str, any]:
        """
        Process incoming postback for conversion tracking.
        
        Args:
            postback_data: Dictionary containing postback parameters
            
        Returns:
            Dictionary containing processing results
        """
        try:
            # Validate postback data
            validation_result = self._validate_postback(postback_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'status': 'invalid'
                }
            
            # Extract required fields
            user_id = postback_data.get('user_id')
            offer_id = postback_data.get('offer_id')
            conversion_id = postback_data.get('conversion_id')
            revenue = postback_data.get('revenue', 0)
            event_type = postback_data.get('event_type', 'conversion')
            
            # Check for duplicate postback
            if self._is_duplicate_postback(conversion_id):
                return {
                    'success': False,
                    'error': 'Duplicate postback',
                    'status': 'duplicate'
                }
            
            # Verify user and offer
            user = self._verify_user(user_id)
            offer = self._verify_offer(offer_id)
            
            if not user or not offer:
                return {
                    'success': False,
                    'error': 'Invalid user or offer',
                    'status': 'invalid'
                }
            
            # Check for fraud
            fraud_analysis = self._analyze_postback_fraud(postback_data, user, offer)
            if fraud_analysis['risk_score'] > 80:  # High risk threshold
                return {
                    'success': False,
                    'error': 'High fraud risk detected',
                    'status': 'fraud_detected',
                    'fraud_analysis': fraud_analysis
                }
            
            # Process conversion
            with transaction.atomic():
                # Create or update conversion record
                conversion = self._create_conversion_record(
                    user=user,
                    offer=offer,
                    postback_data=postback_data,
                    fraud_analysis=fraud_analysis
                )
                
                # Update user history
                self._update_user_history(conversion, postback_data)
                
                # Update analytics
                self._update_conversion_analytics(conversion, postback_data)
                
                # Update user preferences
                self._update_user_preferences(user, offer, postback_data)
                
                # Cache postback to prevent duplicates
                self._cache_postback(conversion_id, postback_data)
                
                # Log security event
                self._log_conversion_event(conversion, postback_data)
            
            logger.info(f"Postback processed successfully: conversion_id={conversion_id}, user_id={user_id}, offer_id={offer_id}")
            
            return {
                'success': True,
                'conversion_id': conversion.id,
                'status': 'processed',
                'revenue': revenue,
                'fraud_score': fraud_analysis['risk_score']
            }
            
        except Exception as e:
            logger.error(f"Error processing postback: {e}")
            return {
                'success': False,
                'error': str(e),
                'status': 'error'
            }
    
    def validate_postback_signature(self, postback_data: Dict[str, any], signature: str) -> bool:
        """
        Validate postback signature for security.
        
        Args:
            postback_data: Postback data
            signature: HMAC signature to validate
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Get secret key from settings
            secret_key = getattr(settings, 'POSTBACK_SECRET_KEY', '')
            
            if not secret_key:
                logger.warning("POSTBACK_SECRET_KEY not configured")
                return False
            
            # Create signature from postback data
            # Sort keys for consistent signature
            sorted_data = {k: v for k, v in sorted(postback_data.items())}
            data_string = json.dumps(sorted_data, separators=(',', ':'))
            
            # Generate HMAC signature
            expected_signature = hmac.new(
                secret_key.encode(),
                data_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error validating postback signature: {e}")
            return False
    
    def get_conversion_attribution(self, conversion_id: str) -> Dict[str, any]:
        """
        Get attribution data for a conversion.
        
        Args:
            conversion_id: Conversion ID
            
        Returns:
            Dictionary containing attribution data
        """
        try:
            # Get conversion record
            conversion = UserOfferHistory.objects.filter(
                conversion_id=conversion_id
            ).select_related('user', 'offer', 'route').first()
            
            if not conversion:
                return {'error': 'Conversion not found'}
            
            # Get routing decision that led to this conversion
            routing_decision = RoutingDecisionLog.objects.filter(
                user_id=conversion.user_id,
                offer_id=conversion.offer_id,
                created_at__lte=conversion.completed_at
            ).order_by('-created_at').first()
            
            # Build attribution data
            attribution_data = {
                'conversion_id': conversion_id,
                'user_id': conversion.user_id,
                'offer_id': conversion.offer_id,
                'route_id': conversion.route_id,
                'conversion_time': conversion.completed_at,
                'revenue': conversion.revenue,
                'attribution_window': self._calculate_attribution_window(conversion, routing_decision),
                'touchpoints': self._get_touchpoints(conversion.user_id, conversion.offer_id),
                'attribution_model': self._get_attribution_model(conversion),
                'fraud_score': conversion.fraud_score,
                'ip_address': conversion.ip_address,
                'user_agent': conversion.user_agent
            }
            
            return attribution_data
            
        except Exception as e:
            logger.error(f"Error getting conversion attribution: {e}")
            return {'error': str(e)}
    
    def process_reversal(self, reversal_data: Dict[str, any]) -> Dict[str, any]:
        """
        Process conversion reversal (chargeback, refund, etc.).
        
        Args:
            reversal_data: Dictionary containing reversal data
            
        Returns:
            Dictionary containing reversal results
        """
        try:
            # Validate reversal data
            validation_result = self._validate_reversal(reversal_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error']
                }
            
            # Get original conversion
            conversion_id = reversal_data.get('conversion_id')
            conversion = UserOfferHistory.objects.filter(
                conversion_id=conversion_id,
                completed_at__isnull=False
            ).first()
            
            if not conversion:
                return {
                    'success': False,
                    'error': 'Original conversion not found'
                }
            
            # Check if already reversed
            if conversion.is_reversed:
                return {
                    'success': False,
                    'error': 'Conversion already reversed'
                }
            
            # Process reversal
            with transaction.atomic():
                # Mark conversion as reversed
                conversion.is_reversed = True
                conversion.reversal_reason = reversal_data.get('reason', 'Unknown')
                conversion.reversal_time = timezone.now()
                conversion.reversal_amount = reversal_data.get('reversal_amount', conversion.revenue)
                conversion.save()
                
                # Update analytics
                self._update_reversal_analytics(conversion, reversal_data)
                
                # Log reversal event
                self._log_reversal_event(conversion, reversal_data)
            
            logger.info(f"Conversion reversal processed: {conversion_id}")
            
            return {
                'success': True,
                'conversion_id': conversion_id,
                'reversal_amount': conversion.reversal_amount,
                'reversal_reason': conversion.reversal_reason
            }
            
        except Exception as e:
            logger.error(f"Error processing reversal: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _validate_postback(self, postback_data: Dict[str, any]) -> Dict[str, any]:
        """Validate postback data structure and required fields."""
        try:
            required_fields = ['user_id', 'offer_id', 'conversion_id']
            
            for field in required_fields:
                if field not in postback_data:
                    return {
                        'valid': False,
                        'error': f'Missing required field: {field}'
                    }
            
            # Validate data types
            if not isinstance(postback_data['user_id'], int):
                return {
                    'valid': False,
                    'error': 'user_id must be an integer'
                }
            
            if not isinstance(postback_data['offer_id'], int):
                return {
                    'valid': False,
                    'error': 'offer_id must be an integer'
                }
            
            if not isinstance(postback_data['conversion_id'], str):
                return {
                    'valid': False,
                    'error': 'conversion_id must be a string'
                }
            
            # Validate revenue if present
            if 'revenue' in postback_data:
                try:
                    revenue = float(postback_data['revenue'])
                    if revenue < 0:
                        return {
                            'valid': False,
                            'error': 'revenue cannot be negative'
                        }
                except (ValueError, TypeError):
                    return {
                        'valid': False,
                        'error': 'revenue must be a number'
                    }
            
            return {'valid': True}
            
        except Exception as e:
            logger.error(f"Error validating postback: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    def _is_duplicate_postback(self, conversion_id: str) -> bool:
        """Check if postback is a duplicate."""
        try:
            cache_key = f"postback_duplicate:{conversion_id}"
            
            if cache.get(cache_key):
                return True
            
            # Also check database
            return UserOfferHistory.objects.filter(
                conversion_id=conversion_id
            ).exists()
            
        except Exception as e:
            logger.error(f"Error checking duplicate postback: {e}")
            return False
    
    def _verify_user(self, user_id: int) -> Optional[User]:
        """Verify user exists and is active."""
        try:
            return User.objects.filter(
                id=user_id,
                is_active=True
            ).first()
        except Exception as e:
            logger.error(f"Error verifying user: {e}")
            return None
    
    def _verify_offer(self, offer_id: int) -> Optional[OfferRoute]:
        """Verify offer exists and is active."""
        try:
            return OfferRoute.objects.filter(
                id=offer_id,
                is_active=True
            ).first()
        except Exception as e:
            logger.error(f"Error verifying offer: {e}")
            return None
    
    def _analyze_postback_fraud(self, postback_data: Dict[str, any], user: User, offer: OfferRoute) -> Dict[str, any]:
        """Analyze postback for fraud indicators."""
        try:
            fraud_analysis = {
                'risk_score': 0,
                'indicators': [],
                'details': {}
            }
            
            # Check user fraud patterns
            user_analysis = self.fraud_service.analyze_user_activity(user.id)
            if user_analysis.get('risk_score', 0) > 50:
                fraud_analysis['risk_score'] += 30
                fraud_analysis['indicators'].append('high_user_risk')
                fraud_analysis['details']['user_risk'] = user_analysis['risk_score']
            
            # Check IP fraud
            ip_address = postback_data.get('ip_address')
            if ip_address:
                ip_analysis = self.fraud_service.detect_ip_fraud(ip_address)
                if ip_analysis.get('risk_score', 0) > 50:
                    fraud_analysis['risk_score'] += 25
                    fraud_analysis['indicators'].append('high_ip_risk')
                    fraud_analysis['details']['ip_risk'] = ip_analysis['risk_score']
            
            # Check device fraud
            device_fingerprint = postback_data.get('device_fingerprint')
            if device_fingerprint:
                device_analysis = self.fraud_service.detect_device_fraud(device_fingerprint)
                if device_analysis.get('risk_score', 0) > 50:
                    fraud_analysis['risk_score'] += 20
                    fraud_analysis['indicators'].append('high_device_risk')
                    fraud_analysis['details']['device_risk'] = device_analysis['risk_score']
            
            # Check conversion fraud
            conversion_analysis = self.fraud_service.detect_conversion_fraud(user.id, offer.id)
            if conversion_analysis.get('risk_score', 0) > 50:
                fraud_analysis['risk_score'] += 25
                fraud_analysis['indicators'].append('high_conversion_risk')
                fraud_analysis['details']['conversion_risk'] = conversion_analysis['risk_score']
            
            # Check for suspicious timing
            if self._is_suspicious_timing(postback_data, user):
                fraud_analysis['risk_score'] += 15
                fraud_analysis['indicators'].append('suspicious_timing')
            
            # Check for unusual revenue
            revenue = postback_data.get('revenue', 0)
            if self._is_unusual_revenue(revenue, offer):
                fraud_analysis['risk_score'] += 10
                fraud_analysis['indicators'].append('unusual_revenue')
            
            return fraud_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing postback fraud: {e}")
            return {'risk_score': 0, 'indicators': [], 'details': {}}
    
    def _create_conversion_record(self, user: User, offer: OfferRoute, postback_data: Dict[str, any], fraud_analysis: Dict[str, any]) -> UserOfferHistory:
        """Create conversion record."""
        try:
            # Get or create user offer history
            history, created = UserOfferHistory.objects.get_or_create(
                user=user,
                offer=offer,
                defaults={
                    'conversion_id': postback_data.get('conversion_id'),
                    'revenue': postback_data.get('revenue', 0),
                    'ip_address': postback_data.get('ip_address'),
                    'user_agent': postback_data.get('user_agent'),
                    'fraud_score': fraud_analysis['risk_score'],
                    'completed_at': timezone.now(),
                    'interaction_type': postback_data.get('event_type', 'conversion')
                }
            )
            
            if not created:
                # Update existing record
                history.conversion_id = postback_data.get('conversion_id')
                history.revenue = postback_data.get('revenue', 0)
                history.ip_address = postback_data.get('ip_address')
                history.user_agent = postback_data.get('user_agent')
                history.fraud_score = fraud_analysis['risk_score']
                history.completed_at = timezone.now()
                history.interaction_type = postback_data.get('event_type', 'conversion')
                history.save()
            
            return history
            
        except Exception as e:
            logger.error(f"Error creating conversion record: {e}")
            raise
    
    def _update_user_history(self, conversion: UserOfferHistory, postback_data: Dict[str, any]):
        """Update user history with conversion data."""
        try:
            # Update user statistics
            user = conversion.user
            
            # Update conversion count
            user.profile.conversion_count += 1
            user.profile.total_revenue += conversion.revenue
            user.profile.last_conversion = conversion.completed_at
            user.profile.save()
            
            # Update offer statistics
            offer = conversion.offer
            offer.conversion_count += 1
            offer.total_revenue += conversion.revenue
            offer.last_conversion = conversion.completed_at
            offer.save()
            
        except Exception as e:
            logger.error(f"Error updating user history: {e}")
    
    def _update_conversion_analytics(self, conversion: UserOfferHistory, postback_data: Dict[str, any]):
        """Update conversion analytics."""
        try:
            # Update daily analytics
            today = timezone.now().date()
            
            # This would update analytics tables
            # Implementation depends on specific analytics schema
            
            logger.debug(f"Updated conversion analytics for user {conversion.user_id}")
            
        except Exception as e:
            logger.error(f"Error updating conversion analytics: {e}")
    
    def _update_user_preferences(self, user: User, offer: OfferRoute, postback_data: Dict[str, any]):
        """Update user preferences based on conversion."""
        try:
            # Get or create user preference vector
            preference_vector, created = UserPreferenceVector.objects.get_or_create(
                user=user,
                defaults={'vector': {}}
            )
            
            # Update preferences based on conversion
            categories = offer.categories.all()
            for category in categories:
                # Increase preference score for converted categories
                current_score = preference_vector.vector.get(category.name, 0)
                preference_vector.vector[category.name] = min(current_score + 1.0, 10.0)
            
            preference_vector.save()
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
    
    def _cache_postback(self, conversion_id: str, postback_data: Dict[str, any]):
        """Cache postback to prevent duplicates."""
        try:
            cache_key = f"postback_duplicate:{conversion_id}"
            cache.set(cache_key, postback_data, self.postback_timeout)
            
        except Exception as e:
            logger.error(f"Error caching postback: {e}")
    
    def _log_conversion_event(self, conversion: UserOfferHistory, postback_data: Dict[str, any]):
        """Log conversion security event."""
        try:
            SecurityEvent.objects.create(
                user=conversion.user,
                event_type='conversion',
                ip_address=conversion.ip_address,
                user_agent=conversion.user_agent,
                request_path='/api/postback',
                details={
                    'conversion_id': conversion.conversion_id,
                    'offer_id': conversion.offer_id,
                    'revenue': conversion.revenue,
                    'fraud_score': conversion.fraud_score
                }
            )
            
        except Exception as e:
            logger.error(f"Error logging conversion event: {e}")
    
    def _calculate_attribution_window(self, conversion: UserOfferHistory, routing_decision: Optional[RoutingDecisionLog]) -> timedelta:
        """Calculate attribution window between click and conversion."""
        try:
            if not routing_decision:
                return timedelta(0)
            
            return conversion.completed_at - routing_decision.created_at
            
        except Exception as e:
            logger.error(f"Error calculating attribution window: {e}")
            return timedelta(0)
    
    def _get_touchpoints(self, user_id: int, offer_id: int) -> List[Dict[str, any]]:
        """Get all touchpoints for user-offer interaction."""
        try:
            # Get all routing decisions for this user-offer pair
            decisions = RoutingDecisionLog.objects.filter(
                user_id=user_id,
                offer_id=offer_id
            ).order_by('created_at')
            
            touchpoints = []
            for decision in decisions:
                touchpoints.append({
                    'timestamp': decision.created_at,
                    'score': decision.score,
                    'rank': decision.rank,
                    'cache_hit': decision.cache_hit,
                    'personalization_applied': decision.personalization_applied
                })
            
            return touchpoints
            
        except Exception as e:
            logger.error(f"Error getting touchpoints: {e}")
            return []
    
    def _get_attribution_model(self, conversion: UserOfferHistory) -> str:
        """Get attribution model used for this conversion."""
        try:
            # This would depend on the routing configuration
            # For now, return a default model
            return 'last_click'
            
        except Exception as e:
            logger.error(f"Error getting attribution model: {e}")
            return 'last_click'
    
    def _is_suspicious_timing(self, postback_data: Dict[str, any], user: User) -> bool:
        """Check if conversion timing is suspicious."""
        try:
            # Get user's last click
            last_click = RoutingDecisionLog.objects.filter(
                user_id=user.id
            ).order_by('-created_at').first()
            
            if not last_click:
                return False
            
            # Check if conversion happened too quickly
            conversion_time = postback_data.get('conversion_time', timezone.now())
            time_diff = conversion_time - last_click.created_at
            
            # Suspicious if conversion happens within 1 second
            return time_diff.total_seconds() < 1.0
            
        except Exception as e:
            logger.error(f"Error checking suspicious timing: {e}")
            return False
    
    def _is_unusual_revenue(self, revenue: float, offer: OfferRoute) -> bool:
        """Check if revenue is unusual for this offer."""
        try:
            # Get average revenue for this offer
            avg_revenue = UserOfferHistory.objects.filter(
                offer=offer,
                completed_at__isnull=False
            ).aggregate(
                avg_revenue=models.Avg('revenue')
            )['avg_revenue'] or 0
            
            # Unusual if revenue is more than 10x average
            return revenue > avg_revenue * 10
            
        except Exception as e:
            logger.error(f"Error checking unusual revenue: {e}")
            return False
    
    def _validate_reversal(self, reversal_data: Dict[str, any]) -> Dict[str, any]:
        """Validate reversal data."""
        try:
            required_fields = ['conversion_id', 'reason']
            
            for field in required_fields:
                if field not in reversal_data:
                    return {
                        'valid': False,
                        'error': f'Missing required field: {field}'
                    }
            
            return {'valid': True}
            
        except Exception as e:
            logger.error(f"Error validating reversal: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    def _update_reversal_analytics(self, conversion: UserOfferHistory, reversal_data: Dict[str, any]):
        """Update analytics for reversal."""
        try:
            # Update user statistics
            user = conversion.user
            user.profile.conversion_count = max(0, user.profile.conversion_count - 1)
            user.profile.total_revenue = max(0, user.profile.total_revenue - conversion.reversal_amount)
            user.profile.save()
            
            # Update offer statistics
            offer = conversion.offer
            offer.conversion_count = max(0, offer.conversion_count - 1)
            offer.total_revenue = max(0, offer.total_revenue - conversion.reversal_amount)
            offer.save()
            
        except Exception as e:
            logger.error(f"Error updating reversal analytics: {e}")
    
    def _log_reversal_event(self, conversion: UserOfferHistory, reversal_data: Dict[str, any]):
        """Log reversal security event."""
        try:
            SecurityEvent.objects.create(
                user=conversion.user,
                event_type='conversion_reversal',
                ip_address=conversion.ip_address,
                user_agent=conversion.user_agent,
                request_path='/api/reversal',
                details={
                    'conversion_id': conversion.conversion_id,
                    'reversal_reason': conversion.reversal_reason,
                    'reversal_amount': conversion.reversal_amount
                }
            )
            
        except Exception as e:
            logger.error(f"Error logging reversal event: {e}")


# Global postback service instance
postback_service = PostbackService()
