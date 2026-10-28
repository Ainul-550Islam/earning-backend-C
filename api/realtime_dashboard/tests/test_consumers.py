"""
Tests for Real-time Dashboard WebSocket consumers.

Authentication note
-------------------
DashboardConsumer and MetricConsumer require an authenticated user and
close the connection with code 4001 if the scope user is anonymous.
EventConsumer intentionally allows anonymous connections.

Tests are split into:
  - Authenticated tests  → use make_auth_scope(user) to inject a real user
  - Anonymous tests      → verify 4001 close code is sent
"""
import pytest
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from asgiref.sync import sync_to_async

from api.realtime_dashboard.routing import websocket_urlpatterns
from api.realtime_dashboard.models.websocket_connection import WebSocketConnection

application = URLRouter(websocket_urlpatterns)

User = get_user_model()


# ─── helpers ─────────────────────────────────────────────────────────────────

def make_auth_scope(user):
    """Scope extras with an authenticated user — accepted by all consumers."""
    return {'user': user, 'session': None}


def make_anon_scope():
    """Scope extras with no user — rejected by Dashboard/MetricConsumer."""
    return {'user': None, 'session': None}


@pytest.fixture
def ws_user(db):
    return User.objects.create_user(
        username='wsuser', email='ws@example.com', password='pass'
    )


# ─── MetricConsumer — authenticated ──────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_metric_consumer_authenticated_connect(ws_user):
    """Authenticated user connects → WebSocketConnection row created."""
    communicator = WebsocketCommunicator(application, '/ws/metric/1/')
    communicator.scope.update(make_auth_scope(ws_user))
    connected, code = await communicator.connect()
    assert connected, f'Expected connected=True, got code={code}'

    count = await sync_to_async(WebSocketConnection.objects.count)()
    assert count == 1
    conn = await sync_to_async(WebSocketConnection.objects.first)()
    assert conn.status == 'connected'
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_metric_consumer_authenticated_disconnect(ws_user):
    """Authenticated disconnect → row marked disconnected."""
    communicator = WebsocketCommunicator(application, '/ws/metric/1/')
    communicator.scope.update(make_auth_scope(ws_user))
    await communicator.connect()
    conn = await sync_to_async(WebSocketConnection.objects.first)()
    await communicator.disconnect()
    await sync_to_async(conn.refresh_from_db)()
    assert conn.status == 'disconnected'


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_metric_consumer_ping_pong(ws_user):
    """Authenticated ping → pong + last_ping refreshed."""
    communicator = WebsocketCommunicator(application, '/ws/metric/1/')
    communicator.scope.update(make_auth_scope(ws_user))
    await communicator.connect()
    conn = await sync_to_async(WebSocketConnection.objects.first)()
    before = conn.last_ping

    await communicator.send_json_to({'type': 'ping'})
    response = await communicator.receive_json_from()
    assert response == {'type': 'pong'}

    await sync_to_async(conn.refresh_from_db)()
    assert conn.last_ping >= before
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_metric_consumer_broadcast(ws_user):
    """Two authenticated subscribers both receive a group message."""
    user2 = await sync_to_async(User.objects.create_user)(
        username='ws2', email='ws2@example.com', password='pass'
    )
    c1 = WebsocketCommunicator(application, '/ws/metric/42/')
    c2 = WebsocketCommunicator(application, '/ws/metric/42/')
    c1.scope.update(make_auth_scope(ws_user))
    c2.scope.update(make_auth_scope(user2))

    await c1.connect()
    await c2.connect()

    await c1.send_json_to({'value': 99, 'name': 'cpu'})
    msg1 = await c1.receive_json_from()
    msg2 = await c2.receive_json_from()
    assert msg1 == msg2 == {'value': 99, 'name': 'cpu'}

    await c1.disconnect()
    await c2.disconnect()


# ─── MetricConsumer — anonymous (auth enforcement) ───────────────────────────

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_metric_consumer_anonymous_rejected():
    """
    Anonymous user must be closed with code 4001 — not accepted.

    FIXED: previous test passed user=None (anonymous) and asserted
    connected=True. That was written before auth enforcement was added.
    Now DashboardConsumer/MetricConsumer close anonymous connections
    immediately; this test verifies that behaviour.
    """
    communicator = WebsocketCommunicator(application, '/ws/metric/1/')
    communicator.scope.update(make_anon_scope())
    connected, code = await communicator.connect()
    assert not connected
    assert code == 4001

    # No DB row should have been created for the rejected connection.
    count = await sync_to_async(WebSocketConnection.objects.count)()
    assert count == 0


# ─── DashboardConsumer — authenticated ───────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_dashboard_consumer_authenticated_connect(ws_user):
    """Authenticated user connects to dashboard consumer."""
    communicator = WebsocketCommunicator(application, '/ws/dashboard/5/')
    communicator.scope.update(make_auth_scope(ws_user))
    connected, code = await communicator.connect()
    assert connected, f'Expected connected, got code={code}'
    count = await sync_to_async(WebSocketConnection.objects.count)()
    assert count == 1
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_dashboard_consumer_anonymous_rejected():
    """Anonymous user must receive close code 4001 from DashboardConsumer."""
    communicator = WebsocketCommunicator(application, '/ws/dashboard/5/')
    communicator.scope.update(make_anon_scope())
    connected, code = await communicator.connect()
    assert not connected
    assert code == 4001
    count = await sync_to_async(WebSocketConnection.objects.count)()
    assert count == 0


# ─── EventConsumer — anonymous allowed ───────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_event_consumer_anonymous_allowed():
    """EventConsumer allows anonymous connections (public broadcast feed)."""
    communicator = WebsocketCommunicator(application, '/ws/events/')
    communicator.scope.update(make_anon_scope())
    connected, _ = await communicator.connect()
    assert connected
    count = await sync_to_async(WebSocketConnection.objects.count)()
    assert count == 1
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_event_consumer_ping_pong():
    """EventConsumer ping → pong (anonymous allowed)."""
    communicator = WebsocketCommunicator(application, '/ws/events/')
    communicator.scope.update(make_anon_scope())
    await communicator.connect()
    await communicator.send_json_to({'type': 'ping'})
    response = await communicator.receive_json_from()
    assert response == {'type': 'pong'}
    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_event_consumer_authenticated_connect(ws_user):
    """EventConsumer also accepts authenticated users."""
    communicator = WebsocketCommunicator(application, '/ws/events/')
    communicator.scope.update(make_auth_scope(ws_user))
    connected, _ = await communicator.connect()
    assert connected
    await communicator.disconnect()
