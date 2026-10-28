"""
Backup Module Permissions
Django permission classes for backup operations
"""

from rest_framework import permissions
from django.contrib.auth.models import User, Group
from .models import Backup, BackupRestoration, BackupSchedule
from .exceptions import InsufficientPermissionsException


class IsBackupAdmin(permissions.BasePermission):
    """
    Permission class to check if user has backup admin privileges
    Allows users to create, restore, and manage backups
    """
    
    def has_permission(self, request, view):
        """
        Check if user has backup admin permission
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check for backup admin group
        return self._is_backup_admin(request.user)
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user has permission for specific object
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        # For backup admin, object-level permission is same as view-level
        return self.has_permission(request, view)
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanDownloadBackup(permissions.BasePermission):
    """
    Permission class to check if user can download backup files
    More restrictive than backup admin - allows only viewing/downloading
    """
    
    def has_permission(self, request, view):
        """
        Check if user has download permission
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check for backup admin group (they can download)
        if self._is_backup_admin(request.user):
            return True
        
        # Check for backup viewer group
        if self._is_backup_viewer(request.user):
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can download specific backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Backup model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Backup admins can download any backup
        if self._is_backup_admin(request.user):
            return True
        
        # Backup viewers can download their own backups or backups they created
        if self._is_backup_viewer(request.user):
            return self._can_access_backup(request.user, obj)
        
        return False
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False
    
    def _is_backup_viewer(self, user):
        """Check if user is in backup viewer group"""
        try:
            backup_viewer_group = Group.objects.get(name='backup_viewer')
            return backup_viewer_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False
    
    def _can_access_backup(self, user, backup):
        """Check if user can access specific backup"""
        # User can access backups they created
        if backup.created_by and backup.created_by.id == user.id:
            return True
        
        # User can access backups for databases they have access to
        # This would need to be implemented based on your database permission system
        return False


class CanCreateBackup(permissions.BasePermission):
    """
    Permission class to check if user can create backups
    """
    
    def has_permission(self, request, view):
        """
        Check if user can create backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Only backup admins can create backups
        return self._is_backup_admin(request.user)
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanRestoreBackup(permissions.BasePermission):
    """
    Permission class to check if user can restore backups
    """
    
    def has_permission(self, request, view):
        """
        Check if user can restore backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Only backup admins can restore backups
        return self._is_backup_admin(request.user)
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can restore specific backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Backup model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Only backup admins can restore backups
        if not self._is_backup_admin(request.user):
            return False
        
        # Additional check: backup must be in completed status
        if hasattr(obj, 'status') and obj.status != 'completed':
            return False
        
        return True
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanDeleteBackup(permissions.BasePermission):
    """
    Permission class to check if user can delete backups
    """
    
    def has_permission(self, request, view):
        """
        Check if user can delete backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Only backup admins can delete backups
        return self._is_backup_admin(request.user)
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can delete specific backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Backup model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Only backup admins can delete backups
        if not self._is_backup_admin(request.user):
            return False
        
        # Additional check: cannot delete backups that are currently being used
        if hasattr(obj, 'status'):
            active_statuses = ['running', 'restoring', 'verifying']
            if obj.status in active_statuses:
                return False
        
        return True
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanManageSchedule(permissions.BasePermission):
    """
    Permission class to check if user can manage backup schedules
    """
    
    def has_permission(self, request, view):
        """
        Check if user can manage backup schedules
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Only backup admins can manage schedules
        return self._is_backup_admin(request.user)
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can manage specific schedule
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: BackupSchedule model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        # For schedule management, object-level permission is same as view-level
        return self.has_permission(request, view)
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class IsOwnerOrStaff(permissions.BasePermission):
    """
    Permission class to check if user is object owner or staff
    Used for backup viewing and basic operations
    """
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user is owner or staff
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Staff users have access
        if request.user.is_staff:
            return True
        
        # Check if user is the owner
        if hasattr(obj, 'created_by') and obj.created_by:
            return obj.created_by.id == request.user.id
        
        # Check if user initiated the operation
        if hasattr(obj, 'initiated_by') and obj.initiated_by:
            return obj.initiated_by.id == request.user.id
        
        return False


