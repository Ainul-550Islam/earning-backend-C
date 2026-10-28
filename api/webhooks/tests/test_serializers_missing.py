"""
Test missing serializer variants (Create, Update, Detail, List)

Issues Fixed:
- WebhookFilterCreateSerializer
- WebhookFilterUpdateSerializer
- WebhookFilterDetailSerializer
- WebhookFilterListSerializer
- WebhookBatchCreateSerializer
- WebhookBatchUpdateSerializer
- WebhookBatchDetailSerializer
- WebhookBatchListSerializer
- WebhookSecretCreateSerializer
- WebhookSecretUpdateSerializer
- WebhookSecretDetailSerializer
- WebhookSecretListSerializer
- WebhookTemplateCreateSerializer
- WebhookTemplateUpdateSerializer
- WebhookTemplateDetailSerializer
- WebhookTemplateListSerializer
- InboundWebhookListSerializer
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status

from api.webhooks.serializers import (
    WebhookFilterCreateSerializer,
    WebhookFilterUpdateSerializer,
    WebhookFilterDetailSerializer,
    WebhookFilterListSerializer,
    WebhookBatchCreateSerializer,
    WebhookBatchUpdateSerializer,
    WebhookBatchDetailSerializer,
    WebhookBatchListSerializer,
    WebhookSecretCreateSerializer,
    WebhookSecretUpdateSerializer,
    WebhookSecretDetailSerializer,
    WebhookSecretListSerializer,
    WebhookTemplateCreateSerializer,
    WebhookTemplateUpdateSerializer,
    WebhookTemplateDetailSerializer,
    WebhookTemplateListSerializer,
    InboundWebhookListSerializer,
)
from api.webhooks.models import (
    WebhookEndpoint,
    WebhookFilter,
    WebhookBatch,
    WebhookSecret,
    WebhookTemplate,
    InboundWebhook,
)


class WebhookFilterSerializerTestCase(TestCase):
    """Test WebhookFilter serializer variants"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            label='Test Endpoint',
            target_url='https://example.com/webhook',
            owner=self.user
        )

    def test_filter_create_serializer_valid(self):
        """Test WebhookFilterCreateSerializer with valid data"""
        data = {
            'endpoint': self.endpoint.id,
            'field_path': 'user.email',
            'operator': 'contains',
            'value': '@example.com',
            'is_active': True,
        }
        serializer = WebhookFilterCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_filter_update_serializer_valid(self):
        """Test WebhookFilterUpdateSerializer"""
        webhook_filter = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator='contains',
            value='@old.com',
            is_active=True,
        )
        data = {
            'field_path': 'user.email',
            'operator': 'contains',
            'value': '@new.com',
            'is_active': True,
        }
        serializer = WebhookFilterUpdateSerializer(webhook_filter, data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_filter_detail_serializer(self):
        """Test WebhookFilterDetailSerializer"""
        webhook_filter = WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator='contains',
            value='@example.com',
            is_active=True,
        )
        serializer = WebhookFilterDetailSerializer(webhook_filter)
        data = serializer.data
        self.assertEqual(data['field_path'], 'user.email')
        self.assertIn('endpoint_name', data)
        self.assertIn('id', data)

    def test_filter_list_serializer(self):
        """Test WebhookFilterListSerializer"""
        WebhookFilter.objects.create(
            endpoint=self.endpoint,
            field_path='user.email',
            operator='contains',
            value='@example.com',
            is_active=True,
        )
        filters = WebhookFilter.objects.all()
        serializer = WebhookFilterListSerializer(filters, many=True)
        self.assertEqual(len(serializer.data), 1)


