"""
Enhanced Threat Intelligence Service with comprehensive security model integration
Author: System Security Team
Version: 2.0.0

Advanced threat intelligence capabilities with multiple data sources,
real-time analysis, and automated threat response integration.
"""

import logging
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction, models
from django.conf import settings

from ..models import ThreatIntelligence
from ..constants import ThreatIntelligence as ThreatIntelConstants, CacheSettings
from ..choices import ThreatCategory, ThreatIntelligenceSource
from ..utils.cache_manager import CacheManager, handle_gracefully

logger = logging.getLogger(__name__)


class ThreatIntelService:
    """
    Advanced Threat Intelligence Service with defensive coding patterns
    Integrates with existing IPReputation logic and provides comprehensive threat analysis
    """
    
    def __init__(self):
        """Initialize Threat Intelligence Service"""
        try:
            self.cache_prefix = "threat_intel"
            self.default_confidence = 0.5
            self.batch_size = 100
            
            # Load feed configurations
            self.feed_configs = self._load_feed_configs()
            
            logger.info("ThreatIntelService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ThreatIntelService: {e}")
            self.feed_configs = {}
    
    def _load_feed_configs(self) -> Dict[str, Any]:
        """Load threat feed configurations with defensive coding"""
        try:
            # Get feed configurations from settings
            configs = getattr(settings, 'THREAT_FEED_CONFIGS', {})
            
            # Default configurations if none provided
            default_configs = {
                'abuse_ch': {
                    'enabled': True,
                    'update_interval': 3600,  # 1 hour
                    'timeout': 30,
                    'retry_attempts': 3
                },
                'phishtank': {
                    'enabled': True,
                    'update_interval': 3600,
                    'timeout': 30,
                    'retry_attempts': 3
                },
                'internal': {
                    'enabled': True,
                    'update_interval': 300,  # 5 minutes
                    'timeout': 10,
                    'retry_attempts': 2
                }
            }
            
            # Merge with user configs
            return {**default_configs, **configs}
            
        except Exception as e:
            logger.error(f"Error loading feed configs: {e}")
            return {}
    
    @handle_gracefully(default_return=[], log_errors=True)
    def check_ip_reputation(self, ip_address: str, include_details: bool = True) -> Dict[str, Any]:
        """
        Check IP reputation integrating with existing IPReputation logic
        This method bridges the gap between old IPReputation and new ThreatIntelligence
        """
        try:
            cache_key = CacheManager.generate_key(self.cache_prefix, "ip_reputation", ip_address)
            
            # Try cache first
            cached_result = CacheManager.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for IP reputation: {ip_address}")
                return cached_result
            
            # Check existing IPReputation if available
            ip_reputation_result = self._check_existing_ip_reputation(ip_address)
            
            # Check new ThreatIntelligence
            threat_intel_result = self._check_threat_intelligence_for_ip(ip_address)
            
            # Merge results
            merged_result = self._merge_reputation_results(
                ip_reputation_result, 
                threat_intel_result,
                include_details
            )
            
            # Cache the result
            cache_ttl = CacheSettings.get_cache_ttl('ip_reputation')
            CacheManager.set(cache_key, merged_result, cache_ttl)
            
            return merged_result
            
        except Exception as e:
            logger.error(f"IP reputation check failed for {ip_address}: {e}")
            return {
                'ip_address': ip_address,
                'risk_score': 0.0,
                'is_blacklisted': False,
                'confidence': 0.0,
                'sources': [],
                'error': str(e)
            }
    
    def _check_existing_ip_reputation(self, ip_address: str) -> Dict[str, Any]:
        """Check existing IPReputation model if available"""
        try:
            # Try to import IPReputation from fraud_detection module
            try:
                from api.fraud_detection.models import IPReputation
                
                reputation = IPReputation.objects.filter(ip_address=ip_address).first()
                if reputation:
                    return {
                        'ip_address': ip_address,
                        'fraud_score': getattr(reputation, 'fraud_score', 0),
                        'is_blacklisted': getattr(reputation, 'is_blacklisted', False),
                        'country': getattr(reputation, 'country', None),
                        'last_updated': getattr(reputation, 'updated_at', None),
                        'source': 'ip_reputation',
                        'confidence': 0.8  # High confidence for existing data
                    }
                    
            except ImportError:
                logger.debug("IPReputation model not available")
            
            return {
                'ip_address': ip_address,
                'fraud_score': 0,
                'is_blacklisted': False,
                'source': 'ip_reputation',
                'confidence': 0.0
            }
            
        except Exception as e:
            logger.error(f"Error checking existing IP reputation: {e}")
            return {
                'ip_address': ip_address,
                'fraud_score': 0,
                'is_blacklisted': False,
                'source': 'ip_reputation',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _check_threat_intelligence_for_ip(self, ip_address: str) -> Dict[str, Any]:
        """Check threat intelligence for IP address"""
        try:
            # Query ThreatIntelligence model
            threats = ThreatIntelligence.check_ioc(ip_address, 'ip_address')
            
            if not threats:
                return {
                    'ip_address': ip_address,
                    'threat_count': 0,
                    'max_threat_score': 0.0,
                    'threat_types': [],
                    'sources': [],
                    'confidence': 0.0
                }
            
            # Aggregate threat data
            max_threat_score = max(float(threat.threat_score) for threat in threats)
            threat_types = list(set(threat.threat_type for threat in threats))
            sources = list(set(threat.source for threat in threats))
            avg_confidence = sum(float(threat.confidence_score) for threat in threats) / len(threats)
            
            return {
                'ip_address': ip_address,
                'threat_count': len(threats),
                'max_threat_score': max_threat_score,
                'threat_types': threat_types,
                'sources': sources,
                'confidence': avg_confidence,
                'threat_details': [
                    {
                        'threat_type': threat.threat_type,
                        'threat_score': float(threat.threat_score),
                        'confidence': float(threat.confidence_score),
                        'source': threat.source,
                        'first_seen': threat.first_seen.isoformat(),
                        'last_seen': threat.last_seen.isoformat(),
                        'description': threat.description
                    }
                    for threat in threats[:5]  # Limit to top 5
                ]
            }
            
        except Exception as e:
            logger.error(f"Error checking threat intelligence for IP {ip_address}: {e}")
            return {
                'ip_address': ip_address,
                'threat_count': 0,
                'max_threat_score': 0.0,
                'threat_types': [],
                'sources': [],
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _merge_reputation_results(self, ip_rep_result: Dict, threat_result: Dict, include_details: bool) -> Dict[str, Any]:
        """Merge IP reputation and threat intelligence results"""
        try:
            # Base result
            merged = {
                'ip_address': ip_rep_result.get('ip_address', ''),
                'checked_at': timezone.now().isoformat(),
                'sources': []
            }
            
            # Calculate combined risk score
            ip_score = float(ip_rep_result.get('fraud_score', 0))
            threat_score = float(threat_result.get('max_threat_score', 0))
            
            # Weight the scores (IP reputation gets higher weight)
            combined_score = (ip_score * 0.6) + (threat_score * 0.4)
            
            merged['risk_score'] = min(combined_score, 1.0)
            merged['is_blacklisted'] = (
                ip_rep_result.get('is_blacklisted', False) or 
                threat_score >= 0.8
            )
            
            # Combine confidence levels
            ip_confidence = float(ip_rep_result.get('confidence', 0))
            threat_confidence = float(threat_result.get('confidence', 0))
            merged['confidence'] = max(ip_confidence, threat_confidence)
            
            # Add sources
            if ip_rep_result.get('confidence', 0) > 0:
                merged['sources'].append('ip_reputation')
            if threat_result.get('threat_count', 0) > 0:
                merged['sources'].extend(threat_result.get('sources', []))
            
            # Add detailed information if requested
            if include_details:
                merged['ip_reputation'] = {
                    'fraud_score': ip_score,
                    'is_blacklisted': ip_rep_result.get('is_blacklisted', False),
                    'country': ip_rep_result.get('country'),
                    'last_updated': ip_rep_result.get('last_updated').isoformat() if ip_rep_result.get('last_updated') else None
                }
                
                merged['threat_intelligence'] = {
                    'threat_count': threat_result.get('threat_count', 0),
                    'max_threat_score': threat_score,
                    'threat_types': threat_result.get('threat_types', []),
                    'threat_details': threat_result.get('threat_details', [])
                }
            
            return merged
            
        except Exception as e:
            logger.error(f"Error merging reputation results: {e}")
            return {
                'ip_address': ip_rep_result.get('ip_address', ''),
                'risk_score': 0.0,
                'is_blacklisted': False,
                'confidence': 0.0,
                'sources': [],
                'error': str(e)
            }
    
    @handle_gracefully(default_return=False, log_errors=True)
    def add_threat_ioc(self, ioc_type: str, ioc_value: str, threat_type: str, 
                      source: str = 'internal', confidence: float = 0.5,
                      threat_score: float = 0.5, description: str = "",
                      metadata: Dict = None) -> bool:
        """
        Add new IOC (Indicator of Compromise) to threat intelligence
        """
        try:
            with transaction.atomic():
                # Check if IOC already exists
                existing = ThreatIntelligence.objects.filter(
                    ioc_type=ioc_type,
                    ioc_value=ioc_value,
                    source=source
                ).first()
                
                if existing:
                    # Update existing record
                    existing.threat_score = max(float(existing.threat_score), threat_score)
                    existing.confidence_score = max(float(existing.confidence_score), confidence)
                    existing.last_seen = timezone.now()
                    existing.description = description or existing.description
                    if metadata:
                        existing.metadata.update(metadata)
                    existing.save()
                    
                    logger.info(f"Updated existing IOC: {ioc_type}:{ioc_value}")
                    return True
                
                # Create new IOC
                threat_intel = ThreatIntelligence(
                    ioc_type=ioc_type,
                    ioc_value=ioc_value,
                    threat_type=threat_type,
                    source=source,
                    confidence_score=min(max(float(confidence), 0.0), 1.0),
                    threat_score=min(max(float(threat_score), 0.0), 1.0),
                    description=description,
                    metadata=metadata or {},
                    first_seen=timezone.now(),
                    last_seen=timezone.now()
                )
                
                threat_intel.save()
                
                # Clear related cache
                self._clear_ioc_cache(ioc_type, ioc_value)
                
                logger.info(f"Added new IOC: {ioc_type}:{ioc_value} from {source}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add IOC {ioc_type}:{ioc_value}: {e}")
            return False
    
    @handle_gracefully(default_return=[], log_errors=True)
    def get_active_threats(self, threat_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get active threats with defensive coding"""
        try:
            cache_key = CacheManager.generate_key(self.cache_prefix, "active_threats", threat_type or "all", limit)
            
            # Try cache first
            cached_result = CacheManager.get(cache_key)
            if cached_result:
                return cached_result
            
            threats = ThreatIntelligence.get_active_threats(threat_type)
            
            # Convert to dict format
            result = []
            for threat in threats[:limit]:
                try:
                    result.append({
                        'id': threat.id,
                        'ioc_type': threat.ioc_type,
                        'ioc_value': threat.ioc_value,
                        'threat_type': threat.threat_type,
                        'threat_score': float(threat.threat_score),
                        'confidence_score': float(threat.confidence_score),
                        'source': threat.source,
                        'first_seen': threat.first_seen.isoformat(),
                        'last_seen': threat.last_seen.isoformat(),
                        'expires_at': threat.expires_at.isoformat(),
                        'risk_level': threat.get_risk_level(),
                        'description': threat.description,
                        'tags': threat.tags,
                        'is_expired': threat.is_expired()
                    })
                except Exception as e:
                    logger.warning(f"Error processing threat {threat.id}: {e}")
                    continue
            
            # Cache the result
            cache_ttl = CacheSettings.get_cache_ttl('threat_intel')
            CacheManager.set(cache_key, result, cache_ttl)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get active threats: {e}")
            return []
    
    @handle_gracefully(default_return=False, log_errors=True)
    def update_threat_feeds(self, feed_name: str = None) -> bool:
        """Update threat feeds from external sources"""
        try:
            if feed_name:
                return self._update_single_feed(feed_name)
            else:
                return self._update_all_feeds()
                
        except Exception as e:
            logger.error(f"Failed to update threat feeds: {e}")
            return False
    
    def _update_all_feeds(self) -> bool:
        """Update all configured threat feeds"""
        success = True
        
        for feed_name in self.feed_configs.keys():
            try:
                feed_success = self._update_single_feed(feed_name)
                if not feed_success:
                    success = False
                    
            except Exception as e:
                logger.error(f"Error updating feed {feed_name}: {e}")
                success = False
        
        return success
    
    def _update_single_feed(self, feed_name: str) -> bool:
        """Update a single threat feed"""
        try:
            config = self.feed_configs.get(feed_name, {})
            
            if not config.get('enabled', False):
                logger.debug(f"Feed {feed_name} is disabled")
                return True
            
            # Check if update is needed
            last_update_key = f"feed_last_update:{feed_name}"
            last_update = CacheManager.get(last_update_key, 0)
            update_interval = config.get('update_interval', 3600)
            
            if timezone.now().timestamp() - last_update < update_interval:
                logger.debug(f"Feed {feed_name} update not needed yet")
                return True
            
            logger.info(f"Updating threat feed: {feed_name}")
            
            # Mock feed update - in real implementation, this would fetch from external sources
            if feed_name == 'abuse_ch':
                success = self._update_abuse_ch_feed(config)
            elif feed_name == 'phishtank':
                success = self._update_phishtank_feed(config)
            elif feed_name == 'internal':
                success = self._update_internal_feed(config)
            else:
                logger.warning(f"Unknown feed: {feed_name}")
                success = False
            
            if success:
                # Update last update timestamp
                CacheManager.set(last_update_key, timezone.now().timestamp(), 86400)
                logger.info(f"Successfully updated feed: {feed_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating feed {feed_name}: {e}")
            return False
    
    def _update_abuse_ch_feed(self, config: Dict) -> bool:
        """Update abuse.ch feed (mock implementation)"""
        try:
            # Mock data - in real implementation, fetch from abuse.ch API
            mock_iocs = [
                {
                    'ioc_type': 'ip_address',
                    'ioc_value': '192.0.2.1',
                    'threat_type': 'malware',
                    'threat_score': 0.9,
                    'confidence': 0.8,
                    'description': 'Known malware C2 server'
                },
                {
                    'ioc_type': 'domain',
                    'ioc_value': 'malicious-domain.example.com',
                    'threat_type': 'phishing',
                    'threat_score': 0.8,
                    'confidence': 0.7,
                    'description': 'Known phishing domain'
                }
            ]
            
            success_count = 0
            for ioc in mock_iocs:
                if self.add_threat_ioc(**ioc):
                    success_count += 1
            
            logger.info(f"Added {success_count}/{len(mock_iocs)} IOCs from abuse.ch feed")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error updating abuse.ch feed: {e}")
            return False
    
    def _update_phishtank_feed(self, config: Dict) -> bool:
        """Update PhishTank feed (mock implementation)"""
        try:
            # Mock data - in real implementation, fetch from PhishTank API
            mock_iocs = [
                {
                    'ioc_type': 'url',
                    'ioc_value': 'http://phishing-site.example.com/login',
                    'threat_type': 'phishing',
                    'threat_score': 0.7,
                    'confidence': 0.6,
                    'description': 'Phishing site targeting financial services'
                }
            ]
            
            success_count = 0
            for ioc in mock_iocs:
                if self.add_threat_ioc(**ioc):
                    success_count += 1
            
            logger.info(f"Added {success_count}/{len(mock_iocs)} IOCs from PhishTank feed")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error updating PhishTank feed: {e}")
            return False
    
    def _update_internal_feed(self, config: Dict) -> bool:
        """Update internal threat feed"""
        try:
            # This would process internal security logs and generate IOCs
            # Mock implementation for now
            logger.debug("Internal feed update (mock)")
            return True
            
        except Exception as e:
            logger.error(f"Error updating internal feed: {e}")
            return False
    
    def _clear_ioc_cache(self, ioc_type: str, ioc_value: str):
        """Clear cache for specific IOC"""
        try:
            cache_keys = [
                CacheManager.generate_key(self.cache_prefix, "ip_reputation", ioc_value),
                CacheManager.generate_key(self.cache_prefix, "ioc_check", ioc_type, ioc_value),
            ]
            
            for key in cache_keys:
                CacheManager.delete(key)
                
        except Exception as e:
            logger.debug(f"Error clearing IOC cache: {e}")
    
    @handle_gracefully(default_return={}, log_errors=True)
    def get_threat_statistics(self) -> Dict[str, Any]:
        """Get threat intelligence statistics"""
        try:
            cache_key = CacheManager.generate_key(self.cache_prefix, "statistics")
            
            # Try cache first
            cached_stats = CacheManager.get(cache_key)
            if cached_stats:
                return cached_stats
            
            # Calculate statistics
            total_iocs = ThreatIntelligence.objects.filter(is_active=True).count()
            expired_iocs = ThreatIntelligence.objects.filter(
                is_active=True,
                expires_at__lt=timezone.now()
            ).count()
            
            # Group by type
            iocs_by_type = {}
            for ioc_type, _ in ThreatIntelligence.IOC_TYPES:
                count = ThreatIntelligence.objects.filter(
                    ioc_type=ioc_type,
                    is_active=True
                ).count()
                iocs_by_type[ioc_type] = count
            
            # Group by threat type
            iocs_by_threat_type = {}
            for threat_type, _ in ThreatIntelligence.THREAT_TYPES:
                count = ThreatIntelligence.objects.filter(
                    threat_type=threat_type,
                    is_active=True
                ).count()
                iocs_by_threat_type[threat_type] = count
            
            # High confidence threats
            high_confidence_count = ThreatIntelligence.objects.filter(
                is_active=True,
                confidence_score__gte=0.8
            ).count()
            
            # High score threats
            high_score_count = ThreatIntelligence.objects.filter(
                is_active=True,
                threat_score__gte=0.8
            ).count()
            
            stats = {
                'total_iocs': total_iocs,
                'active_iocs': total_iocs - expired_iocs,
                'expired_iocs': expired_iocs,
                'high_confidence_count': high_confidence_count,
                'high_score_count': high_score_count,
                'iocs_by_type': iocs_by_type,
                'iocs_by_threat_type': iocs_by_threat_type,
                'last_updated': timezone.now().isoformat(),
                'feed_configs': list(self.feed_configs.keys())
            }
            
            # Cache the statistics
            cache_ttl = CacheSettings.get_cache_ttl('threat_intel')
            CacheManager.set(cache_key, stats, cache_ttl)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get threat statistics: {e}")
            return {
                'error': str(e),
                'last_updated': timezone.now().isoformat()
            }
    
    @classmethod
    def get_service_instance(cls) -> 'ThreatIntelService':
        """Get singleton instance of the service"""
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance