"""
Tests for Real-time Dashboard Backend viewsets.
All viewsets require authentication (IsAuthenticated).

FIXES applied in this version:
  1. TestDashboardLayoutViewSet.test_create_layout
       was: authenticated_api_client (non-staff) → expected 201 (wrong)
       fix: authenticated_staff_client → 201 (correct; IsAdminOrReadOnly)

  2. TestUserDashboardViewSet.test_activate_action
       was: dashboard created with default user_id='test_user_123'
            which doesn't match test_user.pk → IDOR fix returns 403
       fix: create dashboard with user_id=str(test_user.pk)

  3. TestUserDashboardViewSet.test_deactivate_action — same as #2

  4. TestUserDashboardViewSet.test_by_user_action
       was: non-staff client → expected 200 (wrong; by_user is staff-only)
       fix: authenticated_staff_client → 200

  5. TestUserDashboardViewSet.test_by_user_missing_param — same as #4

  6. TestUserDashboardViewSet.test_render_action
       was: dashboard user_id='test_user_123' ≠ test_user.pk
            render IDOR fix uses get_object() which scopes by user → 404
       fix: create dashboard with user_id=str(test_user.pk)

  7. TestUserDashboardViewSet.test_render_action_invalid_widget — same as #6

  8. TestWebSocketConnectionViewSet.test_retrieve_connection
       was: connection user_id='test_user_123' ≠ test_user.pk
            get_queryset() by_user scopes → connection not in QS → 404
       fix: create connection with user_id=str(test_user.pk)

  9. TestWebSocketConnectionViewSet.test_active_action — same as #8

  10. TestWebSocketConnectionViewSet.test_by_user_action
        was: non-staff client → expected 200 (wrong; by_user is staff-only)
        fix: authenticated_staff_client → 200

  11. TestWebSocketConnectionViewSet.test_by_user_missing_param — same as #10

  12. (v1.5.0 — 360-degree DRY-unification audit) TestRealTimeMetricViewSet
        gained test_delete_metric, test_delete_metric_not_found, and
        test_perform_update_non_value_field_preserves_previous_value.
        perform_create/update/destroy now genuinely delegate to
        RealTimeMetricService instead of reimplementing its logic inline;
        delete_metric()'s signature moved from delete_metric(id) (which
        raised for a missing id) to delete_metric(instance), so the
        "missing id" 404 case is asserted here at the HTTP layer instead
        of as a service-level unit test. See test_dry_unification.py for
        the full set of new tests from this audit pass (widget/dashboard
        CRUD delegation, DashboardLayout by_creator, record_ping wiring,
        model clean()).
"""
import pytest
from django.urls import reverse
from api.realtime_dashboard.models.dashboard_widget import DashboardWidget
from api.realtime_dashboard.models.real_time_metric import RealTimeMetric
from .fixtures import (
    create_dashboard_widget, create_widget_configuration,
    create_real_time_metric, create_dashboard_layout,
    create_user_dashboard, create_websocket_connection,
)


