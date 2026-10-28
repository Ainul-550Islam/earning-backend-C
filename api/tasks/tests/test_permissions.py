"""api/tasks/tests/test_permissions.py — DRF permission tests."""
import pytest
from unittest.mock import MagicMock, patch
from django.core.cache import cache
from api.tasks.permissions import (
    IsNotSuspended, IsNotFraudFlagged, IsTaskRateLimitOK,
    CanCompleteTask, CanWithdraw, HasKYCTier,
)


class TestIsNotSuspended:
    def test_active_user_passes(self, user):
        request = MagicMock()
        request.user = user
        perm = IsNotSuspended()
        assert perm.has_permission(request, None) is True

    def test_suspended_user_blocked(self, user):
        cache.set(f'user_suspended_{user.pk}', True, timeout=60)
        request = MagicMock()
        request.user = user
        perm = IsNotSuspended()
        assert perm.has_permission(request, None) is False

    def test_unauthenticated_blocked(self):
        request = MagicMock()
        request.user = MagicMock(is_authenticated=False)
        perm = IsNotSuspended()
        assert perm.has_permission(request, None) is False


class TestIsNotFraudFlagged:
    def test_clean_user_passes(self, user):
        cache.set(f'fraud_score_{user.pk}', 10, timeout=60)
        request = MagicMock()
        request.user = user
        perm = IsNotFraudFlagged()
        assert perm.has_permission(request, None) is True

    def test_high_fraud_score_blocked(self, user):
        cache.set(f'fraud_score_{user.pk}', 75, timeout=60)
        request = MagicMock()
        request.user = user
        perm = IsNotFraudFlagged()
        assert perm.has_permission(request, None) is False

    def test_staff_bypasses_fraud_check(self, staff_user):
        cache.set(f'fraud_score_{staff_user.pk}', 99, timeout=60)
        request = MagicMock()
        request.user = staff_user
        perm = IsNotFraudFlagged()
        assert perm.has_permission(request, None) is True


class TestHasKYCTier:
    def test_none_tier_fails_basic_requirement(self, user):
        cache.set(f'kyc_tier_{user.pk}', 'none', timeout=60)
        request = MagicMock()
        request.user = user
        perm = HasKYCTier.for_tier('basic')()
        assert perm.has_permission(request, None) is False

    def test_basic_tier_passes_basic_requirement(self, user):
        cache.set(f'kyc_tier_{user.pk}', 'basic', timeout=60)
        request = MagicMock()
        request.user = user
        perm = HasKYCTier.for_tier('basic')()
        assert perm.has_permission(request, None) is True

    def test_standard_tier_passes_basic_requirement(self, user):
        cache.set(f'kyc_tier_{user.pk}', 'standard', timeout=60)
        request = MagicMock()
        request.user = user
        perm = HasKYCTier.for_tier('basic')()
        assert perm.has_permission(request, None) is True


class TestIsTaskOwner:
    def test_owner_passes(self, user, completion):
        from api.tasks.permissions import IsTaskOwner
        request = MagicMock()
        request.user = user
        perm = IsTaskOwner()
        assert perm.has_object_permission(request, None, completion) is True

    def test_non_owner_fails(self, second_user, completion):
        from api.tasks.permissions import IsTaskOwner
        request = MagicMock()
        request.user = second_user
        perm = IsTaskOwner()
        assert perm.has_object_permission(request, None, completion) is False

    def test_staff_always_passes(self, staff_user, completion):
        from api.tasks.permissions import IsTaskOwner
        request = MagicMock()
        request.user = staff_user
        perm = IsTaskOwner()
        assert perm.has_object_permission(request, None, completion) is True
