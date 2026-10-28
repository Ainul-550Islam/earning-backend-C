"""
Standalone proof-of-concept test (NOT part of the delivered test suite).
Proves that UserDashboardViewSet.activate()/deactivate() bypass IsDashboardOwner.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_poc_cross_user_activate_is_blocked(authenticated_second_client, test_user):
    """A user should NOT be able to activate another user's dashboard."""
    from api.realtime_dashboard.tests.fixtures import create_user_dashboard
    dashboard = create_user_dashboard(status='inactive', user_id=str(test_user.pk))

    # authenticated_second_client is a DIFFERENT user than the dashboard owner (test_user)
    response = authenticated_second_client.post(
        reverse('userdashboard-activate', kwargs={'pk': dashboard.pk})
    )
    print(f"\n[POC] Cross-user activate response status: {response.status_code}")
    dashboard.refresh_from_db()
    print(f"[POC] Dashboard status after attempted cross-user activation: {dashboard.status}")
    assert response.status_code == 403, (
        f"SECURITY BUG CONFIRMED: expected 403 (forbidden), got {response.status_code}. "
        f"Dashboard status is now '{dashboard.status}' after a non-owner activated it."
    )
