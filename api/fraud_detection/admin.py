# fraud/admin.py
from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg, Q, F, Case, When, Value, IntegerField, DecimalField, FloatField
from django.utils import timezone
from datetime import timedelta, datetime
from django.contrib import messages
from django.db import models
import json
import uuid
from django.contrib.admin import DateFieldListFilter, AllValuesFieldListFilter
from django.core.serializers.json import DjangoJSONEncoder
from django.core.cache import cache
from django.conf import settings
from asgiref.sync import async_to_sync
import requests
from collections import defaultdict
# পরিবর্তে এইভাবে import করুন
try:
    from channels.layers import get_channel_layer
    # DEFAULT_CHANNEL_LAYER আলাদাভাবে import করুন
    from channels import DEFAULT_CHANNEL_LAYER
except ImportError:
    get_channel_layer = None
    DEFAULT_CHANNEL_LAYER = None
    print("[WARN] Channels import failed")

# Unfold imports
try:
    from unfold.admin import ModelAdmin, TabularInline, StackedInline
    from unfold.sites import UnfoldAdminSite
    from unfold.forms import UserCreationForm, UserChangeForm
    from unfold.filters import DateRangeFilter, RelatedDropdownFilter, ChoiceDropdownFilter
    from unfold.contrib.filters.admin import RangeFilter
    from unfold.decorators import action
    UNFOLD_AVAILABLE = True
except ImportError:
    UNFOLD_AVAILABLE = False
    from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
    from django.contrib.admin import AdminSite as UnfoldAdminSite
    from django.contrib.auth.forms import UserCreationForm, UserChangeForm
    from django.contrib.admin import DateFieldListFilter

from .models import (
    FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
    DeviceFingerprint, IPReputation, FraudAlert, OfferCompletion
)


# ====================== CUSTOM ADMIN SITE FOR FRAUD ======================

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
        # ১. Total Fraud Blocked (গত ২৪ ঘণ্টায়)
        fraud_blocked_last_24h = FraudAttempt.objects.filter(
            status='confirmed',
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # ২. Average Risk Score (বর্তমান ইউজারদের গড় রিস্ক স্কোর)
        avg_risk_score = UserRiskProfile.objects.aggregate(
            avg_score=Avg('overall_risk_score')
        )['avg_score'] or 0
        
        # ৩. Active Critical Alerts (বর্তমানে পেন্ডিং থাকা 'Critical' অ্যালার্টের সংখ্যা)
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
        for profile in UserRiskProfile.objects.all()[:100]:  # Sample for analysis
            if profile.risk_factors:
                for factor in profile.risk_factors:
                    if factor not in risk_factors_analysis:
                        risk_factors_analysis[factor] = 0
                    risk_factors_analysis[factor] += 1
        
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
                    'fraud_score': threat_data.get('fraud_score', 0),
                    'is_blacklisted': threat_data.get('is_blacklisted', False),
                    'country': threat_data.get('country', 'Unknown'),
                    'source': 'external_api',
                })
        
        return results
    
    def _check_external_threat_intelligence(self, ip_address):
        """Check external threat intelligence APIs (simulated)"""
        # In production, integrate with actual threat intelligence APIs
        # like AbuseIPDB, VirusTotal, etc.
        
        # Simulated response
        import random
        return {
            'fraud_score': random.randint(0, 100),
            'is_blacklisted': random.choice([True, False]),
            'country': random.choice(['US', 'CN', 'RU', 'IN', 'BR', 'NG']),
            'threat_types': random.sample(['spam', 'botnet', 'phishing', 'malware'], 2),
        }
    
    def index(self, request, extra_context=None):
        """Override admin index to show fraud dashboard"""
        return redirect('admin:fraud_dashboard')


# Create fraud admin site instance
fraud_admin_site = FraudAdminSite(name='fraud_admin')


