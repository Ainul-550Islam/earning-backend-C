# engagement/viewset_cap.py
"""
Capability-based viewsets for engagement system.
Provides viewsets with different capability levels.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .permissions import IsTenantMember, IsActiveUser
from .decorators import engagement_endpoint, rate_limit
from .exceptions import EngagementError


class BaseCapabilityViewSet(viewsets.GenericViewSet):
    """Base viewset with capability management."""
    
    capability_levels = {
        'read': 1,
        'write': 2,
        'admin': 3,
        'superadmin': 4
    }
    
    def get_capability_level(self, user):
        """Get user's capability level."""
        if user.is_superuser:
            return self.capability_levels['superadmin']
        elif user.is_staff:
            return self.capability_levels['admin']
        elif hasattr(user, 'tenant_role') and user.tenant_role in ['admin', 'owner']:
            return self.capability_levels['admin']
        else:
            return self.capability_levels['write']
    
    def check_capability(self, required_level):
        """Check if user has required capability level."""
        user_level = self.get_capability_level(self.request.user)
        return user_level >= required_level
    
    def get_queryset(self):
        """Get queryset based on capabilities."""
        queryset = super().get_queryset()
        
        # Filter by tenant
        if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            queryset = queryset.filter(tenant=self.request.user.tenant)
        
        # Non-admin users can only see their own data
        if not self.check_capability(self.capability_levels['admin']):
            if hasattr(queryset.model, 'user'):
                queryset = queryset.filter(user=self.request.user)
        
        return queryset


