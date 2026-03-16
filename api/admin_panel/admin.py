# api/admin_panel/admin.py
from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User, Group
from django.db.models import Count, Sum, Avg, Q, F
from datetime import datetime, timedelta
from django.contrib.admin import display 
# এটি চেক করুন
from .models import SystemSettings, SiteNotification, SiteContent
import json
import os
from .models import AdminAction
from django.utils.html import format_html
from api.users.models import UserProfile
from api.users.admin import UserProfileAdmin
from django import forms
from .models import SystemSettings
from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.contrib.auth.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from django.utils.safestring import mark_safe

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
import traceback

# ==================== IMPORT YOUR MODELS ====================

# ১. System models from api/models.py (that we just created)
try:
    from api.admin_panel.models import SystemSettings, AdminAction, Report
    MODELS_AVAILABLE = True
    

except ImportError as e:
    print(f"Warning: Could not import system models: {e}")
    SystemSettings = None
    AdminAction = None
    Report = None
    UserProfile = None
    MODELS_AVAILABLE = False

# ২. Backup models
try:
    from api.backup.models import (
        Backup, BackupSchedule, BackupStorageLocation,
        BackupRestoration, BackupLog
    )
    BACKUP_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import backup models: {e}")
    BACKUP_AVAILABLE = False

# ৩. Other models (if they exist in your project)
try:
    from api.wallet.models import Wallet, Transaction, WithdrawalRequest
    WALLET_AVAILABLE = True
except ImportError:
    Wallet = Transaction = WithdrawalRequest = None
    WALLET_AVAILABLE = False

try:
    from api.referral.models import Referral
    REFERRAL_AVAILABLE = True
except ImportError:
    Referral = None
    REFERRAL_AVAILABLE = False

try:
    from api.notifications.models import Notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    Notification = None
    NOTIFICATIONS_AVAILABLE = False

try:
    from api.offers.models import Offer, UserOffer
    OFFERS_AVAILABLE = True
except ImportError:
    Offer = UserOffer = None
    OFFERS_AVAILABLE = False


# ==================== CUSTOM ADMIN SITE ====================

