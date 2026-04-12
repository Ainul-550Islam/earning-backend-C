# kyc/tests/test_services.py  ── WORLD #1
from django.test import TestCase
from .factories import make_user, make_kyc, make_blacklist_entry


class KYCServiceTest(TestCase):

    def test_is_user_verified_false(self):
        from api.kyc.services import KYCService
        user = make_user()
        self.assertFalse(KYCService.is_user_verified(user))

    def test_is_user_verified_true(self):
        from api.kyc.services import KYCService
        user = make_user()
        make_kyc(user, status='verified')
        self.assertTrue(KYCService.is_user_verified(user))

    def test_get_kyc_status_not_submitted(self):
        from api.kyc.services import KYCService
        user   = make_user()
        result = KYCService.get_kyc_status(user)
        self.assertEqual(result['status'], 'not_submitted')
        self.assertFalse(result['verified'])

    def test_get_kyc_status_pending(self):
        from api.kyc.services import KYCService
        user = make_user(); make_kyc(user, status='pending')
        result = KYCService.get_kyc_status(user)
        self.assertEqual(result['status'], 'pending')

    def test_check_duplicate_by_document(self):
        from api.kyc.services import KYCService
        user1 = make_user(username='dup1')
        user2 = make_user(username='dup2')
        kyc1  = make_kyc(user1, status='verified')
        kyc1.document_number = '9999999999'; kyc1.save()
        kyc2  = make_kyc(user2, status='pending')
        kyc2.document_number = '9999999999'; kyc2.save()
        result = KYCService.check_duplicate(kyc2)
        self.assertTrue(result)
        self.assertTrue(kyc2.is_duplicate)


class KYCBlacklistServiceTest(TestCase):

    def test_check_all_not_blocked(self):
        from api.kyc.services import KYCBlacklistService
        result = KYCBlacklistService.check_all(phone='01700000099')
        self.assertFalse(result['is_blocked'])

    def test_check_all_blocked_phone(self):
        from api.kyc.services import KYCBlacklistService
        make_blacklist_entry('phone', '01700000088')
        result = KYCBlacklistService.check_all(phone='01700000088')
        self.assertTrue(result['is_blocked'])
        self.assertIn('phone', result['blocked_fields'])

    def test_add_new_entry(self):
        from api.kyc.services import KYCBlacklistService
        obj, created = KYCBlacklistService.add('document', '1234567890', reason='Fraud')
        self.assertTrue(created)
        self.assertEqual(obj.value, '1234567890')


# kyc/tests/test_validators.py  ── WORLD #1
class ValidatorTest(TestCase):

    def test_valid_nid_10_digits(self):
        from api.kyc.validators import validate_nid_number
        result = validate_nid_number('1234567890')
        self.assertEqual(result, '1234567890')

    def test_valid_nid_17_digits(self):
        from api.kyc.validators import validate_nid_number
        result = validate_nid_number('12345678901234567')
        self.assertEqual(result, '12345678901234567')

    def test_invalid_nid_length(self):
        from api.kyc.validators import validate_nid_number
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_nid_number('12345')

    def test_nid_with_spaces_cleaned(self):
        from api.kyc.validators import validate_nid_number
        result = validate_nid_number('123 456 7890')
        self.assertEqual(result, '1234567890')

    def test_valid_bd_phone(self):
        from api.kyc.validators import validate_bd_phone_number
        result = validate_bd_phone_number('01711234567')
        self.assertEqual(result, '01711234567')

    def test_valid_bd_phone_with_880(self):
        from api.kyc.validators import validate_bd_phone_number
        result = validate_bd_phone_number('+8801711234567')
        self.assertEqual(result, '01711234567')

    def test_invalid_phone(self):
        from api.kyc.validators import validate_bd_phone_number
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_bd_phone_number('01211234567')  # 012XX not valid BD

    def test_valid_full_name(self):
        from api.kyc.validators import validate_full_name
        result = validate_full_name('Rahim Uddin')
        self.assertEqual(result, 'Rahim Uddin')

    def test_name_too_short(self):
        from api.kyc.validators import validate_full_name
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_full_name('AB')

    def test_dob_under_18(self):
        from api.kyc.validators import validate_date_of_birth
        from django.core.exceptions import ValidationError
        import datetime
        with self.assertRaises(ValidationError):
            validate_date_of_birth(datetime.date(2015, 1, 1))

    def test_dob_valid(self):
        from api.kyc.validators import validate_date_of_birth
        import datetime
        # Should not raise
        validate_date_of_birth(datetime.date(1995, 6, 15))

    def test_name_similarity_high(self):
        from api.kyc.validators import check_name_similarity
        is_sim, ratio = check_name_similarity('Mohammad Rahim', 'Mohammad Rahim')
        self.assertTrue(is_sim)
        self.assertAlmostEqual(ratio, 1.0, places=1)

    def test_name_similarity_low(self):
        from api.kyc.validators import check_name_similarity
        is_sim, ratio = check_name_similarity('John Doe', 'Rahim Uddin')
        self.assertFalse(is_sim)
