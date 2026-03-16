from __future__ import annotations
import sys
import traceback
from typing import Optional, Dict, Any, List, Union, Type, Tuple, Callable
from datetime import timedelta, datetime
import logging
from functools import wraps
import inspect
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.urls import path
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
import json
from django.contrib import admin
from functools import wraps
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
import csv

from .models import (
    DeviceInfo,
    SecurityLog,
    UserBan,
    ClickTracker,
    MaintenanceMode,
    AppVersion,
    IPBlacklist,
    WithdrawalProtection,
    RiskScore,
    SecurityDashboard,
    AutoBlockRule,
    AuditTrail,
    DataExport,
    DataImport,
    SecurityNotification,
    AlertRule,
    FraudPattern,
    RealTimeDetection,
    Country,
    GeolocationLog,
    CountryBlockRule,
    APIRateLimit,
    RateLimitLog,
    PasswordPolicy,
    PasswordHistory,
    PasswordAttempt,
    UserSession,
    SessionActivity,
    TwoFactorMethod,
    TwoFactorAttempt,
    TwoFactorRecoveryCode,
    SecurityConfig
)


# ==================== DEFENSIVE CODING DECORATORS ====================

def safe_admin_method(default_return=None):
    """Decorator for safe admin method execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, obj=None, *args, **kwargs):
            try:
                return func(self, obj, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                if default_return is not None:
                    return default_return
                return format_html('<span style="color: #dc3545;">[WARN] Error</span>')
        return wrapper
    return decorator

def safe_action(message_on_error="Action failed"):
    """Decorator for safe admin actions"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, queryset, *args, **kwargs):
            try:
                return func(self, request, queryset, *args, **kwargs)
            except Exception as e:
                logger.error(f"Action {func.__name__} failed: {str(e)}", exc_info=True)
                self.message_user(request, f'[ERROR] {message_on_error}: {str(e)}', messages.ERROR)
                return None
        return wrapper
    return decorator

# ==================== ENHANCED ADMIN CLASS ====================