class ModernAdminSite(admin.AdminSite):
    """Custom Admin Site with Modern Dashboard"""
    
    site_header = "[MONEY] Earning Backend Administration"
    site_title = "Modern Admin Dashboard"
    index_title = "Welcome to Modern Dashboard"
    
    def get_urls(self):
        """Add custom URLs to admin site"""
        urls = super().get_urls()
        
        custom_urls = [
            # Modern Dashboard
            path('modern-dashboard/', self.admin_view(self.modern_dashboard_view), name='modern_dashboard'),
            
            # Referral Dashboard
            path('referral-dashboard/', self.admin_view(self.referral_dashboard_view), name='referral_dashboard'),
            
            # Analytics Dashboard
            path('analytics/', self.admin_view(self.analytics_dashboard_view), name='analytics_dashboard'),
            
            # User Management
            path('user-management/', self.admin_view(self.user_management_view), name='user_management'),
            
            # Financial Overview
            path('financial-overview/', self.admin_view(self.financial_overview_view), name='financial_overview'),
            
            # System Health
            path('system-health/', self.admin_view(self.system_health_view), name='system_health'),
            
            # Backup Management
            path('backup-management/', self.admin_view(self.backup_management_view), name='backup_management'),
        ]
        
        return custom_urls + urls
    
    def modern_dashboard_view(self, request):
        """Modern Dashboard View"""
        try:
            # Get statistics
            stats = self._get_dashboard_stats()
            
            # Prepare context
            context = {
                **self.each_context(request),
                'title': _('Modern Dashboard'),
                'stats': stats,
                'recent_users': self._get_recent_users(),
                'recent_transactions': self._get_recent_transactions(),
                'pending_withdrawals': self._get_pending_withdrawals(),
                'system_status': self._get_system_status(),
                'chart_data': self._get_chart_data(),
            }
            
            # Try to render with Unfold template
            return render(request, 'unfold/layouts/dashboard.html', context)
            
        except Exception as e:
            # Fallback to simple dashboard
            return self._render_fallback_dashboard(request, str(e))
    
    def referral_dashboard_view(self, request):
        """Referral Dashboard View"""
        try:
            # Get referral statistics
            stats = self._get_referral_stats()
            
            context = {
                **self.each_context(request),
                'title': _('Referral Dashboard'),
                'stats': stats,
                'top_referrers': self._get_top_referrers(),
                'referral_conversion': self._get_referral_conversion(),
                'referral_timeline': self._get_referral_timeline(),
            }
            
            return render(request, 'admin/referral_dashboard.html', context)
            
        except Exception as e:
            # Fallback HTML
            return self._render_referral_fallback(stats if 'stats' in locals() else {})
    
    def analytics_dashboard_view(self, request):
        """Analytics Dashboard View"""
        context = {
            **self.each_context(request),
            'title': _('Analytics Dashboard'),
            'user_growth': self._get_user_growth_data(),
            'revenue_trends': self._get_revenue_trends(),
            'offer_performance': self._get_offer_performance(),
            'geographic_data': self._get_geographic_data(),
        }
        
        return render(request, 'admin/analytics_dashboard.html', context)
    
    def user_management_view(self, request):
        """User Management Dashboard"""
        context = {
            **self.each_context(request),
            'title': _('User Management'),
            'total_users': self._get_user_count(),
            'active_users': self._get_active_users_count(),
            'new_users_today': self._get_new_users_today(),
            'users_by_country': self._get_users_by_country(),
            'user_segments': self._get_user_segments(),
        }
        
        return render(request, 'admin/user_management.html', context)
    
    def financial_overview_view(self, request):
        """Financial Overview Dashboard"""
        context = {
            **self.each_context(request),
            'title': _('Financial Overview'),
            'total_earnings': self._get_total_earnings(),
            'total_payouts': self._get_total_payouts(),
            'pending_payouts': self._get_pending_payouts(),
            'revenue_sources': self._get_revenue_sources(),
            'payout_methods': self._get_payout_methods_distribution(),
        }
        
        return render(request, 'admin/financial_overview.html', context)
    
    def system_health_view(self, request):
        """System Health Dashboard"""
        context = {
            **self.each_context(request),
            'title': _('System Health'),
            'server_status': self._get_server_status(),
            'database_status': self._get_database_status(),
            'api_status': self._get_api_status(),
            'storage_status': self._get_storage_status(),
            'error_logs': self._get_recent_error_logs(),
        }
        
        return render(request, 'admin/system_health.html', context)
    
    def backup_management_view(self, request):
        """Backup Management Dashboard"""
        try:
            if BACKUP_AVAILABLE:
                backup_stats = self._get_backup_stats()
            else:
                backup_stats = {}
                
            context = {
                **self.each_context(request),
                'title': _('Backup Management'),
                'backup_stats': backup_stats,
                'recent_backups': self._get_recent_backups(),
                'storage_usage': self._get_storage_usage(),
                'backup_schedules': self._get_backup_schedules(),
            }
            
            return render(request, 'admin/backup_management.html', context)
            
        except Exception as e:
            return HttpResponse(f"Backup Dashboard Error: {str(e)}")
    
    # ==================== HELPER METHODS ====================
    
    def _get_dashboard_stats(self):
        """Get comprehensive dashboard statistics"""
        try:
            stats = {
                'users': {
                    'total': User.objects.count(),
                    'active': self._get_active_users_count(),
                    'new_today': self._get_new_users_today(),
                    'verified': self._get_verified_users_count(),
                },
                'earnings': {
                    'total': self._get_total_earnings(),
                    'today': self._get_earnings_today(),
                    'this_month': self._get_earnings_this_month(),
                    'pending': self._get_pending_earnings(),
                },
                'offers': {
                    'total': self._get_total_offers(),
                    'active': self._get_active_offers(),
                    'completed_today': self._get_completed_offers_today(),
                    'conversion_rate': self._get_conversion_rate(),
                },
                'referrals': {
                    'total': self._get_total_referrals(),
                    'active': self._get_active_referrals(),
                    'commission_today': self._get_referral_commission_today(),
                    'top_referrer': self._get_top_referrer_info(),
                },
                'wallet': {
                    'total_balance': self._get_total_wallet_balance(),
                    'pending_withdrawals': self._get_pending_withdrawals_count(),
                    'total_withdrawn': self._get_total_withdrawn(),
                    'withdrawal_success_rate': self._get_withdrawal_success_rate(),
                },
                'system': {
                    'uptime': self._get_system_uptime(),
                    'response_time': self._get_avg_response_time(),
                    'error_rate': self._get_error_rate(),
                    'storage_used': self._get_storage_used_percentage(),
                }
            }
            return stats
        except Exception as e:
            return self._get_default_stats()
    
    def _get_default_stats(self):
        """Default statistics when models are not available"""
        return {
            'users': {'total': 0, 'active': 0, 'new_today': 0, 'verified': 0},
            'earnings': {'total': 0, 'today': 0, 'this_month': 0, 'pending': 0},
            'offers': {'total': 0, 'active': 0, 'completed_today': 0, 'conversion_rate': 0},
            'referrals': {'total': 0, 'active': 0, 'commission_today': 0, 'top_referrer': 'N/A'},
            'wallet': {'total_balance': 0, 'pending_withdrawals': 0, 'total_withdrawn': 0, 'withdrawal_success_rate': 0},
            'system': {'uptime': '100%', 'response_time': '0ms', 'error_rate': '0%', 'storage_used': '0%'}
        }
    
    def _get_recent_users(self, limit=10):
        """Get recent users"""
        try:
            return User.objects.select_related('profile').order_by('-date_joined')[:limit]
        except:
            return []
    
    def _get_recent_transactions(self, limit=10):
        """Get recent transactions"""
        try:
            if WALLET_AVAILABLE:
                return Transaction.objects.select_related('user').order_by('-created_at')[:limit]
        except:
            pass
        return []
    
    def _get_pending_withdrawals(self, limit=10):
        """Get pending withdrawal requests"""
        try:
            if WALLET_AVAILABLE:
                return WithdrawalRequest.objects.filter(status='pending').select_related('user').order_by('-created_at')[:limit]
        except:
            pass
        return []
    
    def _get_system_status(self):
        """Get system status"""
        return {
            'database': 'Online',
            'cache': 'Online',
            'api': 'Online',
            'storage': 'Online',
            'last_checked': timezone.now(),
        }
    
    def _get_chart_data(self):
        """Get chart data for dashboard"""
        # Generate sample data for charts
        days = 30
        chart_data = {
            'labels': [(timezone.now() - timedelta(days=i)).strftime('%b %d') for i in range(days)][::-1],
            'users': [max(0, 100 + i * 5 + (i % 7) * 10) for i in range(days)],
            'earnings': [max(0, 500 + i * 20 + (i % 5) * 50) for i in range(days)],
            'offers': [max(0, 50 + i * 2 + (i % 3) * 5) for i in range(days)],
        }
        return chart_data
    
    def _get_referral_stats(self):
        """Get referral statistics"""
        return {
            'total_referrals': 0,
            'active_referrals': 0,
            'total_commission': 0,
            'conversion_rate': '0%',
            'top_countries': [],
            'monthly_trend': [],
        }
    
    def _get_top_referrers(self, limit=10):
        """Get top referrers"""
        return []
    
    def _get_user_count(self):
        """Get total user count"""
        return User.objects.count()
    
    def _get_active_users_count(self):
        """Get active users count (last 7 days)"""
        try:
            week_ago = timezone.now() - timedelta(days=7)
            return User.objects.filter(last_login__gte=week_ago).count()
        except:
            return 0
    
    def _get_new_users_today(self):
        """Get new users registered today"""
        try:
            today = timezone.now().date()
            return User.objects.filter(date_joined__date=today).count()
        except:
            return 0
    
    def _get_total_earnings(self):
        """Get total earnings"""
        try:
            if WALLET_AVAILABLE:
                return Transaction.objects.filter(
                    transaction_type='earning'
                ).aggregate(total=Sum('amount'))['total'] or 0
        except:
            pass
        return 0
    
    def _get_server_status(self):
        """Get server status"""
        return {
            'cpu_usage': '25%',
            'memory_usage': '45%',
            'disk_usage': '60%',
            'uptime': '15 days',
            'load_average': '1.2, 1.5, 1.8',
        }
    
    def _get_backup_stats(self):
        """Get backup statistics"""
        try:
            if BACKUP_AVAILABLE:
                total_backups = Backup.objects.count()
                completed_backups = Backup.objects.filter(status=Backup.STATUS_COMPLETED).count()
                failed_backups = Backup.objects.filter(status=Backup.STATUS_FAILED).count()
                total_size = Backup.objects.aggregate(total=Sum('file_size'))['total'] or 0
                
                return {
                    'total_backups': total_backups,
                    'completed_backups': completed_backups,
                    'failed_backups': failed_backups,
                    'total_size': total_size,
                    'success_rate': (completed_backups / total_backups * 100) if total_backups > 0 else 0,
                }
        except:
            pass
        return {}
    
    def _get_recent_backups(self, limit=5):
        """Get recent backups"""
        try:
            if BACKUP_AVAILABLE:
                return Backup.objects.order_by('-created_at')[:limit]
        except:
            pass
        return []
    
    # ==================== FALLBACK RENDERS ====================
    
    def _render_fallback_dashboard(self, request, error_message=None):
        """Render fallback dashboard HTML"""
        stats = self._get_dashboard_stats()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Modern Dashboard - Fallback</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.js"></script>
            <style>
                .stat-card {{ transition: transform 0.2s; }}
                .stat-card:hover {{ transform: translateY(-2px); }}
                .gradient-bg {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
            </style>
        </head>
        <body class="bg-gray-50 min-h-screen">
            <div class="gradient-bg text-white p-6">
                <div class="max-w-7xl mx-auto">
                    <div class="flex justify-between items-center">
                        <div>
                            <h1 class="text-3xl font-bold">[MONEY] Earning Backend Dashboard</h1>
                            <p class="text-gray-200">Real-time statistics and analytics</p>
                        </div>
                        <div class="flex space-x-4">
                            <a href="{reverse('admin:index')}" class="bg-white text-purple-600 px-4 py-2 rounded-lg font-semibold hover:bg-gray-100">
                                Admin Home
                            </a>
                            <a href="{reverse('admin:logout')}" class="bg-red-500 text-white px-4 py-2 rounded-lg font-semibold hover:bg-red-600">
                                Logout
                            </a>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="max-w-7xl mx-auto p-6">
                {f'<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">Template Error: {error_message}</div>' if error_message else ''}
                
                <!-- Stats Grid -->
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    <div class="stat-card bg-white rounded-xl shadow-lg p-6">
                        <div class="flex items-center">
                            <div class="p-3 bg-blue-100 rounded-lg mr-4">
                                <i data-lucide="users" class="w-6 h-6 text-blue-600"></i>
                            </div>
                            <div>
                                <p class="text-gray-500 text-sm">Total Users</p>
                                <p class="text-2xl font-bold text-gray-800">{stats['users']['total']}</p>
                            </div>
                        </div>
                        <div class="mt-4 text-sm text-green-600">
                            +{stats['users']['new_today']} today
                        </div>
                    </div>
                    
                    <div class="stat-card bg-white rounded-xl shadow-lg p-6">
                        <div class="flex items-center">
                            <div class="p-3 bg-green-100 rounded-lg mr-4">
                                <i data-lucide="dollar-sign" class="w-6 h-6 text-green-600"></i>
                            </div>
                            <div>
                                <p class="text-gray-500 text-sm">Total Earnings</p>
                                <p class="text-2xl font-bold text-gray-800">${stats['earnings']['total']}</p>
                            </div>
                        </div>
                        <div class="mt-4 text-sm text-green-600">
                            +${stats['earnings']['today']} today
                        </div>
                    </div>
                    
                    <div class="stat-card bg-white rounded-xl shadow-lg p-6">
                        <div class="flex items-center">
                            <div class="p-3 bg-purple-100 rounded-lg mr-4">
                                <i data-lucide="git-branch" class="w-6 h-6 text-purple-600"></i>
                            </div>
                            <div>
                                <p class="text-gray-500 text-sm">Total Referrals</p>
                                <p class="text-2xl font-bold text-gray-800">{stats['referrals']['total']}</p>
                            </div>
                        </div>
                        <div class="mt-4 text-sm text-green-600">
                            ${stats['referrals']['commission_today']} commission
                        </div>
                    </div>
                    
                    <div class="stat-card bg-white rounded-xl shadow-lg p-6">
                        <div class="flex items-center">
                            <div class="p-3 bg-yellow-100 rounded-lg mr-4">
                                <i data-lucide="package" class="w-6 h-6 text-yellow-600"></i>
                            </div>
                            <div>
                                <p class="text-gray-500 text-sm">Active Offers</p>
                                <p class="text-2xl font-bold text-gray-800">{stats['offers']['active']}</p>
                            </div>
                        </div>
                        <div class="mt-4 text-sm text-green-600">
                            {stats['offers']['conversion_rate']}% conversion
                        </div>
                    </div>
                </div>
                
                <!-- Quick Links -->
                <div class="bg-white rounded-xl shadow-lg p-6 mb-8">
                    <h2 class="text-xl font-bold text-gray-800 mb-4">Quick Actions</h2>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <a href="/admin/auth/user/" class="bg-blue-50 hover:bg-blue-100 p-4 rounded-lg text-center">
                            <i data-lucide="users" class="w-8 h-8 text-blue-600 mx-auto mb-2"></i>
                            <p class="font-semibold text-gray-700">Manage Users</p>
                        </a>
                        <a href="/admin/backup/backup/" class="bg-green-50 hover:bg-green-100 p-4 rounded-lg text-center">
                            <i data-lucide="database" class="w-8 h-8 text-green-600 mx-auto mb-2"></i>
                            <p class="font-semibold text-gray-700">Backup System</p>
                        </a>
                        <a href="/admin/referral-dashboard/" class="bg-purple-50 hover:bg-purple-100 p-4 rounded-lg text-center">
                            <i data-lucide="git-branch" class="w-8 h-8 text-purple-600 mx-auto mb-2"></i>
                            <p class="font-semibold text-gray-700">Referral Stats</p>
                        </a>
                        <a href="/admin/system-health/" class="bg-red-50 hover:bg-red-100 p-4 rounded-lg text-center">
                            <i data-lucide="activity" class="w-8 h-8 text-red-600 mx-auto mb-2"></i>
                            <p class="font-semibold text-gray-700">System Health</p>
                        </a>
                    </div>
                </div>
                
                <!-- Backup Status -->
                <div class="bg-white rounded-xl shadow-lg p-6">
                    <h2 class="text-xl font-bold text-gray-800 mb-4">Backup System Status</h2>
                    <div class="overflow-x-auto">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead>
                                <tr>
                                    <th class="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">Backup Name</th>
                                    <th class="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                                    <th class="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                    <th class="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                                    <th class="px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                                </tr>
                            </thead>
                            <tbody class="bg-white divide-y divide-gray-200">
        """
        
        # Add backup rows
        recent_backups = self._get_recent_backups()
        for backup in recent_backups:
            status_color = {
                'completed': 'bg-green-100 text-green-800',
                'failed': 'bg-red-100 text-red-800',
                'running': 'bg-blue-100 text-blue-800',
                'pending': 'bg-yellow-100 text-yellow-800',
            }.get(backup.status, 'bg-gray-100 text-gray-800')
            
            html += f"""
                <tr>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{backup.name}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{backup.get_backup_type_display()}</td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_color}">
                            {backup.get_status_display()}
                        </span>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{backup.file_size_formatted}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{backup.created_at.strftime('%Y-%m-%d %H:%M')}</td>
                </tr>
            """
        
        html += """
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <script>
                lucide.createIcons();
                
                // Auto-refresh dashboard every 30 seconds
                setTimeout(function() {
                    window.location.reload();
                }, 30000);
            </script>
        </body>
        </html>
        """
        
        return HttpResponse(html)
    
    def _render_referral_fallback(self, stats):
        """Render fallback referral dashboard"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Referral Dashboard</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-50 p-6">
            <div class="max-w-6xl mx-auto">
                <div class="mb-6">
                    <h1 class="text-3xl font-bold text-gray-800">Referral Dashboard</h1>
                    <p class="text-gray-600">Manage and monitor your referral program</p>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                    <div class="bg-white p-6 rounded-lg shadow">
                        <h3 class="font-semibold text-gray-700 mb-2">Total Referrals</h3>
                        <div class="text-2xl font-bold text-blue-600">{stats.get('total_referrals', 0)}</div>
                    </div>
                    
                    <div class="bg-white p-6 rounded-lg shadow">
                        <h3 class="font-semibold text-gray-700 mb-2">Total Commission</h3>
                        <div class="text-2xl font-bold text-green-600">${stats.get('total_commission', 0)}</div>
                    </div>
                    
                    <div class="bg-white p-6 rounded-lg shadow">
                        <h3 class="font-semibold text-gray-700 mb-2">Conversion Rate</h3>
                        <div class="text-2xl font-bold text-purple-600">{stats.get('conversion_rate', '0%')}</div>
                    </div>
                </div>
                
                <div class="bg-white p-6 rounded-lg shadow">
                    <h3 class="font-semibold text-gray-700 mb-4">Quick Actions</h3>
                    <div class="flex space-x-4">
                        <a href="/admin/auth/user/" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
                            View Users
                        </a>
                        <a href="/admin/modern-dashboard/" class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600">
                            Back to Dashboard
                        </a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html)


