# api/promotions/governance/penalty_manager.py
# Penalty Manager — Violations, warnings, suspensions, bans
import logging
from dataclasses import dataclass
from enum import Enum
logger = logging.getLogger('governance.penalty')

class PenaltyType(str, Enum):
    WARNING     = 'warning'
    TEMP_SUSPEND = 'temp_suspend'   # 1-30 days
    PERM_SUSPEND = 'perm_suspend'
    BAN         = 'ban'
    FINE        = 'fine'             # Wallet deduction

PENALTY_RULES = {
    'fake_screenshot':    {'type': PenaltyType.WARNING,      'escalates_to': PenaltyType.TEMP_SUSPEND, 'at': 3},
    'multi_account':      {'type': PenaltyType.TEMP_SUSPEND, 'escalates_to': PenaltyType.BAN,          'at': 2},
    'vpn_usage':          {'type': PenaltyType.WARNING,      'escalates_to': PenaltyType.TEMP_SUSPEND, 'at': 5},
    'bot_activity':       {'type': PenaltyType.BAN,          'escalates_to': PenaltyType.BAN,          'at': 1},
    'chargeback':         {'type': PenaltyType.PERM_SUSPEND, 'escalates_to': PenaltyType.BAN,          'at': 2},
    'abusive_behavior':   {'type': PenaltyType.WARNING,      'escalates_to': PenaltyType.TEMP_SUSPEND, 'at': 2},
}

@dataclass
class PenaltyResult:
    user_id:     int
    penalty:     str
    duration_days: int
    reason:      str
    fine_usd:    float = 0.0
    escalated:   bool  = False

class PenaltyManager:
    """Violation penalties — progressive enforcement।"""

    def apply_penalty(self, user_id: int, violation: str, actor_id: int = None) -> PenaltyResult:
        rule = PENALTY_RULES.get(violation)
        if not rule:
            logger.warning(f'Unknown violation type: {violation}')
            return PenaltyResult(user_id, 'unknown', 0, violation)

        violation_count = self._get_violation_count(user_id, violation) + 1
        self._record_violation(user_id, violation, actor_id)

        if violation_count >= rule['at']:
            penalty_type = rule['escalates_to']
            escalated    = True
        else:
            penalty_type = rule['type']
            escalated    = False

        duration = {'warning': 0, 'temp_suspend': 7, 'perm_suspend': 365, 'ban': 36500, 'fine': 0}.get(penalty_type.value, 0)
        self._enforce(user_id, penalty_type, duration, violation)

        logger.warning(f'Penalty: user={user_id} violation={violation} type={penalty_type.value} escalated={escalated}')
        return PenaltyResult(user_id, penalty_type.value, duration, violation, escalated=escalated)

    def check_suspended(self, user_id: int) -> bool:
        from django.core.cache import cache
        return cache.get(f'gov:suspended:{user_id}') is not None

    def lift_suspension(self, user_id: int, actor_id: int) -> None:
        from django.core.cache import cache
        cache.delete(f'gov:suspended:{user_id}')
        logger.info(f'Suspension lifted: user={user_id} by actor={actor_id}')

    def _get_violation_count(self, user_id: int, violation: str) -> int:
        try:
            from api.promotions.models import UserViolation
            return UserViolation.objects.filter(user_id=user_id, violation_type=violation).count()
        except Exception:
            return 0

    def _record_violation(self, user_id: int, violation: str, actor_id):
        try:
            from api.promotions.models import UserViolation
            UserViolation.objects.create(user_id=user_id, violation_type=violation, reported_by_id=actor_id)
        except Exception:
            pass

    def _enforce(self, user_id: int, penalty: PenaltyType, duration: int, reason: str):
        from django.core.cache import cache
        if penalty in (PenaltyType.TEMP_SUSPEND, PenaltyType.PERM_SUSPEND, PenaltyType.BAN):
            ttl = duration * 86400 if duration < 36500 else None
            cache.set(f'gov:suspended:{user_id}', {'reason': reason, 'type': penalty.value}, timeout=ttl)
        try:
            from api.promotions.models import UserReputation
            from django.utils import timezone
            from datetime import timedelta
            updates = {}
            if penalty == PenaltyType.BAN:
                updates['is_banned'] = True
            elif penalty in (PenaltyType.TEMP_SUSPEND, PenaltyType.PERM_SUSPEND):
                updates['suspended_until'] = timezone.now() + timedelta(days=duration)
            if updates:
                UserReputation.objects.filter(user_id=user_id).update(**updates)
        except Exception:
            pass
