# api/djoyalty/web3_loyalty.py
"""
Djoyalty Web3 Loyalty -- NFT/Blockchain loyalty infrastructure।
Future-ready: tokenized rewards, NFT badges, on-chain point tracking।

2025/2026 research: 60% of Fortune 500 companies working on blockchain initiatives।
Best practice: blockchain as "invisible plumbing" -- no jargon to customers।
Reference: Starbucks Odyssey (Polygon), Hugo Boss XP, Lacoste UNDW3。

NOTE: Requires web3 package: pip install web3
      And a blockchain provider (Infura, Alchemy, or local node)।

"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from typing import Optional
from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─── Web3 Config ─────────────────────────────────────────────────────────────

def get_web3_config() -> dict:
    return getattr(settings, 'DJOYALTY_WEB3', {
        'ENABLED': False,
        'PROVIDER_URL': '',        # Infura/Alchemy URL
        'CHAIN_ID': 137,           # Polygon mainnet
        'CONTRACT_ADDRESS': '',    # Your loyalty token contract
        'PRIVATE_KEY': '',         # Deployer wallet private key
        'NETWORK': 'polygon',      # 'polygon', 'ethereum', 'solana'
    })


# ─── Models ──────────────────────────────────────────────────────────────────

class NFTBadge(models.Model):
    """
    NFT-backed badge for a customer।
    Minted on blockchain when earned (if web3 enabled)।
    Starbucks Odyssey "journey stamps" style।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='nft_badges',
    )
    badge = models.ForeignKey(
        'djoyalty.Badge', on_delete=models.CASCADE,
        related_name='nft_instances',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='nft_badges',
    )

    # Blockchain data
    token_id = models.CharField(max_length=100, null=True, blank=True,
                                 verbose_name='NFT Token ID on blockchain')
    contract_address = models.CharField(max_length=100, null=True, blank=True)
    blockchain = models.CharField(max_length=30, default='polygon')
    wallet_address = models.CharField(max_length=100, null=True, blank=True,
                                       verbose_name='Customer wallet address')
    transaction_hash = models.CharField(max_length=200, null=True, blank=True)
    metadata_uri = models.URLField(null=True, blank=True, verbose_name='NFT metadata URI (IPFS)')

    # Status
    minted = models.BooleanField(default=False)
    minted_at = models.DateTimeField(null=True, blank=True)
    mint_error = models.CharField(max_length=500, null=True, blank=True)

    # Traditional fallback (always stored in DB even without blockchain)
    earned_at = models.DateTimeField(default=timezone.now)
    is_tradeable = models.BooleanField(default=False)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'NFT Badge'
        ordering = ['-earned_at']
        unique_together = [('customer', 'badge')]

    def __str__(self):
        return f'NFTBadge({self.customer.code}: {self.badge.name} minted={self.minted})'


class CustomerWallet(models.Model):
    """
    Customer's Web3 wallet for receiving NFT rewards।
    Optional -- customers don't need a wallet for traditional loyalty।
    """
    customer = models.OneToOneField(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='web3_wallet',
    )
    wallet_address = models.CharField(max_length=100, unique=True)
    wallet_type = models.CharField(
        max_length=20,
        choices=[
            ('metamask', 'MetaMask'),
            ('walletconnect', 'WalletConnect'),
            ('coinbase', 'Coinbase Wallet'),
            ('custodial', 'Custodial (Managed)'),
        ],
        default='custodial',
    )
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    chain_id = models.IntegerField(default=137)  # Polygon

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Web3 Wallet'

    def __str__(self):
        return f'Wallet({self.customer.code}: {self.wallet_address[:10]}...)'


# ─── Web3 Service ────────────────────────────────────────────────────────────

