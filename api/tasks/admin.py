# tasks/admin.py
"""
Beautiful & Bulletproof Admin Panel for Task Management System
- Defensive coding principles applied
- Graceful error handling
- Null-safe operations
- Beautiful colorful design
- Performance optimized
"""

from django.contrib import admin
from django.utils.html import format_html, escape
from django.urls import reverse, path
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from .models import MasterTask, UserTaskCompletion, AdminLedger
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


# ==================== DEFENSIVE UTILITIES ====================

class SafeDisplay:
    """Defensive display utilities"""
    
    @staticmethod
    def safe_format(value, default='-'):
        """Safely format value with null check"""
        try:
            return escape(str(value)) if value is not None else default
        except Exception as e:
            logger.warning(f"Error formatting value: {e}")
            return default
    
    @staticmethod
    def safe_decimal(value, default=0.0):
        """Safely convert to decimal"""
        try:
            if value is None:
                return Decimal(str(default))
            return Decimal(str(value))
        except (ValueError, InvalidOperation, TypeError):
            return Decimal(str(default))
    
    @staticmethod
    def safe_int(value, default=0):
        """Safely convert to int"""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_dict(value, default=None):
        """Safely get dict"""
        if default is None:
            default = {}
        try:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                return json.loads(value)
            return default
        except (json.JSONDecodeError, TypeError):
            return default


# ==================== INLINE ADMINS ====================

class UserTaskCompletionInline(admin.TabularInline):
    """Show completions inside Task admin with defensive coding"""
    model = UserTaskCompletion
    extra = 0
    can_delete = False
    max_num = 10  # Limit to prevent performance issues
    
    readonly_fields = [
        'user_display', 'status_badge', 'points_display', 
        'time_display', 'duration_display', 'ip_display'
    ]
    
    fields = [
        'user_display', 'status_badge', 'points_display',
        'time_display', 'duration_display', 'ip_display'
    ]
    
    def user_display(self, obj):
        """Display user with safe link"""
        try:
            if not obj or not obj.user:
                return format_html('<span style="color: #999;">👤 Unknown</span>')
            
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            username = escape(obj.user.username)
            
            return format_html(
                '<a href="{}" style="color: #667eea; font-weight: bold; '
                'text-decoration: none;">👤 {}</a>',
                url, username
            )
        except Exception as e:
            logger.error(f"Error displaying user: {e}")
            return format_html('<span style="color: #F44336;">[ERROR] Error</span>')
    
    user_display.short_description = '👤 User'
    
    def status_badge(self, obj):
        """Display status with colored badge"""
        try:
            if not obj:
                return '-'
            
            status_config = {
                'started': {'color': '#FFA500', 'icon': '[LOADING]', 'label': 'Started'},
                'completed': {'color': '#4CAF50', 'icon': '[OK]', 'label': 'Completed'},
                'failed': {'color': '#F44336', 'icon': '[ERROR]', 'label': 'Failed'},
                'verified': {'color': '#2196F3', 'icon': '[OK]', 'label': 'Verified'}
            }
            
            config = status_config.get(obj.status, {
                'color': '#607D8B', 'icon': '❓', 'label': 'Unknown'
            })
            
            return format_html(
                '<span style="background: linear-gradient(135deg, {}, {}); '
                'color: white; padding: 4px 12px; border-radius: 15px; '
                'font-size: 11px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
                '{} {}</span>',
                config['color'], 
                self._lighten_color(config['color']),
                config['icon'], 
                config['label']
            )
        except Exception as e:
            logger.error(f"Error displaying status badge: {e}")
            return format_html('<span style="color: #999;">-</span>')
    
    status_badge.short_description = '[STATS] Status'
    
    def points_display(self, obj):
        """Display points earned"""
        try:
            if not obj:
                return '-'
            
            points = SafeDisplay.safe_int(obj.points_earned, 0)
            
            if points > 0:
                return format_html(
                    '<span style="background: linear-gradient(135deg, #FFD700, #FFA500); '
                    'color: white; padding: 3px 10px; border-radius: 12px; '
                    'font-weight: bold; font-size: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
                    '[MONEY] {}</span>',
                    points
                )
            return format_html('<span style="color: #999;">-</span>')
        except Exception as e:
            logger.error(f"Error displaying points: {e}")
            return '-'
    
    points_display.short_description = '[MONEY] Points'
    
    def time_display(self, obj):
        """Display time information"""
        try:
            if not obj:
                return '-'
            
            if obj.completed_at:
                time_str = obj.completed_at.strftime('%Y-%m-%d %H:%M')
                return format_html(
                    '<span style="color: #4CAF50; font-size: 11px;">[OK] {}</span>',
                    time_str
                )
            elif obj.started_at:
                time_str = obj.started_at.strftime('%Y-%m-%d %H:%M')
                return format_html(
                    '<span style="color: #FFA500; font-size: 11px;">[LOADING] {}</span>',
                    time_str
                )
            return '-'
        except Exception as e:
            logger.error(f"Error displaying time: {e}")
            return '-'
    
    time_display.short_description = '🕐 Time'
    
    def duration_display(self, obj):
        """Display duration"""
        try:
            if not obj or not obj.duration:
                return '-'
            
            total_seconds = SafeDisplay.safe_int(obj.duration.total_seconds(), 0)
            
            if total_seconds > 0:
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                
                return format_html(
                    '<span style="background: linear-gradient(135deg, #9C27B0, #E040FB); '
                    'color: white; padding: 3px 8px; border-radius: 10px; '
                    'font-size: 11px; font-weight: bold;">⏱️ {}m {}s</span>',
                    minutes, seconds
                )
            return '-'
        except Exception as e:
            logger.error(f"Error displaying duration: {e}")
            return '-'
    
    duration_display.short_description = '⏱️ Duration'
    
    def ip_display(self, obj):
        """Display IP address"""
        try:
            if not obj or not obj.ip_address:
                return '-'
            
            ip = escape(str(obj.ip_address))
            
            return format_html(
                '<code style="background: #f5f5f5; padding: 2px 6px; '
                'border-radius: 3px; font-size: 10px; color: #333;">{}</code>',
                ip
            )
        except Exception as e:
            logger.error(f"Error displaying IP: {e}")
            return '-'
    
    ip_display.short_description = '🌐 IP'
    
    @staticmethod
    def _lighten_color(hex_color):
        """Lighten hex color by 20%"""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r = min(255, int(r * 1.2))
            g = min(255, int(g * 1.2))
            b = min(255, int(b * 1.2))
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return hex_color
    
    def has_add_permission(self, request, obj=None):
        return False


