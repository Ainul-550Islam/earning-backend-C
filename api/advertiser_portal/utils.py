"""
Utility Functions for Advertiser Portal

This module contains utility functions and helper classes
that provide common functionality across the application.
"""

from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import UUID
import json
import hashlib
import secrets
import base64
import re
import math
from urllib.parse import urlparse, parse_qs
import logging

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q, F, Sum, Count, Avg
from django.http import HttpRequest
from django.contrib.gis.geoip2 import GeoIP2
# from django.contrib.gis.geoip2.resources import GeoIP2Exception
from geoip2.errors import GeoIP2Error as GeoIP2Exception

logger = logging.getLogger(__name__)


class AdvertiserUtils:
    """Utility functions for advertiser operations."""
    
    @staticmethod
    def generate_unique_identifier(prefix: str = "adv") -> str:
        """
        Generate a unique identifier with prefix.
        
        Args:
            prefix: Prefix for the identifier
            
        Returns:
            Unique identifier string
        """
        unique_id = secrets.token_urlsafe(16)
        return f"{prefix}_{unique_id}"
    
    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """
        Hash sensitive data for storage.
        
        Args:
            data: Data to hash
            
        Returns:
            Hashed string
        """
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def mask_email(email: str) -> str:
        """
        Mask email address for privacy.
        
        Args:
            email: Email address to mask
            
        Returns:
            Masked email
        """
        if '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) <= 2:
            masked_local = '*' * len(local)
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """
        Mask phone number for privacy.
        
        Args:
            phone: Phone number to mask
            
        Returns:
            Masked phone number
        """
        # Remove non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) <= 4:
            return '*' * len(phone)
        
        # Show last 4 digits
        return '*' * (len(phone) - 4) + digits[-4:]
    
    @staticmethod
    def calculate_advertiser_score(advertiser) -> float:
        """
        Calculate advertiser quality score.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Quality score (0-100)
        """
        score = 0.0
        
        # Base score for verification
        if advertiser.is_verified:
            score += 30
        
        # Score for account age
        days_active = (timezone.now() - advertiser.created_at).days
        score += min(days_active / 365 * 20, 20)  # Max 20 points for age
        
        # Score for campaign performance
        campaigns = Campaign.objects.filter(advertiser=advertiser, is_deleted=False)
        if campaigns.exists():
            avg_ctr = campaigns.aggregate(avg_ctr=Avg('ctr'))['avg_ctr'] or 0
            score += min(float(avg_ctr) * 10, 30)  # Max 30 points for CTR
        
        # Score for spending consistency
        total_spend = campaigns.aggregate(total=Sum('current_spend'))['total'] or 0
        if total_spend > 0:
            score += min(float(total_spend) / 10000 * 20, 20)  # Max 20 points for spend
        
        return min(score, 100.0)
    
    @staticmethod
    def get_industry_benchmarks(industry: str) -> Dict[str, float]:
        """
        Get industry benchmark metrics.
        
        Args:
            industry: Industry name
            
        Returns:
            Dictionary of benchmark metrics
        """
        # Default benchmarks - would typically come from external data
        benchmarks = {
            'technology': {'avg_ctr': 2.5, 'avg_cpc': 1.2, 'avg_conversion_rate': 3.2},
            'retail': {'avg_ctr': 1.8, 'avg_cpc': 0.8, 'avg_conversion_rate': 2.5},
            'finance': {'avg_ctr': 1.2, 'avg_cpc': 2.5, 'avg_conversion_rate': 4.1},
            'healthcare': {'avg_ctr': 1.5, 'avg_cpc': 1.8, 'avg_conversion_rate': 3.8},
            'education': {'avg_ctr': 2.1, 'avg_cpc': 1.0, 'avg_conversion_rate': 4.5},
        }
        
        return benchmarks.get(industry.lower(), {
            'avg_ctr': 1.5,
            'avg_cpc': 1.0,
            'avg_conversion_rate': 2.5
        })


