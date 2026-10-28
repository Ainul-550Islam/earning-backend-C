# api/admin_panel/mock_gateway.py
"""Mock payment gateway for testing — never call real APIs."""
from __future__ import annotations
import random, uuid
from typing import Dict

class MockPaymentGateway:
    """Simulates payment gateway responses for testing."""
    SUCCESS_RATE = 0.9  # 90% success rate

    @classmethod
    def process_payout(cls, account: str, amount: float, reference: str) -> Dict:
        if random.random() < cls.SUCCESS_RATE:
            return {'success': True, 'transaction_id': f'MOCK-{uuid.uuid4().hex[:12].upper()}',
                    'reference': reference, 'amount': amount, 'gateway': 'mock'}
        return {'success': False, 'error': 'Mock gateway: random failure', 'reference': reference}

    @classmethod
    def verify_payment(cls, transaction_id: str) -> Dict:
        return {'verified': True, 'transaction_id': transaction_id, 'status': 'COMPLETED'}

    @classmethod
    def refund(cls, transaction_id: str, amount: float) -> Dict:
        return {'success': True, 'refund_id': f'REFUND-{uuid.uuid4().hex[:8].upper()}',
                'amount': amount, 'original': transaction_id}

    @classmethod
    def get_balance(cls) -> Dict:
        return {'balance': 999999.99, 'currency': 'BDT', 'gateway': 'mock'}

mock_gateway = MockPaymentGateway()