@admin.register(DeviceInfo)
class DeviceInfoAdmin(admin.ModelAdmin):
    # ... (your existing list_display, etc.)
    
    # ==================== SAFE DISPLAY METHODS ====================
    
    @safe_admin_method(default_return=format_html('<span style="color: #6c757d;">Error</span>'))
    def device_card(self, obj):
        """Display device as card"""
        icons = []
        if obj.is_rooted:
            icons.append('🔓')
        if obj.is_emulator:
            icons.append('💻')
        if obj.is_vpn:
            icons.append('[SECURE]')
        if obj.is_proxy:
            icons.append('🌐')
        
        badges = ' '.join(icons) if icons else '[OK]'
        
        # Safe attribute access
        device_model = getattr(obj, 'device_model', 'Unknown Device')
        device_id_hash = getattr(obj, 'device_id_hash', '')
        risk_score = getattr(obj, 'risk_score', 0)
        
        # Risk-based border color
        border_color = '#28a745'  # Green default
        if risk_score >= 70:
            border_color = '#dc3545'  # Red
        elif risk_score >= 40:
            border_color = '#ffc107'  # Yellow
        
        # Truncate long strings
        truncated_hash = device_id_hash[:16] + '...' if device_id_hash and len(device_id_hash) > 16 else (device_id_hash or 'No ID')
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 10px; border-left: 3px solid {}; padding-left: 8px;">'
            '<div style="font-size: 24px;">📱</div>'
            '<div>'
            '<strong style="font-size: 13px; display: block;">{}</strong>'
            '<span style="color: #6c757d; font-size: 10px; display: block;">{}</span>'
            '<span style="font-size: 14px; margin-top: 3px; display: block;">{}</span>'
            '</div>'
            '</div>',
            border_color,
            device_model,
            truncated_hash,
            badges
        )
    device_card.short_description = 'Device'
    device_card.admin_order_field = 'device_model'
    
    @safe_admin_method(default_return=format_html('<span style="color: #6c757d;">Error</span>'))
    def user_display(self, obj):
        """Display user info"""
        if not obj or not obj.user:
            return format_html('<span style="color: #6c757d; font-style: italic;">No User</span>')
        
        try:
            # Safe attribute access
            username = getattr(obj.user, 'username', '')
            email = getattr(obj.user, 'email', '')
            user_id = getattr(obj.user, 'pk', None)
            
            initial = username[0].upper() if username else '?'
            
            # Safe URL generation
            if user_id:
                try:
                    user_url = reverse('admin:users_user_change', args=[user_id])
                except:
                    user_url = '#'
            else:
                user_url = '#'
            
            return format_html(
                '<div style="display: flex; align-items: center; gap: 8px;">'
                '<div style="width: 32px; height: 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
                'border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; '
                'font-weight: bold; font-size: 14px;">{}</div>'
                '<div>'
                '<a href="{}" style="font-weight: 600; font-size: 12px; color: #007bff; text-decoration: none;">{}</a><br/>'
                '<span style="font-size: 9px; color: #6c757d;">{}</span>'
                '</div>'
                '</div>',
                initial,
                user_url,
                username or "No Username",
                email or "No Email"
            )
        except Exception as e:
            logger.error(f"Error in user_display: {e}")
            return format_html('<span style="color: #6c757d;">User Error</span>')
    user_display.short_description = 'User'
    user_display.admin_order_field = 'user__username'
    
    @safe_admin_method(default_return=format_html('<span style="color: #6c757d;">Error</span>'))
    def security_status(self, obj):
        """Display security warnings"""
        warnings = []
        
        if getattr(obj, 'is_rooted', False):
            warnings.append('<span style="background: #dc3545; color: white; padding: 3px 8px; '
                          'border-radius: 10px; font-size: 9px; margin: 2px; display: inline-block;">🔓 ROOTED</span>')
        
        if getattr(obj, 'is_emulator', False):
            warnings.append('<span style="background: #fd7e14; color: white; padding: 3px 8px; '
                          'border-radius: 10px; font-size: 9px; margin: 2px; display: inline-block;">💻 EMULATOR</span>')
        
        if getattr(obj, 'is_vpn', False):
            warnings.append('<span style="background: #6f42c1; color: white; padding: 3px 8px; '
                          'border-radius: 10px; font-size: 9px; margin: 2px; display: inline-block;">[SECURE] VPN</span>')
        
        if getattr(obj, 'is_proxy', False):
            warnings.append('<span style="background: #17a2b8; color: white; padding: 3px 8px; '
                          'border-radius: 10px; font-size: 9px; margin: 2px; display: inline-block;">🌐 PROXY</span>')
        
        if not warnings:
            return format_html('<span style="color: #28a745; font-weight: 600;">[OK] CLEAN</span>')
        
        return format_html(
            '<div style="display: flex; flex-wrap: wrap; gap: 3px;">{}</div>',
            ''.join(warnings)
        )
    security_status.short_description = 'Security'
    
    @safe_admin_method(default_return=format_html('<span style="color: #6c757d;">?</span>'))
    def risk_meter(self, obj):
        """Display risk score meter"""
        score = getattr(obj, 'risk_score', 0)
        
        if score >= 70:
            color = '#dc3545'
            emoji = '🔴'
            label = 'HIGH'
        elif score >= 40:
            color = '#ffc107'
            emoji = '🟡'
            label = 'MEDIUM'
        else:
            color = '#28a745'
            emoji = '🟢'
            label = 'LOW'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px;">{}</div>'
            '<div style="color: {}; font-weight: bold; font-size: 14px;">{}</div>'
            '<div style="color: {}; font-size: 8px; font-weight: 600; margin-top: 2px;">{}</div>'
            '</div>',
            emoji,
            color,
            score,
            color,
            label
        )
    risk_meter.short_description = 'Risk'
    risk_meter.admin_order_field = 'risk_score'
    
    @safe_admin_method(default_return=format_html('<span style="color: #6c757d;">?</span>'))
    def trust_level_badge(self, obj):
        """Display trust level"""
        if getattr(obj, 'is_trusted', False):
            return format_html(
                '<div style="text-align: center;">'
                '<div style="font-size: 20px;">🛡️</div>'
                '<div style="background: #17a2b8; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 9px; font-weight: 600; display: inline-block; margin-top: 3px;">TRUSTED</div>'
                '</div>'
            )
        
        trust_level = getattr(obj, 'trust_level', 1)
        trust_config = {
            1: ('#dc3545', 'LOW', '[WARN]'),
            2: ('#ffc107', 'MEDIUM', '[STAR]'),
            3: ('#28a745', 'HIGH', '[OK]'),
        }
        
        color, label, icon = trust_config.get(trust_level, ('#6c757d', 'UNKNOWN', '•'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px;">{}</div>'
            '<div style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 9px; font-weight: 600; display: inline-block; margin-top: 3px;">{}</div>'
            '</div>',
            icon,
            color,
            label
        )
    trust_level_badge.short_description = 'Trust'
    trust_level_badge.admin_order_field = 'trust_level'
    
    @safe_admin_method(default_return=format_html('<span style="color: #6c757d;">—</span>'))
    def location_info(self, obj):
        """Display location info"""
        last_ip = getattr(obj, 'last_ip', None)
        if not last_ip:
            return format_html('<span style="color: #6c757d; font-style: italic;">—</span>')
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-family: monospace; font-weight: 600; color: #495057; font-size: 11px;">{}</div>'
            '</div>',
            last_ip
        )
    location_info.short_description = 'IP Address'
    location_info.admin_order_field = 'last_ip'
    
    @safe_admin_method(default_return=format_html('<span style="color: #6c757d;">—</span>'))
    def activity_time(self, obj):
        """Display last activity"""
        last_activity = getattr(obj, 'last_activity', None)
        if not last_activity:
            return format_html('<span style="color: #6c757d;">—</span>')
        
        try:
            time_ago = timezone.now() - last_activity
            
            if time_ago < timedelta(minutes=1):
                display = 'Just now'
                color = '#28a745'
            elif time_ago < timedelta(hours=1):
                display = f'{int(time_ago.total_seconds() / 60)} min ago'
                color = '#28a745'
            elif time_ago < timedelta(days=1):
                display = f'{int(time_ago.total_seconds() / 3600)} hr ago'
                color = '#17a2b8'
            elif time_ago < timedelta(days=7):
                display = f'{time_ago.days} day ago'
                color = '#6c757d'
            else:
                display = last_activity.strftime('%Y-%m-%d')
                color = '#6c757d'
            
            return format_html(
                '<div style="text-align: center; color: {}; font-size: 10px; font-weight: 600;">{}</div>',
                color,
                display
            )
        except Exception:
            return format_html('<span style="color: #6c757d;">Invalid date</span>')
    activity_time.short_description = 'Last Active'
    activity_time.admin_order_field = 'last_activity'
    
    @safe_admin_method()
    def quick_actions(self, obj):
        """Quick action buttons"""
        if not obj or not obj.pk:
            return format_html('<span style="color: #6c757d;">—</span>')
        
        try:
            change_url = reverse('admin:security_deviceinfo_change', args=[obj.pk])
            return format_html(
                '<div style="display: flex; gap: 3px;">'
                '<a class="button" href="{}" style="background: #17a2b8; color: white; padding: 3px 6px; '
                'border-radius: 3px; text-decoration: none; font-size: 9px;">👁️</a>'
                '<a class="button" href="{}" style="background: #28a745; color: white; padding: 3px 6px; '
                'border-radius: 3px; text-decoration: none; font-size: 9px;">✏️</a>'
                '</div>',
                change_url,
                change_url
            )
        except Exception:
            return format_html('<span style="color: #6c757d;">—</span>')
    quick_actions.short_description = 'Actions'
    
    @safe_admin_method()
    def risk_score_display(self, obj):
        """Display risk score with color"""
        score = getattr(obj, 'risk_score', 0)
        color = '#dc3545' if score >= 70 else '#ffc107' if score >= 40 else '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 16px;">{} / 100</span>',
            color,
            score
        )
    risk_score_display.short_description = 'Current Risk Score'
    
    # ==================== SAFE READONLY FIELDS ====================
    
    @safe_admin_method()
    def device_overview(self, obj):
        """Device overview dashboard"""
        risk_score = getattr(obj, 'risk_score', 0)
        risk_color = '#dc3545' if risk_score >= 70 else '#ffc107' if risk_score >= 40 else '#28a745'
        
        # Safe attribute access with defaults
        device_model = getattr(obj, 'device_model', 'Unknown Device')
        device_id_hash = getattr(obj, 'device_id_hash', 'No ID')
        username = getattr(obj.user, 'username', 'No User') if obj.user else 'No User'
        device_brand = getattr(obj, 'device_brand', 'Unknown')
        android_version = getattr(obj, 'android_version', 'Unknown')
        app_version = getattr(obj, 'app_version', 'Unknown')
        
        html = f'<div style="background: linear-gradient(135deg, {risk_color}dd 0%, {risk_color} 100%); ' \
               f'padding: 20px; border-radius: 10px; color: white; margin-bottom: 15px;">'
        
        # Header
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">'
        html += '<div>'
        html += f'<div style="font-size: 12px; opacity: 0.9;">Device Security Profile</div>'
        html += f'<h2 style="margin: 5px 0 0 0; font-size: 24px;">{device_model}</h2>'
        html += f'<div style="font-size: 10px; opacity: 0.8; margin-top: 5px; font-family: monospace;">{device_id_hash[:32] if device_id_hash else "No ID"}</div>'
        html += '</div>'
        
        # Risk score badge
        html += f'<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 50%; width: 70px; height: 70px; '
        html += f'display: flex; flex-direction: column; align-items: center; justify-content: center;">'
        html += f'<div style="font-size: 24px; font-weight: bold;">{risk_score}</div>'
        html += f'<div style="font-size: 8px; opacity: 0.9;">RISK</div>'
        html += '</div>'
        html += '</div>'
        
        # Stats grid
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;">'
        
        stats = [
            ('User', username[:15] + '...' if len(username) > 15 else username),
            ('Brand', device_brand[:10] + '...' if len(device_brand) > 10 else device_brand),
            ('Android', android_version[:10] + '...' if len(android_version) > 10 else android_version),
            ('App Ver', app_version),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 8px; border-radius: 5px; text-align: center;">'
            html += f'<div style="font-size: 8px; opacity: 0.9; margin-bottom: 3px;">{label}</div>'
            html += f'<div style="font-size: 11px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    device_overview.short_description = ''
    
    @safe_admin_method()
    def security_analysis(self, obj):
        """Security analysis"""
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 6px;">'
        html += '<h4 style="margin-top: 0; margin-bottom: 12px; font-size: 14px;">🔍 Security Analysis</h4>'
        
        # Security checks
        checks = [
            ('Rooted Device', getattr(obj, 'is_rooted', False), '#dc3545'),
            ('Emulator Detected', getattr(obj, 'is_emulator', False), '#fd7e14'),
            ('VPN Usage', getattr(obj, 'is_vpn', False), '#6f42c1'),
            ('Proxy Detected', getattr(obj, 'is_proxy', False), '#17a2b8'),
            ('Trusted Device', getattr(obj, 'is_trusted', False), '#28a745'),
        ]
        
        html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">'
        
        for label, status, color in checks:
            if status:
                bg_color = f'{color}20'
                icon = '[OK]' if label == 'Trusted Device' else '[WARN]'
            else:
                bg_color = '#f8f9fa'
                color = '#6c757d'
                icon = '[OK]' if label == 'Trusted Device' else '[ERROR]'
            
            html += f'<div style="background: {bg_color}; border-left: 2px solid {color}; padding: 8px; border-radius: 3px;">'
            html += f'<div style="font-size: 14px; margin-bottom: 2px;">{icon}</div>'
            html += f'<div style="font-size: 10px; font-weight: 600; color: {color};">{label}</div>'
            html += '</div>'
        
        html += '</div>'
        
        # Risk breakdown
        if hasattr(obj, 'is_suspicious') and callable(getattr(obj, 'is_suspicious')):
            try:
                if obj.is_suspicious():
                    html += '<div style="background: #fff3cd; border-left: 3px solid #ffc107; padding: 10px; border-radius: 3px; margin-top: 12px;">'
                    html += '<strong style="color: #856404; font-size: 11px;">[WARN] WARNING: Suspicious Device Detected</strong>'
                    html += '<p style="margin: 5px 0 0 0; color: #856404; font-size: 10px;">This device shows multiple security concerns.</p>'
                    html += '</div>'
            except Exception:
                pass
        
        html += '</div>'
        
        return format_html(html)
    security_analysis.short_description = '🔍 Security Analysis'
    
    @safe_admin_method()
    def duplicate_devices_list(self, obj):
        """List duplicate devices"""
        if not obj or not obj.device_id_hash:
            return format_html('<div style="color: #6c757d;">No device ID to check</div>')
        
        try:
            duplicate_count = DeviceInfo.check_duplicate_devices(obj.device_id_hash, exclude_user=obj.user)
            
            html = '<div style="background: #f8f9fa; padding: 12px; border-radius: 6px;">'
            
            if duplicate_count > 0:
                html += f'<div style="background: #f8d7da; border-left: 3px solid #dc3545; padding: 10px; border-radius: 3px; margin-bottom: 12px;">'
                html += f'<strong style="color: #721c24; font-size: 12px;">🚨 {duplicate_count} Duplicate Account(s) Found!</strong>'
                html += '</div>'
                
                # List duplicate accounts
                duplicates = DeviceInfo.objects.filter(device_id_hash=obj.device_id_hash).exclude(id=obj.id)[:10]
                
                if duplicates.exists():
                    html += '<table style="width: 100%; border-collapse: collapse; font-size: 11px;">'
                    html += '<tr style="background: #dee2e6;"><th style="padding: 6px; text-align: left;">User</th>'
                    html += '<th style="padding: 6px;">Created</th><th style="padding: 6px;">Risk</th></tr>'
                    
                    for dup in duplicates[:5]:
                        username = dup.user.username[:15] + '...' if dup.user and len(dup.user.username) > 15 else (dup.user.username if dup.user else "No User")
                        created = dup.created_at.strftime("%Y-%m-%d") if dup.created_at else "Unknown"
                        risk = dup.risk_score or 0
                        risk_color = '#dc3545' if risk > 70 else '#28a745'
                        
                        html += f'<tr style="border-bottom: 1px solid #dee2e6;">'
                        html += f'<td style="padding: 6px;">{username}</td>'
                        html += f'<td style="padding: 6px; text-align: center;">{created}</td>'
                        html += f'<td style="padding: 6px; text-align: center; font-weight: 600; color: {risk_color};">{risk}</td>'
                        html += '</tr>'
                    
                    if duplicates.count() > 5:
                        html += f'<tr><td colspan="3" style="padding: 6px; text-align: center; color: #6c757d;">... and {duplicates.count() - 5} more</td></tr>'
                    
                    html += '</table>'
                else:
                    html += '<div style="text-align: center; padding: 10px; color: #6c757d;">No duplicates found</div>'
            else:
                html += '<div style="text-align: center; color: #28a745; padding: 15px;">'
                html += '<div style="font-size: 32px;">[OK]</div>'
                html += '<div style="font-size: 12px; font-weight: 600; margin-top: 5px;">No Duplicate Devices</div>'
                html += '</div>'
            
            html += '</div>'
            
            return format_html(html)
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return format_html('<div style="color: #6c757d;">Unable to load duplicates</div>')
    duplicate_devices_list.short_description = '👥 Duplicate Devices'
    
    @safe_admin_method()
    def activity_timeline(self, obj):
        """Activity timeline"""
        html = '<div style="background: #f8f9fa; padding: 12px; border-radius: 6px;">'
        html += '<table style="width: 100%; border-collapse: collapse; font-size: 11px;">'
        
        timeline = [
            ('Created', getattr(obj, 'created_at', None), '#17a2b8'),
            ('Last Updated', getattr(obj, 'updated_at', None), '#6c757d'),
            ('Last Activity', getattr(obj, 'last_activity', None), '#28a745'),
        ]
        
        for label, timestamp, color in timeline:
            if timestamp:
                try:
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_time = 'Invalid date'
                    color = '#6c757d'
            else:
                formatted_time = 'Unknown'
                color = '#6c757d'
            
            html += f'<tr><td style="padding: 6px 0; color: #6c757d; border-bottom: 1px solid #dee2e6;">{label}</td>'
            html += f'<td style="padding: 6px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #dee2e6; color: {color};">'
            html += formatted_time
            html += '</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    activity_timeline.short_description = '📅 Timeline'
    
    # ==================== SAFE ACTIONS ====================
    
    @safe_action("Failed to mark as trusted")
    def mark_as_trusted(self, request, queryset):
        """Mark selected devices as trusted"""
        count = queryset.update(is_trusted=True, trust_level=3, risk_score=0)
        self.message_user(request, f'[OK] {count} device(s) marked as trusted.', messages.SUCCESS)
    mark_as_trusted.short_description = '[OK] Mark as trusted'
    
    @safe_action("Failed to mark as suspicious")
    def mark_as_suspicious(self, request, queryset):
        """Mark selected devices as suspicious"""
        count = queryset.update(is_trusted=False, trust_level=1, risk_score=80)
        self.message_user(request, f'[WARN] {count} device(s) marked as suspicious.', messages.WARNING)
    mark_as_suspicious.short_description = '[WARN] Mark as suspicious'
    
    @safe_action("Failed to block duplicate devices")
    def block_duplicate_devices(self, request, queryset):
        """Block users with duplicate devices"""
        count = 0
        for device in queryset:
            if not device.device_id_hash:
                continue
                
            duplicates = DeviceInfo.objects.filter(
                device_id_hash=device.device_id_hash
            ).exclude(id=device.id).exclude(user__isnull=True)
            
            for dup in duplicates:
                if dup.user:
                    ban, created = UserBan.objects.get_or_create(
                        user=dup.user,
                        defaults={
                            'reason': 'duplicate_device',
                            'description': f'Duplicate device detected: {device.device_id_hash[:16]}...',
                            'is_permanent': False,
                            'banned_until': timezone.now() + timedelta(days=7)
                        }
                    )
                    if created:
                        count += 1
        
        self.message_user(request, f'🚫 {count} user(s) blocked for duplicate devices.', messages.SUCCESS)
    block_duplicate_devices.short_description = '🚫 Block duplicate accounts'
    
    @safe_action("Failed to update risk scores")
    def update_risk_scores(self, request, queryset):
        """Update risk scores for selected devices"""
        success_count = 0
        for device in queryset:
            if hasattr(device, 'update_risk_score') and callable(device.update_risk_score):
                try:
                    if device.update_risk_score():
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to update risk score for device {device.id}: {e}")
        
        self.message_user(request, f'[LOADING] {success_count}/{queryset.count()} risk scores updated.', messages.SUCCESS)
    update_risk_scores.short_description = '[LOADING] Update risk scores'
    
    @safe_action("Export failed")
    def export_selected_devices(self, request, queryset):
        """Export selected devices as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="devices_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Device ID', 'Model', 'Brand', 'User', 'Risk Score', 'Rooted', 'Emulator', 'VPN', 'Last IP', 'Last Activity'])
        
        for device in queryset:
            writer.writerow([
                getattr(device, 'device_id_hash', '') or '',
                getattr(device, 'device_model', '') or '',
                getattr(device, 'device_brand', '') or '',
                device.user.username if device.user else '',
                getattr(device, 'risk_score', 0),
                getattr(device, 'is_rooted', False),
                getattr(device, 'is_emulator', False),
                getattr(device, 'is_vpn', False),
                getattr(device, 'last_ip', '') or '',
                device.last_activity.strftime('%Y-%m-%d %H:%M:%S') if device.last_activity else '',
            ])
        
        return response
    export_selected_devices.short_description = '📥 Export selected devices (CSV)'
    
    # ==================== OVERRIDE METHODS ====================
    
    def get_queryset(self, request):
        """Optimize queryset with error handling"""
        try:
            return super().get_queryset(request).select_related('user')
        except Exception as e:
            logger.error(f"Error in get_queryset: {e}")
            return super().get_queryset(request)
    
    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly based on permissions"""
        try:
            if obj:  # Editing existing object
                return self.readonly_fields
            return []  # Creating new object - allow editing all fields
        except Exception:
            return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        """Save with audit trail"""
        try:
            if not change:  # New object
                if not hasattr(obj, 'metadata') or obj.metadata is None:
                    obj.metadata = {}
                obj.metadata['created_by'] = request.user.username
            
            super().save_model(request, obj, form, change)
            
            if change:
                logger.info(f"Device {obj.id} updated by {request.user.username}")
            else:
                logger.info(f"Device {obj.id} created by {request.user.username}")
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            raise
    
    def delete_model(self, request, obj):
        """Delete with audit"""
        try:
            logger.warning(f"Device {obj.id} deleted by {request.user.username}")
            super().delete_model(request, obj)
        except Exception as e:
            logger.error(f"Error deleting model: {e}")
            raise
    
    def delete_queryset(self, request, queryset):
        """Bulk delete with audit"""
        try:
            count = queryset.count()
            logger.warning(f"{count} devices deleted by {request.user.username}")
            super().delete_queryset(request, queryset)
        except Exception as e:
            logger.error(f"Error bulk deleting: {e}")
            self.message_user(request, f'[ERROR] Delete failed: {str(e)}', messages.ERROR)
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
        js = ('admin/js/custom_admin.js',)


# ==================== Security Log Admin ====================
@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = [
        'log_badge',
        'security_type',
        'user_link',
        'type_badge',
        'severity_indicator',
        'risk_score_display',
        'ip_address_display',
        'device_info_display',
        'resolved_status',
        'created_display',
    ]
    
    list_filter = [
        'security_type',
        'severity',
        ('created_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'ip_address',
        'user_agent',
        'request_path',
    ]
    
    readonly_fields = [
        'log_overview',
        'log_id',
        'full_details',
        'ip_address_safe',
        'metadata_display',
        'created_at',
    ]
    
    fieldsets = (
        ('🚨 Security Log Overview', {
            'fields': ('log_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Log Information', {
            'fields': (
                ('log_id', 'event_type'),
                'severity',
                'full_details',
            )
        }),
        
        ('🌐 Network & Device', {
            'fields': (
                'ip_address_safe',
                'user_agent',
                'request_path',
                'request_method',
            ),
            'classes': ('collapse',)
        }),
        
        ('👤 User Information', {
            'fields': (
                'user',
            )
        }),
        
        ('[FIX] Metadata', {
            'fields': (
                'metadata_display',
                'details',
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] Timestamp', {
            'fields': (
                'created_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_high_severity',
        'mark_as_critical',
        'export_logs',
        'fix_invalid_ips',
    ]
    
    date_hierarchy = 'created_at'
    
    # ==================== Display Methods ====================
    
    def log_badge(self, obj):
        """Display log ID with severity color"""
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545',
        }
        
        color = severity_colors.get(obj.severity, '#6c757d')
        
        return format_html(
            '<div style="border-left: 4px solid {}; padding-left: 10px;">'
            '<div style="font-weight: bold; font-size: 11px; color: {};">#{}</div>'
            '<div style="font-size: 9px; color: #6c757d; margin-top: 2px;">{}</div>'
            '</div>',
            color,
            color,
            obj.pk,
            obj.created_at.strftime('%H:%M:%S') if obj.created_at else 'N/A'
        )
    log_badge.short_description = 'Log'
    
    def user_link(self, obj):
        """Display user with link"""
        if not obj.user:
            return format_html('<span style="color: #6c757d;">Anonymous</span>')
        
        try:
            url = reverse('admin:users_user_change', args=[obj.user.pk])
            return format_html(
                '<a href="{}" style="font-weight: 600; font-size: 12px;">{}</a>',
                url,
                obj.user.username
            )
        except:
            return format_html(
                '<span style="font-weight: 600; font-size: 12px;">{}</span>',
                obj.user.username
            )
    user_link.short_description = 'User'
    
    def type_badge(self, obj):
        """Display security type badge"""
        type_colors = {
            'login': '#28a745',
            'logout': '#6c757d',
            'failed_login': '#dc3545',
            'permission_denied': '#ffc107',
            'not_found': '#17a2b8',
            'access_denied': '#fd7e14',
            'success': '#28a745',
        }
        
        color = type_colors.get(obj.event_type, '#6c757d')
        display_text = obj.get_event_type_display() if hasattr(obj, 'get_event_type_display') else obj.event_type
        
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600; white-space: nowrap;">{}</span>',
            color,
            display_text
        )
    type_badge.short_description = 'Event Type'
    
    def severity_indicator(self, obj):
        """Display severity"""
        severity_config = {
            'low': ('#28a745', '[INFO]'),
            'medium': ('#ffc107', '[WARN]'),
            'high': ('#fd7e14', '[WARN]'),
            'critical': ('#dc3545', '🚨'),
        }
        
        color, icon = severity_config.get(obj.severity, ('#6c757d', '•'))
        display_text = obj.get_severity_display() if hasattr(obj, 'get_severity_display') else obj.severity
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 24px;">{}</div>'
            '<div style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 9px; font-weight: 600; display: inline-block; margin-top: 3px;">{}</div>'
            '</div>',
            icon,
            color,
            display_text.upper()
        )
    severity_indicator.short_description = 'Severity'
    
    def risk_score_display(self, obj):
        """Display risk score"""
        # Calculate risk score based on severity
        risk_scores = {
            'low': 25,
            'medium': 50,
            'high': 75,
            'critical': 95,
        }
        score = risk_scores.get(obj.severity, 50)
        
        if score >= 70:
            color = '#dc3545'
        elif score >= 40:
            color = '#ffc107'
        else:
            color = '#28a745'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-weight: bold; font-size: 14px;">{}</div>',
            color,
            score
        )
    risk_score_display.short_description = 'Risk'
    
    def ip_address_display(self, obj):
        """Display IP address with validation indicator"""
        from api.wallet.validators import is_valid_ipv4, is_valid_ipv6
        
        ip = obj.ip_address or '0.0.0.0'
        
        # Check if IP is valid
        is_valid = is_valid_ipv4(ip) or is_valid_ipv6(ip)
        
        if is_valid:
            icon = '[OK]'
            bg_color = '#d4edda'
            text_color = '#155724'
        else:
            icon = '[WARN]'
            bg_color = '#fff3cd'
            text_color = '#856404'
        
        return format_html(
            '<div style="background: {}; color: {}; padding: 5px 10px; '
            'border-radius: 5px; font-family: monospace; font-size: 11px; display: inline-block;">'
            '{} {}'
            '</div>',
            bg_color,
            text_color,
            icon,
            ip
        )
    ip_address_display.short_description = 'IP Address'
    
    def device_info_display(self, obj):
        """Display device info"""
        if not obj.user_agent:
            return format_html('<span style="color: #6c757d;">—</span>')
        
        # Extract browser/device from user agent
        user_agent = obj.user_agent[:50]
        
        return format_html(
            '<div style="font-size: 10px; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{}">{}</div>',
            obj.user_agent,
            user_agent
        )
    device_info_display.short_description = 'Device'
    
    def resolved_status(self, obj):
        """Display resolved status"""
        # For now, all logs are considered "logged"
        return format_html(
            '<span style="background: #28a745; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px;">✓ LOGGED</span>'
        )
    resolved_status.short_description = 'Status'
    
    def created_display(self, obj):
        """Display creation time"""
        if not obj.created_at:
            return format_html('<span style="color: #6c757d;">N/A</span>')
        
        time_ago = timezone.now() - obj.created_at
        
        if time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m'
            color = '#dc3545'
        elif time_ago < timedelta(days=1):
            display = f'{int(time_ago.total_seconds() / 3600)}h'
            color = '#ffc107'
        else:
            display = f'{time_ago.days}d'
            color = '#6c757d'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-size: 11px; font-weight: 600;">{}</div>',
            color,
            display
        )
    created_display.short_description = 'Age'
    
    # ==================== Readonly Fields ====================
    
    def log_overview(self, obj):
        """Log overview"""
        severity_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545',
        }
        
        color = severity_colors.get(obj.severity, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); ' \
               'padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">'
        
        html += f'<h2 style="margin: 0 0 10px 0;">Security Log #{obj.pk}</h2>'
        
        event_display = obj.get_event_type_display() if hasattr(obj, 'get_event_type_display') else obj.event_type
        html += f'<p style="margin: 0; opacity: 0.9; font-size: 14px;">{event_display}</p>'
        
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 15px;">'
        
        stats = [
            ('User', obj.user.username if obj.user else 'Anonymous'),
            ('Severity', obj.get_severity_display() if hasattr(obj, 'get_severity_display') else obj.severity),
            ('IP Address', obj.ip_address or '0.0.0.0'),
            ('Time', obj.created_at.strftime('%H:%M:%S') if obj.created_at else 'N/A'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 6px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 3px;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    log_overview.short_description = ''
    
    def full_details(self, obj):
        """Full details"""
        details_text = ''
        
        if obj.request_path:
            details_text += f"Path: {obj.request_path}\n"
        
        if obj.request_method:
            details_text += f"Method: {obj.request_method}\n"
        
        if obj.user_agent:
            details_text += f"User Agent: {obj.user_agent}\n"
        
        if not details_text:
            details_text = 'No additional details available'
        
        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<pre style="margin: 0; line-height: 1.6; font-size: 11px; white-space: pre-wrap;">{}</pre>'
            '</div>',
            details_text
        )
    full_details.short_description = 'Details'
    
    def ip_address_safe(self, obj):
        """Safe IP address display with validation"""
        from api.wallet.validators import safe_ip_address, is_valid_ipv4, is_valid_ipv6
        
        original_ip = obj.ip_address or 'Not Set'
        validated_ip = safe_ip_address(obj.ip_address, '0.0.0.0')
        
        is_valid = is_valid_ipv4(validated_ip) or is_valid_ipv6(validated_ip)
        
        if is_valid:
            status_html = '<span style="color: #28a745;">[OK] Valid IP</span>'
        else:
            status_html = '<span style="color: #dc3545;">[WARN] Invalid IP (Auto-fixed)</span>'
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
        html += f'<div style="margin-bottom: 10px;"><strong>Original:</strong> <code>{original_ip}</code></div>'
        html += f'<div style="margin-bottom: 10px;"><strong>Validated:</strong> <code>{validated_ip}</code></div>'
        html += f'<div><strong>Status:</strong> {status_html}</div>'
        html += '</div>'
        
        return format_html(html)
    ip_address_safe.short_description = 'IP Address (Validated)'
    
    def metadata_display(self, obj):
        """Display metadata"""
        if not obj.details:
            return format_html('<span style="color: #6c757d;">No metadata</span>')
        
        try:
            if isinstance(obj.details, dict):
                formatted = json.dumps(obj.details, indent=2)
            else:
                formatted = str(obj.details)
        except:
            formatted = str(obj.details)
        
        html = '<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-size: 11px; overflow-x: auto; max-height: 300px;">'
        html += formatted
        html += '</pre>'
        
        return format_html(html)
    metadata_display.short_description = 'Metadata'
    
    # ==================== Actions ====================
    
    def mark_as_high_severity(self, request, queryset):
        """Mark as high severity"""
        count = queryset.update(severity='high')
        self.message_user(request, f'{count} logs marked as HIGH severity.', messages.SUCCESS)
    mark_as_high_severity.short_description = '⬆️ Mark as HIGH severity'
    
    def mark_as_critical(self, request, queryset):
        """Mark as critical severity"""
        count = queryset.update(severity='critical')
        self.message_user(request, f'{count} logs marked as CRITICAL severity.', messages.WARNING)
    mark_as_critical.short_description = '🚨 Mark as CRITICAL'
    
    def fix_invalid_ips(self, request, queryset):
        """Fix invalid IP addresses in selected logs"""
        from api.wallet.validators import safe_ip_address
        
        count = 0
        for log in queryset:
            original_ip = log.ip_address
            validated_ip = safe_ip_address(original_ip, '0.0.0.0')
            
            if original_ip != validated_ip:
                log.ip_address = validated_ip
                log.save()
                count += 1
        
        self.message_user(
            request,
            f'Fixed {count} invalid IP addresses.',
            messages.SUCCESS
        )
    fix_invalid_ips.short_description = '[FIX] Fix Invalid IPs'
    
    def export_logs(self, request, queryset):
        """Export logs (placeholder)"""
        self.message_user(request, 'Export feature coming soon.', messages.INFO)
    export_logs.short_description = '📥 Export logs'
    
    
    
    # security/admin.py (continued)

# ==================== User Ban Admin ====================

@admin.register(UserBan)
class UserBanAdmin(admin.ModelAdmin):
    list_display = [
        'ban_badge',
        'user_display',
        'reason_badge',
        'status_indicator',
        'time_remaining_display',
        'banned_by_display',
        'created_display',
        'quick_actions',
    ]
    
    list_filter = [
        'reason',
        'is_permanent',
        # 'is_active',
        # 'can_appeal',
        # 'created_at',
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'description',
        'banned_by__username',
    ]
    
    readonly_fields = [
        'ban_overview',
        'ban_timeline',
        'appeal_info',
        # 'created_at',
        # 'updated_at',
    ]
    
    fieldsets = (
        ('🚫 Ban Overview', {
            'fields': ('ban_overview',),
            'classes': ('wide',)
        }),
        
        ('👤 User & Reason', {
            'fields': (
                'user',
                'reason',
                'description',
            )
        }),
        
        ('⏰ Ban Duration', {
            'fields': (
                'ban_timeline',
                'is_permanent',
                'banned_until',
            )
        }),
        
        ('⚙️ Settings', {
            'fields': (
                ('is_active', 'can_appeal'),
                'banned_by',
            )
        }),
        
        ('[NOTE] Appeal', {
            'fields': (
                'appeal_info',
                'appeal_text',
                ('appeal_status', 'appeal_reviewed_by'),
                'appeal_reviewed_at',
            ),
            'classes': ('collapse',)
        }),
        
        ('[FIX] Metadata', {
            'fields': (
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'unban_users',
        'make_permanent',
        'extend_ban',
        'approve_appeals',
        'reject_appeals',
    ]
    
    # date_hierarchy = 'created_at'
    
    # ==================== Display Methods ====================
    
    def ban_badge(self, obj):
        """Display ban badge"""
        if obj.is_permanent:
            color = '#dc3545'
            icon = '🔒'
            status = 'PERMANENT'
        elif obj.is_active:
            color = '#ffc107'
            icon = '⏳'
            status = 'ACTIVE'
        else:
            color = '#6c757d'
            icon = '[OK]'
            status = 'EXPIRED'
        
        return format_html(
            '<div style="text-align: center; background: {}; color: white; '
            'padding: 10px; border-radius: 8px;">'
            '<div style="font-size: 24px;">{}</div>'
            '<div style="font-size: 9px; font-weight: 600; margin-top: 3px;">{}</div>'
            '</div>',
            color,
            icon,
            status
        )
    ban_badge.short_description = 'Status'
    
    def user_display(self, obj):
        """Display user"""
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<div style="width: 32px; height: 32px; background: linear-gradient(135deg, #ff0844 0%, #ffb199 100%); '
            'border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; '
            'font-weight: bold; font-size: 14px;">{}</div>'
            '<div>'
            '<a href="{}" style="font-weight: 600; font-size: 12px; color: #dc3545;">{}</a><br/>'
            '<span style="font-size: 9px; color: #6c757d;">{}</span>'
            '</div>'
            '</div>',
            obj.user.username[0].upper(),
            reverse('admin:users_user_change', args=[obj.user.pk]),
            obj.user.username,
            obj.user.email
        )
    user_display.short_description = 'User'
    
    def reason_badge(self, obj):
        """Display reason badge"""
        reason_colors = {
            'fraud': '#dc3545',
            'multiple_accounts': '#6f42c1',
            'vpn_abuse': '#fd7e14',
            'fast_clicking': '#ffc107',
            'rooted_device': '#e83e8c',
            'terms_violation': '#17a2b8',
            'suspicious_activity': '#dc3545',
            'payment_fraud': '#dc3545',
            'spam': '#6c757d',
        }
        
        color = reason_colors.get(obj.reason, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>',
            color,
            obj.get_reason_display()
        )
    reason_badge.short_description = 'Reason'
    
    def status_indicator(self, obj):
        """Display active status"""
        if obj.is_active:
            return format_html(
                '<div style="text-align: center;">'
                '<div style="width: 12px; height: 12px; background: #dc3545; border-radius: 50%; '
                'margin: 0 auto 5px auto; animation: pulse 2s infinite;"></div>'
                '<div style="font-size: 10px; color: #dc3545; font-weight: 600;">ACTIVE</div>'
                '</div>'
                '<style>@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}</style>'
            )
        return format_html(
            '<div style="text-align: center;">'
            '<div style="width: 12px; height: 12px; background: #6c757d; border-radius: 50%; '
            'margin: 0 auto 5px auto;"></div>'
            '<div style="font-size: 10px; color: #6c757d; font-weight: 600;">INACTIVE</div>'
            '</div>'
        )
    status_indicator.short_description = 'Active'
    
    def time_remaining_display(self, obj):
        """Display time remaining"""
        if obj.is_permanent:
            return format_html(
                '<div style="text-align: center; color: #dc3545; font-weight: 600;">'
                '<div style="font-size: 20px;">∞</div>'
                '<div style="font-size: 9px;">PERMANENT</div>'
                '</div>'
            )
        
        time_left = obj.time_remaining()
        
        return format_html(
            '<div style="text-align: center; font-size: 11px; font-weight: 600; color: #ffc107;">{}</div>',
            time_left
        )
    time_remaining_display.short_description = 'Time Left'
    
    def banned_by_display(self, obj):
        """Display who banned"""
        if not obj.banned_by:
            return format_html('<span style="color: #6c757d;">System</span>')
        
        return format_html(
            '<div style="font-size: 11px;">{}</div>',
            obj.banned_by.username
        )
    banned_by_display.short_description = 'Banned By'
    
    def created_display(self, obj):
        """Display creation time"""
        time_ago = timezone.now() - obj.created_at
        
        if time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m ago'
        elif time_ago < timedelta(days=1):
            display = f'{int(time_ago.total_seconds() / 3600)}h ago'
        else:
            display = f'{time_ago.days}d ago'
        
        return format_html(
            '<div style="font-size: 11px; color: #6c757d;">{}</div>',
            display
        )
    created_display.short_description = 'Created'
    
    def quick_actions(self, obj):
        """Quick action buttons"""
        if obj.is_active:
            return format_html(
                '<a href="#" class="button" style="background: #28a745; color: white; '
                'font-size: 10px; padding: 4px 8px;">Unban</a>'
            )
        return format_html('<span style="color: #6c757d;">—</span>')
    quick_actions.short_description = 'Actions'
    
    # ==================== Readonly Fields ====================
    
    def ban_overview(self, obj):
        """Ban overview"""
        if obj.is_permanent:
            bg_gradient = 'linear-gradient(135deg, #ff0844 0%, #ffb199 100%)'
        elif obj.is_active:
            bg_gradient = 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'
        else:
            bg_gradient = 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)'
        
        html = f'<div style="background: {bg_gradient}; padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += '<div style="display: flex; justify-content: space-between; align-items: center;">'
        html += '<div>'
        html += f'<h2 style="margin: 0;">User Ban</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 16px;">{obj.user.username}</p>'
        html += '</div>'
        
        # Status badge
        icon = '🔒' if obj.is_permanent else '⏳' if obj.is_active else '[OK]'
        status = 'PERMANENT' if obj.is_permanent else 'ACTIVE' if obj.is_active else 'EXPIRED'
        
        html += f'<div style="background: rgba(255,255,255,0.2); padding: 20px; border-radius: 50%; '
        html += f'width: 80px; height: 80px; display: flex; flex-direction: column; align-items: center; justify-content: center;">'
        html += f'<div style="font-size: 32px;">{icon}</div>'
        html += f'<div style="font-size: 9px; margin-top: 3px;">{status}</div>'
        html += '</div>'
        html += '</div>'
        
        # Stats
        html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Reason', obj.get_reason_display()),
            ('Banned By', obj.banned_by.username if obj.banned_by else 'System'),
            ('Created', obj.created_at.strftime('%b %d, %Y')),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    ban_overview.short_description = ''
    
    def ban_timeline(self, obj):
        """Ban timeline"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        
        if obj.is_permanent:
            html += '<div style="text-align: center; padding: 30px;">'
            html += '<div style="font-size: 64px; margin-bottom: 15px;">🔒</div>'
            html += '<h3 style="margin: 0; color: #dc3545;">PERMANENT BAN</h3>'
            html += '<p style="margin: 10px 0 0 0; color: #6c757d;">This ban has no expiration date</p>'
            html += '</div>'
        else:
            html += '<h4 style="margin-top: 0;">⏳ Ban Duration</h4>'
            
            # Time calculation
            if obj.banned_until:
                now = timezone.now()
                total_duration = obj.banned_until - obj.created_at
                elapsed = now - obj.created_at
                remaining = obj.banned_until - now
                
                if remaining.total_seconds() > 0:
                    percentage = (elapsed.total_seconds() / total_duration.total_seconds()) * 100
                    
                    days = remaining.days
                    hours = int((remaining.total_seconds() % 86400) / 3600)
                    minutes = int((remaining.total_seconds() % 3600) / 60)
                    
                    # Countdown
                    html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px;">'
                    countdown_items = [
                        (days, 'Days'),
                        (hours, 'Hours'),
                        (minutes, 'Minutes'),
                    ]
                    
                    for value, label in countdown_items:
                        html += '<div style="background: white; padding: 15px; border-radius: 8px; text-align: center; border: 2px solid #e9ecef;">'
                        html += f'<div style="font-size: 32px; font-weight: bold; color: #ffc107;">{value:02d}</div>'
                        html += f'<div style="font-size: 11px; color: #6c757d; margin-top: 5px;">{label}</div>'
                        html += '</div>'
                    
                    html += '</div>'
                    
                    # Progress bar
                    bar_color = '#28a745' if percentage < 30 else '#ffc107' if percentage < 70 else '#dc3545'
                    
                    html += '<div style="margin-bottom: 10px;">'
                    html += f'<div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 12px;">'
                    html += f'<span>Ban Progress</span><span>{percentage:.1f}%</span>'
                    html += '</div>'
                    html += '<div style="background: #e9ecef; border-radius: 10px; height: 12px; overflow: hidden;">'
                    html += f'<div style="background: {bar_color}; width: {percentage}%; height: 100%; border-radius: 10px;"></div>'
                    html += '</div>'
                    html += '</div>'
                    
                    # Dates
                    html += f'<div style="text-align: center; color: #6c757d; font-size: 12px; margin-top: 15px;">'
                    html += f'Expires: <strong>{obj.banned_until.strftime("%B %d, %Y at %H:%M")}</strong>'
                    html += '</div>'
                else:
                    html += '<div style="text-align: center; padding: 20px; background: #d4edda; border-radius: 5px;">'
                    html += '<div style="font-size: 48px; margin-bottom: 10px;">[OK]</div>'
                    html += '<h4 style="margin: 0; color: #155724;">Ban Expired</h4>'
                    html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    ban_timeline.short_description = '⏰ Timeline'
    
    def appeal_info(self, obj):
        """Appeal information"""
        if not obj.can_appeal:
            return format_html(
                '<div style="background: #f8d7da; padding: 15px; border-radius: 5px; text-align: center;">'
                '<div style="font-size: 32px; margin-bottom: 10px;">🚫</div>'
                '<strong style="color: #721c24;">Appeals Not Allowed</strong>'
                '</div>'
            )
        
        if not obj.appeal_text:
            return format_html(
                '<div style="background: #d1ecf1; padding: 15px; border-radius: 5px; text-align: center;">'
                '<div style="font-size: 32px; margin-bottom: 10px;">[NOTE]</div>'
                '<strong style="color: #0c5460;">No Appeal Submitted</strong>'
                '</div>'
            )
        
        status_config = {
            'pending': ('#ffc107', '⏳', 'Pending Review'),
            'approved': ('#28a745', '[OK]', 'Approved'),
            'rejected': ('#dc3545', '[ERROR]', 'Rejected'),
        }
        
        color, icon, label = status_config.get(obj.appeal_status, ('#6c757d', '•', 'Unknown'))
        
        html = f'<div style="background: {color}20; border-left: 4px solid {color}; padding: 15px; border-radius: 5px;">'
        html += f'<div style="font-size: 32px; margin-bottom: 10px;">{icon}</div>'
        html += f'<strong style="color: {color};">Appeal Status: {label}</strong>'
        
        if obj.appeal_reviewed_by:
            html += f'<div style="margin-top: 10px; font-size: 12px;">Reviewed by: {obj.appeal_reviewed_by.username}</div>'
        
        if obj.appeal_reviewed_at:
            html += f'<div style="font-size: 12px;">On: {obj.appeal_reviewed_at.strftime("%B %d, %Y")}</div>'
        
        html += '</div>'
        
        return format_html(html)
    appeal_info.short_description = 'Appeal Status'
    
    # ==================== Actions ====================
    
    def unban_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} users unbanned.')
    unban_users.short_description = '[OK] Unban users'
    
    def make_permanent(self, request, queryset):
        count = queryset.update(is_permanent=True, banned_until=None)
        self.message_user(request, f'{count} bans made permanent.')
    make_permanent.short_description = '🔒 Make permanent'
    
    def extend_ban(self, request, queryset):
        """Extend ban by 30 days"""
        for ban in queryset.filter(is_permanent=False):
            if ban.banned_until:
                ban.banned_until = ban.banned_until + timedelta(days=30)
                ban.save()
        
        self.message_user(request, f'{queryset.count()} bans extended by 30 days.')
    extend_ban.short_description = '⏰ Extend by 30 days'
    
    def approve_appeals(self, request, queryset):
        count = queryset.filter(appeal_text__isnull=False).update(
            appeal_status='approved',
            appeal_reviewed_by=request.user,
            appeal_reviewed_at=timezone.now(),
            is_active=False
        )
        self.message_user(request, f'{count} appeals approved.')
    approve_appeals.short_description = '[OK] Approve appeals'
    
    def reject_appeals(self, request, queryset):
        count = queryset.filter(appeal_text__isnull=False).update(
            appeal_status='rejected',
            appeal_reviewed_by=request.user,
            appeal_reviewed_at=timezone.now()
        )
        self.message_user(request, f'{count} appeals rejected.')
    reject_appeals.short_description = '[ERROR] Reject appeals'


# ==================== Click Tracker Admin ====================

@admin.register(ClickTracker)
class ClickTrackerAdmin(admin.ModelAdmin):
    list_display = [
        'action_badge',
        'user_link',
        'action_type_badge',
        'device_display',
        'ip_display',
        'fast_clicking_indicator',
        'time_display',
    ]
    
    list_filter = [
        'action_type',
        'clicked_at',
    ]
    
    search_fields = [
        'user__username',
        'ip_address',
    ]
    
    readonly_fields = [
        'tracker_overview',
        'activity_pattern',
        'device_details',
        'clicked_at',
    ]
    
    fieldsets = (
        ('[STATS] Tracker Overview', {
            'fields': ('tracker_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Action Information', {
            'fields': (
                ('user', 'action_type'),
                'ip_address',
                'device_info',
            )
        }),
        
        ('📈 Activity Pattern', {
            'fields': (
                'activity_pattern',
            ),
            'classes': ('collapse',)
        }),
        
        ('📱 Device Details', {
            'fields': (
                'device_details',
            ),
            'classes': ('collapse',)
        }),
        
        ('[FIX] Metadata', {
            'fields': (
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        
        ('⏰ Timestamp', {
            'fields': (
                'clicked_at',
            )
        }),
    )
    
    date_hierarchy = 'clicked_at'
    
    actions = ['detect_fast_clickers', 'export_activity']
    
    # ==================== Display Methods ====================
    
    def action_badge(self, obj):
        """Display action badge"""
        action_icons = {
            'ad_click': '📢',
            'video_watch': '🎥',
            'task_complete': '[OK]',
            'withdrawal_request': '[MONEY]',
            'login': '[SECURE]',
            'api_call': '🔌',
        }
        
        icon = action_icons.get(obj.action_type, '•')
        
        return format_html(
            '<div style="text-align: center; font-size: 24px;">{}</div>',
            icon
        )
    action_badge.short_description = 'Type'
    
    def user_link(self, obj):
        """Display user link"""
        return format_html(
            '<a href="{}" style="font-weight: 600; font-size: 12px;">{}</a>',
            reverse('admin:users_user_change', args=[obj.user.pk]),
            obj.user.username
        )
    user_link.short_description = 'User'
    
    def action_type_badge(self, obj):
        """Display action type"""
        type_colors = {
            'ad_click': '#17a2b8',
            'video_watch': '#6f42c1',
            'task_complete': '#28a745',
            'withdrawal_request': '#ffc107',
            'login': '#fd7e14',
            'api_call': '#6c757d',
        }
        
        color = type_colors.get(obj.action_type, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>',
            color,
            obj.get_action_type_display()
        )
    action_type_badge.short_description = 'Action'
    
    def device_display(self, obj):
        """Display device info"""
        if not obj.device_info:
            return format_html('<span style="color: #6c757d;">—</span>')
        
        return format_html(
            '<div style="font-size: 11px;">{}</div>',
            obj.device_info.device_model[:20]
        )
    device_display.short_description = 'Device'
    
    def ip_display(self, obj):
        """Display IP address"""
        return format_html(
            '<div style="font-family: monospace; font-size: 11px; color: #495057;">{}</div>',
            obj.ip_address
        )
    ip_display.short_description = 'IP'
    
    def fast_clicking_indicator(self, obj):
        """Check if fast clicking"""
        is_fast = ClickTracker.check_fast_clicking(
            obj.user,
            obj.action_type,
            time_window=60,
            max_clicks=5
        )
        
        if is_fast:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 4px 8px; '
                'border-radius: 10px; font-size: 9px; font-weight: 600;">🚨 FAST</span>'
            )
        return format_html('<span style="color: #28a745;">✓ Normal</span>')
    fast_clicking_indicator.short_description = 'Speed'
    
    def time_display(self, obj):
        """Display time"""
        return format_html(
            '<div style="font-size: 11px; color: #6c757d;">{}</div>',
            obj.clicked_at.strftime('%H:%M:%S')
        )
    time_display.short_description = 'Time'
    
    # ==================== Readonly Fields ====================
    
    def tracker_overview(self, obj):
        """Tracker overview"""
        action_colors = {
            'ad_click': '#17a2b8',
            'video_watch': '#6f42c1',
            'task_complete': '#28a745',
            'withdrawal_request': '#ffc107',
            'login': '#fd7e14',
        }
        
        color = action_colors.get(obj.action_type, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); ' \
               'padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;">'
        
        html += f'<h2 style="margin: 0 0 10px 0;">Click Tracker #{obj.pk}</h2>'
        html += f'<p style="margin: 0; opacity: 0.9;">{obj.get_action_type_display()}</p>'
        
        html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 15px;">'
        
        stats = [
            ('User', obj.user.username),
            ('IP', obj.ip_address),
            ('Time', obj.clicked_at.strftime('%H:%M:%S')),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 6px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 3px;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    tracker_overview.short_description = ''
    
    def activity_pattern(self, obj):
        """Activity pattern analysis"""
        # Get recent actions from same user
        recent_time = timezone.now() - timedelta(hours=1)
        recent_actions = ClickTracker.objects.filter(
            user=obj.user,
            action_type=obj.action_type,
            clicked_at__gte=recent_time
        ).count()
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[STATS] Activity Pattern (Last Hour)</h4>'
        
        # Determine if pattern is suspicious
        if recent_actions > 10:
            bg_color = '#f8d7da'
            text_color = '#721c24'
            icon = '🚨'
            label = 'HIGH FREQUENCY (Suspicious)'
        elif recent_actions > 5:
            bg_color = '#fff3cd'
            text_color = '#856404'
            icon = '[WARN]'
            label = 'MODERATE FREQUENCY'
        else:
            bg_color = '#d4edda'
            text_color = '#155724'
            icon = '[OK]'
            label = 'NORMAL FREQUENCY'
        
        html += f'<div style="background: {bg_color}; color: {text_color}; padding: 15px; border-radius: 5px; text-align: center;">'
        html += f'<div style="font-size: 32px; margin-bottom: 10px;">{icon}</div>'
        html += f'<div style="font-size: 24px; font-weight: bold; margin-bottom: 5px;">{recent_actions}</div>'
        html += f'<div style="font-size: 12px; font-weight: 600;">{label}</div>'
        html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    activity_pattern.short_description = '📈 Pattern'
    
    def device_details(self, obj):
        """Device details"""
        if not obj.device_info:
            return format_html('<span style="color: #6c757d;">No device info</span>')
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        details = [
            ('Model', obj.device_info.device_model),
            ('Brand', obj.device_info.device_brand),
            ('Android', obj.device_info.android_version),
            ('Is Rooted', '[OK] Yes' if obj.device_info.is_rooted else '[ERROR] No'),
            ('Is Emulator', '[OK] Yes' if obj.device_info.is_emulator else '[ERROR] No'),
        ]
        
        for label, value in details:
            html += f'<tr><td style="padding: 5px 0; color: #6c757d;">{label}</td>'
            html += f'<td style="padding: 5px 0; text-align: right; font-weight: 600;">{value}</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    device_details.short_description = '📱 Device'
    
    # ==================== Actions ====================
    
    def detect_fast_clickers(self, request, queryset):
        """Detect fast clicking patterns"""
        suspicious_users = set()
        
        for tracker in queryset:
            is_fast = ClickTracker.check_fast_clicking(
                tracker.user,
                tracker.action_type,
                time_window=60,
                max_clicks=5
            )
            
            if is_fast:
                suspicious_users.add(tracker.user.username)
        
        if suspicious_users:
            self.message_user(
                request,
                f'Found {len(suspicious_users)} suspicious users: {", ".join(list(suspicious_users)[:5])}',
                level='warning'
            )
        else:
            self.message_user(request, 'No fast clicking detected.')
    detect_fast_clickers.short_description = '🔍 Detect fast clickers'
    
    def export_activity(self, request, queryset):
        self.message_user(request, 'Export feature coming soon.', level='info')
    export_activity.short_description = '📥 Export activity'
    
    
    
    
    # security/admin.py (continued)

# ==================== Maintenance Mode Admin ====================

@admin.register(MaintenanceMode)
class MaintenanceModeAdmin(admin.ModelAdmin):
    list_display = [
        'maintenance_badge',
        'status_indicator',
        'schedule_display',
        'admin_access_badge',
        'duration_display',
        'quick_toggle',
    ]
    
    list_filter = [
        'is_active',
        # 'allow_admin_access',
        'created_at',
    ]
    
    search_fields = [
        'reason',
        'message',
    ]
    
    readonly_fields = [
        'maintenance_overview',
        'schedule_timeline',
        'impact_analysis',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('[FIX] Maintenance Overview', {
            'fields': ('maintenance_overview',),
            'classes': ('wide',)
        }),
        
        ('⚙️ Settings', {
            'fields': (
                'is_active',
                'allow_admin_access',
            )
        }),
        
        ('📅 Schedule', {
            'fields': (
                'schedule_timeline',
                ('scheduled_start', 'scheduled_end'),
                ('actual_start', 'actual_end'),
            )
        }),
        
        ('[NOTE] Information', {
            'fields': (
                'reason',
                'message',
                'affected_services',
            )
        }),
        
        ('[STATS] Impact Analysis', {
            'fields': (
                'impact_analysis',
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_maintenance', 'deactivate_maintenance']
    
    # ==================== Display Methods ====================
    
    def maintenance_badge(self, obj):
        """Display maintenance badge"""
        if obj.is_active:
            return format_html(
                '<div style="text-align: center; background: linear-gradient(135deg, #ff0844 0%, #ffb199 100%); '
                'color: white; padding: 15px; border-radius: 10px;">'
                '<div style="font-size: 36px; margin-bottom: 5px;">[FIX]</div>'
                '<div style="font-size: 12px; font-weight: 600;">MAINTENANCE</div>'
                '<div style="font-size: 10px; opacity: 0.9; margin-top: 3px;">ACTIVE</div>'
                '</div>'
            )
        return format_html(
            '<div style="text-align: center; background: #f8f9fa; '
            'color: #6c757d; padding: 15px; border-radius: 10px; border: 2px dashed #dee2e6;">'
            '<div style="font-size: 36px; margin-bottom: 5px;">[OK]</div>'
            '<div style="font-size: 12px; font-weight: 600;">SYSTEM ONLINE</div>'
            '</div>'
        )
    maintenance_badge.short_description = 'Status'
    
    def status_indicator(self, obj):
        """Display status with animation"""
        if obj.is_active:
            return format_html(
                '<div style="text-align: center;">'
                '<div style="width: 16px; height: 16px; background: #dc3545; border-radius: 50%; '
                'margin: 0 auto 5px auto; animation: blink 1.5s infinite;"></div>'
                '<div style="font-size: 10px; color: #dc3545; font-weight: 600;">ACTIVE</div>'
                '</div>'
                '<style>@keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}</style>'
            )
        return format_html(
            '<div style="text-align: center;">'
            '<div style="width: 16px; height: 16px; background: #28a745; border-radius: 50%; '
            'margin: 0 auto 5px auto;"></div>'
            '<div style="font-size: 10px; color: #28a745; font-weight: 600;">INACTIVE</div>'
            '</div>'
        )
    status_indicator.short_description = 'Live Status'
    
    def schedule_display(self, obj):
        """Display schedule"""
        if not obj.scheduled_start:
            return format_html('<span style="color: #6c757d;">Not scheduled</span>')
        
        html = '<div style="font-size: 11px;">'
        html += f'<div><strong>Start:</strong> {obj.scheduled_start.strftime("%b %d, %H:%M")}</div>'
        
        if obj.scheduled_end:
            html += f'<div style="margin-top: 3px;"><strong>End:</strong> {obj.scheduled_end.strftime("%b %d, %H:%M")}</div>'
        
        html += '</div>'
        
        return format_html(html)
    schedule_display.short_description = 'Schedule'
    
    def admin_access_badge(self, obj):
        """Display admin access status"""
        if obj.allow_admin_access:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 10px;">✓ Allowed</span>'
            )
        return format_html(
            '<span style="background: #dc3545; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px;">✗ Blocked</span>'
        )
    admin_access_badge.short_description = 'Admin Access'
    
    def duration_display(self, obj):
        """Display duration"""
        if obj.actual_start and obj.actual_end:
            duration = obj.actual_end - obj.actual_start
            hours = int(duration.total_seconds() / 3600)
            minutes = int((duration.total_seconds() % 3600) / 60)
            return format_html(
                '<div style="text-align: center; font-size: 11px; color: #6c757d;">'
                '{}h {}m'
                '</div>',
                hours,
                minutes
            )
        elif obj.actual_start:
            duration = timezone.now() - obj.actual_start
            hours = int(duration.total_seconds() / 3600)
            minutes = int((duration.total_seconds() % 3600) / 60)
            return format_html(
                '<div style="text-align: center; font-size: 11px; color: #ffc107; font-weight: 600;">'
                '{}h {}m (ongoing)'
                '</div>',
                hours,
                minutes
            )
        return format_html('<span style="color: #6c757d;">—</span>')
    duration_display.short_description = 'Duration'
    
    def quick_toggle(self, obj):
        """Quick toggle button"""
        if obj.is_active:
            return format_html(
                '<a href="#" class="button" style="background: #28a745; color: white; '
                'font-size: 10px; padding: 5px 10px;">Deactivate</a>'
            )
        return format_html(
            '<a href="#" class="button" style="background: #dc3545; color: white; '
            'font-size: 10px; padding: 5px 10px;">Activate</a>'
        )
    quick_toggle.short_description = 'Toggle'
    
    # ==================== Readonly Fields ====================
    
    def maintenance_overview(self, obj):
        """Maintenance overview"""
        if obj.is_active:
            bg_gradient = 'linear-gradient(135deg, #ff0844 0%, #ffb199 100%)'
            status_text = '[FIX] MAINTENANCE MODE ACTIVE'
        else:
            bg_gradient = 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'
            status_text = '[OK] SYSTEM OPERATIONAL'
        
        html = f'<div style="background: {bg_gradient}; padding: 30px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += f'<div style="text-align: center; margin-bottom: 20px;">'
        html += f'<h2 style="margin: 0; font-size: 32px;">{status_text}</h2>'
        html += '</div>'
        
        # Stats grid
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px;">'
        
        # Calculate duration
        if obj.actual_start:
            if obj.actual_end:
                duration = obj.actual_end - obj.actual_start
                duration_text = f'{int(duration.total_seconds() / 3600)}h'
            else:
                duration = timezone.now() - obj.actual_start
                duration_text = f'{int(duration.total_seconds() / 3600)}h (ongoing)'
        else:
            duration_text = 'Not started'
        
        stats = [
            ('Status', 'Active' if obj.is_active else 'Inactive'),
            ('Admin Access', 'Allowed' if obj.allow_admin_access else 'Blocked'),
            ('Duration', duration_text),
            ('Services', len(obj.affected_services) if obj.affected_services else 0),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 11px; opacity: 0.9; margin-bottom: 5px;">{label}</div>'
            html += f'<div style="font-size: 18px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        
        # Warning message
        if obj.is_active:
            html += '<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center;">'
            html += '<strong>[WARN] WARNING:</strong> Users cannot access the system during maintenance'
            html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    maintenance_overview.short_description = ''
    
    def schedule_timeline(self, obj):
        """Schedule timeline"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">📅 Maintenance Timeline</h4>'
        
        # Timeline events
        events = []
        
        if obj.scheduled_start:
            events.append(('Scheduled Start', obj.scheduled_start, '#17a2b8'))
        
        if obj.actual_start:
            events.append(('Actual Start', obj.actual_start, '#28a745'))
        
        if obj.scheduled_end:
            events.append(('Scheduled End', obj.scheduled_end, '#ffc107'))
        
        if obj.actual_end:
            events.append(('Actual End', obj.actual_end, '#6c757d'))
        
        if events:
            html += '<table style="width: 100%; border-collapse: collapse;">'
            
            for label, timestamp, color in events:
                html += f'<tr>'
                html += f'<td style="padding: 10px 0; color: #6c757d; border-bottom: 1px solid #dee2e6; width: 40%;">'
                html += f'<div style="display: flex; align-items: center; gap: 10px;">'
                html += f'<div style="width: 12px; height: 12px; background: {color}; border-radius: 50%;"></div>'
                html += f'{label}'
                html += '</div>'
                html += '</td>'
                html += f'<td style="padding: 10px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #dee2e6; color: {color};">'
                html += timestamp.strftime('%B %d, %Y at %H:%M:%S')
                html += '</td>'
                html += '</tr>'
            
            html += '</table>'
        else:
            html += '<div style="text-align: center; padding: 20px; color: #6c757d;">No timeline events recorded</div>'
        
        html += '</div>'
        
        return format_html(html)
    schedule_timeline.short_description = '📅 Timeline'
    
    def impact_analysis(self, obj):
        """Impact analysis"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[STATS] Impact Analysis</h4>'
        
        # Affected services
        if obj.affected_services:
            html += '<div style="margin-bottom: 20px;">'
            html += '<strong style="font-size: 13px;">Affected Services:</strong>'
            html += '<div style="display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px;">'
            
            for service in obj.affected_services:
                html += f'<span style="background: #dc3545; color: white; padding: 5px 12px; '
                html += f'border-radius: 12px; font-size: 11px; font-weight: 600;">{service}</span>'
            
            html += '</div>'
            html += '</div>'
        
        # Estimated metrics
        html += '<div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">'
        html += '<h5 style="margin: 0 0 10px 0;">[WARN] Estimated Impact</h5>'
        html += '<ul style="margin: 0; padding-left: 20px; font-size: 12px; color: #6c757d;">'
        html += '<li>All user access blocked (except admins if enabled)</li>'
        html += '<li>API endpoints unavailable</li>'
        html += '<li>Scheduled tasks paused</li>'
        html += '<li>Payment processing suspended</li>'
        html += '</ul>'
        html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    impact_analysis.short_description = '[STATS] Impact'
    
    # ==================== Actions ====================
    
    def activate_maintenance(self, request, queryset):
        """Activate maintenance mode"""
        count = queryset.update(
            is_active=True,
            actual_start=timezone.now()
        )
        self.message_user(
            request,
            f'{count} maintenance mode(s) activated. Users cannot access the system.',
            level='warning'
        )
    activate_maintenance.short_description = '[FIX] Activate maintenance'
    
    def deactivate_maintenance(self, request, queryset):
        """Deactivate maintenance mode"""
        count = queryset.update(
            is_active=False,
            actual_end=timezone.now()
        )
        self.message_user(request, f'{count} maintenance mode(s) deactivated. System is now accessible.')
    deactivate_maintenance.short_description = '[OK] Deactivate maintenance'


# ==================== App Version Admin ====================

@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = [
        'version_badge',
        'supported_platforms',
        'current_indicator',
        'version_info',
        'is_mandatory',
        'release_date_display',
        'release_type',
    ]
    
    list_filter = [
        'supported_platforms',
        'is_active',
        'is_mandatory',
        'is_active',
        'release_date',
    ]
    
    search_fields = [
        'version_name',
        'version_code',
        'release_notes',
    ]
    
    readonly_fields = [
        'version_overview',
        'compatibility_info',
        'update_statistics',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('📱 Version Overview', {
            'fields': ('version_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Version Information', {
            'fields': (
                'platform',
                ('version_name', 'version_code'),
                ('min_supported_version', 'min_supported_code'),
            )
        }),
        
        ('⚙️ Settings', {
            'fields': (
                ('is_current', 'is_active'),
                'force_update',
                'update_priority',
            )
        }),
        
        ('[NOTE] Release Information', {
            'fields': (
                'release_date',
                'release_notes',
                'changelog',
            )
        }),
        
        ('🔗 Download Links', {
            'fields': (
                'download_url',
                'apk_url',
            ),
            'classes': ('collapse',)
        }),
        
        ('[STATS] Compatibility', {
            'fields': (
                'compatibility_info',
                'min_os_version',
                'supported_devices',
            ),
            'classes': ('collapse',)
        }),
        
        ('📈 Statistics', {
            'fields': (
                'update_statistics',
                'download_count',
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'set_as_current',
        'enable_force_update',
        'disable_force_update',
        'mark_as_deprecated',
    ]
    
    # ==================== Display Methods ====================
    
    def version_badge(self, obj):
        """Display version badge"""
        platform_colors = {
            'android': '#3DDC84',
            'ios': '#000000',
            'web': '#61DAFB',
        }
        
        platform_icons = {
            'android': '🤖',
            'ios': '🍎',
            'web': '🌐',
        }
        
        color = platform_colors.get(obj.platform, '#6c757d')
        icon = platform_icons.get(obj.platform, '📱')
        
        return format_html(
            '<div style="background: {}; color: white; padding: 15px; border-radius: 10px; text-align: center;">'
            '<div style="font-size: 28px; margin-bottom: 5px;">{}</div>'
            '<div style="font-size: 16px; font-weight: bold;">{}</div>'
            '<div style="font-size: 11px; opacity: 0.9; margin-top: 3px;">v{}</div>'
            '</div>',
            color,
            icon,
            obj.version_code,
            obj.version_name
        )
    version_badge.short_description = 'Version'
    
    def platform_badge(self, obj):
        """Display platform"""
        platform_config = {
            'android': ('#3DDC84', '🤖'),
            'ios': ('#000000', '🍎'),
            'web': ('#61DAFB', '🌐'),
        }
        
        color, icon = platform_config.get(obj.platform, ('#6c757d', '📱'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 32px; margin-bottom: 5px;">{}</div>'
            '<span style="background: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>'
            '</div>',
            icon,
            color,
            obj.get_platform_display().upper()
        )
    platform_badge.short_description = 'Platform'
    
    def current_indicator(self, obj):
        """Display if current version"""
        if obj.is_current:
            return format_html(
                '<div style="text-align: center;">'
                '<div style="font-size: 24px; margin-bottom: 3px;">[STAR]</div>'
                '<span style="background: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 9px; font-weight: 600;">CURRENT</span>'
                '</div>'
            )
        return format_html(
            '<div style="text-align: center;">'
            '<span style="color: #6c757d; font-size: 10px;">Older</span>'
            '</div>'
        )
    current_indicator.short_description = 'Current'
    
    def version_info(self, obj):
        """Display version info"""
        html = '<div style="font-size: 11px;">'
        html += f'<div><strong>Name:</strong> {obj.version_name}</div>'
        html += f'<div style="margin-top: 3px;"><strong>Code:</strong> {obj.version_code}</div>'
        
        if obj.min_supported_version:
            html += f'<div style="margin-top: 3px; color: #6c757d;"><strong>Min:</strong> {obj.min_supported_version}</div>'
        
        html += '</div>'
        
        return format_html(html)
    version_info.short_description = 'Info'
    
    def force_update_badge(self, obj):
        """Display force update status"""
        if obj.force_update:
            return format_html(
                '<div style="text-align: center;">'
                '<div style="font-size: 20px; margin-bottom: 3px;">[WARN]</div>'
                '<span style="background: #dc3545; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 9px; font-weight: 600;">FORCE UPDATE</span>'
                '</div>'
            )
        return format_html(
            '<div style="text-align: center;">'
            '<span style="color: #28a745; font-size: 10px;">✓ Optional</span>'
            '</div>'
        )
    force_update_badge.short_description = 'Update Type'
    
    def release_date_display(self, obj):
        """Display release date"""
        if not obj.release_date:
            return format_html('<span style="color: #6c757d;">Not set</span>')
        
        time_ago = timezone.now() - obj.release_date
        
        if time_ago < timedelta(days=7):
            color = '#28a745'
            label = 'NEW'
        elif time_ago < timedelta(days=30):
            color = '#17a2b8'
            label = 'RECENT'
        else:
            color = '#6c757d'
            label = 'OLD'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 11px; color: {}; font-weight: 600; margin-bottom: 3px;">{}</div>'
            '<div style="font-size: 10px; color: #6c757d;">{}</div>'
            '</div>',
            color,
            label,
            obj.release_date.strftime('%b %d, %Y')
        )
    release_date_display.short_description = 'Released'
    
    def status_badge(self, obj):
        """Display status"""
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 10px;">✓ ACTIVE</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px;">✗ INACTIVE</span>'
        )
    status_badge.short_description = 'Status'
    
    # ==================== Readonly Fields ====================
    
    def version_overview(self, obj):
        """Version overview"""
        platform_colors = {
            'android': '#3DDC84',
            'ios': '#000000',
            'web': '#61DAFB',
        }
        
        color = platform_colors.get(obj.platform, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); ' \
               'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += '<div style="display: flex; justify-content: space-between; align-items: center;">'
        html += '<div>'
        html += f'<h2 style="margin: 0; font-size: 32px;">Version {obj.version_name}</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 16px;">{obj.get_platform_display()}</p>'
        html += '</div>'
        
        # Badge
        if obj.is_current:
            icon = '[STAR]'
            label = 'CURRENT'
        elif obj.force_update:
            icon = '[WARN]'
            label = 'FORCE UPDATE'
        else:
            icon = '📦'
            label = 'AVAILABLE'
        
        html += f'<div style="background: rgba(255,255,255,0.2); padding: 20px; border-radius: 50%; '
        html += f'width: 90px; height: 90px; display: flex; flex-direction: column; align-items: center; justify-content: center;">'
        html += f'<div style="font-size: 36px;">{icon}</div>'
        html += f'<div style="font-size: 9px; margin-top: 3px;">{label}</div>'
        html += '</div>'
        html += '</div>'
        
        # Stats
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Version Code', obj.version_code),
            ('Downloads', f'{obj.download_count:,}'),
            ('Min Version', obj.min_supported_version or 'N/A'),
            ('Priority', obj.get_update_priority_display()),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9; margin-bottom: 5px;">{label}</div>'
            html += f'<div style="font-size: 16px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    version_overview.short_description = ''
    
    def compatibility_info(self, obj):
        """Compatibility information"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[FIX] Compatibility Information</h4>'
        
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        compat_data = [
            ('Platform', obj.get_platform_display()),
            ('Version Name', obj.version_name),
            ('Version Code', obj.version_code),
            ('Minimum Supported', f'{obj.min_supported_version} (Code: {obj.min_supported_code})' if obj.min_supported_version else 'Not set'),
            ('Min OS Version', obj.min_os_version or 'Not specified'),
            ('Supported Devices', ', '.join(obj.supported_devices) if obj.supported_devices else 'All devices'),
        ]
        
        for label, value in compat_data:
            html += f'<tr><td style="padding: 8px 0; color: #6c757d; border-bottom: 1px solid #dee2e6;">{label}</td>'
            html += f'<td style="padding: 8px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #dee2e6;">{value}</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    compatibility_info.short_description = '[FIX] Compatibility'
    
    def update_statistics(self, obj):
        """Update statistics"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[STATS] Update Statistics</h4>'
        
        # Download stats
        html += '<div style="background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #17a2b8;">'
        html += '<div style="display: flex; justify-content: space-between; align-items: center;">'
        html += '<div>'
        html += '<div style="font-size: 12px; color: #6c757d; margin-bottom: 5px;">Total Downloads</div>'
        html += f'<div style="font-size: 32px; font-weight: bold; color: #17a2b8;">{obj.download_count:,}</div>'
        html += '</div>'
        html += '<div style="font-size: 48px;">📥</div>'
        html += '</div>'
        html += '</div>'
        
        # Update priority
        priority_colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545',
        }
        
        priority_color = priority_colors.get(obj.update_priority, '#6c757d')
        
        html += f'<div style="background: {priority_color}20; border-left: 4px solid {priority_color}; padding: 15px; border-radius: 5px;">'
        html += f'<strong style="color: {priority_color};">Update Priority: {obj.get_update_priority_display().upper()}</strong>'
        html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    update_statistics.short_description = '[STATS] Statistics'
    
    # ==================== Actions ====================
    
    def set_as_current(self, request, queryset):
        """Set as current version"""
        for version in queryset:
            # Unset other current versions for same platform
            AppVersion.objects.filter(
                platform=version.platform,
                is_current=True
            ).exclude(pk=version.pk).update(is_current=False)
            
            # Set this as current
            version.is_current = True
            version.save()
        
        self.message_user(request, f'{queryset.count()} version(s) set as current.')
    set_as_current.short_description = '[STAR] Set as current version'
    
    def enable_force_update(self, request, queryset):
        count = queryset.update(force_update=True)
        self.message_user(
            request,
            f'{count} version(s) now require force update. Users must update to continue.',
            level='warning'
        )
    enable_force_update.short_description = '[WARN] Enable force update'
    
    def disable_force_update(self, request, queryset):
        count = queryset.update(force_update=False)
        self.message_user(request, f'{count} version(s) force update disabled.')
    disable_force_update.short_description = '✓ Disable force update'
    
    def mark_as_deprecated(self, request, queryset):
        count = queryset.update(is_active=False, is_current=False)
        self.message_user(request, f'{count} version(s) marked as deprecated.')
    mark_as_deprecated.short_description = '[DELETE] Mark as deprecated'
    
    
    
    # security/admin.py (continued)

# ==================== IP Blacklist Admin ====================

@admin.register(IPBlacklist)
class IPBlacklistAdmin(admin.ModelAdmin):
    list_display = [
        'ip_badge',
        'reason_badge',
        'status_indicator',
        'block_count_display',
        'created_by_display',
        'created_display',
        'quick_actions',
    ]
    
    list_filter = [
        'reason',
        # 'is_active',
        # 'created_at',
    ]
    
    search_fields = [
        'ip_address',
        'description',
        'created_by__username',
    ]
    
    readonly_fields = [
        'blacklist_overview',
        'block_statistics',
        'related_activities',
        # 'created_at',
        # 'updated_at',
    ]
    
    fieldsets = (
        ('🚫 IP Blacklist Overview', {
            'fields': ('blacklist_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 IP Information', {
            'fields': (
                'ip_address',
                'reason',
                'description',
            )
        }),
        
        ('⚙️ Settings', {
            'fields': (
                'is_active',
                'created_by',
            )
        }),
        
        ('[STATS] Statistics', {
            'fields': (
                'block_statistics',
                'block_count',
            ),
            'classes': ('collapse',)
        }),
        
        ('🔗 Related Activities', {
            'fields': (
                'related_activities',
            ),
            'classes': ('collapse',)
        }),
        
        ('[FIX] Metadata', {
            'fields': (
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_ips',
        'deactivate_ips',
        'export_blacklist',
        'check_duplicates',
    ]
    
    # date_hierarchy = 'created_at'
    
    # ==================== Display Methods ====================
    
    def ip_badge(self, obj):
        """Display IP address badge"""
        return format_html(
            '<div style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); '
            'color: white; padding: 12px; border-radius: 8px; text-align: center;">'
            '<div style="font-size: 20px; margin-bottom: 5px;">🚫</div>'
            '<div style="font-family: monospace; font-weight: bold; font-size: 13px;">{}</div>'
            '</div>',
            obj.ip_address
        )
    ip_badge.short_description = 'IP Address'
    
    def reason_badge(self, obj):
        """Display reason badge"""
        reason_config = {
            'spam': ('#6c757d', '📧'),
            'fraud': ('#dc3545', '🚨'),
            'abuse': ('#e83e8c', '[WARN]'),
            'bot': ('#6f42c1', '🤖'),
            'ddos': ('#fd7e14', '💥'),
            'hacking': ('#dc3545', '🔓'),
            'vpn_abuse': ('#17a2b8', '[SECURE]'),
            'multiple_accounts': ('#ffc107', '👥'),
        }
        
        color, icon = reason_config.get(obj.reason, ('#6c757d', '•'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 28px; margin-bottom: 5px;">{}</div>'
            '<span style="background: {}; color: white; padding: 4px 12px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>'
            '</div>',
            icon,
            color,
            obj.get_reason_display()
        )
    reason_badge.short_description = 'Reason'
    
    def status_indicator(self, obj):
        """Display status with animation"""
        if obj.is_active:
            return format_html(
                '<div style="text-align: center;">'
                '<div style="width: 14px; height: 14px; background: #dc3545; border-radius: 50%; '
                'margin: 0 auto 5px auto; box-shadow: 0 0 8px rgba(220, 53, 69, 0.6);"></div>'
                '<div style="font-size: 10px; color: #dc3545; font-weight: 600;">ACTIVE</div>'
                '</div>'
            )
        return format_html(
            '<div style="text-align: center;">'
            '<div style="width: 14px; height: 14px; background: #6c757d; border-radius: 50%; '
            'margin: 0 auto 5px auto;"></div>'
            '<div style="font-size: 10px; color: #6c757d; font-weight: 600;">INACTIVE</div>'
            '</div>'
        )
    status_indicator.short_description = 'Status'
    
    def block_count_display(self, obj):
        """Display block count"""
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px; font-weight: bold; color: #dc3545;">{}</div>'
            '<div style="font-size: 9px; color: #6c757d;">BLOCKS</div>'
            '</div>',
            obj.block_count
        )
    block_count_display.short_description = 'Blocks'
    
    def created_by_display(self, obj):
        """Display who created"""
        if not obj.created_by:
            return format_html('<span style="color: #6c757d; font-size: 11px;">System</span>')
        
        return format_html(
            '<div style="font-size: 11px;">{}</div>',
            obj.created_by.username
        )
    created_by_display.short_description = 'Created By'
    
    def created_display(self, obj):
        """Display creation time"""
        time_ago = timezone.now() - obj.created_at
        
        if time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m ago'
            color = '#dc3545'
        elif time_ago < timedelta(days=1):
            display = f'{int(time_ago.total_seconds() / 3600)}h ago'
            color = '#ffc107'
        else:
            display = f'{time_ago.days}d ago'
            color = '#6c757d'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-size: 11px; font-weight: 600;">{}</div>',
            color,
            display
        )
    created_display.short_description = 'Created'
    
    def quick_actions(self, obj):
        """Quick action buttons"""
        if obj.is_active:
            return format_html(
                '<a href="#" class="button" style="background: #28a745; color: white; '
                'font-size: 10px; padding: 4px 8px;">Unblock</a>'
            )
        return format_html(
            '<a href="#" class="button" style="background: #dc3545; color: white; '
            'font-size: 10px; padding: 4px 8px;">Block</a>'
        )
    quick_actions.short_description = 'Actions'
    
    # ==================== Readonly Fields ====================
    
    def blacklist_overview(self, obj):
        """Blacklist overview"""
        html = '<div style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); ' \
               'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += '<div style="display: flex; justify-content: space-between; align-items: center;">'
        html += '<div>'
        html += '<h2 style="margin: 0; font-size: 28px;">IP Blacklist Entry</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 18px; font-family: monospace;">{obj.ip_address}</p>'
        html += '</div>'
        
        # Status badge
        icon = '🚫' if obj.is_active else '[OK]'
        status = 'BLOCKED' if obj.is_active else 'UNBLOCKED'
        
        html += f'<div style="background: rgba(255,255,255,0.2); padding: 20px; border-radius: 50%; '
        html += f'width: 90px; height: 90px; display: flex; flex-direction: column; align-items: center; justify-content: center;">'
        html += f'<div style="font-size: 36px;">{icon}</div>'
        html += f'<div style="font-size: 9px; margin-top: 3px;">{status}</div>'
        html += '</div>'
        html += '</div>'
        
        # Stats
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Reason', obj.get_reason_display()),
            ('Blocks', f'{obj.block_count:,}'),
            ('Created By', obj.created_by.username if obj.created_by else 'System'),
            ('Status', 'Active' if obj.is_active else 'Inactive'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9; margin-bottom: 5px;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    blacklist_overview.short_description = ''
    
    def block_statistics(self, obj):
        """Block statistics"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[STATS] Block Statistics</h4>'
        
        # Block count visualization
        html += '<div style="background: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 15px; border-left: 4px solid #dc3545;">'
        html += '<div style="font-size: 48px; font-weight: bold; color: #dc3545; margin-bottom: 10px;">'
        html += f'{obj.block_count:,}'
        html += '</div>'
        html += '<div style="font-size: 14px; color: #6c757d;">Total Access Attempts Blocked</div>'
        html += '</div>'
        
        # Timeline
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        timeline_data = [
            ('First Blocked', obj.created_at.strftime('%B %d, %Y at %H:%M')),
            ('Last Updated', obj.updated_at.strftime('%B %d, %Y at %H:%M')),
            ('Days Blocked', (timezone.now() - obj.created_at).days),
        ]
        
        for label, value in timeline_data:
            html += f'<tr><td style="padding: 8px 0; color: #6c757d; border-bottom: 1px solid #dee2e6;">{label}</td>'
            html += f'<td style="padding: 8px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #dee2e6;">{value}</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    block_statistics.short_description = '[STATS] Statistics'
    
    def related_activities(self, obj):
        """Related security activities"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">🔗 Related Security Activities</h4>'
        
        # Get security logs for this IP
        security_logs = SecurityLog.objects.filter(ip_address=obj.ip_address).order_by('-created_at')[:10]
        
        if security_logs:
            html += '<table style="width: 100%; border-collapse: collapse;">'
            html += '<tr style="background: #dee2e6;"><th style="padding: 8px; text-align: left;">Type</th>'
            html += '<th style="padding: 8px;">Severity</th><th style="padding: 8px;">Date</th></tr>'
            
            for log in security_logs:
                severity_color = {
                    'low': '#28a745',
                    'medium': '#ffc107',
                    'high': '#fd7e14',
                    'critical': '#dc3545',
                }.get(log.severity, '#6c757d')
                
                html += f'<tr style="border-bottom: 1px solid #dee2e6;">'
                html += f'<td style="padding: 8px;">{log.get_security_type_display()}</td>'
                html += f'<td style="padding: 8px; text-align: center;"><span style="color: {severity_color}; font-weight: 600;">{log.severity}</span></td>'
                html += f'<td style="padding: 8px; text-align: center; font-size: 11px; color: #6c757d;">{log.created_at.strftime("%b %d, %H:%M")}</td>'
                html += '</tr>'
            
            html += '</table>'
        else:
            html += '<div style="text-align: center; padding: 20px; color: #6c757d;">No security activities recorded</div>'
        
        html += '</div>'
        
        return format_html(html)
    related_activities.short_description = '🔗 Activities'
    
    # ==================== Actions ====================
    
    def activate_ips(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} IP(s) activated (blocked).')
    activate_ips.short_description = '🚫 Activate (Block) IPs'
    
    def deactivate_ips(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} IP(s) deactivated (unblocked).')
    deactivate_ips.short_description = '[OK] Deactivate (Unblock) IPs'
    
    def export_blacklist(self, request, queryset):
        self.message_user(request, 'Export feature coming soon.', level='info')
    export_blacklist.short_description = '📥 Export blacklist'
    
    def check_duplicates(self, request, queryset):
        """Check for duplicate IPs"""
        from django.db.models import Count
        
        duplicates = IPBlacklist.objects.values('ip_address').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if duplicates:
            self.message_user(
                request,
                f'Found {duplicates.count()} duplicate IP(s) in blacklist.',
                level='warning'
            )
        else:
            self.message_user(request, 'No duplicate IPs found.')
    check_duplicates.short_description = '🔍 Check duplicates'


# ==================== Withdrawal Protection Admin ====================

@admin.register(WithdrawalProtection)
class WithdrawalProtectionAdmin(admin.ModelAdmin):
    list_display = [
        'withdrawal_badge',
        'user_display',
        'amount_display',
        'status_badge',
        'verification_progress',
        'risk_indicator',
        'created_display',
    ]
    
    list_filter = [
        # 'status',
        # 'requires_pin',
        # 'requires_2fa',
        # 'requires_device_verification',
        # 'vpn_detected',
        # 'suspicious_activity',
        'created_at',
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'withdrawal_id',
    ]
    
    readonly_fields = [
        'withdrawal_overview',
        'verification_checklist',
        'security_analysis',
        'device_info_display',
        'created_at',
        # 'verified_at',
        # 'approved_at',
    ]
    
    fieldsets = (
        ('[MONEY] Withdrawal Overview', {
            'fields': ('withdrawal_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Withdrawal Information', {
            'fields': (
                'user',
                'withdrawal_id',
                'amount',
                'status',
            )
        }),
        
        ('[OK] Verification Requirements', {
            'fields': (
                'verification_checklist',
                ('requires_pin', 'pin_verified'),
                ('requires_2fa', 'two_fa_verified'),
                ('requires_device_verification', 'device_verified'),
            )
        }),
        
        ('[SECURE] Security Analysis', {
            'fields': (
                'security_analysis',
                ('vpn_detected', 'suspicious_activity'),
                'device_info',
            ),
            'classes': ('collapse',)
        }),
        
        ('📱 Device Information', {
            'fields': (
                'device_info_display',
            ),
            'classes': ('collapse',)
        }),
        
        ('[FIX] Metadata', {
            'fields': (
                'metadata',
            ),
            'classes': ('collapse',)
        }),
        
        ('⏰ Timestamps', {
            'fields': (
                'created_at',
                'verified_at',
                'approved_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'approve_withdrawals',
        'reject_withdrawals',
        'require_additional_verification',
    ]
    
    date_hierarchy = 'created_at'
    
    # ==================== Display Methods ====================
    
    def withdrawal_badge(self, obj):
        """Display withdrawal badge"""
        return format_html(
            '<div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); '
            'color: white; padding: 12px; border-radius: 8px; text-align: center;">'
            '<div style="font-size: 24px; margin-bottom: 5px;">[MONEY]</div>'
            '<div style="font-size: 11px; font-weight: 600; font-family: monospace;">{}</div>'
            '</div>',
            obj.withdrawal_id[:12] + '...' if len(obj.withdrawal_id) > 12 else obj.withdrawal_id
        )
    withdrawal_badge.short_description = 'Withdrawal'
    
    def user_display(self, obj):
        """Display user"""
        return format_html(
            '<a href="{}" style="font-weight: 600; font-size: 12px;">{}</a>',
            reverse('admin:users_user_change', args=[obj.user.pk]),
            obj.user.username
        )
    user_display.short_description = 'User'
    
    def amount_display(self, obj):
        """Display amount"""
        return format_html(
            '<div style="text-align: center; font-size: 16px; font-weight: bold; color: #28a745;">৳{:,.2f}</div>',
            obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        """Display status"""
        status_config = {
            'pending': ('#ffc107', '⏳'),
            'verified': ('#17a2b8', '✓'),
            'approved': ('#28a745', '[OK]'),
            'rejected': ('#dc3545', '[ERROR]'),
            'processing': ('#6f42c1', '[LOADING]'),
        }
        
        color, icon = status_config.get(obj.status, ('#6c757d', '•'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 24px; margin-bottom: 3px;">{}</div>'
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 9px; font-weight: 600;">{}</span>'
            '</div>',
            icon,
            color,
            obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def verification_progress(self, obj):
        """Display verification progress"""
        total_checks = 0
        completed_checks = 0
        
        # Count required checks
        if obj.requires_pin:
            total_checks += 1
            if obj.pin_verified:
                completed_checks += 1
        
        if obj.requires_2fa:
            total_checks += 1
            if obj.two_fa_verified:
                completed_checks += 1
        
        if obj.requires_device_verification:
            total_checks += 1
            if obj.device_verified:
                completed_checks += 1
        
        if total_checks == 0:
            return format_html('<span style="color: #6c757d;">No checks required</span>')
        
        percentage = (completed_checks / total_checks) * 100
        
        if percentage == 100:
            color = '#28a745'
        elif percentage >= 50:
            color = '#ffc107'
        else:
            color = '#dc3545'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 14px; font-weight: bold; color: {};">{}/{}</div>'
            '<div style="font-size: 9px; color: #6c757d; margin-top: 2px;">VERIFIED</div>'
            '<div style="background: #e9ecef; border-radius: 10px; height: 4px; margin-top: 5px; overflow: hidden;">'
            '<div style="background: {}; width: {}%; height: 100%;"></div>'
            '</div>'
            '</div>',
            color,
            completed_checks,
            total_checks,
            color,
            percentage
        )
    verification_progress.short_description = 'Verification'
    
    def risk_indicator(self, obj):
        """Display risk indicator"""
        risk_factors = 0
        
        if obj.vpn_detected:
            risk_factors += 1
        if obj.suspicious_activity:
            risk_factors += 1
        if not obj.device_verified:
            risk_factors += 1
        
        if risk_factors >= 2:
            color = '#dc3545'
            icon = '🔴'
            label = 'HIGH'
        elif risk_factors == 1:
            color = '#ffc107'
            icon = '🟡'
            label = 'MEDIUM'
        else:
            color = '#28a745'
            icon = '🟢'
            label = 'LOW'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px; margin-bottom: 3px;">{}</div>'
            '<div style="color: {}; font-size: 10px; font-weight: 600;">{}</div>'
            '</div>',
            icon,
            color,
            label
        )
    risk_indicator.short_description = 'Risk'
    
    def created_display(self, obj):
        """Display creation time"""
        time_ago = timezone.now() - obj.created_at
        
        if time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m ago'
        elif time_ago < timedelta(days=1):
            display = f'{int(time_ago.total_seconds() / 3600)}h ago'
        else:
            display = f'{time_ago.days}d ago'
        
        return format_html(
            '<div style="font-size: 11px; color: #6c757d;">{}</div>',
            display
        )
    created_display.short_description = 'Created'
    
    # ==================== Readonly Fields ====================
    
    def withdrawal_overview(self, obj):
        """Withdrawal overview"""
        status_colors = {
            'pending': '#ffc107',
            'verified': '#17a2b8',
            'approved': '#28a745',
            'rejected': '#dc3545',
            'processing': '#6f42c1',
        }
        
        color = status_colors.get(obj.status, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); ' \
               'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += '<div style="display: flex; justify-content: space-between; align-items: center;">'
        html += '<div>'
        html += f'<h2 style="margin: 0; font-size: 28px;">Withdrawal Request</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">User: {obj.user.username}</p>'
        html += '</div>'
        
        # Amount badge
        html += f'<div style="background: rgba(255,255,255,0.2); padding: 20px; border-radius: 10px;">'
        html += f'<div style="font-size: 28px; font-weight: bold;">৳{obj.amount:,.2f}</div>'
        html += f'<div style="font-size: 10px; opacity: 0.9; text-align: center; margin-top: 3px;">AMOUNT</div>'
        html += '</div>'
        html += '</div>'
        
        # Stats
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Status', obj.get_status_display()),
            ('VPN', 'Detected' if obj.vpn_detected else 'Clean'),
            ('Suspicious', 'Yes' if obj.suspicious_activity else 'No'),
            ('Device', 'Verified' if obj.device_verified else 'Unverified'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9; margin-bottom: 5px;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    withdrawal_overview.short_description = ''
    
    def verification_checklist(self, obj):
        """Verification checklist"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[OK] Verification Checklist</h4>'
        
        checks = []
        
        if obj.requires_pin:
            checks.append(('PIN Verification', obj.pin_verified))
        
        if obj.requires_2fa:
            checks.append(('Two-Factor Authentication', obj.two_fa_verified))
        
        if obj.requires_device_verification:
            checks.append(('Device Verification', obj.device_verified))
        
        if not checks:
            html += '<div style="text-align: center; padding: 20px; color: #6c757d;">No verification required</div>'
        else:
            for label, verified in checks:
                if verified:
                    bg_color = '#d4edda'
                    text_color = '#155724'
                    icon = '[OK]'
                else:
                    bg_color = '#fff3cd'
                    text_color = '#856404'
                    icon = '⏳'
                
                html += f'<div style="background: {bg_color}; color: {text_color}; padding: 12px; '
                html += f'border-radius: 5px; margin-bottom: 10px; display: flex; align-items: center; gap: 10px;">'
                html += f'<div style="font-size: 24px;">{icon}</div>'
                html += f'<div style="flex: 1; font-weight: 600;">{label}</div>'
                html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    verification_checklist.short_description = '[OK] Checklist'
    
    def security_analysis(self, obj):
        """Security analysis"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[SECURE] Security Analysis</h4>'
        
        # Risk factors
        risk_factors = []
        
        if obj.vpn_detected:
            risk_factors.append(('VPN Detected', '#fd7e14', '[SECURE]'))
        
        if obj.suspicious_activity:
            risk_factors.append(('Suspicious Activity', '#dc3545', '🚨'))
        
        if not obj.device_verified:
            risk_factors.append(('Unverified Device', '#ffc107', '📱'))
        
        if risk_factors:
            for label, color, icon in risk_factors:
                html += f'<div style="background: {color}20; border-left: 4px solid {color}; '
                html += f'padding: 12px; border-radius: 5px; margin-bottom: 10px; display: flex; align-items: center; gap: 10px;">'
                html += f'<div style="font-size: 24px;">{icon}</div>'
                html += f'<div style="flex: 1; font-weight: 600; color: {color};">{label}</div>'
                html += '</div>'
        else:
            html += '<div style="background: #d4edda; padding: 15px; border-radius: 5px; text-align: center;">'
            html += '<div style="font-size: 32px; margin-bottom: 10px;">[OK]</div>'
            html += '<strong style="color: #155724;">No Security Concerns</strong>'
            html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    security_analysis.short_description = '[SECURE] Security'
    
    def device_info_display(self, obj):
        """Device information"""
        if not obj.device_info:
            return format_html('<span style="color: #6c757d;">No device information</span>')
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        device_data = [
            ('Model', obj.device_info.device_model),
            ('Brand', obj.device_info.device_brand),
            ('Android', obj.device_info.android_version),
            ('Is Rooted', '[OK] Yes' if obj.device_info.is_rooted else '[ERROR] No'),
            ('Is Emulator', '[OK] Yes' if obj.device_info.is_emulator else '[ERROR] No'),
            ('Risk Score', obj.device_info.risk_score),
        ]
        
        for label, value in device_data:
            html += f'<tr><td style="padding: 5px 0; color: #6c757d;">{label}</td>'
            html += f'<td style="padding: 5px 0; text-align: right; font-weight: 600;">{value}</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    device_info_display.short_description = '📱 Device'
    
    # ==================== Actions ====================
    
    def approve_withdrawals(self, request, queryset):
        count = queryset.update(
            status='approved',
            approved_at=timezone.now()
        )
        self.message_user(request, f'{count} withdrawal(s) approved.')
    approve_withdrawals.short_description = '[OK] Approve withdrawals'
    
    def reject_withdrawals(self, request, queryset):
        count = queryset.update(status='rejected')
        self.message_user(request, f'{count} withdrawal(s) rejected.')
    reject_withdrawals.short_description = '[ERROR] Reject withdrawals'
    
    def require_additional_verification(self, request, queryset):
        """Require additional verification"""
        count = queryset.update(
            requires_2fa=True,
            requires_device_verification=True
        )
        self.message_user(
            request,
            f'{count} withdrawal(s) now require additional verification.',
            level='warning'
        )
    require_additional_verification.short_description = '[SECURE] Require additional verification'
    
    
    
    
    # security/admin.py (continued)

# ==================== Risk Score Admin ====================

@admin.register(RiskScore)
class RiskScoreAdmin(admin.ModelAdmin):
    list_display = [
        'user_display',
        'risk_meter',
        'trend_indicator',
        'behavioral_summary',
        'threat_level_badge',
        'last_calculated',
    ]
    
    list_filter = [
        'calculated_at',
    ]
    
    search_fields = [
        'user__username',
        'user__email',
    ]
    
    readonly_fields = [
        'risk_overview',
        'risk_breakdown',
        'behavioral_analysis',
        'threat_timeline',
        'calculated_at',
    ]
    
    fieldsets = (
        ('[STATS] Risk Score Overview', {
            'fields': ('risk_overview',),
            'classes': ('wide',)
        }),
        
        ('👤 User', {
            'fields': ('user',)
        }),
        
        ('📈 Risk Scores', {
            'fields': (
                'risk_breakdown',
                ('current_score', 'previous_score'),
            )
        }),
        
        ('🎭 Behavioral Factors', {
            'fields': (
                'behavioral_analysis',
                ('login_frequency', 'device_diversity'),
                'location_diversity',
            ),
            'classes': ('collapse',)
        }),
        
        ('[WARN] Risk Factors', {
            'fields': (
                ('failed_login_attempts', 'suspicious_activities'),
                'vpn_usage_count',
            ),
            'classes': ('collapse',)
        }),
        
        ('⏰ Timeline', {
            'fields': (
                'threat_timeline',
                ('last_login_time', 'last_suspicious_activity'),
            ),
            'classes': ('collapse',)
        }),
        
        ('[INFO] System Info', {
            'fields': (
                'calculated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['recalculate_scores', 'reset_scores']
    
    # ==================== Display Methods ====================
    
    def user_display(self, obj):
        """Display user"""
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<div style="width: 32px; height: 32px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
            'border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; '
            'font-weight: bold; font-size: 14px;">{}</div>'
            '<div>'
            '<a href="{}" style="font-weight: 600; font-size: 12px;">{}</a><br/>'
            '<span style="font-size: 9px; color: #6c757d;">{}</span>'
            '</div>'
            '</div>',
            obj.user.username[0].upper(),
            reverse('admin:users_user_change', args=[obj.user.pk]),
            obj.user.username,
            obj.user.email
        )
    user_display.short_description = 'User'
    
    def risk_meter(self, obj):
        """Display risk meter"""
        score = obj.current_score
        
        if score >= 70:
            color = '#dc3545'
            emoji = '🔴'
            label = 'CRITICAL'
        elif score >= 50:
            color = '#fd7e14'
            emoji = '🟠'
            label = 'HIGH'
        elif score >= 30:
            color = '#ffc107'
            emoji = '🟡'
            label = 'MEDIUM'
        else:
            color = '#28a745'
            emoji = '🟢'
            label = 'LOW'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 32px; margin-bottom: 5px;">{}</div>'
            '<div style="font-size: 24px; font-weight: bold; color: {};">{}</div>'
            '<div style="font-size: 9px; color: {}; font-weight: 600; margin-top: 3px;">{}</div>'
            '</div>',
            emoji,
            color,
            score,
            color,
            label
        )
    risk_meter.short_description = 'Risk Score'
    
    def trend_indicator(self, obj):
        """Display trend"""
        change = obj.current_score - obj.previous_score
        
        if change > 0:
            color = '#dc3545'
            icon = '⬆️'
            label = f'+{change}'
        elif change < 0:
            color = '#28a745'
            icon = '⬇️'
            label = f'{change}'
        else:
            color = '#6c757d'
            icon = '➡️'
            label = '0'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px; margin-bottom: 3px;">{}</div>'
            '<div style="color: {}; font-weight: bold; font-size: 14px;">{}</div>'
            '</div>',
            icon,
            color,
            label
        )
    trend_indicator.short_description = 'Trend'
    
    def behavioral_summary(self, obj):
        """Display behavioral summary"""
        html = '<div style="font-size: 10px; line-height: 1.5;">'
        html += f'<div>[SECURE] Logins: <strong>{obj.login_frequency}/day</strong></div>'
        html += f'<div>📱 Devices: <strong>{obj.device_diversity}</strong></div>'
        html += f'<div>🌍 Locations: <strong>{obj.location_diversity}</strong></div>'
        html += '</div>'
        
        return format_html(html)
    behavioral_summary.short_description = 'Behavior'
    
    def threat_level_badge(self, obj):
        """Display threat level"""
        threats = obj.failed_login_attempts + obj.suspicious_activities + obj.vpn_usage_count
        
        if threats >= 10:
            color = '#dc3545'
            icon = '🚨'
            label = 'SEVERE'
        elif threats >= 5:
            color = '#fd7e14'
            icon = '[WARN]'
            label = 'HIGH'
        elif threats >= 2:
            color = '#ffc107'
            icon = '⚡'
            label = 'MODERATE'
        else:
            color = '#28a745'
            icon = '[OK]'
            label = 'LOW'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 24px; margin-bottom: 3px;">{}</div>'
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 9px; font-weight: 600;">{}</span>'
            '</div>',
            icon,
            color,
            label
        )
    threat_level_badge.short_description = 'Threats'
    
    def last_calculated(self, obj):
        """Display last calculation time"""
        time_ago = timezone.now() - obj.calculated_at
        
        if time_ago < timedelta(minutes=5):
            display = 'Just now'
            color = '#28a745'
        elif time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m ago'
            color = '#17a2b8'
        else:
            display = f'{int(time_ago.total_seconds() / 3600)}h ago'
            color = '#6c757d'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-size: 11px; font-weight: 600;">{}</div>',
            color,
            display
        )
    last_calculated.short_description = 'Calculated'
    
    # ==================== Readonly Fields ====================
    
    def risk_overview(self, obj):
        """Risk overview"""
        score = obj.current_score
        
        if score >= 70:
            bg_gradient = 'linear-gradient(135deg, #ff0844 0%, #ffb199 100%)'
        elif score >= 50:
            bg_gradient = 'linear-gradient(135deg, #ff6b6b 0%, #feca57 100%)'
        elif score >= 30:
            bg_gradient = 'linear-gradient(135deg, #feca57 0%, #48dbfb 100%)'
        else:
            bg_gradient = 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)'
        
        html = f'<div style="background: {bg_gradient}; padding: 30px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">'
        html += '<div>'
        html += f'<h2 style="margin: 0; font-size: 32px;">Risk Assessment</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 16px;">{obj.user.username}</p>'
        html += '</div>'
        
        # Score circle
        html += f'<div style="background: rgba(255,255,255,0.2); padding: 25px; border-radius: 50%; '
        html += f'width: 100px; height: 100px; display: flex; flex-direction: column; align-items: center; justify-content: center;">'
        html += f'<div style="font-size: 36px; font-weight: bold;">{score}</div>'
        html += f'<div style="font-size: 10px; opacity: 0.9;">RISK SCORE</div>'
        html += '</div>'
        html += '</div>'
        
        # Stats grid
        html += '<div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px;">'
        
        stats = [
            ('Login Freq', f'{obj.login_frequency}/d'),
            ('Devices', obj.device_diversity),
            ('Locations', obj.location_diversity),
            ('Failed Logins', obj.failed_login_attempts),
            ('Suspicious', obj.suspicious_activities),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9; margin-bottom: 5px;">{label}</div>'
            html += f'<div style="font-size: 16px; font-weight: bold;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        html += '</div>'
        
        return format_html(html)
    risk_overview.short_description = ''
    
    def risk_breakdown(self, obj):
        """Risk score breakdown"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[STATS] Risk Score Breakdown</h4>'
        
        # Score comparison
        html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">'
        
        # Current score
        current_color = '#dc3545' if obj.current_score >= 70 else '#ffc107' if obj.current_score >= 30 else '#28a745'
        html += f'<div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid {current_color};">'
        html += '<div style="font-size: 12px; color: #6c757d; margin-bottom: 5px;">Current Score</div>'
        html += f'<div style="font-size: 36px; font-weight: bold; color: {current_color};">{obj.current_score}</div>'
        html += '</div>'
        
        # Previous score
        prev_color = '#dc3545' if obj.previous_score >= 70 else '#ffc107' if obj.previous_score >= 30 else '#28a745'
        html += f'<div style="background: white; padding: 20px; border-radius: 8px; border-left: 4px solid {prev_color};">'
        html += '<div style="font-size: 12px; color: #6c757d; margin-bottom: 5px;">Previous Score</div>'
        html += f'<div style="font-size: 36px; font-weight: bold; color: {prev_color};">{obj.previous_score}</div>'
        html += '</div>'
        
        html += '</div>'
        
        # Change indicator
        change = obj.current_score - obj.previous_score
        if change > 0:
            change_color = '#dc3545'
            change_icon = '⬆️'
            change_text = f'Increased by {change} points'
        elif change < 0:
            change_color = '#28a745'
            change_icon = '⬇️'
            change_text = f'Decreased by {abs(change)} points'
        else:
            change_color = '#6c757d'
            change_icon = '➡️'
            change_text = 'No change'
        
        html += f'<div style="background: {change_color}20; border-left: 4px solid {change_color}; '
        html += f'padding: 15px; border-radius: 5px; display: flex; align-items: center; gap: 10px;">'
        html += f'<div style="font-size: 32px;">{change_icon}</div>'
        html += f'<div style="font-weight: 600; color: {change_color};">{change_text}</div>'
        html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    risk_breakdown.short_description = '[STATS] Breakdown'
    
    def behavioral_analysis(self, obj):
        """Behavioral analysis"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">🎭 Behavioral Analysis</h4>'
        
        behaviors = [
            ('Login Frequency', obj.login_frequency, 20, 'logins/day'),
            ('Device Diversity', obj.device_diversity, 5, 'devices'),
            ('Location Diversity', obj.location_diversity, 3, 'locations'),
        ]
        
        for label, value, threshold, unit in behaviors:
            percentage = min((value / threshold) * 100, 100)
            
            if percentage >= 70:
                bar_color = '#dc3545'
            elif percentage >= 40:
                bar_color = '#ffc107'
            else:
                bar_color = '#28a745'
            
            html += '<div style="margin-bottom: 15px;">'
            html += f'<div style="display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 12px;">'
            html += f'<span style="color: #6c757d;">{label}</span>'
            html += f'<span style="font-weight: 600;">{value} {unit}</span>'
            html += '</div>'
            html += '<div style="background: #e9ecef; border-radius: 10px; height: 10px; overflow: hidden;">'
            html += f'<div style="background: {bar_color}; width: {percentage}%; height: 100%; border-radius: 10px;"></div>'
            html += '</div>'
            html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    behavioral_analysis.short_description = '🎭 Behavior'
    
    def threat_timeline(self, obj):
        """Threat timeline"""
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[WARN] Threat Timeline</h4>'
        
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        timeline_events = []
        
        if obj.last_login_time:
            timeline_events.append(('Last Login', obj.last_login_time, '#17a2b8'))
        
        if obj.last_suspicious_activity:
            timeline_events.append(('Last Suspicious Activity', obj.last_suspicious_activity, '#dc3545'))
        
        timeline_events.append(('Risk Calculated', obj.calculated_at, '#6c757d'))
        
        for label, timestamp, color in timeline_events:
            html += f'<tr><td style="padding: 10px 0; color: #6c757d; border-bottom: 1px solid #dee2e6;">{label}</td>'
            html += f'<td style="padding: 10px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #dee2e6; color: {color};">'
            html += timestamp.strftime('%B %d, %Y %H:%M:%S')
            html += '</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    threat_timeline.short_description = '⏰ Timeline'
    
    # ==================== Actions ====================
    
    def recalculate_scores(self, request, queryset):
        """Recalculate risk scores"""
        for risk_score in queryset:
            risk_score.update_score()
        
        self.message_user(request, f'{queryset.count()} risk score(s) recalculated.')
    recalculate_scores.short_description = '[LOADING] Recalculate scores'
    
    def reset_scores(self, request, queryset):
        """Reset scores to default"""
        count = queryset.update(
            current_score=50,
            previous_score=50,
            failed_login_attempts=0,
            suspicious_activities=0,
            vpn_usage_count=0
        )
        self.message_user(request, f'{count} risk score(s) reset to default.')
    reset_scores.short_description = '↩️ Reset scores'


# ==================== Simple Admin for Remaining Models ====================

@admin.register(PasswordPolicy)
class PasswordPolicyAdmin(admin.ModelAdmin):
    list_display = ['name', 'min_length', 'is_active', 'applies_to_all_users']
    list_filter = ['is_active', 'applies_to_all_users']
    search_fields = ['name']
    
    fieldsets = (
        ('Policy Information', {
            'fields': ('name', 'is_active', 'applies_to_all_users')
        }),
        ('Length Requirements', {
            'fields': (('min_length', 'max_length'),)
        }),
        ('Complexity Requirements', {
            'fields': (
                ('require_uppercase', 'require_lowercase'),
                ('require_digits', 'require_special_chars'),
                ('min_special_chars', 'special_chars_set'),
            )
        }),
        ('History & Expiry', {
            'fields': (
                'remember_last_passwords',
                ('password_expiry_days', 'warn_before_expiry_days'),
            ),
            'classes': ('collapse',)
        }),
        ('Lockout Policy', {
            'fields': (
                ('max_failed_attempts', 'lockout_duration_minutes'),
                'lockout_increment_factor',
            ),
            'classes': ('collapse',)
        }),
    )


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'changed_by']
    list_filter = ['created_at']
    search_fields = ['user__username']
    readonly_fields = ['password_hash', 'created_at']
    
    def has_add_permission(self, request):
        return False


@admin.register(PasswordAttempt)
class PasswordAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'successful', 'attempted_at']
    list_filter = ['successful', 'attempted_at']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['attempted_at']
    
    def has_add_permission(self, request):
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_badge',
        'user_display',
        'device_display',
        'ip_display',
        'status_badge',
        'activity_display',
    ]
    
    list_filter = ['is_active', 'is_compromised', 'created_at']
    search_fields = ['user__username', 'session_key', 'ip_address']
    readonly_fields = ['created_at', 'last_activity', 'expires_at']
    
    def session_badge(self, obj):
        return format_html(
            '<div style="font-family: monospace; font-size: 10px; color: #6c757d;">{}</div>',
            obj.session_key[:16] + '...'
        )
    session_badge.short_description = 'Session'
    
    def user_display(self, obj):
        return format_html(
            '<a href="{}" style="font-weight: 600;">{}</a>',
            reverse('admin:users_user_change', args=[obj.user.pk]),
            obj.user.username
        )
    user_display.short_description = 'User'
    
    def device_display(self, obj):
        if not obj.device_info:
            return '—'
        return obj.device_info.device_model[:20]
    device_display.short_description = 'Device'
    
    def ip_display(self, obj):
        return format_html(
            '<span style="font-family: monospace; font-size: 11px;">{}</span>',
            obj.ip_address
        )
    ip_display.short_description = 'IP'
    
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-size: 9px;">ACTIVE</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 9px;">INACTIVE</span>'
        )
    status_badge.short_description = 'Status'
    
    def activity_display(self, obj):
        time_ago = timezone.now() - obj.last_activity
        if time_ago < timedelta(minutes=5):
            return format_html('<span style="color: #28a745;">Just now</span>')
        elif time_ago < timedelta(hours=1):
            return f'{int(time_ago.total_seconds() / 60)}m ago'
        else:
            return f'{int(time_ago.total_seconds() / 3600)}h ago'
    activity_display.short_description = 'Last Activity'
    
    actions = ['terminate_sessions']
    
    def terminate_sessions(self, request, queryset):
        for session in queryset:
            session.terminate("Terminated by admin")
        self.message_user(request, f'{queryset.count()} session(s) terminated.')
    terminate_sessions.short_description = '🚫 Terminate sessions'


@admin.register(SessionActivity)
class SessionActivityAdmin(admin.ModelAdmin):
    list_display = ['session', 'activity_type', 'ip_address', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['session__user__username', 'ip_address']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False


@admin.register(TwoFactorMethod)
class TwoFactorMethodAdmin(admin.ModelAdmin):
    list_display = ['user', 'method_type', 'is_primary', 'is_enabled', 'last_used_at']
    list_filter = ['method_type', 'is_primary', 'is_enabled']
    search_fields = ['user__username']
    readonly_fields = ['last_used_at', 'created_at', 'updated_at']


@admin.register(TwoFactorAttempt)
class TwoFactorAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'method', 'successful', 'ip_address', 'attempted_at']
    list_filter = ['successful', 'attempted_at']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['attempted_at']
    
    def has_add_permission(self, request):
        return False


@admin.register(TwoFactorRecoveryCode)
class TwoFactorRecoveryCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_used', 'used_at', 'expires_at', 'created_at']
    list_filter = ['is_used', 'created_at']
    search_fields = ['user__username']
    readonly_fields = ['code_hash', 'used_at', 'created_at', 'expires_at']


@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = ['user', 'action_type', 'model_name', 'object_id', 'ip_address', 'created_at']
    list_filter = ['action_type', 'model_name', 'created_at']
    search_fields = ['user__username', 'model_name', 'object_id', 'ip_address']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SecurityNotification)
class SecurityNotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'priority', 'title', 'status', 'sent_at']
    list_filter = ['notification_type', 'priority', 'status', 'sent_at']
    search_fields = ['user__username', 'title', 'recipient']
    readonly_fields = ['sent_at', 'delivered_at', 'read_at', 'created_at']


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_active', 'cooldown_minutes', 'trigger_count', 'last_triggered_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'user__username']
    readonly_fields = ['last_triggered_at', 'created_at', 'updated_at']


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'risk_level', 'is_blocked', 'total_users', 'fraud_cases']
    list_filter = ['risk_level', 'is_blocked']
    search_fields = ['name', 'code']
    readonly_fields = ['last_updated', 'created_at']


@admin.register(GeolocationLog)
class GeolocationLogAdmin(admin.ModelAdmin):
    list_display = ['ip_address', 'country_name', 'city', 'is_vpn', 'is_proxy', 'threat_score', 'queried_at']
    list_filter = ['is_vpn', 'is_proxy', 'is_tor', 'queried_at']
    search_fields = ['ip_address', 'country_name', 'city']
    readonly_fields = ['queried_at', 'updated_at']


@admin.register(APIRateLimit)
class APIRateLimitAdmin(admin.ModelAdmin):
    list_display = ['name', 'limit_type', 'limit_period', 'request_limit', 'is_active', 'total_blocks']
    list_filter = ['limit_type', 'limit_period', 'is_active']
    search_fields = ['name', 'endpoint_pattern']
    readonly_fields = ['last_blocked_at', 'created_at', 'updated_at']


@admin.register(RateLimitLog)
class RateLimitLogAdmin(admin.ModelAdmin):
    list_display = ['rate_limit', 'user', 'ip_address', 'endpoint', 'limit_exceeded', 'created_at']
    list_filter = ['limit_exceeded', 'created_at']
    search_fields = ['user__username', 'ip_address', 'endpoint']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False


@admin.register(FraudPattern)
class FraudPatternAdmin(admin.ModelAdmin):
    list_display = ['name', 'pattern_type', 'weight', 'confidence_threshold', 'auto_block', 'is_active', 'match_count']
    list_filter = ['pattern_type', 'auto_block', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['last_match_at', 'created_at', 'updated_at']


@admin.register(AutoBlockRule)
class AutoBlockRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'rule_type', 'action_type', 'threshold_value', 'is_active', 'priority']
    list_filter = ['rule_type', 'action_type', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SecurityDashboard)
class SecurityDashboardAdmin(admin.ModelAdmin):
    list_display = [
        'date',
        'total_users',
        'active_users',
        'total_threats',
        'threats_blocked',
        'critical_risk_users'
    ]
    list_filter = ['date']
    readonly_fields = ['calculated_at']
    
    def has_add_permission(self, request):
        return False


# ==================== Custom Admin Site Title ====================

admin.site.site_header = "[SECURE] Security Administration"
admin.site.site_title = "Security Admin"
admin.site.index_title = "Welcome to Security Management"


# ==================== Admin Panel CSS Customization ====================

class SecurityAdminSite(admin.AdminSite):
    """Custom admin site for security"""
    
    def each_context(self, request):
        context = super().each_context(request)
        
        # Add custom CSS
        context['custom_css'] = """
        <style>
            /* Modern gradient header */
            #header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            
            /* Smooth transitions */
            .button, input[type=submit], .submit-row input {
                transition: all 0.3s ease;
            }
            
            .button:hover, input[type=submit]:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }
            
            /* Better table styling */
            #result_list tbody tr:hover {
                background: #f8f9fa;
                cursor: pointer;
            }
            
            /* Modern cards */
            .module {
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            
            /* Colored badges */
            .badge-success { background: #28a745; color: white; padding: 4px 8px; border-radius: 12px; }
            .badge-danger { background: #dc3545; color: white; padding: 4px 8px; border-radius: 12px; }
            .badge-warning { background: #ffc107; color: #333; padding: 4px 8px; border-radius: 12px; }
            .badge-info { background: #17a2b8; color: white; padding: 4px 8px; border-radius: 12px; }
        </style>
        """
        
        return context
    
    
    
    # security/admin.py - Add these registrations

# ==================== Security Config Admin ====================

@admin.register(SecurityConfig)
class SecurityConfigAdmin(admin.ModelAdmin):
    list_display = [
        'config_badge',
        'type_badge',
        'status_indicator',
        'version_display',
        'effective_display',
        'default_badge',
    ]
    
    list_filter = [
        'config_type',
        'is_active',
        'is_default',
        'created_at',
    ]
    
    search_fields = [
        'name',
        'description',
    ]
    
    readonly_fields = [
        'config_overview',
        'config_data_display',
        'version_history',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('⚙️ Configuration Overview', {
            'fields': ('config_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Basic Information', {
            'fields': (
                'name',
                'description',
                'config_type',
            )
        }),
        
        ('[FIX] Configuration Data', {
            'fields': (
                'config_data_display',
                'config_data',
            )
        }),
        
        ('[OK] Status & Activation', {
            'fields': (
                ('is_active', 'is_default'),
                ('effective_from', 'effective_until'),
            )
        }),
        
        ('📚 Versioning', {
            'fields': (
                'version_history',
                'version',
                'parent_config',
            ),
            'classes': ('collapse',)
        }),
        
        ('👤 User Info', {
            'fields': (
                ('created_by', 'updated_by'),
            ),
            'classes': ('collapse',)
        }),
        
        ('⏰ Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_configs', 'deactivate_configs', 'set_as_default']
    
    def config_badge(self, obj):
        type_icons = {
            'rate_limit': '⏱️',
            'password_policy': '[SECURE]',
            'login_security': '[KEY]',
            'api_security': '🔌',
            'content_security': '[DOC]',
            'general': '⚙️',
        }
        
        icon = type_icons.get(obj.config_type, '⚙️')
        
        return format_html(
            '<div style="text-align: center; font-size: 32px;">{}</div>',
            icon
        )
    config_badge.short_description = 'Type'
    
    def type_badge(self, obj):
        type_colors = {
            'rate_limit': '#17a2b8',
            'password_policy': '#dc3545',
            'login_security': '#ffc107',
            'api_security': '#6f42c1',
            'content_security': '#28a745',
            'general': '#6c757d',
        }
        
        color = type_colors.get(obj.config_type, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>',
            color,
            obj.get_config_type_display()
        )
    type_badge.short_description = 'Category'
    
    def status_indicator(self, obj):
        if obj.is_currently_effective():
            return format_html(
                '<span style="background: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 10px;">✓ ACTIVE</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px;">✗ INACTIVE</span>'
        )
    status_indicator.short_description = 'Status'
    
    def version_display(self, obj):
        return format_html(
            '<div style="text-align: center; font-weight: bold;">v{}</div>',
            obj.version
        )
    version_display.short_description = 'Version'
    
    def effective_display(self, obj):
        if not obj.effective_from:
            return '—'
        
        html = f'<div style="font-size: 10px;">'
        html += f'From: {obj.effective_from.strftime("%Y-%m-%d")}<br/>'
        
        if obj.effective_until:
            html += f'Until: {obj.effective_until.strftime("%Y-%m-%d")}'
        else:
            html += 'Until: Permanent'
        
        html += '</div>'
        
        return format_html(html)
    effective_display.short_description = 'Effective Period'
    
    def default_badge(self, obj):
        if obj.is_default:
            return format_html(
                '<span style="background: #ffc107; color: #333; padding: 4px 10px; '
                'border-radius: 12px; font-size: 10px;">[STAR] DEFAULT</span>'
            )
        return format_html('<span style="color: #6c757d;">—</span>')
    default_badge.short_description = 'Default'
    
    def config_overview(self, obj):
        html = '<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
        html += 'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += f'<h2 style="margin: 0;">{obj.name}</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9;">{obj.description or "No description"}</p>'
        
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Type', obj.get_config_type_display()),
            ('Version', f'v{obj.version}'),
            ('Status', 'Active' if obj.is_active else 'Inactive'),
            ('Default', 'Yes' if obj.is_default else 'No'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div></div>'
        
        return format_html(html)
    config_overview.short_description = ''
    
    def config_data_display(self, obj):
        if not obj.config_data:
            return format_html('<span style="color: #6c757d;">No configuration data</span>')
        
        html = '<pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; '
        html += 'font-size: 11px; overflow-x: auto; max-height: 400px;">'
        html += json.dumps(obj.config_data, indent=2)
        html += '</pre>'
        
        return format_html(html)
    config_data_display.short_description = 'Configuration Preview'
    
    def version_history(self, obj):
        if not obj.parent_config:
            return format_html('<span style="color: #6c757d;">Original version</span>')
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">'
        html += f'<strong>Parent Config:</strong> {obj.parent_config.name} (v{obj.parent_config.version})'
        html += '</div>'
        
        return format_html(html)
    version_history.short_description = 'Version History'
    
    def activate_configs(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} configuration(s) activated.')
    activate_configs.short_description = '[OK] Activate configurations'
    
    def deactivate_configs(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} configuration(s) deactivated.')
    deactivate_configs.short_description = '[ERROR] Deactivate configurations'
    
    def set_as_default(self, request, queryset):
        for config in queryset:
            SecurityConfig.objects.filter(
                config_type=config.config_type,
                is_default=True
            ).exclude(pk=config.pk).update(is_default=False)
            
            config.is_default = True
            config.save()
        
        self.message_user(request, f'{queryset.count()} configuration(s) set as default.')
    set_as_default.short_description = '[STAR] Set as default'


# ==================== Data Export Admin ====================

@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    list_display = [
        'export_badge',
        'user_display',
        'format_badge',
        'status_badge',
        'progress_display',
        'created_display',
    ]
    
    list_filter = [
        'status',
        'format',
        'is_encrypted',
        'requested_at',
    ]
    
    search_fields = [
        'export_name',
        'user__username',
    ]
    
    readonly_fields = [
        'export_overview',
        'export_progress',
        'download_info',
        'requested_at',
        'started_at',
        'completed_at',
        'expires_at',
    ]
    
    fieldsets = (
        ('📤 Export Overview', {
            'fields': ('export_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Export Information', {
            'fields': (
                ('user', 'export_name'),
                'format',
                'model_name',
            )
        }),
        
        ('[SECURE] Security', {
            'fields': (
                'is_encrypted',
                'encryption_key',
            ),
            'classes': ('collapse',)
        }),
        
        ('[STATS] Progress', {
            'fields': (
                'export_progress',
                'status',
                ('total_records', 'exported_records'),
            )
        }),
        
        ('📥 Download', {
            'fields': (
                'download_info',
                'file_path',
                'download_url',
            ),
            'classes': ('collapse',)
        }),
        
        ('⏰ Timeline', {
            'fields': (
                'requested_at',
                'started_at',
                'completed_at',
                'expires_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['cancel_exports', 'regenerate_download_url']
    date_hierarchy = 'requested_at'
    
    def export_badge(self, obj):
        format_icons = {
            'csv': '[STATS]',
            'json': '📋',
            'xlsx': '📗',
            'pdf': '📕',
        }
        
        icon = format_icons.get(obj.format, '[DOC]')
        
        return format_html(
            '<div style="text-align: center; font-size: 32px;">{}</div>',
            icon
        )
    export_badge.short_description = 'Format'
    
    def user_display(self, obj):
        return format_html(
            '<a href="{}" style="font-weight: 600;">{}</a>',
            reverse('admin:users_user_change', args=[obj.user.pk]),
            obj.user.username
        )
    user_display.short_description = 'User'
    
    def format_badge(self, obj):
        format_colors = {
            'csv': '#28a745',
            'json': '#17a2b8',
            'xlsx': '#28a745',
            'pdf': '#dc3545',
        }
        
        color = format_colors.get(obj.format, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px; font-weight: 600;">{}</span>',
            color,
            obj.format.upper()
        )
    format_badge.short_description = 'Format'
    
    def status_badge(self, obj):
        status_config = {
            'pending': ('#ffc107', '⏳'),
            'processing': ('#17a2b8', '[LOADING]'),
            'completed': ('#28a745', '[OK]'),
            'failed': ('#dc3545', '[ERROR]'),
            'cancelled': ('#6c757d', '🚫'),
        }
        
        color, icon = status_config.get(obj.status, ('#6c757d', '•'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px;">{}</div>'
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 9px; font-weight: 600; margin-top: 3px; display: inline-block;">{}</span>'
            '</div>',
            icon,
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def progress_display(self, obj):
        if obj.total_records == 0:
            percentage = 0
        else:
            percentage = (obj.exported_records / obj.total_records) * 100
        
        if percentage >= 75:
            color = '#28a745'
        elif percentage >= 25:
            color = '#ffc107'
        else:
            color = '#dc3545'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-weight: bold; color: {};">{:.0f}%</div>'
            '<div style="background: #e9ecef; border-radius: 10px; height: 4px; margin-top: 3px;">'
            '<div style="background: {}; width: {}%; height: 100%; border-radius: 10px;"></div>'
            '</div>'
            '</div>',
            color,
            percentage,
            color,
            percentage
        )
    progress_display.short_description = 'Progress'
    
    def created_display(self, obj):
        time_ago = timezone.now() - obj.requested_at
        
        if time_ago < timedelta(hours=1):
            return f'{int(time_ago.total_seconds() / 60)}m ago'
        elif time_ago < timedelta(days=1):
            return f'{int(time_ago.total_seconds() / 3600)}h ago'
        else:
            return f'{time_ago.days}d ago'
    created_display.short_description = 'Requested'
    
    def export_overview(self, obj):
        status_colors = {
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'failed': '#dc3545',
            'cancelled': '#6c757d',
        }
        
        color = status_colors.get(obj.status, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); '
        html += 'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += f'<h2 style="margin: 0;">{obj.export_name}</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9;">User: {obj.user.username}</p>'
        
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Format', obj.format.upper()),
            ('Status', obj.get_status_display()),
            ('Records', f'{obj.exported_records}/{obj.total_records}'),
            ('Encrypted', 'Yes' if obj.is_encrypted else 'No'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div></div>'
        
        return format_html(html)
    export_overview.short_description = ''
    
    def export_progress(self, obj):
        if obj.total_records == 0:
            percentage = 0
        else:
            percentage = (obj.exported_records / obj.total_records) * 100
        
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[STATS] Export Progress</h4>'
        
        html += f'<div style="text-align: center; font-size: 48px; font-weight: bold; color: #17a2b8; margin: 20px 0;">'
        html += f'{percentage:.0f}%'
        html += '</div>'
        
        html += '<div style="background: #e9ecef; border-radius: 10px; height: 20px; overflow: hidden;">'
        html += f'<div style="background: #17a2b8; width: {percentage}%; height: 100%; transition: width 0.3s;"></div>'
        html += '</div>'
        
        html += f'<div style="text-align: center; margin-top: 10px; color: #6c757d;">'
        html += f'{obj.exported_records:,} of {obj.total_records:,} records exported'
        html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    export_progress.short_description = '[STATS] Progress'
    
    def download_info(self, obj):
        if obj.status != 'completed':
            return format_html(
                '<div style="background: #fff3cd; padding: 15px; border-radius: 5px; text-align: center;">'
                '<strong style="color: #856404;">Export not completed yet</strong>'
                '</div>'
            )
        
        if obj.is_expired():
            return format_html(
                '<div style="background: #f8d7da; padding: 15px; border-radius: 5px; text-align: center;">'
                '<strong style="color: #721c24;">[WARN] Download link has expired</strong>'
                '</div>'
            )
        
        html = '<div style="background: #d4edda; padding: 15px; border-radius: 5px;">'
        html += '<strong style="color: #155724;">[OK] Ready for Download</strong>'
        
        if obj.download_url:
            html += f'<div style="margin-top: 10px;"><a href="{obj.download_url}" target="_blank" '
            html += 'class="button" style="background: #28a745; color: white;">Download File</a></div>'
        
        html += f'<div style="margin-top: 10px; font-size: 12px; color: #155724;">'
        html += f'Expires: {obj.expires_at.strftime("%B %d, %Y")}'
        html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    download_info.short_description = '📥 Download'
    
    def cancel_exports(self, request, queryset):
        count = queryset.filter(status__in=['pending', 'processing']).update(status='cancelled')
        self.message_user(request, f'{count} export(s) cancelled.')
    cancel_exports.short_description = '🚫 Cancel exports'
    
    def regenerate_download_url(self, request, queryset):
        count = 0
        for export in queryset.filter(status='completed'):
            export.generate_secure_download_url()
            count += 1
        
        self.message_user(request, f'{count} download URL(s) regenerated.')
    regenerate_download_url.short_description = '[LOADING] Regenerate download URLs'


# ==================== Data Import Admin ====================

@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = [
        'import_badge',
        'user_display',
        'file_display',
        'status_badge',
        'progress_display',
        'success_rate',
        'uploaded_display',
    ]
    
    list_filter = [
        'status',
        'is_verified',
        'uploaded_at',
    ]
    
    search_fields = [
        'import_name',
        'file_name',
        'user__username',
    ]
    
    readonly_fields = [
        'import_overview',
        'import_progress',
        'validation_results',
        'uploaded_at',
        'started_at',
        'completed_at',
    ]
    
    fieldsets = (
        ('📥 Import Overview', {
            'fields': ('import_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Import Information', {
            'fields': (
                ('user', 'import_name'),
                'model_name',
                ('file_name', 'file_hash'),
            )
        }),
        
        ('[STATS] Progress', {
            'fields': (
                'import_progress',
                'status',
                ('total_records', 'processed_records'),
                ('successful_records', 'failed_records'),
            )
        }),
        
        ('[OK] Validation', {
            'fields': (
                'validation_results',
                'is_verified',
                'verification_hash',
            ),
            'classes': ('collapse',)
        }),
        
        ('⏰ Timeline', {
            'fields': (
                'uploaded_at',
                'started_at',
                'completed_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['start_import', 'cancel_import', 'retry_failed']
    date_hierarchy = 'uploaded_at'
    
    def import_badge(self, obj):
        return format_html(
            '<div style="text-align: center; font-size: 32px;">📥</div>'
        )
    import_badge.short_description = 'Import'
    
    def user_display(self, obj):
        return format_html(
            '<a href="{}" style="font-weight: 600;">{}</a>',
            reverse('admin:users_user_change', args=[obj.user.pk]),
            obj.user.username
        )
    user_display.short_description = 'User'
    
    def file_display(self, obj):
        return format_html(
            '<div style="font-size: 11px;">'
            '<div style="font-weight: 600;">{}</div>'
            '<div style="color: #6c757d; margin-top: 3px;">{:,.0f} KB</div>'
            '</div>',
            obj.file_name[:30] + '...' if len(obj.file_name) > 30 else obj.file_name,
            obj.file_size / 1024
        )
    file_display.short_description = 'File'
    
    def status_badge(self, obj):
        status_config = {
            'pending': ('#ffc107', '⏳'),
            'validating': ('#17a2b8', '🔍'),
            'processing': ('#6f42c1', '[LOADING]'),
            'completed': ('#28a745', '[OK]'),
            'failed': ('#dc3545', '[ERROR]'),
            'partially_completed': ('#fd7e14', '[WARN]'),
        }
        
        color, icon = status_config.get(obj.status, ('#6c757d', '•'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 20px;">{}</div>'
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 9px; font-weight: 600; margin-top: 3px; display: inline-block;">{}</span>'
            '</div>',
            icon,
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def progress_display(self, obj):
        if obj.total_records == 0:
            percentage = 0
        else:
            percentage = (obj.processed_records / obj.total_records) * 100
        
        color = '#28a745' if percentage >= 75 else '#ffc107' if percentage >= 25 else '#dc3545'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-weight: bold; color: {};">{:.0f}%</div>'
            '<div style="background: #e9ecef; border-radius: 10px; height: 4px; margin-top: 3px;">'
            '<div style="background: {}; width: {}%; height: 100%; border-radius: 10px;"></div>'
            '</div>'
            '</div>',
            color,
            percentage,
            color,
            percentage
        )
    progress_display.short_description = 'Progress'
    
    def success_rate(self, obj):
        if obj.processed_records == 0:
            rate = 0
        else:
            rate = (obj.successful_records / obj.processed_records) * 100
        
        color = '#28a745' if rate >= 90 else '#ffc107' if rate >= 70 else '#dc3545'
        
        return format_html(
            '<div style="text-align: center; color: {}; font-weight: bold;">{:.0f}%</div>',
            color,
            rate
        )
    success_rate.short_description = 'Success'
    
    def uploaded_display(self, obj):
        time_ago = timezone.now() - obj.uploaded_at
        
        if time_ago < timedelta(hours=1):
            return f'{int(time_ago.total_seconds() / 60)}m ago'
        elif time_ago < timedelta(days=1):
            return f'{int(time_ago.total_seconds() / 3600)}h ago'
        else:
            return f'{time_ago.days}d ago'
    uploaded_display.short_description = 'Uploaded'
    
    def import_overview(self, obj):
        status_colors = {
            'pending': '#ffc107',
            'validating': '#17a2b8',
            'processing': '#6f42c1',
            'completed': '#28a745',
            'failed': '#dc3545',
            'partially_completed': '#fd7e14',
        }
        
        color = status_colors.get(obj.status, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); '
        html += 'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += f'<h2 style="margin: 0;">{obj.import_name}</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9;">File: {obj.file_name}</p>'
        
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Status', obj.get_status_display()),
            ('Total', f'{obj.total_records:,}'),
            ('Success', f'{obj.successful_records:,}'),
            ('Failed', f'{obj.failed_records:,}'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div></div>'
        
        return format_html(html)
    import_overview.short_description = ''
    
    def import_progress(self, obj):
        if obj.total_records == 0:
            percentage = 0
        else:
            percentage = (obj.processed_records / obj.total_records) * 100
        
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[STATS] Import Progress</h4>'
        
        # Progress circle/number
        html += f'<div style="text-align: center; font-size: 48px; font-weight: bold; color: #6f42c1; margin: 20px 0;">'
        html += f'{percentage:.0f}%'
        html += '</div>'
        
        # Progress bar
        html += '<div style="background: #e9ecef; border-radius: 10px; height: 20px; overflow: hidden;">'
        html += f'<div style="background: #6f42c1; width: {percentage}%; height: 100%; transition: width 0.3s;"></div>'
        html += '</div>'
        
        # Details
        html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 20px;">'
        
        details = [
            ('Processed', obj.processed_records, '#6f42c1'),
            ('Success', obj.successful_records, '#28a745'),
            ('Failed', obj.failed_records, '#dc3545'),
        ]
        
        for label, value, color in details:
            html += f'<div style="text-align: center; padding: 10px; background: {color}20; border-radius: 5px;">'
            html += f'<div style="font-size: 24px; font-weight: bold; color: {color};">{value:,}</div>'
            html += f'<div style="font-size: 10px; color: #6c757d; margin-top: 3px;">{label}</div>'
            html += '</div>'
        
        html += '</div></div>'
        
        return format_html(html)
    import_progress.short_description = '[STATS] Progress'
    
    def validation_results(self, obj):
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[OK] Validation Results</h4>'
        
        if obj.is_verified:
            html += '<div style="background: #d4edda; padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 15px;">'
            html += '<div style="font-size: 32px; margin-bottom: 10px;">[OK]</div>'
            html += '<strong style="color: #155724;">File Verified Successfully</strong>'
            html += '</div>'
        else:
            html += '<div style="background: #f8d7da; padding: 15px; border-radius: 5px; text-align: center; margin-bottom: 15px;">'
            html += '<div style="font-size: 32px; margin-bottom: 10px;">[WARN]</div>'
            html += '<strong style="color: #721c24;">File Not Verified</strong>'
            html += '</div>'
        
        # Errors
        if obj.validation_errors:
            html += '<div style="margin-top: 15px;"><strong>Errors:</strong></div>'
            html += '<ul style="margin: 10px 0; padding-left: 20px; color: #dc3545;">'
            for error in obj.validation_errors[:5]:
                html += f'<li style="margin: 5px 0;">{error}</li>'
            html += '</ul>'
        
        # Warnings
        if obj.validation_warnings:
            html += '<div style="margin-top: 15px;"><strong>Warnings:</strong></div>'
            html += '<ul style="margin: 10px 0; padding-left: 20px; color: #ffc107;">'
            for warning in obj.validation_warnings[:5]:
                html += f'<li style="margin: 5px 0;">{warning}</li>'
            html += '</ul>'
        
        html += '</div>'
        
        return format_html(html)
    validation_results.short_description = '[OK] Validation'
    
    def start_import(self, request, queryset):
        count = queryset.filter(status='pending').update(status='validating')
        self.message_user(request, f'{count} import(s) started.')
    start_import.short_description = '▶️ Start import'
    
    def cancel_import(self, request, queryset):
        count = queryset.filter(status__in=['pending', 'validating', 'processing']).update(status='failed')
        self.message_user(request, f'{count} import(s) cancelled.')
    cancel_import.short_description = '🚫 Cancel import'
    
    def retry_failed(self, request, queryset):
        count = queryset.filter(status__in=['failed', 'partially_completed']).update(
            status='pending',
            processed_records=0,
            successful_records=0,
            failed_records=0
        )
        self.message_user(request, f'{count} import(s) queued for retry.')
    retry_failed.short_description = '[LOADING] Retry failed imports'


# ==================== Real Time Detection Admin ====================

@admin.register(RealTimeDetection)
class RealTimeDetectionAdmin(admin.ModelAdmin):
    list_display = [
        'detection_badge',
        'type_display',
        'status_indicator',
        'stats_display',
        'performance_display',
        'last_run_display',
    ]
    
    list_filter = [
        'status',
        'detection_type',
        'last_run_at',
    ]
    
    search_fields = [
        'name',
        'description',
    ]
    
    readonly_fields = [
        'detection_overview',
        'performance_metrics',
        'last_run_at',
    ]
    
    fieldsets = (
        ('🔍 Detection Overview', {
            'fields': ('detection_overview',),
            'classes': ('wide',)
        }),
        
        ('📋 Detection Information', {
            'fields': (
                'name',
                'description',
                'detection_type',
            )
        }),
        
        ('⚙️ Configuration', {
            'fields': (
                ('check_interval_seconds', 'batch_size'),
            )
        }),
        
        ('[STATS] Performance', {
            'fields': (
                'performance_metrics',
                'average_processing_time',
            ),
            'classes': ('collapse',)
        }),
        
        ('📈 Statistics', {
            'fields': (
                ('total_checks', 'total_matches'),
            ),
            'classes': ('collapse',)
        }),
        
        ('⏰ Timing', {
            'fields': (
                'last_run_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['start_detection', 'pause_detection', 'reset_stats']
    
    def detection_badge(self, obj):
        status_icons = {
            'idle': '⏸️',
            'running': '▶️',
            'paused': '⏸️',
            'error': '[ERROR]',
        }
        
        icon = status_icons.get(obj.status, '•')
        
        return format_html(
            '<div style="text-align: center; font-size: 32px;">{}</div>',
            icon
        )
    detection_badge.short_description = 'Status'
    
    def type_display(self, obj):
        return format_html(
            '<div style="font-size: 11px; font-weight: 600;">{}</div>',
            obj.detection_type.replace('_', ' ').title()
        )
    type_display.short_description = 'Detection Type'
    
    def status_indicator(self, obj):
        status_config = {
            'idle': ('#6c757d', '⏸️'),
            'running': ('#28a745', '▶️'),
            'paused': ('#ffc107', '⏸️'),
            'error': ('#dc3545', '[ERROR]'),
        }
        
        color, icon = status_config.get(obj.status, ('#6c757d', '•'))
        
        if obj.status == 'running':
            return format_html(
                '<div style="text-align: center;">'
                '<div style="width: 12px; height: 12px; background: {}; border-radius: 50%; '
                'margin: 0 auto 5px auto; animation: pulse 2s infinite;"></div>'
                '<div style="font-size: 10px; color: {}; font-weight: 600;">{}</div>'
                '</div>'
                '<style>@keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}</style>',
                color,
                color,
                obj.get_status_display().upper()
            )
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="width: 12px; height: 12px; background: {}; border-radius: 50%; '
            'margin: 0 auto 5px auto;"></div>'
            '<div style="font-size: 10px; color: {}; font-weight: 600;">{}</div>'
            '</div>',
            color,
            color,
            obj.get_status_display().upper()
        )
    status_indicator.short_description = 'Status'
    
    def stats_display(self, obj):
        if obj.total_checks == 0:
            match_rate = 0
        else:
            match_rate = (obj.total_matches / obj.total_checks) * 100
        
        return format_html(
            '<div style="font-size: 10px; line-height: 1.5;">'
            '<div>Checks: <strong>{:,}</strong></div>'
            '<div>Matches: <strong>{:,}</strong></div>'
            '<div>Rate: <strong>{:.1f}%</strong></div>'
            '</div>',
            obj.total_checks,
            obj.total_matches,
            match_rate
        )
    stats_display.short_description = 'Statistics'
    
    def performance_display(self, obj):
        avg_time = obj.average_processing_time
        
        if avg_time < 1:
            color = '#28a745'
            label = 'FAST'
        elif avg_time < 5:
            color = '#ffc107'
            label = 'NORMAL'
        else:
            color = '#dc3545'
            label = 'SLOW'
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-weight: bold; color: {};">{:.2f}s</div>'
            '<div style="font-size: 9px; color: {};">{}</div>'
            '</div>',
            color,
            avg_time,
            color,
            label
        )
    performance_display.short_description = 'Avg Time'
    
    def last_run_display(self, obj):
        if not obj.last_run_at:
            return format_html('<span style="color: #6c757d;">Never</span>')
        
        time_ago = timezone.now() - obj.last_run_at
        
        if time_ago < timedelta(minutes=5):
            display = 'Just now'
            color = '#28a745'
        elif time_ago < timedelta(hours=1):
            display = f'{int(time_ago.total_seconds() / 60)}m ago'
            color = '#17a2b8'
        else:
            display = f'{int(time_ago.total_seconds() / 3600)}h ago'
            color = '#6c757d'
        
        return format_html(
            '<div style="font-size: 11px; color: {}; font-weight: 600;">{}</div>',
            color,
            display
        )
    last_run_display.short_description = 'Last Run'
    
    def detection_overview(self, obj):
        status_colors = {
            'idle': '#6c757d',
            'running': '#28a745',
            'paused': '#ffc107',
            'error': '#dc3545',
        }
        
        color = status_colors.get(obj.status, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); '
        html += 'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += f'<h2 style="margin: 0;">{obj.name}</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9;">{obj.description}</p>'
        
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        if obj.total_checks > 0:
            match_rate = (obj.total_matches / obj.total_checks) * 100
        else:
            match_rate = 0
        
        stats = [
            ('Status', obj.get_status_display()),
            ('Checks', f'{obj.total_checks:,}'),
            ('Matches', f'{obj.total_matches:,}'),
            ('Match Rate', f'{match_rate:.1f}%'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div></div>'
        
        return format_html(html)
    detection_overview.short_description = ''
    
    def performance_metrics(self, obj):
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">⚡ Performance Metrics</h4>'
        
        html += '<table style="width: 100%; border-collapse: collapse;">'
        
        metrics = [
            ('Check Interval', f'{obj.check_interval_seconds}s'),
            ('Batch Size', obj.batch_size),
            ('Average Processing Time', f'{obj.average_processing_time:.2f}s'),
            ('Total Checks', f'{obj.total_checks:,}'),
            ('Total Matches', f'{obj.total_matches:,}'),
        ]
        
        for label, value in metrics:
            html += f'<tr><td style="padding: 8px 0; color: #6c757d; border-bottom: 1px solid #dee2e6;">{label}</td>'
            html += f'<td style="padding: 8px 0; text-align: right; font-weight: 600; border-bottom: 1px solid #dee2e6;">{value}</td></tr>'
        
        html += '</table>'
        html += '</div>'
        
        return format_html(html)
    performance_metrics.short_description = '⚡ Performance'
    
    def start_detection(self, request, queryset):
        count = queryset.exclude(status='running').update(status='running')
        self.message_user(request, f'{count} detection(s) started.')
    start_detection.short_description = '▶️ Start detection'
    
    def pause_detection(self, request, queryset):
        count = queryset.filter(status='running').update(status='paused')
        self.message_user(request, f'{count} detection(s) paused.')
    pause_detection.short_description = '⏸️ Pause detection'
    
    def reset_stats(self, request, queryset):
        count = queryset.update(
            total_checks=0,
            total_matches=0,
            average_processing_time=0
        )
        self.message_user(request, f'{count} detection(s) statistics reset.')
    reset_stats.short_description = '↩️ Reset statistics'


# ==================== Country Block Rule Admin ====================

@admin.register(CountryBlockRule)
class CountryBlockRuleAdmin(admin.ModelAdmin):
    list_display = [
        'country_display',
        'block_type_badge',
        'status_indicator',
        'verification_requirements',
        'created_by_display',
        'active_period_display',
    ]
    
    list_filter = [
        'block_type',
        'is_active',
        'require_phone_verification',
        'require_id_verification',
        'created_at',
    ]
    
    search_fields = [
        'country__name',
        'country__code',
    ]
    
    readonly_fields = [
        'rule_overview',
        'verification_summary',
        'ip_exceptions_display',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('🚫 Block Rule Overview', {
            'fields': ('rule_overview',),
            'classes': ('wide',)
        }),
        
        ('🌍 Country', {
            'fields': ('country',)
        }),
        
        ('⚙️ Block Configuration', {
            'fields': (
                'block_type',
                ('block_all_ips', 'is_active'),
            )
        }),
        
        ('[SECURE] Verification Requirements', {
            'fields': (
                'verification_summary',
                'require_phone_verification',
                'require_id_verification',
                'require_address_verification',
            )
        }),
        
        ('📋 Exceptions', {
            'fields': (
                'ip_exceptions_display',
                'allowed_ips',
                'allowed_asns',
            ),
            'classes': ('collapse',)
        }),
        
        ('📅 Schedule', {
            'fields': (
                ('start_date', 'end_date'),
            ),
            'classes': ('collapse',)
        }),
        
        ('👤 Metadata', {
            'fields': (
                'created_by',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_rules', 'deactivate_rules', 'require_full_verification']
    
    def country_display(self, obj):
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<div style="font-size: 24px;">{}</div>'
            '<div>'
            '<div style="font-weight: 600; font-size: 12px;">{}</div>'
            '<div style="font-size: 10px; color: #6c757d;">{}</div>'
            '</div>'
            '</div>',
            '🏳️',
            obj.country.name,
            obj.country.code
        )
    country_display.short_description = 'Country'
    
    def block_type_badge(self, obj):
        type_config = {
            'complete': ('#dc3545', '🚫'),
            'partial': ('#ffc107', '[WARN]'),
            'monitor': ('#17a2b8', '👁️'),
            'require_verification': ('#6f42c1', '[OK]'),
        }
        
        color, icon = type_config.get(obj.block_type, ('#6c757d', '•'))
        
        return format_html(
            '<div style="text-align: center;">'
            '<div style="font-size: 24px; margin-bottom: 3px;">{}</div>'
            '<span style="background: {}; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 9px; font-weight: 600;">{}</span>'
            '</div>',
            icon,
            color,
            obj.get_block_type_display()
        )
    block_type_badge.short_description = 'Block Type'
    
    def status_indicator(self, obj):
        if obj.is_active_now():
            return format_html(
                '<span style="background: #28a745; color: white; padding: 4px 10px; '
                'border-radius: 12px; font-size: 10px;">✓ ACTIVE</span>'
            )
        return format_html(
            '<span style="background: #6c757d; color: white; padding: 4px 10px; '
            'border-radius: 12px; font-size: 10px;">✗ INACTIVE</span>'
        )
    status_indicator.short_description = 'Status'
    
    def verification_requirements(self, obj):
        requirements = []
        
        if obj.require_phone_verification:
            requirements.append('📱')
        if obj.require_id_verification:
            requirements.append('🆔')
        if obj.require_address_verification:
            requirements.append('📍')
        
        if not requirements:
            return format_html('<span style="color: #6c757d;">None</span>')
        
        return format_html(
            '<div style="font-size: 16px;">{}</div>',
            ' '.join(requirements)
        )
    verification_requirements.short_description = 'Verification'
    
    def created_by_display(self, obj):
        if not obj.created_by:
            return format_html('<span style="color: #6c757d;">System</span>')
        
        return obj.created_by.username
    created_by_display.short_description = 'Created By'
    
    def active_period_display(self, obj):
        if not obj.start_date:
            return format_html('<span style="color: #6c757d;">No schedule</span>')
        
        html = f'<div style="font-size: 10px;">'
        html += f'From: {obj.start_date.strftime("%Y-%m-%d")}<br/>'
        
        if obj.end_date:
            html += f'Until: {obj.end_date.strftime("%Y-%m-%d")}'
        else:
            html += 'Until: Permanent'
        
        html += '</div>'
        
        return format_html(html)
    active_period_display.short_description = 'Active Period'
    
    def rule_overview(self, obj):
        type_colors = {
            'complete': '#dc3545',
            'partial': '#ffc107',
            'monitor': '#17a2b8',
            'require_verification': '#6f42c1',
        }
        
        color = type_colors.get(obj.block_type, '#6c757d')
        
        html = f'<div style="background: linear-gradient(135deg, {color}dd 0%, {color} 100%); '
        html += 'padding: 25px; border-radius: 12px; color: white; margin-bottom: 20px;">'
        
        html += '<div style="display: flex; justify-content: space-between; align-items: center;">'
        html += '<div>'
        html += f'<h2 style="margin: 0;">Country Block Rule</h2>'
        html += f'<p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 16px;">{obj.country.name} ({obj.country.code})</p>'
        html += '</div>'
        
        # Status badge
        html += f'<div style="background: rgba(255,255,255,0.2); padding: 20px; border-radius: 50%; '
        html += f'width: 80px; height: 80px; display: flex; flex-direction: column; align-items: center; justify-content: center;">'
        html += f'<div style="font-size: 32px;">🚫</div>'
        html += f'<div style="font-size: 9px; margin-top: 3px;">{obj.get_block_type_display()}</div>'
        html += '</div>'
        html += '</div>'
        
        # Stats
        html += '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px;">'
        
        stats = [
            ('Block Type', obj.get_block_type_display()),
            ('Status', 'Active' if obj.is_active else 'Inactive'),
            ('Block All IPs', 'Yes' if obj.block_all_ips else 'No'),
            ('Exceptions', len(obj.allowed_ips or []) + len(obj.allowed_asns or [])),
        ]
        
        for label, value in stats:
            html += f'<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
            html += f'<div style="font-size: 10px; opacity: 0.9;">{label}</div>'
            html += f'<div style="font-size: 14px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div></div>'
        
        return format_html(html)
    rule_overview.short_description = ''
    
    def verification_summary(self, obj):
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">[SECURE] Verification Requirements</h4>'
        
        verifications = [
            ('Phone Verification', obj.require_phone_verification, '📱'),
            ('ID Verification', obj.require_id_verification, '🆔'),
            ('Address Verification', obj.require_address_verification, '📍'),
        ]
        
        for label, required, icon in verifications:
            if required:
                bg_color = '#d4edda'
                text_color = '#155724'
                status = 'REQUIRED'
            else:
                bg_color = '#f8f9fa'
                text_color = '#6c757d'
                status = 'NOT REQUIRED'
            
            html += f'<div style="background: {bg_color}; color: {text_color}; padding: 10px; '
            html += f'border-radius: 5px; margin-bottom: 10px; display: flex; align-items: center; gap: 10px;">'
            html += f'<div style="font-size: 24px;">{icon}</div>'
            html += f'<div style="flex: 1; font-weight: 600;">{label}</div>'
            html += f'<div style="font-size: 10px; font-weight: 600;">{status}</div>'
            html += '</div>'
        
        html += '</div>'
        
        return format_html(html)
    verification_summary.short_description = '[SECURE] Verification'
    
    def ip_exceptions_display(self, obj):
        html = '<div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">'
        html += '<h4 style="margin-top: 0;">📋 IP & ASN Exceptions</h4>'
        
        # Allowed IPs
        if obj.allowed_ips:
            html += '<div style="margin-bottom: 15px;">'
            html += '<strong>Allowed IP Addresses:</strong>'
            html += '<div style="display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px;">'
            for ip in obj.allowed_ips[:10]:
                html += f'<span style="background: #28a745; color: white; padding: 4px 8px; '
                html += f'border-radius: 10px; font-size: 10px; font-family: monospace;">{ip}</span>'
            if len(obj.allowed_ips) > 10:
                html += f'<span style="color: #6c757d;">+{len(obj.allowed_ips) - 10} more</span>'
            html += '</div></div>'
        
        # Allowed ASNs
        if obj.allowed_asns:
            html += '<div>'
            html += '<strong>Allowed ASNs:</strong>'
            html += '<div style="display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px;">'
            for asn in obj.allowed_asns[:10]:
                html += f'<span style="background: #17a2b8; color: white; padding: 4px 8px; '
                html += f'border-radius: 10px; font-size: 10px;">AS{asn}</span>'
            if len(obj.allowed_asns) > 10:
                html += f'<span style="color: #6c757d;">+{len(obj.allowed_asns) - 10} more</span>'
            html += '</div></div>'
        
        if not obj.allowed_ips and not obj.allowed_asns:
            html += '<div style="text-align: center; padding: 20px; color: #6c757d;">No exceptions configured</div>'
        
        html += '</div>'
        
        return format_html(html)
    ip_exceptions_display.short_description = '📋 Exceptions'
    
    def activate_rules(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} rule(s) activated.')
    activate_rules.short_description = '[OK] Activate rules'
    
    def deactivate_rules(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} rule(s) deactivated.')
    deactivate_rules.short_description = '[ERROR] Deactivate rules'
    
    def require_full_verification(self, request, queryset):
        count = queryset.update(
            require_phone_verification=True,
            require_id_verification=True,
            require_address_verification=True
        )
        self.message_user(request, f'{count} rule(s) now require full verification.')
    require_full_verification.short_description = '[SECURE] Require full verification'
      
    
# # security/admin.py - Dashboard Enhancement (শেষে যোগ করো)
# class SecurityAdminSite(admin.AdminSite):
#     site_header = '[SECURE] Earning Platform - Security Administration'
#     site_title = 'Security Admin Portal'
#     index_title = 'Security Dashboard'
    
#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path('security-dashboard/', self.admin_view(self.security_dashboard_view), name='security_dashboard'),
#         ]
#         return custom_urls + urls
    
#     def security_dashboard_view(self, request):
#         """Custom Security Dashboard"""
        
#         # Calculate date ranges
#         today = timezone.now()
#         last_7_days = today - timedelta(days=7)
#         last_30_days = today - timedelta(days=30)
        
#         # === USER STATISTICS ===
#         from django.contrib.auth import get_user_model
#         User = get_user_model()
        
#         total_users = User.objects.count()
#         active_users_today = User.objects.filter(last_login__gte=today - timedelta(hours=24)).count()
#         new_users_week = User.objects.filter(date_joined__gte=last_7_days).count()
        
#         # === SECURITY STATISTICS ===
#         total_threats = SecurityLog.objects.count()
#         threats_today = SecurityLog.objects.filter(created_at__gte=today - timedelta(hours=24)).count()
#         critical_threats = SecurityLog.objects.filter(severity='critical').count()
#         unresolved_threats = SecurityLog.objects.filter(resolved=False).count()
        
#         # === DEVICE STATISTICS ===
#         total_devices = DeviceInfo.objects.count()
#         rooted_devices = DeviceInfo.objects.filter(is_rooted=True).count()
#         vpn_detected = DeviceInfo.objects.filter(is_vpn=True).count()
#         suspicious_devices = DeviceInfo.objects.filter(risk_score__gte=70).count()
        
#         # === BAN STATISTICS ===
#         total_bans = UserBan.objects.count()
#         active_bans = UserBan.objects.filter(is_active_ban=True).count()
#         permanent_bans = UserBan.objects.filter(is_permanent=True).count()
        
#         # === IP BLACKLIST STATISTICS ===
#         blocked_ips = IPBlacklist.objects.filter(is_active=True).count()
        
#         # === RECENT ACTIVITIES ===
#         recent_threats = SecurityLog.objects.select_related('user', 'device_info').order_by('-created_at')[:10]
#         recent_bans = UserBan.objects.select_related('user').order_by('-created_at')[:5]
#         high_risk_users = RiskScore.objects.filter(current_score__gte=70).select_related('user').order_by('-current_score')[:10]
        
#         # === THREAT BREAKDOWN ===
#         threat_types = SecurityLog.objects.values('security_type').annotate(
#             count=Count('id')
#         ).order_by('-count')[:5]
        
#         context = {
#             # Summaries
#             'total_users': total_users,
#             'active_users_today': active_users_today,
#             'new_users_week': new_users_week,
            
#             'total_threats': total_threats,
#             'threats_today': threats_today,
#             'critical_threats': critical_threats,
#             'unresolved_threats': unresolved_threats,
            
#             'total_devices': total_devices,
#             'rooted_devices': rooted_devices,
#             'vpn_detected': vpn_detected,
#             'suspicious_devices': suspicious_devices,
            
#             'total_bans': total_bans,
#             'active_bans': active_bans,
#             'permanent_bans': permanent_bans,
#             'blocked_ips': blocked_ips,
            
#             # Recent Activities
#             'recent_threats': recent_threats,
#             'recent_bans': recent_bans,
#             'high_risk_users': high_risk_users,
#             'threat_types': threat_types,
            
#             # Metadata
#             'dashboard_generated': timezone.now(),
#         }
        
#         return render(request, 'admin/security_dashboard.html', context)
    
#     def index(self, request, extra_context=None):
#         """Override admin index to show dashboard link"""
#         extra_context = extra_context or {}
#         extra_context['show_dashboard_link'] = True
#         return super().index(request, extra_context)


# # Replace default admin site
# # Comment out or remove if already using custom admin site
# # admin.site = SecurityAdminSite(name='security_admin')

# # security/admin.py - একদম শেষে এই কোড যোগ করুন

# # ==================== ADMIN SITE CUSTOMIZATION ====================

# # Custom admin site header
# admin.site.site_header = '[SECURE] Security & Protection Administration'
# admin.site.site_title = 'Security Admin Portal'
# admin.site.index_title = 'Security Management Dashboard'

# # Enable admin site for your app
# from django.contrib.admin import AdminSite

# # Optional: Custom AdminSite class for better organization
# class SecurityAdminSite(AdminSite):
#     site_header = '[SECURE] Security & Protection Administration'
#     site_title = 'Security Admin'
#     index_title = 'Welcome to Security Management'
    
#     def get_app_list(self, request):
#         """
#         Return a sorted list of all installed apps with models registered for admin
#         """
#         app_dict = self._build_app_dict(request)
        
#         # Sort the apps alphabetically
#         app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())
        
#         # Sort models within each app
#         for app in app_list:
#             app['models'].sort(key=lambda x: x['name'])
        
#         return app_list

# # আপনি চাইলে এটা use করতে পারেন (optional):
# # security_admin_site = SecurityAdminSite(name='security_admin')

# # তারপর সব models এই site এ register করুন

# # ১. আপনার কাস্টম অ্যাডমিন ক্লাসটির একটি অবজেক্ট তৈরি করুন
# # ১. কাস্টম সাইট অবজেক্ট তৈরি
# security_admin_site = SecurityAdminSite(name='security_admin')

# # ২. ড্যাশবোর্ডের রাস্তা (URL) ঠিক করা
# def get_custom_urls(self):
#     urls = super(SecurityAdminSite, self).get_urls()
#     custom_urls = [
#         # খেয়াল করুন, এখানে name টা 'security_dashboard' হতে হবে
#         path('security-dashboard/', self.admin_view(self.security_dashboard_view), name='security_dashboard'),
#     ]
#     return custom_urls + urls

# # ডাইনামিকালি সেট করা
# SecurityAdminSite.get_urls = get_custom_urls

# # ৩. লুপ চালিয়ে সব মডেল একসাথে রেজিস্টার করা (নিরাপদ উপায়)
# from django.contrib.admin.sites import AlreadyRegistered

# for model, model_admin in admin.site._registry.items():
#     if model._meta.app_label == 'security':
#         try:
#             security_admin_site.register(model, type(model_admin))
#         except AlreadyRegistered:
#             pass

# security/admin.py
"""
Security Admin Module with Comprehensive Defensive Programming
Author: Your Name
Last Updated: 2024
"""
try:
    from django.contrib import admin
    from django.urls import path, reverse
    from django.shortcuts import render
    from django.utils import timezone
    from django.db.models import Count, QuerySet, Model
    from django.http import HttpRequest, HttpResponse, JsonResponse
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ImproperlyConfigured, PermissionDenied
    from django.contrib.admin.sites import AlreadyRegistered
    from django.views.decorators.cache import never_cache
    from django.views.decorators.csrf import csrf_protect
    from django.contrib.auth.decorators import login_required, permission_required
    from django.conf import settings
except ImportError as e:
    print(f"CRITICAL: Django imports failed: {e}")
    sys.exit(1)

# Local imports with fallback
try:
    from .models import (
        SecurityLog, DeviceInfo, UserBan, 
        IPBlacklist, RiskScore
    )
except ImportError as e:
    print(f"WARNING: Some models not available: {e}")
    # Create placeholder classes if models don't exist
    class PlaceholderModel:
        def __init__(self, *args, **kwargs):
            pass
        
        @classmethod
        def objects(cls):
            return PlaceholderQuerySet()
    
    class PlaceholderQuerySet:
        def count(self): return 0
        def filter(self, **kwargs): return self
        def all(self): return self
        def select_related(self, *args): return self
        def order_by(self, *args): return self
    
    # Assign placeholders
    SecurityLog = PlaceholderModel
    DeviceInfo = PlaceholderModel
    UserBan = PlaceholderModel
    IPBlacklist = PlaceholderModel
    RiskScore = PlaceholderModel
    

# ==================== 2. لاگر کنفیگریشن ====================
def setup_logger() -> logging.Logger:
    """Setup secure logger with rotation"""
    logger = logging.getLogger('security_admin')
    
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # File handler with rotation (if configured)
        try:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                'logs/security_admin.log', 
                maxBytes=10485760,  # 10MB
                backupCount=5
            )
            file_handler.setLevel(logging.WARNING)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"File logging not available: {e}")
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    return logger

logger = setup_logger()

# ==================== 3. ڈیکوریٹرز ====================
def safe_view(func: Callable) -> Callable:
    """Decorator for safe view execution"""
    @wraps(func)
    def wrapper(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        try:
            # Check permissions
            if not request.user.is_active or not request.user.is_staff:
                raise PermissionDenied("Insufficient permissions")
            
            return func(self, request, *args, **kwargs)
            
        except PermissionDenied as e:
            logger.warning(f"Permission denied for {request.user}: {e}")
            return render(request, 'admin/permission_denied.html', {
                'error': str(e)
            }, status=403)
            
        except Exception as e:
            logger.exception(f"Error in {func.__name__}: {e}")
            
            if settings.DEBUG:
                # Show detailed error in debug mode
                return render(request, 'admin/error_debug.html', {
                    'error': str(e),
                    'traceback': traceback.format_exc(),
                    'view': func.__name__
                })
            else:
                # Show user-friendly error in production
                return render(request, 'admin/error_generic.html', {
                    'error': 'An error occurred. Our team has been notified.'
                }, status=500)
    
    return wrapper

def cache_result(timeout: int = 300) -> Callable:
    """Cache expensive operations"""
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check cache
            if key in cache:
                result, timestamp = cache[key]
                if (datetime.now() - timestamp).seconds < timeout:
                    return result
            
            # Execute function
            result = func(*args, **kwargs)
            cache[key] = (result, datetime.now())
            
            # Clean old cache entries
            for k in list(cache.keys()):
                if (datetime.now() - cache[k][1]).seconds > timeout:
                    del cache[k]
            
            return result
        
        return wrapper
    return decorator

# ==================== 4. ڈیٹا ویلڈیشن کلاسز ====================
class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_date_range(start_date: Optional[datetime], 
                           end_date: Optional[datetime]) -> Tuple[datetime, datetime]:
        """Validate and fix date range"""
        now = timezone.now()
        
        if start_date is None:
            start_date = now - timedelta(days=30)
        
        if end_date is None:
            end_date = now
        
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        if end_date > now:
            end_date = now
        
        return start_date, end_date
    
    @staticmethod
    def validate_int(value: Any, default: int = 0, min_val: Optional[int] = None, 
                     max_val: Optional[int] = None) -> int:
        """Validate integer values"""
        try:
            result = int(value) if value is not None else default
            if min_val is not None:
                result = max(result, min_val)
            if max_val is not None:
                result = min(result, max_val)
            return result
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def validate_string(value: Any, default: str = "", 
                        max_length: Optional[int] = None) -> str:
        """Validate string values"""
        try:
            result = str(value) if value is not None else default
            if max_length and len(result) > max_length:
                result = result[:max_length]
            return result
        except Exception:
            return default

class SafeQuerySet:
    """Ultimate safe queryset wrapper"""
    
    def __init__(self, queryset: Optional[QuerySet] = None, model_name: str = "Unknown"):
        self._queryset = queryset
        self.model_name = model_name
    
    def safe_count(self, default: int = 0) -> int:
        """Safely count queryset"""
        if self._queryset is None:
            logger.debug(f"Queryset is None for {self.model_name}")
            return default
        
        try:
            # Check if queryset exists in database
            if not self._queryset.model._meta.db_table:
                logger.warning(f"Table doesn't exist for {self.model_name}")
                return default
            
            return self._queryset.count()
            
        except Exception as e:
            logger.error(f"Error counting {self.model_name}: {e}")
            return default
    
    def safe_filter(self, default: Optional[QuerySet] = None, **kwargs) -> 'SafeQuerySet':
        """Safely filter queryset"""
        if self._queryset is None:
            return SafeQuerySet(default, self.model_name)
        
        try:
            filtered = self._queryset.filter(**kwargs)
            return SafeQuerySet(filtered, self.model_name)
        except Exception as e:
            logger.error(f"Error filtering {self.model_name}: {e}")
            return SafeQuerySet(default, self.model_name)
    
    def safe_exists(self) -> bool:
        """Safely check if queryset has results"""
        return self.safe_count() > 0
    
    def safe_first(self, default: Optional[Model] = None) -> Optional[Model]:
        """Safely get first object"""
        if self._queryset is None:
            return default
        
        try:
            return self._queryset.first()
        except Exception as e:
            logger.error(f"Error getting first from {self.model_name}: {e}")
            return default
    
    def safe_list(self, default: Optional[List] = None) -> List:
        """Safely convert to list"""
        if self._queryset is None:
            return default or []
        
        try:
            return list(self._queryset)
        except Exception as e:
            logger.error(f"Error converting to list {self.model_name}: {e}")
            return default or []
    
    def execute_safe(self, operation: str, **kwargs) -> Any:
        """Execute any queryset operation safely"""
        try:
            method = getattr(self._queryset, operation, None)
            if method and callable(method):
                return method(**kwargs)
        except Exception as e:
            logger.error(f"Error executing {operation} on {self.model_name}: {e}")
        
        return None

# ==================== 5. ڈیٹا ریٹریور کلاس ====================
class DataRetriever:
    """Centralized data retrieval with error handling"""
    
    def __init__(self):
        self._cache = {}
        self._stats = {
            'success': 0,
            'failures': 0,
            'last_error': None
        }
    
    def get_user_model(self):
        """Safely get user model"""
        try:
            return get_user_model()
        except Exception as e:
            logger.error(f"Error getting user model: {e}")
            return None
    
    @cache_result(timeout=60)  # Cache for 1 minute
    def get_user_stats(self, date_ranges: Dict[str, datetime]) -> Dict[str, int]:
        """Get user statistics with validation"""
        result = {
            'total_users': 0,
            'active_users_today': 0,
            'new_users_week': 0,
            'verified_users': 0,
            'banned_users': 0,
        }
        
        try:
            User = self.get_user_model()
            if User is None:
                return result
            
            user_qs = SafeQuerySet(User.objects.all(), "User")
            
            result.update({
                'total_users': user_qs.safe_count(),
                'active_users_today': SafeQuerySet(
                    User.objects.filter(last_login__gte=date_ranges['last_24_hours']),
                    "Active Users"
                ).safe_count(),
                'new_users_week': SafeQuerySet(
                    User.objects.filter(date_joined__gte=date_ranges['last_7_days']),
                    "New Users"
                ).safe_count(),
            })
            
            # Try to get additional fields if they exist
            try:
                if hasattr(User, 'is_verified'):
                    result['verified_users'] = SafeQuerySet(
                        User.objects.filter(is_verified=True),
                        "Verified Users"
                    ).safe_count()
            except Exception as e:
                logger.debug(f"Verified users field not available: {e}")
            
            self._stats['success'] += 1
            
        except Exception as e:
            self._stats['failures'] += 1
            self._stats['last_error'] = str(e)
            logger.error(f"Error in get_user_stats: {e}")
        
        return result
    
    @cache_result(timeout=30)  # Cache for 30 seconds
    def get_security_stats(self, date_ranges: Dict[str, datetime]) -> Dict[str, int]:
        """Get security statistics with validation"""
        result = {
            'total_threats': 0,
            'threats_today': 0,
            'critical_threats': 0,
            'unresolved_threats': 0,
            'high_severity': 0,
            'medium_severity': 0,
            'low_severity': 0,
        }
        
        try:
            if SecurityLog is None:
                return result
            
            log_qs = SafeQuerySet(SecurityLog.objects.all(), "SecurityLog")
            
            result.update({
                'total_threats': log_qs.safe_count(),
                'threats_today': SafeQuerySet(
                    SecurityLog.objects.filter(created_at__gte=date_ranges['last_24_hours']),
                    "Today's Threats"
                ).safe_count(),
                'unresolved_threats': SafeQuerySet(
                    SecurityLog.objects.filter(resolved=False),
                    "Unresolved Threats"
                ).safe_count(),
            })
            
            # Severity breakdown
            for severity in ['critical', 'high', 'medium', 'low']:
                try:
                    result[f'{severity}_threats'] = SafeQuerySet(
                        SecurityLog.objects.filter(severity=severity),
                        f"{severity} Threats"
                    ).safe_count()
                except Exception:
                    pass
            
        except Exception as e:
            logger.error(f"Error in get_security_stats: {e}")
        
        return result
    
    def get_all_stats(self, request: HttpRequest) -> Dict[str, Any]:
        """Get all statistics in one go"""
        date_ranges = self.get_date_ranges()
        
        stats = {
            # Date ranges
            **date_ranges,
            
            # User stats
            **self.get_user_stats(date_ranges),
            
            # Security stats
            **self.get_security_stats(date_ranges),
            
            # Device stats (if available)
            **self.get_device_stats(),
            
            # Ban stats (if available)
            **self.get_ban_stats(),
            
            # IP stats (if available)
            **self.get_ip_stats(),
            
            # Recent activities
            **self.get_recent_activities(),
            
            # Performance stats
            'query_performance': self._stats,
            'dashboard_generated': timezone.now(),
        }
        
        return stats
    
    def get_date_ranges(self, reference: Optional[datetime] = None) -> Dict[str, datetime]:
        """Get validated date ranges"""
        try:
            now = reference or timezone.now()
            return {
                'now': now,
                'today_start': now.replace(hour=0, minute=0, second=0, microsecond=0),
                'last_24_hours': now - timedelta(hours=24),
                'last_7_days': now - timedelta(days=7),
                'last_30_days': now - timedelta(days=30),
                'last_90_days': now - timedelta(days=90),
            }
        except Exception as e:
            logger.error(f"Error calculating date ranges: {e}")
            fallback = datetime.now()
            return {
                'now': fallback,
                'today_start': fallback.replace(hour=0, minute=0, second=0, microsecond=0),
                'last_24_hours': fallback - timedelta(hours=24),
                'last_7_days': fallback - timedelta(days=7),
                'last_30_days': fallback - timedelta(days=30),
                'last_90_days': fallback - timedelta(days=90),
            }

# security/admin.py - _safe_admin_view FIX

# ==================== সমস্যার কারণ ====================
# [ERROR] WRONG - এভাবে করলে request argument missing হয়
def _safe_admin_view(self, view):
    @wraps(view)
    @never_cache
    @csrf_protect
    @login_required                    # ← এটা request miss করে
    @permission_required('is_staff')   # ← এটাও
    @safe_view
    def wrapper(request, *args, **kwargs):
        return view(request, *args, **kwargs)
    return wrapper

# [OK] CORRECT - এভাবে করুন
def _safe_admin_view(self, view):
    """Create safe admin view - FIXED VERSION"""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        return view(request, *args, **kwargs)
    # Django admin এর built-in method use করুন
    return self.admin_site.admin_view(wrapper)

# ==================== সম্পূর্ণ FIX ====================

class SecurityAdminSite(admin.AdminSite):
    """
    Ultimate Security Admin Site - FULLY FIXED & BULLETPROOF
    """
    
    site_header = '[SECURE] Earning Platform - Security Administration'
    site_title = 'Security Admin Portal'
    index_title = 'Security Dashboard'
    
    def __init__(self, *args, **kwargs):
        """Initialize with defensive setup"""
        try:
            super().__init__(*args, **kwargs)
            logger.info("[OK] SecurityAdminSite initialized")
        except Exception as e:
            logger.critical(f"[ERROR] Init failed: {e}")
            raise
    
    def get_urls(self):
        """[OK] FIXED: Correct URL registration"""
        try:
            urls = super().get_urls()
            
            custom_urls = [
                path(
                    'security-dashboard/',
                    # [OK] KEY FIX: self.admin_view() use করুন
                    # এটা automatically request, auth সব handle করে
                    self.admin_view(self.security_dashboard_view),
                    name='security_dashboard'
                ),
                path(
                    'security-dashboard/json/',
                    self.admin_view(self.security_dashboard_json),
                    name='security_dashboard_json'
                ),
                path(
                    'security-stats/<str:stat_type>/',
                    self.admin_view(self.get_statistics_api),
                    name='security_stats_api'
                ),
            ]
            
            return custom_urls + urls
            
        except Exception as e:
            logger.error(f"[ERROR] URL generation failed: {e}")
            # Minimum fallback
            return [
                path(
                    'security-dashboard/',
                    self.admin_view(self.security_dashboard_view),
                    name='security_dashboard'
                ),
            ] + super().get_urls()
    
    def security_dashboard_view(self, request):
        """
        [OK] FIXED: Main security dashboard view
        self.admin_view() already handles:
        - Authentication check
        - Permission check  
        - CSRF protection
        - Cache control
        """
        try:
            # Staff check (extra safety)
            if not request.user.is_staff:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            
            # Get statistics safely
            stats = self._get_dashboard_stats_safe(request)
            
            context = {
                **self.each_context(request),  # [OK] Admin context add করুন
                **stats,
                'title': '[SECURE] Security Dashboard',
                'user': request.user,
            }
            
            # Template render with fallback
            try:
                return render(
                    request,
                    'admin/security_dashboard.html',
                    context
                )
            except Exception as template_error:
                logger.warning(f"Template missing, using fallback: {template_error}")
                return self._fallback_dashboard_response(request, stats)
                
        except Exception as e:
            logger.exception(f"[ERROR] Dashboard failed: {e}")
            return self._error_response(request, e)
    
    def security_dashboard_json(self, request):
        """[OK] FIXED: JSON API endpoint"""
        try:
            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            
            stats = self._get_dashboard_stats_safe(request)
            
            # Convert non-serializable objects
            clean_stats = self._make_json_safe(stats)
            
            return JsonResponse({
                'success': True,
                'data': clean_stats,
                'timestamp': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.exception(f"[ERROR] JSON API failed: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e) if settings.DEBUG else 'Internal server error',
            }, status=500)
    
    def get_statistics_api(self, request, stat_type):
        """[OK] FIXED: Statistics API"""
        try:
            if not request.user.is_staff:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
            
            valid_types = ['users', 'security', 'devices', 'bans', 'ips']
            
            if stat_type not in valid_types:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid type. Valid: {valid_types}'
                }, status=400)
            
            data = self._get_stat_by_type(stat_type)
            
            return JsonResponse({
                'success': True,
                'type': stat_type,
                'data': data,
                'timestamp': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.exception(f"[ERROR] Stats API failed: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e) if settings.DEBUG else 'Server error',
            }, status=500)
    
    def _get_dashboard_stats_safe(self, request):
        """[OK] Safely get all dashboard stats"""
        stats = {}
        
        # ---- User Stats ----
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            stats['total_users'] = User.objects.count()
            stats['active_users_today'] = User.objects.filter(
                last_login__date=timezone.now().date()
            ).count()
        except Exception as e:
            logger.error(f"User stats error: {e}")
            stats['total_users'] = 0
            stats['active_users_today'] = 0
        
        # ---- Security Log Stats ----
        try:
            from .models import SecurityLog
            stats['total_threats'] = SecurityLog.objects.count()
            stats['critical_threats'] = SecurityLog.objects.filter(
                severity='critical'
            ).count()
            stats['high_threats'] = SecurityLog.objects.filter(
                severity='high'
            ).count()
            stats['threats_today'] = SecurityLog.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
        except Exception as e:
            logger.error(f"SecurityLog stats error: {e}")
            stats['total_threats'] = 0
            stats['critical_threats'] = 0
            stats['high_threats'] = 0
            stats['threats_today'] = 0
        
        # ---- Device Stats ----
        try:
            from .models import DeviceInfo
            stats['total_devices'] = DeviceInfo.objects.count()
            stats['rooted_devices'] = DeviceInfo.objects.filter(
                is_rooted=True
            ).count()
            stats['emulator_devices'] = DeviceInfo.objects.filter(
                is_emulator=True
            ).count()
        except Exception as e:
            logger.error(f"Device stats error: {e}")
            stats['total_devices'] = 0
            stats['rooted_devices'] = 0
            stats['emulator_devices'] = 0
        
        # ---- Ban Stats ----
        try:
            from .models import UserBan
            stats['total_bans'] = UserBan.objects.count()
            stats['active_bans'] = UserBan.objects.filter(
                is_active_ban=True
            ).count()
            stats['permanent_bans'] = UserBan.objects.filter(
                is_permanent=True,
                is_active_ban=True
            ).count()
        except Exception as e:
            logger.error(f"Ban stats error: {e}")
            stats['total_bans'] = 0
            stats['active_bans'] = 0
            stats['permanent_bans'] = 0
        
        # ---- IP Blacklist Stats ----
        try:
            from .models import IPBlacklist
            stats['blocked_ips'] = IPBlacklist.objects.filter(
                is_active=True
            ).count()
            stats['permanent_blocks'] = IPBlacklist.objects.filter(
                is_permanent=True,
                is_active=True
            ).count()
        except Exception as e:
            logger.error(f"IP stats error: {e}")
            stats['blocked_ips'] = 0
            stats['permanent_blocks'] = 0
        
        # ---- Risk Score Stats ----
        try:
            from .models import RiskScore
            high_risk = RiskScore.objects.filter(
                current_score__gte=70
            ).count()
            stats['high_risk_users'] = high_risk
        except Exception as e:
            logger.error(f"Risk stats error: {e}")
            stats['high_risk_users'] = 0
        
        stats['dashboard_generated'] = timezone.now().isoformat()
        
        return stats
    
    def _get_stat_by_type(self, stat_type):
        """Get specific stats by type"""
        try:
            if stat_type == 'users':
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return {
                    'total': User.objects.count(),
                    'active_today': User.objects.filter(
                        last_login__date=timezone.now().date()
                    ).count(),
                }
            elif stat_type == 'security':
                from .models import SecurityLog
                return {
                    'total': SecurityLog.objects.count(),
                    'critical': SecurityLog.objects.filter(severity='critical').count(),
                    'high': SecurityLog.objects.filter(severity='high').count(),
                    'today': SecurityLog.objects.filter(
                        created_at__date=timezone.now().date()
                    ).count(),
                }
            elif stat_type == 'devices':
                from .models import DeviceInfo
                return {
                    'total': DeviceInfo.objects.count(),
                    'rooted': DeviceInfo.objects.filter(is_rooted=True).count(),
                    'emulator': DeviceInfo.objects.filter(is_emulator=True).count(),
                }
            elif stat_type == 'bans':
                from .models import UserBan
                return {
                    'total': UserBan.objects.count(),
                    'active': UserBan.objects.filter(is_active_ban=True).count(),
                }
            elif stat_type == 'ips':
                from .models import IPBlacklist
                return {
                    'blocked': IPBlacklist.objects.filter(is_active=True).count(),
                    'permanent': IPBlacklist.objects.filter(
                        is_permanent=True,
                        is_active=True
                    ).count(),
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting {stat_type} stats: {e}")
            return {'error': str(e)}
    
    def _make_json_safe(self, data):
        """Convert data to JSON-serializable format"""
        clean = {}
        for key, value in data.items():
            try:
                if isinstance(value, (int, float, str, bool, list, dict)):
                    clean[key] = value
                elif value is None:
                    clean[key] = None
                else:
                    clean[key] = str(value)
            except Exception:
                clean[key] = 0
        return clean
    
    def _fallback_dashboard_response(self, request, stats):
        """[OK] Simple HTML fallback if template missing"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>[SECURE] Security Dashboard</title>
            <style>
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{ 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    background: #f0f2f5; 
                    min-height: 100vh;
                }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; 
                    padding: 20px 30px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                }}
                .header h1 {{ font-size: 24px; }}
                .header p {{ opacity: 0.85; font-size: 14px; margin-top: 5px; }}
                .container {{ max-width: 1200px; margin: 30px auto; padding: 0 20px; }}
                .grid {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .card {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                    text-align: center;
                    transition: transform 0.2s;
                }}
                .card:hover {{ transform: translateY(-3px); }}
                .card .icon {{ font-size: 36px; margin-bottom: 10px; }}
                .card .number {{ 
                    font-size: 32px; 
                    font-weight: bold; 
                    color: #333;
                    margin-bottom: 5px;
                }}
                .card .label {{ 
                    font-size: 13px; 
                    color: #666;
                    font-weight: 500;
                }}
                .card.blue {{ border-top: 4px solid #2196F3; }}
                .card.green {{ border-top: 4px solid #4CAF50; }}
                .card.red {{ border-top: 4px solid #F44336; }}
                .card.orange {{ border-top: 4px solid #FF9800; }}
                .card.purple {{ border-top: 4px solid #9C27B0; }}
                .card.teal {{ border-top: 4px solid #009688; }}
                .section-title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 15px;
                    padding-bottom: 8px;
                    border-bottom: 2px solid #eee;
                }}
                .back-link {{
                    display: inline-block;
                    margin-top: 20px;
                    padding: 10px 20px;
                    background: #667eea;
                    color: white;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: bold;
                }}
                .back-link:hover {{ background: #5a6fd6; }}
                .timestamp {{
                    text-align: right;
                    color: #999;
                    font-size: 12px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>[SECURE] Security Dashboard</h1>
                <p>Welcome, {request.user.username} | Earning Platform Security Administration</p>
            </div>
            
            <div class="container">
                <div class="section-title">👥 User Statistics</div>
                <div class="grid">
                    <div class="card blue">
                        <div class="icon">👥</div>
                        <div class="number">{stats.get('total_users', 0)}</div>
                        <div class="label">Total Users</div>
                    </div>
                    <div class="card green">
                        <div class="icon">[OK]</div>
                        <div class="number">{stats.get('active_users_today', 0)}</div>
                        <div class="label">Active Today</div>
                    </div>
                    <div class="card red">
                        <div class="icon">[WARN]</div>
                        <div class="number">{stats.get('high_risk_users', 0)}</div>
                        <div class="label">High Risk Users</div>
                    </div>
                </div>
                
                <div class="section-title">🔒 Security Statistics</div>
                <div class="grid">
                    <div class="card orange">
                        <div class="icon">🚨</div>
                        <div class="number">{stats.get('total_threats', 0)}</div>
                        <div class="label">Total Threats</div>
                    </div>
                    <div class="card red">
                        <div class="icon">🔴</div>
                        <div class="number">{stats.get('critical_threats', 0)}</div>
                        <div class="label">Critical Threats</div>
                    </div>
                    <div class="card orange">
                        <div class="icon">🟠</div>
                        <div class="number">{stats.get('high_threats', 0)}</div>
                        <div class="label">High Threats</div>
                    </div>
                    <div class="card blue">
                        <div class="icon">📅</div>
                        <div class="number">{stats.get('threats_today', 0)}</div>
                        <div class="label">Threats Today</div>
                    </div>
                </div>
                
                <div class="section-title">📱 Device Statistics</div>
                <div class="grid">
                    <div class="card teal">
                        <div class="icon">📱</div>
                        <div class="number">{stats.get('total_devices', 0)}</div>
                        <div class="label">Total Devices</div>
                    </div>
                    <div class="card red">
                        <div class="icon">🔓</div>
                        <div class="number">{stats.get('rooted_devices', 0)}</div>
                        <div class="label">Rooted Devices</div>
                    </div>
                    <div class="card orange">
                        <div class="icon">🤖</div>
                        <div class="number">{stats.get('emulator_devices', 0)}</div>
                        <div class="label">Emulators</div>
                    </div>
                </div>
                
                <div class="section-title">🚫 Ban & Block Statistics</div>
                <div class="grid">
                    <div class="card red">
                        <div class="icon">🚫</div>
                        <div class="number">{stats.get('total_bans', 0)}</div>
                        <div class="label">Total Bans</div>
                    </div>
                    <div class="card orange">
                        <div class="icon">⛔</div>
                        <div class="number">{stats.get('active_bans', 0)}</div>
                        <div class="label">Active Bans</div>
                    </div>
                    <div class="card purple">
                        <div class="icon">🔒</div>
                        <div class="number">{stats.get('blocked_ips', 0)}</div>
                        <div class="label">Blocked IPs</div>
                    </div>
                    <div class="card red">
                        <div class="icon">[ERROR]</div>
                        <div class="number">{stats.get('permanent_blocks', 0)}</div>
                        <div class="label">Permanent Blocks</div>
                    </div>
                </div>
                
                <a href="/api/security-admin/" class="back-link">← Back to Admin</a>
                
                <div class="timestamp">
                    Generated: {stats.get('dashboard_generated', 'Unknown')}
                </div>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html)
    
    def _error_response(self, request, error):
        """[OK] Error response with debug info"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Dashboard Error</title></head>
        <body style="font-family: Arial; padding: 30px; background: #fff5f5;">
            <h2 style="color: #F44336;">[ERROR] Dashboard Error</h2>
            <p><strong>Error:</strong> {str(error) if settings.DEBUG else 'Internal server error'}</p>
            <p><strong>Type:</strong> {type(error).__name__ if settings.DEBUG else 'Error'}</p>
            <p><strong>Time:</strong> {timezone.now()}</p>
            <br>
            <a href="/api/security-admin/" 
               style="background: #667eea; color: white; padding: 10px 20px; 
                      border-radius: 5px; text-decoration: none;">
               ← Back to Admin
            </a>
        </body>
        </html>
        """
        return HttpResponse(html, status=500)
    
    def index(self, request, extra_context=None):
        """[OK] Override index with security info"""
        try:
            extra_context = extra_context or {}
            extra_context.update({
                'show_dashboard_link': True,
                'dashboard_url': '/api/security-admin/security-dashboard/',
                'welcome_message': (
                    f'Welcome, {request.user.get_full_name() or request.user.username}!'
                ),
            })
            return super().index(request, extra_context)
        except Exception as e:
            logger.error(f"Index error: {e}")
            return super().index(request, {})


# ==================== MODEL REGISTRATION ====================

def safe_register(admin_site, model, admin_class=None):
    """[OK] Safely register a single model"""
    try:
        if model is None:
            return False
        
        if model in admin_site._registry:
            logger.debug(f"Already registered: {model.__name__}")
            return True
        
        if admin_class:
            admin_site.register(model, admin_class)
        else:
            admin_site.register(model)
        
        logger.info(f"[OK] Registered: {model.__name__}")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to register {getattr(model, '__name__', 'Unknown')}: {e}")
        return False


# ==================== CREATE ADMIN SITE ====================


from django.contrib.admin import AdminSite

# ১. প্রথমে ক্লাস তৈরি করুন
class SecurityAdminSite(AdminSite):
    site_header = "Security Admin Portal"
    site_title = "Security Admin"
    index_title = "Welcome to Security Portal"

# ২. ভেরিয়েবলটি ডিফাইন করুন (এটি না থাকলে NameError দেয়)
security_admin_site = SecurityAdminSite(name='security_admin')


# ==================== REGISTER MODELS ====================
from .models import (
    DeviceInfo, SecurityLog, RiskScore, SecurityDashboard, AutoBlockRule,
    AuditTrail, DataExport, DataImport, SecurityNotification, AlertRule,
    FraudPattern, RealTimeDetection, Country, GeolocationLog, CountryBlockRule,
    APIRateLimit, RateLimitLog, PasswordPolicy, PasswordHistory, PasswordAttempt,
    UserSession, SessionActivity, TwoFactorMethod, TwoFactorAttempt,
    TwoFactorRecoveryCode, UserBan, ClickTracker, MaintenanceMode,
    SecurityConfig, AppVersion, IPBlacklist, WithdrawalProtection
)

security_models_list = [
    DeviceInfo, SecurityLog, RiskScore, SecurityDashboard, AutoBlockRule,
    AuditTrail, DataExport, DataImport, SecurityNotification, AlertRule,
    FraudPattern, RealTimeDetection, Country, GeolocationLog, CountryBlockRule,
    APIRateLimit, RateLimitLog, PasswordPolicy, PasswordHistory, PasswordAttempt,
    UserSession, SessionActivity, TwoFactorMethod, TwoFactorAttempt,
    TwoFactorRecoveryCode, UserBan, ClickTracker, MaintenanceMode,
    SecurityConfig, AppVersion, IPBlacklist, WithdrawalProtection
]

print("\n[SECURE] Registering Security models in BOTH admin sites...")

for model in security_models_list:
    # ডিফল্ট অ্যাডমিনে রেজিস্ট্রেশন
    if not admin.site.is_registered(model):
        try:
            admin.site.register(model)
        except Exception:
            pass
        
    # আপনার কাস্টম সিকিউরিটি পোর্টালে রেজিস্ট্রেশন
    try:
        security_admin_site.register(model)
    except Exception:
        pass

print(f"[SECURE] Registration Complete!")