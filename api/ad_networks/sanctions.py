"""
api/ad_networks/sanctions.py
Sanctions and compliance management for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, UserWallet, BlacklistedIP, KnownBadIP,
    FraudDetectionRule, OfferClick
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import FRAUD_SCORE_THRESHOLD, CACHE_TIMEOUTS
from .helpers import get_cache_key, validate_ip_address

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== SANCTION TYPES ====================

class SanctionType:
    """Sanction types for different violations"""
    
    WARNING = "warning"
    TEMPORARY_SUSPENSION = "temporary_suspension"
    PERMANENT_BAN = "permanent_ban"
    WALLET_FREEZE = "wallet_freeze"
    OFFER_REMOVAL = "offer_removal"
    NETWORK_BAN = "network_ban"
    IP_BLACKLIST = "ip_blacklist"
    DEVICE_BAN = "device_ban"
    PAYMENT_HOLD = "payment_hold"
    VERIFICATION_REQUIRED = "verification_required"


# ==================== SANCTION SEVERITY ====================

class SanctionSeverity:
    """Sanction severity levels"""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== BASE SANCTION MANAGER ====================

class BaseSanctionManager:
    """Base sanction manager with common functionality"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('sanctions', 3600)
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key"""
        return get_cache_key(self.__class__.__name__, self.tenant_id, *args, **kwargs)
    
    def _get_from_cache(self, key: str) -> Any:
        """Get data from cache"""
        return cache.get(key)
    
    def _set_cache(self, key: str, data: Any, timeout: int = None) -> None:
        """Set data in cache"""
        timeout = timeout or self.cache_timeout
        cache.set(key, data, timeout)


# ==================== USER SANCTION MANAGER ====================

class UserSanctionManager(BaseSanctionManager):
    """Manager for user sanctions"""
    
    def apply_user_sanction(self, user_id: int, sanction_type: str, 
                           reason: str, severity: str = SanctionSeverity.MEDIUM,
                           duration_days: int = None, applied_by: int = None) -> Dict[str, Any]:
        """Apply sanction to user"""
        with transaction.atomic():
            # Get user
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise ValueError("User not found")
            
            # Check existing sanctions
            existing_sanctions = self.get_user_active_sanctions(user_id)
            if existing_sanctions:
                # Check if user already has a more severe sanction
                for sanction in existing_sanctions:
                    if self._is_more_severe(sanction['type'], sanction_type):
                        raise ValueError(f"User already has a more severe sanction: {sanction['type']}")
            
            # Create sanction record
            sanction_data = {
                'user_id': user_id,
                'type': sanction_type,
                'reason': reason,
                'severity': severity,
                'applied_at': timezone.now(),
                'applied_by_id': applied_by,
                'status': 'active',
            }
            
            if duration_days:
                sanction_data['expires_at'] = timezone.now() + timedelta(days=duration_days)
            
            # This would typically save to a Sanction model
            # For now, we'll apply the sanction directly
            
            # Apply sanction based on type
            result = self._apply_user_sanction_by_type(user, sanction_type, reason, duration_days)
            
            # Log sanction
            self._log_sanction('user', user_id, sanction_type, reason, applied_by)
            
            # Send notifications
            self._send_sanction_notification(user, sanction_type, reason)
            
            return {
                'user_id': user_id,
                'sanction_type': sanction_type,
                'reason': reason,
                'severity': severity,
                'applied_at': sanction_data['applied_at'].isoformat(),
                'expires_at': sanction_data.get('expires_at', None),
                'result': result,
            }
    
    def _apply_user_sanction_by_type(self, user: User, sanction_type: str, 
                                     reason: str, duration_days: int = None) -> Dict[str, Any]:
        """Apply specific sanction type to user"""
        result = {}
        
        if sanction_type == SanctionType.WARNING:
            result = self._apply_warning(user, reason)
        
        elif sanction_type == SanctionType.TEMPORARY_SUSPENSION:
            result = self._apply_temporary_suspension(user, reason, duration_days)
        
        elif sanction_type == SanctionType.PERMANENT_BAN:
            result = self._apply_permanent_ban(user, reason)
        
        elif sanction_type == SanctionType.WALLET_FREEZE:
            result = self._apply_wallet_freeze(user, reason)
        
        elif sanction_type == SanctionType.VERIFICATION_REQUIRED:
            result = self._apply_verification_required(user, reason)
        
        elif sanction_type == SanctionType.PAYMENT_HOLD:
            result = self._apply_payment_hold(user, reason)
        
        else:
            raise ValueError(f"Unknown sanction type: {sanction_type}")
        
        return result
    
    def _apply_warning(self, user: User, reason: str) -> Dict[str, Any]:
        """Apply warning to user"""
        # This would create a warning record
        logger.warning(f"Warning applied to user {user.id}: {reason}")
        
        return {
            'type': 'warning',
            'message': 'Warning issued to user',
            'user_status': user.is_active,
        }
    
    def _apply_temporary_suspension(self, user: User, reason: str, 
                                   duration_days: int = 7) -> Dict[str, Any]:
        """Apply temporary suspension to user"""
        # Deactivate user
        user.is_active = False
        user.save(update_fields=['is_active'])
        
        # Freeze wallet
        try:
            wallet = UserWallet.objects.get(user=user, tenant_id=self.tenant_id)
            wallet.is_frozen = True
            wallet.freeze_reason = f"Temporary suspension: {reason}"
            wallet.frozen_at = timezone.now()
            wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
        except UserWallet.DoesNotExist:
            pass
        
        # Cancel pending engagements
        UserOfferEngagement.objects.filter(
            user=user,
            tenant_id=self.tenant_id,
            status=EngagementStatus.IN_PROGRESS
        ).update(status=EngagementStatus.CANCELLED)
        
        return {
            'type': 'temporary_suspension',
            'duration_days': duration_days,
            'user_status': user.is_active,
            'wallet_frozen': True,
        }
    
    def _apply_permanent_ban(self, user: User, reason: str) -> Dict[str, Any]:
        """Apply permanent ban to user"""
        # Deactivate user permanently
        user.is_active = False
        user.save(update_fields=['is_active'])
        
        # Freeze wallet permanently
        try:
            wallet = UserWallet.objects.get(user=user, tenant_id=self.tenant_id)
            wallet.is_frozen = True
            wallet.freeze_reason = f"Permanent ban: {reason}"
            wallet.frozen_at = timezone.now()
            wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
        except UserWallet.DoesNotExist:
            pass
        
        # Cancel all engagements
        UserOfferEngagement.objects.filter(
            user=user,
            tenant_id=self.tenant_id
        ).update(status=EngagementStatus.CANCELLED)
        
        # Reject pending conversions
        OfferConversion.objects.filter(
            engagement__user=user,
            tenant_id=self.tenant_id,
            status=ConversionStatus.PENDING
        ).update(
            status=ConversionStatus.REJECTED,
            rejection_reason=f"User permanently banned: {reason}"
        )
        
        return {
            'type': 'permanent_ban',
            'user_status': user.is_active,
            'wallet_frozen': True,
            'engagements_cancelled': True,
            'conversions_rejected': True,
        }
    
    def _apply_wallet_freeze(self, user: User, reason: str) -> Dict[str, Any]:
        """Freeze user wallet"""
        try:
            wallet = UserWallet.objects.get(user=user, tenant_id=self.tenant_id)
            wallet.is_frozen = True
            wallet.freeze_reason = f"Wallet freeze: {reason}"
            wallet.frozen_at = timezone.now()
            wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
            
            return {
                'type': 'wallet_freeze',
                'wallet_frozen': True,
                'previous_balance': float(wallet.current_balance),
            }
        except UserWallet.DoesNotExist:
            return {
                'type': 'wallet_freeze',
                'wallet_frozen': False,
                'message': 'No wallet found for user',
            }
    
    def _apply_verification_required(self, user: User, reason: str) -> Dict[str, Any]:
        """Require user verification"""
        # This would set a flag requiring verification
        logger.info(f"Verification required for user {user.id}: {reason}")
        
        return {
            'type': 'verification_required',
            'verification_needed': True,
            'user_status': user.is_active,
        }
    
    def _apply_payment_hold(self, user: User, reason: str) -> Dict[str, Any]:
        """Hold user payments"""
        # This would create a payment hold record
        logger.info(f"Payment hold applied to user {user.id}: {reason}")
        
        return {
            'type': 'payment_hold',
            'payment_hold': True,
            'message': 'User payments are on hold',
        }
    
    def get_user_active_sanctions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's active sanctions"""
        # This would query a Sanction model
        # For now, check user status and wallet status
        sanctions = []
        
        try:
            user = User.objects.get(id=user_id)
            
            if not user.is_active:
                sanctions.append({
                    'type': SanctionType.PERMANENT_BAN,
                    'reason': 'User is inactive',
                    'applied_at': user.date_joined,
                    'status': 'active',
                })
            
            try:
                wallet = UserWallet.objects.get(user=user, tenant_id=self.tenant_id)
                if wallet.is_frozen:
                    sanctions.append({
                        'type': SanctionType.WALLET_FREEZE,
                        'reason': wallet.freeze_reason,
                        'applied_at': wallet.frozen_at,
                        'status': 'active',
                    })
            except UserWallet.DoesNotExist:
                pass
            
        except User.DoesNotExist:
            pass
        
        return sanctions
    
    def lift_user_sanction(self, user_id: int, sanction_type: str, 
                          lifted_by: int = None, reason: str = None) -> Dict[str, Any]:
        """Lift user sanction"""
        with transaction.atomic():
            # Get user
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise ValueError("User not found")
            
            # Lift sanction based on type
            result = self._lift_user_sanction_by_type(user, sanction_type)
            
            # Log sanction lift
            self._log_sanction_lift('user', user_id, sanction_type, reason, lifted_by)
            
            return {
                'user_id': user_id,
                'sanction_type': sanction_type,
                'lifted_at': timezone.now().isoformat(),
                'lifted_by': lifted_by,
                'reason': reason,
                'result': result,
            }
    
    def _lift_user_sanction_by_type(self, user: User, sanction_type: str) -> Dict[str, Any]:
        """Lift specific sanction type"""
        result = {}
        
        if sanction_type == SanctionType.TEMPORARY_SUSPENSION:
            # Reactivate user
            user.is_active = True
            user.save(update_fields=['is_active'])
            
            # Unfreeze wallet
            try:
                wallet = UserWallet.objects.get(user=user, tenant_id=self.tenant_id)
                wallet.is_frozen = False
                wallet.freeze_reason = None
                wallet.frozen_at = None
                wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
            except UserWallet.DoesNotExist:
                pass
            
            result = {
                'type': 'temporary_suspension_lifted',
                'user_status': user.is_active,
                'wallet_frozen': False,
            }
        
        elif sanction_type == SanctionType.WALLET_FREEZE:
            # Unfreeze wallet
            try:
                wallet = UserWallet.objects.get(user=user, tenant_id=self.tenant_id)
                wallet.is_frozen = False
                wallet.freeze_reason = None
                wallet.frozen_at = None
                wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
                
                result = {
                    'type': 'wallet_freeze_lifted',
                    'wallet_frozen': False,
                }
            except UserWallet.DoesNotExist:
                result = {
                    'type': 'wallet_freeze_lifted',
                    'wallet_frozen': False,
                    'message': 'No wallet found for user',
                }
        
        else:
            raise ValueError(f"Cannot lift sanction type: {sanction_type}")
        
        return result


