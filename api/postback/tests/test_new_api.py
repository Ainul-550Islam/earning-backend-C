"""test_new_api.py – Tests for new postback API endpoints and serializers."""
from decimal import Decimal
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.utils import timezone

from api.postback.tests.factories import (
    NetworkPostbackConfigFactory,
    PostbackInsightFactory,
    PostbackTemplateFactory,
    PostbackIPWhitelistFactory,
    PostbackRateLimitFactory,
    AnomalousPostbackInsightFactory,
    InactivePostbackTemplateFactory,
    BlockedRateLimitFactory,
    HighUsageRateLimitFactory,
)
from api.postback.models import PostbackInsight, PostbackTemplate, PostbackIPWhitelist, PostbackRateLimit
from api.postback.choices import PostbackStatus


class PostbackInsightAPITests(APITestCase):
    """Test PostbackInsight API endpoints."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.insight = PostbackInsightFactory(network=self.network)

    def test_list_insights(self):
        """Test listing insights."""
        url = reverse('postback:insight-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.insight.id))

    def test_retrieve_insight(self):
        """Test retrieving insight detail."""
        url = reverse('postback:insight-detail', kwargs={'pk': self.insight.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.insight.id))
        self.assertIn('success_rate', response.data)
        self.assertIn('rejection_rate', response.data)
        self.assertIn('duplicate_rate', response.data)

    def test_detect_anomalies(self):
        """Test anomaly detection endpoint."""
        url = reverse('postback:insight-detect-anomalies', kwargs={'pk': self.insight.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('anomalies_detected', response.data)
        self.assertIn('anomaly_details', response.data)

    def test_detect_anomalies_with_anomalies(self):
        """Test anomaly detection with actual anomalies."""
        anomalous_insight = AnomalousPostbackInsightFactory()
        url = reverse('postback:insight-detect-anomalies', kwargs={'pk': anomalous_insight.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['anomalies_detected'])
        self.assertIn('volume_spike', response.data['anomaly_details'])

    def test_recalculate_insight(self):
        """Test insight recalculation endpoint."""
        url = reverse('postback:insight-recalculate', kwargs={'pk': self.insight.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.insight.id))

    def test_filter_insights_by_network(self):
        """Test filtering insights by network."""
        other_network = NetworkPostbackConfigFactory()
        other_insight = PostbackInsightFactory(network=other_network)
        
        url = reverse('postback:insight-list')
        response = self.client.get(url, {'network': self.network.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.insight.id))

    def test_filter_insights_by_anomaly_detected(self):
        """Test filtering insights by anomaly detection."""
        anomalous_insight = AnomalousPostbackInsightFactory()
        
        url = reverse('postback:insight-list')
        response = self.client.get(url, {'anomaly_detected': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertTrue(response.data['results'][0]['anomaly_detected'])


class PostbackTemplateAPITests(APITestCase):
    """Test PostbackTemplate API endpoints."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.template = PostbackTemplateFactory(network=self.network)

    def test_list_templates(self):
        """Test listing templates."""
        url = reverse('postback:template-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.template.id))

    def test_create_template(self):
        """Test creating a template."""
        url = reverse('postback:template-list')
        data = {
            'network': self.network.id,
            'name': 'New Template',
            'template_body': 'Lead: {{lead_id}}, Offer: {{offer_id}}',
            'variables': {'lead_id': 'string', 'offer_id': 'string'},
            'required_variables': ['lead_id', 'offer_id'],
            'is_active': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Template')
        self.assertEqual(response.data['network_key'], self.network.network_key)

    def test_create_template_validation_error(self):
        """Test creating template with validation error."""
        url = reverse('postback:template-list')
        data = {
            'network': self.network.id,
            'name': 'Invalid Template',
            'template_body': 'No variables here',
            'variables': {},
            'required_variables': [],
            'is_active': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('template_body', response.data)

    def test_retrieve_template(self):
        """Test retrieving template detail."""
        url = reverse('postback:template-detail', kwargs={'pk': self.template.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.template.id))
        self.assertIn('variable_count', response.data)

    def test_update_template(self):
        """Test updating a template."""
        url = reverse('postback:template-detail', kwargs={'pk': self.template.id})
        data = {
            'name': 'Updated Template',
            'description': 'Updated description'
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Template')
        self.assertEqual(response.data['description'], 'Updated description')

    def test_render_template(self):
        """Test template rendering endpoint."""
        url = reverse('postback:template-render', kwargs={'pk': self.template.id})
        data = {
            'context': {
                'lead_id': 'LEAD123',
                'offer_id': 'OFFER456'
            },
            'increment_usage': True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rendered_content', response.data)
        self.assertIn('usage_count', response.data)

    def test_render_template_missing_variable(self):
        """Test template rendering with missing variable."""
        template = PostbackTemplateFactory(
            required_variables=['lead_id', 'offer_id']
        )
        url = reverse('postback:template-render', kwargs={'pk': template.id})
        data = {
            'context': {'lead_id': 'LEAD123'},  # Missing offer_id
            'increment_usage': True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_clone_template(self):
        """Test template cloning endpoint."""
        url = reverse('postback:template-clone', kwargs={'pk': self.template.id})
        data = {'name': 'Cloned Template'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Cloned Template')
        self.assertEqual(response.data['network_key'], self.network.network_key)
        self.assertNotEqual(response.data['id'], str(self.template.id))

    def test_verify_template_integrity(self):
        """Test template integrity verification endpoint."""
        url = reverse('postback:template-verify-integrity', kwargs={'pk': self.template.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', response.data)
        self.assertIn('template_name', response.data)

    def test_filter_templates_by_network(self):
        """Test filtering templates by network."""
        other_network = NetworkPostbackConfigFactory()
        other_template = PostbackTemplateFactory(network=other_network)
        
        url = reverse('postback:template-list')
        response = self.client.get(url, {'network': self.network.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.template.id))

    def test_filter_templates_by_active_status(self):
        """Test filtering templates by active status."""
        InactivePostbackTemplateFactory()
        
        url = reverse('postback:template-list')
        response = self.client.get(url, {'is_active': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertTrue(result['is_active'])


class PostbackIPWhitelistAPITests(APITestCase):
    """Test PostbackIPWhitelist API endpoints."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.whitelist = PostbackIPWhitelistFactory(network=self.network)

    def test_list_ip_whitelists(self):
        """Test listing IP whitelists."""
        url = reverse('postback:ip-whitelist-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.whitelist.id))

    def test_create_ip_whitelist(self):
        """Test creating IP whitelist."""
        url = reverse('postback:ip-whitelist-list')
        data = {
            'network': self.network.id,
            'name': 'New IP Rule',
            'ip_address': '192.168.1.0/24',
            'description': 'Test network',
            'is_active': True,
            'priority': 5
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New IP Rule')
        self.assertEqual(response.data['ip_address'], '192.168.1.0/24')

    def test_create_ip_whitelist_invalid_ip(self):
        """Test creating IP whitelist with invalid IP."""
        url = reverse('postback:ip-whitelist-list')
        data = {
            'network': self.network.id,
            'name': 'Invalid IP Rule',
            'ip_address': 'invalid-ip-address',
            'is_active': True,
            'priority': 5
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ip_address', response.data)

    def test_test_ip_endpoint(self):
        """Test IP testing endpoint."""
        whitelist = PostbackIPWhitelistFactory(ip_address='192.168.1.0/24')
        url = reverse('postback:ip-whitelist-test-ip', kwargs={'pk': whitelist.id})
        
        # Test IP in range
        data = {'ip_address': '192.168.1.100'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_allowed'])
        
        # Test IP not in range
        data = {'ip_address': '10.0.0.1'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_allowed'])

    def test_verify_ip_whitelist_integrity(self):
        """Test IP whitelist integrity verification."""
        url = reverse('postback:ip-whitelist-verify-integrity', kwargs={'pk': self.whitelist.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', response.data)
        self.assertIn('ip_address', response.data)

    def test_filter_ip_whitelists_by_network(self):
        """Test filtering IP whitelists by network."""
        other_network = NetworkPostbackConfigFactory()
        other_whitelist = PostbackIPWhitelistFactory(network=other_network)
        
        url = reverse('postback:ip-whitelist-list')
        response = self.client.get(url, {'network': self.network.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.whitelist.id))


class PostbackRateLimitAPITests(APITestCase):
    """Test PostbackRateLimit API endpoints."""

    def setUp(self):
        self.network = NetworkPostbackConfigFactory()
        self.rate_limit = PostbackRateLimitFactory(network=self.network)

    def test_list_rate_limits(self):
        """Test listing rate limits."""
        url = reverse('postback:rate-limit-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.rate_limit.id))

    def test_create_rate_limit(self):
        """Test creating rate limit."""
        url = reverse('postback:rate-limit-list')
        data = {
            'network': self.network.id,
            'name': 'New Rate Limit',
            'max_per_minute': 500,
            'max_per_hour': 25000,
            'max_per_day': 500000,
            'is_active': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Rate Limit')
        self.assertEqual(response.data['max_per_minute'], 500)

    def test_create_rate_limit_validation_error(self):
        """Test creating rate limit with validation error."""
        url = reverse('postback:rate-limit-list')
        data = {
            'network': self.network.id,
            'name': 'Invalid Rate Limit',
            'max_per_minute': 1000,
            'max_per_hour': 500,  # Less than minute limit
            'max_per_day': 100000,
            'is_active': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('max_per_hour', response.data)

    def test_retrieve_rate_limit(self):
        """Test retrieving rate limit detail."""
        url = reverse('postback:rate-limit-detail', kwargs={'pk': self.rate_limit.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.rate_limit.id))
        self.assertIn('current_utilization', response.data)
        self.assertIn('is_currently_blocked', response.data)

    def test_reset_window_endpoint(self):
        """Test rate limit window reset endpoint."""
        rate_limit = HighUsageRateLimitFactory(current_count=50)
        url = reverse('postback:rate-limit-reset-window', kwargs={'pk': rate_limit.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('current_count', response.data)

    def test_unblock_endpoint(self):
        """Test rate limit unblock endpoint."""
        blocked_rate_limit = BlockedRateLimitFactory()
        url = reverse('postback:rate-limit-unblock', kwargs={'pk': blocked_rate_limit.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('is_blocked', response.data)

    def test_verify_rate_limit_integrity(self):
        """Test rate limit integrity verification."""
        url = reverse('postback:rate-limit-verify-integrity', kwargs={'pk': self.rate_limit.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_valid', response.data)
        self.assertIn('rate_limit_name', response.data)

    def test_filter_rate_limits_by_blocked_status(self):
        """Test filtering rate limits by blocked status."""
        BlockedRateLimitFactory()
        
        url = reverse('postback:rate-limit-list')
        response = self.client.get(url, {'is_blocked': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result in response.data['results']:
            self.assertTrue(result['is_blocked'])


class PostbackSerializerTests(APITestCase):
    """Test postback serializers."""

    def test_postback_insight_serializer(self):
        """Test PostbackInsight serializer."""
        insight = PostbackInsightFactory()
        
        from api.postback.serializers import PostbackInsightSerializer
        serializer = PostbackInsightSerializer(insight)
        
        data = serializer.data
        self.assertEqual(data['network_key'], insight.network.network_key)
        self.assertIn('health_score_display', data)
        self.assertEqual(data['health_score_display'], f"{insight.health_score}%")

    def test_postback_insight_detail_serializer(self):
        """Test PostbackInsightDetail serializer."""
        insight = PostbackInsightFactory(
            received_count=100,
            rewarded_count=60,
            rejected_count=20,
            duplicate_count=10
        )
        
        from api.postback.serializers import PostbackInsightDetailSerializer
        serializer = PostbackInsightDetailSerializer(insight)
        
        data = serializer.data
        self.assertIn('success_rate', data)
        self.assertIn('rejection_rate', data)
        self.assertIn('duplicate_rate', data)
        
        # Verify calculated rates
        expected_success_rate = round((60 + 0) / 100 * 100, 2)  # rewarded + validated
        expected_rejection_rate = round((20 + 0) / 100 * 100, 2)  # rejected + failed
        expected_duplicate_rate = round(10 / 100 * 100, 2)
        
        self.assertEqual(data['success_rate'], expected_success_rate)
        self.assertEqual(data['rejection_rate'], expected_rejection_rate)
        self.assertEqual(data['duplicate_rate'], expected_duplicate_rate)

    def test_postback_template_serializer(self):
        """Test PostbackTemplate serializer."""
        template = PostbackTemplateFactory(
            variables={'lead_id': 'string', 'offer_id': 'string'}
        )
        
        from api.postback.serializers import PostbackTemplateSerializer
        serializer = PostbackTemplateSerializer(template)
        
        data = serializer.data
        self.assertEqual(data['network_key'], template.network.network_key)
        self.assertIn('variable_count', data)
        self.assertEqual(data['variable_count'], 2)

    def test_postback_template_create_serializer_validation(self):
        """Test PostbackTemplateCreateSerializer validation."""
        from api.postback.serializers import PostbackTemplateCreateSerializer
        
        # Valid template
        data = {
            'name': 'Test Template',
            'template_body': 'Lead: {{lead_id}}',
            'variables': {'lead_id': 'string'},
            'required_variables': ['lead_id']
        }
        serializer = PostbackTemplateCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid template (no variables)
        data = {
            'name': 'Invalid Template',
            'template_body': 'No variables here',
            'variables': {},
            'required_variables': []
        }
        serializer = PostbackTemplateCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('template_body', serializer.errors)

    def test_postback_ip_whitelist_serializer(self):
        """Test PostbackIPWhitelist serializer."""
        whitelist = PostbackIPWhitelistFactory(ip_address='192.168.1.0/24')
        
        from api.postback.serializers import PostbackIPWhitelistSerializer
        serializer = PostbackIPWhitelistSerializer(whitelist)
        
        data = serializer.data
        self.assertEqual(data['network_key'], whitelist.network.network_key)
        self.assertIn('ip_type', data)
        self.assertEqual(data['ip_type'], 'CIDR')

    def test_postback_ip_whitelist_create_serializer_validation(self):
        """Test PostbackIPWhitelistCreateSerializer validation."""
        from api.postback.serializers import PostbackIPWhitelistCreateSerializer
        
        # Valid IP
        data = {
            'name': 'Test IP Rule',
            'ip_address': '192.168.1.0/24',
            'is_active': True,
            'priority': 5
        }
        serializer = PostbackIPWhitelistCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid IP
        data = {
            'name': 'Invalid IP Rule',
            'ip_address': 'invalid-ip',
            'is_active': True,
            'priority': 5
        }
        serializer = PostbackIPWhitelistCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('ip_address', serializer.errors)

    def test_postback_rate_limit_serializer(self):
        """Test PostbackRateLimit serializer."""
        rate_limit = HighUsageRateLimitFactory(current_count=850)
        
        from api.postback.serializers import PostbackRateLimitSerializer
        serializer = PostbackRateLimitSerializer(rate_limit)
        
        data = serializer.data
        self.assertEqual(data['network_key'], rate_limit.network.network_key)
        self.assertIn('current_utilization', data)
        self.assertIn('is_currently_blocked', data)
        
        # Verify utilization calculation
        expected_utilization = round(850 / rate_limit.max_per_minute * 100, 2)
        self.assertEqual(data['current_utilization'], expected_utilization)

    def test_postback_rate_limit_create_serializer_validation(self):
        """Test PostbackRateLimitCreateSerializer validation."""
        from api.postback.serializers import PostbackRateLimitCreateSerializer
        
        # Valid limits
        data = {
            'name': 'Test Rate Limit',
            'max_per_minute': 1000,
            'max_per_hour': 50000,
            'max_per_day': 1000000,
            'is_active': True
        }
        serializer = PostbackRateLimitCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Invalid limits (hourly < minute)
        data = {
            'name': 'Invalid Rate Limit',
            'max_per_minute': 1000,
            'max_per_hour': 500,  # Less than minute limit
            'max_per_day': 100000,
            'is_active': True
        }
        serializer = PostbackRateLimitCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('max_per_hour', serializer.errors)


class PostbackAPIIntegrationTests(APITestCase):
    """Test API integration scenarios."""

    def test_complete_template_workflow(self):
        """Test complete template workflow through API."""
        network = NetworkPostbackConfigFactory()
        
        # Create template
        url = reverse('postback:template-list')
        data = {
            'network': network.id,
            'name': 'Workflow Template',
            'template_body': 'Lead: {{lead_id}}, Offer: {{offer_id}}, Amount: {{amount}}',
            'variables': {'lead_id': 'string', 'offer_id': 'string', 'amount': 'string'},
            'required_variables': ['lead_id', 'offer_id']
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        template_id = response.data['id']
        
        # Render template
        url = reverse('postback:template-render', kwargs={'pk': template_id})
        render_data = {
            'context': {
                'lead_id': 'LEAD123',
                'offer_id': 'OFFER456',
                'amount': '$25.00'
            }
        }
        response = self.client.post(url, render_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['rendered_content'],
            'Lead: LEAD123, Offer: OFFER456, Amount: $25.00'
        )
        
        # Verify usage was tracked
        template = PostbackTemplate.objects.get(id=template_id)
        self.assertEqual(template.usage_count, 1)

    def test_complete_ip_whitelist_workflow(self):
        """Test complete IP whitelist workflow through API."""
        network = NetworkPostbackConfigFactory()
        
        # Create IP whitelist
        url = reverse('postback:ip-whitelist-list')
        data = {
            'network': network.id,
            'name': 'Test Network',
            'ip_address': '192.168.1.0/24',
            'priority': 10
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        whitelist_id = response.data['id']
        
        # Test IP in range
        url = reverse('postback:ip-whitelist-test-ip', kwargs={'pk': whitelist_id})
        test_data = {'ip_address': '192.168.1.100'}
        response = self.client.post(url, test_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_allowed'])
        
        # Test IP not in range
        test_data = {'ip_address': '10.0.0.1'}
        response = self.client.post(url, test_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_allowed'])

    def test_complete_rate_limit_workflow(self):
        """Test complete rate limit workflow through API."""
        network = NetworkPostbackConfigFactory()
        
        # Create rate limit
        url = reverse('postback:rate-limit-list')
        data = {
            'network': network.id,
            'name': 'Test Limit',
            'max_per_minute': 100,
            'max_per_hour': 5000,
            'max_per_day': 100000
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        rate_limit_id = response.data['id']
        
        # Check initial state
        url = reverse('postback:rate-limit-detail', kwargs={'pk': rate_limit_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_count'], 0)
        self.assertEqual(response.data['current_utilization'], 0.0)
        self.assertFalse(response.data['is_currently_blocked'])
        
        # Reset window (should work fine)
        url = reverse('postback:rate-limit-reset-window', kwargs={'pk': rate_limit_id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_analytics_workflow(self):
        """Test analytics workflow through API."""
        network = NetworkPostbackConfigFactory()
        
        # Create insight with data
        insight = PostbackInsightFactory(
            network=network,
            received_count=100,
            rewarded_count=80,
            rejected_count=15,
            duplicate_count=5
        )
        
        # Get insight detail
        url = reverse('postback:insight-detail', kwargs={'pk': insight.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify calculated metrics
        data = response.data
        self.assertIn('success_rate', data)
        self.assertIn('rejection_rate', data)
        self.assertIn('duplicate_rate', data)
        
        # Run anomaly detection
        url = reverse('postback:insight-detect-anomalies', kwargs={'pk': insight.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('anomalies_detected', response.data)