# ─── DashboardWidgetViewSet ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardWidgetViewSet:

    def test_unauthenticated_request_rejected(self, api_client):
        response = api_client.get(reverse('dashboardwidget-list'))
        # DRF returns 401 when an authentication class is configured,
        # 403 when no authentication class is set (default DRF behaviour
        # with SessionAuthentication only). Both mean "not allowed in".
        assert response.status_code in (401, 403)

    def test_list_widgets(self, authenticated_api_client):
        create_dashboard_widget(name='W1')
        create_dashboard_widget(name='W2')
        response = authenticated_api_client.get(reverse('dashboardwidget-list'))
        assert response.status_code == 200

    def test_create_widget(self, authenticated_api_client):
        data = {'name': 'New Widget', 'widget_type': 'chart', 'status': 'active',
                'configuration': {}, 'refresh_interval': 60, 'width': 6, 'height': 4}
        response = authenticated_api_client.post(reverse('dashboardwidget-list'), data, format='json')
        assert response.status_code == 201
        assert DashboardWidget.objects.filter(name='New Widget').exists()

    def test_retrieve_widget(self, authenticated_api_client):
        widget = create_dashboard_widget(name='Test Widget')
        response = authenticated_api_client.get(reverse('dashboardwidget-detail', kwargs={'pk': widget.pk}))
        assert response.status_code == 200
        assert response.data['name'] == 'Test Widget'

    def test_update_widget(self, authenticated_api_client):
        widget = create_dashboard_widget(name='Old Name')
        data = {'name': 'New Name', 'widget_type': 'chart', 'status': 'active',
                'configuration': {}, 'refresh_interval': 60, 'width': 6, 'height': 4}
        response = authenticated_api_client.put(
            reverse('dashboardwidget-detail', kwargs={'pk': widget.pk}), data, format='json')
        assert response.status_code == 200
        widget.refresh_from_db()
        assert widget.name == 'New Name'

    def test_delete_widget(self, authenticated_api_client):
        widget = create_dashboard_widget()
        response = authenticated_api_client.delete(reverse('dashboardwidget-detail', kwargs={'pk': widget.pk}))
        assert response.status_code == 204

    def test_update_widget_not_found(self, authenticated_api_client):
        """v1.5.0: WidgetService.update_widget() is now instance-based; the
        'missing id' case is decided by DRF's get_object() before it's reached."""
        data = {'name': 'X', 'widget_type': 'chart', 'status': 'active',
                'configuration': {}, 'refresh_interval': 60, 'width': 6, 'height': 4}
        response = authenticated_api_client.put(
            reverse('dashboardwidget-detail', kwargs={'pk': 999999}), data, format='json')
        assert response.status_code == 404

    def test_delete_widget_not_found(self, authenticated_api_client):
        """v1.5.0: same as above for delete_widget()."""
        response = authenticated_api_client.delete(reverse('dashboardwidget-detail', kwargs={'pk': 999999}))
        assert response.status_code == 404

    def test_activate_widget_action(self, authenticated_api_client):
        widget = create_dashboard_widget(status='inactive')
        response = authenticated_api_client.post(reverse('dashboardwidget-activate', kwargs={'pk': widget.pk}))
        assert response.status_code == 200
        widget.refresh_from_db()
        assert widget.status == 'active'

    def test_deactivate_widget_action(self, authenticated_api_client):
        widget = create_dashboard_widget(status='active')
        response = authenticated_api_client.post(reverse('dashboardwidget-deactivate', kwargs={'pk': widget.pk}))
        assert response.status_code == 200
        widget.refresh_from_db()
        assert widget.status == 'inactive'

    def test_active_widgets_action(self, authenticated_api_client):
        create_dashboard_widget(name='Active', status='active')
        create_dashboard_widget(name='Inactive', status='inactive')
        response = authenticated_api_client.get(reverse('dashboardwidget-active'))
        assert response.status_code == 200
        names = [w['name'] for w in response.data]
        assert 'Active' in names
        assert 'Inactive' not in names


# ─── WidgetConfigurationViewSet ───────────────────────────────────────────────

@pytest.mark.django_db
class TestWidgetConfigurationViewSet:

    def test_list_configurations(self, authenticated_api_client):
        widget = create_dashboard_widget()
        create_widget_configuration(widget, key='k1')
        response = authenticated_api_client.get(reverse('widgetconfiguration-list'))
        assert response.status_code == 200

    def test_create_configuration(self, authenticated_api_client):
        widget = create_dashboard_widget()
        data = {'widget': widget.pk, 'config_type': 'chart', 'key': 'new_key', 'value': {}}
        response = authenticated_api_client.post(reverse('widgetconfiguration-list'), data, format='json')
        assert response.status_code == 201

    def test_retrieve_configuration(self, authenticated_api_client):
        widget = create_dashboard_widget()
        config = create_widget_configuration(widget, key='my_key')
        response = authenticated_api_client.get(reverse('widgetconfiguration-detail', kwargs={'pk': config.pk}))
        assert response.status_code == 200

    def test_by_widget_action(self, authenticated_api_client):
        w1 = create_dashboard_widget(name='W1')
        w2 = create_dashboard_widget(name='W2')
        create_widget_configuration(w1, key='k1')
        create_widget_configuration(w2, key='k2')
        url = reverse('widgetconfiguration-by-widget') + f'?widget_id={w1.pk}'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        keys = [c['key'] for c in response.data]
        assert 'k1' in keys and 'k2' not in keys

    def test_by_widget_missing_param(self, authenticated_api_client):
        response = authenticated_api_client.get(reverse('widgetconfiguration-by-widget'))
        assert response.status_code == 400


