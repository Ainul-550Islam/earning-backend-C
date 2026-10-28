# api/rate_limit/adapters/messaging.py
"""
Messaging / WebSocket ↔ Rate Limit Adapter
============================================
Covers: message send, WebSocket connect, reaction, call initiate.

Usage in api/messaging/consumers.py (AsyncJsonWebsocketConsumer):
    from api.rate_limit.adapters.messaging import MessagingRateLimitAdapter

    class ChatConsumer(AsyncJsonWebsocketConsumer):
        async def connect(self):
            # Check WS connection rate limit
            allowed = await database_sync_to_async(
                MessagingRateLimitAdapter.check_ws_connect
            )(user=self.scope['user'])
            if not allowed.allowed:
                await self.close(code=4029)
                return
            await self.accept()

        async def receive_json(self, content):
            if content.get('type') == 'message.send':
                result = await database_sync_to_async(
                    MessagingRateLimitAdapter.check_message_send
                )(user=self.scope['user'])
                if not result.allowed:
                    await self.send_json({'error': 'rate_limit', 'retry_after': 5})
                    return
            ...

Usage in api/messaging/middleware.py:
    from api.rate_limit.adapters.messaging import MessagingRateLimitAdapter
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.messaging')


class MessagingRateLimitAdapter:
    """Adapter for api/messaging system."""

    # ── Message Send ───────────────────────────────────────────

    @staticmethod
    def check_message_send(user, request=None) -> RateLimitResult:
        """
        Check before sending a chat message.
        Prevents message spam.

        Where to call:
            api/messaging/consumers.py → ChatConsumer.receive_json()
            api/messaging/views.py → message send endpoint
        """
        return RateLimitIntegrationService.check(
            'message_send',
            user=user,
            request=request,
            extra_context={'source': 'websocket'},
        )

    # ── WebSocket Connect ──────────────────────────────────────

    @staticmethod
    def check_ws_connect(user=None, ip_address: str = '', request=None) -> RateLimitResult:
        """
        Check on WebSocket connection attempt.
        Prevents WS connection flooding.

        Where to call:
            api/messaging/consumers.py → ChatConsumer.connect()
            api/messaging/consumers.py → PresenceConsumer.connect()
            api/messaging/consumers.py → CallConsumer.connect()
            api/messaging/consumers.py → SupportConsumer.connect()
        """
        return RateLimitIntegrationService.check(
            'message_websocket_connect',
            user=user,
            ip_address=ip_address,
            request=request,
        )

    # ── Reaction ───────────────────────────────────────────────

    @staticmethod
    def check_reaction(user, request=None) -> RateLimitResult:
        """
        Check before adding a message reaction.

        Where to call:
            api/messaging/consumers.py → reaction handler
        """
        return RateLimitIntegrationService.check(
            'message_reaction',
            user=user,
            request=request,
        )

    # ── Call Initiate ──────────────────────────────────────────

    @staticmethod
    def check_call_initiate(user, request=None) -> RateLimitResult:
        """
        Check before initiating a WebRTC call.

        Where to call:
            api/messaging/consumers.py → CallConsumer.receive_json()
                when type == 'call.offer'
        """
        return RateLimitIntegrationService.check(
            'call_initiate',
            user=user,
            request=request,
            extra_context={'source': 'webrtc'},
        )

    # ── Middleware bridge ──────────────────────────────────────

    @staticmethod
    def check_from_middleware(request) -> RateLimitResult:
        """
        Called from api/messaging/middleware.py.
        Replaces any existing middleware rate limit logic.

        Where to call:
            api/messaging/middleware.py → MessagingMiddleware.process_request()
        """
        user = getattr(request, 'user', None)
        ip = RateLimitIntegrationService._extract_ip(request)
        path = request.path

        # Route to most appropriate action
        if '/ws/' in path or '/websocket/' in path:
            action = 'message_websocket_connect'
        elif '/call' in path:
            action = 'call_initiate'
        else:
            action = 'message_send'

        return RateLimitIntegrationService.check(
            action,
            request=request,
            user=user if user and getattr(user, 'is_authenticated', False) else None,
            ip_address=ip,
        )