class AdminLedgerInline(admin.TabularInline):
    """Show admin profits with defensive coding"""
    model = AdminLedger
    extra = 0
    can_delete = False
    max_num = 5  # Limit display
    
    readonly_fields = [
        'entry_display', 'source_badge', 'amount_display', 
        'user_display', 'time_display'
    ]
    
    fields = [
        'entry_display', 'source_badge', 'amount_display',
        'user_display', 'time_display'
    ]
    
    def entry_display(self, obj):
        """Display entry ID"""
        try:
            if not obj or not obj.entry_id:
                return '-'
            
            entry_id = escape(str(obj.entry_id))
            
            return format_html(
                '<code style="background: linear-gradient(135deg, #e3f2fd, #bbdefb); '
                'padding: 4px 8px; border-radius: 5px; font-size: 10px; '
                'color: #1976D2; font-weight: bold; border: 1px solid #90CAF9;">{}</code>',
                entry_id
            )
        except Exception as e:
            logger.error(f"Error displaying entry ID: {e}")
            return '-'
    
    entry_display.short_description = '🔖 Entry ID'
    
    def source_badge(self, obj):
        """Display source type with badge"""
        try:
            if not obj:
                return '-'
            
            source_config = {
                'task': {'color': '#4CAF50', 'icon': '📋', 'label': 'Task'},
                'withdrawal_fee': {'color': '#FF9800', 'icon': '💳', 'label': 'Fee'},
                'referral_unclaimed': {'color': '#9C27B0', 'icon': '👥', 'label': 'Referral'},
                'adjustment': {'color': '#2196F3', 'icon': '⚙️', 'label': 'Adjust'},
                'other': {'color': '#607D8B', 'icon': '📦', 'label': 'Other'}
            }
            
            config = source_config.get(obj.source_type, {
                'color': '#999', 'icon': '❓', 'label': 'Unknown'
            })
            
            return format_html(
                '<span style="background: {}; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 10px; font-weight: bold;">{} {}</span>',
                config['color'], config['icon'], config['label']
            )
        except Exception as e:
            logger.error(f"Error displaying source badge: {e}")
            return '-'
    
    source_badge.short_description = '[STATS] Source'
    
    def amount_display(self, obj):
        """Display amount with currency"""
        try:
            if not obj:
                return '-'
            
            amount = SafeDisplay.safe_decimal(obj.amount, 0)
            
            if amount > 0:
                return format_html(
                    '<span style="background: linear-gradient(135deg, #4CAF50, #8BC34A); '
                    'color: white; padding: 4px 12px; border-radius: 15px; '
                    'font-weight: bold; font-size: 13px; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">'
                    '[MONEY] ${:.2f}</span>',
                    amount
                )
            return '-'
        except Exception as e:
            logger.error(f"Error displaying amount: {e}")
            return '-'
    
    amount_display.short_description = '[MONEY] Amount'
    
    def user_display(self, obj):
        """Display user"""
        try:
            if not obj or not obj.user:
                return format_html('<span style="color: #999;">-</span>')
            
            username = escape(obj.user.username)
            return format_html(
                '<span style="color: #667eea; font-weight: 500;">👤 {}</span>',
                username
            )
        except Exception as e:
            logger.error(f"Error displaying user: {e}")
            return '-'
    
    user_display.short_description = '👤 User'
    
    def time_display(self, obj):
        """Display creation time"""
        try:
            if not obj or not obj.created_at:
                return '-'
            
            time_str = obj.created_at.strftime('%Y-%m-%d %H:%M')
            return format_html(
                '<span style="color: #666; font-size: 11px;">🕐 {}</span>',
                time_str
            )
        except Exception as e:
            logger.error(f"Error displaying time: {e}")
            return '-'
    
    time_display.short_description = '🕐 Created'
    
    def has_add_permission(self, request, obj=None):
        return False


# ==================== MASTER TASK ADMIN ====================

