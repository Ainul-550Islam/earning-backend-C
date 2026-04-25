"""
Conversion Quality Service

Service for scoring conversion quality,
including behavioral analysis and validation.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.fraud_protection import ConversionQualityScore
from ...models.offer import AdvertiserOffer
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class ConversionQualityService:
    """
    Service for scoring conversion quality.
    
    Handles behavioral analysis, quality scoring,
    and conversion validation.
    """
    
    def __init__(self):
        self.logger = logger
    
    def score_conversion_quality(self, offer: AdvertiserOffer, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score conversion quality.
        
        Args:
            offer: Offer instance
            conversion_data: Conversion information
            
        Returns:
            Dict[str, Any]: Quality score results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Perform quality analysis
            quality_analysis = self._perform_quality_analysis(offer, conversion_data)
            
            # Calculate overall quality score
            overall_score = self._calculate_overall_quality_score(quality_analysis)
            
            # Determine quality level
            quality_level = self._determine_quality_level(overall_score)
            
            # Create quality score record
            quality_score = ConversionQualityScore.objects.create(
                offer=offer,
                date=timezone.now().date(),
                overall_score=overall_score,
                quality_level=quality_level,
                behavioral_score=quality_analysis.get('behavioral_score', 0.0),
                timing_score=quality_analysis.get('timing_score', 0.0),
        engagement_score=quality_analysis.get('engagement_score', 0.0),
        technical_score=quality_analysis.get('technical_score', 0.0),
        valid_conversion_rate=quality_analysis.get('valid_conversion_rate', 0.0),
        invalid_conversion_rate=quality_analysis.get('invalid_conversion_rate', 0.0),
        metadata={
            'conversion_data': conversion_data,
            'analysis': quality_analysis,
        }
            )
            
            # Send alert for low quality conversions
            if quality_level in ['poor', 'very_poor']:
                self._send_quality_alert(offer.advertiser, quality_score)
            
            self.logger.info(f"Scored conversion quality for offer: {offer.title}")
            
            return {
                'quality_score_id': quality_score.id,
                'overall_score': overall_score,
                'quality_level': quality_level,
                'analysis': quality_analysis,
                'scored_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error scoring conversion quality: {e}")
            raise ValidationError(f"Failed to score conversion quality: {str(e)}")
    
    def get_quality_report(self, offer: AdvertiserOffer, days: int = 30) -> Dict[str, Any]:
        """
        Get quality report for offer.
        
        Args:
            offer: Offer instance
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Quality report
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            start_date = timezone.now().date() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get quality scores for the period
            quality_scores = ConversionQualityScore.objects.filter(
                offer=offer,
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
            
            if not quality_scores.exists():
                return {
                    'offer_id': offer.id,
                    'offer_title': offer.title,
                    'period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'days': days,
                    },
                    'summary': {
                        'total_conversions': 0,
                        'avg_quality_score': 0.0,
                        'quality_distribution': {},
                    },
                    'daily_breakdown': {},
                    'trends': {},
                    'recommendations': [],
                }
            
            # Aggregate quality data
            quality_data = quality_scores.aggregate(
                total_conversions=models.Count('id'),
                avg_overall_score=models.Avg('overall_score'),
                avg_behavioral_score=models.Avg('behavioral_score'),
                avg_timing_score=models.Avg('timing_score'),
                avg_engagement_score=models.Avg('engagement_score'),
                avg_technical_score=models.Avg('technical_score'),
                avg_valid_rate=models.Avg('valid_conversion_rate'),
                avg_invalid_rate=models.Avg('invalid_conversion_rate'),
            )
            
            # Get quality level distribution
            quality_distribution = quality_scores.values('quality_level').annotate(
                count=models.Count('id')
            ).order_by('-count')
            
            # Get daily breakdown
            daily_breakdown = {}
            for score in quality_scores:
                daily_breakdown[score.date.isoformat()] = {
                    'overall_score': float(score.overall_score),
                    'quality_level': score.quality_level,
                    'behavioral_score': float(score.behavioral_score),
                    'timing_score': float(score.timing_score),
                    'engagement_score': float(score.engagement_score),
                    'technical_score': float(score.technical_score),
                }
            
            # Calculate trends
            trends = self._calculate_quality_trends(quality_scores)
            
            # Generate recommendations
            recommendations = self._generate_quality_recommendations(quality_data, trends)
            
            return {
                'offer_id': offer.id,
                'offer_title': offer.title,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'summary': {
                    'total_conversions': quality_data['total_conversions'],
                    'avg_quality_score': float(quality_data['avg_overall_score'] or 0),
                    'avg_behavioral_score': float(quality_data['avg_behavioral_score'] or 0),
                    'avg_timing_score': float(quality_data['avg_timing_score'] or 0),
                    'avg_engagement_score': float(quality_data['avg_engagement_score'] or 0),
                    'avg_technical_score': float(quality_data['avg_technical_score'] or 0),
                    'avg_valid_rate': float(quality_data['avg_valid_rate'] or 0),
                    'avg_invalid_rate': float(quality_data['avg_invalid_rate'] or 0),
                    'quality_distribution': {
                        item['quality_level']: item['count']
                        for item in quality_distribution
                    },
                },
                'daily_breakdown': daily_breakdown,
                'trends': trends,
                'recommendations': recommendations,
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting quality report: {e}")
            raise ValidationError(f"Failed to get quality report: {str(e)}")
    
    def get_advertiser_quality_summary(self, advertiser, days: int = 30) -> Dict[str, Any]:
        """
        Get quality summary for advertiser.
        
        Args:
            advertiser: Advertiser instance
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Quality summary
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            start_date = timezone.now().date() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get quality scores for all advertiser offers
            quality_scores = ConversionQualityScore.objects.filter(
                offer__advertiser=advertiser,
                date__gte=start_date,
                date__lte=end_date
            ).select_related('offer')
            
            if not quality_scores.exists():
                return {
                    'advertiser_id': advertiser.id,
                    'advertiser_name': advertiser.company_name,
                    'period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'days': days,
                    },
                    'summary': {
                        'total_conversions': 0,
                        'avg_quality_score': 0.0,
                        'top_performing_offers': [],
                        'low_performing_offers': [],
                    },
                    'offer_breakdown': {},
                    'generated_at': timezone.now().isoformat(),
                }
            
            # Aggregate overall data
            overall_data = quality_scores.aggregate(
                total_conversions=models.Count('id'),
                avg_overall_score=models.Avg('overall_score'),
                avg_valid_rate=models.Avg('valid_conversion_rate'),
            )
            
            # Get offer breakdown
            offer_breakdown = quality_scores.values('offer__id', 'offer__title').annotate(
                conversions=models.Count('id'),
                avg_score=models.Avg('overall_score'),
                valid_rate=models.Avg('valid_conversion_rate')
            ).order_by('-avg_score')
            
            # Get top and low performing offers
            top_offers = list(offer_breakdown[:5])
            low_offers = list(offer_breakdown.reverse()[:5])
            
            return {
                'advertiser_id': advertiser.id,
                'advertiser_name': advertiser.company_name,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'summary': {
                    'total_conversions': overall_data['total_conversions'],
                    'avg_quality_score': float(overall_data['avg_overall_score'] or 0),
                    'avg_valid_rate': float(overall_data['avg_valid_rate'] or 0),
                    'top_performing_offers': [
                        {
                            'offer_id': offer['offer__id'],
                            'offer_title': offer['offer__title'],
                            'conversions': offer['conversions'],
                            'avg_score': float(offer['avg_score']),
                            'valid_rate': float(offer['valid_rate']),
                        }
                        for offer in top_offers
                    ],
                    'low_performing_offers': [
                        {
                            'offer_id': offer['offer__id'],
                            'offer_title': offer['offer__title'],
                            'conversions': offer['conversions'],
                            'avg_score': float(offer['avg_score']),
                            'valid_rate': float(offer['valid_rate']),
                        }
                        for offer in low_offers
                    ],
                },
                'offer_breakdown': {
                    str(offer['offer__id']): {
                        'offer_title': offer['offer__title'],
                        'conversions': offer['conversions'],
                        'avg_score': float(offer['avg_score']),
                        'valid_rate': float(offer['valid_rate']),
                    }
                    for offer in offer_breakdown
                },
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting advertiser quality summary: {e}")
            raise ValidationError(f"Failed to get advertiser quality summary: {str(e)}")
    
    def analyze_conversion_patterns(self, offer: AdvertiserOffer, days: int = 30) -> Dict[str, Any]:
        """
        Analyze conversion patterns for quality insights.
        
        Args:
            offer: Offer instance
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Pattern analysis results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            start_date = timezone.now().date() - timezone.timedelta(days=days-1)
            end_date = timezone.now().date()
            
            # Get quality scores
            quality_scores = ConversionQualityScore.objects.filter(
                offer=offer,
                date__gte=start_date,
                date__lte=end_date
            ).order_by('date')
            
            if not quality_scores.exists():
                return {
                    'offer_id': offer.id,
                    'offer_title': offer.title,
                    'period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'days': days,
                    },
                    'patterns': {},
                    'anomalies': [],
                    'insights': [],
                }
            
            # Analyze patterns
            patterns = {
                'temporal': self._analyze_temporal_patterns(quality_scores),
                'behavioral': self._analyze_behavioral_patterns(quality_scores),
                'geographic': self._analyze_geographic_patterns(quality_scores),
                'device': self._analyze_device_patterns(quality_scores),
            }
            
            # Detect anomalies
            anomalies = self._detect_quality_anomalies(quality_scores)
            
            # Generate insights
            insights = self._generate_quality_insights(patterns, anomalies)
            
            return {
                'offer_id': offer.id,
                'offer_title': offer.title,
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days,
                },
                'patterns': patterns,
                'anomalies': anomalies,
                'insights': insights,
                'analyzed_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing conversion patterns: {e}")
            raise ValidationError(f"Failed to analyze conversion patterns: {str(e)}")
    
    def _perform_quality_analysis(self, offer: AdvertiserOffer, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive quality analysis."""
        analysis = {}
        
        # Behavioral analysis
        analysis['behavioral_score'] = self._analyze_behavioral_quality(conversion_data)
        analysis['behavioral_factors'] = self._get_behavioral_factors(conversion_data)
        
        # Timing analysis
        analysis['timing_score'] = self._analyze_timing_quality(conversion_data)
        analysis['timing_factors'] = self._get_timing_factors(conversion_data)
        
        # Engagement analysis
        analysis['engagement_score'] = self._analyze_engagement_quality(conversion_data)
        analysis['engagement_factors'] = self._get_engagement_factors(conversion_data)
        
        # Technical analysis
        analysis['technical_score'] = self._analyze_technical_quality(conversion_data)
        analysis['technical_factors'] = self._get_technical_factors(conversion_data)
        
        # Calculate validity rates
        analysis['valid_conversion_rate'] = self._calculate_validity_rate(conversion_data)
        analysis['invalid_conversion_rate'] = 1.0 - analysis['valid_conversion_rate']
        
        return analysis
    
    def _analyze_behavioral_quality(self, conversion_data: Dict[str, Any]) -> float:
        """Analyze behavioral quality indicators."""
        score = 50.0  # Base score
        
        # Session duration
        session_duration = conversion_data.get('session_duration', 0)
        if session_duration >= 60:
            score += 20
        elif session_duration >= 30:
            score += 10
        elif session_duration < 10:
            score -= 20
        
        # Page views
        page_views = conversion_data.get('page_views', 1)
        if page_views >= 5:
            score += 15
        elif page_views >= 3:
            score += 10
        elif page_views == 1:
            score -= 10
        
        # Time on page
        time_on_page = conversion_data.get('time_on_page', 0)
        if time_on_page >= 120:
            score += 15
        elif time_on_page >= 60:
            score += 10
        elif time_on_page < 15:
            score -= 15
        
        return max(0, min(100, score))
    
    def _analyze_timing_quality(self, conversion_data: Dict[str, Any]) -> float:
        """Analyze timing quality indicators."""
        score = 50.0  # Base score
        
        # Time to conversion
        time_to_conversion = conversion_data.get('time_to_conversion', 0)
        if 300 <= time_to_conversion <= 1800:  # 5-30 minutes
            score += 20
        elif 60 <= time_to_conversion <= 3600:  # 1 minute - 1 hour
            score += 10
        elif time_to_conversion < 10:  # Less than 10 seconds
            score -= 25
        elif time_to_conversion > 7200:  # More than 2 hours
            score -= 15
        
        # Time of day
        hour_of_day = conversion_data.get('hour_of_day', 12)
        if 9 <= hour_of_day <= 21:  # Business hours
            score += 10
        elif 0 <= hour_of_day <= 6:  # Late night
            score -= 15
        
        return max(0, min(100, score))
    
    def _analyze_engagement_quality(self, conversion_data: Dict[str, Any]) -> float:
        """Analyze engagement quality indicators."""
        score = 50.0  # Base score
        
        # Scroll depth
        scroll_depth = conversion_data.get('scroll_depth', 0)
        if scroll_depth >= 80:
            score += 20
        elif scroll_depth >= 50:
            score += 15
        elif scroll_depth < 20:
            score -= 20
        
        # Click events
        click_events = conversion_data.get('click_events', 0)
        if click_events >= 5:
            score += 15
        elif click_events >= 2:
            score += 10
        elif click_events == 0:
            score -= 10
        
        # Form interactions
        form_interactions = conversion_data.get('form_interactions', 0)
        if form_interactions >= 3:
            score += 15
        elif form_interactions >= 1:
            score += 5
        
        return max(0, min(100, score))
    
    def _analyze_technical_quality(self, conversion_data: Dict[str, Any]) -> float:
        """Analyze technical quality indicators."""
        score = 50.0  # Base score
        
        # Browser compatibility
        user_agent = conversion_data.get('user_agent', '')
        if self._is_modern_browser(user_agent):
            score += 10
        elif self._is_old_browser(user_agent):
            score -= 15
        
        # Device type
        device_type = conversion_data.get('device_type', 'desktop')
        if device_type == 'desktop':
            score += 10
        elif device_type == 'mobile':
            score += 5
        
        # Connection speed
        connection_speed = conversion_data.get('connection_speed', 'unknown')
        if connection_speed == 'fast':
            score += 10
        elif connection_speed == 'slow':
            score -= 10
        
        # JavaScript enabled
        js_enabled = conversion_data.get('javascript_enabled', True)
        if js_enabled:
            score += 10
        else:
            score -= 30
        
        return max(0, min(100, score))
    
    def _get_behavioral_factors(self, conversion_data: Dict[str, Any]) -> List[str]:
        """Get behavioral quality factors."""
        factors = []
        
        session_duration = conversion_data.get('session_duration', 0)
        if session_duration < 10:
            factors.append('Very short session duration')
        elif session_duration > 1800:
            factors.append('Very long session duration')
        
        page_views = conversion_data.get('page_views', 1)
        if page_views == 1:
            factors.append('Single page view')
        
        return factors
    
    def _get_timing_factors(self, conversion_data: Dict[str, Any]) -> List[str]:
        """Get timing quality factors."""
        factors = []
        
        time_to_conversion = conversion_data.get('time_to_conversion', 0)
        if time_to_conversion < 10:
            factors.append('Instant conversion')
        elif time_to_conversion > 7200:
            factors.append('Very slow conversion')
        
        hour_of_day = conversion_data.get('hour_of_day', 12)
        if 0 <= hour_of_day <= 6:
            factors.append('Late night conversion')
        
        return factors
    
    def _get_engagement_factors(self, conversion_data: Dict[str, Any]) -> List[str]:
        """Get engagement quality factors."""
        factors = []
        
        scroll_depth = conversion_data.get('scroll_depth', 0)
        if scroll_depth < 20:
            factors.append('Low scroll depth')
        
        click_events = conversion_data.get('click_events', 0)
        if click_events == 0:
            factors.append('No click events')
        
        return factors
    
    def _get_technical_factors(self, conversion_data: Dict[str, Any]) -> List[str]:
        """Get technical quality factors."""
        factors = []
        
        user_agent = conversion_data.get('user_agent', '')
        if self._is_old_browser(user_agent):
            factors.append('Old browser')
        
        js_enabled = conversion_data.get('javascript_enabled', True)
        if not js_enabled:
            factors.append('JavaScript disabled')
        
        return factors
    
    def _calculate_validity_rate(self, conversion_data: Dict[str, Any]) -> float:
        """Calculate conversion validity rate."""
        # This would implement actual validity calculation
        # For now, return high validity
        return 0.95
    
    def _calculate_overall_quality_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall quality score from analysis."""
        weights = {
            'behavioral_score': 0.35,
            'timing_score': 0.25,
            'engagement_score': 0.25,
            'technical_score': 0.15,
        }
        
        overall_score = 0.0
        for factor, weight in weights.items():
            overall_score += analysis.get(factor, 0.0) * weight
        
        return max(0, min(100, overall_score))
    
    def _determine_quality_level(self, score: float) -> str:
        """Determine quality level from score."""
        if score >= 90:
            return 'excellent'
        elif score >= 80:
            return 'very_good'
        elif score >= 70:
            return 'good'
        elif score >= 60:
            return 'fair'
        elif score >= 50:
            return 'poor'
        else:
            return 'very_poor'
    
    def _is_modern_browser(self, user_agent: str) -> bool:
        """Check if browser is modern."""
        modern_browsers = ['Chrome', 'Firefox', 'Safari', 'Edge']
        return any(browser in user_agent for browser in modern_browsers)
    
    def _is_old_browser(self, user_agent: str) -> bool:
        """Check if browser is old."""
        old_browsers = ['IE', 'MSIE', 'Netscape']
        return any(browser in user_agent for browser in old_browsers)
    
    def _calculate_quality_trends(self, quality_scores) -> Dict[str, Any]:
        """Calculate quality trends."""
        if len(quality_scores) < 2:
            return {
                'trend': 'stable',
                'direction': 'neutral',
                'change_percentage': 0.0,
            }
        
        # Split into two halves
        mid_point = len(quality_scores) // 2
        first_half = quality_scores[:mid_point]
        second_half = quality_scores[mid_point:]
        
        # Calculate averages
        first_avg = first_half.aggregate(avg_score=models.Avg('overall_score'))['avg_score'] or 0
        second_avg = second_half.aggregate(avg_score=models.Avg('overall_score'))['avg_score'] or 0
        
        # Calculate trend
        if second_avg > first_avg * 1.05:
            trend = 'improving'
            direction = 'up'
        elif second_avg < first_avg * 0.95:
            trend = 'declining'
            direction = 'down'
        else:
            trend = 'stable'
            direction = 'neutral'
        
        change_percentage = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
        
        return {
            'trend': trend,
            'direction': direction,
            'change_percentage': change_percentage,
        }
    
    def _generate_quality_recommendations(self, quality_data: Dict[str, Any], trends: Dict[str, Any]) -> List[str]:
        """Generate quality improvement recommendations."""
        recommendations = []
        
        avg_score = quality_data.get('avg_quality_score', 0)
        avg_behavioral = quality_data.get('avg_behavioral_score', 0)
        avg_timing = quality_data.get('avg_timing_score', 0)
        avg_engagement = quality_data.get('avg_engagement_score', 0)
        avg_technical = quality_data.get('avg_technical_score', 0)
        
        if avg_score < 70:
            recommendations.append('Overall conversion quality needs improvement')
        
        if avg_behavioral < 60:
            recommendations.append('Focus on improving user engagement and session quality')
        
        if avg_timing < 60:
            recommendations.append('Review conversion timing patterns and optimize user journey')
        
        if avg_engagement < 60:
            recommendations.append('Improve content engagement and user experience')
        
        if avg_technical < 60:
            recommendations.append('Optimize technical aspects and device compatibility')
        
        if trends.get('trend') == 'declining':
            recommendations.append('Quality is declining - investigate and address issues promptly')
        
        return recommendations
    
    def _analyze_temporal_patterns(self, quality_scores) -> Dict[str, Any]:
        """Analyze temporal quality patterns."""
        # This would implement temporal pattern analysis
        return {
            'daily_pattern': 'stable',
            'weekly_pattern': 'stable',
            'hourly_pattern': 'stable',
        }
    
    def _analyze_behavioral_patterns(self, quality_scores) -> Dict[str, Any]:
        """Analyze behavioral quality patterns."""
        return {
            'session_patterns': 'normal',
            'engagement_patterns': 'normal',
        }
    
    def _analyze_geographic_patterns(self, quality_scores) -> Dict[str, Any]:
        """Analyze geographic quality patterns."""
        return {
            'regional_patterns': 'consistent',
            'country_patterns': 'consistent',
        }
    
    def _analyze_device_patterns(self, quality_scores) -> Dict[str, Any]:
        """Analyze device quality patterns."""
        return {
            'device_patterns': 'consistent',
            'browser_patterns': 'consistent',
        }
    
    def _detect_quality_anomalies(self, quality_scores) -> List[Dict[str, Any]]:
        """Detect quality anomalies."""
        anomalies = []
        
        # This would implement anomaly detection
        # For now, return empty list
        return anomalies
    
    def _generate_quality_insights(self, patterns: Dict[str, Any], anomalies: List[Dict[str, Any]]) -> List[str]:
        """Generate quality insights."""
        insights = []
        
        if anomalies:
            insights.append(f'Detected {len(anomalies)} quality anomalies requiring attention')
        
        # Add pattern-based insights
        if patterns.get('temporal', {}).get('daily_pattern') == 'declining':
            insights.append('Daily quality trend shows decline - investigate recent changes')
        
        return insights
    
    def _send_quality_alert(self, advertiser, quality_score: ConversionQualityScore):
        """Send quality alert notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='low_quality',
            title=_('Low Conversion Quality Detected'),
            message=_(
                'Low quality conversion detected. Quality level: {level}, Score: {score:.1f}'
            ).format(
                level=quality_score.quality_level,
                score=quality_score.overall_score
            ),
            priority='medium',
            action_url='/advertiser/offers/quality/',
            action_text=_('View Quality Report')
        )