class CampaignUtils:
    """Utility functions for campaign operations."""
    
    @staticmethod
    def calculate_optimal_daily_budget(total_budget: Decimal, campaign_duration_days: int) -> Decimal:
        """
        Calculate optimal daily budget based on total budget and duration.
        
        Args:
            total_budget: Total campaign budget
            campaign_duration_days: Campaign duration in days
            
        Returns:
            Optimal daily budget
        """
        if campaign_duration_days <= 0:
            return total_budget
        
        # Add 10% buffer for unexpected variations
        buffer_multiplier = Decimal('1.1')
        optimal_budget = (total_budget / campaign_duration_days) * buffer_multiplier
        
        return optimal_budget
    
    @staticmethod
    def predict_campaign_performance(campaign) -> Dict[str, Any]:
        """
        Predict campaign performance based on historical data.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            Performance prediction dictionary
        """
        # Get historical data from similar campaigns
        similar_campaigns = Campaign.objects.filter(
            objective=campaign.objective,
            industry=campaign.advertiser.industry,
            is_deleted=False
        ).exclude(id=campaign.id)
        
        if not similar_campaigns.exists():
            return {
                'predicted_ctr': 1.5,
                'predicted_cpc': Decimal('1.0'),
                'predicted_conversion_rate': 2.5,
                'confidence': 'low'
            }
        
        # Calculate averages from similar campaigns
        averages = similar_campaigns.aggregate(
            avg_ctr=Avg('ctr'),
            avg_cpc=Avg('cpc'),
            avg_conversion_rate=Avg('conversion_rate')
        )
        
        return {
            'predicted_ctr': float(averages['avg_ctr'] or 1.5),
            'predicted_cpc': averages['avg_cpc'] or Decimal('1.0'),
            'predicted_conversion_rate': float(averages['avg_conversion_rate'] or 2.5),
            'confidence': 'medium' if similar_campaigns.count() >= 5 else 'low'
        }
    
    @staticmethod
    def get_campaign_insights(campaign) -> List[Dict[str, Any]]:
        """
        Get insights and recommendations for campaign.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            List of insights
        """
        insights = []
        
        # Budget utilization insight
        utilization = campaign.budget_utilization
        if utilization > 90:
            insights.append({
                'type': 'warning',
                'title': 'High Budget Utilization',
                'message': f'Campaign has used {utilization:.1f}% of budget. Consider increasing budget.',
                'action': 'increase_budget'
            })
        elif utilization < 30 and campaign.status == 'active':
            insights.append({
                'type': 'info',
                'title': 'Low Budget Utilization',
                'message': f'Campaign has used only {utilization:.1f}% of budget. Check targeting or creative performance.',
                'action': 'review_performance'
            })
        
        # CTR insight
        if campaign.ctr < 1.0:
            insights.append({
                'type': 'warning',
                'title': 'Low Click-Through Rate',
                'message': f'CTR of {campaign.ctr:.2f}% is below average. Consider improving creatives or targeting.',
                'action': 'optimize_creatives'
            })
        
        # Conversion rate insight
        if campaign.conversion_rate < 2.0:
            insights.append({
                'type': 'warning',
                'title': 'Low Conversion Rate',
                'message': f'Conversion rate of {campaign.conversion_rate:.2f}% needs improvement. Review landing page and offer.',
                'action': 'optimize_landing_page'
            })
        
        return insights
    
    @staticmethod
    def calculate_campaign_roi(campaign) -> float:
        """
        Calculate campaign return on investment.
        
        Args:
            campaign: Campaign instance
            
        Returns:
            ROI percentage
        """
        if campaign.current_spend == 0:
            return 0.0
        
        # Assuming revenue data is tracked separately
        # For now, using a simple estimate based on conversions
        estimated_revenue = campaign.conversions * 50  # $50 per conversion estimate
        roi = ((estimated_revenue - float(campaign.current_spend)) / float(campaign.current_spend)) * 100
        
        return roi


