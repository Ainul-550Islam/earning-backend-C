from django.utils import timezone
"""
IPBlockService.py – Advanced IP blocking and management service.

Provides comprehensive IP blocking functionality including:
- IP range and subnet blocking
- Temporary and permanent blocks
- Block expiration management
- Integration with abuse detection
"""
import logging
import ipaddress
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count
from django.core.cache import cache

from api.rate_limit.models import IPBlockList, AbuseReport, RateLimitLog

logger = logging.getLogger(__name__)


class IPBlockService:
    """Advanced IP blocking and management service."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cache_timeout = 300  # 5 minutes
    
    def block_ip(self, ip_address: str, reason: str = 'manual', block_reason: str = '', 
                blocked_by=None, duration_days: int = 7,
                permanent: bool = False, description: str = '') -> IPBlockList:
        """
        Block a single IP address.
        
        Args:
            ip_address: IP address to block
            reason: Reason for blocking
            blocked_by: User who blocked the IP
            duration_days: Duration in days (ignored if permanent=True)
            permanent: Whether block is permanent
            description: Additional description
            
        Returns:
            Created IPBlockList instance
        """
        try:
            # Validate IP address
            ipaddress.ip_address(ip_address)
            
            # Check if already blocked
            existing_block = IPBlockList.objects.filter(
                ip_address=ip_address,
                is_active=True
            ).first()
            
            if existing_block:
                # Update existing block
                existing_block.reason = reason
                existing_block.blocked_by = blocked_by
                existing_block.description = description
                existing_block.permanent = permanent
                if not permanent:
                    existing_block.expires_at = timezone.now() + timedelta(days=duration_days)
                existing_block.save()
                return existing_block
            
            # Create new block
            expires_at = None if permanent else timezone.now() + timedelta(days=duration_days)
            
            block = IPBlockList.objects.create(
                ip_address=ip_address,
                block_type='single',
                reason=reason,
                blocked_by=blocked_by,
                description=description,
                expires_at=expires_at,
                permanent=permanent
            )
            
            # Clear cache for this IP
            self._clear_ip_cache(ip_address)
            
            self.logger.info(f"Blocked IP: {ip_address} (Reason: {reason})")
            return block
            
        except ValueError as e:
            self.logger.error(f"Invalid IP address {ip_address}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error blocking IP: {e}")
            raise
    
    def block_ip_range(self, start_ip: str, end_ip: str, reason: str = 'manual',
                      blocked_by=None, duration_days: int = 7,
                      permanent: bool = False, description: str = '') -> IPBlockList:
        """
        Block a range of IP addresses.
        
        Args:
            start_ip: Start IP address
            end_ip: End IP address
            reason: Reason for blocking
            blocked_by: User who blocked the IP
            duration_days: Duration in days
            permanent: Whether block is permanent
            description: Additional description
            
        Returns:
            Created IPBlockList instance
        """
        try:
            # Validate IP addresses
            start = ipaddress.ip_address(start_ip)
            end = ipaddress.ip_address(end_ip)
            
            if start > end:
                raise ValueError("Start IP must be less than or equal to end IP")
            
            # Create block
            expires_at = None if permanent else timezone.now() + timedelta(days=duration_days)
            
            block = IPBlockList.objects.create(
                ip_range_start=start_ip,
                ip_range_end=end_ip,
                block_type='range',
                reason=reason,
                blocked_by=blocked_by,
                description=description,
                expires_at=expires_at,
                permanent=permanent
            )
            
            self.logger.info(f"Blocked IP range: {start_ip} - {end_ip} (Reason: {reason})")
            return block
            
        except ValueError as e:
            self.logger.error(f"Invalid IP range: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error blocking IP range: {e}")
            raise
    
    def block_subnet(self, subnet: str, reason: str = 'manual',
                    blocked_by=None, duration_days: int = 7,
                    permanent: bool = False, description: str = '') -> IPBlockList:
        """
        Block a subnet (CIDR notation).
        
        Args:
            subnet: Subnet in CIDR notation (e.g., "192.168.1.0/24")
            reason: Reason for blocking
            blocked_by: User who blocked the IP
            duration_days: Duration in days
            permanent: Whether block is permanent
            description: Additional description
            
        Returns:
            Created IPBlockList instance
        """
        try:
            # Validate subnet
            network = ipaddress.ip_network(subnet, strict=False)
            
            # Create block
            expires_at = None if permanent else timezone.now() + timedelta(days=duration_days)
            
            block = IPBlockList.objects.create(
                subnet=subnet,
                block_type='subnet',
                reason=reason,
                blocked_by=blocked_by,
                description=description,
                expires_at=expires_at,
                permanent=permanent
            )
            
            self.logger.info(f"Blocked subnet: {subnet} (Reason: {reason})")
            return block
            
        except ValueError as e:
            self.logger.error(f"Invalid subnet {subnet}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error blocking subnet: {e}")
            raise
    
    def unblock_ip(self, ip_address: str, unblocked_by=None) -> bool:
        """
        Unblock an IP address.
        
        Args:
            ip_address: IP address to unblock
            unblocked_by: User who unblocked the IP
            
        Returns:
            True if successfully unblocked
        """
        try:
            # Find and deactivate block
            blocks = IPBlockList.objects.filter(
                Q(ip_address=ip_address) | 
                Q(ip_range_start__lte=ip_address, ip_range_end__gte=ip_address) |
                Q(subnet__isnull=False)  # Will check subnet in loop
            ).filter(is_active=True)
            
            # Check subnet blocks
            subnet_blocks = []
            for block in blocks:
                if block.block_type == 'subnet' and block.subnet:
                    try:
                        network = ipaddress.ip_network(block.subnet, strict=False)
                        if ipaddress.ip_address(ip_address) in network:
                            subnet_blocks.append(block)
                    except:
                        continue
            
            all_blocks = list(blocks) + subnet_blocks
            
            if not all_blocks:
                return False
            
            # Deactivate all matching blocks
            for block in all_blocks:
                block.is_active = False
                block.save()
            
            # Clear cache
            self._clear_ip_cache(ip_address)
            
            self.logger.info(f"Unblocked IP: {ip_address}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unblocking IP: {e}")
            return False
    
    def is_ip_blocked(self, ip_address: str) -> Tuple[bool, Optional[IPBlockList]]:
        """
        Check if IP address is blocked.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            Tuple of (is_blocked, blocking_rule)
        """
        try:
            # Check cache first
            cache_key = f"ip_blocked_{ip_address}"
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result['blocked'], cached_result.get('rule')
            
            # Check database
            blocked_rules = IPBlockList.objects.filter(is_active=True)
            
            for rule in blocked_rules:
                if rule.is_ip_blocked(ip_address):
                    # Cache the result
                    cache.set(cache_key, {'blocked': True, 'rule': rule}, self.cache_timeout)
                    return True, rule
            
            # Not blocked
            cache.set(cache_key, {'blocked': False, 'rule': None}, self.cache_timeout)
            return False, None
            
        except Exception as e:
            self.logger.error(f"Error checking IP block status: {e}")
            return False, None
    
    def block_abusive_ips(self, abuse_reports: List[AbuseReport], 
                         severity_threshold: int = 3, block_duration_days: int = 7) -> int:
        """
        Automatically block IPs based on abuse reports.
        
        Args:
            abuse_reports: List of abuse reports
            severity_threshold: Minimum severity to auto-block
            block_duration_days: Duration for temporary blocks
            
        Returns:
            Number of IPs blocked
        """
        blocked_count = 0
        
        for report in abuse_reports:
            if report.severity >= severity_threshold and not report.is_blocked:
                try:
                    # Determine block duration based on severity
                    if report.severity >= 4:
                        permanent = True
                        duration = 0
                    else:
                        permanent = False
                        duration = block_duration_days * report.severity
                    
                    # Block the IP
                    self.block_ip(
                        ip_address=report.ip_address,
                        reason='automatic',
                        duration_days=duration,
                        permanent=permanent,
                        description=f"Auto-blocked due to {report.abuse_type} abuse (Severity: {report.severity})"
                    )
                    
                    # Update report
                    report.is_blocked = True
                    report.save()
                    
                    blocked_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Error auto-blocking IP {report.ip_address}: {e}")
                    continue
        
        self.logger.info(f"Auto-blocked {blocked_count} IPs based on abuse reports")
        return blocked_count
    
    def get_block_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get IP blocking statistics."""
        try:
            since = timezone.now() - timedelta(days=days)
            
            # Overall stats
            total_blocks = IPBlockList.objects.filter(created_at__gte=since).count()
            active_blocks = IPBlockList.objects.filter(is_active=True).count()
            expired_blocks = IPBlockList.objects.filter(
                created_at__gte=since,
                expires_at__lt=timezone.now(),
                permanent=False
            ).count()
            
            # By reason
            blocks_by_reason = IPBlockList.objects.filter(
                created_at__gte=since
            ).values('reason').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # By type
            blocks_by_type = IPBlockList.objects.filter(
                created_at__gte=since
            ).values('block_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Recent blocks
            recent_blocks = IPBlockList.objects.filter(
                created_at__gte=since
            ).order_by('-created_at')[:10]
            
            return {
                'period_days': days,
                'total_blocks': total_blocks,
                'active_blocks': active_blocks,
                'expired_blocks': expired_blocks,
                'blocks_by_reason': list(blocks_by_reason),
                'blocks_by_type': list(blocks_by_type),
                'recent_blocks': [
                    {
                        'id': block.id,
                        'ip_address': block.ip_address,
                        'block_type': block.block_type,
                        'reason': block.reason,
                        'created_at': block.created_at.isoformat(),
                        'expires_at': block.expires_at.isoformat() if block.expires_at else None,
                        'permanent': block.permanent
                    }
                    for block in recent_blocks
                ],
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting block statistics: {e}")
            return {'error': str(e)}
    
    def cleanup_expired_blocks(self) -> int:
        """Clean up expired blocks."""
        try:
            expired_blocks = IPBlockList.objects.filter(
                expires_at__lt=timezone.now(),
                permanent=False,
                is_active=True
            )
            
            count = expired_blocks.count()
            expired_blocks.update(is_active=False)
            
            self.logger.info(f"Cleaned up {count} expired IP blocks")
            return count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up expired blocks: {e}")
            return 0
    
    def get_blocked_ips_for_export(self, format: str = 'csv') -> List[Dict[str, Any]]:
        """Get blocked IPs for export."""
        try:
            blocks = IPBlockList.objects.filter(is_active=True).order_by('-created_at')
            
            export_data = []
            for block in blocks:
                row = {
                    'ip_address': block.ip_address or '',
                    'ip_range_start': block.ip_range_start or '',
                    'ip_range_end': block.ip_range_end or '',
                    'subnet': block.subnet or '',
                    'block_type': block.block_type,
                    'reason': block.reason,
                    'description': block.description,
                    'created_at': block.created_at.isoformat(),
                    'expires_at': block.expires_at.isoformat() if block.expires_at else '',
                    'permanent': block.permanent,
                    'block_count': block.block_count,
                    'last_blocked_at': block.last_blocked_at.isoformat() if block.last_blocked_at else ''
                }
                export_data.append(row)
            
            return export_data
            
        except Exception as e:
            self.logger.error(f"Error exporting blocked IPs: {e}")
            return []
    
    def _clear_ip_cache(self, ip_address: str):
        """Clear cache for IP address."""
        try:
            cache_key = f"ip_blocked_{ip_address}"
            cache.delete(cache_key)
        except Exception as e:
            self.logger.error(f"Error clearing IP cache: {e}")
    
    def update_block_statistics(self):
        """Update block count and last blocked timestamp."""
        try:
            # This would typically be called periodically via a management command
            active_blocks = IPBlockList.objects.filter(is_active=True)
            
            for block in active_blocks:
                # Update block count based on recent rate limit logs
                recent_logs = RateLimitLog.objects.filter(
                    ip_address=block.ip_address,
                    status='blocked',
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                ).count()
                
                if recent_logs > block.block_count:
                    block.block_count = recent_logs
                    block.last_blocked_at = timezone.now()
                    block.save(update_fields=['block_count', 'last_blocked_at'])
            
        except Exception as e:
            self.logger.error(f"Error updating block statistics: {e}")


    # ─────────────────────────────────────────────────────────
    # Integration-friendly methods (called by integration_service.py)
    # ─────────────────────────────────────────────────────────

    def block_ip_for_hours(
        self,
        ip_address: str,
        reason: str = 'integration',
        hours: int = 24,
        blocked_by_user_id: int = None,
        description: str = '',
    ):
        """
        Block IP by hours instead of days.
        Called by integration_service.block_ip().
        Converts hours → duration_days for existing block_ip().
        """
        from math import ceil
        blocked_by = None
        if blocked_by_user_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                blocked_by = User.objects.filter(id=blocked_by_user_id).first()
            except Exception:
                pass

        duration_days = max(1, ceil(hours / 24))
        return self.block_ip(
            ip_address=ip_address,
            reason=reason,
            blocked_by=blocked_by,
            duration_days=duration_days,
            permanent=False,
            description=description or f'Blocked for {hours} hours',
        )

    def is_blocked_simple(self, ip_address: str) -> bool:
        """
        Simple bool check — is this IP currently blocked?
        Called by integration_service._run_check() blacklist path.
        """
        blocked, _ = self.is_ip_blocked(ip_address)
        return blocked
