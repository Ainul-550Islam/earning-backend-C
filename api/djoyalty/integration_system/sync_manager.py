# api/djoyalty/integration_system/sync_manager.py
"""
Sync Manager -- Data Conflict Resolver।
Handles data synchronization between Djoyalty and external systems।
Resolves conflicts when data diverges between server/client/partner।

World reference: CQRS pattern for Django microservices।
Use cases:
  - Partner merchant sync (points balance after coalition earn)
  - Family account points pool sync
  - Multi-device customer session sync
  - Webhook retry reconciliation
"""
import logging
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from django.db import transaction
from django.utils import timezone
from .integ_constants import SYNC_CONFLICT_RESOLUTION, SYNC_MAX_DRIFT_SECONDS
from .integ_exceptions import DataSyncConflictError, SyncLockError

logger = logging.getLogger(__name__)


class SyncConflict:
    """Represents a data sync conflict।"""
    def __init__(self, model: str, object_id, field: str,
                  server_value, client_value, resolution: str = ''):
        self.model = model
        self.object_id = object_id
        self.field = field
        self.server_value = server_value
        self.client_value = client_value
        self.resolution = resolution
        self.detected_at = timezone.now()

    def to_dict(self) -> dict:
        return {
            'model': self.model,
            'object_id': str(self.object_id),
            'field': self.field,
            'server_value': str(self.server_value),
            'client_value': str(self.client_value),
            'resolution': self.resolution,
            'detected_at': self.detected_at.isoformat(),
        }


