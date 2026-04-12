# users/admin.py
"""
Beautiful & Bulletproof Admin Panel for Users App
- Defensive coding principles
- Graceful error handling  
- Null-safe operations
- Beautiful colorful design
- Models matched exactly with models.py
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db.models import Count, Sum, Avg
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

# ==================== UNREGISTER USER IF ALREADY REGISTERED ====================
try:
    if admin.site.is_registered(User):
        admin.site.unregister(User)
except Exception:
    pass

# ==================== IMPORT ALL MODELS (DEFENSIVE) ====================
try:
    from .models import (
        User, OTP, LoginHistory, UserActivity, UserDevice,
        DeviceFingerprint, IPReputation, UserAccountLink, UserBehavior,
        FraudDetectionLog, RiskScoreHistory, RateLimitTracker,
        KYCVerification, UserLevel, NotificationSettings, SecuritySettings,
        UserStatistics, UserPreferences, UserProfile, UserRank
    )
    MODELS_LOADED = True
except ImportError as e:
    logger.error(f"Error importing models: {e}")
    MODELS_LOADED = False


# ==================== DEFENSIVE SAFE DISPLAY ====================
class S:
    """Safe display utilities - null safe"""

    @staticmethod
    def val(v, default='-'):
        try:
            return escape(str(v)) if v is not None else default
        except Exception:
            return default

    @staticmethod
    def num(v, default=0):
        try:
            return int(v) if v is not None else default
        except Exception:
            return default

    @staticmethod
    def dec(v, default='0.00'):
        try:
            return f"{float(v):.2f}" if v is not None else default
        except Exception:
            return default


# ==================== BADGE HELPER FUNCTIONS ====================

def badge(text, color, icon=''):
    """Generic colorful badge"""
    try:
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 12px; '
            'border-radius: 15px; font-size: 11px; font-weight: bold; '
            'box-shadow: 0 2px 4px rgba(0,0,0,0.15); display: inline-block;">'
            '{} {}</span>',
            color, icon, escape(str(text))
        )
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def gradient_badge(text, color1, color2, icon=''):
    """Gradient colorful badge"""
    try:
        return format_html(
            '<span style="background: linear-gradient(135deg, {}, {}); color: white; '
            'padding: 5px 14px; border-radius: 18px; font-size: 11px; font-weight: bold; '
            'box-shadow: 0 2px 5px rgba(0,0,0,0.2); display: inline-block;">'
            '{} {}</span>',
            color1, color2, icon, escape(str(text))
        )
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def bool_badge(value, true_text='Yes', false_text='No',
               true_icon='[OK]', false_icon='[ERROR]',
               true_color='#4CAF50', false_color='#F44336'):
    """Boolean status badge"""
    try:
        if value:
            return gradient_badge(true_text, true_color, '#81C784', true_icon)
        return gradient_badge(false_text, false_color, '#EF9A9A', false_icon)
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def money_badge(amount, currency='৳'):
    """Money display badge"""
    try:
        amt = float(amount) if amount is not None else 0
        color = '#4CAF50' if amt > 0 else '#9E9E9E'
        return format_html(
            '<span style="background: linear-gradient(135deg, {}, {}); color: white; '
            'padding: 5px 12px; border-radius: 14px; font-weight: bold; font-size: 12px; '
            'font-family: monospace; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">'
            '[MONEY] {}{}</span>',
            color, '#A5D6A7' if amt > 0 else '#BDBDBD',
            currency, f"{amt:.2f}"
        )
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def score_badge(score, max_val=100):
    """Risk/Score badge with color based on value"""
    try:
        s = int(score) if score is not None else 0
        if s >= 70:
            c1, c2, icon = '#F44336', '#EF5350', '🔴'
        elif s >= 40:
            c1, c2, icon = '#FF9800', '#FFA726', '🟠'
        else:
            c1, c2, icon = '#4CAF50', '#66BB6A', '🟢'
        return format_html(
            '<span style="background: linear-gradient(135deg, {}, {}); color: white; '
            'padding: 5px 12px; border-radius: 14px; font-weight: bold; font-size: 12px; '
            'box-shadow: 0 2px 4px rgba(0,0,0,0.15);">{} {}/{}</span>',
            c1, c2, icon, s, max_val
        )
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def level_badge(level_name, colors_map):
    """Level/type badge from color map"""
    try:
        color = colors_map.get(str(level_name), '#9E9E9E')
        return badge(level_name, color)
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def progress_bar(current, total, color='#4CAF50'):
    """Progress bar HTML"""
    try:
        pct = min(100, int((int(current) / int(total)) * 100)) if int(total) > 0 else 100
        c = '#4CAF50' if pct >= 75 else '#FF9800' if pct >= 50 else '#F44336'
        return format_html(
            '<div style="width:120px; background:#e0e0e0; border-radius:10px; overflow:hidden;">'
            '<div style="width:{}%; background:linear-gradient(90deg,{},{}); height:18px; '
            'text-align:center; color:white; font-size:10px; line-height:18px; font-weight:bold;">'
            '{}%</div></div>',
            pct, c, '#A5D6A7', pct
        )
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def time_ago(dt):
    """Time ago display"""
    try:
        if not dt:
            return '-'
        delta = timezone.now() - dt
        if delta.days > 365:
            return f"{delta.days // 365}y ago"
        elif delta.days > 30:
            return f"{delta.days // 30}mo ago"
        elif delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        return "just now"
    except Exception:
        return '-'


# ==================== 1. USER ADMIN ====================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'account_id_col', 'username_col', 'email_col',
        'tier_col', 'role_col', 'balance_col',
        'status_col', 'verified_col', 'joined_col'
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'tier', 'role', 'is_verified', 'country')
    search_fields = ('username', 'email', 'referral_code', 'phone')
    readonly_fields = ('id', 'uid', 'last_login', 'created_at', 'updated_at', 'last_activity', 'referral_code')
    ordering = ('-created_at',)
    list_per_page = 30

    fieldsets = (
        ('[SECURE] Account Information', {
            'fields': ('id', 'uid', 'username', 'email', 'phone', 'password')
        }),
        ('[STAR] Role & Tier', {
            'fields': ('role', 'tier', 'is_verified', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('[MONEY] Financial', {
            'fields': ('balance', 'total_earned')
        }),
        ('👥 Referral', {
            'fields': ('referral_code', 'referred_by')
        }),
        ('🌍 Location & Device', {
            'fields': ('country', 'last_login_ip', 'avatar')
        }),
        ('📅 Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_activity', 'last_login')
        }),
        ('👮 Permissions', {
            'fields': ('groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        ('➕ Create New User', {
            'classes': ('wide',),
            'fields': ('username', 'email', 'phone', 'password1', 'password2', 'tier', 'role'),
        }),
    )

    actions = ['ban_users', 'unban_users', 'verify_users',
               'upgrade_bronze', 'upgrade_silver', 'upgrade_gold', 'upgrade_platinum']

    # ---- List Display Methods ----
    def account_id_col(self, obj):
        try:
            uid_short = str(obj.id)[:8] if obj.id else '?'
            return format_html(
                '<span style="background: linear-gradient(135deg, #667eea, #764ba2); '
                'color: white; padding: 4px 10px; border-radius: 12px; '
                'font-family: monospace; font-size: 11px; font-weight: bold;">#{}</span>',
                uid_short
            )
        except Exception as e:
            logger.error(f"account_id_col error: {e}")
            return '-'
    account_id_col.short_description = '🆔 ID'

    def username_col(self, obj):
        try:
            return format_html(
                '<strong style="color: #333; font-size: 13px;">👤 {}</strong>',
                escape(obj.username)
            )
        except Exception:
            return '-'
    username_col.short_description = '👤 Username'
    username_col.admin_order_field = 'username'

    def email_col(self, obj):
        try:
            return format_html(
                '<span style="color: #667eea; font-size: 12px;">✉️ {}</span>',
                escape(obj.email or '-')
            )
        except Exception:
            return '-'
    email_col.short_description = '✉️ Email'

    def tier_col(self, obj):
        try:
            colors = {
                'FREE': '#9E9E9E', 'BRONZE': '#CD7F32',
                'SILVER': '#9E9E9E', 'GOLD': '#FFC107', 'PLATINUM': '#607D8B'
            }
            icons = {
                'FREE': '🔘', 'BRONZE': '🥉',
                'SILVER': '🥈', 'GOLD': '🥇', 'PLATINUM': '💎'
            }
            tier = obj.tier or 'FREE'
            c = colors.get(tier, '#9E9E9E')
            ic = icons.get(tier, '🔘')
            return gradient_badge(tier, c, '#BDBDBD', ic)
        except Exception as e:
            logger.error(f"tier_col error: {e}")
            return '-'
    tier_col.short_description = '🏅 Tier'
    tier_col.admin_order_field = 'tier'

    def role_col(self, obj):
        try:
            colors = {'user': '#2196F3', 'admin': '#F44336', 'moderator': '#FF9800'}
            icons = {'user': '👤', 'admin': '👑', 'moderator': '🛡️'}
            role = obj.role or 'user'
            return gradient_badge(role.upper(), colors.get(role, '#9E9E9E'), '#90CAF9', icons.get(role, '👤'))
        except Exception as e:
            logger.error(f"role_col error: {e}")
            return '-'
    role_col.short_description = '🎭 Role'

    def balance_col(self, obj):
        try:
            return money_badge(obj.balance)
        except Exception:
            return '-'
    balance_col.short_description = '[MONEY] Balance'
    balance_col.admin_order_field = 'balance'

    def status_col(self, obj):
        try:
            if not obj.is_active:
                return gradient_badge('INACTIVE', '#9E9E9E', '#BDBDBD', '⚫')
            if obj.is_superuser:
                return gradient_badge('SUPERUSER', '#9C27B0', '#CE93D8', '👑')
            if obj.is_staff:
                return gradient_badge('STAFF', '#2196F3', '#90CAF9', '🛡️')
            return gradient_badge('ACTIVE', '#4CAF50', '#A5D6A7', '[OK]')
        except Exception as e:
            logger.error(f"status_col error: {e}")
            return '-'
    status_col.short_description = '[STATS] Status'

    def verified_col(self, obj):
        try:
            return bool_badge(
                obj.is_verified,
                'Verified', 'Unverified',
                '[OK]', '✖️',
                '#4CAF50', '#FF9800'
            )
        except Exception:
            return '-'
    verified_col.short_description = '[OK] Verified'

    def joined_col(self, obj):
        try:
            if not obj.created_at:
                return '-'
            return format_html(
                '<div style="text-align:center;">'
                '<div style="color:#666; font-size:11px;">📅 {}</div>'
                '<div style="color:#999; font-size:9px;">{}</div>'
                '</div>',
                obj.created_at.strftime('%Y-%m-%d'),
                time_ago(obj.created_at)
            )
        except Exception:
            return '-'
    joined_col.short_description = '📅 Joined'
    joined_col.admin_order_field = 'created_at'

    # ---- Actions ----
    def ban_users(self, request, queryset):
        try:
            count = queryset.update(is_active=False)
            self.message_user(request, format_html(
                '<span style="color:#F44336; font-weight:bold;">🚫 {} user(s) banned</span>', count))
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='ERROR')
    ban_users.short_description = '🚫 Ban selected users'

    def unban_users(self, request, queryset):
        try:
            count = queryset.update(is_active=True)
            self.message_user(request, format_html(
                '<span style="color:#4CAF50; font-weight:bold;">[OK] {} user(s) unbanned</span>', count))
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='ERROR')
    unban_users.short_description = '[OK] Unban selected users'

    def verify_users(self, request, queryset):
        try:
            count = queryset.update(is_verified=True)
            self.message_user(request, format_html(
                '<span style="color:#2196F3; font-weight:bold;">[OK] {} user(s) verified</span>', count))
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='ERROR')
    verify_users.short_description = '[OK] Verify selected users'

    def upgrade_bronze(self, request, queryset):
        queryset.update(tier='BRONZE')
        self.message_user(request, '🥉 Upgraded to Bronze')
    upgrade_bronze.short_description = '🥉 Upgrade to Bronze'

    def upgrade_silver(self, request, queryset):
        queryset.update(tier='SILVER')
        self.message_user(request, '🥈 Upgraded to Silver')
    upgrade_silver.short_description = '🥈 Upgrade to Silver'

    def upgrade_gold(self, request, queryset):
        queryset.update(tier='GOLD')
        self.message_user(request, '🥇 Upgraded to Gold')
    upgrade_gold.short_description = '🥇 Upgrade to Gold'

    def upgrade_platinum(self, request, queryset):
        queryset.update(tier='PLATINUM')
        self.message_user(request, '💎 Upgraded to Platinum')
    upgrade_platinum.short_description = '💎 Upgrade to Platinum'


# ==================== 2. OTP ADMIN ====================
@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'code_col', 'type_col', 'status_col', 'expires_col', 'created_col')
    list_filter = ('otp_type', 'is_used', 'created_at')
    search_fields = ('user__username', 'code')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 40

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def code_col(self, obj):
        try:
            return format_html(
                '<code style="background: linear-gradient(135deg, #6f42c1, #9C27B0); '
                'color: white; padding: 5px 12px; border-radius: 8px; '
                'font-size: 14px; letter-spacing: 3px; font-weight: bold;">{}</code>',
                escape(obj.code)
            )
        except Exception:
            return '-'
    code_col.short_description = '[KEY] OTP Code'

    def type_col(self, obj):
        try:
            colors = {
                'registration': '#4CAF50', 'login': '#2196F3',
                'password_reset': '#FF9800', 'phone_verify': '#00BCD4'
            }
            icons = {
                'registration': '[NOTE]', 'login': '[SECURE]',
                'password_reset': '[LOADING]', 'phone_verify': '📱'
            }
            t = obj.otp_type
            return gradient_badge(t.replace('_', ' ').title(),
                                  colors.get(t, '#9E9E9E'), '#90CAF9', icons.get(t, '📋'))
        except Exception:
            return '-'
    type_col.short_description = '📋 Type'

    def status_col(self, obj):
        try:
            return bool_badge(obj.is_used, 'Used', 'Active', '[OK]', '[LOADING]', '#9E9E9E', '#4CAF50')
        except Exception:
            return '-'
    status_col.short_description = '[STATS] Status'

    def expires_col(self, obj):
        try:
            if not obj.expires_at:
                return '-'
            now = timezone.now()
            expired = now > obj.expires_at
            color = '#F44336' if expired else '#4CAF50'
            label = '⌛ Expired' if expired else '[OK] Valid'
            return format_html(
                '<span style="color:{}; font-weight:bold; font-size:11px;">{}</span><br>'
                '<span style="color:#999; font-size:10px;">{}</span>',
                color, label, obj.expires_at.strftime('%H:%M %d-%m-%Y')
            )
        except Exception:
            return '-'
    expires_col.short_description = '⏰ Expires'

    def created_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:11px;">📅 {}</span>',
                               obj.created_at.strftime('%Y-%m-%d %H:%M') if obj.created_at else '-')
        except Exception:
            return '-'
    created_col.short_description = '📅 Created'

    def has_add_permission(self, request):
        return False


# ==================== 3. LOGIN HISTORY ADMIN ====================
@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'ip_col', 'device_col', 'location_col', 'status_col', 'time_col')
    list_filter = ('is_successful', 'created_at')
    search_fields = ('user__username', 'ip_address', 'location', 'device')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 40

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def ip_col(self, obj):
        try:
            return format_html(
                '<code style="background:#f5f5f5; padding:4px 8px; border-radius:5px; '
                'font-size:11px; color:#333; border:1px solid #ddd;">🌐 {}</code>',
                escape(str(obj.ip_address))
            )
        except Exception:
            return '-'
    ip_col.short_description = '🌐 IP Address'

    def device_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:12px;">📱 {}</span>',
                               escape(obj.device or 'Unknown'))
        except Exception:
            return '-'
    device_col.short_description = '📱 Device'

    def location_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:12px;">📍 {}</span>',
                               escape(obj.location or 'Unknown'))
        except Exception:
            return '-'
    location_col.short_description = '📍 Location'

    def status_col(self, obj):
        try:
            return bool_badge(obj.is_successful, 'Success', 'Failed', '[OK]', '[ERROR]', '#4CAF50', '#F44336')
        except Exception:
            return '-'
    status_col.short_description = '[STATS] Status'

    def time_col(self, obj):
        try:
            return format_html(
                '<div style="text-align:center;">'
                '<div style="color:#666; font-size:11px;">🕐 {}</div>'
                '<div style="color:#999; font-size:9px;">{}</div>'
                '</div>',
                obj.created_at.strftime('%Y-%m-%d %H:%M') if obj.created_at else '-',
                time_ago(obj.created_at)
            )
        except Exception:
            return '-'
    time_col.short_description = '🕐 Time'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== 4. USER ACTIVITY ADMIN ====================
@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'action_col', 'ip_col', 'time_col')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'action', 'ip_address')
    readonly_fields = ('user', 'action', 'description', 'ip_address', 'user_agent', 'timestamp')
    list_per_page = 50

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def action_col(self, obj):
        try:
            return format_html(
                '<span style="background:linear-gradient(135deg,#2196F3,#42A5F5); '
                'color:white; padding:4px 12px; border-radius:12px; '
                'font-size:11px; font-weight:bold;">⚡ {}</span>',
                escape(str(obj.action)[:40])
            )
        except Exception:
            return '-'
    action_col.short_description = '⚡ Action'

    def ip_col(self, obj):
        try:
            return format_html(
                '<code style="background:#f5f5f5; padding:3px 7px; '
                'border-radius:4px; font-size:11px;">🌐 {}</code>',
                escape(str(obj.ip_address or 'N/A'))
            )
        except Exception:
            return '-'
    ip_col.short_description = '🌐 IP'

    def time_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:11px;">🕐 {} <br><small>{}</small></span>',
                               obj.timestamp.strftime('%Y-%m-%d %H:%M') if obj.timestamp else '-',
                               time_ago(obj.timestamp))
        except Exception:
            return '-'
    time_col.short_description = '🕐 Time'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== 5. USER DEVICE ADMIN ====================
@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'device_name_col', 'device_type_col', 'status_col', 'created_col')
    list_filter = ('device_type', 'is_active', 'created_at')
    search_fields = ('user__username', 'device_id', 'device_name')
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def device_name_col(self, obj):
        try:
            return format_html('<strong style="color:#333;">📱 {}</strong>',
                               escape(obj.device_name or 'Unknown'))
        except Exception:
            return '-'
    device_name_col.short_description = '📱 Device Name'

    def device_type_col(self, obj):
        try:
            colors = {'android': '#4CAF50', 'ios': '#2196F3', 'web': '#FF9800'}
            icons = {'android': '🤖', 'ios': '🍎', 'web': '🌐'}
            dt = obj.device_type or 'web'
            return gradient_badge(dt.upper(), colors.get(dt, '#9E9E9E'), '#90CAF9', icons.get(dt, '📱'))
        except Exception:
            return '-'
    device_type_col.short_description = '📋 Type'

    def status_col(self, obj):
        try:
            return bool_badge(obj.is_active, 'Active', 'Inactive', '[OK]', '[ERROR]')
        except Exception:
            return '-'
    status_col.short_description = '[STATS] Status'

    def created_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:11px;">📅 {}</span>',
                               obj.created_at.strftime('%Y-%m-%d') if obj.created_at else '-')
        except Exception:
            return '-'
    created_col.short_description = '📅 Created'


# ==================== 6. DEVICE FINGERPRINT ADMIN ====================
@admin.register(DeviceFingerprint)
class DeviceFingerprintAdmin(admin.ModelAdmin):
    list_display = ('hash_col', 'platform_col', 'accounts_col', 'suspicious_col', 'blocked_col', 'last_seen_col')
    list_filter = ('is_suspicious', 'is_blocked', 'platform')
    search_fields = ('fingerprint_hash', 'user_agent')
    readonly_fields = ('fingerprint_hash', 'first_seen', 'last_seen')
    list_per_page = 30

    def hash_col(self, obj):
        try:
            return format_html(
                '<code style="background:linear-gradient(135deg,#455A64,#607D8B); '
                'color:white; padding:5px 10px; border-radius:8px; font-size:10px;">'
                '[KEY] {}...</code>',
                escape(obj.fingerprint_hash[:16])
            )
        except Exception:
            return '-'
    hash_col.short_description = '[KEY] Fingerprint'

    def platform_col(self, obj):
        try:
            colors = {'android': '#4CAF50', 'ios': '#2196F3', 'web': '#FF9800', 'windows': '#00BCD4'}
            p = str(obj.platform or 'unknown').lower()
            return badge(obj.platform or 'Unknown', colors.get(p, '#9E9E9E'), '💻')
        except Exception:
            return '-'
    platform_col.short_description = '💻 Platform'

    def accounts_col(self, obj):
        try:
            n = S.num(obj.total_accounts)
            c = '#F44336' if n >= 10 else '#FF9800' if n >= 5 else '#4CAF50'
            return format_html(
                '<span style="background:{}; color:white; padding:5px 12px; '
                'border-radius:50%; font-weight:bold; font-size:13px;">{}</span>',
                c, n
            )
        except Exception:
            return '-'
    accounts_col.short_description = '👥 Accounts'

    def suspicious_col(self, obj):
        try:
            return bool_badge(obj.is_suspicious, 'Suspicious', 'Clean', '[WARN]', '[OK]', '#FF9800', '#4CAF50')
        except Exception:
            return '-'
    suspicious_col.short_description = '[WARN] Suspicious'

    def blocked_col(self, obj):
        try:
            return bool_badge(obj.is_blocked, 'Blocked', 'Active', '🚫', '[OK]', '#F44336', '#4CAF50')
        except Exception:
            return '-'
    blocked_col.short_description = '🚫 Blocked'

    def last_seen_col(self, obj):
        try:
            return format_html(
                '<span style="color:#666; font-size:11px;">👁️ {}<br><small>{}</small></span>',
                obj.last_seen.strftime('%Y-%m-%d') if obj.last_seen else '-',
                time_ago(obj.last_seen)
            )
        except Exception:
            return '-'
    last_seen_col.short_description = '👁️ Last Seen'


# ==================== 7. IP REPUTATION ADMIN ====================
@admin.register(IPReputation)
class IPReputationAdmin(admin.ModelAdmin):
    list_display = ('ip_col', 'reputation_col', 'vpn_col', 'proxy_col',
                    'registrations_col', 'fraud_col', 'blacklisted_col')
    list_filter = ('reputation', 'is_vpn', 'is_proxy', 'is_tor', 'is_blacklisted')
    search_fields = ('ip_address', 'country_code', 'city', 'isp')
    readonly_fields = ('first_seen', 'last_seen', 'updated_at')
    list_per_page = 30

    def ip_col(self, obj):
        try:
            return format_html(
                '<code style="background:linear-gradient(135deg,#37474F,#546E7A); '
                'color:white; padding:5px 12px; border-radius:8px; font-weight:bold;">🌐 {}</code>',
                escape(str(obj.ip_address))
            )
        except Exception:
            return '-'
    ip_col.short_description = '🌐 IP Address'

    def reputation_col(self, obj):
        try:
            colors = {'trusted': '#4CAF50', 'neutral': '#9E9E9E', 'suspicious': '#FF9800', 'blocked': '#F44336'}
            icons = {'trusted': '[OK]', 'neutral': '⚪', 'suspicious': '[WARN]', 'blocked': '🚫'}
            r = obj.reputation or 'neutral'
            return gradient_badge(r.upper(), colors.get(r, '#9E9E9E'), '#90CAF9', icons.get(r, '❓'))
        except Exception:
            return '-'
    reputation_col.short_description = '[WIN] Reputation'

    def vpn_col(self, obj):
        try:
            return bool_badge(obj.is_vpn, 'VPN', 'Clean', '🔒', '[OK]', '#FF9800', '#4CAF50')
        except Exception:
            return '-'
    vpn_col.short_description = '🔒 VPN'

    def proxy_col(self, obj):
        try:
            return bool_badge(obj.is_proxy, 'Proxy', 'Clean', '🔗', '[OK]', '#FF9800', '#4CAF50')
        except Exception:
            return '-'
    proxy_col.short_description = '🔗 Proxy'

    def registrations_col(self, obj):
        try:
            n = S.num(obj.total_registrations)
            c = '#F44336' if n >= 10 else '#FF9800' if n >= 5 else '#4CAF50'
            return format_html(
                '<span style="background:{}; color:white; padding:4px 10px; '
                'border-radius:12px; font-weight:bold; font-size:12px;">[NOTE] {}</span>',
                c, n
            )
        except Exception:
            return '-'
    registrations_col.short_description = '[NOTE] Registrations'

    def fraud_col(self, obj):
        try:
            return score_badge(obj.fraud_score)
        except Exception:
            return '-'
    fraud_col.short_description = '🎯 Fraud Score'

    def blacklisted_col(self, obj):
        try:
            return bool_badge(obj.is_blacklisted, 'Blacklisted', 'Clean', '⛔', '[OK]', '#F44336', '#4CAF50')
        except Exception:
            return '-'
    blacklisted_col.short_description = '⛔ Blacklisted'


# ==================== 8. USER ACCOUNT LINK ADMIN ====================
@admin.register(UserAccountLink)
class UserAccountLinkAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'linked_col', 'risk_col', 'flagged_col', 'ip_col', 'created_col')
    list_filter = ('is_flagged', 'created_at')
    search_fields = ('user__username', 'registration_ip', 'flag_reason')
    readonly_fields = ('created_at', 'registration_date')
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def linked_col(self, obj):
        try:
            return format_html('<span style="color:#333; font-size:12px;">🔗 {}</span>',
                               escape(str(obj.linked_account)[:30]))
        except Exception:
            return '-'
    linked_col.short_description = '🔗 Linked Account'

    def risk_col(self, obj):
        try:
            return score_badge(obj.risk_score)
        except Exception:
            return '-'
    risk_col.short_description = '[WARN] Risk Score'

    def flagged_col(self, obj):
        try:
            return bool_badge(obj.is_flagged, 'Flagged', 'Clean', '🚩', '[OK]', '#F44336', '#4CAF50')
        except Exception:
            return '-'
    flagged_col.short_description = '🚩 Flagged'

    def ip_col(self, obj):
        try:
            return format_html(
                '<code style="background:#f5f5f5; padding:3px 7px; border-radius:4px; font-size:11px;">🌐 {}</code>',
                escape(str(obj.registration_ip or 'N/A'))
            )
        except Exception:
            return '-'
    ip_col.short_description = '🌐 IP'

    def created_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:11px;">📅 {}</span>',
                               obj.created_at.strftime('%Y-%m-%d') if obj.created_at else '-')
        except Exception:
            return '-'
    created_col.short_description = '📅 Created'


# ==================== 9. USER BEHAVIOR ADMIN ====================
@admin.register(UserBehavior)
class UserBehaviorAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'action_col', 'logins_col', 'anomaly_col', 'updated_col')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def action_col(self, obj):
        try:
            return badge(obj.action_type or 'N/A', '#2196F3', '⚡')
        except Exception:
            return '-'
    action_col.short_description = '⚡ Action Type'

    def logins_col(self, obj):
        try:
            return format_html(
                '<span style="background:#2196F3; color:white; padding:4px 10px; '
                'border-radius:12px; font-weight:bold;">[SECURE] {}</span>',
                S.num(obj.total_logins)
            )
        except Exception:
            return '-'
    logins_col.short_description = '[SECURE] Total Logins'

    def anomaly_col(self, obj):
        try:
            return score_badge(obj.anomaly_score)
        except Exception:
            return '-'
    anomaly_col.short_description = '🔍 Anomaly Score'

    def updated_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:11px;">[LOADING] {}</span>',
                               obj.updated_at.strftime('%Y-%m-%d') if obj.updated_at else '-')
        except Exception:
            return '-'
    updated_col.short_description = '[LOADING] Updated'


# ==================== 10. FRAUD DETECTION LOG ADMIN ====================
@admin.register(FraudDetectionLog)
class FraudDetectionLogAdmin(admin.ModelAdmin):
    list_display = ('event_col', 'severity_col', 'user_col', 'ip_col', 'resolved_col', 'detected_col')
    list_filter = ('event_type', 'severity', 'is_resolved', 'detected_at')
    search_fields = ('user__username', 'ip_address', 'description')
    readonly_fields = ('detected_at',)
    list_per_page = 30

    def event_col(self, obj):
        try:
            colors = {
                'vpn_detected': '#FF9800', 'proxy_detected': '#FF9800',
                'multi_account': '#F44336', 'suspicious_ip': '#FF9800',
                'rate_limit_exceeded': '#F44336', 'device_banned': '#F44336',
                'ip_banned': '#F44336', 'anomaly_detected': '#FF9800',
                'high_risk_score': '#F44336'
            }
            label = obj.get_event_type_display() if hasattr(obj, 'get_event_type_display') else obj.event_type
            return gradient_badge(label, colors.get(obj.event_type, '#9E9E9E'), '#FFCC80', '🚨')
        except Exception:
            return '-'
    event_col.short_description = '🚨 Event Type'

    def severity_col(self, obj):
        try:
            colors = {'low': '#4CAF50', 'medium': '#FF9800', 'high': '#FF5722', 'critical': '#F44336'}
            icons = {'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴'}
            s = obj.severity or 'low'
            return gradient_badge(s.upper(), colors.get(s, '#9E9E9E'), '#FFCC80', icons.get(s, '⚪'))
        except Exception:
            return '-'
    severity_col.short_description = '⚡ Severity'

    def user_col(self, obj):
        try:
            if not obj.user:
                return format_html('<span style="color:#999;">Anonymous</span>')
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def ip_col(self, obj):
        try:
            return format_html(
                '<code style="background:#f5f5f5; padding:3px 7px; border-radius:4px; font-size:11px;">🌐 {}</code>',
                escape(str(obj.ip_address))
            )
        except Exception:
            return '-'
    ip_col.short_description = '🌐 IP'

    def resolved_col(self, obj):
        try:
            return bool_badge(obj.is_resolved, 'Resolved', 'Pending', '[OK]', '⏳', '#4CAF50', '#FF9800')
        except Exception:
            return '-'
    resolved_col.short_description = '[STATS] Status'

    def detected_col(self, obj):
        try:
            return format_html(
                '<span style="color:#666; font-size:11px;">🕐 {}<br><small>{}</small></span>',
                obj.detected_at.strftime('%Y-%m-%d %H:%M') if obj.detected_at else '-',
                time_ago(obj.detected_at)
            )
        except Exception:
            return '-'
    detected_col.short_description = '🕐 Detected'

    def has_add_permission(self, request):
        return False


# ==================== 11. KYC VERIFICATION ADMIN ====================
@admin.register(KYCVerification)
class KYCVerificationAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'doc_type_col', 'status_col', 'submitted_col', 'reviewed_col')
    list_filter = ('verification_status', 'document_type', 'submitted_at')
    search_fields = ('user__username', 'document_number')
    readonly_fields = ('submitted_at', 'reviewed_at', 'created_at', 'updated_at')
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def doc_type_col(self, obj):
        try:
            colors = {'nid': '#2196F3', 'passport': '#4CAF50', 'driving_license': '#FF9800', 'voter_id': '#9C27B0'}
            icons = {'nid': '🆔', 'passport': '📘', 'driving_license': '🚗', 'voter_id': '🗳️'}
            dt = obj.document_type or 'nid'
            return gradient_badge(dt.replace('_', ' ').title(), colors.get(dt, '#9E9E9E'), '#90CAF9', icons.get(dt, '[DOC]'))
        except Exception:
            return '-'
    doc_type_col.short_description = '[DOC] Document Type'

    def status_col(self, obj):
        try:
            colors = {
                'pending': '#9E9E9E', 'submitted': '#2196F3',
                'under_review': '#FF9800', 'approved': '#4CAF50', 'rejected': '#F44336'
            }
            icons = {
                'pending': '⏳', 'submitted': '📤',
                'under_review': '🔍', 'approved': '[OK]', 'rejected': '[ERROR]'
            }
            s = obj.verification_status or 'pending'
            return gradient_badge(s.replace('_', ' ').upper(), colors.get(s, '#9E9E9E'), '#90CAF9', icons.get(s, '❓'))
        except Exception:
            return '-'
    status_col.short_description = '[STATS] Status'

    def submitted_col(self, obj):
        try:
            if not obj.submitted_at:
                return format_html('<span style="color:#999;">Not submitted</span>')
            return format_html('<span style="color:#666; font-size:11px;">📤 {}</span>',
                               obj.submitted_at.strftime('%Y-%m-%d'))
        except Exception:
            return '-'
    submitted_col.short_description = '📤 Submitted'

    def reviewed_col(self, obj):
        try:
            if not obj.reviewed_at:
                return format_html('<span style="color:#999;">Not reviewed</span>')
            return format_html('<span style="color:#666; font-size:11px;">🔍 {}</span>',
                               obj.reviewed_at.strftime('%Y-%m-%d'))
        except Exception:
            return '-'
    reviewed_col.short_description = '🔍 Reviewed'

    actions = ['approve_kyc', 'reject_kyc']

    def approve_kyc(self, request, queryset):
        try:
            count = queryset.update(verification_status='approved', reviewed_at=timezone.now())
            self.message_user(request, format_html(
                '<span style="color:#4CAF50; font-weight:bold;">[OK] {} KYC(s) approved</span>', count))
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='ERROR')
    approve_kyc.short_description = '[OK] Approve KYC'

    def reject_kyc(self, request, queryset):
        try:
            count = queryset.update(verification_status='rejected', reviewed_at=timezone.now())
            self.message_user(request, format_html(
                '<span style="color:#F44336; font-weight:bold;">[ERROR] {} KYC(s) rejected</span>', count))
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='ERROR')
    reject_kyc.short_description = '[ERROR] Reject KYC'


# ==================== 12. USER LEVEL ADMIN ====================
@admin.register(UserLevel)
class UserLevelAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'level_col', 'xp_col', 'progress_col', 'tasks_col', 'referrals_col')
    list_filter = ('level_type', 'current_level')
    search_fields = ('user__username',)
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def level_col(self, obj):
        try:
            colors = {'bronze': '#CD7F32', 'silver': '#9E9E9E', 'gold': '#FFC107', 'platinum': '#607D8B', 'diamond': '#00BCD4'}
            icons = {'bronze': '🥉', 'silver': '🥈', 'gold': '🥇', 'platinum': '💎', 'diamond': '💠'}
            lt = obj.level_type or 'bronze'
            return format_html(
                '<span style="background:linear-gradient(135deg,{},{}); color:white; '
                'padding:5px 14px; border-radius:18px; font-weight:bold; font-size:12px; '
                'box-shadow:0 2px 5px rgba(0,0,0,0.2);">{} Level {} - {}</span>',
                colors.get(lt, '#9E9E9E'), '#BDBDBD',
                icons.get(lt, '[STAR]'), S.num(obj.current_level), lt.upper()
            )
        except Exception:
            return '-'
    level_col.short_description = '[WIN] Level'

    def xp_col(self, obj):
        try:
            return format_html(
                '<span style="background:linear-gradient(135deg,#667eea,#764ba2); color:white; '
                'padding:5px 12px; border-radius:14px; font-weight:bold; font-size:12px;">'
                '[STAR] {} / {} XP</span>',
                S.num(obj.experience_points), S.num(obj.xp_to_next_level)
            )
        except Exception:
            return '-'
    xp_col.short_description = '[STAR] XP'

    def progress_col(self, obj):
        try:
            return progress_bar(obj.experience_points, obj.xp_to_next_level)
        except Exception:
            return '-'
    progress_col.short_description = '[STATS] Progress'

    def tasks_col(self, obj):
        try:
            return format_html(
                '<span style="background:#2196F3; color:white; padding:4px 10px; '
                'border-radius:12px; font-weight:bold;">📋 {}</span>',
                S.num(obj.tasks_completed)
            )
        except Exception:
            return '-'
    tasks_col.short_description = '📋 Tasks'

    def referrals_col(self, obj):
        try:
            return format_html(
                '<span style="background:#4CAF50; color:white; padding:4px 10px; '
                'border-radius:12px; font-weight:bold;">👥 {}</span>',
                S.num(obj.referral_count)
            )
        except Exception:
            return '-'
    referrals_col.short_description = '👥 Referrals'


# ==================== 13. USER STATISTICS ADMIN ====================
@admin.register(UserStatistics)
class UserStatisticsAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'earned_col', 'tasks_col', 'streak_col', 'approval_col', 'withdrawn_col')
    search_fields = ('user__username',)
    readonly_fields = ('statistics_updated_at',)
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def earned_col(self, obj):
        try:
            return money_badge(obj.total_earned)
        except Exception:
            return '-'
    earned_col.short_description = '[MONEY] Total Earned'
    earned_col.admin_order_field = 'total_earned'

    def tasks_col(self, obj):
        try:
            return format_html(
                '<span style="background:linear-gradient(135deg,#2196F3,#42A5F5); color:white; '
                'padding:5px 12px; border-radius:18px; font-weight:bold;">📋 {}</span>',
                S.num(obj.total_tasks_completed)
            )
        except Exception:
            return '-'
    tasks_col.short_description = '📋 Tasks'

    def streak_col(self, obj):
        try:
            days = S.num(obj.current_streak)
            c = '#FF5722' if days >= 30 else '#FF9800' if days >= 7 else '#4CAF50' if days > 0 else '#9E9E9E'
            icon = '🔥' if days >= 7 else '✨' if days > 0 else '💤'
            return format_html(
                '<span style="background:linear-gradient(135deg,{},{}); color:white; '
                'padding:5px 12px; border-radius:14px; font-weight:bold;">{} {} days</span>',
                c, '#FFCC80', icon, days
            )
        except Exception:
            return '-'
    streak_col.short_description = '🔥 Streak'

    def approval_col(self, obj):
        try:
            rate = float(obj.task_approval_rate or 0)
            c = '#4CAF50' if rate >= 80 else '#FF9800' if rate >= 60 else '#F44336'
            return format_html(
                '<span style="background:{}; color:white; padding:5px 12px; '
                'border-radius:14px; font-weight:bold; font-size:12px;">[OK] {}%</span>',
                c, round(rate, 1)
            )
        except Exception:
            return '-'
    approval_col.short_description = '[OK] Approval Rate'

    def withdrawn_col(self, obj):
        try:
            return money_badge(obj.total_withdrawn)
        except Exception:
            return '-'
    withdrawn_col.short_description = '💸 Withdrawn'


# ==================== 14. USER PROFILE ADMIN ====================
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'profile_id_col', 'phone_col',
                    'status_col', 'verify_col', 'earnings_col', 'country_col')
    list_filter = ('account_status', 'email_verified', 'phone_verified',
                   'identity_verified', 'is_premium', 'country')
    search_fields = ('user__username', 'profile_id', 'phone_number', 'nid_number', 'referral_code')
    readonly_fields = ('profile_id', 'created_at', 'updated_at')
    list_per_page = 30

    fieldsets = (
        ('👤 Basic Information', {
            'fields': ('user', 'profile_id', 'phone_number', 'bio', 'profile_picture', 'gender', 'date_of_birth')
        }),
        ('📍 Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code', 'zip_code'),
            'classes': ('collapse',)
        }),
        ('🆔 Identity', {
            'fields': ('nid_number',),
            'classes': ('collapse',)
        }),
        ('[MONEY] Earnings', {
            'fields': ('total_points', 'total_earnings', 'total_withdrawn')
        }),
        ('[OK] Verification', {
            'fields': ('email_verified', 'phone_verified', 'identity_verified')
        }),
        ('[STATS] Account', {
            'fields': ('account_status', 'is_premium', 'is_affiliate', 'email_notifications')
        }),
        ('👥 Referral', {
            'fields': ('referral_code', 'referred_by'),
            'classes': ('collapse',)
        }),
        ('📅 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def profile_id_col(self, obj):
        try:
            if not obj.profile_id:
                return format_html('<span style="color:#999;">No ID</span>')
            return format_html(
                '<code style="background:linear-gradient(135deg,#6f42c1,#9C27B0); '
                'color:white; padding:4px 10px; border-radius:8px; font-size:11px;">{}</code>',
                escape(obj.profile_id)
            )
        except Exception:
            return '-'
    profile_id_col.short_description = '🆔 Profile ID'

    def phone_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:12px;">📱 {}</span>',
                               escape(obj.phone_number or 'N/A'))
        except Exception:
            return '-'
    phone_col.short_description = '📱 Phone'

    def status_col(self, obj):
        try:
            colors = {'active': '#4CAF50', 'inactive': '#9E9E9E', 'suspended': '#FF9800', 'banned': '#F44336'}
            icons = {'active': '[OK]', 'inactive': '⚫', 'suspended': '[WARN]', 'banned': '🚫'}
            s = obj.account_status or 'active'
            return gradient_badge(s.upper(), colors.get(s, '#9E9E9E'), '#90CAF9', icons.get(s, '❓'))
        except Exception:
            return '-'
    status_col.short_description = '[STATS] Status'

    def verify_col(self, obj):
        try:
            parts = []
            if obj.email_verified:
                parts.append('<span style="background:#4CAF50; color:white; padding:2px 7px; border-radius:8px; font-size:10px; margin:1px;">✉️</span>')
            if obj.phone_verified:
                parts.append('<span style="background:#2196F3; color:white; padding:2px 7px; border-radius:8px; font-size:10px; margin:1px;">📱</span>')
            if obj.identity_verified:
                parts.append('<span style="background:#FF9800; color:white; padding:2px 7px; border-radius:8px; font-size:10px; margin:1px;">🆔</span>')
            if not parts:
                return format_html('<span style="color:#999; font-size:11px;">Not verified</span>')
            return format_html(' '.join(parts))
        except Exception:
            return '-'
    verify_col.short_description = '[OK] Verified'

    def earnings_col(self, obj):
        try:
            return money_badge(obj.total_earnings)
        except Exception:
            return '-'
    earnings_col.short_description = '[MONEY] Earnings'

    def country_col(self, obj):
        try:
            return format_html('<span style="color:#666; font-size:12px;">🌍 {}</span>',
                               escape(obj.country or 'N/A'))
        except Exception:
            return '-'
    country_col.short_description = '🌍 Country'


# ==================== 15. USER RANK ADMIN ====================
@admin.register(UserRank)
class UserRankAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'rank_col', 'points_col', 'progress_col', 'next_rank_col', 'updated_col')
    list_filter = ('rank', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 30
    actions = ['recalculate_ranks']

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def rank_col(self, obj):
        try:
            colors = {'Bronze': '#CD7F32', 'Silver': '#9E9E9E', 'Gold': '#FFC107', 'Platinum': '#607D8B', 'Diamond': '#00BCD4'}
            icons = {'Bronze': '🥉', 'Silver': '🥈', 'Gold': '🥇', 'Platinum': '💎', 'Diamond': '💠'}
            r = obj.rank or 'Bronze'
            return format_html(
                '<span style="background:linear-gradient(135deg,{},{}); color:white; '
                'padding:6px 16px; border-radius:18px; font-weight:bold; font-size:13px; '
                'box-shadow:0 3px 6px rgba(0,0,0,0.2); text-shadow:1px 1px 2px rgba(0,0,0,0.3);">'
                '{} {}</span>',
                colors.get(r, '#9E9E9E'), '#BDBDBD', icons.get(r, '[STAR]'), r
            )
        except Exception:
            return '-'
    rank_col.short_description = '[WIN] Rank'

    def points_col(self, obj):
        try:
            return format_html(
                '<span style="background:linear-gradient(135deg,#17a2b8,#0097A7); color:white; '
                'padding:5px 12px; border-radius:14px; font-weight:bold;">🎯 {} pts</span>',
                S.num(obj.points)
            )
        except Exception:
            return '-'
    points_col.short_description = '🎯 Points'

    def progress_col(self, obj):
        try:
            return progress_bar(obj.points, obj.next_rank_points)
        except Exception:
            return '-'
    progress_col.short_description = '[STATS] Progress'

    def next_rank_col(self, obj):
        try:
            remaining = max(0, S.num(obj.next_rank_points) - S.num(obj.points))
            return format_html(
                '<span style="color:#666; font-size:11px;">🎯 {} pts needed</span>',
                remaining
            )
        except Exception:
            return '-'
    next_rank_col.short_description = '🎯 Next Rank'

    def updated_col(self, obj):
        try:
            return format_html(
                '<span style="color:#666; font-size:11px;">[LOADING] {}<br><small>{}</small></span>',
                obj.updated_at.strftime('%Y-%m-%d') if obj.updated_at else '-',
                time_ago(obj.updated_at)
            )
        except Exception:
            return '-'
    updated_col.short_description = '[LOADING] Updated'

    def recalculate_ranks(self, request, queryset):
        try:
            count = 0
            for rank in queryset:
                rank.update_rank()
                count += 1
            self.message_user(request, format_html(
                '<span style="color:#4CAF50; font-weight:bold;">[WIN] {} rank(s) recalculated</span>', count))
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='ERROR')
    recalculate_ranks.short_description = '[LOADING] Recalculate ranks'


# ==================== 16. NOTIFICATION SETTINGS ADMIN ====================
@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'email_col', 'push_col', 'sms_col', 'frequency_col')
    search_fields = ('user__username',)
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def email_col(self, obj):
        try:
            count = sum(bool(v) for v in [
                obj.email_task_approved, obj.email_task_rejected,
                obj.email_withdrawal_processed, obj.email_promotional, obj.email_security_alerts
            ])
            c = '#4CAF50' if count >= 4 else '#FF9800' if count >= 2 else '#9E9E9E'
            return format_html(
                '<span style="background:{}; color:white; padding:5px 12px; '
                'border-radius:18px; font-weight:bold;">✉️ {}/5</span>', c, count)
        except Exception:
            return '-'
    email_col.short_description = '✉️ Email'

    def push_col(self, obj):
        try:
            count = sum(bool(v) for v in [
                obj.push_task_assigned, obj.push_task_completed,
                obj.push_reward_received, obj.push_referral_joined, obj.push_level_up
            ])
            c = '#4CAF50' if count >= 4 else '#FF9800' if count >= 2 else '#9E9E9E'
            return format_html(
                '<span style="background:{}; color:white; padding:5px 12px; '
                'border-radius:18px; font-weight:bold;">🔔 {}/5</span>', c, count)
        except Exception:
            return '-'
    push_col.short_description = '🔔 Push'

    def sms_col(self, obj):
        try:
            count = sum(bool(v) for v in [
                obj.sms_withdrawal_otp, obj.sms_important_alerts, obj.sms_promo_codes
            ])
            c = '#4CAF50' if count >= 2 else '#FF9800' if count >= 1 else '#9E9E9E'
            return format_html(
                '<span style="background:{}; color:white; padding:5px 12px; '
                'border-radius:18px; font-weight:bold;">📱 {}/3</span>', c, count)
        except Exception:
            return '-'
    sms_col.short_description = '📱 SMS'

    def frequency_col(self, obj):
        try:
            colors = {'immediate': '#F44336', 'hourly': '#FF9800', 'daily': '#4CAF50'}
            icons = {'immediate': '⚡', 'hourly': '🕐', 'daily': '📅'}
            f = obj.notification_frequency or 'immediate'
            return gradient_badge(f.upper(), colors.get(f, '#9E9E9E'), '#90CAF9', icons.get(f, '🔔'))
        except Exception:
            return '-'
    frequency_col.short_description = '⏰ Frequency'


# ==================== 17. SECURITY SETTINGS ADMIN ====================
@admin.register(SecuritySettings)
class SecuritySettingsAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'twofa_col', 'login_verify_col', 'alerts_col', 'sessions_col')
    search_fields = ('user__username',)
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def twofa_col(self, obj):
        try:
            if obj.two_factor_enabled:
                method_colors = {'email': '#2196F3', 'sms': '#4CAF50', 'authenticator': '#9C27B0'}
                m = obj.two_factor_method or 'email'
                return format_html(
                    '<span style="background:linear-gradient(135deg,{},{}); color:white; '
                    'padding:5px 14px; border-radius:18px; font-weight:bold; font-size:12px;">'
                    '[SECURE] ON ({})</span>',
                    method_colors.get(m, '#4CAF50'), '#A5D6A7', m.upper()
                )
            return gradient_badge('2FA OFF', '#F44336', '#EF9A9A', '[ERROR]')
        except Exception:
            return '-'
    twofa_col.short_description = '[SECURE] 2FA'

    def login_verify_col(self, obj):
        try:
            return bool_badge(obj.require_login_verification, 'Required', 'Optional', '🔒', '🔓')
        except Exception:
            return '-'
    login_verify_col.short_description = '🔒 Login Verify'

    def alerts_col(self, obj):
        try:
            count = sum(bool(v) for v in [
                obj.alert_on_new_device, obj.alert_on_new_location,
                obj.alert_on_failed_login, obj.alert_on_withdrawal
            ])
            c = '#4CAF50' if count >= 3 else '#FF9800' if count >= 2 else '#9E9E9E'
            return format_html(
                '<span style="background:{}; color:white; padding:5px 12px; '
                'border-radius:18px; font-weight:bold;">🔔 {}/4</span>', c, count)
        except Exception:
            return '-'
    alerts_col.short_description = '🔔 Alerts'

    def sessions_col(self, obj):
        try:
            return format_html(
                '<span style="background:#2196F3; color:white; padding:4px 10px; '
                'border-radius:12px; font-weight:bold; font-size:11px;">💻 Max {}</span>',
                S.num(obj.max_simultaneous_sessions, 3)
            )
        except Exception:
            return '-'
    sessions_col.short_description = '💻 Sessions'


# ==================== 18. USER PREFERENCES ADMIN ====================
@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'theme_col', 'language_col', 'visibility_col', 'premium_features_col')
    list_filter = ('theme', 'language', 'profile_visibility')
    search_fields = ('user__username',)
    list_per_page = 30

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def theme_col(self, obj):
        try:
            configs = {
                'light': ('#FFF9C4', '#F9A825', '☀️'),
                'dark': ('#212121', '#424242', '🌙'),
                'auto': ('#607D8B', '#78909C', '[LOADING]')
            }
            t = obj.theme or 'auto'
            c1, c2, icon = configs.get(t, ('#9E9E9E', '#BDBDBD', '🎨'))
            return format_html(
                '<span style="background:linear-gradient(135deg,{},{}); color:white; '
                'padding:5px 12px; border-radius:14px; font-weight:bold;">{} {}</span>',
                c1, c2, icon, t.upper()
            )
        except Exception:
            return '-'
    theme_col.short_description = '🎨 Theme'

    def language_col(self, obj):
        try:
            flags = {'en': '🇺🇸', 'bn': '🇧🇩', 'hi': '🇮🇳', 'ur': '🇵🇰'}
            label = obj.get_language_display() if hasattr(obj, 'get_language_display') else obj.language
            flag = flags.get(obj.language, '🌐')
            return format_html(
                '<span style="background:linear-gradient(135deg,#2196F3,#42A5F5); color:white; '
                'padding:5px 12px; border-radius:14px; font-weight:bold;">{} {}</span>',
                flag, escape(str(label))
            )
        except Exception:
            return '-'
    language_col.short_description = '🌐 Language'

    def visibility_col(self, obj):
        try:
            colors = {'public': '#4CAF50', 'friends': '#FF9800', 'private': '#F44336'}
            icons = {'public': '🌍', 'friends': '👥', 'private': '🔒'}
            v = obj.profile_visibility or 'public'
            return gradient_badge(v.upper(), colors.get(v, '#9E9E9E'), '#90CAF9', icons.get(v, '👁️'))
        except Exception:
            return '-'
    visibility_col.short_description = '👁️ Visibility'

    def premium_features_col(self, obj):
        try:
            features = []
            if getattr(obj, 'show_in_leaderboard', False):
                features.append('[WIN]')
            if getattr(obj, 'task_reminder_enabled', False):
                features.append('⏰')
            if getattr(obj, 'auto_claim_tasks', False):
                features.append('🤖')
            if not features:
                return format_html('<span style="color:#999; font-size:11px;">No features</span>')
            return format_html(
                '<span style="font-size:16px;">{}</span>',
                ' '.join(features)
            )
        except Exception:
            return '-'
    premium_features_col.short_description = '⚙️ Features'


# ==================== 19. RISK SCORE HISTORY ADMIN ====================
@admin.register(RiskScoreHistory)
class RiskScoreHistoryAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'score_col', 'prev_score_col', 'change_col', 'created_col')
    list_filter = ('created_at',)
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'calculated_at')
    list_per_page = 40

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def score_col(self, obj):
        try:
            return score_badge(obj.risk_score)
        except Exception:
            return '-'
    score_col.short_description = '[WARN] Risk Score'

    def prev_score_col(self, obj):
        try:
            return score_badge(obj.previous_score)
        except Exception:
            return '-'
    prev_score_col.short_description = '[STATS] Previous Score'

    def change_col(self, obj):
        try:
            current = S.num(obj.risk_score)
            previous = S.num(obj.previous_score)
            diff = current - previous
            if diff > 0:
                return format_html(
                    '<span style="color:#F44336; font-weight:bold; font-size:13px;">▲ +{}</span>', diff)
            elif diff < 0:
                return format_html(
                    '<span style="color:#4CAF50; font-weight:bold; font-size:13px;">▼ {}</span>', diff)
            return format_html('<span style="color:#9E9E9E;">— 0</span>')
        except Exception:
            return '-'
    change_col.short_description = '📈 Change'

    def created_col(self, obj):
        try:
            return format_html(
                '<span style="color:#666; font-size:11px;">📅 {}<br><small>{}</small></span>',
                obj.created_at.strftime('%Y-%m-%d %H:%M') if obj.created_at else '-',
                time_ago(obj.created_at)
            )
        except Exception:
            return '-'
    created_col.short_description = '📅 Date'

    def has_add_permission(self, request):
        return False


# ==================== 20. RATE LIMIT TRACKER ADMIN ====================
@admin.register(RateLimitTracker)
class RateLimitTrackerAdmin(admin.ModelAdmin):
    list_display = ('user_col', 'endpoint_col', 'count_col', 'blocked_col', 'block_until_col', 'created_col')
    list_filter = ('is_blocked', 'created_at', 'limit_type')
    search_fields = ('user__username', 'endpoint', 'identifier')
    readonly_fields = ('created_at', 'window_start', 'last_request')
    list_per_page = 40
    actions = ['unblock_trackers', 'reset_counters']

    def user_col(self, obj):
        try:
            return format_html('<span style="color:#667eea; font-weight:bold;">👤 {}</span>',
                               escape(obj.user.username))
        except Exception:
            return '-'
    user_col.short_description = '👤 User'

    def endpoint_col(self, obj):
        try:
            ep = str(obj.endpoint or 'N/A')
            if len(ep) > 35:
                ep = ep[:32] + '...'
            return format_html(
                '<code style="background:#f5f5f5; padding:3px 8px; border-radius:5px; '
                'font-size:11px; color:#333; border:1px solid #ddd;">🔗 {}</code>',
                escape(ep)
            )
        except Exception:
            return '-'
    endpoint_col.short_description = '🔗 Endpoint'

    def count_col(self, obj):
        try:
            n = S.num(obj.request_count)
            c = '#F44336' if n >= 100 else '#FF9800' if n >= 50 else '#4CAF50'
            return format_html(
                '<span style="background:{}; color:white; padding:4px 10px; '
                'border-radius:12px; font-weight:bold;">[STATS] {}</span>', c, n)
        except Exception:
            return '-'
    count_col.short_description = '[STATS] Count'

    def blocked_col(self, obj):
        try:
            return bool_badge(obj.is_blocked, 'Blocked', 'Active', '🚫', '[OK]', '#F44336', '#4CAF50')
        except Exception:
            return '-'
    blocked_col.short_description = '🚫 Blocked'

    def block_until_col(self, obj):
        try:
            if not obj.block_until:
                return format_html('<span style="color:#999;">-</span>')
            now = timezone.now()
            expired = now > obj.block_until
            c = '#9E9E9E' if expired else '#F44336'
            label = 'Expired' if expired else obj.block_until.strftime('%H:%M %d-%m')
            return format_html('<span style="color:{}; font-size:11px; font-weight:bold;">⏰ {}</span>', c, label)
        except Exception:
            return '-'
    block_until_col.short_description = '⏰ Block Until'

    def created_col(self, obj):
        try:
            return format_html(
                '<span style="color:#666; font-size:11px;">📅 {}<br><small>{}</small></span>',
                obj.created_at.strftime('%Y-%m-%d') if obj.created_at else '-',
                time_ago(obj.created_at)
            )
        except Exception:
            return '-'
    created_col.short_description = '📅 Created'

    def unblock_trackers(self, request, queryset):
        try:
            count = queryset.update(is_blocked=False, block_until=None)
            self.message_user(request, format_html(
                '<span style="color:#4CAF50; font-weight:bold;">[OK] {} tracker(s) unblocked</span>', count))
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='ERROR')
    unblock_trackers.short_description = '[OK] Unblock selected'

    def reset_counters(self, request, queryset):
        try:
            count = queryset.update(request_count=0, count=0)
            self.message_user(request, format_html(
                '<span style="color:#2196F3; font-weight:bold;">[LOADING] {} counter(s) reset</span>', count))
        except Exception as e:
            self.message_user(request, f'Error: {e}', level='ERROR')
    reset_counters.short_description = '[LOADING] Reset counters'


# ==================== ADMIN SITE CUSTOMIZATION ====================
admin.site.site_header = mark_safe(
    '<span style="font-size:20px; font-weight:bold; color:#667eea;">'
    '[START] Earning Platform - Admin Panel</span>'
)
admin.site.site_title = 'Earning Platform Admin'
admin.site.index_title = mark_safe(
    '<span style="color:#667eea; font-weight:bold;">Welcome to Earning Platform Administration</span>'
)


# ==================== FORCE REGISTER ALL MODELS ====================
# Register models that are not yet registered using decorators
try:
    # Dictionary of models and their admin classes (excluding already decorated ones)
    models_to_register = {
        NotificationSettings: NotificationSettingsAdmin,
        SecuritySettings: SecuritySettingsAdmin,
        UserStatistics: UserStatisticsAdmin,
        UserPreferences: UserPreferencesAdmin,
        UserRank: UserRankAdmin,
    }
    
    # Models already registered via @admin.register() decorators
    already_registered = {
        OTP, LoginHistory, UserActivity, UserDevice, DeviceFingerprint,
        IPReputation, UserAccountLink, UserBehavior, FraudDetectionLog,
        RiskScoreHistory, RateLimitTracker, KYCVerification, UserLevel,
        User, UserProfile
    }
    
    registered_count = 0
    for model, admin_class in models_to_register.items():
        try:
            if not admin.site.is_registered(model):
                admin.site.register(model, admin_class)
                registered_count += 1
                logger.debug(f"[OK] Registered: {model.__name__}")
            else:
                logger.debug(f"[INFO] Already registered: {model.__name__}")
        except Exception as e:
            logger.warning(f"[WARN] Failed to register {model.__name__}: {e}")
    
    logger.info(f"[OK] {registered_count} additional models registered successfully!")
    
except Exception as e:
    logger.error(f"[ERROR] Admin registration error: {e}")
    

def _force_register_users():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [(User, UserAdmin), (OTP, OTPAdmin), (LoginHistory, LoginHistoryAdmin), (UserActivity, UserActivityAdmin), (UserDevice, UserDeviceAdmin), (DeviceFingerprint, DeviceFingerprintAdmin), (IPReputation, IPReputationAdmin), (UserAccountLink, UserAccountLinkAdmin), (UserBehavior, UserBehaviorAdmin), (FraudDetectionLog, FraudDetectionLogAdmin), (KYCVerification, KYCVerificationAdmin), (UserLevel, UserLevelAdmin), (UserStatistics, UserStatisticsAdmin), (UserProfile, UserProfileAdmin), (UserRank, UserRankAdmin), (NotificationSettings, NotificationSettingsAdmin), (SecuritySettings, SecuritySettingsAdmin), (UserPreferences, UserPreferencesAdmin), (RiskScoreHistory, RiskScoreHistoryAdmin), (RateLimitTracker, RateLimitTrackerAdmin)]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                pass
        print(f"[OK] users registered {registered} models")
    except Exception as e:
        print(f"[WARN] users: {e}")
