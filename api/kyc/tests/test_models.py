# kyc/tests/test_models.py  ── WORLD #1
"""Unit tests for all KYC models."""
from django.test import TestCase
from django.utils import timezone
from .factories import make_user, make_kyc, make_blacklist_entry


class KYCModelTest(TestCase):

    def setUp(self):
        self.user  = make_user()
        self.kyc   = make_kyc(self.user, status='pending')

    def test_kyc_str(self):
        self.assertIn(self.user.username, str(self.kyc))

    def test_submit_for_review(self):
        self.kyc.status = 'not_submitted'
        self.kyc.save()
        self.kyc.submit_for_review()
        self.assertEqual(self.kyc.status, 'pending')

    def test_approve(self):
        reviewer = make_user(username='admin', is_staff=True)
        self.kyc.approve(reviewed_by=reviewer)
        self.assertEqual(self.kyc.status, 'verified')
        self.assertIsNotNone(self.kyc.verified_at)
        self.assertIsNotNone(self.kyc.expires_at)

    def test_reject(self):
        self.kyc.reject(reason='Invalid document', reviewed_by=make_user(is_staff=True))
        self.assertEqual(self.kyc.status, 'rejected')
        self.assertEqual(self.kyc.rejection_reason, 'Invalid document')

    def test_calculate_risk_score_age_flag(self):
        import datetime
        self.kyc.date_of_birth = datetime.date(2015, 1, 1)  # under 18
        self.kyc.save()
        score = self.kyc.calculate_risk_score()
        self.assertGreater(score, 0)
        self.assertIn('Under 18', self.kyc.risk_factors)

    def test_calculate_risk_score_duplicate(self):
        self.kyc.is_duplicate = True
        score = self.kyc.calculate_risk_score()
        self.assertIn('Duplicate KYC', self.kyc.risk_factors)

    def test_calculate_risk_score_max_100(self):
        import datetime
        self.kyc.date_of_birth = datetime.date(2015, 1, 1)
        self.kyc.is_duplicate  = True
        self.kyc.ocr_confidence = 0.5
        score = self.kyc.calculate_risk_score()
        self.assertLessEqual(score, 100)


class KYCBlacklistModelTest(TestCase):

    def test_is_blacklisted_phone(self):
        make_blacklist_entry('phone', '01700000000')
        self.assertTrue(
            __import__('api.kyc.models', fromlist=['KYCBlacklist']).KYCBlacklist.is_blacklisted('phone', '01700000000')
        )

    def test_is_not_blacklisted(self):
        from api.kyc.models import KYCBlacklist
        self.assertFalse(KYCBlacklist.is_blacklisted('phone', '01900000000'))

    def test_inactive_blacklist_not_blocked(self):
        entry = make_blacklist_entry('phone', '01711111111')
        entry.is_active = False; entry.save()
        from api.kyc.models import KYCBlacklist
        self.assertFalse(KYCBlacklist.is_blacklisted('phone', '01711111111'))


class KYCFeatureFlagTest(TestCase):

    def test_flag_off_by_default(self):
        from api.kyc.models import KYCFeatureFlag
        self.assertFalse(KYCFeatureFlag.is_on('test_feature'))

    def test_flag_can_be_enabled(self):
        from api.kyc.models import KYCFeatureFlag
        KYCFeatureFlag.objects.create(key='test_feature', is_enabled=True)
        self.assertTrue(KYCFeatureFlag.is_on('test_feature'))

    def test_flag_get_value(self):
        from api.kyc.models import KYCFeatureFlag
        KYCFeatureFlag.objects.create(key='config_flag', is_enabled=True, value={'limit': 10})
        val = KYCFeatureFlag.get_value('config_flag')
        self.assertEqual(val['limit'], 10)


class KYCAuditTrailImmutableTest(TestCase):

    def test_audit_trail_cannot_be_deleted(self):
        from api.kyc.models import KYCAuditTrail
        trail = KYCAuditTrail.log(entity_type='kyc', entity_id=1, action='test')
        with self.assertRaises(PermissionError):
            trail.delete()

    def test_audit_trail_cannot_be_updated(self):
        from api.kyc.models import KYCAuditTrail
        trail = KYCAuditTrail.log(entity_type='kyc', entity_id=1, action='test')
        trail.action = 'modified'
        with self.assertRaises(PermissionError):
            trail.save()