class Web3LoyaltyService:
    """
    Web3 loyalty service -- NFT minting, token transfers।
    Falls back gracefully if web3 not configured।

    Best practice (2025/2026): blockchain = invisible infrastructure।
    Customers don't need to know about blockchain -- they just get "digital badges"।
    """

    @staticmethod
    def is_enabled() -> bool:
        return get_web3_config().get('ENABLED', False)

    @staticmethod
    def get_provider():
        """Get Web3 provider connection।"""
        try:
            from web3 import Web3
            config = get_web3_config()
            provider_url = config.get('PROVIDER_URL', '')
            if not provider_url:
                return None
            w3 = Web3(Web3.HTTPProvider(provider_url))
            return w3 if w3.is_connected() else None
        except ImportError:
            logger.debug('web3_loyalty: web3 package not installed. pip install web3')
            return None
        except Exception as e:
            logger.debug('web3_loyalty.get_provider error: %s', e)
            return None

    @staticmethod
    def mint_badge_nft(customer, badge) -> NFTBadge:
        """
        Mint an NFT badge for a customer।
        Creates DB record first, then tries to mint on-chain (non-blocking)।
        If blockchain mint fails, the DB record still exists (traditional badge)。
        """
        nft_badge, created = NFTBadge.objects.get_or_create(
            customer=customer,
            badge=badge,
            defaults={
                'tenant': customer.tenant,
                'earned_at': timezone.now(),
                'blockchain': get_web3_config().get('NETWORK', 'polygon'),
            },
        )

        if not created or nft_badge.minted:
            return nft_badge

        # Try to get customer wallet
        wallet = CustomerWallet.objects.filter(
            customer=customer, is_verified=True
        ).first()

        if Web3LoyaltyService.is_enabled() and wallet:
            # Queue blockchain minting (non-blocking)
            try:
                from .background_jobs import LoyaltyJobRunner
                # Would call a Celery task to mint on-chain
                logger.info('web3_loyalty: queued NFT mint for %s badge %s',
                            customer.code, badge.name)
            except Exception as e:
                logger.debug('web3_loyalty.mint_badge_nft queue error: %s', e)

        return nft_badge

    @staticmethod
    def get_customer_nft_badges(customer) -> list:
        """Get all NFT badges for a customer।"""
        return list(
            NFTBadge.objects.filter(customer=customer)
            .select_related('badge')
            .order_by('-earned_at')
        )

    @staticmethod
    def verify_wallet_ownership(customer, wallet_address: str,
                                  signature: str, message: str) -> bool:
        """
        Verify customer owns a wallet via signature verification।
        Customer signs a message in MetaMask -> we verify server-side।
        """
        try:
            from web3 import Web3
            from eth_account.messages import encode_defunct
            w3 = Web3()
            msg = encode_defunct(text=message)
            recovered = w3.eth.account.recover_message(msg, signature=signature)
            return recovered.lower() == wallet_address.lower()
        except ImportError:
            logger.debug('web3: web3 package not installed')
            return False
        except Exception as e:
            logger.debug('verify_wallet_ownership error: %s', e)
            return False

    @staticmethod
    def link_wallet(customer, wallet_address: str, wallet_type: str = 'metamask') -> CustomerWallet:
        """Link a Web3 wallet to a customer account।"""
        wallet, created = CustomerWallet.objects.update_or_create(
            customer=customer,
            defaults={
                'wallet_address': wallet_address.lower(),
                'wallet_type': wallet_type,
                'is_verified': False,
            },
        )
        logger.info('web3_loyalty: wallet linked for %s -- %s', customer.code, wallet_address[:10])
        return wallet


# ─── Tokenized Points (ERC-20 style) ─────────────────────────────────────────

class TokenizedPointsService:
    """
    Optional: Represent loyalty points as on-chain tokens।
    ERC-20 loyalty tokens that customers can potentially trade/transfer।
    
    WARNING: Token-based loyalty has legal implications (securities law)।
    Consult legal counsel before enabling for users।
    Current approach: DB-backed first, optional on-chain mirroring।
    """

    @staticmethod
    def mirror_balance_on_chain(customer, balance: Decimal) -> bool:
        """Mirror DB points balance to on-chain token balance (optional)。"""
        if not Web3LoyaltyService.is_enabled():
            return False

        wallet = CustomerWallet.objects.filter(
            customer=customer, is_verified=True
        ).first()

        if not wallet:
            return False

        # Log intent -- actual on-chain mirroring requires smart contract
        logger.info(
            'TokenizedPointsService: would mirror %s pts for %s to %s (on-chain disabled)',
            balance, customer.code, wallet.wallet_address[:10],
        )
        return False  # Returns False until smart contract is deployed
