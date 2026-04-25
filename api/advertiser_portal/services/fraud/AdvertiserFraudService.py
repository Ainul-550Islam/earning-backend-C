"""
Advertiser Fraud Service

Service for applying fraud detection to incoming clicks,
including real-time analysis and prevention.
"""

import logging
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ...models.fraud_protection import AdvertiserFraudConfig, InvalidClickLog
from ...models.notification import AdvertiserNotification

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserFraudService:
    """
    Service for applying fraud detection to incoming clicks.
    
    Handles real-time analysis, fraud prevention,
    and click validation.
    """
    
    def __init__(self):
        self.logger = logger
    
    def analyze_click(self, advertiser, click_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze click for fraud indicators.
        
        Args:
            advertiser: Advertiser instance
            click_data: Click information
            
        Returns:
            Dict[str, Any]: Fraud analysis results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get fraud configuration
            fraud_config = self._get_fraud_config(advertiser)
            
            if not fraud_config or not fraud_config.is_active:
                return {
                    'fraud_score': 0.0,
                    'risk_level': 'low',
                    'is_fraudulent': False,
                    'blocked': False,
                    'reason': 'Fraud detection disabled',
                }
            
            # Perform fraud analysis
            analysis_result = self._perform_fraud_analysis(click_data, fraud_config)
            
            # Log suspicious clicks
            if analysis_result['is_fraudulent']:
                self._log_invalid_click(advertiser, click_data, analysis_result)
            
            # Send alert for high-risk clicks
            if analysis_result['risk_level'] == 'critical':
                self._send_fraud_alert(advertiser, analysis_result)
            
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Error analyzing click for fraud: {e}")
            raise ValidationError(f"Failed to analyze click: {str(e)}")
    
    def validate_conversion(self, advertiser, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate conversion for fraud indicators.
        
        Args:
            advertiser: Advertiser instance
            conversion_data: Conversion information
            
        Returns:
            Dict[str, Any]: Validation results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Get fraud configuration
            fraud_config = self._get_fraud_config(advertiser)
            
            if not fraud_config or not fraud_config.is_active:
                return {
                    'fraud_score': 0.0,
                    'risk_level': 'low',
                    'is_fraudulent': False,
                    'blocked': False,
                    'reason': 'Fraud detection disabled',
                }
            
            # Perform conversion validation
            validation_result = self._validate_conversion_fraud(conversion_data, fraud_config)
            
            # Log suspicious conversions
            if validation_result['is_fraudulent']:
                self._log_invalid_conversion(advertiser, conversion_data, validation_result)
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Error validating conversion for fraud: {e}")
            raise ValidationError(f"Failed to validate conversion: {str(e)}")
    
    def get_fraud_statistics(self, advertiser, days: int = 30) -> Dict[str, Any]:
        """
        Get fraud statistics for advertiser.
        
        Args:
            advertiser: Advertiser instance
            days: Number of days to analyze
            
        Returns:
            Dict[str, Any]: Fraud statistics
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            # Get invalid click logs
            invalid_clicks = InvalidClickLog.objects.filter(
                advertiser=advertiser,
                created_at__gte=start_date
            )
            
            # Aggregate statistics
            stats = invalid_clicks.aggregate(
                total_invalid_clicks=models.Count('id'),
                blocked_clicks=models.Count('id', filter=models.Q(blocked=True)),
                high_risk_clicks=models.Count('id', filter=models.Q(risk_level='high')),
                critical_risk_clicks=models.Count('id', filter=models.Q(risk_level='critical'))
            )
            
            # Get breakdown by reason
            reason_breakdown = invalid_clicks.values('reason').annotate(
                count=models.Count('id')
            ).order_by('-count')
            
            # Get breakdown by IP
            ip_breakdown = invalid_clicks.values('ip').annotate(
                count=models.Count('id')
            ).order_by('-count')[:10]
            
            # Get daily breakdown
            daily_breakdown = {}
            current_date = start_date.date()
            while current_date <= timezone.now().date():
                day_invalid = invalid_clicks.filter(created_at__date=current_date).count()
                daily_breakdown[current_date.isoformat()] = day_invalid
                current_date += timezone.timedelta(days=1)
            
            return {
                'period': {
                    'start_date': start_date.date().isoformat(),
                    'end_date': timezone.now().date().isoformat(),
                    'days': days,
                },
                'summary': {
                    'total_invalid_clicks': stats['total_invalid_clicks'],
                    'blocked_clicks': stats['blocked_clicks'],
                    'high_risk_clicks': stats['high_risk_clicks'],
                    'critical_risk_clicks': stats['critical_risk_clicks'],
                    'block_rate': (stats['blocked_clicks'] / stats['total_invalid_clicks'] * 100) if stats['total_invalid_clicks'] > 0 else 0,
                },
                'breakdowns': {
                    'by_reason': [
                        {'reason': item['reason'], 'count': item['count']}
                        for item in reason_breakdown
                    ],
                    'by_ip': [
                        {'ip': item['ip'], 'count': item['count']}
                        for item in ip_breakdown
                    ],
                    'by_day': daily_breakdown,
                },
                'generated_at': timezone.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting fraud statistics: {e}")
            raise ValidationError(f"Failed to get fraud statistics: {str(e)}")
    
    def update_fraud_config(self, advertiser, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update fraud detection configuration.
        
        Args:
            advertiser: Advertiser instance
            config_data: Configuration data
            
        Returns:
            Dict[str, Any]: Update result
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            with transaction.atomic():
                # Get or create fraud config
                fraud_config, created = AdvertiserFraudConfig.objects.get_or_create(
                    advertiser=advertiser,
                    defaults={
                        'is_active': True,
                        'block_vpn': True,
                        'block_proxy': True,
                        'block_bots': True,
                        'min_session_seconds': 30,
                        'max_conversions_per_ip_per_day': 10,
                        'custom_rules': {},
                    }
                )
                
                # Update configuration
                allowed_fields = [
                    'is_active', 'block_vpn', 'block_proxy', 'block_bots',
                    'min_session_seconds', 'max_conversions_per_ip_per_day',
                    'custom_rules'
                ]
                
                for field in allowed_fields:
                    if field in config_data:
                        setattr(fraud_config, field, config_data[field])
                
                fraud_config.save()
                
                # Send notification
                if not created:
                    self._send_config_updated_notification(advertiser, fraud_config)
                
                self.logger.info(f"Updated fraud config for {advertiser.company_name}")
                
                return {
                    'success': True,
                    'config_id': fraud_config.id,
                    'is_active': fraud_config.is_active,
                    'updated_at': timezone.now().isoformat(),
                }
                
        except Exception as e:
            self.logger.error(f"Error updating fraud config: {e}")
            raise ValidationError(f"Failed to update fraud config: {str(e)}")
    
    def get_fraud_config(self, advertiser) -> Dict[str, Any]:
        """
        Get fraud detection configuration.
        
        Args:
            advertiser: Advertiser instance
            
        Returns:
            Dict[str, Any]: Fraud configuration
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            fraud_config = self._get_fraud_config(advertiser)
            
            if not fraud_config:
                return {
                    'has_config': False,
                    'is_active': False,
                }
            
            return {
                'has_config': True,
                'is_active': fraud_config.is_active,
                'block_vpn': fraud_config.block_vpn,
                'block_proxy': fraud_config.block_proxy,
                'block_bots': fraud_config.block_bots,
                'min_session_seconds': fraud_config.min_session_seconds,
                'max_conversions_per_ip_per_day': fraud_config.max_conversions_per_ip_per_day,
                'custom_rules': fraud_config.custom_rules,
                'created_at': fraud_config.created_at.isoformat(),
                'updated_at': fraud_config.updated_at.isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting fraud config: {e}")
            raise ValidationError(f"Failed to get fraud config: {str(e)}")
    
    def get_fraud_alerts(self, advertiser, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get recent fraud alerts for advertiser.
        
        Args:
            advertiser: Advertiser instance
            hours: Number of hours to look back
            
        Returns:
            List[Dict[str, Any]]: Fraud alerts
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            start_time = timezone.now() - timezone.timedelta(hours=hours)
            
            # Get recent invalid clicks
            recent_clicks = InvalidClickLog.objects.filter(
                advertiser=advertiser,
                created_at__gte=start_time
            ).order_by('-created_at')
            
            alerts = []
            for click in recent_clicks:
                alerts.append({
                    'id': click.id,
                    'type': 'invalid_click',
                    'risk_level': click.risk_level,
                    'blocked': click.blocked,
                    'reason': click.reason,
                    'ip': click.ip,
                    'user_agent': click.user_agent,
                    'created_at': click.created_at.isoformat(),
                    'campaign_id': click.campaign_id,
                    'offer_id': click.offer_id,
                })
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting fraud alerts: {e}")
            raise ValidationError(f"Failed to get fraud alerts: {str(e)}")
    
    def _get_fraud_config(self, advertiser) -> Optional[AdvertiserFraudConfig]:
        """Get fraud configuration for advertiser."""
        try:
            return AdvertiserFraudConfig.objects.get(advertiser=advertiser)
        except AdvertiserFraudConfig.DoesNotExist:
            return None
    
    def _perform_fraud_analysis(self, click_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> Dict[str, Any]:
        """Perform comprehensive fraud analysis."""
        fraud_score = 0.0
        risk_factors = []
        blocked = False
        
        # Check IP-based fraud
        ip_score, ip_factors = self._check_ip_fraud(click_data, fraud_config)
        fraud_score += ip_score
        risk_factors.extend(ip_factors)
        
        # Check user agent
        ua_score, ua_factors = self._check_user_agent_fraud(click_data, fraud_config)
        fraud_score += ua_score
        risk_factors.extend(ua_factors)
        
        # Check session duration
        session_score, session_factors = self._check_session_fraud(click_data, fraud_config)
        fraud_score += session_score
        risk_factors.extend(session_factors)
        
        # Check conversion patterns
        conversion_score, conversion_factors = self._check_conversion_fraud(click_data, fraud_config)
        fraud_score += conversion_score
        risk_factors.extend(conversion_factors)
        
        # Check custom rules
        custom_score, custom_factors = self._check_custom_rules(click_data, fraud_config)
        fraud_score += custom_score
        risk_factors.extend(custom_factors)
        
        # Determine risk level and action
        risk_level = self._determine_risk_level(fraud_score)
        
        if risk_level == 'critical':
            blocked = True
        elif risk_level == 'high' and fraud_config.block_high_risk:
            blocked = True
        
        return {
            'fraud_score': min(fraud_score, 100.0),
            'risk_level': risk_level,
            'is_fraudulent': fraud_score > 50.0,
            'blocked': blocked,
            'risk_factors': risk_factors,
            'analysis_time': timezone.now().isoformat(),
        }
    
    def _check_ip_fraud(self, click_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> tuple:
        """Check IP-based fraud indicators."""
        score = 0.0
        factors = []
        
        ip = click_data.get('ip', '')
        
        # Check for VPN/proxy
        if fraud_config.block_vpn and self._is_vpn_ip(ip):
            score += 30.0
            factors.append('VPN detected')
        
        if fraud_config.block_proxy and self._is_proxy_ip(ip):
            score += 25.0
            factors.append('Proxy detected')
        
        # Check for datacenter IP
        if self._is_datacenter_ip(ip):
            score += 35.0
            factors.append('Datacenter IP')
        
        # Check for suspicious IP ranges
        if self._is_suspicious_ip(ip):
            score += 20.0
            factors.append('Suspicious IP range')
        
        return score, factors
    
    def _check_user_agent_fraud(self, click_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> tuple:
        """Check user agent fraud indicators."""
        score = 0.0
        factors = []
        
        user_agent = click_data.get('user_agent', '')
        
        # Check for bots
        if fraud_config.block_bots and self._is_bot_user_agent(user_agent):
            score += 40.0
            factors.append('Bot detected')
        
        # Check for suspicious user agents
        if self._is_suspicious_user_agent(user_agent):
            score += 15.0
            factors.append('Suspicious user agent')
        
        return score, factors
    
    def _check_session_fraud(self, click_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> tuple:
        """Check session duration fraud indicators."""
        score = 0.0
        factors = []
        
        session_duration = click_data.get('session_duration', 0)
        
        # Check for too short sessions
        if session_duration < fraud_config.min_session_seconds:
            score += 20.0
            factors.append(f'Session too short: {session_duration}s')
        
        return score, factors
    
    def _check_conversion_fraud(self, click_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> tuple:
        """Check conversion pattern fraud indicators."""
        score = 0.0
        factors = []
        
        ip = click_data.get('ip', '')
        
        # Check conversion frequency from IP
        if self._has_high_conversion_frequency(ip, fraud_config):
            score += 25.0
            factors.append('High conversion frequency from IP')
        
        return score, factors
    
    def _check_custom_rules(self, click_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> tuple:
        """Check custom fraud rules."""
        score = 0.0
        factors = []
        
        custom_rules = fraud_config.custom_rules or {}
        
        # This would implement custom rule checking
        # For now, return no score
        return score, factors
    
    def _validate_conversion_fraud(self, conversion_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> Dict[str, Any]:
        """Validate conversion for fraud indicators."""
        fraud_score = 0.0
        risk_factors = []
        
        # Check conversion timing
        timing_score, timing_factors = self._check_conversion_timing(conversion_data, fraud_config)
        fraud_score += timing_score
        risk_factors.extend(timing_factors)
        
        # Check conversion patterns
        pattern_score, pattern_factors = self._check_conversion_patterns(conversion_data, fraud_config)
        fraud_score += pattern_score
        risk_factors.extend(pattern_factors)
        
        # Determine risk level
        risk_level = self._determine_risk_level(fraud_score)
        
        return {
            'fraud_score': min(fraud_score, 100.0),
            'risk_level': risk_level,
            'is_fraudulent': fraud_score > 50.0,
            'blocked': risk_level == 'critical',
            'risk_factors': risk_factors,
            'validation_time': timezone.now().isoformat(),
        }
    
    def _check_conversion_timing(self, conversion_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> tuple:
        """Check conversion timing fraud indicators."""
        score = 0.0
        factors = []
        
        # This would implement timing analysis
        # For now, return no score
        return score, factors
    
    def _check_conversion_patterns(self, conversion_data: Dict[str, Any], fraud_config: AdvertiserFraudConfig) -> tuple:
        """Check conversion pattern fraud indicators."""
        score = 0.0
        factors = []
        
        # This would implement pattern analysis
        # For now, return no score
        return score, factors
    
    def _determine_risk_level(self, fraud_score: float) -> str:
        """Determine risk level based on fraud score."""
        if fraud_score >= 80:
            return 'critical'
        elif fraud_score >= 60:
            return 'high'
        elif fraud_score >= 40:
            return 'medium'
        elif fraud_score >= 20:
            return 'low'
        else:
            return 'minimal'
    
    def _is_vpn_ip(self, ip: str) -> bool:
        """Check if IP is from VPN."""
        # This would implement VPN detection
        return False
    
    def _is_proxy_ip(self, ip: str) -> bool:
        """Check if IP is from proxy."""
        # This would implement proxy detection
        return False
    
    def _is_datacenter_ip(self, ip: str) -> bool:
        """Check if IP is from datacenter."""
        # This would implement datacenter detection
        return False
    
    def _is_suspicious_ip(self, ip: str) -> bool:
        """Check if IP is suspicious."""
        # This would implement suspicious IP detection
        return False
    
    def _is_bot_user_agent(self, user_agent: str) -> bool:
        """Check if user agent is from bot."""
        bot_indicators = ['bot', 'crawler', 'spider', 'scraper', 'curl', 'wget']
        user_agent_lower = user_agent.lower()
        
        return any(indicator in user_agent_lower for indicator in bot_indicators)
    
    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent is suspicious."""
        # This would implement suspicious user agent detection
        return False
    
    def _has_high_conversion_frequency(self, ip: str, fraud_config: AdvertiserFraudConfig) -> bool:
        """Check if IP has high conversion frequency."""
        # This would implement frequency checking
        return False
    
    def _log_invalid_click(self, advertiser, click_data: Dict[str, Any], analysis_result: Dict[str, Any]):
        """Log invalid click for analysis."""
        try:
            InvalidClickLog.objects.create(
                advertiser=advertiser,
                ip=click_data.get('ip', ''),
                user_agent=click_data.get('user_agent', ''),
                reason=', '.join(analysis_result['risk_factors']),
                risk_level=analysis_result['risk_level'],
                blocked=analysis_result['blocked'],
                fraud_score=analysis_result['fraud_score'],
                campaign_id=click_data.get('campaign_id'),
                offer_id=click_data.get('offer_id'),
                metadata={
                    'click_data': click_data,
                    'analysis_result': analysis_result,
                }
            )
        except Exception as e:
            self.logger.error(f"Error logging invalid click: {e}")
    
    def _log_invalid_conversion(self, advertiser, conversion_data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Log invalid conversion for analysis."""
        # This would implement conversion logging
        pass
    
    def _send_fraud_alert(self, advertiser, analysis_result: Dict[str, Any]):
        """Send fraud alert notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='fraud_alert',
            title=_('High Risk Fraud Detected'),
            message=_(
                'A high-risk fraudulent activity has been detected. '
                'Risk level: {risk_level}, Fraud score: {score:.1f}'
            ).format(
                risk_level=analysis_result['risk_level'],
                score=analysis_result['fraud_score']
            ),
            priority='high',
            action_url='/advertiser/fraud/alerts/',
            action_text=_('View Alerts')
        )
    
    def _send_config_updated_notification(self, advertiser, fraud_config: AdvertiserFraudConfig):
        """Send configuration updated notification."""
        AdvertiserNotification.objects.create(
            advertiser=advertiser,
            type='fraud_alert',
            title=_('Fraud Configuration Updated'),
            message=_('Your fraud detection configuration has been updated.'),
            priority='medium',
            action_url='/advertiser/fraud/config/',
            action_text=_('View Config')
        )
