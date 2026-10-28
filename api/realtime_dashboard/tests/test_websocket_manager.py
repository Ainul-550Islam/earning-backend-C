"""
Tests for Real-time Dashboard Backend WebSocket manager.
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from api.realtime_dashboard.websocket_manager import WebSocketManager
from .fixtures import (
    create_websocket_connection,
    create_real_time_metric
)


@pytest.mark.django_db
class TestWebSocketManager:
    """Tests for WebSocketManager."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    def test_add_connection(self, manager):
        """Test adding a WebSocket connection."""
        connection = manager.add_connection(
            connection_id='conn123',
            user_id='user123',
            session_id='session123'
        )

        assert connection.connection_id == 'conn123'
        assert connection.user_id == 'user123'
        assert connection.session_id == 'session123'
        assert connection.status == 'connected'

    def test_add_existing_connection(self, manager):
        """Test adding an existing connection reactivates it."""
        create_websocket_connection(
            connection_id='conn123',
            status='disconnected'
        )

        connection = manager.add_connection(
            connection_id='conn123',
            user_id='user123'
        )

        assert connection.status == 'connected'

    def test_remove_connection(self, manager):
        """Test removing a WebSocket connection."""
        connection = create_websocket_connection(connection_id='conn123')

        result = manager.remove_connection('conn123')

        assert result is True
        connection.refresh_from_db()
        assert connection.status == 'disconnected'
        assert connection.disconnected_at is not None

    def test_remove_nonexistent_connection(self, manager):
        """Test removing a non-existent connection."""
        result = manager.remove_connection('nonexistent')
        assert result is False

    def test_broadcast_metric_update(self, manager):
        """Test broadcasting metric update."""
        create_websocket_connection(connection_id='conn1', status='connected')
        create_websocket_connection(connection_id='conn2', status='connected')
        create_websocket_connection(connection_id='conn3', status='disconnected')

        metric = create_real_time_metric(
            name='Test Metric',
            value=100.0,
            unit='units'
        )

        result = manager.broadcast_metric_update(metric)

        assert result is True

    def test_broadcast_metric_update_no_connections(self, manager):
        """Test broadcasting with no active connections."""
        metric = create_real_time_metric(name='Test Metric', value=100.0)

        result = manager.broadcast_metric_update(metric)

        assert result is True

    def test_cleanup_old_connections(self, manager):
        """Test cleaning up old connections."""
        # Create old connection
        old_connection = create_websocket_connection(
            connection_id='old_conn',
            status='connected'
        )
        old_connection.last_ping = timezone.now() - timedelta(seconds=4000)
        old_connection.save()

        # Create recent connection
        recent_connection = create_websocket_connection(
            connection_id='recent_conn',
            status='connected'
        )
        recent_connection.last_ping = timezone.now() - timedelta(seconds=100)
        recent_connection.save()

        count = manager.cleanup_old_connections(timeout_seconds=3600)

        assert count == 1
        old_connection.refresh_from_db()
        assert old_connection.status == 'disconnected'
        recent_connection.refresh_from_db()
        assert recent_connection.status == 'connected'

    def test_cleanup_old_connections_custom_timeout(self, manager):
        """Test cleanup with custom timeout."""
        old_connection = create_websocket_connection(
            connection_id='old_conn',
            status='connected'
        )
        old_connection.last_ping = timezone.now() - timedelta(seconds=120)
        old_connection.save()

        count = manager.cleanup_old_connections(timeout_seconds=60)

        assert count == 1
        old_connection.refresh_from_db()
        assert old_connection.status == 'disconnected'

    def test_send_to_connection(self, manager):
        """Test sending data to a connection."""
        result = manager._send_to_connection('conn123', {'message': 'test'})
        assert result is True

    def test_connections_dict(self, manager):
        """Test that manager maintains connections dict."""
        assert isinstance(manager.connections, dict)
        assert len(manager.connections) == 0