class SyncManager:
    """
    Data sync and conflict resolution manager।

    Conflict resolution strategies:
    - 'server_wins': Server data always takes priority (default)
    - 'client_wins': Client/partner data takes priority
    - 'latest_wins': Most recent timestamp wins
    - 'manual': Flag for human review
    - 'merge': Merge non-conflicting fields (points: take MAX)

    Usage:
        sm = SyncManager()
        # Sync points after partner earn
        sm.sync_points_balance(customer, partner_reported_balance=1500)
        # Resolve conflict
        resolved = sm.resolve_conflict(conflict, strategy='server_wins')
    """

    def __init__(self, strategy: str = SYNC_CONFLICT_RESOLUTION):
        self.strategy = strategy
        self._conflicts: list = []
        self._sync_log: list = []

    # ─── Points Sync ──────────────────────────────────────────────

    @transaction.atomic
    def sync_points_balance(self, customer, partner_reported_balance: Decimal,
                             tolerance: Decimal = Decimal('0.01'),
                             partner_name: str = '') -> Tuple[bool, Optional[SyncConflict]]:
        """
        Sync customer points balance after partner reports it।
        Returns (synced: bool, conflict: SyncConflict | None)
        """
        from ..models.points import LoyaltyPoints

        lp = LoyaltyPoints.objects.select_for_update().filter(customer=customer).first()
        if not lp:
            logger.warning('SyncManager: no LoyaltyPoints for %s', customer.code)
            return False, None

        server_balance = lp.balance
        diff = abs(server_balance - partner_reported_balance)

        if diff <= tolerance:
            logger.debug('SyncManager: points in sync for %s (diff=%s)', customer.code, diff)
            return True, None

        # Conflict detected
        conflict = SyncConflict(
            model='LoyaltyPoints',
            object_id=lp.id,
            field='balance',
            server_value=server_balance,
            client_value=partner_reported_balance,
        )

        resolved_value = self._resolve_numeric_conflict(
            server_balance, partner_reported_balance
        )

        if resolved_value != server_balance:
            old_balance = lp.balance
            lp.balance = resolved_value
            lp.save(update_fields=['balance', 'updated_at'])

            # Log the adjustment
            from ..models.points import PointsLedger
            from ..choices import LEDGER_CREDIT, LEDGER_DEBIT
            adjustment = resolved_value - old_balance
            PointsLedger.objects.create(
                customer=customer,
                tenant=customer.tenant,
                txn_type=LEDGER_CREDIT if adjustment > 0 else LEDGER_DEBIT,
                source='bonus',
                points=abs(adjustment),
                balance_after=resolved_value,
                description=f'Sync adjustment ({partner_name or "partner"}): {old_balance} -> {resolved_value}',
            )

            logger.info('SyncManager: adjusted %s balance %s -> %s (diff=%s)',
                        customer.code, old_balance, resolved_value, diff)

        conflict.resolution = self.strategy
        self._conflicts.append(conflict)
        return True, conflict

    def _resolve_numeric_conflict(self, server_val: Decimal,
                                    client_val: Decimal) -> Decimal:
        """Resolve numeric conflict based on strategy।"""
        if self.strategy == 'server_wins':
            return server_val
        elif self.strategy == 'client_wins':
            return client_val
        elif self.strategy == 'merge':
            # For points: take the higher value (conservative)
            return max(server_val, client_val)
        elif self.strategy == 'latest_wins':
            return client_val  # Assume client has latest data
        return server_val

    # ─── Partner Data Sync ────────────────────────────────────────

    @transaction.atomic
    def sync_partner_data(self, partner, partner_data: dict) -> dict:
        """
        Sync partner merchant data from external source।
        Updates earn_rate, burn_rate, status।
        """
        from ..models.campaigns import PartnerMerchant

        conflicts = []
        updates = {}

        field_map = {
            'earn_rate': ('earn_rate', Decimal),
            'burn_rate': ('burn_rate', Decimal),
            'is_active': ('is_active', bool),
        }

        for external_key, (model_field, field_type) in field_map.items():
            if external_key not in partner_data:
                continue

            client_val = field_type(partner_data[external_key])
            server_val = getattr(partner, model_field)

            if client_val != server_val:
                conflict = SyncConflict(
                    model='PartnerMerchant',
                    object_id=partner.id,
                    field=model_field,
                    server_value=server_val,
                    client_value=client_val,
                    resolution=self.strategy,
                )
                conflicts.append(conflict)

                if self.strategy != 'server_wins':
                    updates[model_field] = client_val

        if updates:
            for field, val in updates.items():
                setattr(partner, field, val)
            partner.last_sync_at = timezone.now()
            partner.save()
            logger.info('SyncManager: partner %s synced: %s', partner.name, updates)

        partner.last_sync_at = timezone.now()
        partner.save(update_fields=['last_sync_at'])

        return {
            'synced': True,
            'conflicts': [c.to_dict() for c in conflicts],
            'updates_applied': updates,
        }

    # ─── Family Account Sync ──────────────────────────────────────

    @transaction.atomic
    def sync_family_pool(self, family_account) -> dict:
        """
        Recalculate family account shared_balance from member contributions।
        Resolves any drift between recorded and actual contributions।
        """
        from ..models.family_eco import FamilyMember

        members = FamilyMember.objects.filter(
            family_account=family_account, is_active=True,
        ).select_related('customer')

        actual_pool = Decimal('0')
        for member in members:
            lp = member.customer.loyalty_points.first()
            if lp:
                actual_pool += member.points_contributed

        recorded_pool = family_account.shared_balance
        diff = abs(actual_pool - recorded_pool)

        if diff > Decimal('0.01'):
            logger.warning('SyncManager: family pool drift for %s: recorded=%s actual=%s',
                           family_account.name, recorded_pool, actual_pool)
            family_account.shared_balance = actual_pool
            family_account.save(update_fields=['shared_balance'])

        return {
            'family': family_account.name,
            'recorded': str(recorded_pool),
            'recalculated': str(actual_pool),
            'drift': str(diff),
            'synced': diff <= Decimal('0.01'),
        }

    # ─── Lock Management ──────────────────────────────────────────

    @staticmethod
    def acquire_sync_lock(resource_key: str, timeout: int = 30) -> bool:
        """
        Acquire distributed sync lock via Redis।
        Prevents concurrent sync operations on same resource।
        """
        try:
            from django.core.cache import cache
            lock_key = f'djoyalty:sync_lock:{resource_key}'
            acquired = cache.add(lock_key, '1', timeout=timeout)
            if not acquired:
                logger.warning('SyncManager: could not acquire lock for %s', resource_key)
            return acquired
        except Exception as e:
            logger.debug('SyncManager.acquire_sync_lock error: %s', e)
            return True  # Fail open if Redis unavailable

    @staticmethod
    def release_sync_lock(resource_key: str):
        """Release sync lock।"""
        try:
            from django.core.cache import cache
            cache.delete(f'djoyalty:sync_lock:{resource_key}')
        except Exception:
            pass

    # ─── Conflict Reports ─────────────────────────────────────────

    def get_conflict_report(self) -> dict:
        """Get summary of detected conflicts in this session।"""
        return {
            'total_conflicts': len(self._conflicts),
            'by_model': {},
            'by_strategy': self.strategy,
            'conflicts': [c.to_dict() for c in self._conflicts[-20:]],
        }

    @staticmethod
    def audit_points_integrity(customer=None, tenant=None) -> dict:
        """
        Full points integrity audit।
        Verifies: balance == sum(ledger credits) - sum(ledger debits)।
        """
        from ..models.points import LoyaltyPoints, PointsLedger
        from django.db.models import Sum, Q

        customers_checked = 0
        issues_found = 0
        issues = []

        qs = LoyaltyPoints.objects.all()
        if customer:
            qs = qs.filter(customer=customer)
        if tenant:
            qs = qs.filter(tenant=tenant)

        for lp in qs.select_related('customer')[:1000]:
            # Calculate balance from ledger
            credits = PointsLedger.objects.filter(
                customer=lp.customer, txn_type='credit', is_reversed=False,
            ).aggregate(total=Sum('points'))['total'] or Decimal('0')

            debits = PointsLedger.objects.filter(
                customer=lp.customer, txn_type='debit', is_reversed=False,
            ).aggregate(total=Sum('points'))['total'] or Decimal('0')

            expected = credits - debits
            actual = lp.balance
            diff = abs(expected - actual)

            customers_checked += 1

            if diff > Decimal('0.01'):
                issues_found += 1
                issues.append({
                    'customer': lp.customer.code,
                    'recorded_balance': str(actual),
                    'calculated_balance': str(expected),
                    'diff': str(diff),
                })

        return {
            'customers_checked': customers_checked,
            'issues_found': issues_found,
            'issues': issues[:10],
            'integrity_score': f'{((customers_checked - issues_found) / max(customers_checked, 1) * 100):.1f}%',
        }
