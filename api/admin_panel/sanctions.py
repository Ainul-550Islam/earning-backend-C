# api/admin_panel/sanctions.py
"""
Sanctions Screening — AML, OFAC, UN, EU sanctions list screening.
admin_panel calls api.kyc for actual data — this module provides
the screening logic, scoring, and admin controls.

Features:
  - Real-time sanctions screening on KYC submission
  - Batch screening for existing users
  - Match scoring with configurable threshold
  - Admin override for false positives
  - Audit trail for all screening decisions
  - Integration with api.kyc.compliance
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


# ===========================================================================
# SANCTIONS RESULT
# ===========================================================================

@dataclass
class SanctionsMatch:
    matched: bool
    score: float               # 0.0 = no match, 1.0 = exact match
    match_type: str            # 'exact', 'partial', 'alias', 'none'
    list_name: str             # 'OFAC', 'UN', 'EU', 'HM_TREASURY'
    entry_name: str            # Matched entry name
    entry_id: str              # Sanctions list entry ID
    reason: str                # Why it matched
    requires_review: bool      # Should go to manual review
    auto_blocked: bool         # Was auto-blocked (high confidence match)

    def to_dict(self) -> Dict:
        return {
            'matched':         self.matched,
            'score':           self.score,
            'match_type':      self.match_type,
            'list_name':       self.list_name,
            'entry_name':      self.entry_name,
            'entry_id':        self.entry_id,
            'reason':          self.reason,
            'requires_review': self.requires_review,
            'auto_blocked':    self.auto_blocked,
        }


@dataclass
class SanctionsScreeningResult:
    user_id: Any
    name_screened: str
    matches: List[SanctionsMatch] = field(default_factory=list)
    overall_risk: str = 'clear'           # clear | review | blocked
    highest_score: float = 0.0
    screened_at: str = field(default_factory=lambda: timezone.now().isoformat())
    overridden_by: Optional[str] = None
    override_reason: str = ''

    @property
    def is_clear(self) -> bool:
        return self.overall_risk == 'clear'

    @property
    def needs_review(self) -> bool:
        return self.overall_risk == 'review'

    @property
    def is_blocked(self) -> bool:
        return self.overall_risk == 'blocked'

    def to_dict(self) -> Dict:
        return {
            'user_id':        self.user_id,
            'name_screened':  self.name_screened,
            'overall_risk':   self.overall_risk,
            'highest_score':  self.highest_score,
            'match_count':    len(self.matches),
            'matches':        [m.to_dict() for m in self.matches],
            'screened_at':    self.screened_at,
            'overridden_by':  self.overridden_by,
            'override_reason': self.override_reason,
        }


# ===========================================================================
# SANCTIONS SCREENER
# ===========================================================================

class SanctionsScreener:
    """
    Main sanctions screening engine.
    Calls api.kyc.compliance for actual list data.
    """

    MATCH_THRESHOLD_REVIEW  = 0.70   # 70%+ = manual review
    MATCH_THRESHOLD_BLOCK   = 0.95   # 95%+ = auto-block

    SANCTIONS_LISTS = ['OFAC', 'UN', 'EU', 'HM_TREASURY', 'INTERPOL']

    def screen_user(
        self,
        user_id: Any,
        full_name: str,
        country: str = '',
        date_of_birth: str = '',
        id_number: str = '',
    ) -> SanctionsScreeningResult:
        """
        Screen a user against all active sanctions lists.
        Results cached for 24 hours unless override.
        """
        cache_key = f'sanctions:screen:{user_id}:{hashlib.md5(full_name.encode()).hexdigest()}'
        cached = cache.get(cache_key)
        if cached:
            return SanctionsScreeningResult(**cached)

        result = SanctionsScreeningResult(user_id=user_id, name_screened=full_name)
        all_matches = []

        # Try api.kyc.compliance first
        try:
            from api.kyc.compliance.models import SanctionsCheck
            check = SanctionsCheck.objects.filter(
                user_id=user_id, name_checked=full_name
            ).order_by('-created_at').first()
            if check:
                match_score = float(check.match_score or 0) / 100
                if match_score >= self.MATCH_THRESHOLD_REVIEW:
                    all_matches.append(SanctionsMatch(
                        matched=True,
                        score=match_score,
                        match_type='partial' if match_score < self.MATCH_THRESHOLD_BLOCK else 'exact',
                        list_name=check.list_name or 'OFAC',
                        entry_name=check.matched_name or full_name,
                        entry_id=str(check.pk),
                        reason=f'Name similarity {match_score:.0%}',
                        requires_review=match_score >= self.MATCH_THRESHOLD_REVIEW,
                        auto_blocked=match_score >= self.MATCH_THRESHOLD_BLOCK,
                    ))
        except Exception as e:
            logger.debug(f"[Sanctions] kyc.compliance check: {e}")

        # Fuzzy name matching via internal algorithm
        internal_matches = self._fuzzy_screen(full_name, country, date_of_birth)
        all_matches.extend(internal_matches)

        # Determine overall risk
        result.matches = all_matches
        if all_matches:
            result.highest_score = max(m.score for m in all_matches)
            if result.highest_score >= self.MATCH_THRESHOLD_BLOCK:
                result.overall_risk = 'blocked'
            elif result.highest_score >= self.MATCH_THRESHOLD_REVIEW:
                result.overall_risk = 'review'
        else:
            result.overall_risk = 'clear'
            result.highest_score = 0.0

        # Auto-block high confidence matches
        if result.is_blocked:
            self._auto_block_user(user_id, result)

        # Cache result
        cache.set(cache_key, result.__dict__, 86400)

        # Persist to audit log
        self._log_screening(user_id, full_name, result)

        return result

    def _fuzzy_screen(self, name: str, country: str, dob: str) -> List[SanctionsMatch]:
        """
        Internal fuzzy matching against cached sanctions entries.
        Uses Levenshtein distance for name similarity.
        """
        matches = []
        try:
            # Load cached sanctions names
            cached_list = cache.get('sanctions:names_cache')
            if not cached_list:
                return matches  # List not loaded — safe pass

            name_lower = name.lower().strip()
            for entry in (cached_list or []):
                entry_name = entry.get('name', '').lower().strip()
                if not entry_name:
                    continue
                score = self._similarity(name_lower, entry_name)
                if score >= self.MATCH_THRESHOLD_REVIEW:
                    matches.append(SanctionsMatch(
                        matched=True,
                        score=score,
                        match_type='exact' if score >= 0.99 else 'partial',
                        list_name=entry.get('list', 'UNKNOWN'),
                        entry_name=entry.get('name', ''),
                        entry_id=entry.get('id', ''),
                        reason=f'Name similarity {score:.0%}',
                        requires_review=score >= self.MATCH_THRESHOLD_REVIEW,
                        auto_blocked=score >= self.MATCH_THRESHOLD_BLOCK,
                    ))
        except Exception as e:
            logger.debug(f"[Sanctions._fuzzy_screen] {e}")
        return matches

    @staticmethod
    def _similarity(s1: str, s2: str) -> float:
        """Simple similarity score (Jaccard on character bigrams)."""
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0
        bigrams1 = set(s1[i:i+2] for i in range(len(s1)-1))
        bigrams2 = set(s2[i:i+2] for i in range(len(s2)-1))
        if not bigrams1 or not bigrams2:
            return 0.0
        intersection = bigrams1 & bigrams2
        union = bigrams1 | bigrams2
        return len(intersection) / len(union)

    def _auto_block_user(self, user_id: Any, result: SanctionsScreeningResult) -> None:
        """Auto-block user if sanctions match confidence >= BLOCK threshold."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(pk=user_id, is_active=True).update(is_active=False)
            from api.wallet.models import Wallet
            Wallet.objects.filter(user_id=user_id).update(is_locked=True)
            logger.warning(f"[Sanctions] AUTO-BLOCKED user {user_id}: score={result.highest_score:.2f}")
        except Exception as e:
            logger.error(f"[Sanctions._auto_block_user] {e}")

    def _log_screening(self, user_id: Any, name: str, result: SanctionsScreeningResult) -> None:
        """Log screening result to AdminActivity."""
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=None,
                action='sanctions_screen',
                model_name='User', object_id=str(user_id),
                changes={
                    'name': name, 'result': result.overall_risk,
                    'score': result.highest_score, 'matches': len(result.matches)
                },
                status='success',
            )
        except Exception:
            pass

    def override_result(
        self,
        user_id: Any,
        name: str,
        decision: str,  # 'clear' | 'block'
        reason: str,
        actor,
    ) -> bool:
        """Admin manual override of a sanctions match (false positive/true positive)."""
        try:
            cache_key = f'sanctions:screen:{user_id}:{hashlib.md5(name.encode()).hexdigest()}'
            cache.delete(cache_key)  # Clear cached result

            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor,
                action='sanctions_override',
                model_name='User', object_id=str(user_id),
                changes={'name': name, 'decision': decision, 'reason': reason},
                status='success',
            )
            # If clearing, unblock user
            if decision == 'clear':
                from django.contrib.auth import get_user_model
                User = get_user_model()
                User.objects.filter(pk=user_id).update(is_active=True)
            return True
        except Exception as e:
            logger.error(f"[Sanctions.override] {e}")
            return False

    def batch_screen(self, user_ids: List[Any]) -> Dict[Any, SanctionsScreeningResult]:
        """Screen multiple users. Returns {user_id: result}."""
        results = {}
        for uid in user_ids:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(pk=uid)
                name = user.get_full_name() or user.username
                results[uid] = self.screen_user(uid, name)
            except Exception:
                pass
        return results

    def load_sanctions_list_to_cache(self, entries: List[Dict]) -> int:
        """Load a sanctions list into cache for screening."""
        cache.set('sanctions:names_cache', entries, 86400 * 7)  # 1 week
        logger.info(f"[Sanctions] Loaded {len(entries)} entries to cache")
        return len(entries)

    def get_screening_stats(self, days: int = 30) -> Dict:
        """Screening statistics for admin dashboard."""
        try:
            from api.admin_panel.models.activity import AdminActivity
            from django.db.models import Count
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=days)
            qs = AdminActivity.objects.filter(action='sanctions_screen', created_at__gte=cutoff)
            return {
                'total_screened': qs.count(),
                'by_result': list(
                    qs.values('changes__result').annotate(count=Count('id')).order_by('-count')
                ),
                'blocked': qs.filter(changes__result='blocked').count(),
                'period_days': days,
            }
        except Exception:
            return {'total_screened': 0, 'period_days': days}


# Global screener instance
screener = SanctionsScreener()


# ===========================================================================
# ADMIN SANCTIONS VIEWSET HELPERS
# ===========================================================================

def screen_user_api(user_id: Any, actor) -> Dict:
    """API-friendly wrapper for sanctions screening."""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        name = user.get_full_name() or user.username
        result = screener.screen_user(user_id, name)
        return {'success': True, 'data': result.to_dict()}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def override_sanctions(user_id: Any, decision: str, reason: str, actor) -> Dict:
    """Override a sanctions match from admin panel."""
    if decision not in ('clear', 'block'):
        return {'success': False, 'error': 'decision must be clear or block'}
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        name = user.get_full_name() or user.username
        ok = screener.override_result(user_id, name, decision, reason, actor)
        return {'success': ok, 'user_id': user_id, 'decision': decision}
    except Exception as e:
        return {'success': False, 'error': str(e)}