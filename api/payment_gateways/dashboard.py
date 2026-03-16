from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import path, include
from django.db.models import Count, Sum, Avg, Q, F, Func, Value, Window
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, Coalesce
from django.utils import timezone
from django.http import JsonResponse
from django.core.cache import cache
import json
from datetime import datetime, timedelta
import decimal

from .models import (
    OfferProvider, OfferCategory, Offer, 
    OfferClick, OfferConversion, OfferWall
)


def get_color_for_score(score):
    """Get color based on score"""
    if score >= 80:
        return '#10b981'  # Green
    elif score >= 60:
        return '#f59e0b'  # Yellow
    elif score >= 40:
        return '#f97316'  # Orange
    else:
        return '#ef4444'  # Red


def calculate_eCPM(offer):
    """Calculate eCPM for an offer"""
    if offer.click_count == 0:
        return 0
    revenue = offer.total_revenue or 0
    return (revenue / offer.click_count) * 1000


def calculate_conversion_funnel():
    """Calculate conversion funnel data"""
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=7)
    
    clicks = OfferClick.objects.filter(
        clicked_at__date__gte=seven_days_ago
    ).count()
    
    conversions = OfferConversion.objects.filter(
        converted_at__date__gte=seven_days_ago
    ).count()
    
    # Assuming we have user registration tracking
    registrations = OfferClick.objects.filter(
        clicked_at__date__gte=seven_days_ago,
        user__isnull=False
    ).count()
    
    return {
        'clicks': clicks,
        'registrations': registrations,
        'conversions': conversions
    }


@staff_member_required
def admin_dashboard(request):
    """
    Main admin dashboard with charts and analytics
    """
    # Date ranges
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=7)
    thirty_days_ago = today - timedelta(days=30)
    
    # Performance metrics
    total_offers = Offer.objects.count()
    active_offers = Offer.objects.filter(status='active').count()
    total_conversions = OfferConversion.objects.count()
    pending_conversions = OfferConversion.objects.filter(status='pending').count()
    
    # Revenue calculations
    revenue_data = OfferConversion.objects.filter(
        status='approved'
    ).aggregate(
        total_revenue=Sum('payout_amount'),
        total_payout=Sum('reward_amount')
    )
    
    total_revenue = revenue_data['total_revenue'] or 0
    total_payout = revenue_data['total_payout'] or 0
    
    # Calculate profit
    profit = total_revenue - total_payout
    
    # Get top performing offers by eCPM
    top_offers = Offer.objects.annotate(
        conversion_count=Count('offerconversion'),
        total_revenue=Sum('offerconversion__payout_amount'),
        eCPM=(Sum('offerconversion__payout_amount') / F('click_count') * 1000)
    ).filter(
        click_count__gt=0,
        conversion_count__gt=0
    ).order_by('-eCPM')[:10]
    
    # Get recent conversions
    recent_conversions = OfferConversion.objects.select_related(
        'user', 'offer'
    ).order_by('-converted_at')[:10]
    
    # Fraud detection metrics
    suspicious_conversions = OfferConversion.objects.filter(
        Q(status='rejected') | Q(status='pending')
    ).count()
    
    # Smart Sort metrics
    smart_sort_data = Offer.objects.annotate(
        completion_rate=(Count('offerconversion') * 100.0 / F('click_count'))
    ).filter(
        click_count__gt=10
    ).order_by('-completion_rate')[:5]
    
    context = {
        'total_offers': total_offers,
        'active_offers': active_offers,
        'total_conversions': total_conversions,
        'pending_conversions': pending_conversions,
        'total_revenue': total_revenue,
        'total_payout': total_payout,
        'profit': profit,
        'top_offers': top_offers,
        'recent_conversions': recent_conversions,
        'suspicious_conversions': suspicious_conversions,
        'smart_sort_data': smart_sort_data,
        'today': today,
    }
    
    return render(request, 'admin/offerwall/dashboard.html', context)