# ─── RealTimeMetricViewSet ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRealTimeMetricViewSet:

    def test_list_metrics(self, authenticated_api_client):
        create_real_time_metric(name='M1')
        response = authenticated_api_client.get(reverse('realtimemetric-list'))
        assert response.status_code == 200

    def test_create_metric(self, authenticated_api_client):
        data = {'name': 'NewM', 'metric_type': 'gauge', 'status': 'active', 'value': 10.0, 'unit': '%'}
        response = authenticated_api_client.post(reverse('realtimemetric-list'), data, format='json')
        assert response.status_code == 201

    def test_activate_metric(self, authenticated_api_client):
        metric = create_real_time_metric(status='inactive')
        response = authenticated_api_client.post(reverse('realtimemetric-activate', kwargs={'pk': metric.pk}))
        assert response.status_code == 200
        metric.refresh_from_db()
        assert metric.status == 'active'

    def test_deactivate_metric(self, authenticated_api_client):
        metric = create_real_time_metric(status='active')
        response = authenticated_api_client.post(reverse('realtimemetric-deactivate', kwargs={'pk': metric.pk}))
        assert response.status_code == 200
        metric.refresh_from_db()
        assert metric.status == 'inactive'

    def test_active_action(self, authenticated_api_client):
        create_real_time_metric(name='ActiveM', status='active')
        create_real_time_metric(name='InactiveM', status='inactive')
        response = authenticated_api_client.get(reverse('realtimemetric-active'))
        assert response.status_code == 200
        names = [m['name'] for m in response.data]
        assert 'ActiveM' in names and 'InactiveM' not in names

    def test_perform_update_tracks_previous_value(self, authenticated_api_client):
        """PATCH value → previous_value auto-updated (perform_update fix)."""
        metric = create_real_time_metric(value=100.0)
        response = authenticated_api_client.patch(
            reverse('realtimemetric-detail', kwargs={'pk': metric.pk}),
            {'value': 200.0}, format='json')
        assert response.status_code == 200
        metric.refresh_from_db()
        assert metric.value == 200.0
        assert metric.previous_value == 100.0

    def test_perform_update_non_value_field_preserves_previous_value(self, authenticated_api_client):
        """v1.5.0: PATCHing a non-value field must NOT touch previous_value."""
        metric = create_real_time_metric(value=100.0, previous_value=50.0, name='Old')
        response = authenticated_api_client.patch(
            reverse('realtimemetric-detail', kwargs={'pk': metric.pk}),
            {'name': 'New'}, format='json')
        assert response.status_code == 200
        metric.refresh_from_db()
        assert metric.name == 'New'
        assert metric.value == 100.0
        assert metric.previous_value == 50.0

    def test_delete_metric(self, authenticated_api_client):
        """v1.5.0: DELETE now routes through RealTimeMetricService.delete_metric()."""
        metric = create_real_time_metric(name='ToDelete')
        pk = metric.pk
        response = authenticated_api_client.delete(reverse('realtimemetric-detail', kwargs={'pk': pk}))
        assert response.status_code == 204
        assert not RealTimeMetric.objects.filter(pk=pk).exists()

    def test_delete_metric_not_found(self, authenticated_api_client):
        """
        v1.5.0: delete_metric()'s signature changed from delete_metric(id)
        — which used to raise MetricNotFoundError for a missing id — to
        delete_metric(instance). The "missing id" case is now handled
        entirely by DRF's get_object(), before perform_destroy() (and this
        service) is ever reached. This test replaces the old
        TestGetMetricOrRaise.test_delete_metric_raises_for_missing_id
        service-level test at the layer where "missing" is now decided.
        """
        response = authenticated_api_client.delete(reverse('realtimemetric-detail', kwargs={'pk': 999999}))
        assert response.status_code == 404


# ─── DashboardLayoutViewSet ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardLayoutViewSet:

    def test_list_layouts(self, authenticated_api_client):
        create_dashboard_layout(name='L1')
        response = authenticated_api_client.get(reverse('dashboardlayout-list'))
        assert response.status_code == 200

    def test_create_layout(self, authenticated_staff_client):
        """
        FIX #1: DashboardLayoutViewSet uses IsAdminOrReadOnly — only staff
        may create layouts. Was: authenticated_api_client (non-staff) → 403.
        Fix: use authenticated_staff_client → 201.
        """
        data = {'name': 'NewLayout', 'layout_type': 'grid', 'columns': 12, 'rows': 12}
        response = authenticated_staff_client.post(reverse('dashboardlayout-list'), data, format='json')
        assert response.status_code == 201

    def test_by_type_action(self, authenticated_api_client):
        create_dashboard_layout(name='Grid1', layout_type='grid')
        create_dashboard_layout(name='Tabs1', layout_type='tabs')
        url = reverse('dashboardlayout-by-type') + '?layout_type=grid'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        names = [item['name'] for item in response.data]
        assert 'Grid1' in names and 'Tabs1' not in names

    def test_by_type_missing_param(self, authenticated_api_client):
        response = authenticated_api_client.get(reverse('dashboardlayout-by-type'))
        assert response.status_code == 400


