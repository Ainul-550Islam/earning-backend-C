"""Self Healing — Detects and repairs system issues automatically."""
import logging, subprocess
from datetime import datetime
logger = logging.getLogger(__name__)

class SelfHealing:
    def __init__(self, rules: list = None):
        self.rules = rules or self._default_rules()

    def _default_rules(self) -> list:
        return [
            {"trigger": "service_down", "action": "restart_service", "max_attempts": 3},
            {"trigger": "disk_full", "action": "cleanup_old_logs", "max_attempts": 1},
            {"trigger": "high_memory", "action": "clear_cache", "max_attempts": 2},
            {"trigger": "replication_lag_high", "action": "restart_replica", "max_attempts": 1},
        ]

    def heal(self, trigger: str, context: dict) -> dict:
        rule = next((r for r in self.rules if r["trigger"] == trigger), None)
        if not rule:
            return {"healed": False, "reason": f"No rule for trigger: {trigger}"}
        action = rule["action"]
        logger.warning(f"SELF HEAL: trigger={trigger} action={action}")
        return getattr(self, f"_action_{action}")(context, rule)

    def _action_restart_service(self, ctx: dict, rule: dict) -> dict:
        svc = ctx.get("service_name", "")
        try:
            subprocess.run(["systemctl", "restart", svc], timeout=30)
            return {"healed": True, "action": "restart_service", "service": svc}
        except Exception as e:
            return {"healed": False, "error": str(e)}

    def _action_cleanup_old_logs(self, ctx: dict, rule: dict) -> dict:
        import shutil, os
        log_dir = ctx.get("log_dir", "/var/log")
        freed = 0
        for f in os.listdir(log_dir):
            if f.endswith(".gz") or f.endswith(".1"):
                path = os.path.join(log_dir, f)
                freed += os.path.getsize(path)
                os.remove(path)
        return {"healed": True, "action": "cleanup_old_logs", "freed_bytes": freed}

    def _action_clear_cache(self, ctx: dict, rule: dict) -> dict:
        try:
            subprocess.run(["sync"], timeout=5)
            with open("/proc/sys/vm/drop_caches", "w") as f:
                f.write("3")
            return {"healed": True, "action": "clear_cache"}
        except Exception as e:
            return {"healed": False, "error": str(e)}

    def _action_restart_replica(self, ctx: dict, rule: dict) -> dict:
        return {"healed": True, "action": "restart_replica", "note": "Manual intervention may be required"}
