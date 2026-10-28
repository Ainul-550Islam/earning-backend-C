"""
Tests for offer_routing/forms.py

Covers all five form classes:
  OfferRouteForm, RoutingABTestForm, BulkAssignmentForm,
  PerformanceReportForm, SystemConfigForm
"""

from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..forms import (
    OfferRouteForm,
    RoutingABTestForm,
    BulkAssignmentForm,
    PerformanceReportForm,
    SystemConfigForm,
)
from ..models import OfferRoute, RoutingABTest

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="formuser"):
    return User.objects.create_user(username=username, password="pass")


def make_route(tenant, name="Test Route", priority=5):
    return OfferRoute.objects.create(
        tenant=tenant,
        name=name,
        priority=priority,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# OfferRouteForm
# ---------------------------------------------------------------------------

class OfferRouteFormTest(TestCase):

    def _valid_data(self, **overrides):
        data = {
            "name": "My Route",
            "description": "A test route",
            "priority": 5,
            "max_offers": 10,
            "is_active": True,
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = OfferRouteForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_priority_too_low(self):
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)

    def test_priority_too_high(self):
        form = OfferRouteForm(data=self._valid_data(priority=11))
        self.assertFalse(form.is_valid())
        self.assertIn("priority", form.errors)

    def test_priority_boundary_values(self):
        for p in (1, 10):
            form = OfferRouteForm(data=self._valid_data(priority=p))
            self.assertTrue(form.is_valid(), f"priority={p} should be valid")

    def test_max_offers_zero_is_invalid(self):
        form = OfferRouteForm(data=self._valid_data(max_offers=0))
        self.assertFalse(form.is_valid())
        self.assertIn("max_offers", form.errors)

    def test_max_offers_one_is_valid(self):
        form = OfferRouteForm(data=self._valid_data(max_offers=1))
        self.assertTrue(form.is_valid(), form.errors)

    def test_name_required(self):
        form = OfferRouteForm(data=self._valid_data(name=""))
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_description_optional(self):
        form = OfferRouteForm(data=self._valid_data(description=""))
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# RoutingABTestForm
# ---------------------------------------------------------------------------

class RoutingABTestFormTest(TestCase):

    def setUp(self):
        self.tenant = make_user("abtestuser")
        self.control = make_route(self.tenant, "Control")
        self.variant = make_route(self.tenant, "Variant")

    def _valid_data(self, **overrides):
        data = {
            "name": "My AB Test",
            "description": "desc",
            "control_route": self.control.pk,
            "variant_route": self.variant.pk,
            "split_percentage": 50,
            "duration_hours": 24,
            "min_sample_size": 200,
            "confidence_level": 0.95,
            "success_metric": "conversion_rate",
            "is_active": True,
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = RoutingABTestForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_same_control_and_variant_raises(self):
        form = RoutingABTestForm(
            data=self._valid_data(variant_route=self.control.pk)
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_split_too_low(self):
        form = RoutingABTestForm(data=self._valid_data(split_percentage=0))
        self.assertFalse(form.is_valid())

    def test_split_too_high(self):
        form = RoutingABTestForm(data=self._valid_data(split_percentage=100))
        self.assertFalse(form.is_valid())

    def test_split_boundary_values(self):
        for s in (1, 99):
            form = RoutingABTestForm(data=self._valid_data(split_percentage=s))
            self.assertTrue(form.is_valid(), f"split={s} should be valid")

    def test_name_required(self):
        form = RoutingABTestForm(data=self._valid_data(name=""))
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)


# ---------------------------------------------------------------------------
# BulkAssignmentForm
# ---------------------------------------------------------------------------

class BulkAssignmentFormTest(TestCase):

    def setUp(self):
        self.tenant = make_user("bulkuser")
        self.route = make_route(self.tenant, "Bulk Route")

    def _valid_data(self, **overrides):
        data = {
            "user_ids": "1\n2\n3",
            "assignment_type": "assign_route",
            "route": self.route.pk,
            "new_priority": "",
            "dry_run": False,
        }
        data.update(overrides)
        return data

    def test_valid_assign_form(self):
        form = BulkAssignmentForm(data=self._valid_data(), tenant=self.tenant)
        self.assertTrue(form.is_valid(), form.errors)

    def test_user_ids_comma_separated(self):
        form = BulkAssignmentForm(
            data=self._valid_data(user_ids="10, 20, 30"),
            tenant=self.tenant,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["user_ids"], [10, 20, 30])

    def test_invalid_user_id(self):
        form = BulkAssignmentForm(
            data=self._valid_data(user_ids="1, abc, 3"),
            tenant=self.tenant,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("user_ids", form.errors)

    def test_empty_user_ids(self):
        form = BulkAssignmentForm(
            data=self._valid_data(user_ids="   "),
            tenant=self.tenant,
        )
        self.assertFalse(form.is_valid())

    def test_assign_route_requires_route(self):
        form = BulkAssignmentForm(
            data=self._valid_data(route=""),
            tenant=self.tenant,
        )
        self.assertFalse(form.is_valid())

    def test_update_priority_requires_new_priority(self):
        form = BulkAssignmentForm(
            data=self._valid_data(
                assignment_type="update_priority",
                route="",
                new_priority="",
            ),
            tenant=self.tenant,
        )
        self.assertFalse(form.is_valid())

    def test_activate_does_not_require_route(self):
        form = BulkAssignmentForm(
            data=self._valid_data(assignment_type="activate", route=""),
            tenant=self.tenant,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_no_tenant_gives_empty_route_queryset(self):
        form = BulkAssignmentForm(data=self._valid_data())
        # Without tenant kwarg the route queryset is none(); route pk is invalid
        self.assertFalse(form.is_valid())

    def test_dry_run_flag(self):
        form = BulkAssignmentForm(
            data=self._valid_data(dry_run=True),
            tenant=self.tenant,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.cleaned_data["dry_run"])


# ---------------------------------------------------------------------------
# PerformanceReportForm
# ---------------------------------------------------------------------------

class PerformanceReportFormTest(TestCase):

    def _valid_data(self, **overrides):
        data = {
            "report_type": "overview",
            "period_days": 30,
            "start_date": "",
            "end_date": "",
            "include_charts": True,
            "export_format": "html",
        }
        data.update(overrides)
        return data

    def test_valid_form_no_dates(self):
        form = PerformanceReportForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_form_with_dates(self):
        today = date.today()
        form = PerformanceReportForm(data=self._valid_data(
            start_date=(today - timedelta(days=14)).isoformat(),
            end_date=(today - timedelta(days=1)).isoformat(),
        ))
        self.assertTrue(form.is_valid(), form.errors)

    def test_start_after_end_is_invalid(self):
        today = date.today()
        form = PerformanceReportForm(data=self._valid_data(
            start_date=(today - timedelta(days=1)).isoformat(),
            end_date=(today - timedelta(days=7)).isoformat(),
        ))
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_end_date_in_future_is_invalid(self):
        today = date.today()
        form = PerformanceReportForm(data=self._valid_data(
            start_date=(today - timedelta(days=7)).isoformat(),
            end_date=(today + timedelta(days=1)).isoformat(),
        ))
        self.assertFalse(form.is_valid())

    def test_report_type_required(self):
        form = PerformanceReportForm(data=self._valid_data(report_type=""))
        self.assertFalse(form.is_valid())

    def test_all_report_types_accepted(self):
        for rt in ("overview", "route_performance", "ab_test_results",
                   "user_analytics", "revenue_report"):
            form = PerformanceReportForm(data=self._valid_data(report_type=rt))
            self.assertTrue(form.is_valid(), f"report_type={rt} should be valid")

    def test_all_export_formats_accepted(self):
        for fmt in ("json", "csv", "html"):
            form = PerformanceReportForm(data=self._valid_data(export_format=fmt))
            self.assertTrue(form.is_valid(), f"export_format={fmt} should be valid")


# ---------------------------------------------------------------------------
# SystemConfigForm
# ---------------------------------------------------------------------------

class SystemConfigFormTest(TestCase):

    def _valid_data(self, **overrides):
        data = {
            "cache_enabled": True,
            "cache_backend": "redis",
            "default_cache_ttl": 300,
            "routing_timeout_ms": 500,
            "max_offers_per_request": 50,
            "personalization_enabled": True,
            "ab_testing_enabled": True,
            "fallback_enabled": True,
            "debug_mode": False,
            "log_all_decisions": True,
            "decision_log_retention_days": 30,
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = SystemConfigForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_routing_timeout_below_50_invalid(self):
        form = SystemConfigForm(data=self._valid_data(routing_timeout_ms=49))
        self.assertFalse(form.is_valid())
        self.assertIn("routing_timeout_ms", form.errors)

    def test_routing_timeout_50_is_valid(self):
        form = SystemConfigForm(data=self._valid_data(routing_timeout_ms=50))
        self.assertTrue(form.is_valid(), form.errors)

    def test_routing_timeout_10000_is_valid(self):
        form = SystemConfigForm(data=self._valid_data(routing_timeout_ms=10000))
        self.assertTrue(form.is_valid(), form.errors)

    def test_routing_timeout_above_10000_invalid(self):
        form = SystemConfigForm(data=self._valid_data(routing_timeout_ms=10001))
        self.assertFalse(form.is_valid())

    def test_max_offers_per_request_zero_invalid(self):
        form = SystemConfigForm(data=self._valid_data(max_offers_per_request=0))
        self.assertFalse(form.is_valid())

    def test_max_offers_per_request_500_valid(self):
        form = SystemConfigForm(data=self._valid_data(max_offers_per_request=500))
        self.assertTrue(form.is_valid(), form.errors)

    def test_all_cache_backends_accepted(self):
        for backend in ("redis", "memcached", "database", "locmem"):
            form = SystemConfigForm(data=self._valid_data(cache_backend=backend))
            self.assertTrue(form.is_valid(), f"backend={backend} should be valid")

    def test_decision_log_retention_boundaries(self):
        for days in (1, 365):
            form = SystemConfigForm(data=self._valid_data(decision_log_retention_days=days))
            self.assertTrue(form.is_valid(), f"retention={days} should be valid")

    def test_decision_log_retention_zero_invalid(self):
        form = SystemConfigForm(data=self._valid_data(decision_log_retention_days=0))
        self.assertFalse(form.is_valid())
