# api/referral/INTEGRATION_SYSTEM/sync_manager.py
# Data sync & conflict resolver between referral and other modules
# Fixes duplicate data issues across offer_inventory, promotions, users
# ============================================================

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone
from .integ_exceptions import SyncConflictError

logger = logging.getLogger(__name__)


class ReferralSyncManager:
    """
    Resolves data conflicts between referral module and other modules.

    Known conflicts in your project:
    1. offer_inventory.UserReferral  ↔  referral.Referral (duplicate)
    2. promotions.ReferralCommissionLog ↔ referral.CommissionLog (duplicate)
    3. promotions/referral_manager.py (cache-based tree) ↔ referral.ReferralTree (DB)
    4. users.User.referral_earnings ↔ referral.ReferralEarning (sum mismatch)
    """

    # ── Conflict Detection ────────────────────────────────────────────────────

    def detect_conflicts(self) -> Dict:
        """Scan for all data conflicts across modules."""
        report = {
            'timestamp': timezone.now().isoformat(),
            'conflicts': {},
            'total_conflicts': 0,
        }

        report['conflicts']['duplicate_referrals'] = self._detect_duplicate_referrals()
        report['conflicts']['commission_mismatch']  = self._detect_commission_mismatch()
        report['conflicts']['user_earning_mismatch'] = self._detect_user_earning_mismatch()
        report['conflicts']['orphan_commissions']  = self._detect_orphan_commissions()

        report['total_conflicts'] = sum(
            c.get('count', 0) for c in report['conflicts'].values()
        )
        return report

    def _detect_duplicate_referrals(self) -> Dict:
        """
        Check for users in both offer_inventory.UserReferral AND referral.Referral.
        """
        try:
            from api.referral.models import Referral
            from api.offer_inventory.models import UserReferral

            referral_pairs = set(
                Referral.objects.values_list('referrer_id', 'referred_user_id')
            )
            offer_pairs = set(
                UserReferral.objects.values_list('referrer_id', 'referred_id')
            )
            duplicates = referral_pairs & offer_pairs
            return {
                'count': len(duplicates),
                'referral_total': len(referral_pairs),
                'offer_inventory_total': len(offer_pairs),
                'status': 'conflict' if duplicates else 'ok',
            }
        except Exception as e:
            return {'count': 0, 'error': str(e), 'status': 'unknown'}

    def _detect_commission_mismatch(self) -> Dict:
        """
        Check if referral.ReferralEarning totals match users.referral_earnings.
        """
        try:
            from django.db.models import Sum
            from api.referral.models import ReferralEarning
            from django.contrib.auth import get_user_model

            User = get_user_model()
            mismatches = 0
            checked = 0

            for user in User.objects.filter(
                referral_earnings__isnull=False
            ).exclude(referral_earnings=0)[:100]:
                db_total = ReferralEarning.objects.filter(
                    referrer=user, status='released'
                ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

                user_total = Decimal(str(user.referral_earnings or 0))
                if abs(db_total - user_total) > Decimal('0.01'):
                    mismatches += 1
                checked += 1

            return {
                'count': mismatches,
                'checked': checked,
                'status': 'conflict' if mismatches > 0 else 'ok',
            }
        except Exception as e:
            return {'count': 0, 'error': str(e), 'status': 'unknown'}

    def _detect_user_earning_mismatch(self) -> Dict:
        """Check user.total_referrals vs actual Referral count."""
        try:
            from api.referral.models import Referral
            from django.contrib.auth import get_user_model

            User = get_user_model()
            mismatches = 0
            for user in User.objects.filter(total_referrals__gt=0)[:100]:
                actual = Referral.objects.filter(referrer=user).count()
                if abs(actual - (user.total_referrals or 0)) > 0:
                    mismatches += 1
            return {
                'count': mismatches,
                'status': 'conflict' if mismatches > 0 else 'ok',
            }
        except Exception as e:
            return {'count': 0, 'error': str(e), 'status': 'unknown'}

    def _detect_orphan_commissions(self) -> Dict:
        """
        Find CommissionLog entries where the Referral no longer exists.
        """
        try:
            from api.referral.models import CommissionLog, Referral
            referral_user_ids = set(
                Referral.objects.values_list('referred_user_id', flat=True)
            )
            orphans = CommissionLog.objects.exclude(
                referred_user_id__in=referral_user_ids
            ).count()
            return {
                'count': orphans,
                'status': 'warning' if orphans > 0 else 'ok',
            }
        except Exception as e:
            return {'count': 0, 'error': str(e), 'status': 'unknown'}

    # ── Conflict Resolution ───────────────────────────────────────────────────

    @transaction.atomic
    def sync_from_offer_inventory(self, dry_run: bool = True) -> Dict:
        """
        Migrate offer_inventory.UserReferral → referral.Referral.
        This is a one-time migration to consolidate duplicate data.
        """
        try:
            from api.offer_inventory.models import UserReferral
            from api.referral.models import Referral

            migrated = 0
            skipped = 0
            errors = 0

            for ur in UserReferral.objects.select_related('referrer', 'referred').iterator():
                try:
                    exists = Referral.objects.filter(
                        referred_user=ur.referred
                    ).exists()
                    if exists:
                        skipped += 1
                        continue
                    if not dry_run:
                        Referral.objects.create(
                            referrer=ur.referrer,
                            referred_user=ur.referred,
                            level=1,
                            signup_bonus_given=True,
                        )
                    migrated += 1
                except Exception as e:
                    errors += 1
                    logger.error(f'[SyncManager] Migration error: {e}')

            return {
                'migrated': migrated, 'skipped': skipped,
                'errors': errors, 'dry_run': dry_run,
            }
        except ImportError:
            return {'error': 'offer_inventory.UserReferral not found', 'migrated': 0}

    @transaction.atomic
    def sync_user_referral_counts(self, dry_run: bool = True) -> Dict:
        """
        Recalculate user.total_referrals and user.referral_earnings
        from actual referral.Referral and referral.ReferralEarning.
        """
        from django.db.models import Sum, Count
        from api.referral.models import Referral, ReferralEarning
        from django.contrib.auth import get_user_model

        User = get_user_model()
        updated = 0
        skipped = 0

        for user in User.objects.filter(
            referral_referral_referrer__isnull=False
        ).distinct():
            referral_count = Referral.objects.filter(referrer=user).count()
            total_commission = ReferralEarning.objects.filter(
                referrer=user, status='released'
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            needs_update = (
                user.total_referrals != referral_count or
                abs(Decimal(str(user.referral_earnings or 0)) - total_commission) > Decimal('0.01')
            )

            if needs_update:
                if not dry_run:
                    User.objects.filter(id=user.id).update(
                        total_referrals=referral_count,
                        referral_earnings=total_commission,
                    )
                updated += 1
            else:
                skipped += 1

        return {
            'updated': updated, 'skipped': skipped, 'dry_run': dry_run
        }

    @transaction.atomic
    def fix_promotions_cache_tree(self) -> Dict:
        """
        Migrate promotions/referral_manager.py cache-based tree
        to proper database-backed ReferralTree.
        Reads all users and rebuilds from Referral records.
        """
        from api.referral.services.ReferralTreeService import ReferralTreeService
        from api.referral.models import Referral

        rebuilt = 0
        errors = 0
        referrer_ids = Referral.objects.values_list(
            'referrer_id', flat=True
        ).distinct()

        from django.contrib.auth import get_user_model
        User = get_user_model()

        for user in User.objects.filter(id__in=referrer_ids):
            try:
                ReferralTreeService.rebuild_tree(user)
                rebuilt += 1
            except Exception as e:
                errors += 1
                logger.error(f'[SyncManager] Tree rebuild failed for {user.id}: {e}')

        return {'rebuilt': rebuilt, 'errors': errors}

    # ── Periodic Sync ─────────────────────────────────────────────────────────

    def run_periodic_sync(self) -> Dict:
        """
        Run all non-destructive syncs.
        Called by Celery beat — safe to run daily.
        """
        results = {}
        results['user_counts'] = self.sync_user_referral_counts(dry_run=False)
        results['conflicts_detected'] = self.detect_conflicts()
        logger.info(f'[SyncManager] Periodic sync complete: {results}')
        return results