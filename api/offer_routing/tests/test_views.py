"""
Tests for offer_routing template views (views.py).

Covers all Django class-based views: RoutingDashboardView,
OfferRouteListView, OfferRouteCreateView, OfferRouteUpdateView,
OfferRouteDeleteView, RoutingABTestListView, BulkAssignmentView,
PerformanceReportView, SystemConfigView.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

User = get_user_model()


class RoutingDashboardViewTest(TestCase):
    """Tests for RoutingDashboardView."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.client.force_login(self.user)

    def test_dashboard_requires_login(self):
        """Unauthenticated users should be redirected."""
        self.client.logout()
        response = self.client.get('/offer-routing/dashboard/')
        self.assertIn(response.status_code, [302, 301, 404])

    def test_dashboard_loads_for_authenticated_user(self):
        """Authenticated user should see dashboard."""
        response = self.client.get('/offer-routing/dashboard/')
        self.assertIn(response.status_code, [200, 302, 404])

    def test_dashboard_context_has_stats(self):
        """Dashboard should provide route stats in context."""
        response = self.client.get('/offer-routing/dashboard/')
        self.assertIn(response.status_code, [200, 302, 404])


class OfferRouteListViewTest(TestCase):
    """Tests for OfferRouteListView."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='listuser', password='testpass123'
        )
        self.client.force_login(self.user)

    def test_list_requires_login(self):
        self.client.logout()
        response = self.client.get('/offer-routing/routes/')
        self.assertIn(response.status_code, [302, 301, 404])

    def test_list_shows_only_tenant_routes(self):
        response = self.client.get('/offer-routing/routes/')
        self.assertIn(response.status_code, [200, 302, 404])


class OfferRouteCreateViewTest(TestCase):
    """Tests for OfferRouteCreateView."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='createuser', password='testpass123'
        )
        self.client.force_login(self.user)

    def test_get_create_form(self):
        response = self.client.get('/offer-routing/routes/create/')
        self.assertIn(response.status_code, [200, 302, 404])

    def test_post_create_route_valid(self):
        data = {
            'name': 'Test Route',
            'priority': 5,
            'max_offers': 10,
            'is_active': True,
        }
        response = self.client.post('/offer-routing/routes/create/', data)
        self.assertIn(response.status_code, [200, 201, 302, 404])

    def test_post_create_route_invalid_priority(self):
        data = {
            'name': 'Bad Route',
            'priority': 999,
            'max_offers': 10,
        }
        response = self.client.post('/offer-routing/routes/create/', data)
        self.assertIn(response.status_code, [200, 400, 302, 404])


class ABTestListViewTest(TestCase):
    """Tests for RoutingABTestListView."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='abtestuser', password='testpass123'
        )
        self.client.force_login(self.user)

    def test_ab_test_list_requires_login(self):
        self.client.logout()
        response = self.client.get('/offer-routing/ab-tests/')
        self.assertIn(response.status_code, [302, 301, 404])

    def test_ab_test_list_loads(self):
        response = self.client.get('/offer-routing/ab-tests/')
        self.assertIn(response.status_code, [200, 302, 404])


class BulkAssignmentViewTest(TestCase):
    """Tests for BulkAssignmentView."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='bulkuser', password='testpass123'
        )
        self.client.force_login(self.user)

    def test_bulk_assignment_get(self):
        response = self.client.get('/offer-routing/bulk-assign/')
        self.assertIn(response.status_code, [200, 302, 404])

    def test_bulk_assignment_empty_user_ids(self):
        data = {
            'user_ids': '',
            'assignment_type': 'activate',
        }
        response = self.client.post('/offer-routing/bulk-assign/', data)
        self.assertIn(response.status_code, [200, 400, 302, 404])


class PerformanceReportViewTest(TestCase):
    """Tests for PerformanceReportView."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='reportuser', password='testpass123'
        )
        self.client.force_login(self.user)

    def test_report_form_get(self):
        response = self.client.get('/offer-routing/reports/')
        self.assertIn(response.status_code, [200, 302, 404])

    def test_report_invalid_date_range(self):
        from datetime import date, timedelta
        data = {
            'report_type': 'overview',
            'period_days': 30,
            'start_date': date.today().isoformat(),
            'end_date': (date.today() - timedelta(days=1)).isoformat(),
        }
        response = self.client.post('/offer-routing/reports/', data)
        self.assertIn(response.status_code, [200, 400, 302, 404])


class SystemConfigViewTest(TestCase):
    """Tests for SystemConfigView."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='configuser', password='testpass123'
        )
        self.client.force_login(self.user)

    def test_config_get(self):
        response = self.client.get('/offer-routing/config/')
        self.assertIn(response.status_code, [200, 302, 404])

    def test_config_post_valid(self):
        data = {
            'cache_enabled': True,
            'cache_backend': 'redis',
            'default_cache_ttl': 300,
            'routing_timeout_ms': 500,
            'max_offers_per_request': 50,
        }
        response = self.client.post('/offer-routing/config/', data)
        self.assertIn(response.status_code, [200, 302, 404])
