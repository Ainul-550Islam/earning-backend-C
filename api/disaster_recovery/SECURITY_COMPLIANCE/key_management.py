"""
Key Management — Manages encryption key lifecycle: generation, rotation, revocation.
"""
import logging
import os
import base64
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class KeyManager:
    """
    Manages the full lifecycle of encryption keys including:
    - Key generation (local random or via cloud KMS)
    - Scheduled rotation with configurable interval
    - Key revocation and audit trail
    - File-based persistent storage with secure permissions
    """

    KEY_SIZE_BYTES = 32

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.rotation_days = config.get("rotation_days", 90) if config else 90
        self.kms_provider = config.get("kms_provider","local") if config else "local"
        self.key_store_path = config.get("key_store_path","/etc/dr/keys") if config else "/etc/dr/keys"
        self._store: Dict[str, dict] = {}
        self._rotation_log: List[dict] = []
        self._load_keys()

    def generate_key(self, purpose: str = "backup_encryption", expires_days: int = None) -> dict:
        """Generate a new cryptographically secure encryption key."""
        key_material = os.urandom(self.KEY_SIZE_BYTES)
        key_id = self._make_id()
        expires_days = expires_days or self.rotation_days
        key = {"key_id": key_id, "key_material_b64": base64.b64encode(key_material).decode(),
               "created_at": datetime.utcnow().isoformat(),
               "expires_at": (datetime.utcnow() + timedelta(days=expires_days)).isoformat(),
               "purpose": purpose, "version": self._next_version(purpose),
               "revoked": False, "revoked_at": None}
        self._store[key_id] = key
        self._save_keys()
        logger.info(f"Key generated: {key_id} purpose={purpose}")
        return {k: v for k, v in key.items() if k != "key_material_b64"}

    def get_active_key(self, purpose: str = "backup_encryption") -> Optional[dict]:
        """Get the current active key for a purpose."""
        active = [k for k in self._store.values()
                  if k["purpose"] == purpose and not k["revoked"]
                  and k["expires_at"] > datetime.utcnow().isoformat()]
        if not active: return None
        return max(active, key=lambda k: k["created_at"])

    def get_key_by_id(self, key_id: str) -> Optional[dict]:
        """Get a key by ID (including expired/revoked)."""
        return self._store.get(key_id)

    def rotate_key(self, purpose: str = "backup_encryption", authorized_by: str = "system") -> dict:
        """Rotate the key for a purpose."""
        old = self.get_active_key(purpose)
        new = self.generate_key(purpose)
        record = {"old_key_id": old["key_id"] if old else None, "new_key_id": new["key_id"],
                  "purpose": purpose, "rotated_by": authorized_by,
                  "rotated_at": datetime.utcnow().isoformat()}
        self._rotation_log.append(record)
        logger.warning(f"KEY ROTATED: {record['old_key_id']} -> {new['key_id']} by {authorized_by}")
        return {"success": True, **record}

    def revoke_key(self, key_id: str, reason: str, revoked_by: str = "system") -> dict:
        """Revoke a key permanently."""
        key = self._store.get(key_id)
        if not key: return {"success": False, "error": f"Key not found: {key_id}"}
        key["revoked"] = True
        key["revoked_at"] = datetime.utcnow().isoformat()
        self._save_keys()
        logger.warning(f"KEY REVOKED: {key_id} by {revoked_by} | {reason}")
        return {"success": True, "key_id": key_id, "revoked_by": revoked_by, "reason": reason}

    def check_rotation_needed(self) -> List[dict]:
        """Find keys due for rotation."""
        return [{"key_id": k["key_id"], "purpose": k["purpose"],
                 "age_days": (datetime.utcnow() - datetime.fromisoformat(k["created_at"])).days}
                for k in self._store.values()
                if not k["revoked"] and
                (datetime.utcnow() - datetime.fromisoformat(k["created_at"])).days >= self.rotation_days]

    def is_rotation_due(self, key_created_at: datetime) -> bool:
        return (datetime.utcnow() - key_created_at).days >= self.rotation_days

    def get_all_keys(self, include_revoked: bool = False, purpose: str = None) -> List[dict]:
        keys = [k for k in self._store.values()
                if (include_revoked or not k["revoked"]) and (not purpose or k["purpose"] == purpose)]
        return [{k2: v for k2, v in k.items() if k2 != "key_material_b64"}
                for k in sorted(keys, key=lambda x: x["created_at"], reverse=True)]

    def get_rotation_log(self, limit: int = 20) -> List[dict]:
        return self._rotation_log[-limit:]

    def get_key_stats(self) -> dict:
        all_keys = list(self._store.values())
        now_iso = datetime.utcnow().isoformat()
        active = [k for k in all_keys if not k["revoked"] and k["expires_at"] > now_iso]
        return {"total_keys": len(all_keys), "active_keys": len(active),
                "revoked_keys": sum(1 for k in all_keys if k["revoked"]),
                "needing_rotation": len(self.check_rotation_needed()),
                "rotation_interval_days": self.rotation_days}

    def _make_id(self) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        rand = base64.urlsafe_b64encode(os.urandom(8)).decode().rstrip("=")
        return f"drkey-{ts}-{rand}"

    def _next_version(self, purpose: str) -> int:
        existing = [k["version"] for k in self._store.values() if k["purpose"] == purpose]
        return max(existing, default=0) + 1

    def _load_keys(self):
        key_file = os.path.join(self.key_store_path, "keys.json")
        if not os.path.exists(key_file): return
        try:
            with open(key_file) as f:
                data = json.load(f)
            for k in data.get("keys", []):
                self._store[k["key_id"]] = k
        except Exception as e:
            logger.debug(f"Key load error: {e}")

    def _save_keys(self):
        try:
            os.makedirs(self.key_store_path, mode=0o700, exist_ok=True)
            key_file = os.path.join(self.key_store_path, "keys.json")
            data = {"version": "1.0", "saved_at": datetime.utcnow().isoformat(),
                    "keys": list(self._store.values())}
            tmp = key_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, key_file)
            try: os.chmod(key_file, 0o600)
            except Exception: pass
        except Exception as e:
            logger.debug(f"Key save error: {e}")
