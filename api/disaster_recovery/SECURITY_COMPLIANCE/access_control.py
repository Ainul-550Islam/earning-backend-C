"""
Access Control — Role-based access control for DR operations.
"""
import logging
from datetime import datetime
from typing import List, Dict, Set, Optional
from functools import wraps

logger = logging.getLogger(__name__)


ROLES = {
    "viewer": {"backup.read","restore.read","failover.read","incident.read","drill.read","config.read","monitoring.read","audit.read"},
    "operator": {"backup.read","backup.create","restore.read","restore.create","failover.read","incident.read","incident.create","incident.update","drill.read","config.read","monitoring.read","audit.read"},
    "responder": {"backup.read","backup.create","restore.read","restore.create","restore.approve","restore.execute","failover.read","failover.execute","incident.read","incident.create","incident.update","incident.close","drill.read","drill.schedule","config.read","monitoring.read","monitoring.configure","audit.read"},
    "admin": {"backup.read","backup.create","backup.delete","backup.policy.write","restore.read","restore.create","restore.approve","restore.execute","failover.read","failover.execute","failover.configure","incident.read","incident.create","incident.update","incident.close","drill.read","drill.schedule","drill.execute","config.read","config.write","security.read","monitoring.read","monitoring.configure","audit.read"},
    "superadmin": {"*"},
}

PERMISSION_DESCRIPTIONS = {
    "backup.read": "View backups", "backup.create": "Trigger backups", "backup.delete": "Delete backups",
    "restore.read": "View restores", "restore.create": "Request restore", "restore.approve": "Approve restore",
    "restore.execute": "Execute restore", "failover.read": "View failovers", "failover.execute": "Trigger failover",
    "incident.read": "View incidents", "incident.create": "Create incidents", "incident.close": "Close incidents",
    "drill.read": "View drills", "drill.schedule": "Schedule drills", "drill.execute": "Run drills",
    "config.read": "View config", "config.write": "Modify config", "security.read": "View security",
    "security.write": "Modify security", "audit.read": "View audit logs", "monitoring.read": "View monitoring",
    "monitoring.configure": "Configure monitoring",
}


class AccessController:
    """
    RBAC for the DR system with 5 roles: viewer/operator/responder/admin/superadmin.
    """

    def __init__(self, db_session=None, audit_logger=None):
        self.db = db_session
        self.audit_logger = audit_logger

    def can(self, role: str, permission: str) -> bool:
        """Check if a role has a specific permission."""
        role_perms = ROLES.get(role, set())
        return "*" in role_perms or permission in role_perms

    def check(self, user_role: str, permission: str, user_id: str = None, resource_id: str = None) -> dict:
        """Check permission with full audit logging."""
        allowed = self.can(user_role, permission)
        result = {"allowed": allowed, "user_role": user_role, "permission": permission,
                  "checked_at": datetime.utcnow().isoformat()}
        if self.audit_logger and user_id:
            self.audit_logger.log(actor_id=user_id, action=f"permission_check:{permission}",
                                   resource_id=resource_id, result="success" if allowed else "denied")
        if not allowed:
            logger.info(f"ACCESS DENIED: role={user_role} permission={permission} user={user_id}")
        return result

    def require_permission(self, permission: str):
        """Decorator to enforce permission."""
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                user = kwargs.get("user")
                if not user:
                    raise PermissionError(f"No user context for permission: {permission}")
                role = getattr(user, "role", "viewer")
                if not self.can(role, permission):
                    raise PermissionError(f"Permission denied: '{permission}' (role: {role})")
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    def get_role_permissions(self, role: str) -> List[str]:
        """Get all permissions for a role."""
        perms = ROLES.get(role, set())
        if "*" in perms: return list(PERMISSION_DESCRIPTIONS.keys())
        return list(perms)

    def get_user_accessible_resources(self, role: str) -> Dict[str, List[str]]:
        """Get resources accessible to a role."""
        resources: Dict[str, List[str]] = {}
        for perm in self.get_role_permissions(role):
            if "." in perm:
                resource, _, action = perm.partition(".")
                resources.setdefault(resource, []).append(action)
        return resources

    def list_roles(self) -> List[dict]:
        """List all roles."""
        return [{"name": r, "permission_count": len(self.get_role_permissions(r)),
                 "is_superadmin": "*" in ROLES.get(r, set())} for r in ROLES]

    def validate_role(self, role: str) -> bool:
        return role in ROLES


_instance = AccessController()

def get_access_controller() -> AccessController:
    return _instance