# ─── UserDashboardViewSet ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestUserDashboardViewSet:

    def test_list_dashboards(self, authenticated_api_client):
        create_user_dashboard(user_id='u1')
        response = authenticated_api_client.get(reverse('userdashboard-list'))
        assert response.status_code == 200

    def test_create_dashboard(self, authenticated_api_client):
        data = {'name': 'NewDash', 'status': 'active', 'user_id': 'u1', 'widgets': []}
        response = authenticated_api_client.post(reverse('userdashboard-list'), data, format='json')
        assert response.status_code == 201

    def test_activate_action(self, authenticated_api_client, test_user):
        """
        FIX #2: After the IDOR fix, require_dashboard calls
        check_object_permissions(). dashboard.user_id must match
        request.user.pk — use str(test_user.pk) instead of the old
        hardcoded default 'test_user_123'.
        """
        dashboard = create_user_dashboard(status='inactive', user_id=str(test_user.pk))
        response = authenticated_api_client.post(reverse('userdashboard-activate', kwargs={'pk': dashboard.pk}))
        assert response.status_code == 200
        dashboard.refresh_from_db()
        assert dashboard.status == 'active'

    def test_deactivate_action(self, authenticated_api_client, test_user):
        """FIX #3: Same ownership fix as test_activate_action."""
        dashboard = create_user_dashboard(status='active', user_id=str(test_user.pk))
        response = authenticated_api_client.post(reverse('userdashboard-deactivate', kwargs={'pk': dashboard.pk}))
        assert response.status_code == 200
        dashboard.refresh_from_db()
        assert dashboard.status == 'inactive'

    def test_by_user_action(self, authenticated_staff_client, second_user):
        """
        FIX #4: by_user is staff-only. Was: non-staff client → expected 200.
        Fix: use authenticated_staff_client → 200.
        """
        create_user_dashboard(name='U1D1', user_id=str(second_user.pk))
        url = reverse('userdashboard-by-user') + f'?user_id={second_user.pk}'
        response = authenticated_staff_client.get(url)
        assert response.status_code == 200
        names = [d['name'] for d in response.data]
        assert 'U1D1' in names

    def test_by_user_missing_param(self, authenticated_staff_client):
        """FIX #5: staff client hits the 400 missing-param check instead of 403."""
        response = authenticated_staff_client.get(reverse('userdashboard-by-user'))
        assert response.status_code == 400

    def test_render_action(self, authenticated_api_client, test_user):
        """
        FIX #6: render now uses get_object() which scopes by user.
        Dashboard must be owned by test_user so get_object() finds it.
        """
        widget = create_dashboard_widget(name='W1')
        dashboard = create_user_dashboard(widgets=[widget.pk], user_id=str(test_user.pk))
        response = authenticated_api_client.get(reverse('userdashboard-render', kwargs={'pk': dashboard.pk}))
        assert response.status_code == 200
        assert response.data['success'] is True

    def test_render_action_invalid_widget(self, authenticated_api_client, test_user):
        """
        FIX #7: dashboard must be owned by test_user for get_object() to find it.
        Engine then raises DashboardEngineError for missing widget → 404.
        """
        dashboard = create_user_dashboard(widgets=[999999], user_id=str(test_user.pk))
        response = authenticated_api_client.get(reverse('userdashboard-render', kwargs={'pk': dashboard.pk}))
        assert response.status_code == 404

    def test_render_action_missing_dashboard(self, authenticated_api_client):
        response = authenticated_api_client.get(reverse('userdashboard-render', kwargs={'pk': 999999}))
        assert response.status_code == 404


# ─── WebSocketConnectionViewSet ───────────────────────────────────────────────