# ==================== CREATE ADMIN SITE INSTANCE ====================

# Create instance of custom admin site
admin_site = ModernAdminSite(name='modern_admin')

# ==================== SAFE REGISTRATION FUNCTION ====================

def safe_register(model_class, admin_class=None, verbose_name=None):
    """
    Safely register a model with admin site, handling import errors
    """
    if model_class is None:
        print(f"Warning: Cannot register None model")
        return False
    
    try:
        if admin_class:
            admin_site.register(model_class, admin_class)
        else:
            admin_site.register(model_class)
        
        if verbose_name:
            print(f"Successfully registered: {verbose_name}")
        else:
            print(f"Successfully registered: {model_class.__name__}")
        
        return True
    except Exception as e:
        print(f"Warning: Could not register {model_class.__name__}: {e}")
        return False


# ==================== REGISTER DEFAULT DJANGO MODELS ====================

# Register User and Group
try:
    admin_site.unregister(User)
    admin_site.unregister(Group)
except admin.sites.NotRegistered:
    pass

safe_register(User, verbose_name="Users")
safe_register(Group, verbose_name="Groups")

# ==================== REGISTER BACKUP MODELS ====================

if BACKUP_AVAILABLE:
    # Backup Admin Classes
    class BackupAdmin(ModelAdmin):
        list_display = ['name', 'backup_type', 'status', 'database_name', 'file_size_formatted', 'created_at']
        list_filter = ['backup_type', 'created_at', 'database_name', 'storage_type']
        search_fields = ['name', 'description', 'database_name']
        readonly_fields = ['backup_id', 'created_at', 'updated_at', 'file_size_formatted']
        
        fieldsets = (
            ('Basic Information', {
                'fields': ('name', 'description', 'backup_type', 'status', 'created_by')
            }),
            ('Database Information', {
                'fields': ('database_name', 'database_engine', 'tables_included', 'tables_excluded')
            }),
            ('File Information', {
                'fields': ('backup_file', 'file_size_formatted', 'file_format', 'compression_enabled', 'encryption_enabled')
            }),
            ('Timestamps', {
                'fields': ('created_at', 'updated_at', 'start_time', 'end_time', 'expires_at')
            }),
        )
        
        @display(description='File Size')
        def file_size_formatted(self, obj):
            return obj.file_size_formatted if hasattr(obj, 'file_size_formatted') else 'N/A'
    
    class BackupScheduleAdmin(ModelAdmin):
        list_display = ['name', 'frequency', 'backup_type', 'is_active', 'next_run']
        list_filter = ['frequency', 'is_active', 'backup_type']
        list_editable = ['is_active']
    
    class BackupStorageLocationAdmin(ModelAdmin):
        list_display = ['name', 'storage_type', 'is_connected', 'free_space_formatted']
        list_filter = ['storage_type', 'is_connected']
        
        @display(description='Free Space')
        def free_space_formatted(self, obj):
            return obj.free_space_formatted if hasattr(obj, 'free_space_formatted') else 'N/A'
    
    class BackupRestorationAdmin(ModelAdmin):
        list_display = ['restoration_id', 'backup', 'status', 'started_at', 'initiated_by']
        list_filter = ['restoration_type']
        readonly_fields = ['restoration_id', 'started_at']
    
    class BackupLogAdmin(ModelAdmin):
        list_display = ['timestamp', 'level', 'category', 'message_short', 'backup']
        list_filter = ['level', 'category', 'source']
        readonly_fields = ['log_id', 'timestamp']
        search_fields = ['message', 'error_message']
        
        @display(description='Message')
        def message_short(self, obj):
            return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    
    # Register backup models
    safe_register(Backup, BackupAdmin, "Backups")
    safe_register(BackupSchedule, BackupScheduleAdmin, "Backup Schedules")
    safe_register(BackupStorageLocation, BackupStorageLocationAdmin, "Storage Locations")
    safe_register(BackupRestoration, BackupRestorationAdmin, "Backup Restorations")
    safe_register(BackupLog, BackupLogAdmin, "Backup Logs")

