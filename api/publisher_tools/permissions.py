# api/publisher_tools/permissions.py
"""
Publisher Tools — Custom DRF Permission classes।
"""
from rest_framework.permissions import BasePermission, IsAuthenticated
from django.utils.translation import gettext_lazy as _


class IsPublisher(BasePermission):
    """
    User-এর publisher profile আছে এবং active কিনা চেক করে।
    """
    message = _('You must have an active publisher account to perform this action.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            pub = request.user.publisher_profile
            return pub.status == 'active'
        except Exception:
            return False


class IsPublisherOwner(BasePermission):
    """
    Object-এর publisher == request.user.publisher_profile কিনা চেক করে।
    """
    message = _('You do not have permission to access this resource.')

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            publisher = request.user.publisher_profile
            # Check if object has publisher field
            if hasattr(obj, 'publisher'):
                return obj.publisher == publisher
            # If obj IS the publisher
            if hasattr(obj, 'user'):
                return obj.user == request.user
            return False
        except Exception:
            return False


class IsPublisherOrReadOnly(BasePermission):
    """
    Read: সবার জন্য। Write: শুধু active publisher-দের জন্য।
    """
    message = _('You must be an active publisher to modify this resource.')

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            pub = request.user.publisher_profile
            return pub.status == 'active'
        except Exception:
            return False


class IsVerifiedPublisher(BasePermission):
    """
    KYC verified publisher কিনা চেক করে।
    """
    message = _('KYC verification is required to perform this action.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            pub = request.user.publisher_profile
            return pub.is_kyc_verified and pub.status == 'active'
        except Exception:
            return False


class IsPremiumPublisher(BasePermission):
    """
    Premium বা Enterprise tier publisher কিনা চেক করে।
    """
    message = _('This feature requires a Premium or Enterprise publisher account.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            pub = request.user.publisher_profile
            return pub.tier in ('premium', 'enterprise') and pub.status == 'active'
        except Exception:
            return False


class IsEnterprisePublisher(BasePermission):
    """
    Enterprise tier publisher কিনা চেক করে।
    """
    message = _('This feature requires an Enterprise publisher account.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            pub = request.user.publisher_profile
            return pub.tier == 'enterprise' and pub.status == 'active'
        except Exception:
            return False


class CanManageAdUnit(BasePermission):
    """
    AdUnit-এর publisher owner কিনা চেক করে।
    """
    message = _('You do not have permission to manage this ad unit.')

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            publisher = request.user.publisher_profile
            return obj.publisher == publisher
        except Exception:
            return False


class CanManageSite(BasePermission):
    """
    Site-এর publisher owner কিনা চেক করে।
    """
    message = _('You do not have permission to manage this site.')

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            publisher = request.user.publisher_profile
            return obj.publisher == publisher
        except Exception:
            return False


class CanManageApp(BasePermission):
    """
    App-এর publisher owner কিনা চেক করে।
    """
    message = _('You do not have permission to manage this app.')

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            publisher = request.user.publisher_profile
            return obj.publisher == publisher
        except Exception:
            return False


class CanViewEarnings(BasePermission):
    """
    Publisher নিজের earnings দেখতে পারবে।
    Staff সবার earnings দেখতে পারবে।
    """
    message = _('You do not have permission to view these earnings.')

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_staff or hasattr(request.user, 'publisher_profile')

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        try:
            publisher = request.user.publisher_profile
            return obj.publisher == publisher
        except Exception:
            return False


class IsAdminOrPublisher(BasePermission):
    """
    Admin সবকিছু করতে পারবে, Publisher শুধু নিজেরটা।
    """
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or hasattr(request.user, 'publisher_profile'))
        )

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        try:
            publisher = request.user.publisher_profile
            if hasattr(obj, 'publisher'):
                return obj.publisher == publisher
            if hasattr(obj, 'user'):
                return obj.user == request.user
            return False
        except Exception:
            return False
