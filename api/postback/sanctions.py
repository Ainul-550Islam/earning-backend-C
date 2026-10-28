"""
sanctions.py – Sanctions management for postback module.

Provides comprehensive sanctions functionality including:
- Fraud detection and prevention
- IP and user blocking
- Network sanctions
- Compliance enforcement
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum

from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from .models import PostbackLog, NetworkPostbackConfig
from .exceptions import PostbackException

logger = logging.getLogger(__name__)
User = get_user_model()


class SanctionType(Enum):
    """Sanction type enumeration."""
    IP_BLOCK = "ip_block"
    USER_SUSPEND = "user_suspend"
    USER_BAN = "user_ban"
    NETWORK_SUSPEND = "network_suspend"
    NETWORK_BAN = "network_ban"
    RATE_LIMIT = "rate_limit"
    MANUAL_REVIEW = "manual_review"


class SanctionSeverity(Enum):
    """Sanction severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SanctionStatus(Enum):
    """Sanction status enumeration."""
    ACTIVE = "active"
    EXPIRED = "expired"
    LIFTED = "lifted"
    PENDING = "pending"


class Sanction:
    """
    Sanction data structure.
    
    Represents a sanction applied to a user, IP, or network.
    """
    
    def __init__(self, sanction_type: SanctionType, target: str, reason: str, 
                 severity: SanctionSeverity, duration: timedelta = None, 
                 metadata: Dict[str, Any] = None):
        self.sanction_type = sanction_type
        self.target = target
        self.reason = reason
        self.severity = severity
        self.duration = duration
        self.metadata = metadata or {}
        self.created_at = timezone.now()
        self.expires_at = self.created_at + duration if duration else None
        self.status = SanctionStatus.ACTIVE
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique sanction ID."""
        import uuid
        return f"sanction_{uuid.uuid4().hex[:12]}"
    
    def is_expired(self) -> bool:
        """Check if sanction is expired."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at
    
    def is_active(self) -> bool:
        """Check if sanction is active."""
        return self.status == SanctionStatus.ACTIVE and not self.is_expired()
    
    def lift(self):
        """Lift the sanction."""
        self.status = SanctionStatus.LIFTED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'sanction_type': self.sanction_type.value,
            'target': self.target,
            'reason': self.reason,
            'severity': self.severity.value,
            'duration': str(self.duration) if self.duration else None,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'status': self.status.value,
            'metadata': self.metadata,
        }


