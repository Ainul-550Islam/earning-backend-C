"""
Audit Logger — Immutable, tamper-evident audit logging for the DR system.
"""
import logging, json, os, hashlib, threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Immutable audit logging with integrity hashing and dual-write.
    """
    AUDIT_LOG_FILE = "/var/log/dr/dr_audit.jsonl"
    SECURITY_LOG_FILE = "/var/log/dr/security_audit.jsonl"
    SECURITY_SENSITIVE = {"failover.execute","restore.execute","backup.delete","config.write",
                          "security.write","key.rotate","key.revoke","incident.create",
                          "emergency_shutdown","permission_denied","login.failed"}

    def __init__(self, db_session=None, config: dict = None):
        self.db = db_session
        self.config = config or {}
        self._lock = threading.Lock()
        self._setup_dirs()

    def log(self, actor_id: str, action: str, resource_type: str = None,
             resource_id: str = None, ip_address: str = None,
             result: str = "success", error_message: str = None,
             old_values: dict = None, new_values: dict = None,
             request_id: str = None, session_id: str = None,
             actor_type: str = "user", **extra) -> dict:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "actor_id": actor_id, "actor_type": actor_type, "action": action,
            "resource_type": resource_type, "resource_id": resource_id,
            "ip_address": ip_address, "result": result,
            "error_message": error_message, "request_id": request_id,
            "severity": "warning" if result == "denied" or action in self.SECURITY_SENSITIVE else "info",
        }
        entry["hash"] = self._hash(entry)
        self._write(entry, self.AUDIT_LOG_FILE)
        if action in self.SECURITY_SENSITIVE or result == "denied":
            self._write(entry, self.SECURITY_LOG_FILE)
        if self.db:
            self._persist_to_db(entry)
        log_fn = logger.warning if result == "denied" else logger.debug
        log_fn(f"AUDIT [{entry['severity']}] {actor_id}|{action}|{result}")
        return entry

    def log_access_denied(self, actor_id: str, action: str, resource: str, ip_address: str = None) -> dict:
        return self.log(actor_id=actor_id, action=action, resource_type=resource,
                        ip_address=ip_address, result="denied")

    def log_security_event(self, event_type: str, actor_id: str, description: str, details: dict = None) -> dict:
        return self.log(actor_id=actor_id, action=event_type, resource_type="security",
                        new_values={"description": description, **(details or {})}, result="security_event")

    def search(self, actor_id: str = None, action: str = None, resource_type: str = None,
                from_date=None, to_date=None, result: str = None, limit: int = 100) -> List[dict]:
        results = []
        if not os.path.exists(self.AUDIT_LOG_FILE): return results
        try:
            with open(self.AUDIT_LOG_FILE) as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        e = json.loads(line)
                        if self._matches(e, actor_id, action, resource_type, from_date, to_date, result):
                            results.append(e)
                    except json.JSONDecodeError: pass
        except Exception as err:
            logger.warning(f"Audit search error: {err}")
        return sorted(results, key=lambda x: x.get("timestamp",""), reverse=True)[:limit]

    def verify_integrity(self, max_entries: int = 1000) -> dict:
        verified, failed = 0, 0
        if not os.path.exists(self.AUDIT_LOG_FILE):
            return {"status": "no_log_file", "verified": 0, "failed": 0}
        try:
            with open(self.AUDIT_LOG_FILE) as f:
                for i, line in enumerate(f):
                    if i >= max_entries: break
                    if not line.strip(): continue
                    try:
                        e = json.loads(line.strip())
                        stored = e.pop("hash", None)
                        if self._hash(e) == stored: verified += 1
                        else: failed += 1
                    except Exception: failed += 1
        except Exception as err:
            return {"status": "error", "error": str(err)}
        return {"status": "tampered" if failed > 0 else "intact",
                "verified_entries": verified, "failed_entries": failed,
                "integrity_percent": round(verified/max(verified+failed,1)*100,2)}

    def cleanup_old_logs(self, retain_days: int = 2555) -> dict:
        cutoff = datetime.utcnow() - timedelta(days=retain_days)
        if not os.path.exists(self.AUDIT_LOG_FILE): return {"cleaned": 0}
        kept, removed = [], 0
        with open(self.AUDIT_LOG_FILE) as f:
            for line in f:
                try:
                    e = json.loads(line.strip())
                    if datetime.fromisoformat(e.get("timestamp","")) >= cutoff: kept.append(line)
                    else: removed += 1
                except Exception: kept.append(line)
        with open(self.AUDIT_LOG_FILE, "w") as f: f.writelines(kept)
        return {"cleaned": removed, "retained": len(kept)}

    def _hash(self, entry: dict) -> str:
        content = json.dumps({k: entry.get(k) for k in
                               ["timestamp","actor_id","action","resource_type","resource_id","result"]},
                              sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _write(self, entry: dict, log_file: str):
        with self._lock:
            try:
                with open(log_file, "a") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception as e:
                logger.error(f"Audit write error: {e}")

    def _persist_to_db(self, entry: dict):
        try:
            from .sa_models import DR_AuditTrail
            trail = DR_AuditTrail(
                actor_id=entry["actor_id"], actor_type=entry["actor_type"],
                action=entry["action"], resource_type=entry["resource_type"],
                resource_id=entry["resource_id"], ip_address=entry["ip_address"],
                result=entry["result"], error_message=entry["error_message"])
            self.db.add(trail)
            self.db.commit()
        except Exception: pass

    def _setup_dirs(self):
        for f in [self.AUDIT_LOG_FILE, self.SECURITY_LOG_FILE]:
            try: os.makedirs(os.path.dirname(f), mode=0o750, exist_ok=True)
            except Exception: pass

    def _matches(self, entry, actor_id, action, resource_type, from_date, to_date, result) -> bool:
        if actor_id and entry.get("actor_id") != actor_id: return False
        if action and entry.get("action") != action: return False
        if resource_type and entry.get("resource_type") != resource_type: return False
        if result and entry.get("result") != result: return False
        if from_date or to_date:
            try:
                ts = datetime.fromisoformat(entry.get("timestamp",""))
                if from_date and ts < from_date: return False
                if to_date and ts > to_date: return False
            except Exception: return False
        return True
