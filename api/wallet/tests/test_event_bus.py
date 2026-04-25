# api/wallet/tests/test_event_bus.py
from decimal import Decimal
from django.test import TestCase
from ..event_bus import WalletEventBus
from ..events import WalletCredited, WithdrawalRequested, EarningAdded

class EventBusTest(TestCase):
    def setUp(self):
        self.bus = WalletEventBus()

    def test_subscribe_and_publish(self):
        received = []
        @self.bus.subscribe(WalletCredited)
        def handler(event: WalletCredited):
            received.append(event)
        self.bus.publish(WalletCredited(wallet_id=1, user_id=1, amount=Decimal("500")))
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].amount, Decimal("500"))

    def test_multiple_handlers_same_event(self):
        calls = []
        @self.bus.subscribe(EarningAdded)
        def h1(e): calls.append("h1")
        @self.bus.subscribe(EarningAdded)
        def h2(e): calls.append("h2")
        self.bus.publish(EarningAdded(wallet_id=1, user_id=1, amount=Decimal("100")))
        self.assertIn("h1", calls)
        self.assertIn("h2", calls)

    def test_handler_exception_doesnt_crash_bus(self):
        @self.bus.subscribe(WalletCredited)
        def bad_handler(e): raise RuntimeError("intentional error")
        # Should not raise
        self.bus.publish(WalletCredited(wallet_id=1, user_id=1, amount=Decimal("100")))

    def test_clear_handlers(self):
        received = []
        @self.bus.subscribe(WalletCredited)
        def h(e): received.append(1)
        self.bus.clear_handlers("WalletCredited")
        self.bus.publish(WalletCredited(wallet_id=1, user_id=1))
        self.assertEqual(len(received), 0)

    def test_get_handlers_list(self):
        @self.bus.subscribe(EarningAdded)
        def my_handler(e): pass
        handlers = self.bus.get_handlers("EarningAdded")
        self.assertIn("my_handler", handlers)

    def test_events_are_dataclasses(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(WalletCredited))
        self.assertTrue(dataclasses.is_dataclass(WithdrawalRequested))
        self.assertTrue(dataclasses.is_dataclass(EarningAdded))

    def test_event_serialization(self):
        from ..event_bus import _serialize_event
        event = WalletCredited(wallet_id=1, user_id=2, amount=Decimal("100.50"), txn_id="abc")
        serialized = _serialize_event(event)
        import json
        data = json.loads(serialized)
        self.assertEqual(data["wallet_id"], 1)
        self.assertEqual(data["amount"], "100.50")
        self.assertEqual(data["__event_type__"], "WalletCredited")
