from django.test import TestCase
from unittest.mock import patch, MagicMock
from .factories import UserFactory
from ..services.core.DomainService import DomainService
from ..models.publisher import PublisherDomain
from ..choices import DomainVerificationStatus
from ..exceptions import DomainVerificationFailed


class DomainServiceTest(TestCase):
    def setUp(self):
        self.service = DomainService()
        self.publisher = UserFactory()

    def test_initiate_verification_creates_domain(self):
        domain_obj = self.service.initiate_verification(self.publisher, 'test.example.com')
        self.assertEqual(domain_obj.domain, 'test.example.com')
        self.assertEqual(domain_obj.verification_status, DomainVerificationStatus.PENDING)
        self.assertIsNotNone(domain_obj.verification_token)

    def test_initiate_verification_regenerates_token(self):
        domain_obj = self.service.initiate_verification(self.publisher, 'test2.example.com')
        old_token = domain_obj.verification_token
        domain_obj2 = self.service.initiate_verification(self.publisher, 'test2.example.com')
        self.assertNotEqual(old_token, domain_obj2.verification_token)

    def test_dns_txt_record_format(self):
        domain_obj = self.service.initiate_verification(self.publisher, 'mysite.com')
        txt = domain_obj.dns_txt_record
        self.assertTrue(txt.startswith('smartlink-verify='))

    @patch('dns.resolver.resolve')
    def test_verify_success(self, mock_resolve):
        domain_obj = self.service.initiate_verification(self.publisher, 'verified.example.com')
        expected = domain_obj.dns_txt_record

        mock_rdata = MagicMock()
        mock_rdata.strings = [expected.encode('utf-8')]
        mock_resolve.return_value = [mock_rdata]

        result = self.service.verify(domain_obj)
        self.assertTrue(result)
        domain_obj.refresh_from_db()
        self.assertEqual(domain_obj.verification_status, DomainVerificationStatus.VERIFIED)

    @patch('dns.resolver.resolve', side_effect=Exception('DNS timeout'))
    def test_verify_failure_raises(self, mock_resolve):
        domain_obj = self.service.initiate_verification(self.publisher, 'fail.example.com')
        with self.assertRaises(DomainVerificationFailed):
            self.service.verify(domain_obj)

    def test_get_redirect_base_url_default(self):
        url = self.service.get_redirect_base_url(self.publisher)
        self.assertTrue(url.startswith('http'))
