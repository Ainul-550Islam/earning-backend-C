# =============================================================================
# fraud_detection/services/WhitelistService.py
# =============================================================================
"""
Whitelist Service.

Comprehensive service for managing whitelist/blacklist entries including
automatic management, validation, and integration with fraud detection.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from api.fraud_detection.models import FraudWhitelist, FraudAlert, UserRiskProfile
from api.fraud_detection.choices import WhitelistType, FraudAlertType, AlertPriority
from api.fraud_detection.constants import CACHE_KEYS

logger = logging.getLogger(__name__)


class WhitelistService:
    """Service for managing whitelist and blacklist operations."""
    
    def __init__(self):
        self.cache_ttl = 7200  # 2 hours
    
    def add_to_whitelist(self, entity_type: str, entity_value: str, reason: str,
                        whitelisted_by: int, expires_at: Optional[timezone.datetime] = None,
                        metadata: Optional[Dict] = None) -> Tuple[FraudWhitelist, bool]:
        """
        Add an entity to the whitelist.
        
        Args:
            entity_type: Type of entity (user, ip_address, device, domain, email)
            entity_value: Value to whitelist
            reason: Reason for whitelisting
            whitelisted_by: User ID who performed the whitelisting
            expires_at: Optional expiration date
            metadata: Additional metadata
            
        Returns:
            Tuple of (Whitelist instance, created_flag)
        """
        try:
            with transaction.atomic():
                # Check if already whitelisted
                existing = FraudWhitelist.objects.filter(
                    entity_type=entity_type,
                    entity_value=entity_value,
                    is_active=True
                ).first()
                
                if existing:
                    logger.info(f"Entity {entity_value} already whitelisted")
                    return existing, False
                
                # Remove from blacklist if exists
                self._remove_from_blacklist(entity_type, entity_value)
                
                # Create whitelist entry
                whitelist = FraudWhitelist.objects.create(
                    entity_type=entity_type,
                    entity_value=entity_value,
                    reason=reason,
                    whitelisted_by_id=whitelisted_by,
                    expires_at=expires_at,
                    metadata=metadata or {},
                )
                
                # Invalidate cache
                self._invalidate_whitelist_cache(entity_type, entity_value)
                
                # Log the action
                logger.info(f"Added {entity_type} {entity_value} to whitelist by user {whitelisted_by}")
                
                return whitelist, True
                
        except Exception as e:
            logger.error("Error adding %s to whitelist: %s", entity_value, e, exc_info=True)
            raise
    
    def add_to_blacklist(self, entity_type: str, entity_value: str, reason: str,
                        blacklisted_by: int, expires_at: Optional[timezone.datetime] = None,
                        metadata: Optional[Dict] = None) -> Tuple[FraudWhitelist, bool]:
        """
        Add an entity to the blacklist.
        
        Args:
            entity_type: Type of entity (user, ip_address, device, domain, email)
            entity_value: Value to blacklist
            reason: Reason for blacklisting
            blacklisted_by: User ID who performed the blacklisting
            expires_at: Optional expiration date
            metadata: Additional metadata
            
        Returns:
            Tuple of (Whitelist instance, created_flag)
        """
        try:
            with transaction.atomic():
                # Check if already blacklisted
                existing = FraudWhitelist.objects.filter(
                    entity_type=entity_type,
                    entity_value=entity_value,
                    is_blacklisted=True,
                    is_active=True
                ).first()
                
                if existing:
                    logger.info(f"Entity {entity_value} already blacklisted")
                    return existing, False
                
                # Remove from whitelist if exists
                self._remove_from_whitelist(entity_type, entity_value)
                
                # Create blacklist entry
                blacklist = FraudWhitelist.objects.create(
                    entity_type=entity_type,
                    entity_value=entity_value,
                    reason=reason,
                    whitelisted_by_id=blacklisted_by,
                    is_blacklisted=True,
                    blacklisted_at=timezone.now(),
                    expires_at=expires_at,
                    metadata=metadata or {},
                )
                
                # Create alert for blacklisting
                self._create_blacklist_alert(blacklist, blacklisted_by)
                
                # Invalidate cache
                self._invalidate_whitelist_cache(entity_type, entity_value)
                
                # Log the action
                logger.info(f"Added {entity_type} {entity_value} to blacklist by user {blacklisted_by}")
                
                return blacklist, True
                
        except Exception as e:
            logger.error("Error adding %s to blacklist: %s", entity_value, e, exc_info=True)
            raise
    
    def remove_from_whitelist(self, entity_type: str, entity_value: str,
                             removed_by: int, reason: Optional[str] = None) -> bool:
        """
        Remove an entity from the whitelist.
        
        Args:
            entity_type: Type of entity
            entity_value: Value to remove
            removed_by: User ID performing the removal
            reason: Reason for removal
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                whitelist = FraudWhitelist.objects.filter(
                    entity_type=entity_type,
                    entity_value=entity_value,
                    is_active=True,
                    is_blacklisted=False
                ).first()
                
                if not whitelist:
                    logger.warning(f"Whitelist entry not found for {entity_value}")
                    return False
                
                # Deactivate the entry
                whitelist.is_active = False
                whitelist.deactivated_at = timezone.now()
                whitelist.deactivated_by_id = removed_by
                whitelist.deactivation_reason = reason or "Manual removal"
                whitelist.save()
                
                # Invalidate cache
                self._invalidate_whitelist_cache(entity_type, entity_value)
                
                logger.info(f"Removed {entity_type} {entity_value} from whitelist by user {removed_by}")
                return True
                
        except Exception as e:
            logger.error("Error removing %s from whitelist: %s", entity_value, e, exc_info=True)
            return False
    
    def remove_from_blacklist(self, entity_type: str, entity_value: str,
                              removed_by: int, reason: Optional[str] = None) -> bool:
        """
        Remove an entity from the blacklist.
        
        Args:
            entity_type: Type of entity
            entity_value: Value to remove
            removed_by: User ID performing the removal
            reason: Reason for removal
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                blacklist = FraudWhitelist.objects.filter(
                    entity_type=entity_type,
                    entity_value=entity_value,
                    is_active=True,
                    is_blacklisted=True
                ).first()
                
                if not blacklist:
                    logger.warning(f"Blacklist entry not found for {entity_value}")
                    return False
                
                # Deactivate the entry
                blacklist.is_active = False
                blacklist.deactivated_at = timezone.now()
                blacklist.deactivated_by_id = removed_by
                blacklist.deactivation_reason = reason or "Manual removal"
                blacklist.save()
                
                # Invalidate cache
                self._invalidate_whitelist_cache(entity_type, entity_value)
                
                logger.info(f"Removed {entity_type} {entity_value} from blacklist by user {removed_by}")
                return True
                
        except Exception as e:
            logger.error("Error removing %s from blacklist: %s", entity_value, e, exc_info=True)
            return False
    
    def is_whitelisted(self, entity_type: str, entity_value: str) -> bool:
        """
        Check if an entity is whitelisted.
        
        Args:
            entity_type: Type of entity
            entity_value: Value to check
            
        Returns:
            True if whitelisted, False otherwise
        """
        cache_key = f'whitelist_{entity_type}_{entity_value}'
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            whitelist = FraudWhitelist.objects.filter(
                entity_type=entity_type,
                entity_value=entity_value,
                is_active=True,
                is_blacklisted=False
            ).first()
            
            is_whitelisted = whitelist is not None and (
                whitelist.expires_at is None or whitelist.expires_at > timezone.now()
            )
            
            # Cache the result
            cache.set(cache_key, is_whitelisted, self.cache_ttl)
            
            return is_whitelisted
            
        except Exception as e:
            logger.error("Error checking whitelist status for %s: %s", entity_value, e, exc_info=True)
            return False
    
    def is_blacklisted(self, entity_type: str, entity_value: str) -> bool:
        """
        Check if an entity is blacklisted.
        
        Args:
            entity_type: Type of entity
            entity_value: Value to check
            
        Returns:
            True if blacklisted, False otherwise
        """
        cache_key = f'blacklist_{entity_type}_{entity_value}'
        cached_result = cache.get(cache_key)
        
        if cached_result is not None:
            return cached_result
        
        try:
            blacklist = FraudWhitelist.objects.filter(
                entity_type=entity_type,
                entity_value=entity_value,
                is_active=True,
                is_blacklisted=True
            ).first()
            
            is_blacklisted = blacklist is not None and (
                blacklist.expires_at is None or blacklist.expires_at > timezone.now()
            )
            
            # Cache the result
            cache.set(cache_key, is_blacklisted, self.cache_ttl)
            
            return is_blacklisted
            
        except Exception as e:
            logger.error("Error checking blacklist status for %s: %s", entity_value, e, exc_info=True)
            return False
    
    def get_whitelist_entries(self, entity_type: Optional[str] = None,
                           is_blacklisted: Optional[bool] = None,
                           active_only: bool = True,
                           limit: int = 100) -> List[Dict]:
        """
        Get whitelist entries with filtering.
        
        Args:
            entity_type: Filter by entity type
            is_blacklisted: Filter by blacklist status
            active_only: Only active entries
            limit: Maximum number of entries
            
        Returns:
            List of whitelist entry dictionaries
        """
        try:
            queryset = FraudWhitelist.objects.all()
            
            if entity_type:
                queryset = queryset.filter(entity_type=entity_type)
            
            if is_blacklisted is not None:
                queryset = queryset.filter(is_blacklisted=is_blacklisted)
            
            if active_only:
                queryset = queryset.filter(is_active=True)
            
            entries = queryset.select_related('whitelisted_by', 'deactivated_by').order_by('-created_at')[:limit]
            
            return [
                {
                    'id': entry.id,
                    'entity_type': entry.entity_type,
                    'entity_value': entry.entity_value,
                    'is_blacklisted': entry.is_blacklisted,
                    'reason': entry.reason,
                    'whitelisted_by': entry.whitelisted_by.username if entry.whitelisted_by else None,
                    'created_at': entry.created_at.isoformat(),
                    'expires_at': entry.expires_at.isoformat() if entry.expires_at else None,
                    'is_active': entry.is_active,
                    'deactivated_at': entry.deactivated_at.isoformat() if entry.deactivated_at else None,
                    'deactivated_by': entry.deactivated_by.username if entry.deactivated_by else None,
                    'deactivation_reason': entry.deactivation_reason,
                }
                for entry in entries
            ]
            
        except Exception as e:
            logger.error("Error getting whitelist entries: %s", e, exc_info=True)
            return []
    
    def bulk_whitelist(self, entities: List[Tuple[str, str]], reason: str,
                      whitelisted_by: int, expires_at: Optional[timezone.datetime] = None) -> Dict[str, int]:
        """
        Bulk add entities to whitelist.
        
        Args:
            entities: List of (entity_type, entity_value) tuples
            reason: Reason for whitelisting
            whitelisted_by: User ID performing the action
            expires_at: Optional expiration date
            
        Returns:
            Dictionary with success and error counts
        """
        success_count = 0
        error_count = 0
        
        try:
            with transaction.atomic():
                for entity_type, entity_value in entities:
                    try:
                        self.add_to_whitelist(
                            entity_type, entity_value, reason, whitelisted_by, expires_at
                        )
                        success_count += 1
                    except Exception as e:
                        logger.error("Error bulk whitelisting %s: %s", entity_value, e, exc_info=True)
                        error_count += 1
                
                logger.info(f"Bulk whitelist completed: {success_count} success, {error_count} errors")
                return {'success': success_count, 'errors': error_count}
                
        except Exception as e:
            logger.error("Error in bulk whitelist operation: %s", e, exc_info=True)
            return {'success': 0, 'errors': len(entities)}
    
    def bulk_blacklist(self, entities: List[Tuple[str, str]], reason: str,
                      blacklisted_by: int, expires_at: Optional[timezone.datetime] = None) -> Dict[str, int]:
        """
        Bulk add entities to blacklist.
        
        Args:
            entities: List of (entity_type, entity_value) tuples
            reason: Reason for blacklisting
            blacklisted_by: User ID performing the action
            expires_at: Optional expiration date
            
        Returns:
            Dictionary with success and error counts
        """
        success_count = 0
        error_count = 0
        
        try:
            with transaction.atomic():
                for entity_type, entity_value in entities:
                    try:
                        self.add_to_blacklist(
                            entity_type, entity_value, reason, blacklisted_by, expires_at
                        )
                        success_count += 1
                    except Exception as e:
                        logger.error("Error bulk blacklisting %s: %s", entity_value, e, exc_info=True)
                        error_count += 1
                
                logger.info(f"Bulk blacklist completed: {success_count} success, {error_count} errors")
                return {'success': success_count, 'errors': error_count}
                
        except Exception as e:
            logger.error("Error in bulk blacklist operation: %s", e, exc_info=True)
            return {'success': 0, 'errors': len(entities)}
    
    def cleanup_expired_entries(self) -> Dict[str, int]:
        """
        Clean up expired whitelist/blacklist entries.
        
        Returns:
            Dictionary with cleanup counts
        """
        try:
            with transaction.atomic():
                expired_entries = FraudWhitelist.objects.filter(
                    expires_at__lt=timezone.now(),
                    is_active=True
                )
                
                expired_count = expired_entries.count()
                
                # Deactivate expired entries
                expired_entries.update(
                    is_active=False,
                    deactivated_at=timezone.now(),
                    deactivation_reason="Expired"
                )
                
                logger.info(f"Cleaned up {expired_count} expired whitelist entries")
                return {'expired': expired_count}
                
        except Exception as e:
            logger.error(f"Error cleaning up expired entries: {e}")
            return {'expired': 0}
    
    def get_whitelist_statistics(self) -> Dict[str, Any]:
        """
        Get whitelist/blacklist statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            stats = {}
            
            # Total counts
            stats['total_whitelisted'] = FraudWhitelist.objects.filter(
                is_active=True, is_blacklisted=False
            ).count()
            
            stats['total_blacklisted'] = FraudWhitelist.objects.filter(
                is_active=True, is_blacklisted=True
            ).count()
            
            # By entity type
            for entity_type, _ in WhitelistType.choices:
                stats[f'{entity_type}_whitelisted'] = FraudWhitelist.objects.filter(
                    entity_type=entity_type, is_active=True, is_blacklisted=False
                ).count()
                
                stats[f'{entity_type}_blacklisted'] = FraudWhitelist.objects.filter(
                    entity_type=entity_type, is_active=True, is_blacklisted=True
                ).count()
            
            # Recent activity
            recent_cutoff = timezone.now() - timedelta(days=7)
            stats['recent_additions'] = FraudWhitelist.objects.filter(
                created_at__gte=recent_cutoff
            ).count()
            
            stats['recent_removals'] = FraudWhitelist.objects.filter(
                deactivated_at__gte=recent_cutoff
            ).count()
            
            # Expiring soon
            expiring_soon = timezone.now() + timedelta(days=7)
            stats['expiring_soon'] = FraudWhitelist.objects.filter(
                expires_at__lte=expiring_soon,
                expires_at__gt=timezone.now(),
                is_active=True
            ).count()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting whitelist statistics: {e}")
            return {}
    
    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================
    
    def _remove_from_blacklist(self, entity_type: str, entity_value: str):
        """Remove from blacklist if exists."""
        try:
            blacklist = FraudWhitelist.objects.filter(
                entity_type=entity_type,
                entity_value=entity_value,
                is_active=True,
                is_blacklisted=True
            ).first()
            
            if blacklist:
                blacklist.is_active = False
                blacklist.deactivated_at = timezone.now()
                blacklist.deactivation_reason = "Whitelisted"
                blacklist.save()
                
                logger.info(f"Removed {entity_value} from blacklist (whitelisted)")
                
        except Exception as e:
            logger.error(f"Error removing {entity_value} from blacklist: {e}")
    
    def _remove_from_whitelist(self, entity_type: str, entity_value: str):
        """Remove from whitelist if exists."""
        try:
            whitelist = FraudWhitelist.objects.filter(
                entity_type=entity_type,
                entity_value=entity_value,
                is_active=True,
                is_blacklisted=False
            ).first()
            
            if whitelist:
                whitelist.is_active = False
                whitelist.deactivated_at = timezone.now()
                whitelist.deactivation_reason = "Blacklisted"
                whitelist.save()
                
                logger.info(f"Removed {entity_value} from whitelist (blacklisted)")
                
        except Exception as e:
            logger.error(f"Error removing {entity_value} from whitelist: {e}")
    
    def _create_blacklist_alert(self, blacklist: FraudWhitelist, blacklisted_by: int):
        """Create alert for blacklisting."""
        try:
            FraudAlert.objects.create(
                alert_type=FraudAlertType.SYSTEM_ANOMALY,
                priority=AlertPriority.HIGH,
                title=f"Entity Blacklisted: {blacklist.entity_value}",
                description=f"{blacklist.entity_type.title()} {blacklist.entity_value} added to blacklist: {blacklist.reason}",
                data={
                    'entity_type': blacklist.entity_type,
                    'entity_value': blacklist.entity_value,
                    'reason': blacklist.reason,
                    'blacklisted_by': blacklisted_by,
                }
            )
        except Exception as e:
            logger.error(f"Error creating blacklist alert: {e}")
    
    def _invalidate_whitelist_cache(self, entity_type: str, entity_value: str):
        """Invalidate cache entries for whitelist/blacklist."""
        cache_keys = [
            f'whitelist_{entity_type}_{entity_value}',
            f'blacklist_{entity_type}_{entity_value}',
            f'whitelist_stats',
        ]
        
        for key in cache_keys:
            cache.delete(key)
