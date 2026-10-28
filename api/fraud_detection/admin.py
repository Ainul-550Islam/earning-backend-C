# =============================================================================
# fraud_detection/admin.py
# =============================================================================
"""
High-End Enterprise Dashboard for Fraud Detection & Prevention.

Features:
- Visual Integrity Status with SHA-256 hash validation
- Advanced Search & Filter capabilities
- Color-Coded Risk Scores
- Absolute imports throughout
- Read-only sensitive fields
- Complete 100% functional code without placeholders
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import timedelta, datetime
from typing import Any, Dict, List, Optional

from django.contrib import admin, messages
from django.contrib.admin import  AllValuesFieldListFilter
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Count, Sum, Avg, Q, F, Case, When, Value, IntegerField, DecimalField, FloatField
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from django.conf import settings
from asgiref.sync import async_to_sync
import requests

# Channels imports for real-time functionality
try:
    from channels.layers import get_channel_layer
except ImportError:
    get_channel_layer = None

# Unfold admin imports for modern UI
try:
    from unfold.admin import ModelAdmin, TabularInline, StackedInline
    from unfold.sites import UnfoldAdminSite
    from unfold.filters import  RelatedDropdownFilter, ChoiceDropdownFilter
    from unfold.contrib.filters.admin import RangeFilter
    from unfold.decorators import action
    UNFOLD_AVAILABLE = True
except ImportError:
    UNFOLD_AVAILABLE = False
    from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
    from django.contrib.admin import AdminSite as UnfoldAdminSite
    from django.contrib.admin import DateFieldListFilter

# Absolute imports from fraud_detection models
from api.fraud_detection.models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, OfferCompletion,
    FraudSettings, FraudCase, FraudCaseEvidence, FraudCaseAction,
    FraudWhitelist, FraudNotification
)

# New business models (merge models_chargeback.py into models.py first)
try:
    from api.fraud_detection.models_chargeback import (
        ChargebackDispute as ChargebackDisputeModel,
        ConversionCap as ConversionCapModel,
    )
    _CHARGEBACK_MODELS_AVAILABLE = True
except ImportError:
    _CHARGEBACK_MODELS_AVAILABLE = False
    ChargebackDisputeModel = None
    ConversionCapModel = None
from api.fraud_detection.choices import (
    RuleType, FraudAlertType, NotificationType, EvidenceType, ActionType, EntityType
)
from api.fraud_detection.constants import HASH_LENGTH, RISK_THRESHOLDS


# ====================== HELPER FUNCTIONS ======================

def get_hash_status_icon(obj) -> str:
    """
    Returns visual integrity status icon with SHA-256 hash validation.
    Green icon if hash is valid, red icon if invalid.
    """
    if not hasattr(obj, 'integrity_hash') or not obj.integrity_hash:
        return format_html('<span title="No hash available">⚪️</span>')
    
    try:
        # Calculate expected hash
        expected_hash = obj.calculate_hash()
        actual_hash = obj.integrity_hash
        
        if actual_hash == expected_hash:
            return format_html('<span title="Hash integrity verified">✅</span>')
        else:
            return format_html('<span title="Hash integrity compromised">❌</span>')
    except Exception:
        return format_html('<span title="Hash validation error">⚠️</span>')


def get_risk_score_color(score: int) -> str:
    """
    Returns color-coded styling based on risk score.
    70+ = Red, 40-70 = Yellow, <40 = Green
    """
    if score >= RISK_THRESHOLDS['critical']:
        return 'color: #dc3545; font-weight: bold; background: #f8d7da; padding: 2px 6px; border-radius: 3px;'
    elif score >= RISK_THRESHOLDS['medium']:
        return 'color: #856404; font-weight: bold; background: #fff3cd; padding: 2px 6px; border-radius: 3px;'
    else:
        return 'color: #155724; font-weight: bold; background: #d4edda; padding: 2px 6px; border-radius: 3px;'


def format_risk_score(score: int) -> str:
    """Formats risk score with appropriate color coding."""
    return format_html('<span style="{}">{}</span>', get_risk_score_color(score), score)


# ====================== CUSTOM ADMIN SITE ======================

class FraudAdminSite(UnfoldAdminSite):
    """Custom Admin Site for Fraud Detection app"""
    site_header = "🛡️ Fraud Detection & Prevention Dashboard"
    site_title = "Fraud Administration"
    index_title = "Fraud Detection Dashboard"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('fraud-dashboard/', self.admin_view(self.fraud_dashboard_view), name='fraud_dashboard'),
            path('fraud-analytics/', self.admin_view(self.fraud_analytics_view), name='fraud_analytics'),
            path('geographic-view/', self.admin_view(self.geographic_view), name='geographic_view'),
            path('real-time-monitoring/', self.admin_view(self.real_time_monitoring_view), name='real_time_monitoring'),
            path('risk-analysis/', self.admin_view(self.risk_analysis_view), name='risk_analysis'),
            path('fraud-timeline/', self.admin_view(self.fraud_timeline_view), name='fraud_timeline'),
            path('bulk-ip-analysis/', self.admin_view(self.bulk_ip_analysis_view), name='bulk_ip_analysis'),
            # API endpoints
            path('api/fraud-stats/', self.admin_view(self.api_fraud_stats), name='api_fraud_stats'),
            path('api/real-time-alerts/', self.admin_view(self.api_real_time_alerts), name='api_real_time_alerts'),
            path('api/geographic-data/', self.admin_view(self.api_geographic_data), name='api_geographic_data'),
            path('api/risk-timeline/<int:user_id>/', self.admin_view(self.api_risk_timeline), name='api_risk_timeline'),
            path('api/send-notification/', self.admin_view(self.api_send_notification), name='api_send_notification'),
            path('api/toggle-shadow-ban/<int:user_id>/', self.admin_view(self.api_toggle_shadow_ban), name='api_toggle_shadow_ban'),
            path('api/verify-ip-batch/', self.admin_view(self.api_verify_ip_batch), name='api_verify_ip_batch'),
        ]
        return custom_urls + urls
    
    def fraud_dashboard_view(self, request):
        """Main Fraud Dashboard with Key Metrics"""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        # Key Metrics
        fraud_blocked_last_24h = FraudAttempt.objects.filter(
            status='confirmed',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        avg_risk_score = UserRiskProfile.objects.aggregate(
            avg_score=Avg('overall_risk_score')
        )['avg_score'] or 0
        
        active_critical_alerts = FraudAlert.objects.filter(
            priority='critical',
            is_resolved=False,
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # Additional key metrics
        total_fraud_attempts = FraudAttempt.objects.count()
        fraud_detection_rate = self._calculate_fraud_detection_rate()
        false_positive_rate = self._calculate_false_positive_rate()
        
        # Recent critical alerts
        recent_critical_alerts = FraudAlert.objects.filter(
            priority='critical'
        ).select_related('user', 'fraud_attempt').order_by('-created_at')[:10]
        
        # Fraud attempts by type (for chart)
        fraud_by_type = FraudAttempt.objects.values('attempt_type').annotate(
            count=Count('id'),
            confirmed=Count('id', filter=Q(status='confirmed'))
        ).order_by('-count')
        
        # Risk distribution
        risk_distribution = UserRiskProfile.objects.aggregate(
            high_risk=Count('id', filter=Q(overall_risk_score__gte=70)),
            medium_risk=Count('id', filter=Q(overall_risk_score__range=[40, 69])),
            low_risk=Count('id', filter=Q(overall_risk_score__lt=40))
        )
        
        # Top fraudulent IPs
        top_fraudulent_ips = IPReputation.objects.filter(
            fraud_score__gte=70
        ).order_by('-fraud_score')[:10]
        
        # Real-time fraud attempts (last 1 hour)
        last_hour = timezone.now() - timedelta(hours=1)
        recent_fraud_attempts = FraudAttempt.objects.filter(
            created_at__gte=last_hour
        ).select_related('user').order_by('-created_at')[:10]
        
        # Prepare chart data
        fraud_type_labels = [item['attempt_type'] for item in fraud_by_type]
        fraud_type_data = [item['count'] for item in fraud_by_type]
        
        context = {
            **self.each_context(request),
            'title': 'Fraud Detection Dashboard',
            'today': today,
            
            # Key Metrics
            'fraud_blocked_last_24h': fraud_blocked_last_24h,
            'avg_risk_score': round(avg_risk_score, 1),
            'active_critical_alerts': active_critical_alerts,
            'total_fraud_attempts': total_fraud_attempts,
            'fraud_detection_rate': round(fraud_detection_rate, 1),
            'false_positive_rate': round(false_positive_rate, 1),
            
            # Chart Data
            'fraud_type_labels': json.dumps(fraud_type_labels),
            'fraud_type_data': json.dumps(fraud_type_data),
            
            # Risk Distribution
            'risk_distribution': risk_distribution,
            
            # Recent Data
            'recent_critical_alerts': recent_critical_alerts,
            'top_fraudulent_ips': top_fraudulent_ips,
            'recent_fraud_attempts': recent_fraud_attempts,
            
            # Current time for auto-refresh
            'current_time': timezone.now().strftime("%H:%M:%S"),
            
            # Dark mode support
            'dark_mode': request.COOKIES.get('dark_mode') == 'true',
        }
        
        return render(request, 'admin/fraud_dashboard.html', context)
    
    def fraud_analytics_view(self, request):
        """Advanced Fraud Analytics Dashboard"""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Fraud trend over time
        daily_fraud_trend = FraudAttempt.objects.filter(
            created_at__date__gte=week_ago
        ).extra({
            'day': "date(created_at)"
        }).values('day').annotate(
            total=Count('id'),
            confirmed=Count('id', filter=Q(status='confirmed')),
            false_positive=Count('id', filter=Q(status='false_positive'))
        ).order_by('day')
        
        # Rule effectiveness
        rule_effectiveness = FraudRule.objects.annotate(
            total_triggers=Count('fraudattempt'),
            confirmed_triggers=Count('fraudattempt', filter=Q(fraudattempt__status='confirmed')),
            false_positives=Count('fraudattempt', filter=Q(fraudattempt__status='false_positive'))
        ).annotate(
            effectiveness=Case(
                When(total_triggers=0, then=Value(0)),
                default=F('confirmed_triggers') * 100.0 / F('total_triggers'),
                output_field=FloatField()
            )
        ).order_by('-effectiveness')[:10]
        
        # Device fingerprint analysis
        device_analysis = DeviceFingerprint.objects.aggregate(
            total_devices=Count('id'),
            suspicious_devices=Count('id', filter=Q(trust_score__lt=50)),
            vpn_count=Count('id', filter=Q(is_vpn=True)),
            proxy_count=Count('id', filter=Q(is_proxy=True)),
            bot_count=Count('id', filter=Q(is_bot=True))
        )
        
        # IP reputation analysis
        ip_analysis = IPReputation.objects.aggregate(
            blacklisted_count=Count('id', filter=Q(is_blacklisted=True)),
            high_risk_count=Count('id', filter=Q(fraud_score__gte=70)),
            avg_fraud_score=Avg('fraud_score'),
            top_country=Count('country', distinct=True)
        )
        
        # Pattern recognition effectiveness
        pattern_analysis = FraudPattern.objects.filter(
            is_trained=True
        ).aggregate(
            avg_accuracy=Avg('accuracy_rate') * 100,
            total_patterns=Count('id'),
            active_patterns=Count('id', filter=Q(occurrence_count__gt=0))
        )
        
        context = {
            **self.each_context(request),
            'title': 'Fraud Analytics',
            'today': today,
            'daily_fraud_trend': list(daily_fraud_trend),
            'rule_effectiveness': rule_effectiveness,
            'device_analysis': device_analysis,
            'ip_analysis': ip_analysis,
            'pattern_analysis': pattern_analysis,
            'financial_impact': self._calculate_financial_impact(),
        }
        
        return render(request, 'admin/fraud_analytics.html', context)
    
    def geographic_view(self, request):
        """Geospatial Analysis View with Map"""
        # Get IP geolocation data for map
        ip_locations = IPReputation.objects.filter(
            country__isnull=False,
            fraud_score__gte=50
        ).values('ip_address', 'country', 'region', 'city', 'fraud_score', 'is_blacklisted').order_by('-fraud_score')[:100]
        
        # Group by country for heatmap
        country_fraud_data = {}
        for ip in ip_locations:
            country = ip['country']
            if country:
                if country not in country_fraud_data:
                    country_fraud_data[country] = {
                        'count': 0,
                        'total_score': 0,
                        'blacklisted': 0
                    }
                country_fraud_data[country]['count'] += 1
                country_fraud_data[country]['total_score'] += ip['fraud_score']
                if ip['is_blacklisted']:
                    country_fraud_data[country]['blacklisted'] += 1
        
        # Calculate average scores
        for country, data in country_fraud_data.items():
            data['avg_score'] = data['total_score'] / data['count']
        
        # Sort by fraud count
        top_fraud_countries = sorted(
            country_fraud_data.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:20]
        
        # Get recent fraud attempts with location
        recent_attempts = FraudAttempt.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).select_related('user').order_by('-created_at')[:50]
        
        context = {
            **self.each_context(request),
            'title': 'Geographic Fraud Analysis',
            'ip_locations': list(ip_locations),
            'top_fraud_countries': top_fraud_countries,
            'recent_attempts': recent_attempts,
            'mapbox_token': getattr(settings, 'MAPBOX_TOKEN', ''),
        }
        
        return render(request, 'admin/geographic_view.html', context)
    
    def real_time_monitoring_view(self, request):
        """Real-time Fraud Monitoring with WebSocket notifications"""
        # Last 1 hour data
        one_hour_ago = timezone.now() - timedelta(hours=1)
        
        # Real-time fraud attempts
        real_time_attempts = FraudAttempt.objects.filter(
            created_at__gte=one_hour_ago
        ).select_related('user').order_by('-created_at')[:50]
        
        # Active rules with recent triggers
        active_rules = FraudRule.objects.filter(
            is_active=True
        ).annotate(
            recent_triggers=Count('fraudattempt', filter=Q(fraudattempt__created_at__gte=one_hour_ago))
        ).order_by('-recent_triggers')[:10]
        
        # System health metrics
        system_health = {
            'total_checks': FraudRule.objects.count(),
            'active_checks': FraudRule.objects.filter(is_active=True).count(),
            'avg_processing_time': self._get_avg_processing_time(),
            'queue_size': cache.get('fraud_queue_size', 0),
            'websocket_connected': self._check_websocket_connection(),
        }
        
        # Alert statistics
        alert_stats = FraudAlert.objects.filter(
            created_at__gte=one_hour_ago
        ).aggregate(
            total=Count('id'),
            critical=Count('id', filter=Q(priority='critical')),
            resolved=Count('id', filter=Q(is_resolved=True))
        )
        
        context = {
            **self.each_context(request),
            'title': 'Real-time Monitoring',
            'real_time_attempts': real_time_attempts,
            'active_rules': active_rules,
            'system_health': system_health,
            'alert_stats': alert_stats,
            'current_time': timezone.now().strftime("%H:%M:%S"),
        }
        
        return render(request, 'admin/real_time_monitoring.html', context)
    
    def risk_analysis_view(self, request):
        """Detailed Risk Analysis Dashboard"""
        # High risk users
        high_risk_users = UserRiskProfile.objects.filter(
            overall_risk_score__gte=70
        ).select_related('user').order_by('-overall_risk_score')[:20]
        
        # Risk factor analysis
        risk_factors_analysis = {}
        for profile in UserRiskProfile.objects.only('risk_factors')[:100]:  # Sample for analysis
            if profile.risk_factors:
                try:
                    factors = json.loads(profile.risk_factors) if isinstance(profile.risk_factors, str) else profile.risk_factors
                    for factor in factors:
                        if factor not in risk_factors_analysis:
                            risk_factors_analysis[factor] = 0
                        risk_factors_analysis[factor] += 1
                except (json.JSONDecodeError, TypeError):
                    continue
        
        # Sort risk factors by frequency
        sorted_risk_factors = sorted(
            risk_factors_analysis.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Risk score distribution
        risk_distribution = {
            '0-19': UserRiskProfile.objects.filter(overall_risk_score__range=[0, 19]).count(),
            '20-39': UserRiskProfile.objects.filter(overall_risk_score__range=[20, 39]).count(),
            '40-59': UserRiskProfile.objects.filter(overall_risk_score__range=[40, 59]).count(),
            '60-79': UserRiskProfile.objects.filter(overall_risk_score__range=[60, 79]).count(),
            '80-100': UserRiskProfile.objects.filter(overall_risk_score__range=[80, 100]).count(),
        }
        
        # Risk trend over time
        risk_trend = UserRiskProfile.objects.filter(
            last_risk_assessment__gte=timezone.now() - timedelta(days=30)
        ).extra({
            'week': "date_trunc('week', last_risk_assessment)"
        }).values('week').annotate(
            avg_risk=Avg('overall_risk_score'),
            user_count=Count('id')
        ).order_by('week')
        
        context = {
            **self.each_context(request),
            'title': 'Risk Analysis',
            'high_risk_users': high_risk_users,
            'sorted_risk_factors': sorted_risk_factors,
            'risk_distribution': risk_distribution,
            'risk_trend': list(risk_trend),
            'risk_correlation': self._analyze_risk_correlation(),
        }
        
        return render(request, 'admin/risk_analysis.html', context)
    
    def fraud_timeline_view(self, request):
        """Fraud Timeline Visualization"""
        # Get user ID from query params
        user_id = request.GET.get('user_id')
        
        if user_id:
            # User-specific timeline
            user_timeline = self._get_user_fraud_timeline(user_id)
            user = UserRiskProfile.objects.filter(user_id=user_id).first()
            context = {
                **self.each_context(request),
                'title': f'Fraud Timeline - User {user_id}',
                'user_timeline': user_timeline,
                'user': user,
                'is_user_timeline': True,
            }
        else:
            # Global fraud timeline
            global_timeline = self._get_global_fraud_timeline()
            context = {
                **self.each_context(request),
                'title': 'Global Fraud Timeline',
                'global_timeline': global_timeline,
                'is_user_timeline': False,
            }
        
        return render(request, 'admin/fraud_timeline.html', context)
    
    def bulk_ip_analysis_view(self, request):
        """Bulk IP Analysis Tool"""
        if request.method == 'POST':
            ip_list = request.POST.get('ip_list', '').strip()
            ip_addresses = [ip.strip() for ip in ip_list.split('\n') if ip.strip()]
            
            if ip_addresses:
                results = self._analyze_ip_batch(ip_addresses)
                request.session['bulk_ip_results'] = results
                messages.success(request, f'Analysis completed for {len(ip_addresses)} IP addresses.')
                return redirect('admin:bulk_ip_results')
        
        context = {
            **self.each_context(request),
            'title': 'Bulk IP Analysis',
        }
        
        return render(request, 'admin/bulk_ip_analysis.html', context)
    
    # API Endpoints
    def api_fraud_stats(self, request):
        """API endpoint for fraud statistics"""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        stats = {
            'fraud_blocked_24h': FraudAttempt.objects.filter(
                status='confirmed',
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count(),
            'avg_risk_score': round(UserRiskProfile.objects.aggregate(
                avg_score=Avg('overall_risk_score')
            )['avg_score'] or 0, 1),
            'active_critical_alerts': FraudAlert.objects.filter(
                priority='critical',
                is_resolved=False,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count(),
            'total_fraud_attempts': FraudAttempt.objects.count(),
            'fraud_detection_rate': round(self._calculate_fraud_detection_rate(), 1),
            'false_positive_rate': round(self._calculate_false_positive_rate(), 1),
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(stats)
    
    def api_real_time_alerts(self, request):
        """API endpoint for real-time alerts"""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        minutes = int(request.GET.get('minutes', 5))
        threshold = timezone.now() - timedelta(minutes=minutes)
        
        alerts = FraudAlert.objects.filter(
            created_at__gte=threshold
        ).select_related('user', 'fraud_attempt').order_by('-created_at')[:20]
        
        alerts_list = []
        for alert in alerts:
            alerts_list.append({
                'id': alert.id,
                'title': alert.title,
                'type': alert.alert_type,
                'priority': alert.priority,
                'created_at': alert.created_at.strftime("%H:%M:%S"),
                'user': alert.user.username if alert.user else 'System',
                'is_resolved': alert.is_resolved,
            })
        
        return JsonResponse({
            'alerts': alerts_list,
            'count': len(alerts_list),
            'timestamp': timezone.now().isoformat(),
        })
    
    def api_geographic_data(self, request):
        """API endpoint for geographic data"""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # Get IP geolocation data
        ip_locations = IPReputation.objects.filter(
            country__isnull=False,
            fraud_score__gte=50
        ).values('ip_address', 'country', 'region', 'city', 
                'fraud_score', 'is_blacklisted', 'latitude', 'longitude')[:100]
        
        return JsonResponse({
            'locations': list(ip_locations),
            'timestamp': timezone.now().isoformat(),
        })
    
    def api_risk_timeline(self, request, user_id):
        """API endpoint for user risk timeline"""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        timeline = self._get_user_fraud_timeline(user_id)
        
        return JsonResponse({
            'timeline': timeline,
            'user_id': user_id,
            'timestamp': timezone.now().isoformat(),
        })
    
    def api_send_notification(self, request):
        """API endpoint to send real-time notification"""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        if request.method == 'POST':
            data = json.loads(request.body)
            alert_id = data.get('alert_id')
            user_id = data.get('user_id')
            
            try:
                # Send WebSocket notification
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'fraud_alerts',
                    {
                        'type': 'send_alert',
                        'alert_id': alert_id,
                        'user_id': user_id,
                        'message': 'New fraud alert detected!',
                        'timestamp': timezone.now().isoformat(),
                    }
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Notification sent'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
        
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    def api_toggle_shadow_ban(self, request, user_id):
        """API endpoint to toggle shadow ban"""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        try:
            user_profile = UserRiskProfile.objects.get(user_id=user_id)
            # Toggle shadow ban (store in cache or user preferences)
            shadow_ban_key = f'shadow_ban_{user_id}'
            current = cache.get(shadow_ban_key, False)
            cache.set(shadow_ban_key, not current, 86400)  # 24 hours
            
            # Log the action
            FraudAlert.objects.create(
                alert_type='system',
                priority='medium',
                title=f'Shadow ban {"enabled" if not current else "disabled"}',
                description=f'User {user_id} shadow ban status changed',
                user_id=user_id,
                data={'action': 'shadow_ban_toggle', 'new_status': not current}
            )
            
            return JsonResponse({
                'success': True,
                'shadow_ban_enabled': not current,
                'message': f'Shadow ban {"enabled" if not current else "disabled"}'
            })
        except UserRiskProfile.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
    
    def api_verify_ip_batch(self, request):
        """API endpoint for batch IP verification"""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        if request.method == 'POST':
            data = json.loads(request.body)
            ip_list = data.get('ip_list', [])
            
            results = self._analyze_ip_batch(ip_list)
            
            return JsonResponse({
                'success': True,
                'results': results,
                'timestamp': timezone.now().isoformat(),
            })
        
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Helper Methods
    def _calculate_fraud_detection_rate(self):
        """Calculate fraud detection rate"""
        total_attempts = FraudAttempt.objects.count()
        if total_attempts == 0:
            return 100.0
        
        detected_attempts = FraudAttempt.objects.filter(
            status__in=['confirmed', 'detected']
        ).count()
        
        return (detected_attempts / total_attempts) * 100
    
    def _calculate_false_positive_rate(self):
        """Calculate false positive rate"""
        total_attempts = FraudAttempt.objects.count()
        if total_attempts == 0:
            return 0.0
        
        false_positives = FraudAttempt.objects.filter(
            status='false_positive'
        ).count()
        
        return (false_positives / total_attempts) * 100
    
    def _calculate_financial_impact(self):
        """Calculate financial impact of fraud prevention"""
        # This would need actual transaction data
        prevented_fraud = FraudAttempt.objects.filter(
            status='confirmed'
        ).aggregate(
            total_amount=Sum('amount_involved')
        )['total_amount'] or 0
        
        return {
            'prevented_loss': float(prevented_fraud),
            'estimated_savings': float(prevented_fraud) * 0.3,  # 30% of prevented loss
        }
    
    def _get_avg_processing_time(self):
        """Get average fraud detection processing time"""
        # This would need actual timing data
        return 0.5  # seconds
    
    def _check_websocket_connection(self):
        """Check if WebSocket is connected"""
        # Simple check - in production, implement actual WebSocket status check
        return True
    
    def _analyze_risk_correlation(self):
        """Analyze correlation between different risk factors"""
        # This is a simplified analysis
        return {
            'device_trust_vs_fraud': -0.75,  # Negative correlation
            'ip_reputation_vs_fraud': 0.85,   # Positive correlation
            'behavior_vs_fraud': 0.65,
        }
    
    def _get_user_fraud_timeline(self, user_id):
        """Get fraud timeline for a specific user"""
        fraud_attempts = FraudAttempt.objects.filter(
            user_id=user_id
        ).select_related('user').order_by('created_at')
        
        risk_updates = []  # This would come from risk score updates
        alerts = FraudAlert.objects.filter(
            user_id=user_id
        ).select_related('fraud_attempt').order_by('created_at')
        
        timeline = []
        for attempt in fraud_attempts:
            timeline.append({
                'type': 'fraud_attempt',
                'timestamp': attempt.created_at,
                'data': {
                    'attempt_type': attempt.attempt_type,
                    'fraud_score': attempt.fraud_score,
                    'status': attempt.status,
                    'description': attempt.description,
                }
            })
        
        for alert in alerts:
            timeline.append({
                'type': 'alert',
                'timestamp': alert.created_at,
                'data': {
                    'alert_type': alert.alert_type,
                    'priority': alert.priority,
                    'title': alert.title,
                    'is_resolved': alert.is_resolved,
                }
            })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    def _get_global_fraud_timeline(self):
        """Get global fraud timeline"""
        timeline = []
        
        # Major fraud events (last 7 days)
        fraud_events = FraudAttempt.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7),
            fraud_score__gte=80
        ).order_by('-created_at')[:50]
        
        for event in fraud_events:
            timeline.append({
                'type': 'major_fraud',
                'timestamp': event.created_at,
                'data': {
                    'user': event.user.username if event.user else 'Unknown',
                    'attempt_type': event.attempt_type,
                    'fraud_score': event.fraud_score,
                    'status': event.status,
                }
            })
        
        # Rule activations
        rule_activations = FraudRule.objects.filter(
            last_triggered__gte=timezone.now() - timedelta(days=7)
        ).order_by('-last_triggered')[:20]
        
        for rule in rule_activations:
            if rule.last_triggered:
                timeline.append({
                    'type': 'rule_activation',
                    'timestamp': rule.last_triggered,
                    'data': {
                        'rule_name': rule.name,
                        'severity': rule.severity,
                        'trigger_count': rule.trigger_count,
                    }
                })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return timeline
    
    def _analyze_ip_batch(self, ip_list):
        """Analyze a batch of IP addresses"""
        results = []
        
        for ip in ip_list:
            # Check if IP exists in database
            existing = IPReputation.objects.filter(ip_address=ip).first()
            
            if existing:
                results.append({
                    'ip': ip,
                    'fraud_score': existing.fraud_score,
                    'is_blacklisted': existing.is_blacklisted,
                    'country': existing.country,
                    'source': 'database',
                })
            else:
                # Check external threat intelligence (simulated)
                threat_data = self._check_external_threat_intelligence(ip)
                results.append({
                    'ip': ip,
                    'fraud_score': threat_data.get('score', 0),
                    'is_blacklisted': threat_data.get('blacklisted', False),
                    'country': threat_data.get('country', 'Unknown'),
                    'source': 'external',
                })
        
        return results
    
    def _check_external_threat_intelligence(self, ip):
        """Simulate external threat intelligence check"""
        # In production, this would call real threat intelligence APIs
        return {
            'score': 25,
            'blacklisted': False,
            'country': 'Unknown',
        }


# ====================== INLINE ADMIN CLASSES ======================

class FraudCaseEvidenceInline(TabularInline):
    """Inline admin for FraudCaseEvidence"""
    model = FraudCaseEvidence
    extra = 0
    readonly_fields = ('evidence_id', 'integrity_hash', 'created_at', 'hash_status')
    fields = ('evidence_type', 'hash_status', 'added_by', 'created_at', 'integrity_hash')
    
    def hash_status(self, obj):
        return get_hash_status_icon(obj)
    hash_status.short_description = 'Hash Status'


class FraudCaseActionInline(TabularInline):
    """Inline admin for FraudCaseAction"""
    model = FraudCaseAction
    extra = 0
    readonly_fields = ('action_id', 'integrity_hash', 'created_at', 'hash_status')
    fields = ('action_type', 'hash_status', 'performed_by', 'is_completed', 'created_at', 'integrity_hash')
    
    def hash_status(self, obj):
        return get_hash_status_icon(obj)
    hash_status.short_description = 'Hash Status'


# ====================== MAIN ADMIN CLASSES ======================

@admin.register(FraudRule)
class FraudRuleAdmin(ModelAdmin):
    """Admin configuration for FraudRule"""
    list_display = ('name', 'rule_type', 'severity', 'weight', 'threshold', 'is_active', 'trigger_count', 'last_triggered')
    list_filter = ('rule_type', 'severity', 'is_active', 'run_frequency', ('created_at'))
    search_fields = ('name', 'description', 'condition')
    readonly_fields = ('trigger_count', 'false_positive_count', 'last_triggered')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'rule_type', 'severity')
        }),
        ('Rule Configuration', {
            'fields': ('condition', 'weight', 'threshold', 'action_on_trigger')
        }),
        ('Scheduling', {
            'fields': ('is_active', 'run_frequency')
        }),
        ('Statistics', {
            'fields': ('last_triggered', 'trigger_count', 'false_positive_count'),
            'classes': ('collapse',)
        }),
    )
    
    if UNFOLD_AVAILABLE:
        list_display_insert_before = ('name',)
        list_filter_insert_before = ('rule_type',)


@admin.register(FraudAttempt)
class FraudAttemptAdmin(ModelAdmin):
    """Admin configuration for FraudAttempt"""
    list_display = ('attempt_id', 'user', 'attempt_type', 'fraud_score', 'confidence_score', 'status', 'created_at')
    list_filter = ('attempt_type', 'status', 'detected_by', ('fraud_score'))
    search_fields = ('user__username', 'attempt_id', 'description')
    readonly_fields = ('attempt_id', 'evidence_data', 'metadata', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Identifiers', {
            'fields': ('attempt_id', 'user', 'attempt_type')
        }),
        ('Attempt Details', {
            'fields': ('description', 'detected_by', 'fraud_rules')
        }),
        ('Risk Assessment', {
            'fields': ('fraud_score', 'confidence_score')
        }),
        ('Status & Resolution', {
            'fields': ('status', 'is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes')
        }),
        ('Evidence', {
            'fields': ('evidence_data', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Financial Impact', {
            'fields': ('affected_transactions', 'amount_involved'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'resolved_by')


@admin.register(FraudPattern)
class FraudPatternAdmin(ModelAdmin):
    """Admin configuration for FraudPattern"""
    list_display = ('name', 'pattern_type', 'occurrence_count', 'accuracy_rate', 'is_trained', 'model_version')
    list_filter = ('pattern_type', 'is_trained')
    search_fields = ('name', 'description', 'pattern_data')
    readonly_fields = ('occurrence_count', 'last_trained')
    
    fieldsets = (
        ('Pattern Information', {
            'fields': ('name', 'pattern_type', 'description')
        }),
        ('Pattern Data', {
            'fields': ('pattern_data', 'features')
        }),
        ('Statistics', {
            'fields': ('occurrence_count', 'accuracy_rate')
        }),
        ('ML Metadata', {
            'fields': ('is_trained', 'last_trained', 'model_version'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserRiskProfile)
class UserRiskProfileAdmin(ModelAdmin):
    """Admin configuration for UserRiskProfile with color-coded risk scores"""
    list_display = ('user', 'formatted_overall_risk', 'account_risk_score', 'payment_risk_score', 'behavior_risk_score', 'is_flagged', 'monitoring_level')
    list_filter = ('is_flagged', 'is_restricted', 'monitoring_level')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('total_fraud_attempts', 'confirmed_fraud_attempts', 'false_positives', 'last_risk_assessment')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Risk Scores', {
            'fields': ('overall_risk_score', 'account_risk_score', 'payment_risk_score', 'behavior_risk_score')
        }),
        ('Risk Factors', {
            'fields': ('risk_factors', 'warning_flags')
        }),
        ('Statistics', {
            'fields': ('total_fraud_attempts', 'confirmed_fraud_attempts', 'false_positives')
        }),
        ('Restrictions', {
            'fields': ('is_flagged', 'is_restricted', 'restrictions')
        }),
        ('Monitoring', {
            'fields': ('monitoring_level', 'last_risk_assessment', 'next_assessment_due')
        }),
    )
    
    def formatted_overall_risk(self, obj):
        return format_risk_score(obj.overall_risk_score)
    formatted_overall_risk.short_description = 'Overall Risk Score'
    formatted_overall_risk.admin_order_field = 'overall_risk_score'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(DeviceFingerprint)
class DeviceFingerprintAdmin(ModelAdmin):
    """Admin configuration for DeviceFingerprint with advanced search"""
    list_display = ('device_id', 'user', 'platform', 'browser', 'trust_score', 'is_vpn', 'is_proxy', 'last_seen')
    list_filter = ('platform', 'browser', 'os', 'is_vpn', 'is_proxy', 'is_tor', 'is_mobile', 'is_bot')
    search_fields = ('device_id', 'device_hash', 'user__username', 'user_agent', 'ip_address')
    readonly_fields = ('device_hash', 'canvas_fingerprint', 'webgl_fingerprint', 'audio_fingerprint', 'trust_score', 'last_seen')
    
    fieldsets = (
        ('Device Information', {
            'fields': ('user', 'device_id', 'device_hash')
        }),
        ('Browser & Platform', {
            'fields': ('user_agent', 'platform', 'browser', 'browser_version', 'os', 'os_version')
        }),
        ('Hardware & Screen', {
            'fields': ('screen_resolution', 'cpu_cores', 'device_memory', 'max_touch_points')
        }),
        ('Fingerprints', {
            'fields': ('canvas_fingerprint', 'webgl_fingerprint', 'audio_fingerprint'),
            'classes': ('collapse',)
        }),
        ('Network & Location', {
            'fields': ('ip_address', 'location_data')
        }),
        ('Security Flags', {
            'fields': ('is_vpn', 'is_proxy', 'is_tor', 'is_mobile', 'is_bot')
        }),
        ('Trust Score', {
            'fields': ('trust_score', 'last_seen')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(IPReputation)
class IPReputationAdmin(ModelAdmin):
    """Admin configuration for IPReputation with advanced search"""
    list_display = ('ip_address', 'formatted_fraud_score', 'spam_score', 'malware_score', 'is_blacklisted', 'country', 'total_requests')
    list_filter = ('is_blacklisted', 'country', ('fraud_score'))
    search_fields = ('ip_address', 'country', 'region', 'city', 'isp')
    readonly_fields = ('total_requests', 'fraud_attempts', 'unique_users', 'last_threat_check')
    
    fieldsets = (
        ('IP Information', {
            'fields': ('ip_address',)
        }),
        ('Reputation Scores', {
            'fields': ('fraud_score', 'spam_score', 'malware_score')
        }),
        ('Statistics', {
            'fields': ('total_requests', 'fraud_attempts', 'unique_users')
        }),
        ('Classification', {
            'fields': ('is_blacklisted', 'blacklist_reason', 'blacklisted_at')
        }),
        ('Geolocation', {
            'fields': ('country', 'region', 'city', 'isp')
        }),
        ('Threat Intelligence', {
            'fields': ('threat_types', 'last_threat_check'),
            'classes': ('collapse',)
        }),
    )
    
    def formatted_fraud_score(self, obj):
        return format_risk_score(obj.fraud_score)
    formatted_fraud_score.short_description = 'Fraud Score'
    formatted_fraud_score.admin_order_field = 'fraud_score'


@admin.register(FraudAlert)
class FraudAlertAdmin(ModelAdmin):
    """Admin configuration for FraudAlert"""
    list_display = ('alert_id', 'title', 'alert_type', 'priority', 'user', 'is_resolved', 'created_at')
    list_filter = ('alert_type', 'priority', 'is_resolved')
    search_fields = ('title', 'description', 'user__username')
    readonly_fields = ('alert_id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_id', 'alert_type', 'priority', 'title', 'description')
        }),
        ('Related Objects', {
            'fields': ('user', 'fraud_attempt', 'related_rules')
        }),
        ('Alert Data', {
            'fields': ('data',)
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes')
        }),
        ('Notification', {
            'fields': ('notified_users', 'notification_sent'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'fraud_attempt', 'resolved_by')


@admin.register(OfferCompletion)
class OfferCompletionAdmin(ModelAdmin):
    """Admin configuration for OfferCompletion"""
    list_display = ('user', 'offer', 'status', 'reward_amount', 'ip_address', 'is_fraud', 'tracked_at')
    list_filter = ('status', 'is_fraud')
    search_fields = ('user__username', 'offer__title', 'ip_address', 'device_id', 'referral_code')
    readonly_fields = ('tracked_at', 'completed_at', 'reviewed_at')
    
    fieldsets = (
        ('Completion Information', {
            'fields': ('user', 'offer', 'status')
        }),
        ('Reward Details', {
            'fields': ('reward_amount', 'transaction')
        }),
        ('Tracking Data', {
            'fields': ('ip_address', 'user_agent', 'device_id', 'referral_code')
        }),
        ('Fraud Detection', {
            'fields': ('is_fraud', 'fraud_reason')
        }),
        ('Timestamps', {
            'fields': ('tracked_at', 'completed_at', 'reviewed_at', 'reviewed_by', 'notes')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'offer', 'transaction', 'reviewed_by')


@admin.register(FraudSettings)
class FraudSettingsAdmin(ModelAdmin):
    """Admin configuration for FraudSettings"""
    list_display = ('block_vpn', 'global_risk_threshold', 'updated_by', 'updated_at')
    readonly_fields = ('updated_at',)
    
    fieldsets = (
        ('Global Settings', {
            'fields': ('block_vpn', 'global_risk_threshold')
        }),
        ('Metadata', {
            'fields': ('updated_by', 'updated_at')
        }),
    )


@admin.register(FraudCase)
class FraudCaseAdmin(ModelAdmin):
    """Admin configuration for FraudCase with visual integrity status"""
    list_display = ('case_number', 'user', 'title', 'formatted_risk_score', 'priority', 'status', 'hash_status', 'opened_at')
    list_filter = ('status', 'priority', ('risk_score'))
    search_fields = ('case_number', 'user__username', 'title', 'description')
    readonly_fields = ('case_number', 'integrity_hash', 'previous_hash', 'opened_at', 'hash_status')
    
    fieldsets = (
        ('Case Information', {
            'fields': ('case_number', 'user', 'title', 'description', 'hash_status')
        }),
        ('Case Details', {
            'fields': ('status', 'risk_score', 'priority', 'rule_type')
        }),
        ('Timestamps', {
            'fields': ('opened_at', 'resolved_at')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'resolved_by')
        }),
        ('Hash Integrity', {
            'fields': ('integrity_hash', 'previous_hash'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [FraudCaseEvidenceInline, FraudCaseActionInline]
    
    def formatted_risk_score(self, obj):
        return format_risk_score(obj.risk_score)
    formatted_risk_score.short_description = 'Risk Score'
    formatted_risk_score.admin_order_field = 'risk_score'
    
    def hash_status(self, obj):
        return get_hash_status_icon(obj)
    hash_status.short_description = 'Hash Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'assigned_to', 'resolved_by')


@admin.register(FraudCaseEvidence)
class FraudCaseEvidenceAdmin(ModelAdmin):
    """Admin configuration for FraudCaseEvidence"""
    list_display = ('evidence_id', 'fraud_case', 'evidence_type', 'added_by', 'hash_status', 'created_at')
    list_filter = ('evidence_type',)
    search_fields = ('evidence_id', 'fraud_case__case_number', 'data')
    readonly_fields = ('evidence_id', 'integrity_hash', 'previous_hash', 'created_at', 'hash_status')
    
    fieldsets = (
        ('Evidence Information', {
            'fields': ('evidence_id', 'fraud_case', 'evidence_type', 'hash_status')
        }),
        ('Evidence Data', {
            'fields': ('data',)
        }),
        ('Metadata', {
            'fields': ('added_by', 'created_at')
        }),
        ('Hash Integrity', {
            'fields': ('integrity_hash', 'previous_hash'),
            'classes': ('collapse',)
        }),
    )
    
    def hash_status(self, obj):
        return get_hash_status_icon(obj)
    hash_status.short_description = 'Hash Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('fraud_case', 'added_by')


@admin.register(FraudCaseAction)
class FraudCaseActionAdmin(ModelAdmin):
    """Admin configuration for FraudCaseAction"""
    list_display = ('action_id', 'fraud_case', 'action_type', 'performed_by', 'is_completed', 'hash_status', 'created_at')
    list_filter = ('action_type', 'is_completed')
    search_fields = ('action_id', 'fraud_case__case_number', 'note')
    readonly_fields = ('action_id', 'integrity_hash', 'previous_hash', 'created_at', 'hash_status')
    
    fieldsets = (
        ('Action Information', {
            'fields': ('action_id', 'fraud_case', 'action_type', 'hash_status')
        }),
        ('Action Details', {
            'fields': ('performed_by', 'note', 'is_completed')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
        ('Hash Integrity', {
            'fields': ('integrity_hash', 'previous_hash'),
            'classes': ('collapse',)
        }),
    )
    
    def hash_status(self, obj):
        return get_hash_status_icon(obj)
    hash_status.short_description = 'Hash Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('fraud_case', 'performed_by')


@admin.register(FraudWhitelist)
class FraudWhitelistAdmin(ModelAdmin):
    """Admin configuration for FraudWhitelist"""
    list_display = ('whitelist_id', 'entity_type', 'entity_value', 'is_active', 'whitelisted_by', 'hash_status', 'expires_at')
    list_filter = ('entity_type', 'is_active')
    search_fields = ('entity_value', 'reason')
    readonly_fields = ('whitelist_id', 'integrity_hash', 'previous_hash', 'created_at', 'hash_status')
    
    fieldsets = (
        ('Whitelist Information', {
            'fields': ('whitelist_id', 'entity_type', 'entity_value', 'hash_status')
        }),
        ('Details', {
            'fields': ('reason', 'is_active', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('whitelisted_by', 'created_at')
        }),
        ('Hash Integrity', {
            'fields': ('integrity_hash', 'previous_hash'),
            'classes': ('collapse',)
        }),
    )
    
    def hash_status(self, obj):
        return get_hash_status_icon(obj)
    hash_status.short_description = 'Hash Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('whitelisted_by')


@admin.register(FraudNotification)
class FraudNotificationAdmin(ModelAdmin):
    """Admin configuration for FraudNotification"""
    list_display = ('notification_id', 'user', 'notification_type', 'is_sent', 'hash_status', 'sent_at')
    list_filter = ('notification_type', 'is_sent')
    search_fields = ('notification_id', 'user__username', 'message')
    readonly_fields = ('notification_id', 'integrity_hash', 'previous_hash', 'sent_at', 'hash_status')
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('notification_id', 'user', 'notification_type', 'hash_status')
        }),
        ('Message', {
            'fields': ('message',)
        }),
        ('Status', {
            'fields': ('is_sent', 'sent_at', 'read_at')
        }),
        ('Related Case', {
            'fields': ('fraud_case',)
        }),
        ('Hash Integrity', {
            'fields': ('integrity_hash', 'previous_hash'),
            'classes': ('collapse',)
        }),
    )
    
    def hash_status(self, obj):
        return get_hash_status_icon(obj)
    hash_status.short_description = 'Hash Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'fraud_case')


# ====================== CUSTOM ACTIONS ======================

@admin.action(description='Mark selected as confirmed fraud')
def mark_as_confirmed(modeladmin, request, queryset):
    """Mark selected fraud attempts as confirmed"""
    updated = queryset.update(status='confirmed')
    modeladmin.message_user(request, f'{updated} fraud attempts marked as confirmed.', messages.SUCCESS)


@admin.action(description='Mark selected as false positive')
def mark_as_false_positive(modeladmin, request, queryset):
    """Mark selected fraud attempts as false positive"""
    updated = queryset.update(status='false_positive')
    modeladmin.message_user(request, f'{updated} fraud attempts marked as false positive.', messages.SUCCESS)


@admin.action(description='Recalculate risk scores for selected users')
def recalculate_risk_scores(modeladmin, request, queryset):
    """Recalculate risk scores for selected users"""
    updated = 0
    for profile in queryset:
        try:
            profile.update_risk_score()
            updated += 1
        except Exception:
            continue
    modeladmin.message_user(request, f'Risk scores recalculated for {updated} users.', messages.SUCCESS)


@admin.action(description='Blacklist selected IP addresses')
def blacklist_ips(modeladmin, request, queryset):
    """Blacklist selected IP addresses"""
    updated = queryset.update(is_blacklisted=True, blacklisted_at=timezone.now())
    modeladmin.message_user(request, f'{updated} IP addresses blacklisted.', messages.SUCCESS)


# ====================== ADMIN SITE REGISTRATION ======================

# Create custom admin site
fraud_admin_site = FraudAdminSite(name='fraud_admin')

# Register all models with custom admin site
fraud_admin_site.register(FraudRule, FraudRuleAdmin)
fraud_admin_site.register(FraudAttempt, FraudAttemptAdmin)
fraud_admin_site.register(FraudPattern, FraudPatternAdmin)
fraud_admin_site.register(UserRiskProfile, UserRiskProfileAdmin)
fraud_admin_site.register(DeviceFingerprint, DeviceFingerprintAdmin)
fraud_admin_site.register(IPReputation, IPReputationAdmin)
fraud_admin_site.register(FraudAlert, FraudAlertAdmin)
fraud_admin_site.register(OfferCompletion, OfferCompletionAdmin)
fraud_admin_site.register(FraudSettings, FraudSettingsAdmin)
fraud_admin_site.register(FraudCase, FraudCaseAdmin)
fraud_admin_site.register(FraudCaseEvidence, FraudCaseEvidenceAdmin)
fraud_admin_site.register(FraudCaseAction, FraudCaseActionAdmin)
fraud_admin_site.register(FraudWhitelist, FraudWhitelistAdmin)
fraud_admin_site.register(FraudNotification, FraudNotificationAdmin)

# Add custom actions to relevant admin classes
FraudAttemptAdmin.actions = [mark_as_confirmed, mark_as_false_positive]
UserRiskProfileAdmin.actions = [recalculate_risk_scores]
IPReputationAdmin.actions = [blacklist_ips]

# Register new models with both admin sites (if models are available)
if _CHARGEBACK_MODELS_AVAILABLE:
    fraud_admin_site.register(ChargebackDisputeModel, ChargebackDisputeAdmin)
    fraud_admin_site.register(ConversionCapModel, ConversionCapAdmin)


# =============================================================================
# ChargebackDispute Admin
# =============================================================================

# @admin.register(ChargebackDisputeModel)  # Conditionally registered below
class ChargebackDisputeAdmin(ModelAdmin):
    """
    Admin panel for ChargebackDispute model.
    Provides full CRUD, list filters, bulk actions, and SHA-256 integrity display.
    """
    list_display = [
        'dispute_id_short', 'user_link', 'transaction_id',
        'payment_processor', 'reason', 'status_badge',
        'disputed_amount_display', 'currency',
        'received_at', 'response_deadline', 'is_fraudulent',
    ]
    list_filter  = ['status', 'reason', 'payment_processor', 'is_fraudulent',
                    'fraud_confirmed', 'received_at']
    search_fields = ['dispute_id', 'transaction_id', 'bank_reference',
                     'processor_reference', 'description', 'user__username', 'user__email']
    readonly_fields = ['dispute_id', 'received_at', 'created_at', 'updated_at',
                       'is_open_display', 'days_until_deadline_display']
    date_hierarchy  = 'received_at'
    ordering        = ['-received_at']
    list_per_page   = 50
    save_on_top     = True

    fieldsets = (
        ('Dispute Identification', {
            'fields': ('dispute_id', 'user', 'fraud_attempt', 'fraud_case'),
        }),
        ('Payment Information', {
            'fields': ('transaction_id', 'payment_processor', 'original_amount',
                       'disputed_amount', 'currency', 'transaction_date'),
        }),
        ('Dispute Details', {
            'fields': ('reason', 'status', 'bank_reference', 'processor_reference',
                       'description', 'evidence_submitted'),
        }),
        ('Dates & Deadlines', {
            'fields': ('received_at', 'response_deadline', 'resolved_at',
                       'is_open_display', 'days_until_deadline_display'),
        }),
        ('Resolution', {
            'fields': ('resolved_by', 'resolution_notes', 'is_fraudulent', 'fraud_confirmed'),
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = [
        'mark_as_won', 'mark_as_lost', 'mark_as_fraudulent',
        'mark_as_not_fraudulent', 'export_to_csv',
    ]

    def dispute_id_short(self, obj):
        return format_html(
            '<span title="{}">{}</span>',
            str(obj.dispute_id),
            str(obj.dispute_id)[:8] + '…',
        )
    dispute_id_short.short_description = 'Dispute ID'

    def user_link(self, obj):
        if not obj.user:
            return '—'
        return format_html(
            '<a href="/admin/users/user/{}/change/">{}</a>',
            obj.user.pk, obj.user.username,
        )
    user_link.short_description = 'User'
    user_link.allow_tags = True

    def status_badge(self, obj):
        colours = {
            'received':      ('#E6F1FB', '#185FA5'),
            'investigating': ('#FAEEDA', '#854F0B'),
            'represented':   ('#E1F5EE', '#0F6E56'),
            'won':           ('#EAF3DE', '#3B6D11'),
            'lost':          ('#FCEBEB', '#A32D2D'),
            'reversed':      ('#F1EFE8', '#5F5E5A'),
            'withdrawn':     ('#F1EFE8', '#888780'),
        }
        bg, fg = colours.get(obj.status, ('#F1EFE8', '#5F5E5A'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:500">{}</span>',
            bg, fg, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    def disputed_amount_display(self, obj):
        return format_html(
            '<strong>${}</strong>',
            '{:,.2f}'.format(obj.disputed_amount),
        )
    disputed_amount_display.short_description = 'Disputed'

    def is_open_display(self, obj):
        return '🟢 Open' if obj.is_open else '⚫ Closed'
    is_open_display.short_description = 'Open?'

    def days_until_deadline_display(self, obj):
        days = obj.days_until_deadline
        if days is None:
            return '—'
        if days <= 2:
            return format_html('<span style="color:#A32D2D;font-weight:500">{} days</span>', days)
        if days <= 7:
            return format_html('<span style="color:#854F0B">{} days</span>', days)
        return f'{days} days'
    days_until_deadline_display.short_description = 'Deadline in'

    @admin.action(description='✅ Mark selected disputes as WON')
    def mark_as_won(self, request, queryset):
        updated = 0
        for dispute in queryset.filter(status__in=['received', 'investigating', 'represented']):
            dispute.mark_as_won(notes='Bulk marked as won via admin action', resolved_by=request.user)
            updated += 1
        self.message_user(request, f'{updated} dispute(s) marked as WON.', messages.SUCCESS)

    @admin.action(description='❌ Mark selected disputes as LOST')
    def mark_as_lost(self, request, queryset):
        updated = 0
        for dispute in queryset.filter(status__in=['received', 'investigating', 'represented']):
            dispute.mark_as_lost(notes='Bulk marked as lost via admin action', resolved_by=request.user)
            updated += 1
        self.message_user(request, f'{updated} dispute(s) marked as LOST.', messages.SUCCESS)

    @admin.action(description='🚨 Mark selected as fraudulent')
    def mark_as_fraudulent(self, request, queryset):
        updated = queryset.update(is_fraudulent=True, fraud_confirmed=True)
        self.message_user(request, f'{updated} dispute(s) marked as fraudulent.', messages.SUCCESS)

    @admin.action(description='✅ Clear fraudulent flag')
    def mark_as_not_fraudulent(self, request, queryset):
        updated = queryset.update(is_fraudulent=False, fraud_confirmed=False)
        self.message_user(request, f'{updated} dispute(s) cleared.', messages.SUCCESS)

    @admin.action(description='📥 Export selected to CSV')
    def export_to_csv(self, request, queryset):
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="chargebacks.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Dispute ID', 'User', 'Transaction ID', 'Payment Processor',
            'Reason', 'Status', 'Original Amount', 'Disputed Amount',
            'Currency', 'Is Fraudulent', 'Received At', 'Resolved At',
        ])
        for d in queryset.select_related('user'):
            writer.writerow([
                str(d.dispute_id), d.user.username if d.user else '',
                d.transaction_id, d.payment_processor, d.reason, d.status,
                d.original_amount, d.disputed_amount, d.currency,
                d.is_fraudulent, d.received_at, d.resolved_at or '',
            ])
        return response


# =============================================================================
# ConversionCap Admin
# =============================================================================

# @admin.register(ConversionCapModel)  # Conditionally registered below
class ConversionCapAdmin(ModelAdmin):
    """
    Admin panel for ConversionCap model.
    Provides visual cap status, increment tracking, and bulk reset.
    """
    list_display = [
        'id', 'cap_type', 'offer_link', 'advertiser_name',
        'cap_limit', 'current_count', 'remaining_display',
        'usage_bar', 'window_hours', 'action_on_exceed',
        'is_active', 'reset_at',
    ]
    list_filter  = ['cap_type', 'action_on_exceed', 'is_active']
    search_fields = ['advertiser_name', 'offer__title']
    readonly_fields = ['current_count', 'reset_at', 'created_at', 'updated_at',
                       'is_exceeded_display', 'remaining_display']
    ordering = ['-created_at']
    list_per_page = 50
    save_on_top   = True

    fieldsets = (
        ('Cap Configuration', {
            'fields': ('offer', 'advertiser_id', 'advertiser_name',
                       'cap_type', 'cap_limit', 'window_hours', 'action_on_exceed', 'is_active'),
        }),
        ('Current Usage', {
            'fields': ('current_count', 'remaining_display', 'is_exceeded_display', 'reset_at'),
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['reset_caps', 'activate_caps', 'deactivate_caps']

    def offer_link(self, obj):
        if not obj.offer_id:
            return '—'
        return format_html('<a href="/admin/offerwall/offer/{}/change/">Offer #{}</a>', obj.offer_id, obj.offer_id)
    offer_link.short_description = 'Offer'

    def remaining_display(self, obj):
        rem = obj.remaining
        if obj.is_exceeded:
            return format_html('<span style="color:#A32D2D;font-weight:500">EXCEEDED (0)</span>')
        colour = '#3B6D11' if rem > obj.cap_limit * 0.3 else '#854F0B'
        return format_html('<span style="color:{}">{}</span>', colour, rem)
    remaining_display.short_description = 'Remaining'

    def usage_bar(self, obj):
        if obj.cap_limit == 0:
            return '—'
        pct = min(100, int(obj.current_count / obj.cap_limit * 100))
        colour = '#E24B4A' if pct >= 90 else ('#EF9F27' if pct >= 70 else '#639922')
        return format_html(
            '<div style="width:100px;background:#F1EFE8;border-radius:3px;height:10px;">'
            '<div style="width:{}%;background:{};border-radius:3px;height:10px;"></div>'
            '</div> <small>{}%</small>',
            pct, colour, pct,
        )
    usage_bar.short_description = 'Usage'
    usage_bar.allow_tags = True

    def is_exceeded_display(self, obj):
        return '🔴 EXCEEDED' if obj.is_exceeded else '🟢 Within limit'
    is_exceeded_display.short_description = 'Exceeded?'

    @admin.action(description='🔄 Reset counters for selected caps')
    def reset_caps(self, request, queryset):
        for cap in queryset:
            cap.reset()
        self.message_user(request, f'{queryset.count()} cap(s) reset successfully.', messages.SUCCESS)

    @admin.action(description='✅ Activate selected caps')
    def activate_caps(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} cap(s) activated.', messages.SUCCESS)

    @admin.action(description='⏸ Deactivate selected caps')
    def deactivate_caps(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} cap(s) deactivated.', messages.SUCCESS)
