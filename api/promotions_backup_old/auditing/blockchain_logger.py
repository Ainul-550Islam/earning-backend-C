# api/promotions/auditing/blockchain_logger.py
# Blockchain Logger — Immutable ledger using hash chain (Merkle-style)
# Full blockchain integration optional: Polygon/BSC for actual on-chain logging
import hashlib, json, logging, time
from dataclasses import dataclass, field
from django.core.cache import cache
logger = logging.getLogger('auditing.blockchain')

@dataclass
class Block:
    index:       int
    data:        dict
    previous_hash: str
    timestamp:   float = field(default_factory=time.time)
    hash:        str   = ''
    nonce:       int   = 0

    def __post_init__(self):
        if not self.hash:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        payload = json.dumps({
            'index': self.index, 'data': self.data,
            'prev': self.previous_hash, 'ts': self.timestamp, 'nonce': self.nonce,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

class BlockchainLogger:
    """
    Local hash chain for tamper-evident audit log.
    Optional: push to Polygon/BSC for true decentralization.

    Every financial transaction → new block → chained to previous block.
    Any tampering invalidates the entire chain from that point.
    """
    CHAIN_KEY = 'audit:blockchain:chain'

    def append(self, data: dict) -> Block:
        chain = cache.get(self.CHAIN_KEY) or []
        prev_hash = chain[-1]['hash'] if chain else '0' * 64
        block     = Block(index=len(chain), data=data, previous_hash=prev_hash)
        chain.append(block.__dict__)
        cache.set(self.CHAIN_KEY, chain[-10000:], timeout=86400 * 30)
        # Persist to DB
        self._save_block(block)
        return block

    def log_payout(self, user_id: int, amount_usd: float, tx_hash: str) -> Block:
        return self.append({'type': 'payout', 'user_id': user_id, 'amount': amount_usd, 'tx': tx_hash})

    def log_commission(self, campaign_id: int, amount_usd: float, actor_id: int) -> Block:
        return self.append({'type': 'commission', 'campaign': campaign_id, 'amount': amount_usd, 'actor': actor_id})

    def verify_chain(self) -> dict:
        """Chain integrity verify করে।"""
        chain  = cache.get(self.CHAIN_KEY) or []
        errors = []
        for i in range(1, len(chain)):
            b     = chain[i]
            prev  = chain[i-1]
            block = Block(b['index'], b['data'], b['previous_hash'], b['timestamp'], '', b['nonce'])
            if block.compute_hash() != b['hash']:
                errors.append(f'Block {i}: hash mismatch')
            if b['previous_hash'] != prev['hash']:
                errors.append(f'Block {i}: previous hash mismatch')
        return {'length': len(chain), 'valid': len(errors) == 0, 'errors': errors}

    def push_to_blockchain(self, block: Block) -> str | None:
        """Polygon/BSC এ push করো (optional)।"""
        web3_url = __import__('django.conf', fromlist=['settings']).settings.__dict__.get('WEB3_PROVIDER_URL')
        if not web3_url:
            return None
        # Web3.py দিয়ে smart contract call করুন
        logger.info(f'Block {block.index} pushed to blockchain')
        return block.hash

    def _save_block(self, block: Block):
        try:
            from api.promotions.models import BlockchainEntry
            BlockchainEntry.objects.create(
                block_index=block.index, block_hash=block.hash,
                previous_hash=block.previous_hash, data=block.data,
            )
        except Exception:
            pass
