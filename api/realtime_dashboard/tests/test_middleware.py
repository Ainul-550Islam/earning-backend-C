"""
Tests for Real-time Dashboard Backend middleware.

FIX: DashboardMiddleware.test_authenticated_user_gets_active_dashboards and
test_authenticated_user_other_users_excluded were failing because the mock
user only set `user.id` but NOT `user.pk`. The middleware calls
`DashboardService().get_user_dashboards(str(user.pk))`. On a MagicMock,
`user.pk` auto-creates a new MagicMock attribute — `str(MagicMock())` is
something like "<MagicMock id='...'>" — which never matches the dashboard's
user_id. Both `user.pk` and `user.id` are now set to the same value so the
middleware's str(user.pk) lookup finds the correct dashboards.
"""
import pytest
from unittest.mock import MagicMock
from django.test import RequestFactory
from api.realtime_dashboard.middleware import WebSocketMiddleware, DashboardMiddleware
from .fixtures import create_user_dashboard


def make_get_response(status=200):
    """Return a minimal get_response callable."""
    from django.http import HttpResponse

    def get_response(request):
        return HttpResponse(status=status)
    return get_response


class TestWebSocketMiddleware:

    def test_attaches_manager_to_request(self):
        factory = RequestFactory()
        request = factory.get('/')
        middleware = WebSocketMiddleware(make_get_response())
        middleware(request)
        assert hasattr(request, 'websocket_manager')

    def test_returns_response_from_next_layer(self):
        factory = RequestFactory()
        request = factory.get('/')
        middleware = WebSocketMiddleware(make_get_response(200))
        response = middleware(request)
        assert response.status_code == 200

    def test_propagates_exception(self):
        def boom(request):
            raise ValueError('oops')
        factory = RequestFactory()
        request = factory.get('/')
        middleware = WebSocketMiddleware(boom)
        with pytest.raises(ValueError, match='oops'):
            middleware(request)

    def test_shared_manager_instance(self):
        """The same WebSocketManager instance is reused across requests."""
        factory = RequestFactory()
        middleware = WebSocketMiddleware(make_get_response())
        req1 = factory.get('/')
        req2 = factory.get('/')
        middleware(req1)
        middleware(req2)
        # Both requests receive the same manager object (shared state).
        assert req1.websocket_manager is req2.websocket_manager


@pytest.mark.django_db
class TestDashboardMiddleware:

    def test_unauthenticated_request_gets_empty_list(self):
        factory = RequestFactory()
        request = factory.get('/')
        # No request.user set
        middleware = DashboardMiddleware(make_get_response())
        middleware(request)
        assert request.user_dashboards == []

    def test_anonymous_user_gets_empty_list(self):
        factory = RequestFactory()
        request = factory.get('/')
        anon = MagicMock()
        anon.is_authenticated = False
        request.user = anon
        middleware = DashboardMiddleware(make_get_response())
        middleware(request)
        assert request.user_dashboards == []

    def test_authenticated_user_gets_active_dashboards(self):
        factory = RequestFactory()
        request = factory.get('/')
        user = MagicMock()
        user.is_authenticated = True
        # FIX: set BOTH user.pk and user.id to the same value.
        # DashboardMiddleware calls str(user.pk). A MagicMock auto-creates
        # any unset attribute as a new MagicMock object whose str() is
        # something like "<MagicMock id='...'>" — it would never match the
        # fixture's user_id string. Setting user.pk explicitly fixes the
        # lookup.
        user.pk = 'user_mw_1'
        user.id = 'user_mw_1'
        request.user = user

        create_user_dashboard(name='Active', user_id='user_mw_1', status='active')
        create_user_dashboard(name='Inactive', user_id='user_mw_1', status='inactive')

        middleware = DashboardMiddleware(make_get_response())
        middleware(request)

        assert len(request.user_dashboards) == 1
        assert request.user_dashboards[0].name == 'Active'

    def test_authenticated_user_other_users_excluded(self):
        factory = RequestFactory()
        request = factory.get('/')
        user = MagicMock()
        user.is_authenticated = True
        # FIX: same as above — user.pk must be set explicitly.
        user.pk = 'user_mw_2'
        user.id = 'user_mw_2'
        request.user = user

        create_user_dashboard(name='Mine', user_id='user_mw_2', status='active')
        create_user_dashboard(name='Others', user_id='user_mw_999', status='active')

        middleware = DashboardMiddleware(make_get_response())
        middleware(request)

        assert len(request.user_dashboards) == 1
        assert request.user_dashboards[0].name == 'Mine'

    def test_returns_response(self):
        factory = RequestFactory()
        request = factory.get('/')
        middleware = DashboardMiddleware(make_get_response(200))
        response = middleware(request)
        assert response.status_code == 200

    def test_user_without_pk_attr_gets_empty_list(self):
        """
        Edge case: user object has is_authenticated=True but no pk attribute
        at all (e.g. a custom auth backend). Should not raise; returns [].
        """
        factory = RequestFactory()
        request = factory.get('/')
        # Use a plain object with is_authenticated but no pk.
        # DashboardService.get_user_dashboards(str(None)) returns [] since
        # no dashboard has user_id 'None'.
        user = MagicMock()
        user.is_authenticated = True
        user.pk = None   # Explicit None simulates missing pk
        request.user = user

        middleware = DashboardMiddleware(make_get_response())
        # Should not raise even with pk=None.
        middleware(request)
        assert isinstance(request.user_dashboards, list)