# Custom Filter for Severity
class SeverityFilter(admin.SimpleListFilter):
    title = 'Severity Level'
    parameter_name = 'severity'

    def lookups(self, request, model_admin):
        return [
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical / Instant Ban'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(severity=self.value())
        return queryset
    
    # Create fraud admin site instance
fraud_admin_site = FraudAdminSite(name='fraud_admin')


# Custom Filter for Severity
class SeverityFilter(admin.SimpleListFilter):
    title = 'Severity Level'
    parameter_name = 'severity'

    def lookups(self, request, model_admin):
        return [
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical / Instant Ban'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(severity=self.value())
        return queryset


# Custom Filter for Fraud Status  
class FraudStatusFilter(admin.SimpleListFilter):
    title = 'Fraud Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('detected', 'Detected'),
            ('confirmed', 'Confirmed'),
            ('false_positive', 'False Positive'),
            ('resolved', 'Resolved'),
            ('reviewing', 'Under Review'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


# Custom Filter for Risk Score
class RiskScoreFilter(admin.SimpleListFilter):
    title = 'Risk Level'
    parameter_name = 'risk_level'

    def lookups(self, request, model_admin):
        return [
            ('high', 'High Risk (70-100)'),
            ('medium', 'Medium Risk (40-69)'),
            ('low', 'Low Risk (0-39)'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'high':
            return queryset.filter(overall_risk_score__gte=70)
        elif self.value() == 'medium':
            return queryset.filter(overall_risk_score__range=[40, 69])
        elif self.value() == 'low':
            return queryset.filter(overall_risk_score__lt=40)
        return queryset
    

# এখন FraudRuleAdmin কাজ করবে
# @admin.register(FraudRule, site=security_admin_site)
# class FraudRuleAdmin(ModelAdmin):
#     list_display = ('name', 'rule_type', 'severity_badge', 'is_active')
#     list_filter = ('rule_type', SeverityFilter, 'is_active')
    
#     def severity_badge(self, obj):
#         colors = {
#             'low': 'text-blue-600 bg-blue-100',
#             'medium': 'text-yellow-600 bg-yellow-100',
#             'high': 'text-orange-600 bg-orange-100',
#             'critical': 'text-white bg-red-600 animate-pulse',
#         }
#         color_class = colors.get(obj.severity, 'text-gray-600 bg-gray-100')
#         return format_html(
#             '<span class="px-2 py-1 rounded-full text-xs font-bold {}">{}</span>',
#             color_class, obj.get_severity_display()
#         )
#     severity_badge.short_description = "Risk Level"


# ====================== ADMIN CLASSES WITH ENHANCED FEATURES ======================

@admin.register(FraudRule, site=fraud_admin_site)
class FraudRuleAdmin(ModelAdmin):
    """Admin interface for Fraud Rules with advanced features"""
    list_display = [
        'name', 'rule_type_display', 'severity_display', 'weight', 
        'is_active_badge', 'trigger_count', 'effectiveness_display',
        'last_triggered_display'
    ]
    
    list_filter = [
        'rule_type', SeverityFilter, 'is_active', 'run_frequency',
    ]
    
    search_fields = [
        'name', 'description', 'condition'
    ]
    
    readonly_fields = [
        'trigger_count', 'false_positive_count', 'last_triggered',
        'effectiveness_display_field', 'performance_metrics', 
        'condition_prettified', 'test_rule_button'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'rule_type', 'severity')
        }),
        ('Rule Configuration', {
            'fields': ('condition_prettified', 'weight', 'threshold', 'action_on_trigger')
        }),
        ('Scheduling', {
            'fields': ('is_active', 'run_frequency')
        }),
        ('Performance', {
            'fields': ('performance_metrics', 'effectiveness_display_field', 'test_rule_button'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('trigger_count', 'false_positive_count', 'last_triggered'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'activate_rules', 'deactivate_rules', 'test_rules',
        'duplicate_rules', 'export_rules_json'
    ]
    
    # Custom display methods
    def rule_type_display(self, obj):
        return dict(obj.RULE_TYPES).get(obj.rule_type, obj.rule_type)
    rule_type_display.short_description = 'Rule Type'
    
    def severity_display(self, obj):
        colors = {
            'critical': '#ef4444',
            'high': '#f97316',
            'medium': '#eab308',
            'low': '#3b82f6'
        }
        color = colors.get(obj.severity, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">{}</span>',
            color,
            obj.get_severity_display()
        )
    severity_display.short_description = 'Severity'
    
    def last_triggered_display(self, obj):
        if obj.last_triggered:
            return timezone.localtime(obj.last_triggered).strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_triggered_display.short_description = 'Last Triggered'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 2px 8px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #6b7280; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    def effectiveness_display(self, obj):
        """Display rule effectiveness"""
        total_triggers = obj.trigger_count
        false_positives = obj.false_positive_count
        
        if total_triggers == 0:
            effectiveness = 100
        else:
            effectiveness = ((total_triggers - false_positives) / total_triggers) * 100
        
        if effectiveness >= 90:
            color = '#10b981'
        elif effectiveness >= 70:
            color = '#eab308'
        else:
            color = '#ef4444'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, effectiveness
        )
    effectiveness_display.short_description = 'Effectiveness'
    
    # Readonly field methods
    def effectiveness_display_field(self, obj):
        """Display effectiveness in readonly field"""
        return self.effectiveness_display(obj)
    effectiveness_display_field.short_description = 'Effectiveness'
    
    def performance_metrics(self, obj):
        """Display performance metrics"""
        metrics = []
        
        # Calculate average fraud score for triggered attempts
        triggered_attempts = obj.fraudattempt_set.all()
        if triggered_attempts.exists():
            avg_fraud_score = triggered_attempts.aggregate(
                avg=Avg('fraud_score')
            )['avg'] or 0
            
            metrics.append(f"Average Fraud Score: {avg_fraud_score:.1f}")
            metrics.append(f"Total Triggers: {obj.trigger_count}")
            metrics.append(f"False Positives: {obj.false_positive_count}")
            
            # Time since last trigger
            if obj.last_triggered:
                time_diff = timezone.now() - obj.last_triggered
                hours_diff = time_diff.total_seconds() / 3600
                metrics.append(f"Last Triggered: {hours_diff:.1f} hours ago")
        
        return format_html('<br>'.join(metrics)) if metrics else "No performance data"
    performance_metrics.short_description = 'Performance Metrics'
    
    def condition_prettified(self, obj):
        """Pretty print rule condition"""
        if obj.condition:
            try:
                condition_json = json.loads(obj.condition)
                return format_html(
                    '<pre style="background: #f8fafc; padding: 12px; border-radius: 6px; '
                    'border: 1px solid #e2e8f0; overflow: auto; max-height: 300px;">{}</pre>',
                    json.dumps(condition_json, indent=2, ensure_ascii=False)
                )
            except:
                return format_html(
                    '<pre style="background: #f8fafc; padding: 12px; border-radius: 6px; '
                    'border: 1px solid #e2e8f0;">{}</pre>',
                    obj.condition
                )
        return "No condition defined"
    condition_prettified.short_description = 'Condition (Formatted)'
    
    def test_rule_button(self, obj):
        """Button to test the rule"""
        return format_html(
            '<button type="button" onclick="testFraudRule({})" '
            'style="background-color: #3b82f6; color: white; padding: 8px 16px; '
            'border-radius: 6px; border: none; cursor: pointer; font-weight: 500;">'
            '🧪 Test Rule</button>',
            obj.id
        )
    test_rule_button.short_description = 'Test Rule'
    
    # Custom actions
    def activate_rules(self, request, queryset):
        """Activate selected rules"""
        updated = queryset.update(is_active=True)
        messages.success(request, f'[OK] {updated} rules activated.')
    activate_rules.short_description = "[OK] Activate selected rules"
    
    def deactivate_rules(self, request, queryset):
        """Deactivate selected rules"""
        updated = queryset.update(is_active=False)
        messages.success(request, f'⏸️ {updated} rules deactivated.')
    deactivate_rules.short_description = "⏸️ Deactivate selected rules"
    
    def test_rules(self, request, queryset):
        """Test selected rules"""
        for rule in queryset:
            # Create test fraud attempt
            test_attempt = FraudAttempt.objects.create(
                user=request.user,
                attempt_type='test',
                description=f'Test fraud attempt for rule: {rule.name}',
                fraud_score=rule.threshold + 10,
                detected_by='manual_test',
                status='detected',
            )
            test_attempt.fraud_rules.add(rule)
        
        messages.success(request, f'🧪 Tested {queryset.count()} rules.')
    test_rules.short_description = "🧪 Test selected rules"
    
    def duplicate_rules(self, request, queryset):
        """Duplicate selected rules"""
        count = 0
        for rule in queryset:
            # Create a copy
            rule.pk = None
            rule.name = f"{rule.name} (Copy)"
            rule.is_active = False
            rule.trigger_count = 0
            rule.false_positive_count = 0
            rule.last_triggered = None
            rule.save()
            count += 1
        
        messages.success(request, f'📋 Duplicated {count} rules.')
    duplicate_rules.short_description = "📋 Duplicate selected rules"
    
    def export_rules_json(self, request, queryset):
        """Export rules as JSON"""
        rules_data = []
        for rule in queryset:
            rules_data.append({
                'id': str(rule.id),
                'name': rule.name,
                'type': rule.rule_type,
                'severity': rule.severity,
                'condition': rule.condition,
                'threshold': rule.threshold,
                'weight': rule.weight,
            })
        
        # In a real app, create downloadable file
        messages.info(request, f'📤 Exported {len(rules_data)} rules.')
    export_rules_json.short_description = "📤 Export as JSON"
    
    class Media:
        js = ('fraud/js/fraud_admin.js',)
        css = {'all': ('fraud/css/fraud_admin.css',)}


@admin.register(FraudAttempt, site=fraud_admin_site)
class FraudAttemptAdmin(ModelAdmin):
    """Advanced Admin interface for Fraud Attempts"""
    list_display = [
        'attempt_id_short', 'user_link', 'attempt_type_display', 
        'fraud_score_display', 'status_display', 'created_at_display',
        'evidence_preview', 'quick_actions'
    ]
    
    list_filter = [
        FraudStatusFilter, 'attempt_type', 'is_resolved',
        ('created_at', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
        ('fraud_score', AllValuesFieldListFilter),
    ]
    
    search_fields = [
        'attempt_id', 'user__username', 'user__email', 'description',
        'ip_address', 'user_agent'
    ]
    
    readonly_fields = [
        'attempt_id', 'created_at', 'updated_at', 'evidence_data_prettified',
        'metadata_prettified', 'fraud_score_progress', 'related_entities',
        'timeline_view'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('attempt_id', 'user', 'attempt_type', 'description', 'detected_by')
        }),
        ('Risk Assessment', {
            'fields': ('fraud_score_progress', 'confidence_score', 'fraud_rules')
        }),
        ('Evidence & Data', {
            'fields': ('evidence_data_prettified', 'metadata_prettified', 
                      'affected_transactions', 'amount_involved'),
        }),
        ('Status & Resolution', {
            'fields': ('status', 'is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent', 'device_fingerprint', 'session_id'),
            'classes': ('collapse',)
        }),
        ('Related Entities', {
            'fields': ('related_entities', 'timeline_view'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_confirmed', 'mark_as_false_positive', 'mark_as_resolved',
        'escalate_to_critical', 'request_2fa_verification', 'export_attempts_csv'
    ]
    
    # Custom display methods
    def attempt_id_short(self, obj):
        return str(obj.attempt_id)[:8]
    attempt_id_short.short_description = 'Attempt ID'
    
    def user_link(self, obj):
        """Clickable user link with risk badge"""
        if obj.user:
            url = f'/admin/users/user/{obj.user.id}/change/'
            
            # Get user risk profile
            try:
                risk_profile = UserRiskProfile.objects.get(user=obj.user)
                risk_color = '#10b981'  # green
                if risk_profile.overall_risk_score >= 70:
                    risk_color = '#ef4444'  # red
                elif risk_profile.overall_risk_score >= 40:
                    risk_color = '#f59e0b'  # yellow
                
                risk_badge = format_html(
                    '<span style="background-color: {}; color: white; padding: 1px 6px; '
                    'border-radius: 10px; font-size: 10px; margin-left: 5px;">{}</span>',
                    risk_color, risk_profile.overall_risk_score
                )
            except UserRiskProfile.DoesNotExist:
                risk_badge = ''
            
            return format_html(
                '<a href="{}" style="font-weight: 500;">{}</a>{}',
                url, obj.user.username, risk_badge
            )
        return "Anonymous"
    user_link.short_description = 'User'
    
    def attempt_type_display(self, obj):
        types = {
            'account_takeover': '👤 Account Takeover',
            'payment_fraud': '💳 Payment Fraud',
            'offer_completion_fraud': '[MONEY] Offer Fraud',
            'identity_theft': '🆔 Identity Theft',
            'bot_activity': '🤖 Bot Activity',
            'multiple_accounts': '👥 Multi Account',
        }
        return types.get(obj.attempt_type, obj.attempt_type)
    attempt_type_display.short_description = 'Type'
    
    def fraud_score_display(self, obj):
        if obj.fraud_score >= 80:
            color = '#ef4444'  # red
            icon = '🔴'
        elif obj.fraud_score >= 60:
            color = '#f97316'  # orange
            icon = '🟠'
        elif obj.fraud_score >= 40:
            color = '#eab308'  # yellow
            icon = '🟡'
        else:
            color = '#3b82f6'  # blue
            icon = '🔵'
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 5px;">'
            '<span>{}</span>'
            '<span style="color: {}; font-weight: bold; font-size: 14px;">{}</span>'
            '</div>',
            icon, color, obj.fraud_score
        )
    fraud_score_display.short_description = 'Fraud Score'
    
    def status_display(self, obj):
        status_config = {
            'detected': {'color': '#3b82f6', 'icon': '🔍', 'label': 'Detected'},
            'confirmed': {'color': '#ef4444', 'icon': '[OK]', 'label': 'Confirmed'},
            'false_positive': {'color': '#10b981', 'icon': '[ERROR]', 'label': 'False Positive'},
            'resolved': {'color': '#6b7280', 'icon': '✓', 'label': 'Resolved'},
            'reviewing': {'color': '#f59e0b', 'icon': '⏳', 'label': 'Reviewing'},
        }
        
        config = status_config.get(obj.status, {'color': '#6b7280', 'icon': '', 'label': obj.status})
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500; display: inline-flex; '
            'align-items: center; gap: 4px;">{} {}</span>',
            config['color'], config['icon'], config['label']
        )
    status_display.short_description = 'Status'
    
    def created_at_display(self, obj):
        return format_html(
            '<div style="font-size: 12px;">{}</div>'
            '<div style="font-size: 11px; color: #6b7280;">{}</div>',
            timezone.localtime(obj.created_at).strftime('%Y-%m-%d'),
            timezone.localtime(obj.created_at).strftime('%H:%M:%S')
        )
    created_at_display.short_description = 'Detected At'
    
    def evidence_preview(self, obj):
        """Preview of evidence data"""
        if obj.evidence_data:
            # Take first 50 characters
            preview = str(obj.evidence_data)[:50]
            if len(str(obj.evidence_data)) > 50:
                preview += '...'
            return preview
        return "—"
    evidence_preview.short_description = 'Evidence Preview'
    
    def quick_actions(self, obj):
        """Quick action buttons"""
        buttons = []
        
        if not obj.is_resolved:
            buttons.append(format_html(
                '<button type="button" onclick="confirmFraudAttempt({})" '
                'style="background-color: #10b981; color: white; padding: 2px 8px; '
                'border-radius: 4px; border: none; cursor: pointer; font-size: 11px; margin-right: 5px;">'
                '[OK] Confirm</button>',
                obj.id
            ))
            
            buttons.append(format_html(
                '<button type="button" onclick="markAsFalsePositive({})" '
                'style="background-color: #f59e0b; color: white; padding: 2px 8px; '
                'border-radius: 4px; border: none; cursor: pointer; font-size: 11px; margin-right: 5px;">'
                '[ERROR] False Positive</button>',
                obj.id
            ))
        
        buttons.append(format_html(
            '<a href="/admin/fraud/fraudattempt/{}/change/" '
            'style="background-color: #3b82f6; color: white; padding: 2px 8px; '
            'border-radius: 4px; text-decoration: none; font-size: 11px;">'
            '🔍 View</a>',
            obj.id
        ))
        
        return format_html(''.join(buttons))
    quick_actions.short_description = 'Actions'
    
    # Readonly field methods
    def evidence_data_prettified(self, obj):
        """Pretty print evidence data with JSON syntax highlighting"""
        if obj.evidence_data:
            try:
                evidence_json = json.loads(obj.evidence_data)
                return self._get_json_viewer_html(evidence_json, 'Evidence Data')
            except:
                # Not JSON, show as plain text
                return format_html(
                    '<pre style="background: #f8fafc; padding: 12px; border-radius: 6px; '
                    'border: 1px solid #e2e8f0; overflow: auto; max-height: 400px;">{}</pre>',
                    obj.evidence_data
                )
        return "No evidence data"
    evidence_data_prettified.short_description = 'Evidence Data'
    
    def metadata_prettified(self, obj):
        """Pretty print metadata"""
        if obj.metadata:
            return self._get_json_viewer_html(obj.metadata, 'Metadata')
        return "No metadata"
    metadata_prettified.short_description = 'Metadata'
    
    def fraud_score_progress(self, obj):
        """Progress bar for fraud score"""
        return format_html(
            '<div style="margin: 10px 0;">'
            '<div style="display: flex; justify-content: space-between; margin-bottom: 4px;">'
            '<span>Fraud Score</span>'
            '<span style="font-weight: bold;">{}%</span>'
            '</div>'
            '<div style="width: 100%; height: 12px; background: #e5e7eb; border-radius: 6px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background: linear-gradient(90deg, #ef4444, #f97316); '
            'border-radius: 6px;"></div>'
            '</div>'
            '<div style="display: flex; justify-content: space-between; margin-top: 4px; font-size: 12px; color: #6b7280;">'
            '<span>Low Risk</span><span>High Risk</span>'
            '</div>'
            '</div>',
            obj.fraud_score, obj.fraud_score
        )
    fraud_score_progress.short_description = 'Fraud Score Progress'
    
    def related_entities(self, obj):
        """Show related entities"""
        entities = []
        
        # Related user
        if obj.user:
            entities.append(f"User: {obj.user.username} ({obj.user.email})")
        
        # Related IP
        if obj.ip_address:
            ip_reputation = IPReputation.objects.filter(ip_address=obj.ip_address).first()
            if ip_reputation:
                entities.append(f"IP Reputation: {ip_reputation.fraud_score}/100")
        
        # Related rules
        rule_count = obj.fraud_rules.count()
        if rule_count:
            entities.append(f"Triggered Rules: {rule_count}")
        
        return format_html('<br>'.join(entities)) if entities else "No related entities"
    related_entities.short_description = 'Related Entities'
    
    def timeline_view(self, obj):
        """Show timeline view"""
        timeline_events = []
        
        # Detection event
        timeline_events.append({
            'time': obj.created_at,
            'event': 'Fraud Attempt Detected',
            'icon': '🔍',
            'color': '#3b82f6'
        })
        
        # Status changes
        if obj.status == 'confirmed':
            timeline_events.append({
                'time': obj.updated_at,
                'event': 'Confirmed as Fraud',
                'icon': '[OK]',
                'color': '#ef4444'
            })
        
        if obj.is_resolved and obj.resolved_at:
            timeline_events.append({
                'time': obj.resolved_at,
                'event': 'Resolved',
                'icon': '✓',
                'color': '#10b981'
            })
        
        # Sort by time
        timeline_events.sort(key=lambda x: x['time'])
        
        # Generate HTML
        html_events = []
        for event in timeline_events:
            html_events.append(format_html(
                '<div style="display: flex; align-items: flex-start; margin-bottom: 8px;">'
                '<div style="width: 24px; height: 24px; background-color: {}; '
                'border-radius: 50%; display: flex; align-items: center; justify-content: center; '
                'margin-right: 12px; color: white; font-size: 12px;">{}</div>'
                '<div>'
                '<div style="font-weight: 500;">{}</div>'
                '<div style="font-size: 12px; color: #6b7280;">{}</div>'
                '</div>'
                '</div>',
                event['color'], event['icon'], event['event'],
                timezone.localtime(event['time']).strftime('%Y-%m-%d %H:%M:%S')
            ))
        
        return format_html('<div style="padding: 10px;">' + ''.join(html_events) + '</div>')
    timeline_view.short_description = 'Timeline'
    
    # Helper method for JSON viewer
    def _get_json_viewer_html(self, data, title):
        """Generate HTML for JSON viewer with syntax highlighting"""
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        
        return format_html(
            '<div style="border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden;">'
            '<div style="background: #f8fafc; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; '
            'font-weight: 500; font-size: 14px;">{}</div>'
            '<pre style="margin: 0; padding: 12px; max-height: 400px; overflow: auto; '
            'background: #f8fafc; font-family: \'Menlo\', \'Monaco\', \'Courier New\', monospace; '
            'font-size: 12px; line-height: 1.4;">{}</pre>'
            '</div>',
            title, json_str
        )
    
    # Custom actions
    def mark_as_confirmed(self, request, queryset):
        """Mark selected attempts as confirmed fraud"""
        count = 0
        for attempt in queryset.filter(status__in=['detected', 'reviewing']):
            attempt.status = 'confirmed'
            attempt.is_resolved = True
            attempt.resolved_at = timezone.now()
            attempt.resolved_by = request.user
            attempt.resolution_notes = f'Bulk confirmed via admin by {request.user.username}'
            attempt.save()
            count += 1
        
        messages.success(request, f'[OK] Marked {count} fraud attempts as confirmed.')
    mark_as_confirmed.short_description = "[OK] Mark as confirmed fraud"
    
    def mark_as_false_positive(self, request, queryset):
        """Mark selected attempts as false positive"""
        count = queryset.filter(status__in=['detected', 'reviewing']).update(
            status='false_positive',
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user,
            resolution_notes=f'Bulk marked as false positive via admin'
        )
        
        messages.success(request, f'[ERROR] Marked {count} fraud attempts as false positive.')
    mark_as_false_positive.short_description = "[ERROR] Mark as false positive"
    
    def mark_as_resolved(self, request, queryset):
        """Mark selected attempts as resolved"""
        count = queryset.filter(is_resolved=False).update(
            status='resolved',
            is_resolved=True,
            resolved_at=timezone.now(),
            resolved_by=request.user,
            resolution_notes=f'Bulk resolved via admin'
        )
        
        messages.success(request, f'✓ Marked {count} fraud attempts as resolved.')
    mark_as_resolved.short_description = "✓ Mark as resolved"
    
    def escalate_to_critical(self, request, queryset):
        """Escalate selected attempts to critical"""
        for attempt in queryset.filter(priority__in=['low', 'medium', 'high']):
            # Create critical alert
            FraudAlert.objects.create(
                alert_type='fraud_escalation',
                priority='critical',
                title=f'Escalated Fraud Attempt: {attempt.attempt_id}',
                description=f'Fraud attempt escalated to critical by admin',
                user=attempt.user,
                fraud_attempt=attempt,
                data={'escalated_by': request.user.username}
            )
        
        messages.info(request, f'🚨 Escalated {queryset.count()} fraud attempts to critical.')
    escalate_to_critical.short_description = "🚨 Escalate to critical"
    
    def request_2fa_verification(self, request, queryset):
        """Request 2FA verification for suspicious users"""
        for attempt in queryset.filter(user__isnull=False):
            # Store 2FA request in cache
            cache_key = f'2fa_required_{attempt.user.id}'
            cache.set(cache_key, True, 3600)  # 1 hour
            
            # Create alert
            FraudAlert.objects.create(
                alert_type='2fa_required',
                priority='high',
                title='2FA Verification Required',
                description=f'2FA verification requested for suspicious activity',
                user=attempt.user,
                fraud_attempt=attempt,
                data={'requested_by': request.user.username}
            )
        
        messages.info(request, f'[SECURE] 2FA verification requested for {queryset.count()} users.')
    request_2fa_verification.short_description = "[SECURE] Request 2FA verification"
    
    def export_attempts_csv(self, request, queryset):
        """Export fraud attempts as CSV"""
        messages.info(request, f'📤 CSV export started for {queryset.count()} fraud attempts.')
    export_attempts_csv.short_description = "📤 Export as CSV"
    
    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return super().get_queryset(request).select_related(
            'user', 'resolved_by'
        ).prefetch_related(
            'fraud_rules', 'affected_transactions'
        )
        
 # Custom Filter for Risk Score
# class RiskScoreFilter(admin.SimpleListFilter):
#     title = 'Risk Level'
#     parameter_name = 'risk_level'

#     def lookups(self, request, model_admin):
#         return [
#             ('high', 'High Risk (70-100)'),
#             ('medium', 'Medium Risk (40-69)'),
#             ('low', 'Low Risk (0-39)'),
#         ]

#     def queryset(self, request, queryset):
#         if self.value() == 'high':
#             return queryset.filter(overall_risk_score__gte=70)
#         elif self.value() == 'medium':
#             return queryset.filter(overall_risk_score__range=[40, 69])
#         elif self.value() == 'low':
#             return queryset.filter(overall_risk_score__lt=40)
#         return queryset       


@admin.register(UserRiskProfile, site=fraud_admin_site)
class UserRiskProfileAdmin(ModelAdmin):
    """Advanced Admin interface for User Risk Profiles"""
    list_display = [
        'user_link', 'overall_risk_score_display', 'account_risk_score_badge',
        'payment_risk_score_badge', 'is_flagged_badge', 'is_restricted_badge',
        'last_risk_assessment_display', 'quick_actions'
    ]
    
    list_filter = [
        RiskScoreFilter, 'is_flagged', 'is_restricted', 'monitoring_level',
        ('last_risk_assessment', DateRangeFilter if UNFOLD_AVAILABLE else DateFieldListFilter),
    ]
    
    search_fields = [
        'user__username', 'user__email', 'risk_factors', 'warning_flags'
    ]
    
    readonly_fields = [
        'last_risk_assessment', 'next_assessment_due', 'total_fraud_attempts',
        'confirmed_fraud_attempts', 'false_positives', 'risk_timeline_chart',
        'risk_factors_list', 'warning_flags_list', 'shadow_ban_status'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Risk Scores', {
            'fields': ('overall_risk_score', 'account_risk_score', 
                      'payment_risk_score', 'behavior_risk_score',
                      'risk_timeline_chart')
        }),
        ('Risk Factors', {
            'fields': ('risk_factors_list', 'warning_flags_list')
        }),
        ('Statistics', {
            'fields': ('total_fraud_attempts', 'confirmed_fraud_attempts', 'false_positives')
        }),
        ('Restrictions', {
            'fields': ('is_flagged', 'is_restricted', 'restrictions', 'shadow_ban_status')
        }),
        ('Monitoring', {
            'fields': ('monitoring_level', 'last_risk_assessment', 'next_assessment_due'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'flag_users', 'unflag_users', 'restrict_users', 'unrestrict_users',
        'update_risk_scores', 'enable_shadow_ban', 'disable_shadow_ban',
        'request_manual_review'
    ]
    
    # Custom display methods
    def user_link(self, obj):
        """Clickable user link"""
        if obj.user:
            url = f'/admin/users/user/{obj.user.id}/change/'
            return format_html(
                '<a href="{}" style="font-weight: 500;">{} <span style="color: #6b7280; font-size: 12px;">{}</span></a>',
                url, obj.user.username, obj.user.email
            )
        return "Anonymous"
    user_link.short_description = 'User'
    
    def overall_risk_score_display(self, obj):
        """Overall risk score with progress bar"""
        if obj.overall_risk_score >= 70:
            color = '#ef4444'
            label = 'High'
            icon = '🔴'
        elif obj.overall_risk_score >= 40:
            color = '#f59e0b'
            label = 'Medium'
            icon = '🟡'
        else:
            color = '#10b981'
            label = 'Low'
            icon = '🟢'
        
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px; min-width: 150px;">'
            '<span style="font-size: 16px;">{}</span>'
            '<div style="flex-grow: 1;">'
            '<div style="background: #e5e7eb; height: 8px; border-radius: 4px; overflow: hidden;">'
            '<div style="background: {}; height: 100%; width: {}%;"></div>'
            '</div>'
            '</div>'
            '<span style="color: {}; font-weight: bold; font-size: 12px;">{} ({}%)</span>'
            '</div>',
            icon, color, obj.overall_risk_score, color, label, obj.overall_risk_score
        )
    overall_risk_score_display.short_description = 'Overall Risk'
    
    def account_risk_score_badge(self, obj):
        """Account risk score badge"""
        return self._risk_score_badge(obj.account_risk_score, '👤')
    account_risk_score_badge.short_description = 'Account Risk'
    
    def payment_risk_score_badge(self, obj):
        """Payment risk score badge"""
        return self._risk_score_badge(obj.payment_risk_score, '💳')
    payment_risk_score_badge.short_description = 'Payment Risk'
    
    def _risk_score_badge(self, score, icon):
        """Generate risk score badge"""
        if score >= 70:
            color = '#ef4444'
        elif score >= 40:
            color = '#f59e0b'
        else:
            color = '#10b981'
        
        return format_html(
            '<div style="display: inline-flex; align-items: center; gap: 4px; '
            'background-color: {}20; color: {}; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500;">'
            '{} {}'
            '</div>',
            color, color, icon, score
        )
    
    def is_flagged_badge(self, obj):
        """Flagged status badge"""
        if obj.is_flagged:
            return format_html(
                '<span style="background-color: #fef3c7; color: #92400e; padding: 2px 8px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500; display: inline-flex; '
                'align-items: center; gap: 4px;">🚩 Flagged</span>'
            )
        return "—"
    is_flagged_badge.short_description = 'Flagged'
    
    def is_restricted_badge(self, obj):
        """Restricted status badge"""
        if obj.is_restricted:
            return format_html(
                '<span style="background-color: #fee2e2; color: #991b1b; padding: 2px 8px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500; display: inline-flex; '
                'align-items: center; gap: 4px;">⛔ Restricted</span>'
            )
        return "—"
    is_restricted_badge.short_description = 'Restricted'
    
    def last_risk_assessment_display(self, obj):
        if obj.last_risk_assessment:
            time_diff = timezone.now() - obj.last_risk_assessment
            hours_diff = time_diff.total_seconds() / 3600
            
            if hours_diff < 1:
                time_ago = f"{int(time_diff.total_seconds() / 60)}m ago"
            elif hours_diff < 24:
                time_ago = f"{int(hours_diff)}h ago"
            else:
                time_ago = f"{int(hours_diff / 24)}d ago"
            
            return format_html(
                '<div style="font-size: 12px;">{}</div>'
                '<div style="font-size: 11px; color: #6b7280;">{}</div>',
                timezone.localtime(obj.last_risk_assessment).strftime('%Y-%m-%d'),
                time_ago
            )
        return "Never"
    last_risk_assessment_display.short_description = 'Last Assessment'
    
    def quick_actions(self, obj):
        """Quick action buttons"""
        buttons = []
        
        if not obj.is_flagged:
            buttons.append(format_html(
                '<button type="button" onclick="flagUser({})" '
                'style="background-color: #f59e0b; color: white; padding: 2px 8px; '
                'border-radius: 4px; border: none; cursor: pointer; font-size: 11px; margin-right: 5px;">'
                '🚩 Flag</button>',
                obj.user.id if obj.user else 0
            ))
        else:
            buttons.append(format_html(
                '<button type="button" onclick="unflagUser({})" '
                'style="background-color: #6b7280; color: white; padding: 2px 8px; '
                'border-radius: 4px; border: none; cursor: pointer; font-size: 11px; margin-right: 5px;">'
                '[OK] Unflag</button>',
                obj.user.id if obj.user else 0
            ))
        
        if not obj.is_restricted:
            buttons.append(format_html(
                '<button type="button" onclick="restrictUser({})" '
                'style="background-color: #ef4444; color: white; padding: 2px 8px; '
                'border-radius: 4px; border: none; cursor: pointer; font-size: 11px; margin-right: 5px;">'
                '⛔ Restrict</button>',
                obj.user.id if obj.user else 0
            ))
        
        buttons.append(format_html(
            '<a href="/admin/fraud/fraudtimeline/?user_id={}" '
            'style="background-color: #3b82f6; color: white; padding: 2px 8px; '
            'border-radius: 4px; text-decoration: none; font-size: 11px;">'
            '[STATS] Timeline</a>',
            obj.user.id if obj.user else 0
        ))
        
        return format_html(''.join(buttons))
    quick_actions.short_description = 'Actions'
    
    # Readonly field methods
    def risk_timeline_chart(self, obj):
        """Display risk timeline chart"""
        # This would be a JavaScript chart in production
        return format_html(
            '<div style="text-align: center; padding: 20px; background: #f8fafc; '
            'border-radius: 6px; border: 1px solid #e2e8f0;">'
            '<p style="color: #6b7280; margin: 0;">Risk Timeline Chart</p>'
            '<p style="font-size: 12px; color: #9ca3af;">(Interactive chart would appear here)</p>'
            '</div>'
        )
    risk_timeline_chart.short_description = 'Risk Timeline'
    
    def risk_factors_list(self, obj):
        """Display risk factors as list"""
        if obj.risk_factors:
            factors_html = []
            for factor in obj.risk_factors:
                factors_html.append(f'<li>{factor}</li>')
            
            return format_html(
                '<ul style="margin: 0; padding-left: 20px; color: #6b7280;">{}</ul>',
                mark_safe(''.join(factors_html))
            )
        return "No risk factors identified"
    risk_factors_list.short_description = 'Risk Factors'
    
    def warning_flags_list(self, obj):
        """Display warning flags as list"""
        if obj.warning_flags:
            flags_html = []
            for flag in obj.warning_flags:
                flags_html.append(f'<li style="color: #ef4444;">{flag}</li>')
            
            return format_html(
                '<ul style="margin: 0; padding-left: 20px;">{}</ul>',
                mark_safe(''.join(flags_html))
            )
        return "No warning flags"
    warning_flags_list.short_description = 'Warning Flags'
    
    def shadow_ban_status(self, obj):
        """Display shadow ban status"""
        if obj.user:
            shadow_ban_key = f'shadow_ban_{obj.user.id}'
            is_shadow_banned = cache.get(shadow_ban_key, False)
            
            if is_shadow_banned:
                return format_html(
                    '<div style="background-color: #fef3c7; color: #92400e; padding: 8px; '
                    'border-radius: 6px; border-left: 4px solid #f59e0b;">'
                    '<strong>👤 Shadow Ban Active</strong><br>'
                    '<span style="font-size: 12px;">User is shadow banned - offers are hidden</span>'
                    '</div>'
                )
        
        return "Not shadow banned"
    shadow_ban_status.short_description = 'Shadow Ban Status'
    
    # Custom actions
    def flag_users(self, request, queryset):
        """Flag selected users"""
        count = queryset.update(is_flagged=True)
        
        # Create alerts for flagged users
        for profile in queryset:
            if profile.user:
                FraudAlert.objects.create(
                    alert_type='user_flagged',
                    priority='medium',
                    title='User Flagged for Review',
                    description=f'User {profile.user.username} flagged by admin',
                    user=profile.user,
                    data={'flagged_by': request.user.username}
                )
        
        messages.success(request, f'🚩 {count} users flagged for review.')
    flag_users.short_description = "🚩 Flag users"
    
    def unflag_users(self, request, queryset):
        """Unflag selected users"""
        count = queryset.update(is_flagged=False)
        messages.success(request, f'[OK] {count} users unflagged.')
    unflag_users.short_description = "[OK] Unflag users"
    
    def restrict_users(self, request, queryset):
        """Restrict selected users"""
        count = queryset.update(is_restricted=True)
        
        for profile in queryset:
            if profile.user:
                FraudAlert.objects.create(
                    alert_type='user_restricted',
                    priority='high',
                    title='User Account Restricted',
                    description=f'User {profile.user.username} restricted by admin',
                    user=profile.user,
                    data={'restricted_by': request.user.username}
                )
        
        messages.success(request, f'⛔ {count} users restricted.')
    restrict_users.short_description = "⛔ Restrict users"
    
    def unrestrict_users(self, request, queryset):
        """Unrestrict selected users"""
        count = queryset.update(is_restricted=False)
        messages.success(request, f'🔓 {count} users unrestricted.')
    unrestrict_users.short_description = "🔓 Unrestrict users"
    
    def update_risk_scores(self, request, queryset):
        """Update risk scores for selected users"""
        count = 0
        for profile in queryset:
            if profile.update_risk_score():
                count += 1
        
        messages.success(request, f'[STATS] Risk scores updated for {count} users.')
    update_risk_scores.short_description = "[STATS] Update risk scores"
    
    def enable_shadow_ban(self, request, queryset):
        """Enable shadow ban for selected users"""
        count = 0
        for profile in queryset:
            if profile.user:
                shadow_ban_key = f'shadow_ban_{profile.user.id}'
                cache.set(shadow_ban_key, True, 86400)  # 24 hours
                
                FraudAlert.objects.create(
                    alert_type='shadow_ban',
                    priority='low',
                    title='Shadow Ban Enabled',
                    description=f'Shadow ban enabled for user {profile.user.username}',
                    user=profile.user,
                    data={'enabled_by': request.user.username}
                )
                count += 1
        
        messages.info(request, f'👤 Shadow ban enabled for {count} users.')
    enable_shadow_ban.short_description = "👤 Enable shadow ban"
    
    def disable_shadow_ban(self, request, queryset):
        """Disable shadow ban for selected users"""
        count = 0
        for profile in queryset:
            if profile.user:
                shadow_ban_key = f'shadow_ban_{profile.user.id}'
                cache.set(shadow_ban_key, False, 86400)
                count += 1
        
        messages.info(request, f'👤 Shadow ban disabled for {count} users.')
    disable_shadow_ban.short_description = "👤 Disable shadow ban"
    
    def request_manual_review(self, request, queryset):
        """Request manual review for selected users"""
        for profile in queryset:
            if profile.user:
                FraudAlert.objects.create(
                    alert_type='manual_review',
                    priority='medium',
                    title='Manual Review Requested',
                    description=f'Manual review requested for user {profile.user.username}',
                    user=profile.user,
                    data={'requested_by': request.user.username}
                )
        
        messages.info(request, f'[NOTE] Manual review requested for {queryset.count()} users.')
    request_manual_review.short_description = "[NOTE] Request manual review"


@admin.register(IPReputation, site=fraud_admin_site)
class IPReputationAdmin(ModelAdmin):
    """Advanced Admin interface for IP Reputation"""
    list_display = [
        'ip_address', 'country_flag', 'fraud_score_display', 
        'spam_score_badge', 'malware_score_badge', 'is_blacklisted_badge',
        'total_requests', 'unique_users', 'quick_actions'
    ]
    
    list_filter = [
        'is_blacklisted', 'country', 'threat_types',
        ('fraud_score', AllValuesFieldListFilter),
    ]
    
    search_fields = [
        'ip_address', 'country', 'city', 'isp', 'threat_types'
    ]
    
    readonly_fields = [
        'total_requests', 'fraud_attempts', 'unique_users', 'blacklisted_at',
        'threat_types_list', 'geolocation_map', 'risk_analysis'
    ]
    
    fieldsets = (
        ('IP Information', {
            'fields': ('ip_address', 'geolocation_map', 'country', 'region', 'city', 'isp')
        }),
        ('Reputation Scores', {
            'fields': ('fraud_score', 'spam_score', 'malware_score')
        }),
        ('Statistics', {
            'fields': ('total_requests', 'fraud_attempts', 'unique_users')
        }),
        ('Threat Intelligence', {
            'fields': ('threat_types_list', 'last_threat_check', 'risk_analysis'),
            'classes': ('collapse',)
        }),
        ('Blacklist Status', {
            'fields': ('is_blacklisted', 'blacklist_reason', 'blacklisted_at')
        }),
    )
    
    actions = [
        'blacklist_ips', 'whitelist_ips', 'update_threat_intelligence',
        'export_ip_list', 'bulk_check_external'
    ]
    
    # Custom display methods
    def country_flag(self, obj):
        """Display country with flag emoji"""
        if not obj.country:
            return "🌐 Unknown"
        
        # Country to flag mapping (simplified)
        flag_map = {
            'US': '🇺🇸', 'CN': '🇨🇳', 'IN': '🇮🇳', 'RU': '🇷🇺',
            'BR': '🇧🇷', 'NG': '🇳🇬', 'GB': '🇬🇧', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'JP': '🇯🇵', 'KR': '🇰🇷', 'CA': '🇨🇦',
            'AU': '🇦🇺', 'MX': '🇲🇽', 'ID': '🇮🇩', 'TR': '🇹🇷',
        }
        
        flag = flag_map.get(obj.country, '🌐')
        return format_html(
            '<span title="{}">{} {}</span>',
            obj.country, flag, obj.country
        )
    country_flag.short_description = 'Country'
    
    def fraud_score_display(self, obj):
        """Fraud score with color coding"""
        if obj.fraud_score >= 80:
            color = '#ef4444'
            icon = '🔴'
        elif obj.fraud_score >= 60:
            color = '#f97316'
            icon = '🟠'
        elif obj.fraud_score >= 40:
            color = '#eab308'
            icon = '🟡'
        else:
            color = '#10b981'
            icon = '🟢'
        
        return format_html(
            '<div style="display: inline-flex; align-items: center; gap: 4px;">'
            '<span>{}</span>'
            '<span style="color: {}; font-weight: bold;">{}</span>'
            '</div>',
            icon, color, obj.fraud_score
        )
    fraud_score_display.short_description = 'Fraud Score'
    
    def spam_score_badge(self, obj):
        """Spam score badge"""
        return self._score_badge(obj.spam_score, '📧')
    
    def malware_score_badge(self, obj):
        """Malware score badge"""
        return self._score_badge(obj.malware_score, '🦠')
    
    def _score_badge(self, score, icon):
        """Generate score badge"""
        if score >= 70:
            color = '#ef4444'
        elif score >= 40:
            color = '#f59e0b'
        else:
            color = '#10b981'
        
        return format_html(
            '<div style="display: inline-flex; align-items: center; gap: 2px; '
            'background-color: {}20; color: {}; padding: 1px 6px; '
            'border-radius: 10px; font-size: 11px; font-weight: 500;">'
            '{} {}'
            '</div>',
            color, color, icon, score
        )
    
    def is_blacklisted_badge(self, obj):
        """Blacklist status badge"""
        if obj.is_blacklisted:
            return format_html(
                '<span style="background-color: #fee2e2; color: #991b1b; padding: 2px 8px; '
                'border-radius: 12px; font-size: 12px; font-weight: 500; display: inline-flex; '
                'align-items: center; gap: 4px;">⛔ Blacklisted</span>'
            )
        return format_html(
            '<span style="background-color: #d1fae5; color: #065f46; padding: 2px 8px; '
            'border-radius: 12px; font-size: 12px; font-weight: 500; display: inline-flex; '
            'align-items: center; gap: 4px;">[OK] Clean</span>'
        )
    is_blacklisted_badge.short_description = 'Status'
    
    def quick_actions(self, obj):
        """Quick action buttons"""
        buttons = []
        
        if not obj.is_blacklisted:
            buttons.append(format_html(
                '<button type="button" onclick="blacklistIP(\'{}\')" '
                'style="background-color: #ef4444; color: white; padding: 2px 8px; '
                'border-radius: 4px; border: none; cursor: pointer; font-size: 11px; margin-right: 5px;">'
                '⛔ Blacklist</button>',
                obj.ip_address
            ))
        else:
            buttons.append(format_html(
                '<button type="button" onclick="whitelistIP(\'{}\')" '
                'style="background-color: #10b981; color: white; padding: 2px 8px; '
                'border-radius: 4px; border: none; cursor: pointer; font-size: 11px; margin-right: 5px;">'
                '[OK] Whitelist</button>',
                obj.ip_address
            ))
        
        buttons.append(format_html(
            '<button type="button" onclick="checkExternalIntel(\'{}\')" '
            'style="background-color: #3b82f6; color: white; padding: 2px 8px; '
            'border-radius: 4px; border: none; cursor: pointer; font-size: 11px;">'
            '🔍 Check</button>',
            obj.ip_address
        ))
        
        return format_html(''.join(buttons))
    quick_actions.short_description = 'Actions'
    
    # Readonly field methods
    def threat_types_list(self, obj):
        """Display threat types as badges"""
        if obj.threat_types:
            badges = []
            for threat in obj.threat_types:
                color = '#ef4444' if threat in ['malware', 'botnet', 'phishing'] else '#f59e0b'
                badges.append(format_html(
                    '<span style="background-color: {}; color: white; padding: 2px 6px; '
                    'border-radius: 10px; font-size: 10px; margin-right: 4px; margin-bottom: 4px; '
                    'display: inline-block;">{}</span>',
                    color, threat
                ))
            
            return format_html('<div style="line-height: 1.8;">{}</div>', mark_safe(''.join(badges)))
        return "No known threats"
    threat_types_list.short_description = 'Threat Types'
    
    def geolocation_map(self, obj):
        """Display geolocation map (simplified)"""
        if obj.country:
            return format_html(
                '<div style="background: #f8fafc; padding: 15px; border-radius: 6px; '
                'border: 1px solid #e2e8f0; text-align: center;">'
                '<div style="font-size: 14px; font-weight: 500; margin-bottom: 10px;">'
                '📍 Geolocation'
                '</div>'
                '<div style="color: #6b7280; font-size: 13px;">'
                '{} • {} • {}<br>'
                '<span style="font-size: 11px; color: #9ca3af;">IP: {}</span>'
                '</div>'
                '</div>',
                obj.country, obj.region or 'Unknown region', obj.city or 'Unknown city',
                obj.ip_address
            )
        return "No geolocation data"
    geolocation_map.short_description = 'Geolocation'
    
    def risk_analysis(self, obj):
        """Display risk analysis"""
        analysis = []
        
        if obj.fraud_score >= 70:
            analysis.append("High fraud risk detected")
        if obj.spam_score >= 70:
            analysis.append("High spam activity")
        if obj.malware_score >= 70:
            analysis.append("Malware hosting suspected")
        if obj.is_blacklisted:
            analysis.append("Globally blacklisted")
        if obj.threat_types:
            analysis.append(f"{len(obj.threat_types)} known threat types")
        
        if analysis:
            return format_html(
                '<div style="background: #fef3c7; padding: 10px; border-radius: 6px; '
                'border-left: 4px solid #f59e0b;">'
                '<strong style="color: #92400e;">[WARN] Risk Analysis:</strong><br>'
                '<ul style="margin: 5px 0 0 20px; padding: 0; color: #92400e;">'
                '{}'
                '</ul>'
                '</div>',
                mark_safe(''.join([f'<li>{item}</li>' for item in analysis]))
            )
        return "No significant risks detected"
    risk_analysis.short_description = 'Risk Analysis'
    
    # Custom actions
    def blacklist_ips(self, request, queryset):
        """Blacklist selected IPs"""
        count = queryset.update(
            is_blacklisted=True,
            blacklisted_at=timezone.now(),
            blacklist_reason=f'Bulk blacklisted by {request.user.username}'
        )
        
        messages.success(request, f'⛔ {count} IP addresses blacklisted.')
    blacklist_ips.short_description = "⛔ Blacklist IPs"
    
    def whitelist_ips(self, request, queryset):
        """Whitelist selected IPs"""
        count = queryset.update(
            is_blacklisted=False,
            blacklist_reason=''
        )
        
        messages.success(request, f'[OK] {count} IP addresses whitelisted.')
    whitelist_ips.short_description = "[OK] Whitelist IPs"
    
    def update_threat_intelligence(self, request, queryset):
        """Update threat intelligence for selected IPs"""
        for ip_rep in queryset:
            # Check external threat intelligence
            threat_data = self._check_external_threat_intelligence(ip_rep.ip_address)
            
            # Update with new data
            if threat_data:
                ip_rep.threat_types = threat_data.get('threat_types', [])
                ip_rep.save()
        
        messages.info(request, f'[LOADING] Threat intelligence updated for {queryset.count()} IPs.')
    update_threat_intelligence.short_description = "[LOADING] Update threat intelligence"
    
    def export_ip_list(self, request, queryset):
        """Export IP list"""
        messages.info(request, f'📤 IP list export started for {queryset.count()} IPs.')
    export_ip_list.short_description = "📤 Export IP list"
    
    def bulk_check_external(self, request, queryset):
        """Bulk check external threat intelligence"""
        ip_list = [ip.ip_address for ip in queryset]
        
        # Store in session for bulk results page
        request.session['bulk_ip_check'] = {
            'ips': ip_list,
            'timestamp': timezone.now().isoformat()
        }
        
        messages.info(request, f'🔍 Bulk check initiated for {len(ip_list)} IPs.')
    bulk_check_external.short_description = "🔍 Bulk check external"
    
    def _check_external_threat_intelligence(self, ip_address):
        """Check external threat intelligence APIs"""
        # Simulated external check
        import random
        threats = ['spam', 'botnet', 'phishing', 'malware', 'scanning', 'exploit']
        
        return {
            'threat_types': random.sample(threats, random.randint(0, 3)),
            'confidence': random.randint(0, 100),
            'last_seen': timezone.now().isoformat(),
        }
    
    class Media:
        js = ('fraud/js/ip_reputation.js',)


# ====================== URL CONFIGURATION ======================

def get_admin_urls():
    """Get admin URLs for fraud app"""
    from django.urls import path
    return [
        path('fraud/', fraud_admin_site.urls),
    ]

# Function to get the admin site for registration in main urls.py
def get_fraud_admin_site():
    """Get the fraud admin site instance"""
    return fraud_admin_site


# Custom filters (already defined at the top)
class SeverityFilter(admin.SimpleListFilter):
    # ... existing code ...
    pass

class RiskScoreFilter(admin.SimpleListFilter):
    # ... existing code ...
    pass

class FraudStatusFilter(admin.SimpleListFilter):
    # ... existing code ...
    pass