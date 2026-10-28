# api/admin_panel/INTEGRATION_SYSTEM/sync_manager.py
"""
SyncManager — Data Conflict Resolver & Cross-App Sync Coordinator.
New — resolves: data inconsistencies between apps, wallet ≠ payout records,
user status mismatch, conversion count discrepancies.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from .integ_constants import CONFLICT_STRATEGIES, DATA_BRIDGE_MODES

logger = logging.getLogger(__name__)


class SyncConflict:
    """Represents a detected data conflict between two apps."""
    def __init__(self, source_app: str, target_app: str, resource: str,
                 record_id: Any, source_data: dict, target_data: dict,
                 field: str, conflict_type: str = 'value_mismatch'):
        self.source_app = source_app
        self.target_app = target_app
        self.resource = resource
        self.record_id = record_id
        self.source_data = source_data
        self.target_data = target_data
        self.field = field
        self.conflict_type = conflict_type
        self.detected_at = timezone.now()
        self.resolved = False
        self.resolution = None

    def to_dict(self) -> Dict:
        return {
            'source_app': self.source_app,
            'target_app': self.target_app,
            'resource': self.resource,
            'record_id': str(self.record_id),
            'field': self.field,
            'source_value': self.source_data.get(self.field),
            'target_value': self.target_data.get(self.field),
            'conflict_type': self.conflict_type,
            'detected_at': self.detected_at.isoformat(),
            'resolved': self.resolved,
            'resolution': self.resolution,
        }


class SyncManager:
    """
    Manages data synchronization and conflict resolution across all apps.
    Detects and resolves: wallet mismatches, payout discrepancies, KYC inconsistencies.
    """

    def __init__(self, strategy: str = CONFLICT_STRATEGIES['LAST_WRITE_WINS']):
        self.strategy = strategy
        self._conflicts: List[SyncConflict] = []
        self._syncs_completed = 0
        self._conflicts_resolved = 0

    # ==================== WALLET SYNC ====================

    def sync_wallet_with_transactions(self, user_id: Any) -> Dict:
        """
        Recalculate wallet balance from actual transactions.
        Detects and fixes: wallet balance ≠ sum of transactions.
        """
        try:
            from api.wallet.models import Wallet, WalletTransaction
            from django.db.models import Sum

            wallet = Wallet.objects.get(user_id=user_id)
            actual_balance = WalletTransaction.objects.filter(
                wallet=wallet,
                status='completed',
            ).aggregate(total=Sum('gross_amount'))['total'] or 0

            drift = float(wallet.current_balance) - float(actual_balance)

            if abs(drift) < 0.01:  # Tolerance
                return {'success': True, 'user_id': user_id, 'drift': 0, 'action': 'no_action'}

            logger.warning(f"[SyncManager] Wallet drift for user {user_id}: {drift}")
            conflict = SyncConflict(
                source_app='wallet_transactions',
                target_app='wallet',
                resource='Wallet',
                record_id=user_id,
                source_data={'balance': float(actual_balance)},
                target_data={'balance': float(wallet.current_balance)},
                field='balance',
                conflict_type='balance_drift',
            )
            self._conflicts.append(conflict)

            # Auto-resolve: set to actual
            if abs(drift) < 100:  # Small drift: auto-fix
                wallet.current_balance = actual_balance
                wallet.save(update_fields=['balance'])
                conflict.resolved = True
                conflict.resolution = f'Auto-fixed: set to {actual_balance}'
                self._conflicts_resolved += 1
                return {'success': True, 'user_id': user_id, 'drift': drift,
                        'action': 'auto_fixed', 'new_balance': float(actual_balance)}
            else:
                # Large drift: flag for manual review
                return {'success': True, 'user_id': user_id, 'drift': drift,
                        'action': 'flagged_for_review', 'requires_manual': True}
        except Exception as e:
            logger.error(f"[SyncManager] Wallet sync failed for user {user_id}: {e}")
            return {'success': False, 'error': str(e)}

    def sync_user_status(self, user_id: Any) -> Dict:
        """
        Sync user active status across: User model, UserProfile, Wallet.
        Detects: is_active=False but wallet not frozen, profile still active.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
            fixes = []
            if not user.is_active:
                # User is banned — ensure wallet is frozen
                try:
                    from api.wallet.models import Wallet
                    count = Wallet.objects.filter(user_id=user_id, is_locked=False).update(is_locked=True)
                    if count > 0:
                        fixes.append('wallet_frozen')
                except Exception:
                    pass
                # Ensure profile status matches
                try:
                    profile = user.profile
                    if profile.account_status == 'active':
                        profile.account_status = 'banned'
                        profile.save(update_fields=['account_status'])
                        fixes.append('profile_status_updated')
                except Exception:
                    pass
            return {'success': True, 'user_id': user_id, 'fixes': fixes, 'is_active': user.is_active}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def bulk_wallet_integrity_check(self, user_ids: List[Any], auto_fix: bool = False) -> Dict:
        """Check wallet integrity for multiple users."""
        results = {'checked': 0, 'ok': 0, 'drifted': 0, 'fixed': 0, 'errors': 0, 'details': []}
        for uid in user_ids[:500]:  # Max 500
            try:
                result = self.sync_wallet_with_transactions(uid)
                results['checked'] += 1
                if result.get('drift', 0) == 0:
                    results['ok'] += 1
                else:
                    results['drifted'] += 1
                    if result.get('action') == 'auto_fixed':
                        results['fixed'] += 1
                    results['details'].append({'user_id': uid, 'drift': result.get('drift')})
            except Exception:
                results['errors'] += 1
        return results

    # ==================== PAYOUT SYNC ====================

    def sync_payout_with_wallet(self, payout_item_id: Any) -> Dict:
        """Verify payout item matches wallet transaction."""
        try:
            from api.payout_queue.models import PayoutItem
            from api.wallet.models import WalletTransaction

            item = PayoutItem.objects.get(pk=payout_item_id)
            if item.status != 'paid':
                return {'success': True, 'status': item.status, 'action': 'not_paid_yet'}

            # Verify wallet transaction exists
            tx = WalletTransaction.objects.filter(
                wallet__user=item.user,
                amount=-abs(item.gross_amount),
                reference=str(payout_item_id),
            ).first()

            if not tx:
                return {
                    'success': True,
                    'conflict': True,
                    'message': f'PayoutItem {payout_item_id} marked paid but no wallet debit found',
                    'requires_manual': True,
                }
            return {'success': True, 'conflict': False, 'payout_id': payout_item_id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== CONFLICT MANAGEMENT ====================

    def get_conflicts(self, resolved: bool = False) -> List[Dict]:
        return [c.to_dict() for c in self._conflicts if c.resolved == resolved]

    def resolve_conflict(self, conflict_index: int, strategy: Optional[str] = None) -> Dict:
        """Manually resolve a conflict."""
        if conflict_index >= len(self._conflicts):
            return {'success': False, 'error': 'Conflict not found'}
        conflict = self._conflicts[conflict_index]
        strategy = strategy or self.strategy
        conflict.resolved = True
        conflict.resolution = f'Resolved with strategy: {strategy}'
        self._conflicts_resolved += 1
        return {'success': True, 'conflict': conflict.to_dict()}

    def get_stats(self) -> Dict:
        return {
            'total_conflicts': len(self._conflicts),
            'unresolved': sum(1 for c in self._conflicts if not c.resolved),
            'resolved': self._conflicts_resolved,
            'syncs_completed': self._syncs_completed,
            'strategy': self.strategy,
        }

    def clear_resolved_conflicts(self) -> int:
        count = sum(1 for c in self._conflicts if c.resolved)
        self._conflicts = [c for c in self._conflicts if not c.resolved]
        return count


# Global sync manager
sync_manager = SyncManager()