class WebhookBatchSerializerTestCase(TestCase):
    """Test WebhookBatch serializer variants"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            label='Test Endpoint',
            target_url='https://example.com/webhook',
            owner=self.user
        )

    def test_batch_create_serializer_valid(self):
        """Test WebhookBatchCreateSerializer"""
        data = {
            'endpoint': self.endpoint.id,
            'event_count': 100,
            'status': 'pending',
        }
        serializer = WebhookBatchCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_batch_create_serializer_invalid_count(self):
        """Test WebhookBatchCreateSerializer with invalid count"""
        data = {
            'endpoint': self.endpoint.id,
            'event_count': 0,  # Invalid
            'status': 'pending',
        }
        serializer = WebhookBatchCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_batch_update_serializer(self):
        """Test WebhookBatchUpdateSerializer"""
        batch = WebhookBatch.objects.create(
            endpoint=self.endpoint,
            event_count=100,
            status='pending',
        )
        data = {
            'event_count': 150,
            'status': 'processing',
        }
        serializer = WebhookBatchUpdateSerializer(batch, data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_batch_detail_serializer(self):
        """Test WebhookBatchDetailSerializer"""
        batch = WebhookBatch.objects.create(
            endpoint=self.endpoint,
            event_count=100,
            status='pending',
        )
        serializer = WebhookBatchDetailSerializer(batch)
        data = serializer.data
        self.assertEqual(data['event_count'], 100)
        self.assertIn('endpoint_name', data)

    def test_batch_list_serializer(self):
        """Test WebhookBatchListSerializer"""
        WebhookBatch.objects.create(
            endpoint=self.endpoint,
            event_count=100,
            status='pending',
        )
        batches = WebhookBatch.objects.all()
        serializer = WebhookBatchListSerializer(batches, many=True)
        self.assertEqual(len(serializer.data), 1)


class WebhookSecretSerializerTestCase(TestCase):
    """Test WebhookSecret serializer variants"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.endpoint = WebhookEndpoint.objects.create(
            label='Test Endpoint',
            target_url='https://example.com/webhook',
            owner=self.user
        )

    def test_secret_create_serializer(self):
        """Test WebhookSecretCreateSerializer"""
        data = {
            'endpoint': self.endpoint.id,
            'is_active': True,
        }
        serializer = WebhookSecretCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_secret_update_serializer(self):
        """Test WebhookSecretUpdateSerializer"""
        secret = WebhookSecret.objects.create(
            endpoint=self.endpoint,
            is_active=True,
        )
        data = {
            'is_active': False,
        }
        serializer = WebhookSecretUpdateSerializer(secret, data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_secret_detail_serializer_no_expose(self):
        """Test WebhookSecretDetailSerializer doesn't expose secret"""
        secret = WebhookSecret.objects.create(
            endpoint=self.endpoint,
            is_active=True,
        )
        serializer = WebhookSecretDetailSerializer(secret)
        data = serializer.data
        # Secret hash should never be exposed
        self.assertNotIn('secret_hash', data)
        # But we should know if it exists
        self.assertIn('secret_exists', data)

    def test_secret_list_serializer(self):
        """Test WebhookSecretListSerializer"""
        WebhookSecret.objects.create(
            endpoint=self.endpoint,
            is_active=True,
        )
        secrets = WebhookSecret.objects.all()
        serializer = WebhookSecretListSerializer(secrets, many=True)
        self.assertEqual(len(serializer.data), 1)
        # Ensure secret is not exposed in list
        self.assertNotIn('secret_hash', serializer.data[0])


class WebhookTemplateSerializerTestCase(TestCase):
    """Test WebhookTemplate serializer variants"""

    def test_template_create_serializer_valid(self):
        """Test WebhookTemplateCreateSerializer"""
        data = {
            'name': 'Test Template',
            'event_type': 'user.created',
            'payload_template': '{"user": "{{ event.user }}"}',
            'transform_rules': {},
            'is_active': True,
        }
        serializer = WebhookTemplateCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_template_create_serializer_invalid_template(self):
        """Test WebhookTemplateCreateSerializer with invalid Jinja2"""
        data = {
            'name': 'Test Template',
            'event_type': 'user.created',
            # The original string here ('{"user": "{{ event.user }}') has a
            # balanced {{ ... }} - Jinja2 only checks template syntax, not
            # whether the rendered result is valid JSON, so it parsed fine
            # (confirmed empirically: no TemplateSyntaxError). What's
            # actually malformed there is the JSON structure, not the Jinja2
            # syntax - a different, unchecked concern. Using a genuinely
            # unclosed {{ instead, which does raise TemplateSyntaxError.
            'payload_template': '{"user": "{{ event.user',  # Invalid: unclosed {{
            'transform_rules': {},
            'is_active': True,
        }
        serializer = WebhookTemplateCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_template_update_serializer(self):
        """Test WebhookTemplateUpdateSerializer"""
        template = WebhookTemplate.objects.create(
            name='Test Template',
            event_type='user.created',
            payload_template='{"user": "{{ event.user }}"}',
            is_active=True,
        )
        data = {
            'name': 'Updated Template',
            'payload_template': '{"user": "{{ event.user }}", "id": "{{ event.id }}"}',
        }
        # Without partial=True, DRF requires every non-read-only Meta field
        # in `data` (a full PUT-style update), so event_type (omitted here)
        # fails as "This field is required." - confirmed empirically. The
        # serializer's own docstring says it's for "PATCH/PUT"; partial=True
        # is what makes PATCH-style partial data actually work.
        serializer = WebhookTemplateUpdateSerializer(template, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_template_detail_serializer(self):
        """Test WebhookTemplateDetailSerializer"""
        template = WebhookTemplate.objects.create(
            name='Test Template',
            event_type='user.created',
            payload_template='{"user": "{{ event.user }}"}',
            is_active=True,
        )
        serializer = WebhookTemplateDetailSerializer(template)
        data = serializer.data
        self.assertEqual(data['name'], 'Test Template')
        self.assertIn('payload_template', data)

    def test_template_list_serializer(self):
        """Test WebhookTemplateListSerializer"""
        WebhookTemplate.objects.create(
            name='Test Template',
            event_type='user.created',
            payload_template='{"user": "{{ event.user }}"}',
            is_active=True,
        )
        templates = WebhookTemplate.objects.all()
        serializer = WebhookTemplateListSerializer(templates, many=True)
        self.assertEqual(len(serializer.data), 1)


class InboundWebhookListSerializerTestCase(TestCase):
    """Test InboundWebhookListSerializer"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_inbound_webhook_list_serializer(self):
        """Test InboundWebhookListSerializer"""
        # InboundWebhook is a standalone inbound-receiver config, not tied
        # to a WebhookEndpoint - it has no name/endpoint/active fields at
        # all (confirmed against models/inbound.py: source, url_token,
        # secret, created_by, is_active, ...). The real serializer exposes
        # source/url_token/created_by_username/is_active/created_at, not
        # name/active/endpoint_name/endpoint_owner - confirmed empirically.
        inbound = InboundWebhook.objects.create(
            source='stripe',
            url_token='test-token-1',
            secret='test-secret',
            is_active=True,
            created_by=self.user,
        )
        serializer = InboundWebhookListSerializer(inbound)
        data = serializer.data
        self.assertEqual(data['source'], 'stripe')
        self.assertEqual(data['url_token'], 'test-token-1')
        self.assertTrue(data['is_active'])
        self.assertEqual(data['created_by_username'], 'testuser')

    def test_inbound_webhook_list_serializer_many(self):
        """Test InboundWebhookListSerializer with many=True"""
        InboundWebhook.objects.create(
            source='stripe',
            url_token='test-token-1',
            secret='test-secret',
            is_active=True,
            created_by=self.user,
        )
        InboundWebhook.objects.create(
            # 'twilio' isn't a valid InboundSource choice (bkash, nagad,
            # stripe, paypal, rocket) - using a real one instead.
            source='paypal',
            url_token='test-token-2',
            secret='test-secret-2',
            is_active=True,
            created_by=self.user,
        )
        inbounds = InboundWebhook.objects.all()
        serializer = InboundWebhookListSerializer(inbounds, many=True)
        self.assertEqual(len(serializer.data), 2)


class SerializerImportTestCase(TestCase):
    """Test that all serializers can be imported"""

    def test_all_serializers_importable(self):
        """Test all serializers are importable"""
        # This test verifies all missing serializers are now available
        serializers = [
            WebhookFilterCreateSerializer,
            WebhookFilterUpdateSerializer,
            WebhookFilterDetailSerializer,
            WebhookFilterListSerializer,
            WebhookBatchCreateSerializer,
            WebhookBatchUpdateSerializer,
            WebhookBatchDetailSerializer,
            WebhookBatchListSerializer,
            WebhookSecretCreateSerializer,
            WebhookSecretUpdateSerializer,
            WebhookSecretDetailSerializer,
            WebhookSecretListSerializer,
            WebhookTemplateCreateSerializer,
            WebhookTemplateUpdateSerializer,
            WebhookTemplateDetailSerializer,
            WebhookTemplateListSerializer,
            InboundWebhookListSerializer,
        ]
        # All should be importable
        self.assertEqual(len(serializers), 17)
        # All should be classes
        for serializer in serializers:
            self.assertTrue(hasattr(serializer, 'Meta'))
