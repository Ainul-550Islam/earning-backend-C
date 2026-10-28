"""
Security regression tests for Real-time Dashboard Backend.

This file covers:
  1. IDOR on UserDashboard.activate() / deactivate() — fixed in decorators.py
  2. IDOR on UserDashboard.render() — fixed in user_dashboard_viewset.py
  3. Cross-user ownership isolation on list / retrieve / mutate
  4. WebSocketConnection ownership isolation
  5. Non-staff access to staff-only endpoints (by_user actions)
  6. perform_create() user_id hijack prevention

Each test is named with its CVE-style category for clarity in CI output.
"""
import pytest
from django.urls import reverse
from api.realtime_dashboard.models.user_dashboard import UserDashboard
from .fixtures import (
    create_user_dashboard,
    create_dashboard_widget,
    create_websocket_connection,
)


# ─── IDOR: UserDashboard activate / deactivate ───────────────────────────────

@pytest.mark.django_db
class TestIDOR_UserDashboardActivate:
    """
    Before the decorators.py IDOR fix, any authenticated user could POST to
    /api/dashboards/<any_id>/activate/ or /deactivate/ regardless of ownership.

    After the fix, require_dashboard calls
    self.check_object_permissions(request, request.dashboard) which raises
    PermissionDenied (→ HTTP 403) for non-owners.
    """

    def test_owner_can_activate_own_dashboard(
        self, authenticated_api_client, test_user
    ):
        """Positive control: owner can activate their own dashboard."""
        dashboard = create_user_dashboard(
            status='inactive', user_id=str(test_user.pk)
        )
        response = authenticated_api_client.post(
            reverse('userdashboard-activate', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 200
        dashboard.refresh_from_db()
        assert dashboard.status == UserDashboard.DashboardStatus.ACTIVE

    def test_non_owner_cannot_activate_other_users_dashboard(
        self, authenticated_second_client, test_user
    ):
        """SECURITY: non-owner activation must be blocked (IDOR fix)."""
        # Dashboard belongs to test_user, but second_user is making the request.
        victim_dashboard = create_user_dashboard(
            status='inactive', user_id=str(test_user.pk)
        )
        response = authenticated_second_client.post(
            reverse('userdashboard-activate', kwargs={'pk': victim_dashboard.pk})
        )
        assert response.status_code in (403, 404), (
            f"IDOR BUG: Expected 403/404 but got {response.status_code}. "
            f"second_user can activate test_user's dashboard — IDOR is NOT fixed."
        )
        # Status must remain unchanged.
        victim_dashboard.refresh_from_db()
        assert victim_dashboard.status == UserDashboard.DashboardStatus.INACTIVE, (
            "IDOR BUG: dashboard status changed despite the request coming from "
            "a user who does not own it."
        )

    def test_owner_can_deactivate_own_dashboard(
        self, authenticated_api_client, test_user
    ):
        """Positive control: owner can deactivate their own dashboard."""
        dashboard = create_user_dashboard(
            status='active', user_id=str(test_user.pk)
        )
        response = authenticated_api_client.post(
            reverse('userdashboard-deactivate', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 200
        dashboard.refresh_from_db()
        assert dashboard.status == UserDashboard.DashboardStatus.INACTIVE

    def test_non_owner_cannot_deactivate_other_users_dashboard(
        self, authenticated_second_client, test_user
    ):
        """SECURITY: non-owner deactivation must be blocked (IDOR fix)."""
        victim_dashboard = create_user_dashboard(
            status='active', user_id=str(test_user.pk)
        )
        response = authenticated_second_client.post(
            reverse('userdashboard-deactivate', kwargs={'pk': victim_dashboard.pk})
        )
        assert response.status_code in (403, 404), (
            f"IDOR BUG: Expected 403/404 but got {response.status_code}."
        )
        victim_dashboard.refresh_from_db()
        assert victim_dashboard.status == UserDashboard.DashboardStatus.ACTIVE, (
            "IDOR BUG: dashboard deactivated by a non-owner."
        )

    def test_unauthenticated_activate_rejected(self, api_client, test_user):
        """Unauthenticated requests must be rejected before even fetching the object."""
        dashboard = create_user_dashboard(
            status='inactive', user_id=str(test_user.pk)
        )
        response = api_client.post(
            reverse('userdashboard-activate', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code in (401, 403)
        dashboard.refresh_from_db()
        assert dashboard.status == UserDashboard.DashboardStatus.INACTIVE


# ─── IDOR: UserDashboard render ──────────────────────────────────────────────

@pytest.mark.django_db
class TestIDOR_UserDashboardRender:
    """
    Before the user_dashboard_viewset.py render IDOR fix, any authenticated
    user could GET /api/dashboards/<any_id>/render/ and receive the full
    rendered output of another user's dashboard.

    After the fix, render() calls self.get_object() which applies
    get_queryset() (user-scoped) and check_object_permissions().
    """

    def test_owner_can_render_own_dashboard(
        self, authenticated_api_client, test_user
    ):
        """Positive control: owner can render their own dashboard."""
        widget = create_dashboard_widget(name='TestWidget')
        dashboard = create_user_dashboard(
            widgets=[widget.pk], user_id=str(test_user.pk)
        )
        response = authenticated_api_client.get(
            reverse('userdashboard-render', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 200
        assert response.data['success'] is True

    def test_non_owner_cannot_render_other_users_dashboard(
        self, authenticated_second_client, test_user
    ):
        """SECURITY: non-owner render must be blocked (IDOR fix)."""
        widget = create_dashboard_widget(name='VictimWidget')
        victim_dashboard = create_user_dashboard(
            widgets=[widget.pk], user_id=str(test_user.pk)
        )
        # second_user attempts to render test_user's dashboard.
        response = authenticated_second_client.get(
            reverse('userdashboard-render', kwargs={'pk': victim_dashboard.pk})
        )
        # get_object() scopes by user → 404 (dashboard not in second_user's QS)
        assert response.status_code in (403, 404), (
            f"IDOR BUG: Expected 403/404 but got {response.status_code}. "
            f"second_user can render test_user's dashboard."
        )

    def test_render_nonexistent_dashboard_returns_404(
        self, authenticated_api_client
    ):
        """get_object() on a missing pk must return 404, not 500."""
        response = authenticated_api_client.get(
            reverse('userdashboard-render', kwargs={'pk': 999999})
        )
        assert response.status_code == 404


# ─── user_id hijack on create ────────────────────────────────────────────────

@pytest.mark.django_db
class TestUserIdHijackOnCreate:
    """
    perform_create() must ignore any client-supplied user_id and always
    set user_id = str(request.user.pk). Without this, user A could POST
    user_id='<user_B_pk>' to create dashboards attributed to any user.
    """

    def test_supplied_user_id_is_ignored(self, authenticated_api_client, test_user):
        """Client-supplied user_id must not be persisted."""
        attacker_supplied_id = 'any_victim_user_id'
        data = {
            'name': 'Hijack Attempt',
            'status': 'active',
            'user_id': attacker_supplied_id,
            'widgets': [],
            'metadata': {},
            'tags': [],
        }
        response = authenticated_api_client.post(
            reverse('userdashboard-list'), data, format='json'
        )
        assert response.status_code == 201

        created = UserDashboard.objects.get(name='Hijack Attempt')
        assert created.user_id == str(test_user.pk), (
            f"user_id HIJACK BUG: expected '{test_user.pk}', "
            f"got '{created.user_id}' — client-supplied user_id was accepted."
        )
        assert created.user_id != attacker_supplied_id

    def test_created_dashboard_visible_only_to_creator(
        self, authenticated_api_client, authenticated_second_client, test_user
    ):
        """A newly created dashboard must only appear in the creator's list."""
        data = {
            'name': 'Creator Only',
            'status': 'active',
            'widgets': [],
            'metadata': {},
            'tags': [],
        }
        authenticated_api_client.post(reverse('userdashboard-list'), data, format='json')

        # test_user sees it
        own_list = authenticated_api_client.get(reverse('userdashboard-list'))
        own_names = [d['name'] for d in own_list.data.get('results', own_list.data)]
        assert 'Creator Only' in own_names

        # second_user does NOT see it
        other_list = authenticated_second_client.get(reverse('userdashboard-list'))
        other_names = [d['name'] for d in other_list.data.get('results', other_list.data)]
        assert 'Creator Only' not in other_names


# ─── Staff-only endpoint protection ──────────────────────────────────────────

@pytest.mark.django_db
class TestStaffOnlyEndpoints:
    """
    by_user endpoints on UserDashboard and WebSocketConnection are
    staff-only admin tooling. Regular users must receive 403.
    """

    def test_dashboard_by_user_blocked_for_regular_user(
        self, authenticated_api_client
    ):
        url = reverse('userdashboard-by-user') + '?user_id=anyone'
        response = authenticated_api_client.get(url)
        assert response.status_code == 403, (
            f"PRIV-ESC BUG: non-staff got {response.status_code} on "
            f"staff-only by_user endpoint."
        )

    def test_dashboard_by_user_accessible_for_staff(
        self, authenticated_staff_client, second_user
    ):
        create_user_dashboard(name='StaffVisible', user_id=str(second_user.pk))
        url = reverse('userdashboard-by-user') + f'?user_id={second_user.pk}'
        response = authenticated_staff_client.get(url)
        assert response.status_code == 200

    def test_websocket_by_user_blocked_for_regular_user(
        self, authenticated_api_client
    ):
        url = reverse('websocketconnection-by-user') + '?user_id=anyone'
        response = authenticated_api_client.get(url)
        assert response.status_code == 403

    def test_websocket_by_user_accessible_for_staff(
        self, authenticated_staff_client, second_user
    ):
        create_websocket_connection(
            connection_id='staff_visible', user_id=str(second_user.pk)
        )
        url = reverse('websocketconnection-by-user') + f'?user_id={second_user.pk}'
        response = authenticated_staff_client.get(url)
        assert response.status_code == 200
        ids = [c['connection_id'] for c in response.data]
        assert 'staff_visible' in ids


# ─── WebSocketConnection ownership isolation ─────────────────────────────────

@pytest.mark.django_db
class TestWebSocketConnectionOwnershipIsolation:
    """
    WebSocketConnectionViewSet.get_queryset() scopes by str(request.user.pk).
    Non-staff users must never see another user's connections.
    """

    def test_user_only_sees_own_connections(
        self, authenticated_api_client, test_user, second_user
    ):
        create_websocket_connection(connection_id='mine', user_id=str(test_user.pk))
        create_websocket_connection(connection_id='theirs', user_id=str(second_user.pk))

        response = authenticated_api_client.get(reverse('websocketconnection-list'))
        assert response.status_code == 200
        ids = [c['connection_id'] for c in response.data.get('results', response.data)]
        assert 'mine' in ids
        assert 'theirs' not in ids, (
            "IDOR BUG: second_user's connection visible in test_user's list."
        )

    def test_cannot_retrieve_other_users_connection(
        self, authenticated_second_client, test_user
    ):
        """second_user cannot retrieve test_user's connection by PK."""
        conn = create_websocket_connection(
            connection_id='victim_conn', user_id=str(test_user.pk)
        )
        response = authenticated_second_client.get(
            reverse('websocketconnection-detail', kwargs={'pk': conn.pk})
        )
        # get_queryset() excludes it → 404
        assert response.status_code == 404, (
            f"IDOR BUG: Expected 404 but got {response.status_code}. "
            f"second_user can access test_user's WebSocket connection."
        )