# ==================== REGISTER SYSTEM MODELS ====================

if MODELS_AVAILABLE:
    # # System Admin Classes
    # class SystemSettingsAdmin(ModelAdmin):
    #     list_display = ['site_name', 'contact_email', 'currency_code', 'maintenance_mode']
    #     list_editable = ['maintenance_mode']
    #     readonly_fields = ['created_at', 'updated_at']
        
    #     def has_add_permission(self, request):
    #         # Only allow one SystemSettings record
    #         return not SystemSettings.objects.exists()
        
    #     def has_delete_permission(self, request, obj=None):
    #         # Don't allow deletion of SystemSettings
    #         return False
    


 class SystemSettingsAdminForm(forms.ModelForm):
    """Custom form for SystemSettings admin"""
    
    class Meta:
        model = SystemSettings
        fields = '__all__'
        widgets = {
            'smtp_password': forms.PasswordInput(render_value=True),
            'sms_api_secret': forms.PasswordInput(render_value=True),
            'sms_api_key': forms.PasswordInput(render_value=True),
            'firebase_server_key': forms.PasswordInput(render_value=True),
            'maintenance_message': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
            'android_update_message': forms.Textarea(attrs={'rows': 2, 'cols': 80}),
            'ios_update_message': forms.Textarea(attrs={'rows': 2, 'cols': 80}),
            'disclaimer_text': forms.Textarea(attrs={'rows': 4, 'cols': 80}),
            'site_description': forms.Textarea(attrs={'rows': 3, 'cols': 80}),
        }


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    form = SystemSettingsAdminForm
    
    list_display = [
        'site_name',
        'status_indicator',
        'currency_display',
        'version_info',
        'security_status',
        'last_updated'
    ]
    
    list_editable = []
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'settings_health_check',
        'security_summary',
        'version_summary',
        'limits_summary',
        'quick_stats'
    ]
    
    actions = [
        'enable_maintenance_mode',
        'disable_maintenance_mode',
        'enable_all_security',
        'reset_to_defaults'
    ]
    
    fieldsets = (
        # ==================== Quick Overview ====================
        ('[STATS] System Status & Health', {
            'fields': (
                'settings_health_check',
                'quick_stats',
            ),
            'classes': ('wide',)
        }),
        
        # ==================== Site Information ====================
        ('🌐 Site Information', {
            'fields': (
                'site_name',
                'site_tagline',
                'site_description',
                'site_logo',
                'site_favicon',
                'site_url',
                'contact_email',
                'support_email',
                'admin_email'
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Contact Information ====================
        ('📞 Contact & Social Media', {
            'fields': (
                'contact_phone',
                'contact_whatsapp',
                'contact_address',
                ('contact_facebook', 'contact_twitter'),
                ('contact_instagram', 'contact_telegram'),
                ('contact_youtube', 'contact_linkedin')
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Currency & Payment ====================
        ('[MONEY] Currency & Payment Settings', {
            'fields': (
                ('currency_code', 'currency_symbol'),
                ('min_withdrawal_amount', 'max_withdrawal_amount'),
                ('withdrawal_fee_percentage', 'withdrawal_fee_fixed'),
                'tax_percentage',
                # Payment Gateways
                ('enable_bkash', 'enable_nagad', 'enable_rocket'),
                ('enable_stripe', 'enable_paypal', 'enable_bank_transfer'),
            ),
            'description': 'Configure payment methods and withdrawal limits'
        }),
        
        # ==================== Points System ====================
        ('[STAR] Points & Rewards System', {
            'fields': (
                ('point_value', 'min_points_withdrawal'),
                # Bonus Points
                ('welcome_bonus_points', 'daily_login_bonus'),
                ('referral_bonus_points', 'first_withdrawal_bonus'),
                ('birthday_bonus',),
                # Action Rewards
                ('ad_click_points', 'video_watch_points'),
                ('survey_complete_points', 'task_complete_points'),
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Referral System ====================
        ('👥 Referral System', {
            'fields': (
                'enable_referral',
                'referral_levels',
                ('referral_percentage_level1', 'referral_percentage_level2'),
                ('referral_percentage_level3', 'referral_percentage_level4'),
                ('referral_percentage_level5',),
                ('referral_expiry_days', 'min_referral_withdrawal'),
            ),
            'classes': ('collapse',),
            'description': 'Configure multi-level referral commission structure'
        }),
        
        # ==================== App Version Control ====================
        ('📱 Android Version Control', {
            'fields': (
                'version_summary',
                ('android_version', 'android_version_code'),
                ('android_min_version', 'android_min_version_code'),
                'android_force_update',
                'android_update_message',
                'android_app_link',
                'android_apk_link',
            ),
            'description': '🔴 Force Update will prevent old versions from accessing the app'
        }),
        
        ('🍎 iOS Version Control', {
            'fields': (
                ('ios_version', 'ios_version_code'),
                ('ios_min_version', 'ios_min_version_code'),
                'ios_force_update',
                'ios_update_message',
                'ios_app_link',
            ),
            'classes': ('collapse',)
        }),
        
        ('🌐 Web Version Control', {
            'fields': (
                'web_version',
                'web_force_reload',
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Fraud Prevention ====================
        ('🛡️ Fraud Prevention & Daily Limits', {
            'fields': (
                'limits_summary',
                # Daily Limits
                ('max_daily_earning_limit', 'max_daily_withdrawal_limit'),
                ('max_daily_ads', 'max_daily_videos'),
                ('max_daily_tasks', 'max_daily_surveys'),
                # Suspicious Activity
                ('suspicious_activity_threshold', 'suspicious_click_speed'),
                'suspicious_device_count',
            ),
            'description': '[WARN] Set limits to prevent fraud and abuse'
        }),
        
        ('🚫 Auto-Ban Settings', {
            'fields': (
                'auto_ban_on_vpn',
                'auto_ban_on_emulator',
                'auto_ban_on_root',
                'auto_ban_on_multiple_accounts',
            ),
            'classes': ('collapse',)
        }),
        
        ('🌍 IP & Device Restrictions', {
            'fields': (
                ('max_accounts_per_ip', 'max_accounts_per_device'),
                'block_vpn_users',
                'block_proxy_users',
                'block_tor_users',
            ),
            'classes': ('collapse',)
        }),
        
        ('⏱️ Click Fraud Prevention', {
            'fields': (
                'min_ad_watch_time',
                'min_video_watch_time',
                'click_delay_seconds',
            ),
            'classes': ('collapse',),
            'description': 'Minimum time requirements to prevent bot clicking'
        }),
        
        # ==================== Security & Verification ====================
        ('[SECURE] Account Security', {
            'fields': (
                'security_summary',
                'enable_2fa',
                'force_2fa_for_withdrawal',
                ('enable_withdrawal_pin', 'withdrawal_pin_length'),
            ),
        }),
        
        ('[OK] Verification Requirements', {
            'fields': (
                'enable_email_verification',
                'enable_phone_verification',
                'enable_identity_verification',
                'require_email_for_withdrawal',
                'require_phone_for_withdrawal',
                ('require_identity_for_large_withdrawal', 'large_withdrawal_threshold'),
            ),
            'classes': ('collapse',)
        }),
        
        ('[KEY] Login Security', {
            'fields': (
                ('max_login_attempts', 'account_lockout_minutes'),
                'session_timeout_minutes',
                'enable_login_notification',
                'enable_unusual_activity_alert',
            ),
            'classes': ('collapse',)
        }),
        
        ('🔒 Password Policy', {
            'fields': (
                'min_password_length',
                'require_password_uppercase',
                'require_password_lowercase',
                'require_password_number',
                'require_password_special',
                'password_expiry_days',
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Withdrawal Security ====================
        ('💸 Withdrawal Security & Processing', {
            'fields': (
                'withdrawal_review_required',
                'withdrawal_auto_approve_limit',
                ('withdrawal_processing_time', 'withdrawal_cooldown_hours'),
                'max_pending_withdrawals',
                # New User Restrictions
                ('new_user_withdrawal_delay_days', 'new_user_daily_limit'),
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Email Settings ====================
        ('📧 Email/SMTP Configuration', {
            'fields': (
                ('smtp_host', 'smtp_port'),
                'smtp_username',
                'smtp_password',
                ('smtp_use_tls', 'smtp_use_ssl'),
                ('email_from_name', 'email_from_address'),
                # Email Notifications
                'send_welcome_email',
                'send_withdrawal_email',
                'send_deposit_email',
                'send_referral_email',
                'send_security_alert_email',
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== SMS Settings ====================
        ('📱 SMS Configuration', {
            'fields': (
                'enable_sms',
                'sms_provider',
                ('sms_api_key', 'sms_api_secret'),
                ('sms_sender_id', 'sms_api_url'),
                # SMS Notifications
                'send_withdrawal_sms',
                'send_security_alert_sms',
                'send_otp_sms',
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Maintenance Mode ====================
        ('🚧 Maintenance Mode', {
            'fields': (
                'maintenance_mode',
                'maintenance_message',
                ('maintenance_start', 'maintenance_end'),
                ('allow_admin_during_maintenance', 'maintenance_reason'),
            ),
            'description': '🔴 WARNING: Enabling maintenance mode will block all users except admins'
        }),
        
        # ==================== Performance ====================
        ('⚡ Cache & Performance', {
            'fields': (
                ('cache_timeout', 'enable_caching'),
                'enable_query_optimization',
                'max_upload_size',
                'enable_compression',
                # Rate Limiting
                'enable_rate_limiting',
                ('api_rate_limit_per_minute', 'api_rate_limit_per_hour'),
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Analytics ====================
        ('[STATS] Analytics & Tracking', {
            'fields': (
                'enable_analytics',
                'google_analytics_id',
                'facebook_pixel_id',
                'google_tag_manager_id',
                'hotjar_id',
                # User Tracking
                'track_user_activity',
                'track_referral_source',
                'track_device_info',
                'track_location',
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Legal ====================
        ('⚖️ Legal & Compliance', {
            'fields': (
                'terms_url',
                'privacy_policy_url',
                'refund_policy_url',
                'cookie_policy_url',
                'disclaimer_text',
                'copyright_text',
                # GDPR
                'enable_gdpr',
                'data_retention_days',
                'allow_data_export',
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Notifications ====================
        ('🔔 Push Notifications', {
            'fields': (
                'enable_push_notifications',
                'firebase_server_key',
                'firebase_sender_id',
                # Notification Types
                'notify_on_withdrawal',
                'notify_on_deposit',
                'notify_on_referral',
                'notify_on_bonus',
                'notify_on_task_available',
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Advanced Features ====================
        ('🎮 Gamification & Social', {
            'fields': (
                # Gamification
                ('enable_leaderboard', 'enable_badges'),
                ('enable_achievements', 'enable_daily_streak'),
                # Social
                ('enable_social_sharing', 'enable_user_profiles'),
                ('enable_chat', 'enable_comments'),
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== Admin Tools ====================
        ('[FIX] Admin & Developer Tools', {
            'fields': (
                'enable_debug_mode',
                'enable_api_logs',
                'log_retention_days',
            ),
            'classes': ('collapse',)
        }),
        
        # ==================== System Info ====================
        ('[INFO] System Information', {
            'fields': (
                'last_modified_by',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Only allow one SystemSettings record"""
        # return not SystemSettings.objects.exists()
        return True
    
    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of SystemSettings"""
        return False
    
    def save_model(self, request, obj, form, change):
        """Track who modified the settings"""
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)
    
    # ==================== Custom Display Methods ====================
    
    def status_indicator(self, obj):
        """Display system status"""
        if obj.maintenance_mode:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 3px; font-weight: bold;">🚧 MAINTENANCE</span>'
            )
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 5px 10px; border-radius: 3px; font-weight: bold;">[OK] ONLINE</span>'
        )
    status_indicator.short_description = 'Status'
    
    def currency_display(self, obj):
        """Display currency info"""
        return format_html(
            '<strong>{}</strong> ({})',
            obj.currency_code,
            obj.currency_symbol
        )
    currency_display.short_description = 'Currency'
    
    def version_info(self, obj):
        """Display app versions"""
        return format_html(
            '📱 Android: {} | 🍎 iOS: {} | 🌐 Web: {}',
            obj.android_version,
            obj.ios_version,
            obj.web_version
        )
    version_info.short_description = 'Versions'
    
    def security_status(self, obj):
        """Display security status"""
        issues = []
        
        if not obj.enable_2fa:
            issues.append('No 2FA')
        if not obj.enable_email_verification:
            issues.append('No Email Verify')
        if obj.auto_ban_on_vpn:
            issues.append('VPN Ban Active')
        
        if issues:
            return format_html(
                '<span style="color: orange;">[WARN] {}</span>',
                ', '.join(issues)
            )
        return format_html('<span style="color: green;">[OK] Secure</span>')
    security_status.short_description = 'Security'
    
    def last_updated(self, obj):
        """Display last update time"""
        from django.utils.timesince import timesince
        return f"{timesince(obj.updated_at)} ago"
    last_updated.short_description = 'Last Updated'
    
    # ==================== Readonly Summary Fields ====================
    
    def settings_health_check(self, obj):
        """Comprehensive health check"""
        checks = []
        warnings = []
        errors = []
        
        # Critical Checks
        if not obj.smtp_host:
            errors.append("[ERROR] SMTP not configured - emails won't be sent")
        else:
            checks.append("[OK] SMTP configured")
        
        if not obj.contact_email:
            errors.append("[ERROR] Contact email missing")
        else:
            checks.append("[OK] Contact email set")
        
        # Security Checks
        if obj.enable_2fa:
            checks.append("[OK] 2FA enabled")
        else:
            warnings.append("[WARN] 2FA disabled")
        
        if obj.enable_email_verification:
            checks.append("[OK] Email verification enabled")
        else:
            warnings.append("[WARN] Email verification disabled")
        
        # Fraud Prevention
        if obj.max_daily_earning_limit > 0:
            checks.append(f"[OK] Daily earning limit: {obj.currency_symbol}{obj.max_daily_earning_limit}")
        else:
            warnings.append("[WARN] No daily earning limit set")
        
        # Version Control
        if obj.android_force_update:
            warnings.append("[WARN] Android force update enabled")
        if obj.ios_force_update:
            warnings.append("[WARN] iOS force update enabled")
        
        # Maintenance Mode
        if obj.maintenance_mode:
            errors.append("🚧 MAINTENANCE MODE ACTIVE")
        
        # Build HTML
        html_parts = []
        
        if errors:
            html_parts.append('<div style="background: #fff3cd; padding: 10px; margin: 5px 0; border-left: 4px solid #dc3545;">')
            html_parts.append('<strong style="color: #dc3545;">Critical Issues:</strong><br>')
            html_parts.append('<br>'.join(errors))
            html_parts.append('</div>')
        
        if warnings:
            html_parts.append('<div style="background: #fff3cd; padding: 10px; margin: 5px 0; border-left: 4px solid #ffc107;">')
            html_parts.append('<strong style="color: #856404;">Warnings:</strong><br>')
            html_parts.append('<br>'.join(warnings))
            html_parts.append('</div>')
        
        if checks:
            html_parts.append('<div style="background: #d4edda; padding: 10px; margin: 5px 0; border-left: 4px solid #28a745;">')
            html_parts.append('<strong style="color: #155724;">Active Features:</strong><br>')
            html_parts.append('<br>'.join(checks))
            html_parts.append('</div>')
        
        return format_html(''.join(html_parts))
    settings_health_check.short_description = '🏥 System Health Status'
    
    def security_summary(self, obj):
        """Security settings summary"""
        html = '<table style="width: 100%; border-collapse: collapse;">'
        
        security_items = [
            ('2FA', obj.enable_2fa),
            ('Email Verification', obj.enable_email_verification),
            ('Phone Verification', obj.enable_phone_verification),
            ('Withdrawal PIN', obj.enable_withdrawal_pin),
            ('Auto-ban VPN', obj.auto_ban_on_vpn),
            ('Auto-ban Emulator', obj.auto_ban_on_emulator),
            ('Auto-ban Root', obj.auto_ban_on_root),
            ('Block VPN', obj.block_vpn_users),
            ('Block Proxy', obj.block_proxy_users),
        ]
        
        for label, enabled in security_items:
            color = '#28a745' if enabled else '#dc3545'
            status = '[OK] Enabled' if enabled else '[ERROR] Disabled'
            html += f'<tr><td style="padding: 5px;"><strong>{label}:</strong></td>'
            html += f'<td style="padding: 5px; color: {color};">{status}</td></tr>'
        
        html += '</table>'
        return format_html(html)
    security_summary.short_description = '[SECURE] Security Overview'
    
    def version_summary(self, obj):
        """App version summary"""
        html = '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
        html += '<tr style="background: #f8f9fa;"><th style="padding: 8px;">Platform</th><th>Current</th><th>Minimum</th><th>Force Update</th></tr>'
        
        # Android
        android_color = '#dc3545' if obj.android_force_update else '#28a745'
        html += f'<tr><td style="padding: 8px;"><strong>📱 Android</strong></td>'
        html += f'<td>{obj.android_version} (#{obj.android_version_code})</td>'
        html += f'<td>{obj.android_min_version} (#{obj.android_min_version_code})</td>'
        html += f'<td style="color: {android_color};">{"[WARN] YES" if obj.android_force_update else "[OK] NO"}</td></tr>'
        
        # iOS
        ios_color = '#dc3545' if obj.ios_force_update else '#28a745'
        html += f'<tr><td style="padding: 8px;"><strong>🍎 iOS</strong></td>'
        html += f'<td>{obj.ios_version} (#{obj.ios_version_code})</td>'
        html += f'<td>{obj.ios_min_version} (#{obj.ios_min_version_code})</td>'
        html += f'<td style="color: {ios_color};">{"[WARN] YES" if obj.ios_force_update else "[OK] NO"}</td></tr>'
        
        html += '</table>'
        
        if obj.android_force_update or obj.ios_force_update:
            html += '<div style="background: #fff3cd; padding: 10px; margin-top: 10px; border-left: 4px solid #ffc107;">'
            html += '<strong>[WARN] Warning:</strong> Force update is enabled. Users with older versions cannot access the app.</div>'
        
        return format_html(html)
    version_summary.short_description = '📱 App Version Status'
    
    def limits_summary(self, obj):
        """Daily limits summary"""
        html = '<table style="width: 100%; border-collapse: collapse;">'
        
        limits = [
            ('Daily Earning', f'{obj.currency_symbol}{obj.max_daily_earning_limit}'),
            ('Daily Withdrawal', f'{obj.currency_symbol}{obj.max_daily_withdrawal_limit}'),
            ('Daily Ads', obj.max_daily_ads),
            ('Daily Videos', obj.max_daily_videos),
            ('Daily Tasks', obj.max_daily_tasks),
            ('Daily Surveys', obj.max_daily_surveys),
            ('Suspicious Threshold', f'{obj.currency_symbol}{obj.suspicious_activity_threshold}/hour'),
            ('Max Accounts/IP', obj.max_accounts_per_ip),
            ('Max Accounts/Device', obj.max_accounts_per_device),
        ]
        
        for label, value in limits:
            html += f'<tr><td style="padding: 5px;"><strong>{label}:</strong></td>'
            html += f'<td style="padding: 5px;">{value}</td></tr>'
        
        html += '</table>'
        return format_html(html)
    limits_summary.short_description = '[STATS] Limits & Thresholds'
    
    def quick_stats(self, obj):
        """Quick statistics"""
        html = '<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 10px 0;">'
        
        stats = [
            ('[MONEY] Min Withdrawal', f'{obj.currency_symbol}{obj.min_withdrawal_amount}'),
            ('💸 Max Withdrawal', f'{obj.currency_symbol}{obj.max_withdrawal_amount}'),
            ('[STAR] Point Value', f'{obj.currency_symbol}{obj.point_value}'),
            ('🎁 Welcome Bonus', f'{obj.welcome_bonus_points} pts'),
            ('👥 Referral Levels', obj.referral_levels),
            ('📱 Daily Ads Limit', obj.max_daily_ads),
            ('[SECURE] Max Login Attempts', obj.max_login_attempts),
            ('⏱️ Session Timeout', f'{obj.session_timeout_minutes} min'),
        ]
        
        for label, value in stats:
            html += f'<div style="background: #f8f9fa; padding: 10px; border-radius: 5px; text-align: center;">'
            html += f'<div style="color: #6c757d; font-size: 12px;">{label}</div>'
            html += f'<div style="font-size: 18px; font-weight: bold; margin-top: 5px;">{value}</div>'
            html += '</div>'
        
        html += '</div>'
        return format_html(html)
    quick_stats.short_description = '📈 Quick Stats'
    
    # ==================== Admin Actions ====================
    
    def enable_maintenance_mode(self, request, queryset):
        """Enable maintenance mode for selected settings"""
        queryset.update(
            maintenance_mode=True,
            maintenance_start=timezone.now()
        )
        self.message_user(request, '🚧 Maintenance mode enabled')
    enable_maintenance_mode.short_description = '🚧 Enable Maintenance Mode'
    
    def disable_maintenance_mode(self, request, queryset):
        """Disable maintenance mode"""
        queryset.update(
            maintenance_mode=False,
            maintenance_end=timezone.now()
        )
        self.message_user(request, '[OK] Maintenance mode disabled')
    disable_maintenance_mode.short_description = '[OK] Disable Maintenance Mode'
    
    def enable_all_security(self, request, queryset):
        """Enable all security features"""
        queryset.update(
            enable_2fa=True,
            enable_email_verification=True,
            enable_phone_verification=True,
            enable_withdrawal_pin=True,
            auto_ban_on_emulator=True,
            block_vpn_users=True,
            block_proxy_users=True,
            block_tor_users=True
        )
        self.message_user(request, '[SECURE] All security features enabled')
    enable_all_security.short_description = '[SECURE] Enable All Security Features'
    
    def reset_to_defaults(self, request, queryset):
        """Reset settings to safe defaults (confirmation required)"""
        # This would need a confirmation page in real implementation
        self.message_user(
            request,
            '[WARN] Please use admin interface to reset individual settings',
            level='warning'
        )
    reset_to_defaults.short_description = '[LOADING] Reset to Defaults (Use Carefully)'
    
    class Media:
        css = {
            'all': ('admin/css/system_settings.css',)  # Optional custom CSS
        }
        js = ('admin/js/system_settings.js',)  # Optional custom JS


class SiteNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'notification_type_display', 'is_active', 'show_on_login', 'priority', 'start_date', 'end_date']
    list_filter = ['notification_type', 'is_active', 'show_on_login']
    list_editable = ['is_active', 'show_on_login', 'priority']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('title', 'message', 'notification_type')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'show_on_login', 'priority')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date')
        }),
    )
    
    def notification_type_display(self, obj):
        """Color-coded notification type display"""
        colors = {
            'INFO': 'blue',
            'SUCCESS': 'green',
            'WARNING': 'orange',
            'ERROR': 'red',
            'MAINTENANCE': 'purple',
            'UPDATE': 'teal',
            'PROMOTION': 'pink',
        }
        color = colors.get(obj.notification_type, 'gray')
        return format_html(
            f'<span style="color: {color}; font-weight: bold;">{obj.get_notification_type_display()}</span>'
        )
    notification_type_display.short_description = 'Type'


class SiteContentAdmin(admin.ModelAdmin):
    list_display = ['identifier', 'title', 'content_type_display', 'language', 'is_active', 'order']
    list_filter = ['content_type', 'is_active', 'language']
    list_editable = ['is_active', 'order']
    search_fields = ['identifier', 'title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    prepopulated_fields = {"identifier": ("title",)}
    
    fieldsets = (
        ('Content Information', {
            'fields': ('identifier', 'title', 'content', 'content_type', 'language')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
        ('SEO Settings', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
    )
    
    def content_type_display(self, obj):
        """Styled content type display"""
        icons = {
            'PAGE': '[DOC]',
            'SECTION': '📋',
            'BANNER': '🖼️',
            'FOOTER': '⬇️',
            'SIDEBAR': '[STATS]',
            'POPUP': '💬',
        }
        icon = icons.get(obj.content_type, '[NOTE]')
        return f"{icon} {obj.get_content_type_display()}"
    content_type_display.short_description = 'Type'

  
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'report_type', 'status', 'start_date', 'end_date', 'generated_at']
    list_filter = ['report_type', 'created_at']
    list_editable = ['status']
    readonly_fields = ['report_id', 'generated_at']
    search_fields = ['title', 'description']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('title', 'description', 'report_type', 'status')
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date')
        }),
        ('Report Data', {
            'fields': ('report_data', 'generated_by', 'generated_at'),
            'classes': ('collapse',)
        }),
        ('File Information', {
            'fields': ('report_file', 'file_format', 'file_size'),
            'classes': ('collapse',)
        }),
    )

# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ['user', 'phone_number', 'total_points', 'total_earnings', 'account_status']
#     list_filter = ['account_status', 'email_verified', 'phone_verified']
#     search_fields = ['user__username', 'user__email', 'phone_number', 'profile_id']
#     readonly_fields = ['profile_id', 'referral_code', 'created_at', 'updated_at']
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('user', 'profile_id', 'profile_picture', 'bio')
#         }),
#         ('Contact Information', {
#             'fields': ('phone_number', 'email_verified', 'phone_verified')
#         }),
#         ('Personal Details', {
#             'fields': ('date_of_birth', 'gender', 'nid_number', 'identity_verified')
#         }),
#         ('Location Information', {
#             'fields': ('address', 'city', 'state', 'postal_code', 'country')
#         }),
#         ('Earning Information', {
#             'fields': ('total_points', 'total_earnings', 'total_withdrawn')
#         }),
#         ('Referral System', {
#             'fields': ('referral_code', 'referred_by')
#         }),
#         ('Account Settings', {
#             'fields': ('account_status', 'is_premium', 'is_affiliate', 'email_notifications')
#         }),
#         ('Timestamps', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )
    
    


# AdminActionAdmin ক্লাস
class AdminActionAdmin(admin.ModelAdmin):
    list_display = ['admin', 'action_type_display', 'target_user', 'ip_address', 'created_at']
    list_filter = ['action_type', 'created_at', 'admin']
    search_fields = ['admin__username', 'description', 'target_user__username', 'ip_address']
    readonly_fields = ['created_at', 'updated_at', 'action_details']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Action Details', {
            'fields': ('admin', 'action_type', 'description', 'ip_address', 'action_details')
        }),
        ('Target Information', {
            'fields': ('target_user',)
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def action_type_display(self, obj):
        """Color-coded action type display"""
        colors = {
            'user_ban': 'red',
            'user_unban': 'green',
            'payment_approve': 'blue',
            'payment_reject': 'orange',
            'content_delete': 'purple',
            'setting_change': 'teal',
        }
        color = colors.get(obj.action_type, 'gray')
        return format_html(
            f'<span style="color: {color}; font-weight: bold;">{obj.get_action_type_display()}</span>'
        )
    action_type_display.short_description = 'Action Type'
    
    def action_details(self, obj):
        """Display action details"""
        details = []
        if obj.target_user:
            details.append(f"Target User: {obj.target_user.username} (ID: {obj.target_user.id})")
        if obj.metadata:
            import json
            details.append(f"Metadata: {json.dumps(obj.metadata, indent=2)}")
        if obj.ip_address:
            details.append(f"IP Address: {obj.ip_address}")
        
        return format_html("<br>".join(details)) if details else "No additional details"
    action_details.short_description = 'Details'

    


# ==================== REGISTER OTHER MODELS ====================

# Register wallet models if available
if WALLET_AVAILABLE:
    class WalletAdmin(ModelAdmin):
        list_display = ['user', 'balance', 'currency', 'created_at']
        search_fields = ['user__username', 'user__email']
    
    class TransactionAdmin(ModelAdmin):
        list_display = ['user', 'amount', 'transaction_type', 'status', 'created_at']
        list_filter = ['transaction_type',  'created_at']
        search_fields = ['user__username', 'description']
    
    class WithdrawalRequestAdmin(ModelAdmin):
        list_display = ['user', 'amount', 'payment_method', 'status', 'created_at']
        list_filter = ['payment_method', 'created_at']
        list_editable = ['status']
        search_fields = ['user__username', 'transaction_id']
    
    safe_register(Wallet, WalletAdmin, "Wallets")
    safe_register(Transaction, TransactionAdmin, "Transactions")
    safe_register(WithdrawalRequest, WithdrawalRequestAdmin, "Withdrawal Requests")

# Register referral models if available
if REFERRAL_AVAILABLE:
    class ReferralAdmin(ModelAdmin):
        list_display = ['referrer', 'referred_user', 'created_at']
        list_filter = [ 'created_at']
        search_fields = ['referrer__username', 'referred_user__username']
    
    safe_register(Referral, ReferralAdmin, "Referrals")

# Register notification models if available
# if NOTIFICATIONS_AVAILABLE:
#     class NotificationAdmin(ModelAdmin):
#         list_display = ['user', 'title', 'notification_type', 'is_read', 'created_at']
#         list_filter = ['notification_type', 'is_read', 'created_at']
#         list_editable = ['is_read']
#         search_fields = ['user__username', 'title', 'message']
    
#     safe_register(Notification, NotificationAdmin, "Notifications")

# Register offer models if available
if OFFERS_AVAILABLE:
    class OfferAdmin(ModelAdmin):
        list_display = ['name', 'offer_type', 'reward_amount', 'status', 'created_at']
        list_filter = ['offer_type',  'created_at']
        list_editable = ['status']
        search_fields = ['name', 'description']
    
    class UserOfferAdmin(ModelAdmin):
        list_display = ['user', 'offer', 'status', 'completed_at', 'reward_earned']
        list_filter = ['completed_at']
        search_fields = ['user__username', 'offer__name']
    
    safe_register(Offer, OfferAdmin, "Offers")
    safe_register(UserOffer, UserOfferAdmin, "User Offers")

# ==================== SET DEFAULT ADMIN SITE ====================

# Override default admin site
admin.site = admin_site

# Helper function to get admin site
def get_admin_site():
    return admin_site


# ==================== FINAL EXPORTS ====================

__all__ = ['admin_site', 'ModernAdminSite', 'get_admin_site', 'safe_register']

# Register models
admin.site.register(SiteNotification, SiteNotificationAdmin)
admin.site.register(SiteContent, SiteContentAdmin)
admin.site.register(AdminAction, AdminActionAdmin)


    # Register system models
safe_register(SystemSettings, SystemSettingsAdmin, "System Settings")
# safe_register(AdminAction, AdminActionAdmin, "Admin Actions")
safe_register(Report, ReportAdmin, "System Reports")
safe_register(UserProfile, UserProfileAdmin, "User Profiles")



