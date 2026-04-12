# kyc/tests/test_security.py  ── WORLD #1
from django.test import TestCase
from .factories import make_user, make_kyc, make_blacklist_entry


class FraudDetectorTest(TestCase):

    def test_clean_kyc_is_low_risk(self):
        from api.kyc.security.fraud_detector import FraudDetector
        user   = make_user()
        kyc    = make_kyc(user, status='pending', risk_score=0)
        result = FraudDetector(kyc).check()
        self.assertFalse(result.is_high_risk)

    def test_duplicate_kyc_increases_risk(self):
        from api.kyc.security.fraud_detector import FraudDetector
        user = make_user()
        kyc  = make_kyc(user, status='pending')
        kyc.is_duplicate = True
        result = FraudDetector(kyc).check()
        self.assertIn('duplicate', result.flags)
        self.assertGreater(result.score, 0)

    def test_blacklisted_phone_high_risk(self):
        from api.kyc.security.fraud_detector import FraudDetector
        make_blacklist_entry('phone', '01700000077')
        user = make_user()
        kyc  = make_kyc(user, status='pending')
        kyc.phone_number = '01700000077'; kyc.save()
        result = FraudDetector(kyc).check()
        self.assertIn('blacklisted', result.flags)
        self.assertGreater(result.score, 50)

    def test_fraud_result_to_dict(self):
        from api.kyc.security.fraud_detector import FraudDetector
        user   = make_user()
        kyc    = make_kyc(user)
        result = FraudDetector(kyc).check()
        d      = result.to_dict()
        self.assertIn('risk_score', d)
        self.assertIn('risk_level', d)
        self.assertIn('flags', d)


class DataMaskerTest(TestCase):

    def test_mask_nid(self):
        from api.kyc.security.data_masker import mask_nid
        masked = mask_nid('1234567890')
        self.assertTrue(masked.startswith('123'))
        self.assertIn('*', masked)

    def test_mask_phone(self):
        from api.kyc.security.data_masker import mask_phone
        masked = mask_phone('01711234567')
        self.assertTrue(masked.startswith('0171'))
        self.assertIn('****', masked)

    def test_mask_email(self):
        from api.kyc.security.data_masker import mask_email
        masked = mask_email('testuser@gmail.com')
        self.assertIn('@gmail.com', masked)
        self.assertIn('***', masked)

    def test_mask_name(self):
        from api.kyc.security.data_masker import mask_name
        masked = mask_name('Rahim Uddin')
        self.assertIn('*', masked)


class RateLimiterTest(TestCase):

    def test_allows_within_limit(self):
        from api.kyc.security.rate_limiter import KYCRateLimiter
        limiter = KYCRateLimiter(user_id=9999)
        # Should allow 5 times
        for _ in range(5):
            result = limiter.allow('submit_test', limit=5, window=3600)
            self.assertTrue(result)

    def test_blocks_over_limit(self):
        from api.kyc.security.rate_limiter import KYCRateLimiter
        limiter = KYCRateLimiter(user_id=8888)
        for _ in range(3):
            limiter.allow('submit_test2', limit=3, window=3600)
        result = limiter.allow('submit_test2', limit=3, window=3600)
        self.assertFalse(result)


class EncryptionUtilsTest(TestCase):

    def test_hash_and_verify_otp(self):
        from api.kyc.utils.encryption_utils import hash_otp, verify_otp_hash
        otp    = '123456'
        salt   = 'user_42'
        hashed = hash_otp(otp, salt)
        self.assertTrue(verify_otp_hash(otp, hashed, salt))
        self.assertFalse(verify_otp_hash('999999', hashed, salt))

    def test_generate_otp_length(self):
        from api.kyc.utils.encryption_utils import generate_otp
        otp = generate_otp(6)
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

    def test_webhook_signature(self):
        from api.kyc.utils.encryption_utils import generate_webhook_signature, verify_webhook_signature
        payload = '{"event":"kyc.verified"}'
        secret  = 'mysecret'
        sig     = generate_webhook_signature(payload, secret)
        self.assertTrue(verify_webhook_signature(payload, secret, sig))
        self.assertFalse(verify_webhook_signature(payload, secret, 'badsig'))