@staff_member_required
def dashboard_charts_data(request):
    """
    API endpoint for chart data
    """
    chart_type = request.GET.get('chart', 'revenue')
    period = request.GET.get('period', '7d')
    
    # Calculate date range
    today = timezone.now().date()
    if period == '7d':
        days = 7
        start_date = today - timedelta(days=days)
        trunc_func = TruncDay
        label_format = '%b %d'
    elif period == '30d':
        days = 30
        start_date = today - timedelta(days=days)
        trunc_func = TruncDay
        label_format = '%b %d'
    else:  # 3m
        days = 90
        start_date = today - timedelta(days=days)
        trunc_func = TruncWeek
        label_format = 'Week %U'
    
    if chart_type == 'revenue':
        # Revenue and Payout chart
        conversions = OfferConversion.objects.filter(
            converted_at__date__gte=start_date,
            status='approved'
        ).annotate(
            date=trunc_func('converted_at')
        ).values('date').annotate(
            revenue=Sum('payout_amount'),
            payout=Sum('reward_amount')
        ).order_by('date')
        
        labels = []
        revenue_data = []
        payout_data = []
        
        for item in conversions:
            labels.append(item['date'].strftime(label_format))
            revenue_data.append(float(item['revenue'] or 0))
            payout_data.append(float(item['payout'] or 0))
        
        data = {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Revenue ($)',
                    'data': revenue_data,
                    'borderColor': '#10b981',
                    'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                    'tension': 0.4
                },
                {
                    'label': 'Payout ($)',
                    'data': payout_data,
                    'borderColor': '#3b82f6',
                    'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                    'tension': 0.4
                }
            ]
        }
    
    elif chart_type == 'conversion':
        # Conversion funnel chart
        funnel = calculate_conversion_funnel()
        
        data = {
            'labels': ['Clicks', 'Registrations', 'Conversions'],
            'datasets': [{
                'label': 'Conversion Funnel',
                'data': [funnel['clicks'], funnel['registrations'], funnel['conversions']],
                'backgroundColor': [
                    'rgba(59, 130, 246, 0.8)',
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(139, 92, 246, 0.8)'
                ],
                'borderColor': [
                    '#3b82f6',
                    '#10b981',
                    '#8b5cf6'
                ],
                'borderWidth': 1
            }]
        }
    
    elif chart_type == 'country':
        # Country distribution chart
        countries = OfferConversion.objects.filter(
            converted_at__date__gte=start_date,
            status='approved'
        ).values('click__country').annotate(
            count=Count('id'),
            revenue=Sum('payout_amount')
        ).order_by('-revenue')[:10]
        
        labels = []
        country_data = []
        colors = []
        
        color_palette = [
            '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
            '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1'
        ]
        
        for i, country in enumerate(countries):
            labels.append(country['click__country'] or 'Unknown')
            country_data.append(float(country['revenue'] or 0))
            colors.append(color_palette[i % len(color_palette)])
        
        data = {
            'labels': labels,
            'datasets': [{
                'label': 'Revenue by Country ($)',
                'data': country_data,
                'backgroundColor': colors,
                'borderColor': colors,
                'borderWidth': 1
            }]
        }
    
    elif chart_type == 'performance':
        # Offer performance by eCPM
        offers = Offer.objects.annotate(
            conversion_count=Count('offerconversion'),
            total_revenue=Sum('offerconversion__payout_amount'),
            eCPM=(Sum('offerconversion__payout_amount') / F('click_count') * 1000)
        ).filter(
            click_count__gt=0,
            conversion_count__gt=0,
            updated_at__date__gte=start_date
        ).order_by('-eCPM')[:15]
        
        labels = []
        ecpm_data = []
        conv_rate_data = []
        
        for offer in offers:
            labels.append(offer.title[:20] + '...' if len(offer.title) > 20 else offer.title)
            ecpm_data.append(float(offer.eCPM or 0))
            conv_rate_data.append(float(offer.completion_rate or 0))
        
        data = {
            'labels': labels,
            'datasets': [
                {
                    'label': 'eCPM ($)',
                    'data': ecpm_data,
                    'backgroundColor': 'rgba(59, 130, 246, 0.8)',
                    'borderColor': '#3b82f6',
                    'borderWidth': 1,
                    'type': 'bar'
                },
                {
                    'label': 'Conversion Rate (%)',
                    'data': conv_rate_data,
                    'borderColor': '#10b981',
                    'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                    'tension': 0.4,
                    'type': 'line'
                }
            ]
        }
    
    return JsonResponse(data, safe=False)


@staff_member_required
def fraud_analytics_data(request):
    """
    API endpoint for fraud analytics
    """
    today = timezone.now().date()
    seven_days_ago = today - timedelta(days=7)
    
    # Fraud metrics
    total_conversions = OfferConversion.objects.filter(
        converted_at__date__gte=seven_days_ago
    ).count()
    
    rejected_conversions = OfferConversion.objects.filter(
        converted_at__date__gte=seven_days_ago,
        status='rejected'
    ).count()
    
    pending_conversions = OfferConversion.objects.filter(
        converted_at__date__gte=seven_days_ago,
        status='pending'
    ).count()
    
    # Time-to-complete analysis
    fast_conversions = OfferConversion.objects.filter(
        converted_at__date__gte=seven_days_ago,
        offer__estimated_time_minutes__gt=0
    ).annotate(
        time_ratio=F('time_to_complete_seconds') / (F('offer__estimated_time_minutes') * 60)
    ).filter(
        time_ratio__lt=0.1  # Completed in less than 10% of estimated time
    ).count()
    
    # Device analysis
    duplicate_devices = OfferClick.objects.filter(
        clicked_at__date__gte=seven_days_ago
    ).values('device_id').annotate(
        count=Count('id')
    ).filter(
        count__gt=3
    ).count()
    
    data = {
        'total_conversions': total_conversions,
        'rejected_conversions': rejected_conversions,
        'pending_conversions': pending_conversions,
        'fast_conversions': fast_conversions,
        'duplicate_devices': duplicate_devices,
        'fraud_rate': (rejected_conversions / total_conversions * 100) if total_conversions > 0 else 0
    }
    
    return JsonResponse(data)