class SanctionRule:
    """
    Sanction rule definition.
    
    Defines conditions for automatic sanction application.
    """
    
    def __init__(self, name: str, sanction_type: SanctionType, severity: SanctionSeverity,
                 conditions: Dict[str, Any], duration: timedelta = None, enabled: bool = True):
        self.name = name
        self.sanction_type = sanction_type
        self.severity = severity
        self.conditions = conditions
        self.duration = duration
        self.enabled = enabled
        self.trigger_count = 0
        self.last_triggered = None
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate if sanction should be applied based on context.
        
        Args:
            context: Evaluation context
            
        Returns:
            True if sanction should be applied
        """
        if not self.enabled:
            return False
        
        # Check conditions
        for condition, value in self.conditions.items():
            if condition == 'max_postbacks_per_hour':
                postback_count = context.get('postback_count', 0)
                if postback_count > value:
                    return True
            
            elif condition == 'max_rejection_rate':
                rejection_rate = context.get('rejection_rate', 0)
                if rejection_rate > value:
                    return True
            
            elif condition == 'suspicious_ip_ranges':
                ip_address = context.get('ip_address')
                if ip_address and self._ip_in_ranges(ip_address, value):
                    return True
            
            elif condition == 'duplicate_lead_threshold':
                duplicate_count = context.get('duplicate_count', 0)
                if duplicate_count > value:
                    return True
        
        return False
    
    def _ip_in_ranges(self, ip_address: str, ip_ranges: List[str]) -> bool:
        """Check if IP is in suspicious ranges."""
        import ipaddress
        
        try:
            ip = ipaddress.ip_address(ip_address)
            
            for ip_range in ip_ranges:
                if '/' in ip_range:
                    # CIDR range
                    network = ipaddress.ip_network(ip_range, strict=False)
                    if ip in network:
                        return True
                else:
                    # Exact match
                    if ip_address == ip_range:
                        return True
        
        except ValueError:
            pass
        
        return False
    
    def trigger(self) -> Sanction:
        """Trigger sanction based on rule."""
        self.trigger_count += 1
        self.last_triggered = timezone.now()
        
        return Sanction(
            sanction_type=self.sanction_type,
            target="auto_generated",
            reason=f"Auto-sanction by rule: {self.name}",
            severity=self.severity,
            duration=self.duration,
            metadata={
                'rule_name': self.name,
                'trigger_count': self.trigger_count,
                'auto_generated': True,
            }
        )


class FraudDetector:
    """
    Fraud detection system.
    
    Analyzes postback patterns to detect fraudulent activity.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.detection_rules = self._setup_default_rules()
    
    def _setup_default_rules(self) -> List[SanctionRule]:
        """Setup default fraud detection rules."""
        rules = [
            SanctionRule(
                name="high_postback_volume",
                sanction_type=SanctionType.RATE_LIMIT,
                severity=SanctionSeverity.MEDIUM,
                conditions={'max_postbacks_per_hour': 1000},
                duration=timedelta(hours=1),
            ),
            SanctionRule(
                name="high_rejection_rate",
                sanction_type=SanctionType.MANUAL_REVIEW,
                severity=SanctionSeverity.HIGH,
                conditions={'max_rejection_rate': 0.8},
                duration=timedelta(days=7),
            ),
            SanctionRule(
                name="suspicious_ip_activity",
                sanction_type=SanctionType.IP_BLOCK,
                severity=SanctionSeverity.HIGH,
                conditions={'suspicious_ip_ranges': ['192.168.1.0/24', '10.0.0.0/8']},
                duration=timedelta(days=30),
            ),
            SanctionRule(
                name="duplicate_lead_spam",
                sanction_type=SanctionType.USER_SUSPEND,
                severity=SanctionSeverity.MEDIUM,
                conditions={'duplicate_lead_threshold': 50},
                duration=timedelta(days=3),
            ),
        ]
        
        return rules
    
    def analyze_postback(self, postback_data: Dict[str, Any], context: Dict[str, Any] = None) -> List[Sanction]:
        """
        Analyze postback for fraud indicators.
        
        Args:
            postback_data: Postback data
            context: Additional context
            
        Returns:
            List of triggered sanctions
        """
        sanctions = []
        context = context or {}
        
        # Gather analysis context
        analysis_context = self._gather_context(postback_data, context)
        
        # Evaluate rules
        for rule in self.detection_rules:
            if rule.evaluate(analysis_context):
                sanction = rule.trigger()
                sanctions.append(sanction)
                self.logger.warning(f"Fraud detected: {rule.name} - {sanction.reason}")
        
        return sanctions
    
    def _gather_context(self, postback_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Gather context for fraud analysis."""
        analysis_context = {
            'ip_address': postback_data.get('source_ip'),
            'user_agent': postback_data.get('user_agent'),
            'network_key': postback_data.get('network_key'),
            'lead_id': postback_data.get('lead_id'),
            'offer_id': postback_data.get('offer_id'),
            'payout': postback_data.get('payout'),
        }
        
        # Add additional context
        analysis_context.update(context)
        
        # Calculate metrics
        analysis_context.update(self._calculate_metrics(analysis_context))
        
        return analysis_context
    
    def _calculate_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate fraud detection metrics."""
        metrics = {}
        
        # Postback count in last hour
        ip_address = context.get('ip_address')
        if ip_address:
            metrics['postback_count'] = self._get_postback_count_by_ip(ip_address, hours=1)
        
        # Rejection rate for network
        network_key = context.get('network_key')
        if network_key:
            metrics['rejection_rate'] = self._get_rejection_rate_by_network(network_key, hours=24)
        
        # Duplicate lead count
        lead_id = context.get('lead_id')
        if lead_id:
            metrics['duplicate_count'] = self._get_duplicate_lead_count(lead_id)
        
        return metrics
    
    def _get_postback_count_by_ip(self, ip_address: str, hours: int) -> int:
        """Get postback count by IP address."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        count = PostbackLog.objects.filter(
            source_ip=ip_address,
            received_at__gte=cutoff_time
        ).count()
        
        return count
    
    def _get_rejection_rate_by_network(self, network_key: str, hours: int) -> float:
        """Get rejection rate by network."""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        postbacks = PostbackLog.objects.filter(
            network__network_key=network_key,
            received_at__gte=cutoff_time
        )
        
        total_count = postbacks.count()
        if total_count == 0:
            return 0.0
        
        rejected_count = postbacks.filter(status='rejected').count()
        return (rejected_count / total_count) * 100
    
    def _get_duplicate_lead_count(self, lead_id: str) -> int:
        """Get duplicate lead count."""
        return PostbackLog.objects.filter(lead_id=lead_id).count() - 1
    
    def add_rule(self, rule: SanctionRule):
        """Add custom fraud detection rule."""
        self.detection_rules.append(rule)
        self.logger.info(f"Added fraud detection rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove fraud detection rule."""
        self.detection_rules = [rule for rule in self.detection_rules if rule.name != rule_name]
        self.logger.info(f"Removed fraud detection rule: {rule_name}")
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """Get rule statistics."""
        return {
            'total_rules': len(self.detection_rules),
            'enabled_rules': len([rule for rule in self.detection_rules if rule.enabled]),
            'rules': [
                {
                    'name': rule.name,
                    'sanction_type': rule.sanction_type.value,
                    'severity': rule.severity.value,
                    'enabled': rule.enabled,
                    'trigger_count': rule.trigger_count,
                    'last_triggered': rule.last_triggered.isoformat() if rule.last_triggered else None,
                }
                for rule in self.detection_rules
            ],
        }


class SanctionManager:
    """
    Manager for sanctions.
    
    Handles sanction application, enforcement, and lifecycle management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.active_sanctions: Dict[str, Sanction] = {}
        self.sanction_history: List[Sanction] = []
        self.fraud_detector = FraudDetector()
        self._load_active_sanctions()
    
    def _load_active_sanctions(self):
        """Load active sanctions from storage."""
        # This would load from database or cache
        # For now, initialize empty
        pass
    
    def apply_sanction(self, sanction: Sanction) -> bool:
        """
        Apply a sanction.
        
        Args:
            sanction: Sanction to apply
            
        Returns:
            True if applied successfully
        """
        try:
            # Check if sanction already exists for target
            existing_key = f"{sanction.sanction_type.value}:{sanction.target}"
            if existing_key in self.active_sanctions:
                existing = self.active_sanctions[existing_key]
                if existing.is_active():
                    self.logger.warning(f"Sanction already active for {existing_key}")
                    return False
            
            # Apply sanction
            self.active_sanctions[existing_key] = sanction
            self.sanction_history.append(sanction)
            
            # Enforce sanction
            self._enforce_sanction(sanction)
            
            # Cache sanction
            self._cache_sanction(sanction)
            
            self.logger.info(f"Sanction applied: {sanction.id} - {sanction.reason}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error applying sanction: {str(e)}")
            return False
    
    def lift_sanction(self, sanction_id: str) -> bool:
        """
        Lift a sanction.
        
        Args:
            sanction_id: Sanction ID
            
        Returns:
            True if lifted successfully
        """
        try:
            # Find sanction
            sanction = None
            for key, active_sanction in self.active_sanctions.items():
                if active_sanction.id == sanction_id:
                    sanction = active_sanction
                    break
            
            if not sanction:
                self.logger.warning(f"Sanction not found: {sanction_id}")
                return False
            
            # Lift sanction
            sanction.lift()
            
            # Remove from active sanctions
            del self.active_sanctions[f"{sanction.sanction_type.value}:{sanction.target}"]
            
            # Update cache
            self._update_sanction_cache(sanction)
            
            self.logger.info(f"Sanction lifted: {sanction_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error lifting sanction: {str(e)}")
            return False
    
    def check_sanctions(self, sanction_type: SanctionType = None, target: str = None) -> List[Sanction]:
        """
        Check active sanctions.
        
        Args:
            sanction_type: Filter by sanction type
            target: Filter by target
            
        Returns:
            List of matching sanctions
        """
        sanctions = []
        
        for sanction in self.active_sanctions.values():
            if not sanction.is_active():
                continue
            
            if sanction_type and sanction.sanction_type != sanction_type:
                continue
            
            if target and sanction.target != target:
                continue
            
            sanctions.append(sanction)
        
        return sanctions
    
    def is_sanctioned(self, sanction_type: SanctionType, target: str) -> bool:
        """
        Check if target is sanctioned.
        
        Args:
            sanction_type: Type of sanction
            target: Target to check
            
        Returns:
            True if sanctioned
        """
        sanction_key = f"{sanction_type.value}:{target}"
        sanction = self.active_sanctions.get(sanction_key)
        
        return sanction is not None and sanction.is_active()
    
    def process_postback(self, postback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process postback through sanction system.
        
        Args:
            postback_data: Postback data
            
        Returns:
            Processing result
        """
        result = {
            'allowed': True,
            'sanctions': [],
            'warnings': [],
        }
        
        try:
            # Check existing sanctions
            existing_sanctions = self._check_existing_sanctions(postback_data)
            if existing_sanctions:
                result['sanctions'].extend(existing_sanctions)
                result['allowed'] = False
            
            # Run fraud detection
            triggered_sanctions = self.fraud_detector.analyze_postback(postback_data)
            for sanction in triggered_sanctions:
                self.apply_sanction(sanction)
                result['sanctions'].append(sanction.to_dict())
            
            # Update result based on sanctions
            if result['sanctions']:
                critical_sanctions = [s for s in result['sanctions'] if s.get('severity') == 'critical']
                if critical_sanctions:
                    result['allowed'] = False
                    result['warnings'].append("Critical sanctions detected")
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error processing postback sanctions: {str(e)}")
            result['warnings'].append(f"Sanction processing error: {str(e)}")
            return result
    
    def _check_existing_sanctions(self, postback_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check existing sanctions for postback."""
        existing = []
        
        # Check IP block
        ip_address = postback_data.get('source_ip')
        if ip_address and self.is_sanctioned(SanctionType.IP_BLOCK, ip_address):
            sanction = self.active_sanctions[f"{SanctionType.IP_BLOCK.value}:{ip_address}"]
            existing.append(sanction.to_dict())
        
        # Check user sanctions
        user_id = postback_data.get('user_id')
        if user_id:
            if self.is_sanctioned(SanctionType.USER_SUSPEND, str(user_id)):
                sanction = self.active_sanctions[f"{SanctionType.USER_SUSPEND.value}:{user_id}"]
                existing.append(sanction.to_dict())
            elif self.is_sanctioned(SanctionType.USER_BAN, str(user_id)):
                sanction = self.active_sanctions[f"{SanctionType.USER_BAN.value}:{user_id}"]
                existing.append(sanction.to_dict())
        
        # Check network sanctions
        network_key = postback_data.get('network_key')
        if network_key:
            if self.is_sanctioned(SanctionType.NETWORK_SUSPEND, network_key):
                sanction = self.active_sanctions[f"{SanctionType.NETWORK_SUSPEND.value}:{network_key}"]
                existing.append(sanction.to_dict())
            elif self.is_sanctioned(SanctionType.NETWORK_BAN, network_key):
                sanction = self.active_sanctions[f"{SanctionType.NETWORK_BAN.value}:{network_key}"]
                existing.append(sanction.to_dict())
        
        return existing
    
    def _enforce_sanction(self, sanction: Sanction):
        """Enforce sanction based on type."""
        if sanction.sanction_type == SanctionType.IP_BLOCK:
            self._enforce_ip_block(sanction)
        elif sanction.sanction_type == SanctionType.USER_SUSPEND:
            self._enforce_user_suspend(sanction)
        elif sanction.sanction_type == SanctionType.USER_BAN:
            self._enforce_user_ban(sanction)
        elif sanction.sanction_type == SanctionType.NETWORK_SUSPEND:
            self._enforce_network_suspend(sanction)
        elif sanction.sanction_type == SanctionType.NETWORK_BAN:
            self._enforce_network_ban(sanction)
        elif sanction.sanction_type == SanctionType.RATE_LIMIT:
            self._enforce_rate_limit(sanction)
    
    def _enforce_ip_block(self, sanction: Sanction):
        """Enforce IP block sanction."""
        # Add to blocked IPs cache
        cache_key = f"blocked_ips"
        blocked_ips = cache.get(cache_key, set())
        blocked_ips.add(sanction.target)
        cache.set(cache_key, blocked_ips, timeout=86400)  # 24 hours
    
    def _enforce_user_suspend(self, sanction: Sanction):
        """Enforce user suspension."""
        # This would integrate with user management system
        pass
    
    def _enforce_user_ban(self, sanction: Sanction):
        """Enforce user ban."""
        # This would integrate with user management system
        pass
    
    def _enforce_network_suspend(self, sanction: Sanction):
        """Enforce network suspension."""
        # Deactivate network
        network = NetworkPostbackConfig.objects.filter(network_key=sanction.target).first()
        if network:
            network.is_active = False
            network.save()
    
    def _enforce_network_ban(self, sanction: Sanction):
        """Enforce network ban."""
        # Delete network configuration
        NetworkPostbackConfig.objects.filter(network_key=sanction.target).delete()
    
    def _enforce_rate_limit(self, sanction: Sanction):
        """Enforce rate limit sanction."""
        # Add to rate limit cache
        cache_key = f"rate_limit_{sanction.target}"
        cache.set(cache_key, True, timeout=int(sanction.duration.total_seconds()))
    
    def _cache_sanction(self, sanction: Sanction):
        """Cache sanction data."""
        cache_key = f"sanction_{sanction.id}"
        cache.set(cache_key, sanction.to_dict(), timeout=86400)  # 24 hours
    
    def _update_sanction_cache(self, sanction: Sanction):
        """Update sanction cache."""
        cache_key = f"sanction_{sanction.id}"
        cache.set(cache_key, sanction.to_dict(), timeout=86400)  # 24 hours
    
    def cleanup_expired_sanctions(self) -> int:
        """Clean up expired sanctions."""
        expired_count = 0
        
        for sanction_key, sanction in list(self.active_sanctions.items()):
            if sanction.is_expired():
                sanction.status = SanctionStatus.EXPIRED
                del self.active_sanctions[sanction_key]
                expired_count += 1
        
        if expired_count > 0:
            self.logger.info(f"Cleaned up {expired_count} expired sanctions")
        
        return expired_count
    
    def get_sanction_statistics(self) -> Dict[str, Any]:
        """Get sanction statistics."""
        total_sanctions = len(self.sanction_history)
        active_sanctions = len(self.active_sanctions)
        
        sanction_types = {}
        for sanction in self.active_sanctions.values():
            sanction_type = sanction.sanction_type.value
            sanction_types[sanction_type] = sanction_types.get(sanction_type, 0) + 1
        
        sanction_severities = {}
        for sanction in self.active_sanctions.values():
            severity = sanction.severity.value
            sanction_severities[severity] = sanction_severities.get(severity, 0) + 1
        
        return {
            'total_sanctions': total_sanctions,
            'active_sanctions': active_sanctions,
            'sanction_types': sanction_types,
            'sanction_severities': sanction_severities,
            'fraud_detection_rules': self.fraud_detector.get_rule_statistics(),
        }


# Global sanction manager instance
sanction_manager = SanctionManager()


# Convenience functions
def apply_ip_block(ip_address: str, reason: str, duration: timedelta = None, severity: SanctionSeverity = SanctionSeverity.HIGH) -> bool:
    """Apply IP block sanction."""
    sanction = Sanction(
        sanction_type=SanctionType.IP_BLOCK,
        target=ip_address,
        reason=reason,
        severity=severity,
        duration=duration or timedelta(days=30),
    )
    return sanction_manager.apply_sanction(sanction)


def apply_user_suspend(user_id: str, reason: str, duration: timedelta = None, severity: SanctionSeverity = SanctionSeverity.MEDIUM) -> bool:
    """Apply user suspension sanction."""
    sanction = Sanction(
        sanction_type=SanctionType.USER_SUSPEND,
        target=str(user_id),
        reason=reason,
        severity=severity,
        duration=duration or timedelta(days=7),
    )
    return sanction_manager.apply_sanction(sanction)


def apply_user_ban(user_id: str, reason: str, severity: SanctionSeverity = SanctionSeverity.CRITICAL) -> bool:
    """Apply user ban sanction."""
    sanction = Sanction(
        sanction_type=SanctionType.USER_BAN,
        target=str(user_id),
        reason=reason,
        severity=severity,
        duration=None,  # Permanent
    )
    return sanction_manager.apply_sanction(sanction)


def apply_network_suspend(network_key: str, reason: str, duration: timedelta = None, severity: SanctionSeverity = SanctionSeverity.HIGH) -> bool:
    """Apply network suspension sanction."""
    sanction = Sanction(
        sanction_type=SanctionType.NETWORK_SUSPEND,
        target=network_key,
        reason=reason,
        severity=severity,
        duration=duration or timedelta(days=30),
    )
    return sanction_manager.apply_sanction(sanction)


def is_ip_blocked(ip_address: str) -> bool:
    """Check if IP is blocked."""
    return sanction_manager.is_sanctioned(SanctionType.IP_BLOCK, ip_address)


def is_user_suspended(user_id: str) -> bool:
    """Check if user is suspended."""
    return sanction_manager.is_sanctioned(SanctionType.USER_SUSPEND, str(user_id))


def is_user_banned(user_id: str) -> bool:
    """Check if user is banned."""
    return sanction_manager.is_sanctioned(SanctionType.USER_BAN, str(user_id))


def process_postback_sanctions(postback_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process postback through sanction system."""
    return sanction_manager.process_postback(postback_data)


def get_sanction_statistics() -> Dict[str, Any]:
    """Get sanction statistics."""
    return sanction_manager.get_sanction_statistics()


def cleanup_expired_sanctions() -> int:
    """Clean up expired sanctions."""
    return sanction_manager.cleanup_expired_sanctions()


# Sanction utilities
def create_sanction_rule(name: str, sanction_type: SanctionType, severity: SanctionSeverity,
                        conditions: Dict[str, Any], duration: timedelta = None) -> SanctionRule:
    """Create custom sanction rule."""
    return SanctionRule(
        name=name,
        sanction_type=sanction_type,
        severity=severity,
        conditions=conditions,
        duration=duration,
    )


def add_fraud_detection_rule(rule: SanctionRule):
    """Add fraud detection rule."""
    sanction_manager.fraud_detector.add_rule(rule)


def remove_fraud_detection_rule(rule_name: str):
    """Remove fraud detection rule."""
    sanction_manager.fraud_detector.remove_rule(rule_name)


# Sanction health check
def check_sanction_health() -> Dict[str, Any]:
    """Check sanction system health."""
    health_status = {
        'overall': 'healthy',
        'sanction_manager': 'healthy',
        'fraud_detector': 'healthy',
        'issues': [],
    }
    
    # Test sanction manager
    try:
        stats = sanction_manager.get_sanction_statistics()
        health_status['sanction_manager'] = 'healthy'
    except Exception as e:
        health_status['sanction_manager'] = 'error'
        health_status['issues'].append(f"Sanction manager error: {str(e)}")
    
    # Test fraud detector
    try:
        rules = sanction_manager.fraud_detector.get_rule_statistics()
        health_status['fraud_detector'] = 'healthy'
    except Exception as e:
        health_status['fraud_detector'] = 'error'
        health_status['issues'].append(f"Fraud detector error: {str(e)}")
    
    if health_status['issues']:
        health_status['overall'] = 'unhealthy'
    
    return health_status
