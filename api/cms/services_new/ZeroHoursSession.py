# api/cms/services_new/ZeroHoursSession.py
"""
Zero Hours Session Management for Content Locker.

CPAlead Zero-Hours Mode: Require offer completion EVERY time user accesses content.
This service manages temporary sessions, tracking, and validation for zero-hours mode.
"""
import uuid
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List, Any
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class ZeroHoursSession:
    """
    Zero-hours mode session management.
    
    Sessions are temporary (default 30 minutes) and require offer completion
    for each access attempt. This follows CPAlead's official zero-hours mode.
    """
    
    CACHE_PREFIX = "zero_hours_session"
    DAILY_COUNT_PREFIX = "zero_hours_daily"
    DEFAULT_TIMEOUT = 30 * 60  # 30 minutes in seconds
    
    @classmethod
    def create_session(cls, locker_id: int, user_id: int = None, session_key: str = "", 
                    locker_config: Dict = None) -> str:
        """
        Create a new zero-hours mode session.
        
        Args:
            locker_id: ContentLocker ID
            user_id: Authenticated user ID (optional)
            session_key: Anonymous session key (optional)
            locker_config: Locker configuration dict
            
        Returns:
            session_id: UUID string for tracking
        """
        session_id = str(uuid.uuid4())
        
        # Set expiration based on locker config
        timeout_minutes = locker_config.get('session_timeout_minutes', 30) if locker_config else 30
        timeout_seconds = timeout_minutes * 60
        
        expires_at = timezone.now() + timedelta(seconds=timeout_seconds)
        
        session_data = {
            'session_id': session_id,
            'locker_id': locker_id,
            'user_id': user_id,
            'session_key': session_key,
            'created_at': timezone.now().isoformat(),
            'expires_at': expires_at.isoformat(),
            'offers_required': 1,
            'offers_completed': [],
            'status': 'active',
            'ip_address': None,  # Set during offer completion
            'payout_usd': Decimal('0'),
            'unique_offers_required': locker_config.get('require_unique_offers', True) if locker_config else True
        }
        
        # Store in cache with expiration
        cache_key = f"{cls.CACHE_PREFIX}_{session_id}"
        cache.set(cache_key, session_data, timeout_seconds)
        
        logger.info(f"Created zero-hours session {session_id} for locker {locker_id}")
        return session_id
    
    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict]:
        """Retrieve session data from cache."""
        cache_key = f"{cls.CACHE_PREFIX}_{session_id}"
        session_data = cache.get(cache_key)
        
        if not session_data:
            return None
        
        # Check if session has expired
        expires_at = datetime.fromisoformat(session_data['expires_at'])
        if timezone.now() > expires_at:
            cls.expire_session(session_id)
            return None
        
        return session_data
    
    @classmethod
    def update_session(cls, session_id: str, updates: Dict) -> bool:
        """Update session data in cache."""
        session = cls.get_session(session_id)
        if not session:
            return False
        
        session.update(updates)
        
        # Recalculate timeout based on remaining time
        expires_at = datetime.fromisoformat(session['expires_at'])
        remaining_seconds = max(1, int((expires_at - timezone.now()).total_seconds()))
        
        cache_key = f"{cls.CACHE_PREFIX}_{session_id}"
        cache.set(cache_key, session, remaining_seconds)
        
        return True
    
    @classmethod
    def complete_session(cls, session_id: str, lead_id: str, payout_usd: Decimal, 
                      ip_address: str = None) -> bool:
        """
        Mark session as completed with offer completion.
        
        Args:
            session_id: Session UUID
            lead_id: CPAlead lead ID from postback
            payout_usd: Payout amount in USD
            ip_address: User IP address
            
        Returns:
            success: True if session was completed successfully
        """
        session = cls.get_session(session_id)
        if not session:
            logger.warning(f"Attempted to complete non-existent session {session_id}")
            return False
        
        # Check if offer already completed
        if lead_id in session.get('offers_completed', []):
            logger.warning(f"Duplicate offer completion for session {session_id}, lead_id {lead_id}")
            return False
        
        # Update session with completion data
        updates = {
            'offers_completed': session.get('offers_completed', []) + [lead_id],
            'payout_usd': session.get('payout_usd', Decimal('0')) + payout_usd,
            'ip_address': ip_address,
            'status': 'completed'
        }
        
        success = cls.update_session(session_id, updates)
        
        if success:
            # Update daily unlock count
            user_id = session.get('user_id')
            locker_id = session.get('locker_id')
            if user_id:
                cls.increment_daily_count(user_id, locker_id)
            
            # Log completion for analytics
            cls.log_session_completion(session_id, session, lead_id, payout_usd)
            
            logger.info(f"Completed zero-hours session {session_id} with payout {payout_usd}")
        
        return success
    
    @classmethod
    def expire_session(cls, session_id: str) -> bool:
        """Mark session as expired."""
        session = cls.get_session(session_id)
        if not session:
            return False
        
        updates = {'status': 'expired'}
        success = cls.update_session(session_id, updates)
        
        if success:
            # Log expiration for analytics
            cls.log_session_expiration(session_id, session)
            logger.info(f"Expired zero-hours session {session_id}")
        
        return success
    
    @classmethod
    def get_active_session(cls, user_identifier: str, locker_id: int) -> Optional[str]:
        """
        Get active session for user/locker combination.
        
        Args:
            user_identifier: User ID or session key
            locker_id: ContentLocker ID
            
        Returns:
            session_id: Active session UUID or None
        """
        # This would require a more complex cache structure for production
        # For now, we'll use a simple approach with user-locker mapping
        mapping_key = f"{cls.CACHE_PREFIX}_active_{user_identifier}_{locker_id}"
        session_id = cache.get(mapping_key)
        
        if session_id:
            # Verify session is still active
            session = cls.get_session(session_id)
            if session and session.get('status') == 'active':
                return session_id
            else:
                # Clean up invalid mapping
                cache.delete(mapping_key)
        
        return None
    
    @classmethod
    def set_active_session(cls, user_identifier: str, locker_id: int, session_id: str):
        """Set active session mapping for user/locker."""
        # Get session to determine timeout
        session = cls.get_session(session_id)
        if not session:
            return
        
        expires_at = datetime.fromisoformat(session['expires_at'])
        timeout_seconds = max(1, int((expires_at - timezone.now()).total_seconds()))
        
        mapping_key = f"{cls.CACHE_PREFIX}_active_{user_identifier}_{locker_id}"
        cache.set(mapping_key, session_id, timeout_seconds)
    
    @classmethod
    def get_daily_unlock_count(cls, user_id: int, locker_id: int) -> int:
        """Get number of unlocks for user today."""
        today = timezone.now().strftime('%Y-%m-%d')
        count_key = f"{cls.DAILY_COUNT_PREFIX}_{user_id}_{locker_id}_{today}"
        return cache.get(count_key, 0)
    
    @classmethod
    def increment_daily_count(cls, user_id: int, locker_id: int):
        """Increment daily unlock count for user."""
        today = timezone.now().strftime('%Y-%m-%d')
        count_key = f"{cls.DAILY_COUNT_PREFIX}_{user_id}_{locker_id}_{today}"
        
        # Use cache.incr for atomic increment
        try:
            current = cache.incr(count_key)
            if current == 1:  # First increment, set expiration
                cache.expire(count_key, 24 * 3600)  # 24 hours
        except:
            # Fallback if cache.incr not available
            current = cache.get(count_key, 0) + 1
            cache.set(count_key, current, 24 * 3600)
    
    @classmethod
    def validate_offer_completion(cls, session_id: str, lead_id: str, offer_id: str = None) -> Dict:
        """
        Validate offer completion for zero-hours session.
        
        Returns:
            {
                'valid': bool,
                'reason': str,
                'session_data': dict,
                'reward_multiplier': Decimal
            }
        """
        session = cls.get_session(session_id)
        if not session:
            return {'valid': False, 'reason': 'session_not_found', 'session_data': None, 'reward_multiplier': Decimal('1.0')}
        
        if session.get('status') != 'active':
            return {'valid': False, 'reason': f'session_not_active: {session.get("status")}', 
                    'session_data': session, 'reward_multiplier': Decimal('1.0')}
        
        # Check for duplicate offer completion
        if session.get('unique_offers_required', True) and lead_id in session.get('offers_completed', []):
            return {'valid': False, 'reason': 'duplicate_offer', 
                    'session_data': session, 'reward_multiplier': Decimal('1.0')}
        
        # Check if offer already completed in this session
        if offer_id and offer_id in session.get('completed_offer_ids', []):
            return {'valid': False, 'reason': 'duplicate_offer_in_session', 
                    'session_data': session, 'reward_multiplier': Decimal('1.0')}
        
        return {'valid': True, 'reason': 'valid', 
                'session_data': session, 'reward_multiplier': Decimal('1.0')}
    
    @classmethod
    def log_session_completion(cls, session_id: str, session_data: Dict, lead_id: str, payout_usd: Decimal):
        """Log session completion for analytics."""
        try:
            from ..models_new.cpalead import ZeroHoursSessionLog
            
            ZeroHoursSessionLog.objects.create(
                session_id=session_id,
                locker_id=session_data.get('locker_id'),
                user_id=session_data.get('user_id'),
                session_key=session_data.get('session_key'),
                started_at=datetime.fromisoformat(session_data.get('created_at')),
                completed_at=timezone.now(),
                offers_required=session_data.get('offers_required', 1),
                offers_completed=session_data.get('offers_completed', []),
                total_payout_usd=payout_usd,
                status='completed',
                ip_address=session_data.get('ip_address'),
                metadata={
                    'lead_id': lead_id,
                    'unique_offers_required': session_data.get('unique_offers_required', True)
                }
            )
        except Exception as e:
            logger.error(f"Failed to log session completion: {e}")
    
    @classmethod
    def log_session_expiration(cls, session_id: str, session_data: Dict):
        """Log session expiration for analytics."""
        try:
            from ..models_new.cpalead import ZeroHoursSessionLog
            
            ZeroHoursSessionLog.objects.create(
                session_id=session_id,
                locker_id=session_data.get('locker_id'),
                user_id=session_data.get('user_id'),
                session_key=session_data.get('session_key'),
                started_at=datetime.fromisoformat(session_data.get('created_at')),
                completed_at=None,
                offers_required=session_data.get('offers_required', 1),
                offers_completed=session_data.get('offers_completed', []),
                total_payout_usd=Decimal('0'),
                status='expired',
                ip_address=session_data.get('ip_address'),
                metadata={
                    'reason': 'timeout',
                    'unique_offers_required': session_data.get('unique_offers_required', True)
                }
            )
        except Exception as e:
            logger.error(f"Failed to log session expiration: {e}")
    
    @classmethod
    def cleanup_expired_sessions(cls):
        """Clean up expired sessions (call from management command)."""
        # This would be called by a cron job to clean up database logs
        # Cache entries auto-expire, so no need to clean those
        pass
    
    @classmethod
    def get_session_stats(cls, user_id: int = None, locker_id: int = None, 
                        days: int = 7) -> Dict:
        """
        Get session statistics for analytics.
        
        Returns:
            {
                'total_sessions': int,
                'completed_sessions': int,
                'expired_sessions': int,
                'total_payout': Decimal,
                'average_payout': Decimal,
                'completion_rate': float
            }
        """
        try:
            from ..models_new.cpalead import ZeroHoursSessionLog
            from django.db.models import Q, Count, Sum, Avg
            
            # Build query filters
            filters = Q(started_at__gte=timezone.now() - timedelta(days=days))
            if user_id:
                filters &= Q(user_id=user_id)
            if locker_id:
                filters &= Q(locker_id=locker_id)
            
            # Get aggregated stats
            stats = ZeroHoursSessionLog.objects.filter(filters).aggregate(
                total_sessions=Count('id'),
                completed_sessions=Count('id', filter=Q(status='completed')),
                expired_sessions=Count('id', filter=Q(status='expired')),
                total_payout=Sum('total_payout_usd'),
                average_payout=Avg('total_payout_usd')
            )
            
            completed = stats['completed_sessions'] or 0
            total = stats['total_sessions'] or 0
            completion_rate = (completed / total * 100) if total > 0 else 0
            
            return {
                'total_sessions': total,
                'completed_sessions': completed,
                'expired_sessions': stats['expired_sessions'] or 0,
                'total_payout': stats['total_payout'] or Decimal('0'),
                'average_payout': stats['average_payout'] or Decimal('0'),
                'completion_rate': round(completion_rate, 2)
            }
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {
                'total_sessions': 0, 'completed_sessions': 0, 'expired_sessions': 0,
                'total_payout': Decimal('0'), 'average_payout': Decimal('0'), 'completion_rate': 0
            }