class CanViewBackupLogs(permissions.BasePermission):
    """
    Permission class to check if user can view backup logs
    """
    
    def has_permission(self, request, view):
        """
        Check if user can view backup logs
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Backup admins can view logs
        if self._is_backup_admin(request.user):
            return True
        
        # Staff users can view logs
        if request.user.is_staff:
            return True
        
        return False
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class TenantBackupPermission(permissions.BasePermission):
    """
    Permission class for multi-tenant backup access
    Ensures users can only access backups from their own tenant
    """
    
    def has_permission(self, request, view):
        """
        Check if user has basic permission for tenant backup operations
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers can access all tenants
        if request.user.is_superuser:
            return True
        
        # Check if user has tenant context
        if hasattr(request, 'tenant') and request.tenant:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can access backup object from their tenant
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers can access all tenants
        if request.user.is_superuser:
            return True
        
        # Check if object belongs to user's tenant
        if hasattr(obj, 'tenant') and obj.tenant:
            if hasattr(request, 'tenant') and request.tenant:
                return obj.tenant.id == request.tenant.id
        
        return False


def check_backup_permission(user, permission_type, backup=None):
    """
    Helper function to check backup permissions outside of DRF context
    
    Args:
        user: Django User instance
        permission_type: Type of permission to check
        backup: Backup model instance (optional)
        
    Returns:
        bool: True if user has permission, False otherwise
        
    Raises:
        InsufficientPermissionsException: If permission check fails
    """
    if not user or not user.is_authenticated:
        raise InsufficientPermissionsException(
            "User must be authenticated",
            user_id=user.id if user else None,
            required_permission=permission_type
        )
    
    # Superusers always have permission
    if user.is_superuser:
        return True
    
    # Check specific permission types
    if permission_type == 'backup_admin':
        if not _is_backup_admin(user):
            raise InsufficientPermissionsException(
                "User does not have backup admin privileges",
                user_id=user.id,
                required_permission='backup_admin'
            )
    
    elif permission_type == 'download_backup':
        if not _can_download_backup(user, backup):
            raise InsufficientPermissionsException(
                "User does not have permission to download this backup",
                user_id=user.id,
                required_permission='download_backup',
                resource=f'backup_{backup.id}' if backup else None
            )
    
    elif permission_type == 'create_backup':
        if not _is_backup_admin(user):
            raise InsufficientPermissionsException(
                "User does not have permission to create backups",
                user_id=user.id,
                required_permission='create_backup'
            )
    
    elif permission_type == 'restore_backup':
        if not _is_backup_admin(user):
            raise InsufficientPermissionsException(
                "User does not have permission to restore backups",
                user_id=user.id,
                required_permission='restore_backup'
            )
    
    elif permission_type == 'delete_backup':
        if not _is_backup_admin(user):
            raise InsufficientPermissionsException(
                "User does not have permission to delete backups",
                user_id=user.id,
                required_permission='delete_backup'
            )
    
    elif permission_type == 'manage_schedule':
        if not _is_backup_admin(user):
            raise InsufficientPermissionsException(
                "User does not have permission to manage backup schedules",
                user_id=user.id,
                required_permission='manage_schedule'
            )
    
    else:
        raise InsufficientPermissionsException(
            f"Unknown permission type: {permission_type}",
            user_id=user.id,
            required_permission=permission_type
        )
    
    return True


def _is_backup_admin(user):
    """Check if user is in backup admin group"""
    try:
        backup_admin_group = Group.objects.get(name='backup_admin')
        return backup_admin_group.user_set.filter(id=user.id).exists()
    except Group.DoesNotExist:
        return False


def _can_download_backup(user, backup):
    """Check if user can download specific backup"""
    if not backup:
        return False
    
    # Backup admins can download any backup
    if _is_backup_admin(user):
        return True
    
    # Check if user is backup viewer
    try:
        backup_viewer_group = Group.objects.get(name='backup_viewer')
        if backup_viewer_group.user_set.filter(id=user.id).exists():
            # User can download backups they created
            if backup.created_by and backup.created_by.id == user.id:
                return True
    except Group.DoesNotExist:
        pass
    
    return False


