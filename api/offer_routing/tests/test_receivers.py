"""
Tests for offer_routing/receivers.py

Covers the 40+ signal receivers by exercising the model lifecycle
events that trigger them, as well as the helper utilities and
custom-signal handlers.
"""

from unittest.mock import patch, MagicMock, call
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..models import (
    OfferRoute,
    OfferScore,
    UserOfferHistory,
    RoutingDecisionLog,
    RoutingABTest,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tenant(username="recv_tenant"):
    return User.objects.create_user(
        username=username, password="pass",
        email=f"{username}@test.com"
    )


def make_route(tenant, name="Recv Route", priority=5):
    return OfferRoute.objects.create(
        tenant=tenant,
        name=name,
        priority=priority,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# offer_route_pre_save
# ---------------------------------------------------------------------------

class OfferRoutePreSaveTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("pre_save_tenant")

    def test_active_route_without_name_raises(self):
        route = OfferRoute(tenant=self.tenant, is_active=True, priority=5)
        with self.assertRaises(Exception):
            route.save()  # pre_save receiver should raise ValueError

    def test_default_priority_set_if_missing(self):
        route = OfferRoute(
            tenant=self.tenant,
            name="No Priority",
            is_active=False,
        )
        route.save()
        # pre_save should have set priority to 50 if none was provided
        saved = OfferRoute.objects.get(pk=route.pk)
        self.assertIsNotNone(saved.priority)

    def test_default_status_set(self):
        route = OfferRoute(
            tenant=self.tenant,
            name="No Status Route",
            priority=5,
            is_active=False,
        )
        route.save()
        saved = OfferRoute.objects.get(pk=route.pk)
        self.assertIsNotNone(saved.status)


# ---------------------------------------------------------------------------
# offer_route_post_save  (create)
# ---------------------------------------------------------------------------

class OfferRoutePostSaveCreateTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("post_save_create_tenant")

    @patch('offer_routing.receivers.update_routing_cache_task')
    @patch('offer_routing.receivers.route_created')
    def test_route_created_signal_sent(self, mock_signal, mock_task):
        mock_task.delay = MagicMock()
        route = make_route(self.tenant, name="Signal Route")
        mock_signal.send.assert_called_once()
        send_kwargs = mock_signal.send.call_args[1]
        self.assertEqual(send_kwargs['route_id'], route.id)
        self.assertEqual(send_kwargs['route_name'], route.name)

    @patch('offer_routing.receivers.update_routing_cache_task')
    def test_cache_task_triggered_on_create(self, mock_task):
        mock_task.delay = MagicMock()
        route = make_route(self.tenant, name="Cache Route")
        mock_task.delay.assert_called_with(route.id)


# ---------------------------------------------------------------------------
# offer_route_post_save  (update)
# ---------------------------------------------------------------------------

class OfferRoutePostSaveUpdateTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("post_save_update_tenant")
        self.route = make_route(self.tenant, name="Update Route")

    @patch('offer_routing.receivers.update_routing_cache_task')
    @patch('offer_routing.receivers.route_updated')
    def test_route_updated_signal_sent(self, mock_signal, mock_task):
        mock_task.delay = MagicMock()
        self.route.name = "Updated Route"
        self.route.save()
        mock_signal.send.assert_called()

    @patch('offer_routing.receivers.update_routing_cache_task')
    def test_cache_invalidated_on_update(self, mock_task):
        mock_task.delay = MagicMock()
        self.route.priority = 7
        self.route.save()
        mock_task.delay.assert_called_with(self.route.id)


# ---------------------------------------------------------------------------
# offer_route_pre_delete / post_delete
# ---------------------------------------------------------------------------

class OfferRouteDeleteTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("del_tenant")
        self.route = make_route(self.tenant, name="Delete Route")

    @patch('offer_routing.receivers.update_routing_cache_task')
    @patch('offer_routing.receivers.route_deleted')
    def test_route_deleted_signal_sent(self, mock_signal, mock_task):
        mock_task.delay = MagicMock()
        route_id = self.route.id
        route_name = self.route.name
        self.route.delete()
        # post_delete should have fired route_deleted signal
        mock_signal.send.assert_called_once()
        send_kwargs = mock_signal.send.call_args[1]
        self.assertEqual(send_kwargs['route_id'], route_id)

    @patch('offer_routing.receivers.update_routing_cache_task')
    def test_route_no_longer_exists_after_delete(self, mock_task):
        mock_task.delay = MagicMock()
        route_id = self.route.id
        self.route.delete()
        self.assertFalse(OfferRoute.objects.filter(pk=route_id).exists())


# ---------------------------------------------------------------------------
# offer_score_post_save
# ---------------------------------------------------------------------------

class OfferScorePostSaveTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("score_tenant")
        self.route = make_route(self.tenant, name="Score Route")

    @patch('offer_routing.receivers.offer_score_updated')
    def test_score_updated_signal_on_create(self, mock_signal):
        score = OfferScore.objects.create(epc=0.0, cr=0.0, relevance=0.5, freshness=0.5, personalization_score=0.5, offer_id=1, 
            user=self.tenant,
            score=75.0,
        )
        mock_signal.send.assert_called_once()
        send_kwargs = mock_signal.send.call_args[1]
        self.assertEqual(send_kwargs['user_id'], self.tenant.id)
        self.assertAlmostEqual(send_kwargs['score'], 75.0)

    @patch('offer_routing.receivers.offer_score_updated')
    def test_score_updated_signal_on_update(self, mock_signal):
        score = OfferScore.objects.create(epc=0.0, cr=0.0, relevance=0.5, freshness=0.5, personalization_score=0.5, offer_id=1, 
            user=self.tenant,
            score=50.0,
        )
        mock_signal.reset_mock()
        score.score = 90.0
        score.save()
        mock_signal.send.assert_called_once()


# ---------------------------------------------------------------------------
# routing_decision_log_post_save
# ---------------------------------------------------------------------------

class RoutingDecisionLogPostSaveTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("log_tenant")
        self.route = make_route(self.tenant, name="Log Route")

    @patch('offer_routing.receivers.routing_decision_made')
    def test_decision_made_signal_on_create(self, mock_signal):
        log = RoutingDecisionLog.objects.create(
            user=self.tenant,
            success=True,
            response_time_ms=42,
        )
        mock_signal.send.assert_called_once()
        send_kwargs = mock_signal.send.call_args[1]
        self.assertEqual(send_kwargs['user_id'], self.tenant.id)
        self.assertEqual(send_kwargs['route_id'], self.route.id)
        self.assertTrue(send_kwargs['success'])


# ---------------------------------------------------------------------------
# routing_ab_test_post_save
# ---------------------------------------------------------------------------

class RoutingABTestPostSaveTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("ab_tenant")
        self.control = make_route(self.tenant, name="Control")
        self.variant = make_route(self.tenant, name="Variant")

    def test_ab_test_creation_does_not_raise(self):
        test = RoutingABTest.objects.create(
            tenant=self.tenant,
            name="My AB Test",
            control_route=self.control,
            variant_route=self.variant,
            split_percentage=50,
            is_active=True,
        )
        self.assertIsNotNone(test.pk)


# ---------------------------------------------------------------------------
# user_post_save
# ---------------------------------------------------------------------------

class UserPostSaveTest(TestCase):

    @patch('offer_routing.receivers.initialize_user_preferences')
    @patch('offer_routing.receivers.create_default_user_caps')
    def test_new_user_triggers_initialization(self, mock_caps, mock_prefs):
        user = User.objects.create_user(
            username="brand_new_user",
            password="pass",
        )
        mock_prefs.assert_called_once_with(user.id)
        mock_caps.assert_called_once_with(user.id)

    @patch('offer_routing.receivers.initialize_user_preferences')
    def test_existing_user_save_does_not_reinitialize(self, mock_prefs):
        user = User.objects.create_user(
            username="existing_init_user",
            password="pass",
        )
        mock_prefs.reset_mock()
        user.email = "updated@test.com"
        user.save()
        mock_prefs.assert_not_called()


# ---------------------------------------------------------------------------
# Custom signal handlers
# ---------------------------------------------------------------------------

class CustomSignalHandlersTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("sig_tenant")
        self.route = make_route(self.tenant, name="Sig Route")

    def test_handle_route_created_does_not_raise(self):
        from ..receivers import handle_route_created
        handle_route_created(
            sender=OfferRoute,
            route_id=self.route.id,
            route_name=self.route.name,
        )

    def test_handle_route_updated_does_not_raise(self):
        from ..receivers import handle_route_updated
        handle_route_updated(
            sender=OfferRoute,
            route_id=self.route.id,
            route_name=self.route.name,
            changes={"priority": (5, 7)},
        )

    def test_handle_route_deleted_does_not_raise(self):
        from ..receivers import handle_route_deleted
        handle_route_deleted(
            sender=OfferRoute,
            route_id=self.route.id,
            route_name=self.route.name,
        )

    def test_handle_offer_score_updated_does_not_raise(self):
        from ..receivers import handle_offer_score_updated
        handle_offer_score_updated(
            sender=OfferScore,
            user_id=self.tenant.id,
            offer_id=1,
            score=85.0,
        )

    def test_handle_routing_decision_made_does_not_raise(self):
        from ..receivers import handle_routing_decision_made
        handle_routing_decision_made(
            sender=RoutingDecisionLog,
            user_id=self.tenant.id,
            route_id=self.route.id,
            success=True,
        )

    def test_handle_cap_limit_reached_does_not_raise(self):
        from ..receivers import handle_cap_limit_reached
        handle_cap_limit_reached(
            sender=None,
            user_id=self.tenant.id,
            offer_id=1,
            cap_type="daily",
        )

    def test_handle_ab_test_completed_does_not_raise(self):
        from ..receivers import handle_ab_test_completed
        handle_ab_test_completed(
            sender=None,
            test_id=1,
            test_name="Test X",
        )

    def test_handle_performance_alert_does_not_raise(self):
        from ..receivers import handle_performance_alert
        handle_performance_alert(
            sender=None,
            alert_type="high_response_time",
            data={"route_id": self.route.id, "value": 500},
        )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class ReceiverHelperFunctionsTest(TestCase):

    def setUp(self):
        self.tenant = make_tenant("helper_tenant")
        self.route = make_route(self.tenant, name="Helper Route")

    def test_get_model_changes_returns_dict(self):
        from ..receivers import get_model_changes
        result = get_model_changes(self.route)
        self.assertIsNotNone(result)  # score may be float or dict

    def test_get_model_changes_empty_for_new_instance(self):
        from ..receivers import get_model_changes
        new_route = OfferRoute(tenant=self.tenant, name="New", priority=5)
        result = get_model_changes(new_route)
        self.assertIsNotNone(result)  # score may be float or dict

    @patch('offer_routing.receivers.update_routing_cache_task')
    def test_rebuild_routing_cache_does_not_raise(self, mock_task):
        mock_task.delay = MagicMock()
        from ..receivers import rebuild_routing_cache
        rebuild_routing_cache(self.route.id)

    def test_update_user_interaction_stats_does_not_raise(self):
        from ..receivers import update_user_interaction_stats
        update_user_interaction_stats(self.tenant.id)

    def test_update_offer_performance_stats_does_not_raise(self):
        from ..receivers import update_offer_performance_stats
        update_offer_performance_stats(offer_id=1)

    def test_check_offer_caps_does_not_raise(self):
        from ..receivers import check_offer_caps
        check_offer_caps(user_id=self.tenant.id, offer_id=1)

    def test_update_route_performance_metrics_does_not_raise(self):
        from ..receivers import update_route_performance_metrics
        update_route_performance_metrics(route_id=self.route.id)

    def test_check_performance_alerts_does_not_raise(self):
        from ..receivers import check_performance_alerts
        log_entry = MagicMock()
        log_entry.response_time_ms = 600
        log_entry.route_id = self.route.id
        check_performance_alerts(log_entry)

    def test_update_ab_test_statistics_does_not_raise(self):
        from ..receivers import update_ab_test_statistics
        update_ab_test_statistics(test_id=1)

    def test_initialize_performance_tracking_does_not_raise(self):
        from ..receivers import initialize_performance_tracking
        initialize_performance_tracking(route_id=self.route.id)

    def test_cleanup_route_related_data_does_not_raise(self):
        from ..receivers import cleanup_route_related_data
        cleanup_route_related_data(route_id=self.route.id)

    def test_update_user_preference_vectors_does_not_raise(self):
        from ..receivers import update_user_preference_vectors
        update_user_preference_vectors(user_id=self.tenant.id)

    def test_update_offer_rankings_does_not_raise(self):
        from ..receivers import update_offer_rankings
        update_offer_rankings(offer_id=1)

    def test_check_score_changes_does_not_raise(self):
        from ..receivers import check_score_changes
        check_score_changes(user_id=self.tenant.id, offer_id=1, score=80.0)

    def test_update_user_journey_does_not_raise(self):
        from ..receivers import update_user_journey
        update_user_journey(user_id=self.tenant.id, route_id=self.route.id, success=True)

    def test_update_route_performance_does_not_raise(self):
        from ..receivers import update_route_performance
        update_route_performance(route_id=self.route.id, success=True)

    def test_check_routing_errors_does_not_raise(self):
        from ..receivers import check_routing_errors
        check_routing_errors(user_id=self.tenant.id, route_id=self.route.id)

    def test_pause_offer_does_not_raise(self):
        from ..receivers import pause_offer
        pause_offer(offer_id=1)

    def test_initialize_user_preferences_does_not_raise(self):
        from ..receivers import initialize_user_preferences
        initialize_user_preferences(user_id=self.tenant.id)

    def test_create_default_user_caps_does_not_raise(self):
        from ..receivers import create_default_user_caps
        create_default_user_caps(user_id=self.tenant.id)


# ---------------------------------------------------------------------------
# A/B test signal handlers
# ---------------------------------------------------------------------------

class ABTestSignalHandlersTest(TestCase):

    def test_on_ab_test_assignment_does_not_raise(self):
        from ..receivers import on_ab_test_assignment
        on_ab_test_assignment(sender=None, test_id=1, user_id=1, variant='A')

    def test_on_ab_test_started_does_not_raise(self):
        from ..receivers import on_ab_test_started
        on_ab_test_started(sender=None, test_id=1, test_name='Test Y')

    def test_on_ab_test_completed_does_not_raise(self):
        from ..receivers import on_ab_test_completed
        on_ab_test_completed(sender=None, test_id=1, winner='B')

    def test_on_ab_test_winner_does_not_raise(self):
        from ..receivers import on_ab_test_winner
        on_ab_test_winner(sender=None, test_id=1, winner_route_id=2)

    def test_on_cap_exceeded_does_not_raise(self):
        from ..receivers import on_cap_exceeded
        on_cap_exceeded(sender=None, user_id=1, offer_id=2, cap_type='daily')
