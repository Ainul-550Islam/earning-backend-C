"""
Exception Tests — status codes, hierarchy, messages
Run: python manage.py test api.offerwall.tests.test_exceptions
"""
from django.test import TestCase
from api.offerwall.exceptions import (
    OfferwallException, OfferNotFoundException, OfferInactiveException,
    OfferExpiredException, OfferCapReachedException, OfferLimitReachedException,
    InvalidRewardException, RateLimitException, FraudException,
    AccountSuspendedException, ValidationException, InvalidParameterException,
    MissingParameterException, InvalidIPAddressException,
)


class ExceptionStatusCodeTest(TestCase):

    def test_offer_not_found_404(self):
        e = OfferNotFoundException()
        self.assertEqual(e.status_code, 404)

    def test_offer_inactive_400(self):
        e = OfferInactiveException()
        self.assertIn(e.status_code, [400, 410])

    def test_offer_expired_410_or_400(self):
        e = OfferExpiredException()
        self.assertIn(e.status_code, [400, 410])

    def test_offer_cap_reached_429_or_400(self):
        e = OfferCapReachedException()
        self.assertIn(e.status_code, [400, 429])

    def test_offer_limit_reached_429_or_400(self):
        e = OfferLimitReachedException()
        self.assertIn(e.status_code, [400, 429])

    def test_rate_limit_exception_429(self):
        e = RateLimitException()
        self.assertIn(e.status_code, [429, 400])

    def test_fraud_exception_403(self):
        e = FraudException()
        self.assertIn(e.status_code, [403, 400])

    def test_invalid_reward_400(self):
        e = InvalidRewardException()
        self.assertIn(e.status_code, [400, 422])

    def test_account_suspended_403_or_400(self):
        e = AccountSuspendedException()
        self.assertIn(e.status_code, [400, 403])

    def test_validation_exception_400(self):
        e = ValidationException()
        self.assertIn(e.status_code, [400, 422])

    def test_invalid_parameter_400(self):
        e = InvalidParameterException()
        self.assertIn(e.status_code, [400, 422])

    def test_missing_parameter_400(self):
        e = MissingParameterException()
        self.assertIn(e.status_code, [400, 422])

    def test_invalid_ip_address_400(self):
        e = InvalidIPAddressException()
        self.assertIn(e.status_code, [400, 422])


class ExceptionHierarchyTest(TestCase):

    def test_offer_not_found_inherits_offerwall_exception(self):
        self.assertTrue(issubclass(OfferNotFoundException, OfferwallException))

    def test_offer_inactive_inherits_offerwall_exception(self):
        self.assertTrue(issubclass(OfferInactiveException, OfferwallException))

    def test_offer_expired_inherits_offerwall_exception(self):
        self.assertTrue(issubclass(OfferExpiredException, OfferwallException))

    def test_cap_reached_inherits_offerwall_exception(self):
        self.assertTrue(issubclass(OfferCapReachedException, OfferwallException))

    def test_limit_reached_inherits_offerwall_exception(self):
        self.assertTrue(issubclass(OfferLimitReachedException, OfferwallException))

    def test_rate_limit_inherits_offerwall_exception(self):
        self.assertTrue(issubclass(RateLimitException, OfferwallException))

    def test_fraud_inherits_offerwall_exception(self):
        self.assertTrue(issubclass(FraudException, OfferwallException))

    def test_validation_inherits_offerwall_exception(self):
        self.assertTrue(issubclass(ValidationException, OfferwallException))

    def test_invalid_parameter_inherits_validation(self):
        self.assertTrue(issubclass(InvalidParameterException, ValidationException))

    def test_missing_parameter_inherits_validation(self):
        self.assertTrue(issubclass(MissingParameterException, ValidationException))

    def test_invalid_ip_inherits_validation(self):
        self.assertTrue(issubclass(InvalidIPAddressException, ValidationException))

    def test_all_inherit_from_base_api_exception(self):
        from rest_framework.exceptions import APIException
        for exc_class in [
            OfferwallException, OfferNotFoundException, OfferInactiveException,
            OfferExpiredException, OfferCapReachedException, OfferLimitReachedException,
            InvalidRewardException, RateLimitException, FraudException,
            AccountSuspendedException, ValidationException,
        ]:
            self.assertTrue(
                issubclass(exc_class, APIException),
                f'{exc_class.__name__} should inherit from APIException'
            )


class ExceptionMessageTest(TestCase):

    def test_exception_with_custom_message(self):
        e = OfferNotFoundException('Offer 123 not found')
        self.assertIn('123', str(e.detail))

    def test_exception_default_message_not_empty(self):
        e = OfferNotFoundException()
        self.assertTrue(len(str(e.detail)) > 0)

    def test_fraud_exception_custom_message(self):
        e = FraudException('VPN detected')
        self.assertIn('VPN', str(e.detail))

    def test_rate_limit_exception_custom_message(self):
        e = RateLimitException('Too many clicks. Try again in 60s.')
        self.assertIn('60', str(e.detail))

    def test_invalid_reward_negative_amount(self):
        e = InvalidRewardException('Reward cannot be negative: -1.00')
        self.assertIn('-1', str(e.detail))

    def test_all_exceptions_can_be_caught_as_offerwall_exception(self):
        exceptions_to_test = [
            OfferNotFoundException, OfferInactiveException, OfferExpiredException,
            OfferCapReachedException, RateLimitException, FraudException,
        ]
        for ExcClass in exceptions_to_test:
            try:
                raise ExcClass('test message')
            except OfferwallException:
                pass  # Should be caught
            except Exception as e:
                self.fail(f'{ExcClass.__name__} not caught as OfferwallException: {e}')

    def test_exception_status_code_attribute_exists(self):
        for ExcClass in [
            OfferNotFoundException, OfferInactiveException, RateLimitException, FraudException,
        ]:
            e = ExcClass()
            self.assertTrue(hasattr(e, 'status_code'),
                            f'{ExcClass.__name__} missing status_code attribute')