@admin.register(MasterTask)
class MasterTaskAdmin(admin.ModelAdmin):
    """Beautiful & Defensive MasterTask Admin"""
    
    # List Display
    list_display = [
        'task_id_badge', 'name_display', 'system_type_badge',
        'category_badge', 'reward_summary', 'completion_stats',
        'availability_badge', 'active_toggle', 'created_display'
    ]
    
    # List Filters
    list_filter = [
        'system_type', 'category', 'is_active', 'is_featured',
        ('created_at', admin.DateFieldListFilter),
        ('available_from', admin.DateFieldListFilter),
    ]
    
    # Search
    search_fields = ['task_id', 'name', 'description']
    
    # Ordering
    ordering = ['sort_order', '-created_at']
    
    # Readonly Fields
    readonly_fields = [
        'task_id', 'stats_card', 'reward_details',
        'metadata_display', 'constraints_display',
        'ui_config_display', 'created_at', 'updated_at'
    ]
    
    # Fieldsets
    fieldsets = (
        ('📋 Basic Information', {
            'fields': (
                'task_id', 'name', 'description',
                'system_type', 'category'
            ),
            'classes': ('wide',)
        }),
        ('[MONEY] Rewards Configuration', {
            'fields': ('reward_details', 'rewards'),
            'classes': ('collapse',)
        }),
        ('⚙️ Task Metadata', {
            'fields': ('metadata_display', 'task_metadata'),
            'classes': ('collapse',)
        }),
        ('🔒 Constraints & Limits', {
            'fields': ('constraints_display', 'constraints', 'daily_completion_limit'),
            'classes': ('collapse',)
        }),
        ('🎨 UI/UX Configuration', {
            'fields': ('ui_config_display', 'ui_config'),
            'classes': ('collapse',)
        }),
        ('👥 Targeting', {
            'fields': (
                'target_user_segments', 'min_user_level', 'max_user_level'
            ),
            'classes': ('collapse',)
        }),
        ('[STATS] Status & Visibility', {
            'fields': (
                'is_active', 'is_featured', 'sort_order',
                'available_from', 'available_until'
            ),
        }),
        ('📈 Statistics', {
            'fields': ('stats_card', 'total_completions', 'unique_users_completed'),
            'classes': ('collapse',)
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Inlines
    inlines = [UserTaskCompletionInline, AdminLedgerInline]
    
    # Actions
    actions = [
        'activate_tasks', 'deactivate_tasks', 
        'feature_tasks', 'unfeature_tasks',
        'export_tasks_json'
    ]
    
    # Per Page
    list_per_page = 25
    
    # ============ LIST DISPLAY METHODS ============
    
    def task_id_badge(self, obj):
        """Display task ID with badge"""
        try:
            if not obj or not obj.task_id:
                return '-'
            
            task_id = escape(str(obj.task_id))
            
            # Color based on system type
            color_map = {
                'click_visit': '#4CAF50',
                'gamified': '#FF9800',
                'data_input': '#2196F3',
                'guide_signup': '#9C27B0',
                'external_wall': '#F44336'
            }
            
            color = color_map.get(obj.system_type, '#607D8B')
            
            return format_html(
                '<span style="background: linear-gradient(135deg, {}, {}); '
                'color: white; padding: 5px 12px; border-radius: 20px; '
                'font-weight: bold; font-size: 11px; letter-spacing: 0.5px; '
                'box-shadow: 0 2px 5px rgba(0,0,0,0.15); display: inline-block;">'
                '🎯 {}</span>',
                color, self._lighten_color(color), task_id
            )
        except Exception as e:
            logger.error(f"Error displaying task ID badge: {e}")
            return '-'
    
    task_id_badge.short_description = '🎯 Task ID'
    task_id_badge.admin_order_field = 'task_id'
    
    def name_display(self, obj):
        """Display task name with icon"""
        try:
            if not obj:
                return '-'
            
            name = escape(str(obj.name))
            
            # Truncate if too long
            if len(name) > 50:
                name = name[:47] + '...'
            
            return format_html(
                '<strong style="color: #333; font-size: 13px;">[NOTE] {}</strong>',
                name
            )
        except Exception as e:
            logger.error(f"Error displaying name: {e}")
            return '-'
    
    name_display.short_description = '[NOTE] Task Name'
    name_display.admin_order_field = 'name'
    
    def system_type_badge(self, obj):
        """Display system type with colorful badge"""
        try:
            if not obj:
                return '-'
            
            type_config = {
                'click_visit': {
                    'color': '#4CAF50', 
                    'icon': '🖱️', 
                    'label': 'Click & Visit'
                },
                'gamified': {
                    'color': '#FF9800', 
                    'icon': '🎮', 
                    'label': 'Gamified'
                },
                'data_input': {
                    'color': '#2196F3', 
                    'icon': '[NOTE]', 
                    'label': 'Data Input'
                },
                'guide_signup': {
                    'color': '#9C27B0', 
                    'icon': '📱', 
                    'label': 'Guide/Signup'
                },
                'external_wall': {
                    'color': '#F44336', 
                    'icon': '🌐', 
                    'label': 'External Wall'
                }
            }
            
            config = type_config.get(obj.system_type, {
                'color': '#607D8B', 
                'icon': '❓', 
                'label': 'Unknown'
            })
            
            return format_html(
                '<div style="background: {}; color: white; padding: 6px 14px; '
                'border-radius: 18px; font-weight: bold; font-size: 11px; '
                'text-align: center; box-shadow: 0 3px 6px rgba(0,0,0,0.15); '
                'display: inline-block; min-width: 100px;">{} {}</div>',
                config['color'], config['icon'], config['label']
            )
        except Exception as e:
            logger.error(f"Error displaying system type badge: {e}")
            return '-'
    
    system_type_badge.short_description = '[FIX] System Type'
    system_type_badge.admin_order_field = 'system_type'
    
    def category_badge(self, obj):
        """Display category badge"""
        try:
            if not obj:
                return '-'
            
            category_colors = {
                'daily_retention': '#00BCD4',
                'gamified': '#FF5722',
                'ads_multimedia': '#9C27B0',
                'app_social': '#3F51B5',
                'web_content': '#009688',
                'refer_team': '#FF9800',
                'advanced_api': '#795548'
            }
            
            color = category_colors.get(obj.category, '#757575')
            label = obj.get_category_display() if hasattr(obj, 'get_category_display') else obj.category
            
            return format_html(
                '<span style="background: {}; color: white; padding: 4px 10px; '
                'border-radius: 10px; font-size: 10px; font-weight: bold; '
                'box-shadow: 0 2px 4px rgba(0,0,0,0.1);">📂 {}</span>',
                color, escape(str(label))
            )
        except Exception as e:
            logger.error(f"Error displaying category badge: {e}")
            return '-'
    
    category_badge.short_description = '📂 Category'
    category_badge.admin_order_field = 'category'
    
    def reward_summary(self, obj):
        """Display reward summary"""
        try:
            if not obj:
                return '-'
            
            rewards = SafeDisplay.safe_dict(obj.rewards, {})
            points = SafeDisplay.safe_int(rewards.get('points', 0), 0)
            coins = SafeDisplay.safe_int(rewards.get('coins', 0), 0)
            exp = SafeDisplay.safe_int(rewards.get('experience', 0), 0)
            
            return format_html(
                '<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
                '<span style="background: linear-gradient(135deg, #FFD700, #FFA500); '
                'color: white; padding: 3px 8px; border-radius: 10px; font-size: 10px; '
                'font-weight: bold; box-shadow: 0 2px 3px rgba(0,0,0,0.1);">[MONEY] {}</span>'
                '<span style="background: linear-gradient(135deg, #4CAF50, #8BC34A); '
                'color: white; padding: 3px 8px; border-radius: 10px; font-size: 10px; '
                'font-weight: bold; box-shadow: 0 2px 3px rgba(0,0,0,0.1);">[STAR] {}</span>'
                '<span style="background: linear-gradient(135deg, #2196F3, #03A9F4); '
                'color: white; padding: 3px 8px; border-radius: 10px; font-size: 10px; '
                'font-weight: bold; box-shadow: 0 2px 3px rgba(0,0,0,0.1);">🎯 {}</span>'
                '</div>',
                points, coins, exp
            )
        except Exception as e:
            logger.error(f"Error displaying reward summary: {e}")
            return '-'
    
    reward_summary.short_description = '[MONEY] Rewards'
    
    def completion_stats(self, obj):
        """Display completion statistics"""
        try:
            if not obj:
                return '-'
            
            total = SafeDisplay.safe_int(obj.total_completions, 0)
            unique = SafeDisplay.safe_int(obj.unique_users_completed, 0)
            
            # Calculate percentage if possible
            percentage = 0
            if total > 0 and unique > 0:
                percentage = min(100, int((unique / total) * 100))
            
            return format_html(
                '<div style="text-align: center;">'
                '<div style="font-weight: bold; color: #4CAF50; font-size: 18px;">[STATS] {}</div>'
                '<div style="font-size: 10px; color: #666;">👥 {} unique</div>'
                '<div style="background: #e0e0e0; height: 4px; border-radius: 2px; '
                'margin-top: 3px; overflow: hidden;">'
                '<div style="background: linear-gradient(90deg, #4CAF50, #8BC34A); '
                'height: 100%; width: {}%;"></div>'
                '</div>'
                '</div>',
                total, unique, percentage
            )
        except Exception as e:
            logger.error(f"Error displaying completion stats: {e}")
            return '-'
    
    completion_stats.short_description = '[STATS] Completions'
    
    def availability_badge(self, obj):
        """Display availability status"""
        try:
            if not obj:
                return '-'
            
            status_config = {
                'available': {'color': '#4CAF50', 'icon': '[OK]', 'label': 'Available'},
                'expired': {'color': '#F44336', 'icon': '⌛', 'label': 'Expired'},
                'scheduled': {'color': '#FF9800', 'icon': '⏳', 'label': 'Scheduled'},
                'inactive': {'color': '#757575', 'icon': '[ERROR]', 'label': 'Inactive'}
            }
            
            status = obj.time_status if hasattr(obj, 'time_status') else 'inactive'
            config = status_config.get(status, status_config['inactive'])
            
            return format_html(
                '<span style="background: {}; color: white; padding: 5px 12px; '
                'border-radius: 15px; font-weight: bold; font-size: 11px; '
                'box-shadow: 0 2px 4px rgba(0,0,0,0.15); display: inline-block;">'
                '{} {}</span>',
                config['color'], config['icon'], config['label']
            )
        except Exception as e:
            logger.error(f"Error displaying availability badge: {e}")
            return '-'
    
    availability_badge.short_description = '⏰ Status'
    
    def active_toggle(self, obj):
        """Display active/inactive toggle"""
        try:
            if not obj:
                return '-'
            
            if obj.is_active:
                return format_html(
                    '<span style="background: linear-gradient(135deg, #4CAF50, #8BC34A); '
                    'color: white; padding: 4px 12px; border-radius: 12px; '
                    'font-weight: bold; font-size: 11px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
                    '[OK] Active</span>'
                )
            else:
                return format_html(
                    '<span style="background: linear-gradient(135deg, #F44336, #EF5350); '
                    'color: white; padding: 4px 12px; border-radius: 12px; '
                    'font-weight: bold; font-size: 11px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
                    '[ERROR] Inactive</span>'
                )
        except Exception as e:
            logger.error(f"Error displaying active toggle: {e}")
            return '-'
    
    active_toggle.short_description = '🔘 Active'
    active_toggle.admin_order_field = 'is_active'
    
    def created_display(self, obj):
        """Display creation date"""
        try:
            if not obj or not obj.created_at:
                return '-'
            
            # Time ago
            now = timezone.now()
            delta = now - obj.created_at
            
            if delta.days > 365:
                time_ago = f"{delta.days // 365}y ago"
            elif delta.days > 30:
                time_ago = f"{delta.days // 30}mo ago"
            elif delta.days > 0:
                time_ago = f"{delta.days}d ago"
            elif delta.seconds > 3600:
                time_ago = f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                time_ago = f"{delta.seconds // 60}m ago"
            else:
                time_ago = "just now"
            
            date_str = obj.created_at.strftime('%Y-%m-%d')
            
            return format_html(
                '<div style="text-align: center;">'
                '<div style="color: #666; font-size: 11px;">📅 {}</div>'
                '<div style="color: #999; font-size: 9px;">{}</div>'
                '</div>',
                date_str, time_ago
            )
        except Exception as e:
            logger.error(f"Error displaying created date: {e}")
            return '-'
    
    created_display.short_description = '📅 Created'
    created_display.admin_order_field = 'created_at'
    
    # ============ READONLY FIELD METHODS ============
    
    def stats_card(self, obj):
        """Display statistics card"""
        try:
            if not obj:
                return '-'
            
            total = SafeDisplay.safe_int(obj.total_completions, 0)
            unique = SafeDisplay.safe_int(obj.unique_users_completed, 0)
            
            # Calculate completion rate
            completion_rate = 0
            if total > 0:
                completion_rate = min(100, int((unique / total) * 100))
            
            # Get recent completions (last 24h)
            try:
                recent_count = obj.completions.filter(
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).count()
            except Exception:
                recent_count = 0
            
            return format_html(
                '<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
                'padding: 20px; border-radius: 10px; color: white; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">'
                '<h3 style="margin: 0 0 15px 0; font-size: 18px;">[STATS] Task Statistics</h3>'
                '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">'
                '<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 24px; font-weight: bold;">{}</div>'
                '<div style="font-size: 12px; opacity: 0.9;">Total Completions</div>'
                '</div>'
                '<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 24px; font-weight: bold;">{}</div>'
                '<div style="font-size: 12px; opacity: 0.9;">Unique Users</div>'
                '</div>'
                '<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 24px; font-weight: bold;">{}</div>'
                '<div style="font-size: 12px; opacity: 0.9;">Last 24h</div>'
                '</div>'
                '</div>'
                '<div style="margin-top: 15px; background: rgba(255,255,255,0.2); padding: 10px; border-radius: 5px;">'
                '<div style="font-size: 12px; margin-bottom: 5px;">Completion Rate: {}%</div>'
                '<div style="background: rgba(0,0,0,0.2); height: 8px; border-radius: 4px; overflow: hidden;">'
                '<div style="background: #4CAF50; height: 100%; width: {}%; transition: width 0.3s;"></div>'
                '</div>'
                '</div>'
                '</div>',
                total, unique, recent_count, completion_rate, completion_rate
            )
        except Exception as e:
            logger.error(f"Error displaying stats card: {e}")
            return format_html('<div style="color: red;">Error loading statistics</div>')
    
    stats_card.short_description = '[STATS] Statistics Overview'
    
    def reward_details(self, obj):
        """Display detailed rewards"""
        try:
            if not obj:
                return '-'
            
            rewards = SafeDisplay.safe_dict(obj.rewards, {})
            
            points = SafeDisplay.safe_int(rewards.get('points', 0), 0)
            coins = SafeDisplay.safe_int(rewards.get('coins', 0), 0)
            exp = SafeDisplay.safe_int(rewards.get('experience', 0), 0)
            bonus = SafeDisplay.safe_dict(rewards.get('bonus', {}), {})
            
            bonus_html = ''
            if bonus:
                bonus_items = []
                for key, value in bonus.items():
                    bonus_items.append(f'<li><strong>{escape(str(key))}:</strong> {escape(str(value))}</li>')
                bonus_html = '<ul style="margin: 5px 0; padding-left: 20px;">' + ''.join(bonus_items) + '</ul>'
            
            return format_html(
                '<div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); '
                'padding: 20px; border-radius: 10px; color: white; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">'
                '<h3 style="margin: 0 0 15px 0; font-size: 16px;">[MONEY] Reward Breakdown</h3>'
                '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">'
                '<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 20px;">[MONEY]</div>'
                '<div style="font-size: 18px; font-weight: bold; margin: 5px 0;">{}</div>'
                '<div style="font-size: 11px; opacity: 0.9;">Points</div>'
                '</div>'
                '<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 20px;">[STAR]</div>'
                '<div style="font-size: 18px; font-weight: bold; margin: 5px 0;">{}</div>'
                '<div style="font-size: 11px; opacity: 0.9;">Coins</div>'
                '</div>'
                '<div style="background: rgba(255,255,255,0.2); padding: 12px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 20px;">🎯</div>'
                '<div style="font-size: 18px; font-weight: bold; margin: 5px 0;">{}</div>'
                '<div style="font-size: 11px; opacity: 0.9;">Experience</div>'
                '</div>'
                '</div>'
                '{}'
                '</div>',
                points, coins, exp, bonus_html
            )
        except Exception as e:
            logger.error(f"Error displaying reward details: {e}")
            return format_html('<div style="color: red;">Error loading rewards</div>')
    
    reward_details.short_description = '[MONEY] Reward Configuration'
    
    def metadata_display(self, obj):
        """Display task metadata"""
        try:
            if not obj:
                return '-'
            
            metadata = SafeDisplay.safe_dict(obj.task_metadata, {})
            
            if not metadata:
                return format_html(
                    '<div style="color: #999; font-style: italic;">No metadata configured</div>'
                )
            
            items_html = []
            for key, value in metadata.items():
                # Format value based on type
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value, indent=2)
                    value_display = f'<pre style="background: #f5f5f5; padding: 5px; border-radius: 3px; font-size: 11px; overflow: auto;">{escape(value_str)}</pre>'
                else:
                    value_display = f'<code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px;">{escape(str(value))}</code>'
                
                items_html.append(
                    f'<tr>'
                    f'<td style="padding: 8px; font-weight: bold; color: #667eea; border-bottom: 1px solid #eee;">{escape(str(key))}</td>'
                    f'<td style="padding: 8px; border-bottom: 1px solid #eee;">{value_display}</td>'
                    f'</tr>'
                )
            
            return format_html(
                '<div style="border: 2px solid #667eea; border-radius: 8px; overflow: hidden;">'
                '<div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 10px; font-weight: bold;">'
                '⚙️ Task Metadata Configuration'
                '</div>'
                '<table style="width: 100%; border-collapse: collapse;">'
                '{}'
                '</table>'
                '</div>',
                ''.join(items_html)
            )
        except Exception as e:
            logger.error(f"Error displaying metadata: {e}")
            return format_html('<div style="color: red;">Error loading metadata</div>')
    
    metadata_display.short_description = '⚙️ Metadata'
    
    def constraints_display(self, obj):
        """Display constraints"""
        try:
            if not obj:
                return '-'
            
            constraints = SafeDisplay.safe_dict(obj.constraints, {})
            
            daily_limit = constraints.get('daily_limit', 'Unlimited')
            total_limit = constraints.get('total_limit', 'Unlimited')
            cooldown = SafeDisplay.safe_int(constraints.get('cooldown_minutes', 0), 0)
            required_level = SafeDisplay.safe_int(constraints.get('required_level', 1), 1)
            
            return format_html(
                '<div style="background: linear-gradient(135deg, #FA8BFF 0%, #2BD2FF 90%); '
                'padding: 15px; border-radius: 8px; color: white;">'
                '<h4 style="margin: 0 0 10px 0; font-size: 14px;">🔒 Task Constraints</h4>'
                '<table style="width: 100%; color: white; font-size: 12px;">'
                '<tr><td style="padding: 5px 0;"><strong>📅 Daily Limit:</strong></td><td>{}</td></tr>'
                '<tr><td style="padding: 5px 0;"><strong>[STATS] Total Limit:</strong></td><td>{}</td></tr>'
                '<tr><td style="padding: 5px 0;"><strong>⏱️ Cooldown:</strong></td><td>{} minutes</td></tr>'
                '<tr><td style="padding: 5px 0;"><strong>🎯 Required Level:</strong></td><td>Level {}</td></tr>'
                '</table>'
                '</div>',
                daily_limit, total_limit, cooldown, required_level
            )
        except Exception as e:
            logger.error(f"Error displaying constraints: {e}")
            return format_html('<div style="color: red;">Error loading constraints</div>')
    
    constraints_display.short_description = '🔒 Constraints'
    
    def ui_config_display(self, obj):
        """Display UI configuration"""
        try:
            if not obj:
                return '-'
            
            ui_config = SafeDisplay.safe_dict(obj.ui_config, {})
            
            icon = escape(str(ui_config.get('icon', 'default_task.png')))
            color = ui_config.get('color', '#4CAF50')
            button_text = escape(str(ui_config.get('button_text', 'Start')))
            animation = ui_config.get('animation', 'None')
            
            return format_html(
                '<div style="border: 2px solid {}; border-radius: 10px; overflow: hidden;">'
                '<div style="background: {}; color: white; padding: 15px; text-align: center;">'
                '<div style="font-size: 40px; margin-bottom: 10px;">🎨</div>'
                '<div style="font-weight: bold; font-size: 16px;">UI Configuration</div>'
                '</div>'
                '<div style="padding: 15px; background: #f9f9f9;">'
                '<table style="width: 100%; font-size: 12px;">'
                '<tr><td style="padding: 8px 0; font-weight: bold; color: {};">🖼️ Icon:</td><td>{}</td></tr>'
                '<tr><td style="padding: 8px 0; font-weight: bold; color: {};">🎨 Color:</td>'
                '<td><span style="display: inline-block; width: 30px; height: 15px; '
                'background: {}; border: 1px solid #ccc; border-radius: 3px; vertical-align: middle;"></span> {}</td></tr>'
                '<tr><td style="padding: 8px 0; font-weight: bold; color: {};">🔘 Button:</td><td>{}</td></tr>'
                '<tr><td style="padding: 8px 0; font-weight: bold; color: {};">✨ Animation:</td><td>{}</td></tr>'
                '</table>'
                '</div>'
                '</div>',
                color, color, color, icon, color, color, color, color, button_text, color, escape(str(animation))
            )
        except Exception as e:
            logger.error(f"Error displaying UI config: {e}")
            return format_html('<div style="color: red;">Error loading UI config</div>')
    
    ui_config_display.short_description = '🎨 UI Configuration'
    
    # ============ ADMIN ACTIONS ============
    
    def activate_tasks(self, request, queryset):
        """Bulk activate tasks"""
        try:
            count = queryset.update(is_active=True)
            self.message_user(
                request,
                format_html(
                    '<span style="color: #4CAF50; font-weight: bold;">[OK] Successfully activated {} task(s)</span>',
                    count
                )
            )
        except Exception as e:
            logger.error(f"Error activating tasks: {e}")
            self.message_user(request, f'[ERROR] Error: {str(e)}', level='ERROR')
    
    activate_tasks.short_description = '[OK] Activate selected tasks'
    
    def deactivate_tasks(self, request, queryset):
        """Bulk deactivate tasks"""
        try:
            count = queryset.update(is_active=False)
            self.message_user(
                request,
                format_html(
                    '<span style="color: #F44336; font-weight: bold;">[ERROR] Successfully deactivated {} task(s)</span>',
                    count
                )
            )
        except Exception as e:
            logger.error(f"Error deactivating tasks: {e}")
            self.message_user(request, f'[ERROR] Error: {str(e)}', level='ERROR')
    
    deactivate_tasks.short_description = '[ERROR] Deactivate selected tasks'
    
    def feature_tasks(self, request, queryset):
        """Mark tasks as featured"""
        try:
            count = queryset.update(is_featured=True)
            self.message_user(
                request,
                format_html(
                    '<span style="color: #FF9800; font-weight: bold;">[STAR] Successfully featured {} task(s)</span>',
                    count
                )
            )
        except Exception as e:
            logger.error(f"Error featuring tasks: {e}")
            self.message_user(request, f'[ERROR] Error: {str(e)}', level='ERROR')
    
    feature_tasks.short_description = '[STAR] Feature selected tasks'
    
    def unfeature_tasks(self, request, queryset):
        """Unmark tasks as featured"""
        try:
            count = queryset.update(is_featured=False)
            self.message_user(
                request,
                format_html(
                    '<span style="color: #757575;">[STAR] Successfully unfeatured {} task(s)</span>',
                    count
                )
            )
        except Exception as e:
            logger.error(f"Error unfeaturing tasks: {e}")
            self.message_user(request, f'[ERROR] Error: {str(e)}', level='ERROR')
    
    unfeature_tasks.short_description = '☆ Unfeature selected tasks'
    
    def export_tasks_json(self, request, queryset):
        """Export selected tasks as JSON"""
        try:
            tasks_data = []
            
            for task in queryset:
                tasks_data.append({
                    'task_id': task.task_id,
                    'name': task.name,
                    'description': task.description,
                    'system_type': task.system_type,
                    'category': task.category,
                    'rewards': task.rewards,
                    'metadata': task.task_metadata,
                    'constraints': task.constraints,
                    'is_active': task.is_active,
                })
            
            response = HttpResponse(
                json.dumps(tasks_data, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = 'attachment; filename="tasks_export.json"'
            
            return response
            
        except Exception as e:
            logger.error(f"Error exporting tasks: {e}")
            self.message_user(request, f'[ERROR] Export Error: {str(e)}', level='ERROR')
    
    export_tasks_json.short_description = '📤 Export as JSON'
    
    # ============ UTILITY METHODS ============
    
    @staticmethod
    def _lighten_color(hex_color, factor=0.2):
        """Lighten a hex color"""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r = min(255, int(r + (255 - r) * factor))
            g = min(255, int(g + (255 - g) * factor))
            b = min(255, int(b + (255 - b) * factor))
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return hex_color


# ==================== USER TASK COMPLETION ADMIN ====================

@admin.register(UserTaskCompletion)
class UserTaskCompletionAdmin(admin.ModelAdmin):
    """Beautiful & Defensive UserTaskCompletion Admin"""
    
    list_display = [
        'id_badge', 'user_display', 'task_display',
        'status_badge', 'rewards_display', 'time_display',
        'duration_badge', 'ip_badge'
    ]
    
    list_filter = [
        'status',
        ('started_at', admin.DateFieldListFilter),
        ('completed_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'user__username', 'task__task_id', 'task__name', 'ip_address'
    ]
    
    readonly_fields = [
        'user', 'task', 'started_at', 'completed_at', 'verified_at',
        'proof_display', 'rewards_display_detailed', 'duration_card'
    ]
    
    fieldsets = (
        ('📋 Basic Information', {
            'fields': ('user', 'task', 'status'),
        }),
        ('[MONEY] Rewards', {
            'fields': ('rewards_display_detailed', 'rewards_awarded'),
            'classes': ('collapse',)
        }),
        ('[DOC] Proof Data', {
            'fields': ('proof_display', 'proof_data'),
            'classes': ('collapse',)
        }),
        ('🕐 Timing', {
            'fields': ('duration_card', 'started_at', 'completed_at', 'verified_at'),
            'classes': ('collapse',)
        }),
        ('🌐 Network Info', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 50
    date_hierarchy = 'started_at'
    
    # ============ LIST DISPLAY METHODS ============
    
    def id_badge(self, obj):
        """Display ID badge"""
        try:
            if not obj:
                return '-'
            
            return format_html(
                '<span style="background: linear-gradient(135deg, #667eea, #764ba2); '
                'color: white; padding: 4px 10px; border-radius: 12px; '
                'font-weight: bold; font-size: 11px;">#{}</span>',
                obj.id
            )
        except Exception as e:
            logger.error(f"Error displaying ID badge: {e}")
            return '-'
    
    id_badge.short_description = '🔢 ID'
    id_badge.admin_order_field = 'id'
    
    def user_display(self, obj):
        """Display user with link"""
        try:
            if not obj or not obj.user:
                return format_html('<span style="color: #999;">👤 Unknown</span>')
            
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            username = escape(obj.user.username)
            
            return format_html(
                '<a href="{}" style="color: #667eea; font-weight: bold; '
                'text-decoration: none;">👤 {}</a>',
                url, username
            )
        except Exception as e:
            logger.error(f"Error displaying user: {e}")
            return '-'
    
    user_display.short_description = '👤 User'
    user_display.admin_order_field = 'user__username'
    
    def task_display(self, obj):
        """Display task with link"""
        try:
            if not obj or not obj.task:
                return '-'
            
            url = reverse('admin:tasks_mastertask_change', args=[obj.task.id])
            task_name = escape(obj.task.name)
            
            # Truncate if too long
            if len(task_name) > 40:
                task_name = task_name[:37] + '...'
            
            return format_html(
                '<a href="{}" style="color: #4CAF50; font-weight: 500; '
                'text-decoration: none;">📋 {}</a>',
                url, task_name
            )
        except Exception as e:
            logger.error(f"Error displaying task: {e}")
            return '-'
    
    task_display.short_description = '📋 Task'
    task_display.admin_order_field = 'task__name'
    
    def status_badge(self, obj):
        """Display status badge"""
        try:
            if not obj:
                return '-'
            
            status_config = {
                'started': {
                    'color': '#FFA500',
                    'icon': '[LOADING]',
                    'label': 'Started'
                },
                'completed': {
                    'color': '#4CAF50',
                    'icon': '[OK]',
                    'label': 'Completed'
                },
                'failed': {
                    'color': '#F44336',
                    'icon': '[ERROR]',
                    'label': 'Failed'
                },
                'verified': {
                    'color': '#2196F3',
                    'icon': '[OK]',
                    'label': 'Verified'
                }
            }
            
            config = status_config.get(obj.status, {
                'color': '#607D8B',
                'icon': '❓',
                'label': 'Unknown'
            })
            
            return format_html(
                '<span style="background: linear-gradient(135deg, {}, {}); '
                'color: white; padding: 6px 14px; border-radius: 16px; '
                'font-size: 12px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.15); '
                'display: inline-block;">{} {}</span>',
                config['color'],
                UserTaskCompletionInline._lighten_color(config['color']),
                config['icon'],
                config['label']
            )
        except Exception as e:
            logger.error(f"Error displaying status badge: {e}")
            return '-'
    
    status_badge.short_description = '[STATS] Status'
    status_badge.admin_order_field = 'status'
    
    def rewards_display(self, obj):
        """Display rewards summary"""
        try:
            if not obj:
                return '-'
            
            rewards = SafeDisplay.safe_dict(obj.rewards_awarded, {})
            points = SafeDisplay.safe_int(rewards.get('points', 0), 0)
            
            if points > 0:
                return format_html(
                    '<span style="background: linear-gradient(135deg, #FFD700, #FFA500); '
                    'color: white; padding: 5px 12px; border-radius: 14px; '
                    'font-weight: bold; font-size: 13px; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">'
                    '[MONEY] {} pts</span>',
                    points
                )
            return format_html('<span style="color: #999;">-</span>')
        except Exception as e:
            logger.error(f"Error displaying rewards: {e}")
            return '-'
    
    rewards_display.short_description = '[MONEY] Rewards'
    
    def time_display(self, obj):
        """Display time"""
        try:
            if not obj:
                return '-'
            
            if obj.completed_at:
                time_str = obj.completed_at.strftime('%Y-%m-%d %H:%M:%S')
                return format_html(
                    '<div style="text-align: center;">'
                    '<div style="color: #4CAF50; font-size: 11px;">[OK] Completed</div>'
                    '<div style="color: #666; font-size: 10px;">{}</div>'
                    '</div>',
                    time_str
                )
            elif obj.started_at:
                time_str = obj.started_at.strftime('%Y-%m-%d %H:%M:%S')
                return format_html(
                    '<div style="text-align: center;">'
                    '<div style="color: #FFA500; font-size: 11px;">[LOADING] Started</div>'
                    '<div style="color: #666; font-size: 10px;">{}</div>'
                    '</div>',
                    time_str
                )
            return '-'
        except Exception as e:
            logger.error(f"Error displaying time: {e}")
            return '-'
    
    time_display.short_description = '🕐 Time'
    time_display.admin_order_field = 'completed_at'
    
    def duration_badge(self, obj):
        """Display duration badge"""
        try:
            if not obj or not obj.duration:
                return '-'
            
            total_seconds = SafeDisplay.safe_int(obj.duration.total_seconds(), 0)
            
            if total_seconds > 0:
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                
                return format_html(
                    '<span style="background: linear-gradient(135deg, #9C27B0, #E040FB); '
                    'color: white; padding: 5px 12px; border-radius: 12px; '
                    'font-size: 12px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">'
                    '⏱️ {}m {}s</span>',
                    minutes, seconds
                )
            return '-'
        except Exception as e:
            logger.error(f"Error displaying duration badge: {e}")
            return '-'
    
    duration_badge.short_description = '⏱️ Duration'
    
    def ip_badge(self, obj):
        """Display IP badge"""
        try:
            if not obj or not obj.ip_address:
                return '-'
            
            ip = escape(str(obj.ip_address))
            
            return format_html(
                '<code style="background: #f5f5f5; padding: 4px 8px; '
                'border-radius: 5px; font-size: 11px; color: #333; '
                'border: 1px solid #ddd;">🌐 {}</code>',
                ip
            )
        except Exception as e:
            logger.error(f"Error displaying IP badge: {e}")
            return '-'
    
    ip_badge.short_description = '🌐 IP'
    
    # ============ READONLY FIELD METHODS ============
    
    def proof_display(self, obj):
        """Display proof data"""
        try:
            if not obj:
                return '-'
            
            proof = SafeDisplay.safe_dict(obj.proof_data, {})
            
            if not proof:
                return format_html(
                    '<div style="color: #999; font-style: italic;">No proof data available</div>'
                )
            
            proof_json = json.dumps(proof, indent=2)
            
            return format_html(
                '<div style="border: 2px solid #2196F3; border-radius: 8px; overflow: hidden;">'
                '<div style="background: #2196F3; color: white; padding: 10px; font-weight: bold;">'
                '[DOC] Proof Data'
                '</div>'
                '<pre style="background: #f9f9f9; padding: 15px; margin: 0; '
                'max-height: 300px; overflow: auto; font-size: 11px;">{}</pre>'
                '</div>',
                escape(proof_json)
            )
        except Exception as e:
            logger.error(f"Error displaying proof: {e}")
            return format_html('<div style="color: red;">Error loading proof data</div>')
    
    proof_display.short_description = '[DOC] Proof Data'
    
    def rewards_display_detailed(self, obj):
        """Display detailed rewards"""
        try:
            if not obj:
                return '-'
            
            rewards = SafeDisplay.safe_dict(obj.rewards_awarded, {})
            
            if not rewards:
                return format_html(
                    '<div style="color: #999; font-style: italic;">No rewards awarded yet</div>'
                )
            
            points = SafeDisplay.safe_int(rewards.get('points', 0), 0)
            coins = SafeDisplay.safe_int(rewards.get('coins', 0), 0)
            exp = SafeDisplay.safe_int(rewards.get('experience', 0), 0)
            
            return format_html(
                '<div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); '
                'padding: 20px; border-radius: 10px; color: white;">'
                '<h3 style="margin: 0 0 15px 0; font-size: 16px;">[MONEY] Rewards Breakdown</h3>'
                '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">'
                '<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 24px;">[MONEY]</div>'
                '<div style="font-size: 20px; font-weight: bold; margin: 5px 0;">{}</div>'
                '<div style="font-size: 11px; opacity: 0.9;">Points</div>'
                '</div>'
                '<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 24px;">[STAR]</div>'
                '<div style="font-size: 20px; font-weight: bold; margin: 5px 0;">{}</div>'
                '<div style="font-size: 11px; opacity: 0.9;">Coins</div>'
                '</div>'
                '<div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 8px; text-align: center;">'
                '<div style="font-size: 24px;">🎯</div>'
                '<div style="font-size: 20px; font-weight: bold; margin: 5px 0;">{}</div>'
                '<div style="font-size: 11px; opacity: 0.9;">Experience</div>'
                '</div>'
                '</div>'
                '</div>',
                points, coins, exp
            )
        except Exception as e:
            logger.error(f"Error displaying detailed rewards: {e}")
            return format_html('<div style="color: red;">Error loading rewards</div>')
    
    rewards_display_detailed.short_description = '[MONEY] Rewards Details'
    
    def duration_card(self, obj):
        """Display duration card"""
        try:
            if not obj:
                return '-'
            
            if not obj.duration:
                return format_html(
                    '<div style="color: #999; font-style: italic;">Duration not available</div>'
                )
            
            total_seconds = SafeDisplay.safe_int(obj.duration.total_seconds(), 0)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            return format_html(
                '<div style="background: linear-gradient(135deg, #667eea, #764ba2); '
                'padding: 20px; border-radius: 10px; color: white; text-align: center;">'
                '<div style="font-size: 48px; margin-bottom: 10px;">⏱️</div>'
                '<div style="font-size: 32px; font-weight: bold; margin-bottom: 5px;">'
                '{}h {}m {}s'
                '</div>'
                '<div style="font-size: 14px; opacity: 0.9;">Total Duration</div>'
                '</div>',
                hours, minutes, seconds
            )
        except Exception as e:
            logger.error(f"Error displaying duration card: {e}")
            return format_html('<div style="color: red;">Error loading duration</div>')
    
    duration_card.short_description = '⏱️ Duration Details'


# ==================== ADMIN LEDGER ADMIN ====================

@admin.register(AdminLedger)
class AdminLedgerAdmin(admin.ModelAdmin):
    """Beautiful & Defensive AdminLedger Admin"""
    
    list_display = [
        'entry_badge', 'source_type_badge', 'amount_display',
        'task_display', 'user_display', 'date_display'
    ]
    
    list_filter = [
        'source_type',
        ('created_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'entry_id', 'source', 'description',
        'user__username', 'task__task_id'
    ]
    
    readonly_fields = [
        'entry_id', 'amount', 'source', 'source_type',
        'task', 'user', 'completion', 'transaction', 'withdrawal',
        'metadata_display', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('[MONEY] Ledger Entry', {
            'fields': ('entry_id', 'amount', 'source', 'source_type', 'description'),
        }),
        ('🔗 Related Objects', {
            'fields': ('task', 'user', 'completion', 'transaction', 'withdrawal'),
            'classes': ('collapse',)
        }),
        ('[DOC] Metadata', {
            'fields': ('metadata_display', 'metadata'),
            'classes': ('collapse',)
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    # ============ LIST DISPLAY METHODS ============
    
    def entry_badge(self, obj):
        """Display entry ID badge"""
        try:
            if not obj or not obj.entry_id:
                return '-'
            
            entry_id = escape(str(obj.entry_id))
            
            return format_html(
                '<code style="background: linear-gradient(135deg, #e3f2fd, #bbdefb); '
                'padding: 6px 12px; border-radius: 8px; font-size: 11px; '
                'color: #1976D2; font-weight: bold; border: 2px solid #90CAF9; '
                'display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
                '🔖 {}</code>',
                entry_id
            )
        except Exception as e:
            logger.error(f"Error displaying entry badge: {e}")
            return '-'
    
    entry_badge.short_description = '🔖 Entry ID'
    entry_badge.admin_order_field = 'entry_id'
    
    def source_type_badge(self, obj):
        """Display source type badge"""
        try:
            if not obj:
                return '-'
            
            source_config = {
                'task': {
                    'color': '#4CAF50',
                    'icon': '📋',
                    'label': 'Task Revenue'
                },
                'withdrawal_fee': {
                    'color': '#FF9800',
                    'icon': '💳',
                    'label': 'Withdrawal Fee'
                },
                'referral_unclaimed': {
                    'color': '#9C27B0',
                    'icon': '👥',
                    'label': 'Referral'
                },
                'adjustment': {
                    'color': '#2196F3',
                    'icon': '⚙️',
                    'label': 'Adjustment'
                },
                'other': {
                    'color': '#607D8B',
                    'icon': '📦',
                    'label': 'Other'
                }
            }
            
            config = source_config.get(obj.source_type, {
                'color': '#999',
                'icon': '❓',
                'label': 'Unknown'
            })
            
            return format_html(
                '<span style="background: linear-gradient(135deg, {}, {}); '
                'color: white; padding: 6px 14px; border-radius: 16px; '
                'font-size: 12px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.15); '
                'display: inline-block;">{} {}</span>',
                config['color'],
                MasterTaskAdmin._lighten_color(config['color']),
                config['icon'],
                config['label']
            )
        except Exception as e:
            logger.error(f"Error displaying source type badge: {e}")
            return '-'
    
    source_type_badge.short_description = '[STATS] Source Type'
    source_type_badge.admin_order_field = 'source_type'
    
    def amount_display(self, obj):
        """Display amount with currency"""
        try:
            if not obj:
                return '-'
            
            amount = SafeDisplay.safe_decimal(obj.amount, 0)
            
            if amount > 0:
                # Color intensity based on amount
                if amount >= 100:
                    gradient = 'linear-gradient(135deg, #4CAF50, #8BC34A)'
                elif amount >= 10:
                    gradient = 'linear-gradient(135deg, #8BC34A, #CDDC39)'
                else:
                    gradient = 'linear-gradient(135deg, #CDDC39, #FFEB3B)'
                
                return format_html(
                    '<span style="background: {}; color: white; padding: 8px 16px; '
                    'border-radius: 18px; font-weight: bold; font-size: 15px; '
                    'box-shadow: 0 3px 6px rgba(0,0,0,0.2); display: inline-block;">'
                    '[MONEY] ${:.2f}</span>',
                    gradient, amount
                )
            return '-'
        except Exception as e:
            logger.error(f"Error displaying amount: {e}")
            return '-'
    
    amount_display.short_description = '[MONEY] Amount'
    amount_display.admin_order_field = 'amount'
    
    def task_display(self, obj):
        """Display related task"""
        try:
            if not obj or not obj.task:
                return format_html('<span style="color: #999;">-</span>')
            
            url = reverse('admin:tasks_mastertask_change', args=[obj.task.id])
            task_id = escape(obj.task.task_id)
            
            return format_html(
                '<a href="{}" style="color: #4CAF50; font-weight: 500; '
                'text-decoration: none;">📋 {}</a>',
                url, task_id
            )
        except Exception as e:
            logger.error(f"Error displaying task: {e}")
            return '-'
    
    task_display.short_description = '📋 Task'
    
    def user_display(self, obj):
        """Display related user"""
        try:
            if not obj or not obj.user:
                return format_html('<span style="color: #999;">-</span>')
            
            username = escape(obj.user.username)
            
            return format_html(
                '<span style="color: #667eea; font-weight: 500;">👤 {}</span>',
                username
            )
        except Exception as e:
            logger.error(f"Error displaying user: {e}")
            return '-'
    
    user_display.short_description = '👤 User'
    
    def date_display(self, obj):
        """Display creation date"""
        try:
            if not obj or not obj.created_at:
                return '-'
            
            # Time ago
            now = timezone.now()
            delta = now - obj.created_at
            
            if delta.days > 365:
                time_ago = f"{delta.days // 365}y ago"
            elif delta.days > 30:
                time_ago = f"{delta.days // 30}mo ago"
            elif delta.days > 0:
                time_ago = f"{delta.days}d ago"
            elif delta.seconds > 3600:
                time_ago = f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                time_ago = f"{delta.seconds // 60}m ago"
            else:
                time_ago = "just now"
            
            date_str = obj.created_at.strftime('%Y-%m-%d %H:%M')
            
            return format_html(
                '<div style="text-align: center;">'
                '<div style="color: #666; font-size: 11px;">📅 {}</div>'
                '<div style="color: #999; font-size: 9px;">{}</div>'
                '</div>',
                date_str, time_ago
            )
        except Exception as e:
            logger.error(f"Error displaying date: {e}")
            return '-'
    
    date_display.short_description = '📅 Date'
    date_display.admin_order_field = 'created_at'
    
    # ============ READONLY FIELD METHODS ============
    
    def metadata_display(self, obj):
        """Display metadata"""
        try:
            if not obj:
                return '-'
            
            metadata = SafeDisplay.safe_dict(obj.metadata, {})
            
            if not metadata:
                return format_html(
                    '<div style="color: #999; font-style: italic;">No metadata available</div>'
                )
            
            metadata_json = json.dumps(metadata, indent=2)
            
            return format_html(
                '<div style="border: 2px solid #9C27B0; border-radius: 8px; overflow: hidden;">'
                '<div style="background: #9C27B0; color: white; padding: 10px; font-weight: bold;">'
                '[DOC] Metadata'
                '</div>'
                '<pre style="background: #f9f9f9; padding: 15px; margin: 0; '
                'max-height: 300px; overflow: auto; font-size: 11px;">{}</pre>'
                '</div>',
                escape(metadata_json)
            )
        except Exception as e:
            logger.error(f"Error displaying metadata: {e}")
            return format_html('<div style="color: red;">Error loading metadata</div>')
    
    metadata_display.short_description = '[DOC] Metadata'
    
    # ============ CUSTOM ADMIN VIEWS ============
    
    def changelist_view(self, request, extra_context=None):
        """Add custom context to changelist"""
        try:
            extra_context = extra_context or {}
            
            # Calculate total profit
            total_profit = AdminLedger.get_total_profit()
            
            # Get profit by period (last 30 days)
            profit_by_source = AdminLedger.get_profit_by_period(30)
            
            extra_context['total_profit'] = float(total_profit)
            extra_context['profit_by_source'] = profit_by_source
            
        except Exception as e:
            logger.error(f"Error in changelist_view: {e}")
        
        return super().changelist_view(request, extra_context)


# ==================== ADMIN SITE CUSTOMIZATION ====================

# Customize admin site headers
admin.site.site_header = format_html(
    '<span style="color: #667eea; font-weight: bold; font-size: 20px;">🎯 Task Management System</span>'
)
admin.site.site_title = 'Tasks Admin Portal'
admin.site.index_title = format_html(
    '<h2 style="color: #667eea; font-weight: bold;">Welcome to Task Management Dashboard</h2>'
    '<p style="color: #999;">Manage tasks, completions, and admin profits</p>'
)


# ==================== FORCE REGISTER TASKS MODELS ====================
try:
    from .models import MasterTask, UserTaskCompletion, AdminLedger
    
    registered_count = 0
    
    if not admin.site.is_registered(MasterTask):
        admin.site.register(MasterTask, MasterTaskAdmin)
        registered_count += 1
        print("[OK] Registered: MasterTask")
    
    if not admin.site.is_registered(UserTaskCompletion):
        admin.site.register(UserTaskCompletion, UserTaskCompletionAdmin)
        registered_count += 1
        print("[OK] Registered: UserTaskCompletion")
    
    if not admin.site.is_registered(AdminLedger):
        admin.site.register(AdminLedger, AdminLedgerAdmin)
        registered_count += 1
        print("[OK] Registered: AdminLedger")
    
    print(f"[OK][OK][OK] {registered_count} tasks models registered successfully!")
    
except Exception as e:
    print(f"[ERROR] Tasks registration error: {e}")