"""
Global Deduplication Engine
Inspired by: Commvault global dedup, Cohesity global deduplication
Eliminates redundant data blocks across all backups to minimize storage.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BLOCK_SIZE = 4096  # 4KB fixed-size blocks


@dataclass
class DedupBlock:
    hash: str
    size: int
    ref_count: int = 1

    @property
    def is_shared(self) -> bool:
        return self.ref_count > 1


class GlobalDeduplicationEngine:
    """
    Content-addressed block store for deduplication across all backups.
    Stores each unique block once; backup manifests reference block hashes.
    """

    def __init__(self, block_size: int = BLOCK_SIZE):
        self.block_size = block_size
        self._store: Dict[str, DedupBlock] = {}       # hash -> block
        self._manifests: Dict[str, List[str]] = {}    # backup_id -> [hash, ...]
        self.bytes_in = 0
        self.bytes_stored = 0

    def ingest_file(self, backup_id: str, file_path: str) -> Dict[str, int]:
        """Chunk a file into blocks and dedup against global store"""
        blocks = []
        new_blocks = 0
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(self.block_size)
                if not chunk:
                    break
                self.bytes_in += len(chunk)
                h = hashlib.sha256(chunk).hexdigest()
                if h in self._store:
                    self._store[h].ref_count += 1
                else:
                    self._store[h] = DedupBlock(hash=h, size=len(chunk))
                    self.bytes_stored += len(chunk)
                    new_blocks += 1
                blocks.append(h)

        self._manifests[backup_id] = blocks
        return {"total_blocks": len(blocks), "new_blocks": new_blocks,
                "dedup_ratio": self.dedup_ratio}

    def get_manifest(self, backup_id: str) -> Optional[List[str]]:
        return self._manifests.get(backup_id)

    def release_backup(self, backup_id: str) -> int:
        """Decrement ref counts for a backup's blocks; GC orphans"""
        manifest = self._manifests.pop(backup_id, [])
        freed = 0
        for h in manifest:
            block = self._store.get(h)
            if block:
                block.ref_count -= 1
                if block.ref_count <= 0:
                    freed += block.size
                    del self._store[h]
        self.bytes_stored -= freed
        return freed

    @property
    def dedup_ratio(self) -> float:
        if self.bytes_stored == 0:
            return 1.0
        return round(self.bytes_in / self.bytes_stored, 2)

    @property
    def savings_bytes(self) -> int:
        return max(0, self.bytes_in - self.bytes_stored)

    def stats(self) -> Dict[str, any]:
        return {
            "unique_blocks": len(self._store),
            "bytes_in": self.bytes_in,
            "bytes_stored": self.bytes_stored,
            "savings_bytes": self.savings_bytes,
            "dedup_ratio": self.dedup_ratio,
            "tracked_backups": len(self._manifests),
        }
