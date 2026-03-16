# api/cache/admin.py
"""
Beautiful Cache Admin - Colorful badges & dashboard
"""
from django.contrib import admin
from django.utils.html import format_html, escape
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponseRedirect


# ==================== BADGE HELPERS ====================

def badge(text, color, icon=''):
    """Generic colorful badge"""
    try:
        return format_html(
            '<span style="background: {}; color: white; padding: 5px 12px; '
            'border-radius: 16px; font-size: 11px; font-weight: 600; '
            'box-shadow: 0 2px 6px rgba(0,0,0,0.15); display: inline-block;">'
            '{} {}</span>',
            color, icon, escape(str(text))
        )
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def gradient_badge(text, c1, c2, icon=''):
    """Gradient badge"""
    try:
        return format_html(
            '<span style="background: linear-gradient(135deg, {}, {}); color: white; '
            'padding: 6px 14px; border-radius: 18px; font-size: 12px; font-weight: 600; '
            'box-shadow: 0 2px 8px rgba(0,0,0,0.2); display: inline-block;">'
            '{} {}</span>',
            c1, c2, icon, escape(str(text))
        )
    except Exception:
        return format_html('<span style="color:#999;">-</span>')


def status_badge(value, true_text='Active', false_text='Inactive'):
    """Status badge - green/red"""
    if value:
        return gradient_badge(true_text, '#22c55e', '#16a34a', '✓')
    return gradient_badge(false_text, '#ef4444', '#dc2626', '✗')


def stat_card(title, value, color='#6366f1', icon='📊'):
    """Stat card HTML for dashboard"""
    return format_html(
        '<div style="background: linear-gradient(135deg, {}, #818cf8); color: white; '
        'padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); '
        'margin: 8px 0; min-width: 140px;">'
        '<div style="font-size: 11px; opacity: 0.9; margin-bottom: 4px;">{}</div>'
        '<div style="font-size: 24px; font-weight: 700;">{} {}</div></div>',
        color, escape(title), icon, escape(str(value))
    )


# ==================== CACHE ADMIN SITE ====================

class CacheAdminSite(admin.AdminSite):
    """Custom Cache Admin with dashboard"""
    site_title = '⚡ Cache Dashboard'
    site_header = '⚡ Earnify Cache System'
    index_title = 'Cache Management'


cache_admin_site = CacheAdminSite(name='cache_admin')


# ==================== EXPORTS ====================
__all__ = ['badge', 'gradient_badge', 'status_badge', 'stat_card', 'cache_admin_site']
