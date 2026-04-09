# api/djoyalty/services/points/WalletBridgeService.py
"""Wallet system integration bridge।"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class WalletBridgeService:
    @staticmethod
    def sync_balance_to_wallet(customer, balance: Decimal):
        logger.debug('WalletBridge: sync %s pts for %s', balance, customer)
        # Wallet integration hook — override per project
        return True

    @staticmethod
    def sync_balance_from_wallet(customer) -> Decimal:
        logger.debug('WalletBridge: fetch balance for %s', customer)
        return Decimal('0')
