"""
Conversion Tracking Service

Service for managing conversion tracking,
including recording, validation, and attribution.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.tracking import ConversionEvent
from ...models.offer import AdvertiserOffer
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class ConversionTrackingService:
    """
    Service for managing conversion tracking.
    
    Handles conversion recording, validation,
    and attribution logic.
    """
    
    def __init__(self):
        self.logger = logger
    
    def record_conversion(self, offer: AdvertiserOffer, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record a conversion event.
        
        Args:
            offer: Offer instance
            conversion_data: Conversion event data
            
        Returns:
            Dict[str, Any]: Recording results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Validate conversion data
                validation_result = self._validate_conversion_data(offer, conversion_data)
                
                if not validation_result['is_valid']:
                    return {
                        'success': False,
                        'errors': validation_result['errors'],
                        'conversion_id': None,
                    }
                
                # Check for duplicates
                if self._is_duplicate_conversion(offer, conversion_data):
                    return {
                        'success': False,
                        'errors': ['Duplicate conversion detected'],
                        'conversion_id': None,
                    }
                
                # Create conversion event
                conversion_event = ConversionEvent.objects.create(
                    offer=offer,
                    event_name=conversion_data.get('event_name', 'conversion'),
                    event_type=conversion_data.get('event_type', 'custom'),
                    payout_amount=conversion_data.get('payout_amount', offer.payout_amount),
                    payout_type=conversion_data.get('payout_type', 'fixed'),
                    currency=conversion_data.get('currency', offer.currency),
                    deduplication_window_hours=conversion_data.get('deduplication_window_hours', offer.deduplication_window),
                    deduplication_type=conversion_data.get('deduplication_type', 'ip'),
                    validation_rules=conversion_data.get('validation_rules', {}),
                    required_params=conversion_data.get('required_params', []),
                    optional_params=conversion_data.get('optional_params', []),
                )
                
                # Store conversion metadata
                metadata = {
                    'recorded_at': timezone.now().isoformat(),
                    'source_ip': conversion_data.get('ip'),
                    'user_agent': conversion_data.get('user_agent'),
                    'referer': conversion_data.get('referer'),
                    'conversion_data': conversion_data,
                }
                conversion_event.metadata = metadata
                conversion_event.save()
                
                # Send notification for high-value conversions
                if conversion_data.get('payout_amount', 0) > 50:
                    self._send_high_value_conversion_notification(offer, conversion_event)
                
                self.logger.info(f"Recorded conversion for offer: {offer.title}")
                
                return {
                    'success': True,
                    'conversion_id': conversion_event.id,
                    'event_name': conversion_event.event_name,
                    'payout_amount': float(conversion_event.payout_amount),
                    'recorded_at': conversion_event.created_at.isoformat(),
                }
                
        except Exception as e:
            self.logger.error(f"Error recording conversion: {e}")
            raise ValidationError(f"Failed to record conversion: {str(e)}")
    
    def validate_conversion(self, conversion_id: int, validation_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate a conversion event.
        
        Args:
            conversion_id: Conversion event ID
            validation_data: Additional validation data
            
        Returns:
            Dict[str, Any]: Validation results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get conversion event
            conversion = ConversionEvent.objects.get(id=conversion_id)
            
            # Perform validation checks
            validation_results = {
                'conversion_id': conversion_id,
                'validated_at': timezone.now().isoformat(),
                'checks': {},
                'overall_status': 'valid',
                'issues': [],
                'warnings': [],
            }
            
            # Check IP validity
            ip_check = self._validate_conversion_ip(conversion, validation_data)
            validation_results['checks']['ip'] = ip_check
            
            # Check timing validity
            timing_check = self._validate_conversion_timing(conversion, validation_data)
            validation_results['checks']['timing'] = timing_check
            
            # Check device validity
            device_check = self._validate_conversion_device(conversion, validation_data)
            validation_results['checks']['device'] = device_check
            
            # Check geographic validity
            geo_check = self._validate_conversion_geography(conversion, validation_data)
            validation_results['checks']['geography'] = geo_check
            
            # Check behavioral validity
            behavior_check = self._validate_conversion_behavior(conversion, validation_data)
            validation_results['checks']['behavior'] = behavior_check
            
            # Determine overall status
            issues = []
            warnings = []
            
            for check_name, check_result in validation_results['checks'].items():
                if check_result.get('status') == 'invalid':
                    issues.extend(check_result.get('issues', []))
                    validation_results['overall_status'] = 'invalid'
                elif check_result.get('warnings'):
                    warnings.extend(check_result.get('warnings', []))
            
            validation_results['issues'] = issues
            validation_results['warnings'] = warnings
            
            # Store validation results
            metadata = conversion.metadata or {}
            metadata['validation'] = validation_results
            conversion.metadata = metadata
            conversion.save()
            
            return validation_results
            
        except ConversionEvent.DoesNotExist:
            raise ValidationError("Conversion not found")
        except Exception as e:
            self.logger.error(f"Error validating conversion: {e}")
            raise ValidationError(f"Failed to validate conversion: {str(e)}")
    
    def get_conversion_attribution(self, conversion_id: int) -> Dict[str, Any]:
        """
        Get conversion attribution information.
        
        Args:
            conversion_id: Conversion event ID
            
        Returns:
            Dict[str, Any]: Attribution results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get conversion event
            conversion = ConversionEvent.objects.select_related('offer', 'offer__advertiser').get(id=conversion_id)
            
            # This would implement actual attribution logic
            attribution_results = {
                'conversion_id': conversion_id,
                'offer_id': conversion.offer.id,
                'offer_title': conversion.offer.title,
                'advertiser_id': conversion.offer.advertiser.id,
                'advertiser_name': conversion.offer.advertiser.company_name,
                'attribution_model': 'last_click',  # Would be configurable
                'attribution_window': 30,  # Days
                'touchpoints': [],  # Would include click/impression data
                'attribution_credit': {
                    'direct': 1.0,
                    'indirect': 0.0,
                },
                'attribution_confidence': 0.95,
                'path_length': 1,
                'time_to_conversion': 0,  # Hours
                'device_crossing': False,
                'attribution_date': timezone.now().isoformat(),
            }
            
            return attribution_results
            
        except ConversionEvent.DoesNotExist:
            raise ValidationError("Conversion not found")
        except Exception as e:
            self.logger.error(f"Error getting conversion attribution: {e}")
            raise ValidationError(f"Failed to get attribution: {str(e)}")
    
    def get_conversion_analytics(self, offer: AdvertiserOffer = None, days: int = 30) -> Dict[str, Any]:
        """
        Get conversion analytics.
        
        Args:
            offer: Optional offer filter
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Conversion analytics
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            from django.db.models import Sum, Count, Avg, Q
            
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            # Get conversion events
            queryset = ConversionEvent.objects.filter(created_at__gte=start_date)
            
            if offer:
                queryset = queryset.filter(offer=offer)
            
            # Aggregate metrics
            analytics = queryset.aggregate(
                total_conversions=Count('id'),
                total_payout=Sum('payout_amount'),
                avg_payout=Avg('payout_amount'),
                unique_offers=Count('offer', distinct=True),
                unique_events=Count('event_name', distinct=True),
            )
            
            # Fill missing values
            for key, value in analytics.items():
                if value is None:
                    analytics[key] = 0
            
            # Get daily breakdown
            daily_data = {}
            for i in range(days):
                date = (timezone.now() - timezone.timedelta(days=i)).date()
                daily_conversions = queryset.filter(created_at__date=date).count()
                daily_payout = queryset.filter(created_at__date=date).aggregate(
                    total=Sum('payout_amount')
                )['total'] or 0
                
                daily_data[date.isoformat()] = {
                    'conversions': daily_conversions,
                    'payout': float(daily_payout),
                }
            
            # Get event type breakdown
            event_types = queryset.values('event_type').annotate(
                count=Count('id'),
                total_payout=Sum('payout_amount')
            ).order_by('-count')
            
            return {
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': timezone.now().date().isoformat(),
                    'days': days,
                },
                'summary': {
                    'total_conversions': analytics['total_conversions'],
                    'total_payout': float(analytics['total_payout']),
                    'avg_payout': float(analytics['avg_payout']),
                    'unique_offers': analytics['unique_offers'],
                    'unique_events': analytics['unique_events'],
                },
                'daily_breakdown': daily_data,
                'event_type_breakdown': [
                    {
                        'event_type': item['event_type'],
                        'count': item['count'],
                        'total_payout': float(item['total_payout']),
                    }
                    for item in event_types
                ],
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting conversion analytics: {e}")
            raise ValidationError(f"Failed to get analytics: {str(e)}")
    
    def get_conversion_fraud_score(self, conversion_id: int) -> Dict[str, Any]:
        """
        Get fraud score for conversion.
        
        Args:
            conversion_id: Conversion event ID
            
        Returns:
            Dict[str, Any]: Fraud scoring results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get conversion event
            conversion = ConversionEvent.objects.get(id=conversion_id)
            
            # This would implement actual fraud scoring
            fraud_score = self._calculate_fraud_score(conversion)
            
            return {
                'conversion_id': conversion_id,
                'fraud_score': fraud_score,
                'risk_level': self._get_risk_level(fraud_score),
                'risk_factors': self._get_risk_factors(conversion),
                'recommendation': self._get_fraud_recommendation(fraud_score),
                'scored_at': timezone.now().isoformat(),
            }
            
        except ConversionEvent.DoesNotExist:
            raise ValidationError("Conversion not found")
        except Exception as e:
            self.logger.error(f"Error calculating fraud score: {e}")
            raise ValidationError(f"Failed to calculate fraud score: {str(e)}")
    
    def _validate_conversion_data(self, offer: AdvertiserOffer, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate conversion data."""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
        }
        
        # Check required fields
        required_fields = ['ip', 'user_agent']
        for field in required_fields:
            if field not in conversion_data or not conversion_data[field]:
                validation_result['is_valid'] = False
                validation_result['errors'].append(f"Missing required field: {field}")
        
        # Check IP format
        ip = conversion_data.get('ip')
        if ip and not self._is_valid_ip(ip):
            validation_result['is_valid'] = False
            validation_result['errors'].append("Invalid IP address format")
        
        # Check payout amount
        payout_amount = conversion_data.get('payout_amount')
        if payout_amount and payout_amount <= 0:
            validation_result['is_valid'] = False
            validation_result['errors'].append("Payout amount must be positive")
        
        return validation_result
    
    def _is_duplicate_conversion(self, offer: AdvertiserOffer, conversion_data: Dict[str, Any]) -> bool:
        """Check if conversion is duplicate."""
        # This would implement actual duplicate checking logic
        # For now, return False
        return False
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format."""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def _validate_conversion_ip(self, conversion: ConversionEvent, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate conversion IP."""
        # This would implement IP validation logic
        return {
            'status': 'valid',
            'issues': [],
            'warnings': [],
        }
    
    def _validate_conversion_timing(self, conversion: ConversionEvent, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate conversion timing."""
        # This would implement timing validation logic
        return {
            'status': 'valid',
            'issues': [],
            'warnings': [],
        }
    
    def _validate_conversion_device(self, conversion: ConversionEvent, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate conversion device."""
        # This would implement device validation logic
        return {
            'status': 'valid',
            'issues': [],
            'warnings': [],
        }
    
    def _validate_conversion_geography(self, conversion: ConversionEvent, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate conversion geography."""
        # This would implement geography validation logic
        return {
            'status': 'valid',
            'issues': [],
            'warnings': [],
        }
    
    def _validate_conversion_behavior(self, conversion: ConversionEvent, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate conversion behavior."""
        # This would implement behavioral validation logic
        return {
            'status': 'valid',
            'issues': [],
            'warnings': [],
        }
    
    def _calculate_fraud_score(self, conversion: ConversionEvent) -> float:
        """Calculate fraud score for conversion."""
        # This would implement actual fraud scoring algorithm
        # For now, return a low score
        return 15.5
    
    def _get_risk_level(self, fraud_score: float) -> str:
        """Get risk level based on fraud score."""
        if fraud_score < 30:
            return 'low'
        elif fraud_score < 60:
            return 'medium'
        elif fraud_score < 80:
            return 'high'
        else:
            return 'critical'
    
    def _get_risk_factors(self, conversion: ConversionEvent) -> List[str]:
        """Get risk factors for conversion."""
        # This would implement risk factor analysis
        return []
    
    def _get_fraud_recommendation(self, fraud_score: float) -> str:
        """Get fraud recommendation based on score."""
        if fraud_score < 30:
            return 'accept'
        elif fraud_score < 60:
            return 'review'
        elif fraud_score < 80:
            return 'investigate'
        else:
            return 'reject'
    
    def _send_high_value_conversion_notification(self, offer: AdvertiserOffer, conversion: ConversionEvent):
        """Send notification for high-value conversion."""
        AdvertiserNotification.objects.create(
            advertiser=offer.advertiser,
            type='offer_approved',
            title=_('High Value Conversion'),
            message=_('A high-value conversion (${amount:.2f}) has been recorded for your offer "{offer_title}".').format(
                amount=float(conversion.payout_amount),
                offer_title=offer.title
            ),
            priority='high',
            action_url=f'/advertiser/offers/{offer.id}/conversions/',
            action_text=_('View Conversions')
        )
