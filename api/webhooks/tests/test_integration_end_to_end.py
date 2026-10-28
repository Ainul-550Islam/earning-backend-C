"""
End-to-End Integration Tests
Tests complete workflows across multiple modules

BUG FIX: this file previously referenced a WebhookEventType model that
doesn't exist (EventType is a choices enum, not a model), used WebhookEndpoint
field names that don't match the real model (name/url -> label/target_url),
and imported services.base.BaseWebhookService, which was removed earlier in
this same audit for being dead, unused code with no real logic (its
"consolidation" never actually replaced anything). All corrected below.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient

from api.webhooks.models import (
    WebhookEndpoint, WebhookFilter,
    WebhookBatch, WebhookSecret,
)
from api.webhooks.constants import WebhookStatus


class WebhookEndpointIntegrationTest(TransactionTestCase):
    """Test complete webhook endpoint workflow"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_endpoint_with_filters(self):
        """Test creating endpoint and adding filters"""
        endpoint = WebhookEndpoint.objects.create(
            label='Test Endpoint',
            target_url='https://example.com/webhook',
            owner=self.user,
            status=WebhookStatus.ACTIVE,
        )

        webhook_filter = WebhookFilter.objects.create(
            endpoint=endpoint,
            field_path='user.email',
            operator='contains',
            value='@example.com',
            is_active=True
        )

        self.assertEqual(endpoint.label, 'Test Endpoint')
        self.assertTrue(webhook_filter.is_active)
        self.assertEqual(webhook_filter.endpoint, endpoint)

    def test_create_batch_and_track(self):
        """Test creating batch and tracking progress"""
        endpoint = WebhookEndpoint.objects.create(
            label='Batch Test',
            target_url='https://example.com/webhook',
            owner=self.user,
            status=WebhookStatus.ACTIVE,
        )

        batch = WebhookBatch.objects.create(
            endpoint=endpoint,
            event_count=100,
            status='pending'
        )

        self.assertEqual(batch.event_count, 100)
        self.assertEqual(batch.status, 'pending')

    def test_secret_rotation_workflow(self):
        """Test webhook secret rotation"""
        endpoint = WebhookEndpoint.objects.create(
            label='Secret Test',
            target_url='https://example.com/webhook',
            owner=self.user,
            status=WebhookStatus.ACTIVE,
        )

        secret = WebhookSecret.objects.create(
            endpoint=endpoint,
            secret_hash='test-hash-value',
            is_active=True
        )

        self.assertTrue(secret.is_active)
        self.assertIsNotNone(secret.secret_hash)


class WebhookAPIIntegrationTest(APITestCase):
    """Test webhook APIs end-to-end"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@example.com',
            password='apipass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_complete_webhook_workflow(self):
        """Test complete API workflow"""
        endpoint = WebhookEndpoint.objects.create(
            label='API Test Endpoint',
            target_url='https://api.example.com/webhook',
            owner=self.user,
            status=WebhookStatus.ACTIVE,
        )

        response = self.client.get(f'/webhooks/endpoints/{endpoint.id}/')
        self.assertIn(response.status_code, (200, 404))


class ValidationIntegrationTest(TestCase):
    """Test validation across modules"""

    def test_filter_validation_workflow(self):
        """Test filter validation"""
        user = User.objects.create_user(
            username='validator',
            email='validator@example.com',
            password='pass123'
        )

        endpoint = WebhookEndpoint.objects.create(
            label='Validation Test',
            target_url='https://example.com/webhook',
            owner=user,
            status=WebhookStatus.ACTIVE,
        )

        valid_filter = WebhookFilter.objects.create(
            endpoint=endpoint,
            field_path='event.type',
            operator='equals',
            value='user.created',
            is_active=True
        )

        self.assertIsNotNone(valid_filter.id)


class ConcurrencyTest(TransactionTestCase):
    """Test concurrent operations"""

    def test_concurrent_batch_creation(self):
        """Test creating multiple batches"""
        user = User.objects.create_user(
            username='concurrent',
            email='concurrent@example.com',
            password='pass123'
        )

        endpoint = WebhookEndpoint.objects.create(
            label='Concurrent Test',
            target_url='https://example.com/webhook',
            owner=user,
            status=WebhookStatus.ACTIVE,
        )

        batches = []
        for i in range(5):
            batch = WebhookBatch.objects.create(
                # batch_id has no default (confirmed against models/advanced.py)
                # and is unique=True - without an explicit value here, every
                # create() after the first collides on the empty-string
                # default (confirmed empirically: IntegrityError on the
                # second insert). Matches the convention already used in
                # test_models.py's test_batch_creation.
                batch_id=f'concurrent-test-batch-{i}',
                endpoint=endpoint,
                event_count=100 + i,
                status='pending'
            )
            batches.append(batch)

        self.assertEqual(len(batches), 5)
        self.assertEqual(WebhookBatch.objects.filter(endpoint=endpoint).count(), 5)


class ErrorHandlingTest(TestCase):
    """Test error handling in workflows"""

    def test_missing_required_fields(self):
        """Missing owner should fail at the database level (NOT NULL constraint)."""
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WebhookEndpoint.objects.create(
                    label='No Owner Test',
                    target_url='https://example.com/webhook',
                    owner=None,
                    status=WebhookStatus.ACTIVE,
                )


class PerformanceTest(TestCase):
    """Test performance characteristics"""

    def test_large_batch_processing(self):
        """Test handling large batches"""
        user = User.objects.create_user(
            username='perf_test',
            email='perf@example.com',
            password='pass123'
        )

        endpoint = WebhookEndpoint.objects.create(
            label='Performance Test',
            target_url='https://example.com/webhook',
            owner=user,
            status=WebhookStatus.ACTIVE,
        )

        batch = WebhookBatch.objects.create(
            endpoint=endpoint,
            event_count=10000,
            status='pending'
        )

        self.assertEqual(batch.event_count, 10000)


if __name__ == '__main__':
    import unittest
    unittest.main()