class CreativeUtils:
    """Utility functions for creative operations."""
    
    @staticmethod
    def validate_creative_file(file_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate uploaded creative file.
        
        Args:
            file_data: File information dictionary
            
        Returns:
            Validation result
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        # File size validation
        max_size = getattr(settings, 'MAX_CREATIVE_FILE_SIZE', 5 * 1024 * 1024)  # 5MB
        if file_data.get('size', 0) > max_size:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f'File size exceeds maximum allowed size of {max_size / (1024*1024):.1f}MB')
        
        # MIME type validation
        allowed_types = getattr(settings, 'ALLOWED_CREATIVE_TYPES', [
            'image/jpeg', 'image/png', 'image/gif',
            'video/mp4', 'video/webm',
            'text/html', 'application/javascript'
        ])
        
        mime_type = file_data.get('mime_type')
        if mime_type not in allowed_types:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f'File type {mime_type} is not allowed')
        
        # Dimension validation for images
        if mime_type and mime_type.startswith('image/'):
            width = file_data.get('width')
            height = file_data.get('height')
            
            if not width or not height:
                validation_result['warnings'].append('Image dimensions could not be determined')
            elif width < 120 or height < 90:
                validation_result['warnings'].append('Image dimensions are smaller than recommended minimum (120x90)')
        
        return validation_result
    
    @staticmethod
    def optimize_creative_for_delivery(creative_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize creative data for delivery.
        
        Args:
            creative_data: Original creative data
            
        Returns:
            Optimized creative data
        """
        optimized = creative_data.copy()
        
        # Compress images if needed
        if creative_data.get('mime_type', '').startswith('image/'):
            optimized = CreativeUtils._compress_image(optimized)
        
        # Optimize HTML5 creatives
        if creative_data.get('type') == 'html5':
            optimized = CreativeUtils._optimize_html5_creative(optimized)
        
        # Generate thumbnails for videos
        if creative_data.get('mime_type', '').startswith('video/'):
            optimized = CreativeUtils._generate_video_thumbnail(optimized)
        
        return optimized
    
    @staticmethod
    def _compress_image(image_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compress image data."""
        # Placeholder for image compression logic
        # Would typically use PIL or similar library
        return image_data
    
    @staticmethod
    def _optimize_html5_creative(creative_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize HTML5 creative."""
        # Placeholder for HTML5 optimization logic
        # Would typically minify HTML, CSS, JS
        return creative_data
    
    @staticmethod
    def _generate_video_thumbnail(video_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate video thumbnail."""
        # Placeholder for video thumbnail generation
        # Would typically use ffmpeg or similar
        return video_data
    
    @staticmethod
    def calculate_quality_score(creative) -> float:
        """
        Calculate creative quality score.
        
        Args:
            creative: Creative instance
            
        Returns:
            Quality score (0-100)
        """
        score = 0.0
        
        # Base score for approval
        if creative.is_approved:
            score += 30
        
        # Score based on performance
        if creative.impressions > 0:
            ctr_score = min(float(creative.ctr) * 10, 40)
            score += ctr_score
        
        # Score for engagement
        if creative.clicks > 0:
            engagement_score = min((float(creative.conversions) / float(creative.clicks)) * 100, 30)
            score += engagement_score
        
        return min(score, 100.0)


class TargetingUtils:
    """Utility functions for targeting operations."""
    
    @staticmethod
    def get_location_from_ip(ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Get location information from IP address.
        
        Args:
            ip_address: IP address to lookup
            
        Returns:
            Location information dictionary
        """
        try:
            g = GeoIP2()
            location = g.city(ip_address)
            
            return {
                'country_code': location['country_code'],
                'country_name': location['country_name'],
                'region': location['region'],
                'city': location['city'],
                'postal_code': location['postal_code'],
                'latitude': location['latitude'],
                'longitude': location['longitude']
            }
        except (GeoIP2Exception, Exception):
            return None
    
    @staticmethod
    def calculate_audience_size(targeting) -> int:
        """
        Calculate estimated audience size for targeting configuration.
        
        Args:
            targeting: Targeting instance
            
        Returns:
            Estimated audience size
        """
        # This is a simplified calculation
        # In practice, would use actual audience data from data providers
        
        base_audience = 1000000  # Base audience size
        
        # Apply geo targeting filters
        geo_multiplier = 1.0
        if targeting.geo_targeting.get('countries'):
            geo_multiplier = len(targeting.geo_targeting['countries']) * 0.3
        
        # Apply device targeting filters
        device_multiplier = 1.0
        if targeting.device_targeting.get('device_types'):
            device_multiplier = len(targeting.device_targeting['device_types']) * 0.4
        
        # Apply demographic filters
        demo_multiplier = 1.0
        if targeting.age_min or targeting.age_max:
            demo_multiplier = 0.6  # Age targeting typically reduces audience
        
        # Apply interest targeting
        interest_multiplier = 1.0
        if targeting.interests:
            interest_multiplier = max(0.1, 1.0 - (len(targeting.interests) * 0.05))
        
        estimated_size = int(base_audience * geo_multiplier * device_multiplier * 
                           demo_multiplier * interest_multiplier)
        
        return max(1000, estimated_size)  # Minimum audience size
    
    @staticmethod
    def expand_targeting_suggestions(targeting) -> List[Dict[str, Any]]:
        """
        Get targeting expansion suggestions.
        
        Args:
            targeting: Targeting instance
            
        Returns:
            List of targeting suggestions
        """
        suggestions = []
        
        # Geo expansion suggestions
        if targeting.geo_targeting.get('countries'):
            current_countries = set(targeting.geo_targeting['countries'])
            similar_countries = TargetingUtils._get_similar_countries(current_countries)
            
            if similar_countries:
                suggestions.append({
                    'type': 'geo_expansion',
                    'title': 'Expand Geographic Targeting',
                    'description': f'Consider targeting similar countries: {", ".join(similar_countries[:3])}',
                    'suggested_changes': {
                        'geo_targeting': {
                            'countries': list(current_countries.union(set(similar_countries[:3])))
                        }
                    }
                })
        
        # Device expansion suggestions
        if targeting.device_targeting.get('device_types'):
            current_devices = set(targeting.device_targeting['device_types'])
            all_devices = {choice[0] for choice in DeviceTypeEnum}
            missing_devices = all_devices - current_devices
            
            if missing_devices:
                suggestions.append({
                    'type': 'device_expansion',
                    'title': 'Expand Device Targeting',
                    'description': f'Consider adding devices: {", ".join(missing_devices)}',
                    'suggested_changes': {
                        'device_targeting': {
                            'device_types': list(current_devices.union(missing_devices))
                        }
                    }
                })
        
        return suggestions
    
    @staticmethod
    def _get_similar_countries(countries: set) -> List[str]:
        """Get similar countries based on geography/economy."""
        # Simplified mapping - in practice would use more sophisticated logic
        similarity_map = {
            'US': ['CA', 'MX', 'GB'],
            'GB': ['US', 'CA', 'AU'],
            'DE': ['AT', 'CH', 'FR'],
            'FR': ['DE', 'ES', 'IT'],
            'JP': ['KR', 'TW', 'SG'],
            'AU': ['NZ', 'SG', 'JP']
        }
        
        similar = set()
        for country in countries:
            similar.update(similarity_map.get(country, []))
        
        return list(similar - countries)


class AnalyticsUtils:
    """Utility functions for analytics operations."""
    
    @staticmethod
    def calculate_statistical_significance(sample_size: int, conversion_count: int, 
                                         baseline_rate: float = 0.02) -> Dict[str, Any]:
        """
        Calculate statistical significance for A/B tests.
        
        Args:
            sample_size: Sample size
            conversion_count: Number of conversions
            baseline_rate: Baseline conversion rate
            
        Returns:
            Statistical significance results
        """
        if sample_size == 0:
            return {'is_significant': False, 'confidence': 0.0, 'p_value': 1.0}
        
        observed_rate = conversion_count / sample_size
        
        # Simplified z-test calculation
        standard_error = math.sqrt((baseline_rate * (1 - baseline_rate)) / sample_size)
        if standard_error == 0:
            return {'is_significant': False, 'confidence': 0.0, 'p_value': 1.0}
        
        z_score = (observed_rate - baseline_rate) / standard_error
        
        # Simplified p-value calculation
        p_value = 2 * (1 - AnalyticsUtils._normal_cdf(abs(z_score)))
        confidence = (1 - p_value) * 100
        
        return {
            'is_significant': p_value < 0.05,
            'confidence': min(confidence, 99.9),
            'p_value': p_value,
            'observed_rate': observed_rate,
            'baseline_rate': baseline_rate,
            'lift': ((observed_rate - baseline_rate) / baseline_rate) * 100 if baseline_rate > 0 else 0
        }
    
    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Calculate normal cumulative distribution function."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    @staticmethod
    def detect_anomalies(data_points: List[float], threshold: float = 2.0) -> List[Dict[str, Any]]:
        """
        Detect anomalies in time series data using z-score method.
        
        Args:
            data_points: List of data points
            threshold: Z-score threshold for anomaly detection
            
        Returns:
            List of anomalies
        """
        if len(data_points) < 3:
            return []
        
        mean = sum(data_points) / len(data_points)
        variance = sum((x - mean) ** 2 for x in data_points) / len(data_points)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return []
        
        anomalies = []
        for i, value in enumerate(data_points):
            z_score = abs(value - mean) / std_dev
            if z_score > threshold:
                anomalies.append({
                    'index': i,
                    'value': value,
                    'z_score': z_score,
                    'deviation': abs(value - mean)
                })
        
        return anomalies
    
    @staticmethod
    def calculate_moving_average(data_points: List[float], window_size: int = 7) -> List[float]:
        """
        Calculate moving average for data points.
        
        Args:
            data_points: List of data points
            window_size: Window size for moving average
            
        Returns:
            List of moving averages
        """
        if len(data_points) < window_size:
            return data_points
        
        moving_averages = []
        for i in range(len(data_points) - window_size + 1):
            window = data_points[i:i + window_size]
            moving_averages.append(sum(window) / window_size)
        
        return moving_averages
    
    @staticmethod
    def forecast_trend(data_points: List[float], periods: int = 7) -> List[float]:
        """
        Forecast trend using simple linear regression.
        
        Args:
            data_points: Historical data points
            periods: Number of periods to forecast
            
        Returns:
            Forecasted values
        """
        if len(data_points) < 2:
            return [data_points[-1]] * periods if data_points else [0] * periods
        
        # Simple linear regression
        n = len(data_points)
        x_values = list(range(n))
        
        sum_x = sum(x_values)
        sum_y = sum(data_points)
        sum_xy = sum(x * y for x, y in zip(x_values, data_points))
        sum_x2 = sum(x * x for x in x_values)
        
        # Calculate slope and intercept
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        intercept = (sum_y - slope * sum_x) / n
        
        # Forecast
        forecasts = []
        for i in range(periods):
            x = n + i
            forecast = slope * x + intercept
            forecasts.append(max(0, forecast))  # Ensure non-negative
        
        return forecasts


class BillingUtils:
    """Utility functions for billing operations."""
    
    @staticmethod
    def calculate_tax(amount: Decimal, tax_rate: Decimal, country: str) -> Dict[str, Any]:
        """
        Calculate tax based on country and amount.
        
        Args:
            amount: Amount to calculate tax on
            tax_rate: Tax rate as decimal (e.g., 0.20 for 20%)
            country: Country code for tax rules
            
        Returns:
            Tax calculation result
        """
        tax_amount = amount * tax_rate
        total_amount = amount + tax_amount
        
        # Apply country-specific tax rules
        tax_info = {
            'country': country,
            'tax_rate': float(tax_rate * 100),
            'tax_amount': float(tax_amount),
            'total_amount': float(total_amount),
            'tax_type': 'VAT' if country in ['GB', 'DE', 'FR'] else 'Sales Tax'
        }
        
        return tax_info
    
    @staticmethod
    def generate_invoice_number(advertiser_id: UUID, date: date) -> str:
        """
        Generate unique invoice number.
        
        Args:
            advertiser_id: Advertiser UUID
            date: Invoice date
            
        Returns:
            Unique invoice number
        """
        advertiser_prefix = str(advertiser_id)[:8].upper()
        date_prefix = date.strftime('%Y%m')
        sequence = BillingUtils._get_next_invoice_sequence(advertiser_id, date)
        
        return f"INV-{advertiser_prefix}-{date_prefix}-{sequence:04d}"
    
    @staticmethod
    def _get_next_invoice_sequence(advertiser_id: UUID, date: date) -> int:
        """Get next invoice sequence for advertiser and month."""
        from .models import Invoice
        
        month_start = date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        count = Invoice.objects.filter(
            advertiser_id=advertiser_id,
            issue_date__gte=month_start,
            issue_date__lte=month_end
        ).count()
        
        return count + 1
    
    @staticmethod
    def calculate_late_fees(invoice_amount: Decimal, days_overdue: int, 
                           late_fee_rate: Decimal = Decimal('0.02')) -> Decimal:
        """
        Calculate late fees for overdue invoice.
        
        Args:
            invoice_amount: Original invoice amount
            days_overdue: Number of days overdue
            late_fee_rate: Late fee rate per day
            
        Returns:
            Late fee amount
        """
        if days_overdue <= 0:
            return Decimal('0')
        
        # Calculate compound interest
        late_fee = invoice_amount * ((1 + late_fee_rate) ** days_overdue - 1)
        return late_fee
    
    @staticmethod
    def detect_payment_fraud(payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect potential payment fraud.
        
        Args:
            payment_data: Payment transaction data
            
        Returns:
            Fraud detection result
        """
        risk_score = 0
        risk_factors = []
        
        # Check for high amount
        amount = payment_data.get('amount', 0)
        if amount > 10000:
            risk_score += 20
            risk_factors.append('High transaction amount')
        
        # Check for unusual timing
        payment_time = payment_data.get('created_at')
        if payment_time:
            hour = payment_time.hour
            if hour < 6 or hour > 22:
                risk_score += 15
                risk_factors.append('Unusual payment time')
        
        # Check for rapid successive payments
        advertiser_id = payment_data.get('advertiser_id')
        if advertiser_id:
            recent_payments = PaymentTransaction.objects.filter(
                advertiser_id=advertiser_id,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            if recent_payments > 3:
                risk_score += 25
                risk_factors.append('Rapid successive payments')
        
        # Determine risk level
        if risk_score >= 50:
            risk_level = 'high'
        elif risk_score >= 25:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'should_block': risk_score >= 60
        }


class CacheUtils:
    """Utility functions for caching operations."""
    
    @staticmethod
    def get_cache_key(prefix: str, *args) -> str:
        """
        Generate cache key with prefix and arguments.
        
        Args:
            prefix: Cache key prefix
            *args: Additional arguments for key
            
        Returns:
            Cache key string
        """
        key_parts = [prefix] + [str(arg) for arg in args]
        return ':'.join(key_parts)
    
    @staticmethod
    def cache_result(key: str, data: Any, timeout: int = 300) -> None:
        """
        Cache result with specified timeout.
        
        Args:
            key: Cache key
            data: Data to cache
            timeout: Cache timeout in seconds
        """
        try:
            cache.set(key, data, timeout)
        except Exception as e:
            logger.warning(f"Failed to cache data for key {key}: {e}")
    
    @staticmethod
    def get_cached_result(key: str) -> Optional[Any]:
        """
        Get cached result.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None
        """
        try:
            return cache.get(key)
        except Exception as e:
            logger.warning(f"Failed to get cached data for key {key}: {e}")
            return None
    
    @staticmethod
    def invalidate_cache_pattern(pattern: str) -> None:
        """
        Invalidate cache keys matching pattern.
        
        Args:
            pattern: Cache key pattern
        """
        try:
            # This would require cache backend that supports pattern matching
            # For Redis, would use: cache.delete_pattern(pattern)
            # For now, just log the operation
            logger.info(f"Invalidating cache pattern: {pattern}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache pattern {pattern}: {e}")


class ValidationUtils:
    """Utility functions for data validation."""
    
    @staticmethod
    def is_valid_uuid(uuid_string: str) -> bool:
        """
        Check if string is valid UUID.
        
        Args:
            uuid_string: String to validate
            
        Returns:
            True if valid UUID
        """
        try:
            UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """
        Check if string is valid email.
        
        Args:
            email: Email string to validate
            
        Returns:
            True if valid email
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Check if string is valid URL.
        
        Args:
            url: URL string to validate
            
        Returns:
            True if valid URL
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """
        Sanitize string value.
        
        Args:
            value: String to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value)
        
        # Remove potentially harmful characters
        sanitized = re.sub(r'[<>"\']', '', value)
        
        # Truncate to max length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()
        
        return sanitized.strip()


class DateUtils:
    """Utility functions for date operations."""
    
    @staticmethod
    def get_date_range(period: str) -> Tuple[date, date]:
        """
        Get date range for a given period.
        
        Args:
            period: Period type ('today', 'yesterday', 'week', 'month', 'quarter', 'year')
            
        Returns:
            Tuple of (start_date, end_date)
        """
        today = timezone.now().date()
        
        if period == 'today':
            return today, today
        elif period == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif period == 'week':
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=6)
            return start, end
        elif period == 'month':
            start = today.replace(day=1)
            next_month = start.replace(month=start.month % 12 + 1, day=1)
            end = next_month - timedelta(days=1)
            return start, end
        elif period == 'quarter':
            quarter = (today.month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            start = today.replace(month=start_month, day=1)
            end_month = start_month + 2
            end = today.replace(month=end_month, day=1) - timedelta(days=1)
            return start, end
        elif period == 'year':
            start = today.replace(month=1, day=1)
            end = today.replace(month=12, day=31)
            return start, end
        else:
            return today, today
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Format duration in seconds to human-readable string.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            return f"{hours}h {remaining_minutes}m"
    
    @staticmethod
    def get_business_days(start_date: date, end_date: date) -> int:
        """
        Calculate number of business days between dates.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Number of business days
        """
        business_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Monday to Friday
                business_days += 1
            current_date += timedelta(days=1)
        
        return business_days