class ReadOnlyCapabilityViewSet(BaseCapabilityViewSet):
    """Read-only viewset with basic capabilities."""
    
    permission_classes = [IsAuthenticated, IsActiveUser, IsTenantMember]
    
    def list(self, request, *args, **kwargs):
        """List objects - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Insufficient capabilities'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve object - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Insufficient capabilities'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().retrieve(request, *args, **kwargs)


class WriteCapabilityViewSet(ReadOnlyCapabilityViewSet):
    """Write-enabled viewset with extended capabilities."""
    
    def create(self, request, *args, **kwargs):
        """Create object - write capability required."""
        if not self.check_capability(self.capability_levels['write']):
            return Response(
                {'error': 'Insufficient capabilities'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update object - write capability required."""
        if not self.check_capability(self.capability_levels['write']):
            return Response(
                {'error': 'Insufficient capabilities'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update object - write capability required."""
        if not self.check_capability(self.capability_levels['write']):
            return Response(
                {'error': 'Insufficient capabilities'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete object - write capability required."""
        if not self.check_capability(self.capability_levels['write']):
            return Response(
                {'error': 'Insufficient capabilities'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)


class AdminCapabilityViewSet(WriteCapabilityViewSet):
    """Admin-enabled viewset with full capabilities."""
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create objects - admin capability required."""
        if not self.check_capability(self.capability_levels['admin']):
            return Response(
                {'error': 'Admin capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement bulk create logic
        return Response({'message': 'Bulk create implemented'})
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """Bulk update objects - admin capability required."""
        if not self.check_capability(self.capability_levels['admin']):
            return Response(
                {'error': 'Admin capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement bulk update logic
        return Response({'message': 'Bulk update implemented'})
    
    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete objects - admin capability required."""
        if not self.check_capability(self.capability_levels['admin']):
            return Response(
                {'error': 'Admin capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement bulk delete logic
        return Response({'message': 'Bulk delete implemented'})
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export data - admin capability required."""
        if not self.check_capability(self.capability_levels['admin']):
            return Response(
                {'error': 'Admin capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement export logic
        return Response({'message': 'Export implemented'})
    
    @action(detail=False, methods=['post'])
    def import_data(self, request):
        """Import data - admin capability required."""
        if not self.check_capability(self.capability_levels['admin']):
            return Response(
                {'error': 'Admin capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement import logic
        return Response({'message': 'Import implemented'})


class SuperAdminCapabilityViewSet(AdminCapabilityViewSet):
    """Super admin viewset with system-level capabilities."""
    
    @action(detail=False, methods=['post'])
    def system_maintenance(self, request):
        """System maintenance - superadmin capability required."""
        if not self.check_capability(self.capability_levels['superadmin']):
            return Response(
                {'error': 'Superadmin capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement system maintenance logic
        return Response({'message': 'System maintenance implemented'})
    
    @action(detail=False, methods=['post'])
    def system_backup(self, request):
        """System backup - superadmin capability required."""
        if not self.check_capability(self.capability_levels['superadmin']):
            return Response(
                {'error': 'Superadmin capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement system backup logic
        return Response({'message': 'System backup implemented'})
    
    @action(detail=False, methods=['post'])
    def system_restore(self, request):
        """System restore - superadmin capability required."""
        if not self.check_capability(self.capability_levels['superadmin']):
            return Response(
                {'error': 'Superadmin capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement system restore logic
        return Response({'message': 'System restore implemented'})


# ── Capability Mixins ─────────────────────────────────────────────────────

class CapabilityMixin:
    """Mixin for adding capability checks to viewsets."""
    
    def get_serializer_class(self):
        """Get serializer class based on capabilities."""
        if self.check_capability(self.capability_levels['admin']):
            return self.admin_serializer_class
        return self.serializer_class
    
    def get_permissions(self):
        """Get permissions based on capabilities."""
        permissions = super().get_permissions()
        
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if not self.check_capability(self.capability_levels['write']):
                permissions.append('rest_framework.permissions.IsAdminUser')
        
        return permissions


class TenantCapabilityMixin(CapabilityMixin):
    """Mixin for tenant-aware capability checks."""
    
    def get_queryset(self):
        """Get queryset with tenant filtering."""
        queryset = super().get_queryset()
        
        # Filter by tenant if user is not superadmin
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'tenant') and self.request.user.tenant:
                queryset = queryset.filter(tenant=self.request.user.tenant)
        
        return queryset


class UserCapabilityMixin(CapabilityMixin):
    """Mixin for user-aware capability checks."""
    
    def get_queryset(self):
        """Get queryset with user filtering."""
        queryset = super().get_queryset()
        
        # Non-admin users can only see their own data
        if not self.check_capability(self.capability_levels['admin']):
            if hasattr(queryset.model, 'user'):
                queryset = queryset.filter(user=self.request.user)
        
        return queryset


# ── Specific Capability Viewsets ─────────────────────────────────────────────

class CheckInCapabilityViewSet(WriteCapabilityViewSet):
    """Check-in viewset with capability management."""
    
    @action(detail=False, methods=['post'])
    def checkin(self, request):
        """Perform check-in - write capability required."""
        if not self.check_capability(self.capability_levels['write']):
            return Response(
                {'error': 'Write capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement check-in logic
        return Response({'message': 'Check-in implemented'})
    
    @action(detail=False, methods=['get'])
    def streak_info(self, request):
        """Get streak information - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Read capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement streak info logic
        return Response({'message': 'Streak info implemented'})


class SpinWheelCapabilityViewSet(WriteCapabilityViewSet):
    """Spin wheel viewset with capability management."""
    
    @action(detail=False, methods=['post'])
    def spin(self, request):
        """Perform spin - write capability required."""
        if not self.check_capability(self.capability_levels['write']):
            return Response(
                {'error': 'Write capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement spin logic
        return Response({'message': 'Spin implemented'})
    
    @action(detail=False, methods=['get'])
    def remaining_spins(self, request):
        """Get remaining spins - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Read capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement remaining spins logic
        return Response({'message': 'Remaining spins implemented'})


class QuestCapabilityViewSet(WriteCapabilityViewSet):
    """Quest viewset with capability management."""
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete quest - write capability required."""
        if not self.check_capability(self.capability_levels['write']):
            return Response(
                {'error': 'Write capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement quest completion logic
        return Response({'message': 'Quest completion implemented'})
    
    @action(detail=False, methods=['get'])
    def available_quests(self, request):
        """Get available quests - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Read capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement available quests logic
        return Response({'message': 'Available quests implemented'})


class AchievementCapabilityViewSet(ReadOnlyCapabilityViewSet):
    """Achievement viewset with capability management."""
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get achievement progress - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Read capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement achievement progress logic
        return Response({'message': 'Achievement progress implemented'})


class ShopCapabilityViewSet(WriteCapabilityViewSet):
    """Shop viewset with capability management."""
    
    @action(detail=True, methods=['post'])
    def purchase(self, request, pk=None):
        """Purchase item - write capability required."""
        if not self.check_capability(self.capability_levels['write']):
            return Response(
                {'error': 'Write capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement purchase logic
        return Response({'message': 'Purchase implemented'})
    
    @action(detail=False, methods=['get'])
    def inventory(self, request):
        """Get user inventory - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Read capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement inventory logic
        return Response({'message': 'Inventory implemented'})


class LeaderboardCapabilityViewSet(ReadOnlyCapabilityViewSet):
    """Leaderboard viewset with capability management."""
    
    @action(detail=False, methods=['get'])
    def top_players(self, request):
        """Get top players - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Read capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement top players logic
        return Response({'message': 'Top players implemented'})
    
    @action(detail=False, methods=['get'])
    def user_rank(self, request):
        """Get user rank - read capability required."""
        if not self.check_capability(self.capability_levels['read']):
            return Response(
                {'error': 'Read capabilities required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Implement user rank logic
        return Response({'message': 'User rank implemented'})


# ── Capability Utilities ───────────────────────────────────────────────────

class CapabilityChecker:
    """Utility class for checking capabilities."""
    
    @staticmethod
    def can_read(user, obj=None):
        """Check if user can read object."""
        if user.is_superuser:
            return True
        
        if hasattr(user, 'tenant') and user.tenant:
            if obj and hasattr(obj, 'tenant'):
                return obj.tenant == user.tenant
        
        return False
    
    @staticmethod
    def can_write(user, obj=None):
        """Check if user can write object."""
        if user.is_superuser or user.is_staff:
            return True
        
        if hasattr(user, 'tenant_role') and user.tenant_role in ['admin', 'owner']:
            return True
        
        if obj and hasattr(obj, 'user'):
            return obj.user == user
        
        return False
    
    @staticmethod
    def can_admin(user, obj=None):
        """Check if user can admin object."""
        return user.is_superuser or user.is_staff
    
    @staticmethod
    def can_superadmin(user):
        """Check if user is superadmin."""
        return user.is_superuser


def require_capability(capability_level):
    """Decorator to require specific capability level."""
    def decorator(view_func):
        def wrapper(viewset, request, *args, **kwargs):
            if not viewset.check_capability(capability_level):
                return Response(
                    {'error': 'Insufficient capabilities'},
                    status=status.HTTP_403_FORBIDDEN
                )
            return view_func(viewset, request, *args, **kwargs)
        return wrapper
    return decorator


def require_read_capability(view_func):
    """Decorator to require read capability."""
    return require_capability(BaseCapabilityViewSet.capability_levels['read'])(view_func)


def require_write_capability(view_func):
    """Decorator to require write capability."""
    return require_capability(BaseCapabilityViewSet.capability_levels['write'])(view_func)


def require_admin_capability(view_func):
    """Decorator to require admin capability."""
    return require_capability(BaseCapabilityViewSet.capability_levels['admin'])(view_func)


def require_superadmin_capability(view_func):
    """Decorator to require superadmin capability."""
    return require_capability(BaseCapabilityViewSet.capability_levels['superadmin'])(view_func)


# ── Capability Configuration ─────────────────────────────────────────────────

CAPABILITY_CONFIG = {
    'default_levels': {
        'read': 1,
        'write': 2,
        'admin': 3,
        'superadmin': 4
    },
    'user_roles': {
        'user': 2,
        'moderator': 2,
        'admin': 3,
        'owner': 3,
        'superadmin': 4
    },
    'tenant_roles': {
        'member': 2,
        'officer': 3,
        'admin': 3,
        'owner': 3
    }
}


def get_user_capability_level(user):
    """Get capability level for user."""
    if user.is_superuser:
        return CAPABILITY_CONFIG['default_levels']['superadmin']
    
    if user.is_staff:
        return CAPABILITY_CONFIG['default_levels']['admin']
    
    if hasattr(user, 'tenant_role'):
        role_level = CAPABILITY_CONFIG['tenant_roles'].get(user.tenant_role, 2)
        return role_level
    
    return CAPABILITY_CONFIG['default_levels']['write']
