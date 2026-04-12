# =============================================================================
# api/promotions/permissions.py
# DRF Permission Classes — Role-based & Object-level Access Control
# =============================================================================

from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.request import Request
from django.utils.translation import gettext_lazy as _

from .models import Campaign, TaskSubmission, Dispute, Blacklist
from .choices import CampaignStatus, SubmissionStatus


# ─── Role Helpers ─────────────────────────────────────────────────────────────

def _is_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def _is_authenticated_worker(user) -> bool:
    return bool(user and user.is_authenticated and not user.is_staff)


def _is_advertiser(user) -> bool:
    """Advertiser group বা is_advertiser flag — আপনার User model অনুযায়ী adjust করুন।"""
    return bool(
        user and
        user.is_authenticated and
        (hasattr(user, 'is_advertiser') and user.is_advertiser)
    )


# ─── General Permissions ──────────────────────────────────────────────────────

class IsAdminUser(BasePermission):
    """শুধুমাত্র is_staff বা is_superuser।"""
    message = _('শুধুমাত্র admin এই action করতে পারবেন।')

    def has_permission(self, request: Request, view) -> bool:
        return _is_admin(request.user)


class IsWorker(BasePermission):
    """Authenticated non-admin user — Worker।"""
    message = _('এই endpoint শুধুমাত্র worker দের জন্য।')

    def has_permission(self, request: Request, view) -> bool:
        return _is_authenticated_worker(request.user)


class IsAdvertiser(BasePermission):
    """Advertiser role সহ authenticated user।"""
    message = _('এই endpoint শুধুমাত্র advertiser দের জন্য।')

    def has_permission(self, request: Request, view) -> bool:
        return _is_advertiser(request.user)


class IsAdminOrReadOnly(BasePermission):
    """GET/HEAD/OPTIONS সবাই, বাকি শুধু admin।"""
    message = _('এই পরিবর্তন শুধুমাত্র admin করতে পারবেন।')

    def has_permission(self, request: Request, view) -> bool:
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return _is_admin(request.user)


class IsAuthenticatedOrReadOnly(BasePermission):
    """Public read, authenticated write।"""
    def has_permission(self, request: Request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


# ─── Campaign Permissions ─────────────────────────────────────────────────────

class IsCampaignOwnerOrAdmin(BasePermission):
    """Campaign owner (advertiser) অথবা admin।"""
    message = _('শুধুমাত্র campaign এর advertiser বা admin এই action করতে পারবেন।')

    def has_permission(self, request: Request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view, obj: Campaign) -> bool:
        if _is_admin(request.user):
            return True
        return obj.advertiser_id == request.user.pk


class CanCreateCampaign(BasePermission):
    """Campaign তৈরি করার permission।"""
    message = _('Campaign তৈরি করতে advertiser account প্রয়োজন।')

    def has_permission(self, request: Request, view) -> bool:
        return bool(
            request.user and
            request.user.is_authenticated and
            (
                _is_admin(request.user) or
                _is_advertiser(request.user)
            )
        )


class CanViewCampaignDetails(BasePermission):
    """Active campaign সবাই দেখতে পারবে। Draft/Cancelled শুধু owner/admin।"""
    message = _('এই campaign দেখার অনুমতি নেই।')

    def has_permission(self, request: Request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view, obj: Campaign) -> bool:
        if _is_admin(request.user):
            return True
        if obj.advertiser_id == request.user.pk:
            return True
        # Active campaign যেকেউ দেখতে পারবে
        return obj.status == CampaignStatus.ACTIVE and not obj.is_deleted


# ─── Submission Permissions ───────────────────────────────────────────────────

class IsSubmissionOwnerOrAdmin(BasePermission):
    """Submission এর owner বা admin।"""
    message = _('এই submission এ access করার অনুমতি নেই।')

    def has_permission(self, request: Request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view, obj: TaskSubmission) -> bool:
        if _is_admin(request.user):
            return True
        return obj.worker_id == request.user.pk


class CanReviewSubmission(BasePermission):
    """Submission review করার permission — শুধু admin।"""
    message = _('Submission review করার অনুমতি নেই।')

    def has_permission(self, request: Request, view) -> bool:
        return _is_admin(request.user)

    def has_object_permission(self, request: Request, view, obj: TaskSubmission) -> bool:
        # ইতিমধ্যে reviewed submission আবার review করা যাবে না
        return obj.status == SubmissionStatus.PENDING


class CanSubmitTask(BasePermission):
    """Task submit করার permission — blacklist ও reputation check।"""
    message = _('আপনি বর্তমানে কোনো task submit করতে পারবেন না।')

    def has_permission(self, request: Request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if _is_admin(request.user):
            return False  # Admin নিজে কাজ করবেন না
        # IP blacklist check
        ip = _get_client_ip(request)
        if ip and Blacklist.is_blacklisted('ip', ip):
            self.message = _('আপনার IP address নিষিদ্ধ করা হয়েছে।')
            return False
        # User blacklist check
        if Blacklist.is_blacklisted('user', str(request.user.pk)):
            self.message = _('আপনার account নিষিদ্ধ করা হয়েছে।')
            return False
        return True


# ─── Dispute Permissions ──────────────────────────────────────────────────────

class IsDisputeOwnerOrAdmin(BasePermission):
    """Dispute এর owner (worker) বা admin।"""
    message = _('এই dispute এ access করার অনুমতি নেই।')

    def has_permission(self, request: Request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view, obj: Dispute) -> bool:
        if _is_admin(request.user):
            return True
        return obj.worker_id == request.user.pk


class CanResolveDispute(BasePermission):
    """Dispute resolve করার permission — শুধু admin।"""
    message = _('Dispute resolve করার অনুমতি শুধুমাত্র admin এর আছে।')

    def has_permission(self, request: Request, view) -> bool:
        return _is_admin(request.user)


# ─── Finance Permissions ──────────────────────────────────────────────────────

class CanViewFinancialData(BasePermission):
    """নিজের financial data বা admin।"""
    message = _('এই financial data দেখার অনুমতি নেই।')

    def has_permission(self, request: Request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view, obj) -> bool:
        if _is_admin(request.user):
            return True
        # obj তে user_id বা advertiser_id থাকলে check করো
        user_id = getattr(obj, 'user_id', None) or getattr(obj, 'advertiser_id', None)
        return user_id == request.user.pk


class CanManageBlacklist(BasePermission):
    """Blacklist manage করার permission — শুধু admin।"""
    message = _('Blacklist manage করার অনুমতি নেই।')

    def has_permission(self, request: Request, view) -> bool:
        return _is_admin(request.user)


class CanViewAnalytics(BasePermission):
    """Analytics দেখার permission — campaign owner বা admin।"""
    message = _('এই analytics দেখার অনুমতি নেই।')

    def has_permission(self, request: Request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view, obj) -> bool:
        if _is_admin(request.user):
            return True
        campaign = getattr(obj, 'campaign', None)
        if campaign:
            return campaign.advertiser_id == request.user.pk
        return False


# ─── Utility ──────────────────────────────────────────────────────────────────

def _get_client_ip(request: Request) -> str | None:
    """Request থেকে real IP বের করে।"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
