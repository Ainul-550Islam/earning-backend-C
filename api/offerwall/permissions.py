"""
api/offerwall/permissions.py

DRF Permission classes for offerwall module.
Provides 5 granular permission strategies:
  1. IsOfferProvider — user can only manage their own provider's offers
  2. IsOfferAdmin — staff-only permission for offer management
  3. IsConversionApprover — finance/operations team can approve conversions
  4. IsPublisher — user can manage their own content locks
  5. IsOwnerOrAdmin — object owner or admin can modify
"""

from rest_framework.permissions import BasePermission, IsAuthenticated, IsAdminUser


class IsOfferProvider(BasePermission):
    """
    Permission for offer providers.
    Allow provider to manage offers for their own provider account.
    
    - Providers can list/retrieve all offers
    - Providers can only create offers for their own provider
    - Providers can only update/delete their own provider's offers
    - Admins bypass this check
    """
    message = "You can only manage offers for your own provider account."
    
    def has_permission(self, request, view):
        # Allow listing and retrieving
        if request.method in ['GET']:
            return True
        
        # For create/update/delete, user must be authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin always allowed
        if request.user.is_staff:
            return True
        
        # For non-safe methods, user must own the provider
        if request.method not in ['GET']:
            # Check if user is associated with this provider
            # Assumes offer.provider has a user/owner field
            if hasattr(obj, 'provider'):
                return obj.provider.created_by == request.user
            return False
        
        return True


class IsOfferAdmin(IsAdminUser):
    """
    Permission for admin-only offer operations.
    Only staff/admin users can perform sensitive operations:
    - Approve conversions
    - Suspend offers
    - Modify payout amounts
    - Change offer status
    
    Inherits from IsAdminUser (is_staff=True required)
    """
    message = "Only administrators can perform this action."


class IsConversionApprover(BasePermission):
    """
    Permission for conversion approval operations.
    Only users with specific groups/roles can approve conversions:
    - Staff users
    - Members of 'conversion_approvers' group
    - Members of 'finance_team' group
    
    This prevents regular users from approving their own conversions.
    """
    message = "You don't have permission to approve conversions."
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        # Admin always allowed
        if request.user.is_staff:
            return True
        
        # Check for specific groups
        allowed_groups = ['conversion_approvers', 'finance_team', 'finance_admin']
        return request.user.groups.filter(name__in=allowed_groups).exists()
    
    def has_object_permission(self, request, view, obj):
        # Admin allowed
        if request.user.is_staff:
            return True
        
        # User cannot approve their own conversion
        if obj.user == request.user:
            return False
        
        # Check group membership
        allowed_groups = ['conversion_approvers', 'finance_team', 'finance_admin']
        return request.user.groups.filter(name__in=allowed_groups).exists()


class IsPublisher(BasePermission):
    """
    Permission for publisher content management.
    Publishers can manage their own content locks and embed tokens.
    
    - Publish can list their own content locks
    - Publishers can only modify their own locks
    - Admins can manage any publisher's locks
    """
    message = "You can only manage your own published content."
    
    def has_permission(self, request, view):
        # Allow listing
        if request.method == 'GET':
            return request.user and request.user.is_authenticated
        
        # For modifications, must be authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin always allowed
        if request.user.is_staff:
            return True
        
        # User can only access their own content locks
        if hasattr(obj, 'publisher'):
            return obj.publisher == request.user
        
        return False


class IsOwnerOrAdmin(BasePermission):
    """
    Permission that allows object owner or admin to edit it.
    Generic permission for user-owned objects.
    
    - Owner can view/edit/delete their own object
    - Admin can view/edit/delete any object
    - Anonymous users cannot access
    """
    message = "You don't have permission to modify this object."
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin always allowed
        if request.user.is_staff:
            return True
        
        # Safe methods (GET, HEAD, OPTIONS) allowed for authenticated users
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # For modifications, check ownership
        # Try multiple ownership patterns
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False
