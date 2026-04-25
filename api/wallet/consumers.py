# api/wallet/consumers.py
"""
WebSocket consumers — real-time wallet balance updates via Django Channels.

Features:
  - Real-time balance push when wallet changes
  - Real-time withdrawal status updates
  - Transaction feed (live incoming earnings)
  - Admin dashboard live stats

Install: pip install channels channels-redis
settings.py:
  INSTALLED_APPS += ["channels"]
  ASGI_APPLICATION = "config.asgi.application"
  CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer",
                                "CONFIG": {"hosts": [("redis://localhost:6379/1")]}}}
"""
import json
import logging
from decimal import Decimal
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger("wallet.consumers")


class WalletConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time wallet updates.
    URL: ws://host/ws/wallet/
    
    Events sent to client:
      balance_update    — when balance changes
      transaction       — new transaction
      withdrawal_status — withdrawal status change
      notification      — in-app notification
    """

    async def connect(self):
        """Accept connection if user is authenticated."""
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user_id    = user.id
        self.group_name = f"wallet_user_{user.id}"

        # Join user-specific group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send current balance on connect
        try:
            balance_data = await self.get_balance_data(user.id)
            await self.send(text_data=json.dumps({
                "type":    "balance_update",
                "payload": balance_data,
            }))
        except Exception as e:
            logger.debug(f"WalletConsumer connect balance fetch: {e}")

        logger.info(f"WalletConsumer connected: user={user.id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.debug(f"WalletConsumer disconnected: user={self.user_id} code={close_code}")

    async def receive(self, text_data):
        """Handle incoming messages from client."""
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "subscribe_transactions":
                await self.send(json.dumps({"type": "subscribed", "channel": "transactions"}))
            elif action == "get_balance":
                balance = await self.get_balance_data(self.user_id)
                await self.send(json.dumps({"type": "balance_update", "payload": balance}))
            elif action == "ping":
                await self.send(json.dumps({"type": "pong"}))
        except Exception as e:
            logger.error(f"WalletConsumer receive error: {e}")

    # ── Channel Layer event handlers ──────────────────────────

    async def wallet_balance_update(self, event):
        """Receive balance update from channel layer → send to WebSocket."""
        await self.send(text_data=json.dumps({
            "type":    "balance_update",
            "payload": event.get("payload", {}),
        }))

    async def wallet_transaction(self, event):
        """Receive new transaction → send to WebSocket."""
        await self.send(text_data=json.dumps({
            "type":    "transaction",
            "payload": event.get("payload", {}),
        }))

    async def wallet_withdrawal_status(self, event):
        """Receive withdrawal status change → send to WebSocket."""
        await self.send(text_data=json.dumps({
            "type":    "withdrawal_status",
            "payload": event.get("payload", {}),
        }))

    async def wallet_notification(self, event):
        """Receive notification → send to WebSocket."""
        await self.send(text_data=json.dumps({
            "type":    "notification",
            "payload": event.get("payload", {}),
        }))

    # ── DB helpers ────────────────────────────────────────────

    @database_sync_to_async
    def get_balance_data(self, user_id: int) -> dict:
        try:
            from .models.core import Wallet
            wallet = Wallet.objects.get(user_id=user_id)
            return {
                "current_balance":  str(wallet.current_balance),
                "pending_balance":  str(wallet.pending_balance),
                "available_balance":str(wallet.available_balance),
                "bonus_balance":    str(wallet.bonus_balance),
                "frozen_balance":   str(wallet.frozen_balance),
                "is_locked":        wallet.is_locked,
                "currency":         wallet.currency,
            }
        except Exception:
            return {}


class AdminDashboardConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for admin live dashboard.
    URL: ws://host/ws/admin/dashboard/
    Shows: live transaction count, withdrawal queue, total liability.
    """
    GROUP = "admin_dashboard"

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_staff:
            await self.close(code=4003)
            return
        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()
        stats = await self.get_dashboard_stats()
        await self.send(json.dumps({"type": "dashboard_stats", "payload": stats}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    async def dashboard_update(self, event):
        await self.send(json.dumps({"type": "dashboard_stats", "payload": event.get("payload", {})}))

    @database_sync_to_async
    def get_dashboard_stats(self) -> dict:
        try:
            from .models.core import Wallet, WalletTransaction
            from .models.withdrawal import WithdrawalRequest
            from django.db.models import Sum, Count
            return {
                "total_wallets":       Wallet.objects.count(),
                "pending_withdrawals": WithdrawalRequest.objects.filter(status="pending").count(),
                "total_liability":     float(
                    Wallet.objects.aggregate(
                        t=Sum("current_balance") + Sum("pending_balance")
                    )["t"] or 0
                ),
                "today_txn_count":     WalletTransaction.objects.filter(
                    created_at__date=__import__("django.utils.timezone", fromlist=["timezone"]).timezone.now().date()
                ).count(),
            }
        except Exception:
            return {}


# ── Helper: push balance update to WebSocket ─────────────────

def push_balance_update(user_id: int, wallet) -> None:
    """Call from services when balance changes to push to WebSocket."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"wallet_user_{user_id}",
            {
                "type": "wallet.balance_update",
                "payload": {
                    "current_balance":  str(wallet.current_balance),
                    "pending_balance":  str(wallet.pending_balance),
                    "available_balance":str(wallet.available_balance),
                    "is_locked":        wallet.is_locked,
                },
            }
        )
    except Exception as e:
        logger.debug(f"push_balance_update skip: {e}")
