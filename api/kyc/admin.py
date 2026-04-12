# api/kyc/admin.py
"""
[SECURE] KYC Admin - Complete & Beautiful Design
With colorful badges, progress bars, and beautiful UI
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.contrib import messages
from django.db.models import Count, Q
from .models import KYC, KYCVerificationLog, KYCSubmission
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


# ==================== DEFENSIVE UTILITIES ====================

class SafeDisplay:
    """Safe display utilities - null safe"""
    
    @staticmethod
    def val(v, default='-'):
        try:
            return str(v) if v is not None else default
        except Exception:
            return default
    
    @staticmethod
    def truncate(text, length=50):
        try:
            if not text:
                return '-'
            return text[:length] + '...' if len(text) > length else text
        except Exception:
            return '-'


def badge(text, color, icon='', bg_color=None):
    """Beautiful badge generator"""
    bg = bg_color or color
    return format_html(
        '<span style="background: {}; color: white; padding: 4px 12px; '
        'border-radius: 20px; font-size: 11px; font-weight: 600; '
        'box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: inline-flex; '
        'align-items: center; gap: 4px;">{} {}</span>',
        bg, icon, str(text).upper()
    )


def gradient_badge(text, color1, color2, icon=''):
    """Gradient badge"""
    return format_html(
        '<span style="background: linear-gradient(135deg, {}, {}); color: white; '
        'padding: 5px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; '
        'box-shadow: 0 3px 6px rgba(0,0,0,0.15); display: inline-flex; '
        'align-items: center; gap: 5px;">{} {}</span>',
        color1, color2, icon, str(text).upper()
    )


def status_badge(status):
    """Status badge with colors"""
    status_config = {
        'not_submitted': ('#9E9E9E', '[NOTE]'),
        'pending': ('#FF9800', '⏳'),
        'verified': ('#4CAF50', '[OK]'),
        'rejected': ('#F44336', '[ERROR]'),
        'expired': ('#607D8B', '⌛'),
    }
    color, icon = status_config.get(status, ('#9E9E9E', '❓'))
    return badge(status.replace('_', ' ').title(), color, icon)


def doc_type_badge(doc_type):
    """Document type badge"""
    doc_config = {
        'nid': ('#2196F3', '🆔'),
        'passport': ('#4CAF50', '📘'),
        'driving_license': ('#FF9800', '🚗'),
    }
    color, icon = doc_config.get(doc_type, ('#9E9E9E', '[DOC]'))
    return badge(doc_type.replace('_', ' ').title(), color, icon)


def bool_icon(value, true_icon='[OK]', false_icon='[ERROR]'):
    """Boolean icon display"""
    return true_icon if value else false_icon


def time_ago(dt):
    """Human readable time ago"""
    if not dt:
        return '-'
    try:
        delta = timezone.now() - dt
        if delta.days > 365:
            return f"{delta.days // 365}y ago"
        if delta.days > 30:
            return f"{delta.days // 30}mo ago"
        if delta.days > 0:
            return f"{delta.days}d ago"
        if delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        if delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        return "just now"
    except Exception:
        return '-'


def progress_bar(value, max_value=100, width=80):
    """Progress bar HTML"""
    try:
        if max_value <= 0:
            return '-'
        percentage = min(100, int((value / max_value) * 100))
        color = '#4CAF50' if percentage >= 75 else '#FF9800' if percentage >= 50 else '#F44336'
        return format_html(
            '<div style="width: {}px; background: #f0f0f0; border-radius: 10px; overflow: hidden;">'
            '<div style="width: {}%; background: linear-gradient(90deg, {}, {}); height: 18px; '
            'text-align: center; color: white; font-size: 10px; line-height: 18px; font-weight: bold;">'
            '{}%</div></div>',
            width, percentage, color, '#81C784', percentage
        )
    except Exception:
        return '-'


# ==================== KYC ADMIN ====================
@admin.register(KYC)
class KYCAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'full_name_col', 'status_badge',
        'doc_type_badge', 'verification_progress', 'risk_score_display',
        'submitted_ago', 'expiry_status', 'actions_column'
    ]
    
    list_filter = [
        'status', 'document_type', 'is_duplicate',
        'is_name_verified', 'is_phone_verified', 'is_payment_verified',
        'created_at', 'verified_at'
    ]
    
    search_fields = [
        'user__username', 'user__email', 'full_name',
        'document_number', 'phone_number', 'payment_number'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'verified_at', 'expires_at',
        'reviewed_at', 'ocr_confidence', 'risk_score', 'risk_factors',
        'user_details', 'document_preview', 'selfie_preview'
    ]
    
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('👤 User Information', {
            'fields': ('user_details', 'full_name', 'date_of_birth', 'phone_number')
        }),
        ('💳 Payment Details', {
            'fields': ('payment_method', 'payment_number')
        }),
        ('📍 Address', {
            'fields': ('address_line', 'city', 'country'),
            'classes': ('collapse',)
        }),
        ('[DOC] Document Information', {
            'fields': (
                'document_type', 'document_number',
                ('document_front', 'document_back'),
                'selfie_photo'
            )
        }),
        ('🔍 Verification Status', {
            'fields': (
                'status_badge',
                ('is_name_verified', 'is_phone_verified', 'is_payment_verified', 'is_face_verified')
            )
        }),
        ('[STATS] OCR Data', {
            'fields': ('extracted_name', 'extracted_dob', 'extracted_nid', 'ocr_confidence'),
            'classes': ('collapse',)
        }),
        ('[WARN] Risk Assessment', {
            'fields': ('risk_score_display', 'risk_factors', 'is_duplicate', 'duplicate_of'),
            'classes': ('collapse',)
        }),
        ('👨‍⚖️ Admin Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'rejection_reason', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('📅 Timestamps', {
            'fields': ('created_at', 'updated_at', 'verified_at', 'expires_at'),
            'classes': ('collapse',)
        }),
        ('🖼️ Document Preview', {
            'fields': ('document_preview', 'selfie_preview'),
            'classes': ('collapse',)
        }),
    )
    
    # ============ LIST DISPLAY METHODS ============
    
    def user_link(self, obj):
        try:
            url = reverse('admin:users_user_change', args=[obj.user.id])
        except Exception:
            return format_html('<span style="color: #667eea;">👤 {}</span>', obj.user.username)
        return format_html(
            '<a href="{}" style="color: #667eea; font-weight: 500; text-decoration: none;">'
            '<span style="display: flex; align-items: center; gap: 4px;">'
            '<span style="font-size: 14px;">👤</span> {}</span></a>',
            url, obj.user.username
        )
    user_link.short_description = 'User'
    
    def full_name_col(self, obj):
        verified_icon = '[OK]' if obj.is_name_verified else '[ERROR]'
        return format_html(
            '<span style="color: #333; font-weight: 500;">{} {}</span>',
            verified_icon, SafeDisplay.truncate(obj.full_name, 30)
        )
    full_name_col.short_description = 'Full Name'
    
    def status_badge(self, obj):
        return status_badge(obj.status)
    status_badge.short_description = 'Status'
    
    def doc_type_badge(self, obj):
        if obj.document_type:
            return doc_type_badge(obj.document_type)
        return format_html('<span style="color: #999;">-</span>')
    doc_type_badge.short_description = 'Document'
    
    def verification_progress(self, obj):
        verified = sum([
            obj.is_name_verified,
            obj.is_phone_verified,
            obj.is_payment_verified,
            obj.is_face_verified
        ])
        return format_html(
            '<span style="background: #9C27B0; color: white; padding: 4px 10px; '
            'border-radius: 12px;">{}/4</span>',
            verified
        )
    verification_progress.short_description = 'Progress'
    
    def risk_score_display(self, obj):
        score = obj.risk_score
        if score >= 70:
            color = '#F44336'
            icon = '🔴'
        elif score >= 40:
            color = '#FF9800'
            icon = '🟠'
        else:
            color = '#4CAF50'
            icon = '🟢'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, score
        )
    risk_score_display.short_description = 'Risk'
    
    def submitted_ago(self, obj):
        return time_ago(obj.created_at)
    submitted_ago.short_description = 'Submitted'
    
    def expiry_status(self, obj):
        if obj.expires_at:
            if obj.expires_at > timezone.now():
                days_left = (obj.expires_at - timezone.now()).days
                return format_html(
                    '<span style="color: #4CAF50;">{} days left</span>',
                    days_left
                )
            return badge('Expired', '#F44336', '⌛')
        return '-'
    expiry_status.short_description = 'Expiry'
    
    def actions_column(self, obj):
        try:
            url = reverse('admin:kyc_kyc_change', args=[obj.id])
            return format_html(
                '<div style="display: flex; gap: 5px;">'
                '<a href="{}" style="background: #2196F3; color: white; padding: 4px 8px; '
                'border-radius: 4px; text-decoration: none; font-size: 11px;">👁️ View</a>'
                '<a href="{}" style="background: #4CAF50; color: white; padding: 4px 8px; '
                'border-radius: 4px; text-decoration: none; font-size: 11px;">✏️ Edit</a>'
                '</div>',
                url, url
            )
        except Exception:
            return format_html('<span style="color:#999;">-</span>')
    actions_column.short_description = 'Actions'
    
    # ============ READONLY FIELDS ============
    
    def user_details(self, obj):
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
            '<p><strong>Username:</strong> {}</p>'
            '<p><strong>Email:</strong> {}</p>'
            '<p><strong>Joined:</strong> {}</p>'
            '</div>',
            obj.user.username,
            obj.user.email,
            obj.user.date_joined.strftime('%Y-%m-%d') if obj.user.date_joined else '-'
        )
    user_details.short_description = 'User Details'
    
    def document_preview(self, obj):
        html = '<div style="display: flex; gap: 10px;">'
        if obj.document_front:
            html += format_html(
                '<div><strong>Front:</strong><br><img src="{}" style="max-width: 200px; max-height: 150px; border: 1px solid #ddd; border-radius: 5px;"></div>',
                obj.document_front.url
            )
        if obj.document_back:
            html += format_html(
                '<div><strong>Back:</strong><br><img src="{}" style="max-width: 200px; max-height: 150px; border: 1px solid #ddd; border-radius: 5px;"></div>',
                obj.document_back.url
            )
        html += '</div>'
        return format_html(html)
    document_preview.short_description = 'Document Preview'
    
    def selfie_preview(self, obj):
        if obj.selfie_photo:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 150px; border: 2px solid #667eea; border-radius: 10px;">',
                obj.selfie_photo.url
            )
        return '-'
    selfie_preview.short_description = 'Selfie Preview'
    
    # ============ ACTIONS ============
    
    actions = [
        'approve_kyc', 'reject_kyc', 'mark_as_pending',
        'calculate_risk', 'check_duplicates', 'export_kyc_csv'
    ]
    
    def approve_kyc(self, request, queryset):
        count = 0
        for kyc in queryset.filter(status__in=['pending', 'not_submitted']):
            kyc.approve(request.user)
            count += 1
            
            # Log the action
            KYCVerificationLog.objects.create(
                kyc=kyc,
                action='approved',
                performed_by=request.user,
                details=f'KYC approved by {request.user.username}'
            )
        
        self.message_user(request, f'[OK] {count} KYC records approved')
    approve_kyc.short_description = "[OK] Approve selected KYC"
    
    def reject_kyc(self, request, queryset):
        from django import forms
        
        class RejectForm(forms.Form):
            reason = forms.CharField(widget=forms.Textarea, required=True)
        
        if 'apply' in request.POST:
            form = RejectForm(request.POST)
            if form.is_valid():
                reason = form.cleaned_data['reason']
                count = 0
                for kyc in queryset:
                    kyc.reject(reason, request.user)
                    count += 1
                    
                    KYCVerificationLog.objects.create(
                        kyc=kyc,
                        action='rejected',
                        performed_by=request.user,
                        details=f'Rejected: {reason}'
                    )
                
                self.message_user(request, f'[ERROR] {count} KYC records rejected')
                return
            
        form = RejectForm(initial={'_selected_action': request.POST.getlist(admin.ACTION_CHECKBOX_NAME)})
        return self.render_rejection_form(request, form, queryset)
    reject_kyc.short_description = "[ERROR] Reject selected KYC"
    
    def render_rejection_form(self, request, form, queryset):
        return admin.ModelAdmin.render_rejection_form(request, form, queryset)
    
    def mark_as_pending(self, request, queryset):
        count = queryset.update(status='pending')
        self.message_user(request, f'⏳ {count} KYC records marked as pending')
    mark_as_pending.short_description = "⏳ Mark as pending"
    
    def calculate_risk(self, request, queryset):
        count = 0
        for kyc in queryset:
            kyc.calculate_risk_score()
            count += 1
        self.message_user(request, f'[STATS] Risk scores calculated for {count} records')
    calculate_risk.short_description = "[STATS] Calculate risk scores"
    
    def check_duplicates(self, request, queryset):
        from .services import KYCService
        count = 0
        for kyc in queryset:
            if KYCService.check_duplicate_kyc(kyc):
                count += 1
        self.message_user(request, f'🔍 Found {count} duplicate KYC records')
    check_duplicates.short_description = "🔍 Check duplicates"
    
    def export_kyc_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="kyc_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'User', 'Full Name', 'Phone', 'Status', 'Document Type',
            'Document Number', 'Risk Score', 'Submitted At', 'Verified At'
        ])
        
        for kyc in queryset:
            writer.writerow([
                kyc.user.username,
                kyc.full_name,
                kyc.phone_number,
                kyc.get_status_display(),
                kyc.get_document_type_display() if kyc.document_type else '',
                kyc.document_number,
                kyc.risk_score,
                kyc.created_at.strftime('%Y-%m-%d %H:%M'),
                kyc.verified_at.strftime('%Y-%m-%d %H:%M') if kyc.verified_at else ''
            ])
        
        return response
    export_kyc_csv.short_description = "📥 Export as CSV"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'reviewed_by')


# ==================== KYC VERIFICATION LOG ADMIN ====================
@admin.register(KYCVerificationLog)
class KYCVerificationLogAdmin(admin.ModelAdmin):
    list_display = [
        'kyc_link', 'action_badge', 'performed_by_display',
        'details_short', 'created_ago'
    ]
    
    list_filter = ['action', 'created_at']
    search_fields = ['kyc__user__username', 'details']
    readonly_fields = ['created_at']
    list_per_page = 100
    
    def kyc_link(self, obj):
        try:
            url = reverse('admin:kyc_kyc_change', args=[obj.kyc.id])
            return format_html('<a href="{}" style="color: #667eea;">KYC #{}</a>', url, obj.kyc.id)
        except Exception:
            return format_html('<span style="color: #667eea;">KYC #{}</span>', obj.kyc.id)
    kyc_link.short_description = 'KYC'
    
    def action_badge(self, obj):
        action_config = {
            'approved': ('#4CAF50', '[OK]'),
            'rejected': ('#F44336', '[ERROR]'),
            'pending': ('#FF9800', '⏳'),
            'phone_verified': ('#2196F3', '📱'),
            'submitted': ('#9C27B0', '📤'),
        }
        color, icon = action_config.get(obj.action, ('#9E9E9E', '[NOTE]'))
        return badge(obj.action, color, icon)
    action_badge.short_description = 'Action'
    
    def performed_by_display(self, obj):
        if obj.performed_by:
            return obj.performed_by.username
        return format_html('<span style="color: #999;">System</span>')
    performed_by_display.short_description = 'Performed By'
    
    def details_short(self, obj):
        return SafeDisplay.truncate(obj.details, 50)
    details_short.short_description = 'Details'
    
    def created_ago(self, obj):
        return time_ago(obj.created_at)
    created_ago.short_description = 'Time'
    
    def has_add_permission(self, request):
        return False


# ==================== KYC SUBMISSION ADMIN ====================
@admin.register(KYCSubmission)
class KYCSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "user_link",
        "document_type",
        "document_number",
        "status_badge",
        "verification_progress",
        "face_liveness_badge",
        "clarity_score",
        "matching_score",
        "submitted_at",
    ]
    list_filter = ["status", "document_type", "face_liveness_check", "submitted_at"]
    search_fields = ["user__username", "user__email", "document_number"]
    list_per_page = 50

    readonly_fields = [
        "created_at",
        "updated_at",
        "image_clarity_score",
        "document_matching_score",
    ]

    fieldsets = (
        ("👤 User", {"fields": ("user",)}),
        ("[DOC] Document", {"fields": ("document_type", "document_number", "nid_front", "nid_back")}),
        ("🪪 Selfie + Note", {"fields": ("selfie_with_note",)}),
        ("🔍 Fraud & Scores (computed)", {"fields": ("image_clarity_score", "document_matching_score", "face_liveness_check")}),
        ("✅ Verification Workflow", {"fields": ("status", "verification_progress", "rejection_reason")}),
        ("📅 Timestamps", {"fields": ("created_at", "updated_at", "submitted_at")}),
    )

    def user_link(self, obj):
        try:
            try:
                url = reverse("admin:users_user_change", args=[obj.user.id])
            except Exception:
                return format_html('<span style="color:#667eea;">👤 {}</span>', obj.user.username)
            return format_html(
                '<a href="{}" style="color:#667eea; font-weight:600; text-decoration:none;">👤 {}</a>',
                url,
                obj.user.username,
            )
        except Exception:
            return "-"

    user_link.short_description = "User"

    def status_badge(self, obj):
        return status_badge(obj.status)

    status_badge.short_description = "Status"

    def face_liveness_badge(self, obj):
        cfg = {
            "pending": ("#FF9800", "⏳"),
            "success": ("#4CAF50", "[OK]"),
            "failure": ("#F44336", "[FAIL]"),
        }
        color, icon = cfg.get(obj.face_liveness_check, ("#9E9E9E", "[?]"))
        return badge(obj.face_liveness_check.replace("_", " ").title(), color, icon)

    face_liveness_badge.short_description = "Liveness"

    def clarity_score(self, obj):
        return format_html('<span style="font-weight:700;">{}</span>', obj.image_clarity_score)

    clarity_score.short_description = "Clarity"

    def matching_score(self, obj):
        return format_html('<span style="font-weight:700;">{}</span>', obj.document_matching_score)

    matching_score.short_description = "Matching"



# ==================== DASHBOARD WIDGET ====================
class KYCDashboard:
    """KYC Dashboard Widgets"""
    
    @staticmethod
    def get_stats():
        """Get KYC statistics"""
        total = KYC.objects.count()
        pending = KYC.objects.filter(status='pending').count()
        verified = KYC.objects.filter(status='verified').count()
        rejected = KYC.objects.filter(status='rejected').count()
        duplicate = KYC.objects.filter(is_duplicate=True).count()
        
        return {
            'total': total,
            'pending': pending,
            'verified': verified,
            'rejected': rejected,
            'duplicate': duplicate,
            'completion_rate': (verified / total * 100) if total > 0 else 0,
        }
    
    @staticmethod
    def get_recent_activity(limit=10):
        """Get recent KYC activity"""
        return KYCVerificationLog.objects.select_related('kyc', 'performed_by')[:limit]
    
    @staticmethod
    def get_pending_review():
        """Get KYC pending review"""
        return KYC.objects.filter(status='pending').select_related('user')[:20]


# ==================== FORCE REGISTER ALL MODELS ====================
try:
    from django.contrib import admin
    from .models import KYC, KYCVerificationLog
    
    registered = 0
    
    # Register KYC
    if not admin.site.is_registered(KYC):
        admin.site.register(KYC, KYCAdmin)
        registered += 1
        print("[OK] Registered: KYC")
    else:
        print("⏩ Already registered: KYC")
    
    # Register KYCVerificationLog
    if not admin.site.is_registered(KYCVerificationLog):
        admin.site.register(KYCVerificationLog, KYCVerificationLogAdmin)
        registered += 1
        print("[OK] Registered: KYCVerificationLog")
    else:
        print("⏩ Already registered: KYCVerificationLog")
    
    if registered > 0:
        print(f"[OK][OK][OK] {registered} KYC models registered successfully!")
    else:
        print("[OK] All KYC models already registered")
        
except Exception as e:
    print(f"[ERROR] Error registering KYC models: {e}")


# ==================== ADMIN SITE CUSTOMIZATION ====================
admin.site.site_header = '[SECURE] Earning Platform - KYC Management'
admin.site.site_title = 'KYC Admin'
admin.site.index_title = 'Welcome to KYC Management Center'

def _force_register_kyc():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(KYC, KYCAdmin), (KYCVerificationLog, KYCVerificationLogAdmin), (KYCSubmission, KYCSubmissionAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] kyc registered {registered} models")
    except Exception as e:
        print(f"[WARN] kyc: {e}")

# ==================== AUTO REGISTER ALL NEW MODELS ====================
from django.contrib import admin
from . import models as kyc_models
import inspect

_ALREADY_REGISTERED = {KYC, KYCVerificationLog, KYCSubmission}

_new_models = [
    obj for name, obj in inspect.getmembers(kyc_models, inspect.isclass)
    if hasattr(obj, '_meta') 
    and obj._meta.app_label == 'kyc'
    and obj not in _ALREADY_REGISTERED
]

for _model in _new_models:
    try:
        if not admin.site.is_registered(_model):
            admin.site.register(_model)
            print(f"[OK] Registered: {_model.__name__}")
    except Exception as _e:
        print(f"[WARN] Could not register {_model.__name__}: {_e}")