@pytest.mark.django_db
class TestWebSocketConnectionViewSet:

    def test_list_connections(self, authenticated_api_client, test_user):
        create_websocket_connection(connection_id='c1', user_id=str(test_user.pk))
        response = authenticated_api_client.get(reverse('websocketconnection-list'))
        assert response.status_code == 200

    def test_retrieve_connection(self, authenticated_api_client, test_user):
        """
        FIX #8: get_queryset() scopes by user. Connection must use
        str(test_user.pk) as user_id so it appears in the queryset.
        """
        conn = create_websocket_connection(connection_id='c123', user_id=str(test_user.pk))
        response = authenticated_api_client.get(reverse('websocketconnection-detail', kwargs={'pk': conn.pk}))
        assert response.status_code == 200
        assert response.data['connection_id'] == 'c123'

    def test_read_only_post_rejected(self, authenticated_api_client):
        response = authenticated_api_client.post(
            reverse('websocketconnection-list'),
            {'connection_id': 'new', 'user_id': 'u1', 'status': 'connected'},
            format='json')
        assert response.status_code == 405

    def test_active_action(self, authenticated_api_client, test_user):
        """
        FIX #9: connections must use str(test_user.pk) so they appear
        in get_queryset() which scopes by the authenticated user's pk.
        """
        uid = str(test_user.pk)
        create_websocket_connection(connection_id='ca', status='connected', user_id=uid)
        create_websocket_connection(connection_id='cd', status='disconnected', user_id=uid)
        response = authenticated_api_client.get(reverse('websocketconnection-active'))
        assert response.status_code == 200
        ids = [c['connection_id'] for c in response.data]
        assert 'ca' in ids and 'cd' not in ids

    def test_by_user_action(self, authenticated_staff_client):
        """
        FIX #10: by_user is staff-only. Was: non-staff expected 200.
        Fix: use staff client, verify it works.
        """
        create_websocket_connection(connection_id='u1c1', user_id='userA')
        create_websocket_connection(connection_id='u2c1', user_id='userB')
        url = reverse('websocketconnection-by-user') + '?user_id=userA'
        response = authenticated_staff_client.get(url)
        assert response.status_code == 200
        ids = [c['connection_id'] for c in response.data]
        assert 'u1c1' in ids and 'u2c1' not in ids

    def test_by_user_missing_param(self, authenticated_staff_client):
        """FIX #11: staff client reaches the 400 branch instead of 403."""
        response = authenticated_staff_client.get(reverse('websocketconnection-by-user'))
        assert response.status_code == 400


# ─── Health Check ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHealthCheck:

    def test_health_check_returns_200(self, api_client):
        """Health check must be accessible without authentication."""
        response = api_client.get(reverse('health-check'))
        assert response.status_code == 200
        assert response.data['status'] == 'healthy'
        assert response.data['database'] == 'ok'
        assert 'timestamp' in response.data

    def test_health_check_includes_channel_layer(self, api_client):
        """Channel layer (InMemoryChannelLayer) must be healthy in tests."""
        response = api_client.get(reverse('health-check'))
        assert response.status_code == 200
        assert 'channel_layer' in response.data
        assert response.data['channel_layer'] == 'ok'


# ═══════════════════════════════════════════════════════════════════════════════
# Ownership isolation, IsAdminOrReadOnly, filter/search/ordering
# ═══════════════════════════════════════════════════════════════════════════════


# ─── UserDashboard ownership isolation ───────────────────────────────────────

