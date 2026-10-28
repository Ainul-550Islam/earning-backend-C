# =============================================================================
# fraud_detection/services/IPReputationService.py
# =============================================================================
"""
IP Reputation Service.

Comprehensive service for managing IP reputation including lookups,
caching, threat intelligence integration, and automatic updates.
"""

from __future__ import annotations
from django.db import models

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from api.fraud_detection.models import IPReputation, FraudAlert, FraudAttempt
from api.fraud_detection.choices import FraudAlertType, AlertPriority
from api.fraud_detection.constants import RISK_THRESHOLDS, CACHE_KEYS

logger = logging.getLogger(__name__)


class IPReputationService:
    """Service for managing IP reputation data and threat intelligence."""
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour
        self.threat_intelligence_timeout = 10  # seconds
    
    def get_ip_reputation(self, ip_address: str, force_refresh: bool = False) -> IPReputation:
        """
        Get IP reputation with caching and automatic updates.
        
        Args:
            ip_address: IP address to look up
            force_refresh: Force refresh from external sources
            
        Returns:
            IPReputation instance
        """
        try:
            # Check cache first
            cache_key = f'ip_rep_{ip_address}'
            if not force_refresh:
                cached_data = cache.get(cache_key)
                if cached_data:
                    return cached_data
            
            # Get or create IP reputation record
            ip_rep, created = IPReputation.objects.get_or_create(
                ip_address=ip_address,
                defaults={
                    'fraud_score': 0,
                    'spam_score': 0,
                    'malware_score': 0,
                    'total_requests': 0,
                    'fraud_attempts': 0,
                    'unique_users': 0,
                    'last_seen': timezone.now(),
                }
            )
            
            # Update with fresh data if needed
            if created or force_refresh:
                self._update_ip_reputation_data(ip_rep)
                
                # Check external threat intelligence
                self._check_threat_intelligence(ip_rep)
            
            # Cache the result
            cache.set(cache_key, ip_rep, self.cache_ttl)
            
            return ip_rep
            
        except Exception as e:
            logger.error(f"Error getting IP reputation for {ip_address}: {e}")
            # Return default reputation on error
            return IPReputation.objects.create(
                ip_address=ip_address,
                fraud_score=0,
                spam_score=0,
                malware_score=0,
                total_requests=0,
                fraud_attempts=0,
                unique_users=0,
                last_seen=timezone.now(),
            )
    
    def update_ip_activity(self, ip_address: str, user_id: Optional[int] = None,
                         is_fraud_attempt: bool = False, metadata: Optional[Dict] = None) -> IPReputation:
        """
        Update IP reputation based on activity.
        
        Args:
            ip_address: IP address that performed the activity
            user_id: User ID (if applicable)
            is_fraud_attempt: Whether this was a fraud attempt
            metadata: Additional activity metadata
            
        Returns:
            Updated IPReputation instance
        """
        try:
            with transaction.atomic():
                ip_rep = self.get_ip_reputation(ip_address)
                
                # Update activity counters
                ip_rep.total_requests += 1
                ip_rep.last_seen = timezone.now()
                
                if is_fraud_attempt:
                    ip_rep.fraud_attempts += 1
                    # Increase fraud score
                    ip_rep.fraud_score = min(100, ip_rep.fraud_score + 10)
                
                # Update unique users
                if user_id:
                    from django.contrib.auth.models import User
                    if User.objects.filter(id=user_id).exists():
                        # This is a simplified approach - in production, track unique users properly
                        ip_rep.unique_users = max(ip_rep.unique_users, 1)
                
                # Update metadata
                if metadata:
                    current_metadata = ip_rep.metadata or {}
                    current_metadata.update(metadata)
                    ip_rep.metadata = current_metadata
                
                # Auto-blacklist if score is high
                if ip_rep.fraud_score >= 90 and not ip_rep.is_blacklisted:
                    ip_rep.is_blacklisted = True
                    ip_rep.blacklist_reason = "Auto-blacklisted due to high fraud score"
                    ip_rep.blacklisted_at = timezone.now()
                    
                    # Create alert
                    self._create_ip_blacklist_alert(ip_rep)
                
                ip_rep.save()
                
                # Invalidate cache
                cache_key = f'ip_rep_{ip_address}'
                cache.delete(cache_key)
                
                logger.info(f"Updated IP reputation for {ip_address}: fraud_score={ip_rep.fraud_score}")
                return ip_rep
                
        except Exception as e:
            logger.error(f"Error updating IP activity for {ip_address}: {e}")
            raise
    
    def check_ip_risk(self, ip_address: str) -> Dict[str, Any]:
        """
        Check IP risk level and return comprehensive risk assessment.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            Risk assessment dictionary
        """
        try:
            ip_rep = self.get_ip_reputation(ip_address)
            
            risk_assessment = {
                'ip_address': ip_address,
                'fraud_score': ip_rep.fraud_score,
                'spam_score': ip_rep.spam_score,
                'malware_score': ip_rep.malware_score,
                'is_blacklisted': ip_rep.is_blacklisted,
                'risk_level': self._assess_risk_level(ip_rep.fraud_score),
                'total_requests': ip_rep.total_requests,
                'fraud_attempts': ip_rep.fraud_attempts,
                'unique_users': ip_rep.unique_users,
                'last_seen': ip_rep.last_seen.isoformat(),
                'recommendations': self._get_ip_recommendations(ip_rep),
            }
            
            # Add geolocation data if available
            if ip_rep.country:
                risk_assessment['location'] = {
                    'country': ip_rep.country,
                    'region': ip_rep.region,
                    'city': ip_rep.city,
                }
            
            # Add threat indicators
            if ip_rep.is_vpn or ip_rep.is_proxy or ip_rep.is_tor:
                risk_assessment['threat_indicators'] = {
                    'is_vpn': ip_rep.is_vpn,
                    'is_proxy': ip_rep.is_proxy,
                    'is_tor': ip_rep.is_tor,
                }
            
            return risk_assessment
            
        except Exception as e:
            logger.error(f"Error checking IP risk for {ip_address}: {e}")
            return {
                'ip_address': ip_address,
                'error': str(e),
                'risk_level': 'unknown',
            }
    
    def bulk_check_ip_risk(self, ip_addresses: List[str]) -> Dict[str, Any]:
        """
        Check risk levels for multiple IP addresses.
        
        Args:
            ip_addresses: List of IP addresses to check
            
        Returns:
            Dictionary with risk assessments for all IPs
        """
        results = {}
        
        try:
            for ip_address in ip_addresses:
                try:
                    results[ip_address] = self.check_ip_risk(ip_address)
                except Exception as e:
                    logger.error(f"Error checking risk for {ip_address}: {e}")
                    results[ip_address] = {
                        'ip_address': ip_address,
                        'error': str(e),
                        'risk_level': 'error',
                    }
            
            logger.info(f"Bulk IP risk check completed for {len(ip_addresses)} IPs")
            return results
            
        except Exception as e:
            logger.error(f"Error in bulk IP risk check: {e}")
            return {}
    
    def blacklist_ip(self, ip_address: str, reason: str, blacklisted_by: int,
                     expires_at: Optional[timezone.datetime] = None) -> bool:
        """
        Manually blacklist an IP address.
        
        Args:
            ip_address: IP address to blacklist
            reason: Reason for blacklisting
            blacklisted_by: User ID performing the action
            expires_at: Optional expiration date
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                ip_rep = self.get_ip_reputation(ip_address)
                
                ip_rep.is_blacklisted = True
                ip_rep.blacklist_reason = reason
                ip_rep.blacklisted_by_id = blacklisted_by
                ip_rep.blacklisted_at = timezone.now()
                ip_rep.expires_at = expires_at
                ip_rep.save()
                
                # Create alert
                self._create_ip_blacklist_alert(ip_rep)
                
                # Invalidate cache
                cache_key = f'ip_rep_{ip_address}'
                cache.delete(cache_key)
                
                logger.info(f"Blacklisted IP {ip_address} by user {blacklisted_by}: {reason}")
                return True
                
        except Exception as e:
            logger.error(f"Error blacklisting IP {ip_address}: {e}")
            return False
    
    def whitelist_ip(self, ip_address: str, reason: str, whitelisted_by: int,
                    expires_at: Optional[timezone.datetime] = None) -> bool:
        """
        Remove IP from blacklist and optionally whitelist.
        
        Args:
            ip_address: IP address to whitelist
            reason: Reason for whitelisting
            whitelisted_by: User ID performing the action
            expires_at: Optional expiration date
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                ip_rep = self.get_ip_reputation(ip_address)
                
                if ip_rep.is_blacklisted:
                    ip_rep.is_blacklisted = False
                    ip_rep.blacklist_reason = None
                    ip_rep.blacklisted_by = None
                    ip_rep.blacklisted_at = None
                    ip_rep.expires_at = expires_at
                    ip_rep.fraud_score = max(0, ip_rep.fraud_score - 50)  # Reduce score
                    ip_rep.save()
                    
                    # Invalidate cache
                    cache_key = f'ip_rep_{ip_address}'
                    cache.delete(cache_key)
                    
                    logger.info(f"Whitelisted IP {ip_address} by user {whitelisted_by}: {reason}")
                    return True
                else:
                    logger.warning(f"IP {ip_address} was not blacklisted")
                    return False
                    
        except Exception as e:
            logger.error(f"Error whitelisting IP {ip_address}: {e}")
            return False
    
    def get_high_risk_ips(self, min_score: int = 70, limit: int = 100) -> List[Dict]:
        """
        Get high-risk IP addresses.
        
        Args:
            min_score: Minimum fraud score
            limit: Maximum number of results
            
        Returns:
            List of high-risk IP dictionaries
        """
        try:
            high_risk_ips = IPReputation.objects.filter(
                fraud_score__gte=min_score
            ).order_by('-fraud_score')[:limit]
            
            return [
                {
                    'ip_address': ip.ip_address,
                    'fraud_score': ip.fraud_score,
                    'spam_score': ip.spam_score,
                    'malware_score': ip.malware_score,
                    'is_blacklisted': ip.is_blacklisted,
                    'total_requests': ip.total_requests,
                    'fraud_attempts': ip.fraud_attempts,
                    'last_seen': ip.last_seen.isoformat(),
                    'country': ip.country,
                    'blacklist_reason': ip.blacklist_reason,
                }
                for ip in high_risk_ips
            ]
            
        except Exception as e:
            logger.error(f"Error getting high-risk IPs: {e}")
            return []
    
    def get_ip_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get IP reputation statistics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with statistics
        """
        try:
            cutoff = timezone.now() - timedelta(days=days)
            
            stats = {}
            
            # Total unique IPs
            stats['total_unique_ips'] = IPReputation.objects.count()
            
            # Active IPs (seen in last N days)
            stats['active_ips'] = IPReputation.objects.filter(
                last_seen__gte=cutoff
            ).count()
            
            # Blacklisted IPs
            stats['blacklisted_ips'] = IPReputation.objects.filter(
                is_blacklisted=True
            ).count()
            
            # High-risk IPs
            stats['high_risk_ips'] = IPReputation.objects.filter(
                fraud_score__gte=RISK_THRESHOLDS['high']
            ).count()
            
            # Average scores
            avg_scores = IPReputation.objects.aggregate(
                avg_fraud_score=models.Avg('fraud_score'),
                avg_spam_score=models.Avg('spam_score'),
                avg_malware_score=models.Avg('malware_score'),
            )
            
            stats.update(avg_scores)
            
            # Top countries by fraud attempts
            top_countries = IPReputation.objects.filter(
                fraud_attempts__gt=0
            ).values('country').annotate(
                total_fraud=models.Sum('fraud_attempts')
            ).order_by('-total_fraud')[:10]
            
            stats['top_countries'] = list(top_countries)
            
            # Recent activity
            stats['recent_activity'] = IPReputation.objects.filter(
                last_seen__gte=cutoff
            ).aggregate(
                total_requests=models.Sum('total_requests'),
                total_fraud_attempts=models.Sum('fraud_attempts'),
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting IP statistics: {e}")
            return {}
    
    def cleanup_old_ip_data(self, days_to_keep: int = 365) -> Dict[str, int]:
        """
        Clean up old IP reputation data.
        
        Args:
            days_to_keep: Number of days to keep data
            
        Returns:
            Dictionary with cleanup counts
        """
        try:
            with transaction.atomic():
                cutoff = timezone.now() - timedelta(days=days_to_keep)
                
                # Delete IPs with no recent activity and low scores
                old_ips = IPReputation.objects.filter(
                    last_seen__lt=cutoff,
                    fraud_score__lt=20,
                    total_requests__lt=10,
                    is_blacklisted=False
                )
                
                deleted_count = old_ips.count()
                old_ips.delete()
                
                logger.info(f"Cleaned up {deleted_count} old IP records")
                return {'deleted': deleted_count}
                
        except Exception as e:
            logger.error(f"Error cleaning up old IP data: {e}")
            return {'deleted': 0}
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _update_ip_reputation_data(self, ip_rep: IPReputation):
        """Update IP reputation with internal data."""
        try:
            # Update fraud attempt statistics
            fraud_attempts = FraudAttempt.objects.filter(
                evidence_data__icontains=ip_rep.ip_address
            ).count()
            
            if fraud_attempts != ip_rep.fraud_attempts:
                ip_rep.fraud_attempts = fraud_attempts
                ip_rep.fraud_score = min(100, fraud_attempts * 10)
            
        except Exception as e:
            logger.error(f"Error updating IP reputation data for {ip_rep.ip_address}: {e}")
    
    def _check_threat_intelligence(self, ip_rep: IPReputation):
        """Check external threat intelligence sources."""
        try:
            # In production, integrate with real threat intelligence APIs
            # For now, simulate threat intelligence check
            
            threat_data = self._simulate_threat_intelligence_check(ip_rep.ip_address)
            
            if threat_data:
                ip_rep.spam_score = threat_data.get('spam_score', 0)
                ip_rep.malware_score = threat_data.get('malware_score', 0)
                ip_rep.is_vpn = threat_data.get('is_vpn', False)
                ip_rep.is_proxy = threat_data.get('is_proxy', False)
                ip_rep.is_tor = threat_data.get('is_tor', False)
                
                # Update geolocation if available
                if 'country' in threat_data:
                    ip_rep.country = threat_data['country']
                    ip_rep.region = threat_data.get('region')
                    ip_rep.city = threat_data.get('city')
                    ip_rep.latitude = threat_data.get('latitude')
                    ip_rep.longitude = threat_data.get('longitude')
                
                ip_rep.last_threat_check = timezone.now()
                ip_rep.save()
            
        except Exception as e:
            logger.error(f"Error checking threat intelligence for {ip_rep.ip_address}: {e}")
    
    def _simulate_threat_intelligence_check(self, ip_address: str) -> Optional[Dict]:
        """Simulate threat intelligence check (replace with real API calls)."""
        # This is a placeholder - in production, integrate with real threat intelligence APIs
        # like VirusTotal, AbuseIPDB, IPQualityScore, etc.
        
        import random
        
        # Simulate some threat data
        if random.random() < 0.1:  # 10% chance of finding threat data
            return {
                'spam_score': random.randint(0, 100),
                'malware_score': random.randint(0, 100),
                'is_vpn': random.random() < 0.05,
                'is_proxy': random.random() < 0.03,
                'is_tor': random.random() < 0.01,
                'country': 'US',
                'region': 'CA',
                'city': 'San Francisco',
                'latitude': 37.7749,
                'longitude': -122.4194,
            }
        
        return None
    
    def _assess_risk_level(self, fraud_score: int) -> str:
        """Assess risk level based on fraud score."""
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
    
    def _get_ip_recommendations(self, ip_rep: IPReputation) -> List[str]:
        """Get recommendations for IP handling."""
        recommendations = []
        
        if ip_rep.is_blacklisted:
            recommendations.append("IP is blacklisted - block all requests")
        elif ip_rep.fraud_score >= 70:
            recommendations.append("High fraud score - require additional verification")
        elif ip_rep.fraud_score >= 50:
            recommendations.append("Medium fraud score - monitor closely")
        elif ip_rep.is_vpn or ip_rep.is_proxy:
            recommendations.append("VPN/Proxy detected - verify user identity")
        
        if ip_rep.fraud_attempts > 10:
            recommendations.append("Multiple fraud attempts - consider blacklisting")
        
        if not recommendations:
            recommendations.append("Low risk - normal processing")
        
        return recommendations
    
    def _create_ip_blacklist_alert(self, ip_rep: IPReputation):
        """Create alert for IP blacklisting."""
        try:
            FraudAlert.objects.create(
                alert_type=FraudAlertType.SYSTEM_ANOMALY,
                priority=AlertPriority.HIGH,
                title=f"IP Blacklisted: {ip_rep.ip_address}",
                description=f"IP {ip_rep.ip_address} added to blacklist: {ip_rep.blacklist_reason}",
                data={
                    'ip_address': ip_rep.ip_address,
                    'fraud_score': ip_rep.fraud_score,
                    'blacklist_reason': ip_rep.blacklist_reason,
                    'total_requests': ip_rep.total_requests,
                    'fraud_attempts': ip_rep.fraud_attempts,
                }
            )
        except Exception as e:
            logger.error(f"Error creating IP blacklist alert: {e}")