class CanVerifyBackup(permissions.BasePermission):
    """
    Permission class to check if user can verify backups
    """
    
    def has_permission(self, request, view):
        """
        Check if user can verify backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Backup admins can verify backups
        if self._is_backup_admin(request.user):
            return True
        
        # Staff users can verify backups
        if request.user.is_staff:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can verify specific backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Backup model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Backup admins can verify any backup
        if self._is_backup_admin(request.user):
            return True
        
        # Staff users can verify backups they created
        if request.user.is_staff:
            if hasattr(obj, 'created_by') and obj.created_by:
                return obj.created_by.id == request.user.id
        
        return False
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanManageStorage(permissions.BasePermission):
    """
    Permission class to check if user can manage backup storage locations
    """
    
    def has_permission(self, request, view):
        """
        Check if user can manage storage locations
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Only backup admins can manage storage
        return self._is_backup_admin(request.user)
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can manage specific storage location
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: BackupStorageLocation model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        # For storage management, object-level permission is same as view-level
        return self.has_permission(request, view)
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanManageAlerts(permissions.BasePermission):
    """
    Permission class to check if user can manage backup alerts
    """
    
    def has_permission(self, request, view):
        """
        Check if user can manage alerts
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Backup admins can manage alerts
        if self._is_backup_admin(request.user):
            return True
        
        # Staff users can view alerts
        if request.user.is_staff:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can manage specific alert
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: BackupAlert model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Backup admins can manage any alert
        if self._is_backup_admin(request.user):
            return True
        
        # Staff users can view alerts but only resolve their own
        if request.user.is_staff:
            if request.method in ['GET', 'HEAD', 'OPTIONS']:
                return True
            elif hasattr(obj, 'resolved_by'):
                # Allow resolving alerts they created
                return not obj.resolved_by or obj.resolved_by.id == request.user.id
        
        return False
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanManageRetention(permissions.BasePermission):
    """
    Permission class to check if user can manage retention policies
    """
    
    def has_permission(self, request, view):
        """
        Check if user can manage retention policies
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Only backup admins can manage retention policies
        return self._is_backup_admin(request.user)
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can manage specific retention policy
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: RetentionPolicy model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        # For retention policy management, object-level permission is same as view-level
        return self.has_permission(request, view)
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanAccessBackupAPI(permissions.BasePermission):
    """
    Permission class to check if user can access backup API endpoints
    """
    
    def has_permission(self, request, view):
        """
        Check if user can access backup API
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check for backup admin or viewer groups
        if self._is_backup_admin(request.user):
            return True
        
        if self._is_backup_viewer(request.user):
            return True
        
        # Staff users have read access
        if request.user.is_staff and request.method in permissions.SAFE_METHODS:
            return True
        
        return False
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False
    
    def _is_backup_viewer(self, user):
        """Check if user is in backup viewer group"""
        try:
            backup_viewer_group = Group.objects.get(name='backup_viewer')
            return backup_viewer_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class CanManageNotifications(permissions.BasePermission):
    """
    Permission class to check if user can manage backup notifications
    """
    
    def has_permission(self, request, view):
        """
        Check if user can manage notifications
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Backup admins can manage notifications
        if self._is_backup_admin(request.user):
            return True
        
        # Staff users can view notifications
        if request.user.is_staff:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can manage specific notification config
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: BackupNotificationConfig model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Backup admins can manage any notification config
        if self._is_backup_admin(request.user):
            return True
        
        # Staff users can manage notification configs they created
        if request.user.is_staff:
            if hasattr(obj, 'created_by') and obj.created_by:
                return obj.created_by.id == request.user.id
        
        return False
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


class TimeBasedBackupPermission(permissions.BasePermission):
    """
    Permission class that checks time-based access restrictions
    """
    
    def __init__(self, allowed_hours=None, allowed_days=None):
        """
        Initialize time-based permission
        
        Args:
            allowed_hours: List of allowed hours (0-23)
            allowed_days: List of allowed days (0-6, Monday=0)
        """
        self.allowed_hours = allowed_hours or list(range(24))  # All hours by default
        self.allowed_days = allowed_days or list(range(7))    # All days by default
    
    def has_permission(self, request, view):
        """
        Check if current time is within allowed time window
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if within allowed time, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers bypass time restrictions
        if request.user.is_superuser:
            return True
        
        from django.utils import timezone
        now = timezone.now()
        
        # Check hour restriction
        if now.hour not in self.allowed_hours:
            return False
        
        # Check day restriction
        if now.weekday() not in self.allowed_days:
            return False
        
        return True


class DatabaseSpecificBackupPermission(permissions.BasePermission):
    """
    Permission class for database-specific backup access
    """
    
    def has_permission(self, request, view):
        """
        Check if user has basic database backup permission
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check for database-specific permissions
        return self._has_database_permission(request.user)
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can access specific database backup
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Backup model instance
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check if user has permission for this specific database
        if hasattr(obj, 'database_name'):
            return self._can_access_database(request.user, obj.database_name)
        
        return False
    
    def _has_database_permission(self, user):
        """Check if user has any database backup permissions"""
        # This would integrate with your database permission system
        # For now, check if user is backup admin or staff
        if user.is_staff:
            return True
        
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False
    
    def _can_access_database(self, user, database_name):
        """Check if user can access specific database"""
        # This would integrate with your database permission system
        # For now, backup admins and staff can access all databases
        if user.is_superuser or user.is_staff:
            return True
        
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            if backup_admin_group.user_set.filter(id=user.id).exists():
                return True
        except Group.DoesNotExist:
            pass
        
        return False