@pytest.mark.django_db
class TestUserDashboardOwnership:
    """
    Tests confirming that get_queryset() and perform_create() enforce
    per-user ownership on UserDashboard.
    """

    def test_list_returns_only_own_dashboards(
        self, authenticated_api_client, test_user, second_user
    ):
        """User A cannot see User B's dashboards in the list."""
        from .fixtures import create_user_dashboard
        create_user_dashboard(name='Mine', user_id=str(test_user.pk), status='active')
        create_user_dashboard(name='Theirs', user_id=str(second_user.pk), status='active')

        response = authenticated_api_client.get(reverse('userdashboard-list'))
        assert response.status_code == 200
        names = [d['name'] for d in response.data.get('results', response.data)]
        assert 'Mine' in names
        assert 'Theirs' not in names

    def test_retrieve_own_dashboard_allowed(
        self, authenticated_api_client, test_user
    ):
        from .fixtures import create_user_dashboard
        dashboard = create_user_dashboard(name='Mine', user_id=str(test_user.pk))
        response = authenticated_api_client.get(
            reverse('userdashboard-detail', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 200

    def test_retrieve_other_users_dashboard_denied(
        self, authenticated_api_client, second_user
    ):
        """User A cannot retrieve User B's dashboard."""
        from .fixtures import create_user_dashboard
        dashboard = create_user_dashboard(name='Theirs', user_id=str(second_user.pk))
        response = authenticated_api_client.get(
            reverse('userdashboard-detail', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 404

    def test_create_forces_own_user_id(self, authenticated_api_client, test_user):
        """perform_create() must ignore client-supplied user_id and use request.user."""
        data = {
            'name': 'New Dashboard',
            'status': 'active',
            'user_id': 'hacker_id',   # should be silently ignored
            'widgets': [],
            'metadata': {},
            'tags': [],
        }
        response = authenticated_api_client.post(
            reverse('userdashboard-list'), data, format='json'
        )
        assert response.status_code == 201
        from api.realtime_dashboard.models.user_dashboard import UserDashboard
        created = UserDashboard.objects.get(name='New Dashboard')
        assert created.user_id == str(test_user.pk)
        assert created.user_id != 'hacker_id'

    def test_update_own_dashboard_allowed(self, authenticated_api_client, test_user):
        from .fixtures import create_user_dashboard
        dashboard = create_user_dashboard(name='Old', user_id=str(test_user.pk))
        data = {'name': 'Updated', 'status': 'active', 'widgets': [], 'metadata': {}, 'tags': []}
        response = authenticated_api_client.patch(
            reverse('userdashboard-detail', kwargs={'pk': dashboard.pk}),
            data, format='json'
        )
        assert response.status_code == 200

    def test_update_other_users_dashboard_denied(
        self, authenticated_api_client, second_user
    ):
        """User A cannot modify User B's dashboard."""
        from .fixtures import create_user_dashboard
        dashboard = create_user_dashboard(name='Theirs', user_id=str(second_user.pk))
        response = authenticated_api_client.patch(
            reverse('userdashboard-detail', kwargs={'pk': dashboard.pk}),
            {'name': 'Hacked'}, format='json'
        )
        # 404 because get_queryset() excludes other users' dashboards from the QS
        assert response.status_code == 404

    def test_delete_other_users_dashboard_denied(
        self, authenticated_api_client, second_user
    ):
        from .fixtures import create_user_dashboard
        dashboard = create_user_dashboard(user_id=str(second_user.pk))
        response = authenticated_api_client.delete(
            reverse('userdashboard-detail', kwargs={'pk': dashboard.pk})
        )
        assert response.status_code == 404

    def test_by_user_action_forbidden_for_non_staff(self, authenticated_api_client):
        """/dashboards/by_user/ must return 403 for regular users."""
        url = reverse('userdashboard-by-user') + '?user_id=anyone'
        response = authenticated_api_client.get(url)
        assert response.status_code == 403

    def test_by_user_action_allowed_for_staff(
        self, authenticated_staff_client, second_user
    ):
        from .fixtures import create_user_dashboard
        create_user_dashboard(name='U2D', user_id=str(second_user.pk))
        url = reverse('userdashboard-by-user') + f'?user_id={second_user.pk}'
        response = authenticated_staff_client.get(url)
        assert response.status_code == 200


# ─── DashboardLayout IsAdminOrReadOnly ───────────────────────────────────────

@pytest.mark.django_db
class TestDashboardLayoutAdminOnly:
    """
    Regular users may read layouts. Only staff may write.
    """

    def test_regular_user_can_list_layouts(self, authenticated_api_client):
        response = authenticated_api_client.get(reverse('dashboardlayout-list'))
        assert response.status_code == 200

    def test_regular_user_cannot_create_layout(self, authenticated_api_client):
        data = {'name': 'New Layout', 'layout_type': 'grid', 'configuration': {}}
        response = authenticated_api_client.post(
            reverse('dashboardlayout-list'), data, format='json'
        )
        assert response.status_code == 403

    def test_staff_user_can_create_layout(self, authenticated_staff_client):
        data = {'name': 'Admin Layout', 'layout_type': 'grid', 'configuration': {}}
        response = authenticated_staff_client.post(
            reverse('dashboardlayout-list'), data, format='json'
        )
        assert response.status_code == 201

    def test_regular_user_cannot_delete_layout(self, authenticated_api_client):
        from .fixtures import create_dashboard_layout
        layout = create_dashboard_layout(name='Existing')
        response = authenticated_api_client.delete(
            reverse('dashboardlayout-detail', kwargs={'pk': layout.pk})
        )
        assert response.status_code == 403

    def test_staff_user_can_delete_layout(self, authenticated_staff_client):
        from .fixtures import create_dashboard_layout
        layout = create_dashboard_layout(name='ToDelete')
        response = authenticated_staff_client.delete(
            reverse('dashboardlayout-detail', kwargs={'pk': layout.pk})
        )
        assert response.status_code == 204


# ─── WebSocketConnection ownership isolation ─────────────────────────────────

@pytest.mark.django_db
class TestWebSocketConnectionOwnership:

    def test_list_returns_only_own_connections(
        self, authenticated_api_client, test_user, second_user
    ):
        from .fixtures import create_websocket_connection
        create_websocket_connection(connection_id='mine', user_id=str(test_user.pk))
        create_websocket_connection(connection_id='theirs', user_id=str(second_user.pk))

        response = authenticated_api_client.get(reverse('websocketconnection-list'))
        assert response.status_code == 200
        ids = [c['connection_id'] for c in response.data.get('results', response.data)]
        assert 'mine' in ids
        assert 'theirs' not in ids

    def test_by_user_returns_403_for_non_staff(self, authenticated_api_client):
        url = reverse('websocketconnection-by-user') + '?user_id=anyone'
        response = authenticated_api_client.get(url)
        assert response.status_code == 403


# ─── Filter / search / ordering tests ────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardWidgetFilters:

    def test_filter_by_widget_type(self, authenticated_api_client):
        from .fixtures import create_dashboard_widget
        create_dashboard_widget(name='Chart1', widget_type='chart')
        create_dashboard_widget(name='Table1', widget_type='table')
        url = reverse('dashboardwidget-list') + '?widget_type=chart'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        results = response.data.get('results', response.data)
        types = {w['widget_type'] for w in results}
        assert types == {'chart'}

    def test_filter_by_status(self, authenticated_api_client):
        from .fixtures import create_dashboard_widget
        create_dashboard_widget(name='Active', status='active')
        create_dashboard_widget(name='Inactive', status='inactive')
        url = reverse('dashboardwidget-list') + '?status=active'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        results = response.data.get('results', response.data)
        assert all(w['status'] == 'active' for w in results)

    def test_search_by_name(self, authenticated_api_client):
        from .fixtures import create_dashboard_widget
        create_dashboard_widget(name='Revenue Chart')
        create_dashboard_widget(name='User Table')
        url = reverse('dashboardwidget-list') + '?search=Revenue'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        results = response.data.get('results', response.data)
        names = [w['name'] for w in results]
        assert 'Revenue Chart' in names
        assert 'User Table' not in names

    def test_ordering_by_name(self, authenticated_api_client):
        from .fixtures import create_dashboard_widget
        create_dashboard_widget(name='Zebra')
        create_dashboard_widget(name='Alpha')
        url = reverse('dashboardwidget-list') + '?ordering=name'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        results = response.data.get('results', response.data)
        names = [w['name'] for w in results]
        assert names == sorted(names)


@pytest.mark.django_db
class TestRealTimeMetricFilters:

    def test_filter_by_metric_type(self, authenticated_api_client):
        from .fixtures import create_real_time_metric
        create_real_time_metric(name='Gauge1', metric_type='gauge')
        create_real_time_metric(name='Counter1', metric_type='counter')
        url = reverse('realtimemetric-list') + '?metric_type=gauge'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        results = response.data.get('results', response.data)
        assert all(m['metric_type'] == 'gauge' for m in results)

    def test_filter_value_range(self, authenticated_api_client):
        from .fixtures import create_real_time_metric
        create_real_time_metric(name='Low', value=10.0)
        create_real_time_metric(name='High', value=200.0)
        url = reverse('realtimemetric-list') + '?value_min=50'
        response = authenticated_api_client.get(url)
        assert response.status_code == 200
        results = response.data.get('results', response.data)
        names = [m['name'] for m in results]
        assert 'High' in names
        assert 'Low' not in names


@pytest.mark.django_db
class TestHealthCheckV2:
    """Health check now also probes the channel layer."""

    def test_health_check_includes_channel_layer(self, api_client):
        response = api_client.get(reverse('health-check'))
        assert response.status_code == 200
        assert 'channel_layer' in response.data
        # InMemoryChannelLayer is configured in tests/settings.py
        assert response.data['channel_layer'] == 'ok'