# ==================== IP SANCTION MANAGER ====================

class IPSanctionManager(BaseSanctionManager):
    """Manager for IP address sanctions"""
    
    def blacklist_ip(self, ip_address: str, reason: str, 
                     duration_days: int = None, added_by: int = None) -> Dict[str, Any]:
        """Blacklist IP address"""
        if not validate_ip_address(ip_address):
            raise ValueError("Invalid IP address")
        
        with transaction.atomic():
            # Check if IP is already blacklisted
            existing = BlacklistedIP.objects.filter(
                ip_address=ip_address,
                tenant_id=self.tenant_id,
                is_active=True
            ).first()
            
            if existing:
                raise ValueError("IP address is already blacklisted")
            
            # Create blacklist entry
            blacklist_data = {
                'ip_address': ip_address,
                'tenant_id': self.tenant_id,
                'reason': reason,
                'added_by_id': added_by,
                'is_active': True,
            }
            
            if duration_days:
                blacklist_data['expires_at'] = timezone.now() + timedelta(days=duration_days)
            
            blacklist = BlacklistedIP.objects.create(**blacklist_data)
            
            # Cancel active engagements from this IP
            self._cancel_engagements_from_ip(ip_address)
            
            # Log blacklist
            self._log_ip_blacklist(ip_address, reason, added_by)
            
            return {
                'ip_address': ip_address,
                'blacklist_id': blacklist.id,
                'reason': reason,
                'added_at': blacklist.added_at.isoformat(),
                'expires_at': blacklist.expires_at.isoformat() if blacklist.expires_at else None,
                'is_active': blacklist.is_active,
            }
    
    def _cancel_engagements_from_ip(self, ip_address: str):
        """Cancel active engagements from blacklisted IP"""
        # Find offers clicked from this IP
        clicks = OfferClick.objects.filter(
            ip_address=ip_address,
            tenant_id=self.tenant_id
        )
        
        # Cancel corresponding engagements
        for click in clicks:
            UserOfferEngagement.objects.filter(
                user=click.user,
                offer=click.offer,
                tenant_id=self.tenant_id,
                status=EngagementStatus.IN_PROGRESS
            ).update(status=EngagementStatus.CANCELLED)
    
    def is_ip_blacklisted(self, ip_address: str) -> bool:
        """Check if IP is blacklisted"""
        if not validate_ip_address(ip_address):
            return False
        
        return BlacklistedIP.objects.filter(
            ip_address=ip_address,
            tenant_id=self.tenant_id,
            is_active=True
        ).exists()
    
    def get_blacklisted_ips(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get blacklisted IPs"""
        queryset = BlacklistedIP.objects.filter(tenant_id=self.tenant_id)
        
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        blacklisted_ips = []
        
        for ip in queryset:
            blacklisted_ips.append({
                'id': ip.id,
                'ip_address': ip.ip_address,
                'reason': ip.reason,
                'added_at': ip.added_at.isoformat(),
                'expires_at': ip.expires_at.isoformat() if ip.expires_at else None,
                'is_active': ip.is_active,
                'added_by': ip.added_by.username if ip.added_by else None,
            })
        
        return blacklisted_ips
    
    def remove_ip_blacklist(self, ip_address: str, removed_by: int = None, 
                          reason: str = None) -> Dict[str, Any]:
        """Remove IP from blacklist"""
        with transaction.atomic():
            try:
                blacklist = BlacklistedIP.objects.get(
                    ip_address=ip_address,
                    tenant_id=self.tenant_id,
                    is_active=True
                )
                
                blacklist.is_active = False
                blacklist.removed_by_id = removed_by
                blacklist.removed_at = timezone.now()
                blacklist.removal_reason = reason
                blacklist.save(update_fields=['is_active', 'removed_by', 'removed_at', 'removal_reason'])
                
                return {
                    'ip_address': ip_address,
                    'removed_at': blacklist.removed_at.isoformat(),
                    'removed_by': removed_by,
                    'reason': reason,
                    'status': 'removed',
                }
                
            except BlacklistedIP.DoesNotExist:
                raise ValueError("IP address is not blacklisted")
    
    def _log_ip_blacklist(self, ip_address: str, reason: str, added_by: int = None):
        """Log IP blacklist action"""
        logger.warning(f"IP {ip_address} blacklisted: {reason} by {added_by}")


# ==================== OFFER SANCTION MANAGER ====================

class OfferSanctionManager(BaseSanctionManager):
    """Manager for offer sanctions"""
    
    def remove_offer(self, offer_id: int, reason: str, removed_by: int = None) -> Dict[str, Any]:
        """Remove offer from platform"""
        with transaction.atomic():
            # Get offer
            try:
                offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            except Offer.DoesNotExist:
                raise ValueError("Offer not found")
            
            # Cancel active engagements
            UserOfferEngagement.objects.filter(
                offer=offer,
                tenant_id=self.tenant_id,
                status=EngagementStatus.IN_PROGRESS
            ).update(status=EngagementStatus.CANCELLED)
            
            # Reject pending conversions
            OfferConversion.objects.filter(
                engagement__offer=offer,
                tenant_id=self.tenant_id,
                status=ConversionStatus.PENDING
            ).update(
                status=ConversionStatus.REJECTED,
                rejection_reason=f"Offer removed: {reason}"
            )
            
            # Deactivate offer
            offer.status = OfferStatus.REMOVED
            offer.removal_reason = reason
            offer.removed_by_id = removed_by
            offer.removed_at = timezone.now()
            offer.save(update_fields=['status', 'removal_reason', 'removed_by', 'removed_at'])
            
            return {
                'offer_id': offer_id,
                'status': offer.status,
                'reason': reason,
                'removed_at': offer.removed_at.isoformat(),
                'engagements_cancelled': True,
                'conversions_rejected': True,
            }
    
    def suspend_offer(self, offer_id: int, reason: str, duration_days: int = 7,
                     suspended_by: int = None) -> Dict[str, Any]:
        """Suspend offer temporarily"""
        with transaction.atomic():
            # Get offer
            try:
                offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            except Offer.DoesNotExist:
                raise ValueError("Offer not found")
            
            # Cancel active engagements
            UserOfferEngagement.objects.filter(
                offer=offer,
                tenant_id=self.tenant_id,
                status=EngagementStatus.IN_PROGRESS
            ).update(status=EngagementStatus.CANCELLED)
            
            # Suspend offer
            offer.status = OfferStatus.SUSPENDED
            offer.suspension_reason = reason
            offer.suspended_by_id = suspended_by
            offer.suspended_at = timezone.now()
            offer.suspension_expires_at = timezone.now() + timedelta(days=duration_days)
            offer.save(update_fields=['status', 'suspension_reason', 'suspended_by', 'suspended_at', 'suspension_expires_at'])
            
            return {
                'offer_id': offer_id,
                'status': offer.status,
                'reason': reason,
                'suspended_at': offer.suspended_at.isoformat(),
                'expires_at': offer.suspension_expires_at.isoformat(),
                'engagements_cancelled': True,
            }
    
    def restore_offer(self, offer_id: int, restored_by: int = None) -> Dict[str, Any]:
        """Restore suspended offer"""
        with transaction.atomic():
            # Get offer
            try:
                offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            except Offer.DoesNotExist:
                raise ValueError("Offer not found")
            
            if offer.status not in [OfferStatus.SUSPENDED, OfferStatus.REMOVED]:
                raise ValueError("Offer is not suspended or removed")
            
            # Restore offer
            offer.status = OfferStatus.ACTIVE
            offer.restored_by_id = restored_by
            offer.restored_at = timezone.now()
            offer.save(update_fields=['status', 'restored_by', 'restored_at'])
            
            return {
                'offer_id': offer_id,
                'status': offer.status,
                'restored_at': offer.restored_at.isoformat(),
            }


# ==================== SANCTION ANALYTICS ====================

class SanctionAnalytics(BaseSanctionManager):
    """Analytics for sanctions"""
    
    def get_sanction_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get sanction statistics"""
        start_date = timezone.now() - timedelta(days=days)
        
        # This would typically query a Sanction model
        # For now, return placeholder data
        
        return {
            'period_days': days,
            'total_sanctions': 0,
            'user_sanctions': 0,
            'ip_blacklists': 0,
            'offer_removals': 0,
            'sanctions_by_type': {},
            'sanctions_by_severity': {},
            'daily_sanctions': [],
        }
    
    def get_user_sanction_history(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's sanction history"""
        # This would typically query a Sanction model
        return []
    
    def get_ip_sanction_history(self, ip_address: str) -> List[Dict[str, Any]]:
        """Get IP's sanction history"""
        # This would typically query BlacklistedIP model
        return []


# ==================== SANCTION UTILITIES ====================

class SanctionUtils:
    """Utility functions for sanctions"""
    
    @staticmethod
    def is_more_severe(existing_type: str, new_type: str) -> bool:
        """Check if existing sanction is more severe than new one"""
        severity_order = [
            SanctionType.WARNING,
            SanctionType.VERIFICATION_REQUIRED,
            SanctionType.PAYMENT_HOLD,
            SanctionType.WALLET_FREEZE,
            SanctionType.TEMPORARY_SUSPENSION,
            SanctionType.PERMANENT_BAN,
        ]
        
        try:
            existing_index = severity_order.index(existing_type)
            new_index = severity_order.index(new_type)
            return existing_index > new_index
        except ValueError:
            return False
    
    @staticmethod
    def get_sanction_duration(sanction_type: str) -> Optional[int]:
        """Get default duration for sanction type"""
        durations = {
            SanctionType.TEMPORARY_SUSPENSION: 7,
            SanctionType.WALLET_FREEZE: 30,
            SanctionType.IP_BLACKLIST: 90,
        }
        
        return durations.get(sanction_type)
    
    @staticmethod
    def can_apply_sanction(user_id: int, sanction_type: str) -> Tuple[bool, str]:
        """Check if sanction can be applied to user"""
        # This would check various business rules
        return True, "Sanction can be applied"


# ==================== SANCTION FACTORY ====================

class SanctionFactory:
    """Factory for creating sanction managers"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def user(self) -> UserSanctionManager:
        """Create user sanction manager"""
        return UserSanctionManager(self.tenant_id)
    
    def ip(self) -> IPSanctionManager:
        """Create IP sanction manager"""
        return IPSanctionManager(self.tenant_id)
    
    def offer(self) -> OfferSanctionManager:
        """Create offer sanction manager"""
        return OfferSanctionManager(self.tenant_id)
    
    def analytics(self) -> SanctionAnalytics:
        """Create sanction analytics manager"""
        return SanctionAnalytics(self.tenant_id)


# ==================== EXPORTS ====================

__all__ = [
    # Types and severity
    'SanctionType',
    'SanctionSeverity',
    
    # Managers
    'BaseSanctionManager',
    'UserSanctionManager',
    'IPSanctionManager',
    'OfferSanctionManager',
    'SanctionAnalytics',
    
    # Utilities
    'SanctionUtils',
    
    # Factory
    'SanctionFactory',
]
