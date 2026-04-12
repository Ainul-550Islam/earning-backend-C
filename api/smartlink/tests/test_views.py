from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .factories import SmartLinkFactory, UserFactory, SmartLinkGroupFactory


class SmartLinkAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.publisher = UserFactory()
        self.client.force_authenticate(user=self.publisher)
        self.sl = SmartLinkFactory(publisher=self.publisher)

    def test_list_smartlinks(self):
        response = self.client.get('/api/smartlink/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_create_smartlink(self):
        data = {'name': 'New Link', 'type': 'general'}
        response = self.client.post('/api/smartlink/smartlinks/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('slug', response.data)

    def test_retrieve_smartlink(self):
        response = self.client.get(f'/api/smartlink/smartlinks/{self.sl.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], self.sl.slug)

    def test_update_smartlink_name(self):
        response = self.client.patch(
            f'/api/smartlink/smartlinks/{self.sl.pk}/',
            {'name': 'Updated Name'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_smartlink_archives(self):
        response = self.client.delete(f'/api/smartlink/smartlinks/{self.sl.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.sl.refresh_from_db()
        self.assertTrue(self.sl.is_archived)

    def test_cannot_access_other_publisher_smartlink(self):
        other = UserFactory()
        other_sl = SmartLinkFactory(publisher=other)
        response = self.client.get(f'/api/smartlink/smartlinks/{other_sl.pk}/')
        self.assertIn(response.status_code, [403, 404])

    def test_toggle_active(self):
        response = self.client.post(f'/api/smartlink/smartlinks/{self.sl.pk}/toggle-active/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.sl.refresh_from_db()
        self.assertFalse(self.sl.is_active)

    def test_stats_endpoint(self):
        response = self.client.get(f'/api/smartlink/smartlinks/{self.sl.pk}/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('clicks', response.data)

    def test_unauthenticated_denied(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/smartlink/smartlinks/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PublicRedirectViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sl = SmartLinkFactory(is_active=True)

    def test_invalid_slug_returns_404(self):
        response = self.client.get('/go/nonexistentslugxyz/')
        self.assertEqual(response.status_code, 404)

    def test_inactive_link_returns_410(self):
        self.sl.is_active = False
        self.sl.save()
        response = self.client.get(f'/go/{self.sl.slug}/')
        self.assertEqual(response.status_code, 410)
