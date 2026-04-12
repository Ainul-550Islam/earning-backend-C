# =============================================================================
# promotions/crypto_payments/usdt_payment.py
# 🔴 CRITICAL — USDT Fast Pay (CPAlead's signature feature 2024)
# Publishers get paid in USDT same day — $25 minimum
# Supports: TRC20 (Tron), ERC20 (Ethereum), BEP20 (BSC)
# =============================================================================
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
import uuid
import logging

logger = logging.getLogger(__name__)

USDT_MINIMUM = Decimal('25.00')   # CPAlead standard
USDT_NETWORKS = {
    'TRC20': {'name': 'Tron (TRC20)', 'fee': Decimal('1.00'),  'confirmations': 1,  'speed': '2-5 mins'},
    'ERC20': {'name': 'Ethereum (ERC20)', 'fee': Decimal('5.00'),  'confirmations': 12, 'speed': '5-15 mins'},
    'BEP20': {'name': 'BSC (BEP20)', 'fee': Decimal('0.50'),  'confirmations': 3,  'speed': '1-3 mins'},
}


class USDTPaymentProcessor:
    """
    USDT Fast Pay — same-day crypto payouts for publishers.
    CPAlead launched this in 2024; users love it.
    """

    def create_payout_request(
        self,
        publisher_id: int,
        amount: Decimal,
        wallet_address: str,
        network: str = 'TRC20',
    ) -> dict:
        """Request USDT payout."""
        if network not in USDT_NETWORKS:
            return {'error': f'Invalid network. Choose: {", ".join(USDT_NETWORKS.keys())}'}

        if amount < USDT_MINIMUM:
            return {'error': f'Minimum USDT payout is ${USDT_MINIMUM}'}

        if not self._validate_wallet_address(wallet_address, network):
            return {'error': 'Invalid wallet address for selected network'}

        net_info = USDT_NETWORKS[network]
        fee = net_info['fee']
        net_amount = amount - fee

        payout_id = str(uuid.uuid4())
        payout = {
            'payout_id': payout_id,
            'publisher_id': publisher_id,
            'amount_usd': str(amount),
            'fee': str(fee),
            'net_amount': str(net_amount),
            'wallet_address': wallet_address,
            'network': network,
            'network_name': net_info['name'],
            'status': 'pending',
            'estimated_speed': net_info['speed'],
            'created_at': timezone.now().isoformat(),
            'tx_hash': None,
        }

        # Store in cache (production: store in DB)
        cache.set(f'usdt_payout:{payout_id}', payout, timeout=3600 * 24 * 7)

        # Lock publisher balance
        self._lock_publisher_balance(publisher_id, amount, payout_id)

        logger.info(f'USDT payout created: {payout_id} | ${amount} | {network} | Publisher: {publisher_id}')

        return {
            'payout_id': payout_id,
            'status': 'pending',
            'amount': str(amount),
            'fee': str(fee),
            'you_receive': str(net_amount),
            'network': network,
            'wallet': f'{wallet_address[:6]}...{wallet_address[-4:]}',
            'estimated_time': net_info['speed'],
            'message': 'USDT payout queued. Processing within 24 hours.',
        }

    def process_payout(self, payout_id: str) -> dict:
        """Admin/System: actually send the USDT (calls blockchain API)."""
        payout = cache.get(f'usdt_payout:{payout_id}')
        if not payout:
            return {'error': 'Payout not found'}
        if payout['status'] != 'pending':
            return {'error': f'Payout already {payout["status"]}'}

        # In production: call Tron/ETH/BSC API here
        # Example for TRC20 via TronGrid:
        # tx_hash = self._send_trc20(payout['wallet_address'], Decimal(payout['net_amount']))
        tx_hash = f'0x{uuid.uuid4().hex}'  # Simulated

        payout['status'] = 'completed'
        payout['tx_hash'] = tx_hash
        payout['completed_at'] = timezone.now().isoformat()
        cache.set(f'usdt_payout:{payout_id}', payout, timeout=3600 * 24 * 30)

        # Create transaction record
        self._create_withdrawal_record(
            publisher_id=payout['publisher_id'],
            amount=Decimal(payout['amount_usd']),
            payout_id=payout_id,
            tx_hash=tx_hash,
        )

        return {
            'payout_id': payout_id,
            'status': 'completed',
            'tx_hash': tx_hash,
            'explorer_url': self._get_explorer_url(payout['network'], tx_hash),
        }

    def get_payout_status(self, payout_id: str) -> dict:
        payout = cache.get(f'usdt_payout:{payout_id}')
        if not payout:
            return {'error': 'Payout not found'}
        return {
            'payout_id': payout_id,
            'status': payout['status'],
            'amount': payout['amount_usd'],
            'network': payout['network'],
            'wallet': payout['wallet_address'],
            'tx_hash': payout.get('tx_hash'),
            'created_at': payout['created_at'],
            'completed_at': payout.get('completed_at'),
            'explorer_url': (
                self._get_explorer_url(payout['network'], payout['tx_hash'])
                if payout.get('tx_hash') else None
            ),
        }

    def get_supported_networks(self) -> list:
        return [
            {
                'network': k,
                'name': v['name'],
                'fee': str(v['fee']),
                'confirmations': v['confirmations'],
                'speed': v['speed'],
                'minimum': str(USDT_MINIMUM),
            }
            for k, v in USDT_NETWORKS.items()
        ]

    def _validate_wallet_address(self, address: str, network: str) -> bool:
        if network == 'TRC20':
            return address.startswith('T') and len(address) == 34
        elif network in ('ERC20', 'BEP20'):
            return address.startswith('0x') and len(address) == 42
        return False

    def _get_explorer_url(self, network: str, tx_hash: str) -> str:
        explorers = {
            'TRC20': f'https://tronscan.org/#/transaction/{tx_hash}',
            'ERC20': f'https://etherscan.io/tx/{tx_hash}',
            'BEP20': f'https://bscscan.com/tx/{tx_hash}',
        }
        return explorers.get(network, f'#{tx_hash}')

    def _lock_publisher_balance(self, publisher_id: int, amount: Decimal, payout_id: str):
        from api.promotions.models import PromotionTransaction
        try:
            PromotionTransaction.objects.create(
                user_id=publisher_id,
                transaction_type='withdrawal',
                amount=-amount,
                status='pending',
                notes=f'USDT Payout #{payout_id[:8]}',
                metadata={'payout_id': payout_id, 'method': 'usdt'},
            )
        except Exception as e:
            logger.error(f'Failed to lock balance for payout {payout_id}: {e}')

    def _create_withdrawal_record(self, publisher_id: int, amount: Decimal, payout_id: str, tx_hash: str):
        from api.promotions.models import PromotionTransaction
        PromotionTransaction.objects.filter(
            user_id=publisher_id,
            notes__icontains=payout_id[:8],
            status='pending',
        ).update(
            status='completed',
            metadata={'payout_id': payout_id, 'method': 'usdt', 'tx_hash': tx_hash},
        )