class BackupOperationPermission(permissions.BasePermission):
    """
    Permission class that checks if backup operation is allowed
    based on system state and user permissions
    """
    
    def has_permission(self, request, view):
        """
        Check if backup operation is allowed
        
        Args:
            request: HTTP request object
            view: DRF view instance
            
        Returns:
            bool: True if operation is allowed, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check if system is in maintenance mode
        if self._is_maintenance_mode():
            return False
        
        # Check if user has backup admin permission
        if self._is_backup_admin(request.user):
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Check if operation on specific backup is allowed
        
        Args:
            request: HTTP request object
            view: DRF view instance
            obj: Backup model instance
            
        Returns:
            bool: True if operation is allowed, False otherwise
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers always have access
        if request.user.is_superuser:
            return True
        
        # Check if backup is in a state that allows operations
        if hasattr(obj, 'status'):
            restricted_statuses = ['running', 'restoring', 'verifying']
            if obj.status in restricted_statuses:
                # Only backup admins can operate on restricted backups
                return self._is_backup_admin(request.user)
        
        return self.has_permission(request, view)
    
    def _is_maintenance_mode(self):
        """Check if system is in maintenance mode"""
        from django.core.cache import cache
        return cache.get('backup_maintenance_mode', False)
    
    def _is_backup_admin(self, user):
        """Check if user is in backup admin group"""
        try:
            backup_admin_group = Group.objects.get(name='backup_admin')
            return backup_admin_group.user_set.filter(id=user.id).exists()
        except Group.DoesNotExist:
            return False


# Additional helper functions for permission checking
def has_backup_group_permission(user, group_name):
    """
    Check if user belongs to specific backup group
    
    Args:
        user: Django User instance
        group_name: Name of the group to check
        
    Returns:
        bool: True if user is in group, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    try:
        group = Group.objects.get(name=group_name)
        return group.user_set.filter(id=user.id).exists()
    except Group.DoesNotExist:
        return False


def can_perform_backup_operation(user, operation, backup=None):
    """
    Check if user can perform specific backup operation
    
    Args:
        user: Django User instance
        operation: Operation type (create, restore, delete, download, verify)
        backup: Backup model instance (optional)
        
    Returns:
        bool: True if user can perform operation, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superusers can perform any operation
    if user.is_superuser:
        return True
    
    # Check operation-specific permissions
    if operation in ['create', 'restore', 'delete', 'manage_schedule', 'manage_storage', 'manage_retention']:
        return has_backup_group_permission(user, 'backup_admin')
    
    elif operation in ['download', 'view']:
        if has_backup_group_permission(user, 'backup_admin'):
            return True
        if has_backup_group_permission(user, 'backup_viewer'):
            if backup and backup.created_by and backup.created_by.id == user.id:
                return True
        return user.is_staff
    
    elif operation in ['verify']:
        return has_backup_group_permission(user, 'backup_admin') or user.is_staff
    
    return False


def get_user_backup_permissions(user):
    """
    Get all backup permissions for a user
    
    Args:
        user: Django User instance
        
    Returns:
        dict: Dictionary of user's backup permissions
    """
    if not user or not user.is_authenticated:
        return {}
    
    permissions = {
        'is_superadmin': user.is_superuser,
        'is_staff': user.is_staff,
        'is_backup_admin': has_backup_group_permission(user, 'backup_admin'),
        'is_backup_viewer': has_backup_group_permission(user, 'backup_viewer'),
        'can_create': can_perform_backup_operation(user, 'create'),
        'can_restore': can_perform_backup_operation(user, 'restore'),
        'can_delete': can_perform_backup_operation(user, 'delete'),
        'can_download': can_perform_backup_operation(user, 'download'),
        'can_verify': can_perform_backup_operation(user, 'verify'),
        'can_view': can_perform_backup_operation(user, 'view'),
        'can_manage_schedule': can_perform_backup_operation(user, 'manage_schedule'),
        'can_manage_storage': can_perform_backup_operation(user, 'manage_storage'),
        'can_manage_retention': can_perform_backup_operation(user, 'manage_retention'),
    }
    
    return permissions
