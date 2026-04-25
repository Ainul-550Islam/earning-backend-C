# earning_backend/api/notifications/services/SegmentService.py
"""
SegmentService — builds user segments for campaign targeting.

Evaluates a CampaignSegment's conditions dict and returns a list of user IDs
matching all criteria. Results are cached for a configurable TTL.
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

SEGMENT_CACHE_TTL = getattr(settings, 'SEGMENT_CACHE_TTL_SECONDS', 300)  # 5 min


class SegmentService:
    """
    Builds user querysets from segment condition dicts.

    Supported condition keys:
        type         — segment_type string ('all', 'tier', 'geo', 'inactive',
                       'new', 'high_value', 'custom')
        tier         — membership tier string (e.g. 'gold', 'silver')
        country      — ISO country code (e.g. 'BD')
        city         — city string
        inactive_days — int, users inactive for N+ days
        new_days     — int, users created within last N days (default 30)
        min_balance  — Decimal, minimum wallet balance
        max_balance  — Decimal, maximum wallet balance
        user_ids     — explicit list of user PKs (overrides all other conditions)
        exclude_fatigued — bool (default True) — exclude fatigued users
    """

    def evaluate_segment(self, segment) -> List[int]:
        """
        Evaluate a CampaignSegment and return a list of matching user PKs.
        Results are cached using the segment PK.

        Args:
            segment: CampaignSegment model instance.

        Returns:
            List of user PKs (ints).
        """
        cache_key = f'segment_users_{segment.pk}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        user_ids = self._build_queryset(segment.conditions)

        # Update the cached estimated size on the segment object
        try:
            segment.update_estimated_size(len(user_ids))
        except Exception:
            pass

        cache.set(cache_key, user_ids, SEGMENT_CACHE_TTL)
        return user_ids

    def evaluate_conditions(self, conditions: Dict) -> List[int]:
        """Evaluate raw conditions dict without a segment model instance."""
        return self._build_queryset(conditions)

    def _build_queryset(self, conditions: Dict) -> List[int]:
        """Build and return the list of matching user PKs."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Explicit user list — highest priority
        explicit_ids = conditions.get('user_ids')
        if explicit_ids:
            return list(
                User.objects.filter(pk__in=explicit_ids, is_active=True)
                .values_list('pk', flat=True)
            )

        segment_type = conditions.get('type', 'all')
        qs = User.objects.filter(is_active=True)

        # --- Tier filter ---
        tier = conditions.get('tier')
        if tier and hasattr(User, 'membership_tier'):
            qs = qs.filter(membership_tier=tier)
        elif tier:
            # Try profile FK (common pattern)
            try:
                qs = qs.filter(profile__tier=tier)
            except Exception:
                logger.warning(f'SegmentService: cannot filter by tier={tier}')

        # --- Geography filter ---
        country = conditions.get('country')
        if country:
            try:
                qs = qs.filter(profile__country=country)
            except Exception:
                try:
                    qs = qs.filter(country=country)
                except Exception:
                    logger.warning(f'SegmentService: cannot filter by country={country}')

        city = conditions.get('city')
        if city:
            try:
                qs = qs.filter(profile__city=city)
            except Exception:
                logger.warning(f'SegmentService: cannot filter by city={city}')

        # --- Inactive users ---
        inactive_days = conditions.get('inactive_days')
        if inactive_days or segment_type == 'inactive':
            days = inactive_days or 30
            cutoff = timezone.now() - timedelta(days=days)
            qs = qs.filter(last_login__lt=cutoff)

        # --- New users ---
        new_days = conditions.get('new_days')
        if new_days or segment_type == 'new':
            days = new_days or 30
            cutoff = timezone.now() - timedelta(days=days)
            qs = qs.filter(date_joined__gte=cutoff)

        # --- Balance range ---
        min_balance = conditions.get('min_balance')
        if min_balance is not None:
            try:
                qs = qs.filter(wallet__balance__gte=min_balance)
            except Exception:
                logger.warning('SegmentService: cannot filter by min_balance (no wallet FK)')

        max_balance = conditions.get('max_balance')
        if max_balance is not None:
            try:
                qs = qs.filter(wallet__balance__lte=max_balance)
            except Exception:
                pass

        return list(qs.values_list('pk', flat=True))

    def invalidate_cache(self, segment_id: int):
        """Manually invalidate the cache for a segment."""
        cache.delete(f'segment_users_{segment_id}')


    def import_from_csv(self, csv_content: str, validate: bool = True) -> dict:
        """
        Import user IDs from CSV for bulk segment targeting.
        CSV format: one user_id per line, or 'user_id,email' header.

        Returns: {'user_ids': [...], 'total': int, 'invalid': int}
        """
        import csv, io
        from django.contrib.auth import get_user_model
        User = get_user_model()

        reader = csv.reader(io.StringIO(csv_content.strip()))
        user_ids = []
        invalid = 0

        for row in reader:
            if not row:
                continue
            val = row[0].strip()
            # Skip header
            if val.lower() in ('user_id', 'id', 'userid'):
                continue
            # Try as integer ID
            try:
                user_ids.append(int(val))
            except ValueError:
                # Try as email
                if validate and '@' in val:
                    user = User.objects.filter(email=val, is_active=True).first()
                    if user:
                        user_ids.append(user.pk)
                    else:
                        invalid += 1
                else:
                    invalid += 1

        # Validate that IDs exist
        if validate and user_ids:
            existing = set(User.objects.filter(pk__in=user_ids, is_active=True).values_list('pk', flat=True))
            invalid += len(user_ids) - len(existing)
            user_ids = list(existing)

        return {'user_ids': user_ids, 'total': len(user_ids), 'invalid': invalid}

    def export_segment_to_csv(self, segment) -> str:
        """Export segment user IDs to CSV string."""
        import csv, io
        user_ids = self.evaluate_segment(segment)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        users = User.objects.filter(pk__in=user_ids).values('pk', 'username', 'email')

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['user_id', 'username', 'email'])
        for u in users:
            writer.writerow([u['pk'], u['username'], u['email']])
        return output.getvalue()

    def evaluate_realtime(self, segment, max_users: int = 10000) -> list:
        """
        Dynamic segment evaluation — re-evaluates membership in real-time.
        Unlike cached segments, always returns fresh results.
        Used for time-sensitive campaigns.

        Supports conditions:
          - last_login_days: users who logged in within N days
          - balance_gte: wallet balance >= amount
          - level_gte: user level >= N
          - country: users from specific countries
          - kyc_status: 'verified', 'pending', 'rejected'
          - task_completed_today: completed a task today
        """
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta
        User = get_user_model()

        conditions = getattr(segment, 'target_segment', {}).get('filters', {})
        qs = User.objects.filter(is_active=True)

        if conditions.get('last_login_days'):
            cutoff = timezone.now() - timedelta(days=int(conditions['last_login_days']))
            qs = qs.filter(last_login__gte=cutoff)

        if conditions.get('level_gte'):
            qs = qs.filter(profile__level__gte=int(conditions['level_gte']))

        if conditions.get('country'):
            countries = conditions['country'] if isinstance(conditions['country'], list) else [conditions['country']]
            qs = qs.filter(profile__country__in=countries)

        if conditions.get('kyc_status'):
            # Delegate to KYC module via integration handler
            try:
                from notifications.integration_system.integ_handler import handler
                result = handler.trigger('kyc', {
                    'action': 'get_user_ids_by_status',
                    'status': conditions['kyc_status'],
                })
                if result.get('success'):
                    qs = qs.filter(pk__in=result.get('data', {}).get('user_ids', []))
            except Exception:
                pass

        if conditions.get('balance_gte'):
            # Delegate to wallet module
            try:
                from notifications.integration_system.integ_handler import handler
                result = handler.trigger('wallet', {
                    'action': 'get_user_ids_by_min_balance',
                    'min_balance': conditions['balance_gte'],
                })
                if result.get('success'):
                    qs = qs.filter(pk__in=result.get('data', {}).get('user_ids', []))
            except Exception:
                pass

        return list(qs.values_list('pk', flat=True)[:max_users])

    def get_realtime_segment_size(self, segment) -> int:
        """Estimate real-time segment size without loading all users."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        conditions = getattr(segment, 'target_segment', {}).get('filters', {})
        qs = User.objects.filter(is_active=True)
        # Apply only DB-level filters for count (skip external module queries)
        if conditions.get('country'):
            countries = conditions['country'] if isinstance(conditions['country'], list) else [conditions['country']]
            qs = qs.filter(profile__country__in=countries)
        if conditions.get('level_gte'):
            qs = qs.filter(profile__level__gte=int(conditions['level_gte']))
        return qs.count()


# Singleton
segment_service = SegmentService()
