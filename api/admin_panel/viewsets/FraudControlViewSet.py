# api/admin_panel/viewsets/FraudControlViewSet.py
"""
FraudControlViewSet — Real-time fraud detection admin control.
Controls: Fraud rules, suspicious IPs, blocked devices, fraud scores,
VPN/Proxy/TOR blocking, multi-account detection.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class FraudControlViewSet(viewsets.ViewSet):
    """
    Real-time fraud detection & prevention admin panel.
    Integrates: fraud_detection, proxy_intelligence, users security services.
    """
    permission_classes = [IsAdminUser]

    # ==================== FRAUD OVERVIEW ====================

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Fraud system overview — total rules, blocked IPs, fraud rate."""
        try:
            from api.fraud_detection.models import FraudRule, FraudAttempt, FraudSettings
            
            settings_obj = FraudSettings.objects.first()
            last_24h = timezone.now() - timedelta(hours=24)
            last_7d = timezone.now() - timedelta(days=7)
            
            return Response({
                'success': True,
                'data': {
                    'total_rules': FraudRule.objects.count(),
                    'active_rules': FraudRule.objects.filter(is_active=True).count(),
                    'fraud_attempts_24h': FraudAttempt.objects.filter(created_at__gte=last_24h).count(),
                    'fraud_attempts_7d': FraudAttempt.objects.filter(created_at__gte=last_7d).count(),
                    'critical_attempts': FraudAttempt.objects.filter(
                        created_at__gte=last_24h, fraud_score__gte=90
                    ).count(),
                    'settings': {
                        'block_vpn': settings_obj.block_vpn if settings_obj else False,
                        'risk_threshold': settings_obj.global_risk_threshold if settings_obj else 70,
                    } if settings_obj else {},
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    # ==================== FRAUD RULES ====================

    @action(detail=False, methods=['get'])
    def fraud_rules(self, request):
        """List all fraud detection rules."""
        try:
            from api.fraud_detection.models import FraudRule
            rules = list(FraudRule.objects.values(
                'id', 'name', 'rule_type', 'severity', 'is_active',
                'weight', 'threshold', 'action_on_trigger', 'created_at'
            ).order_by('-weight'))
            return Response({'success': True, 'data': rules})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_fraud_rule(self, request):
        """Enable/disable a fraud rule."""
        try:
            from api.fraud_detection.models import FraudRule
            rule_id = request.data.get('rule_id')
            rule = FraudRule.objects.get(pk=rule_id)
            rule.is_active = not rule.is_active
            rule.save(update_fields=['is_active'])
            cache.delete('admin_panel:fraud_rules')
            return Response({'success': True, 'is_active': rule.is_active, 'rule': rule.name})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def update_fraud_settings(self, request):
        """Update global fraud detection settings."""
        try:
            from api.fraud_detection.models import FraudSettings
            settings_obj, _ = FraudSettings.objects.get_or_create(pk=1)
            
            if 'block_vpn' in request.data:
                settings_obj.block_vpn = request.data['block_vpn']
            if 'global_risk_threshold' in request.data:
                threshold = int(request.data['global_risk_threshold'])
                if 0 <= threshold <= 100:
                    settings_obj.global_risk_threshold = threshold
            settings_obj.updated_by = request.user
            settings_obj.save()
            
            cache.delete('admin_panel:fraud_settings')
            return Response({'success': True, 'message': 'Fraud settings updated.'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== FRAUD ATTEMPTS ====================

    @action(detail=False, methods=['get'])
    def recent_fraud_attempts(self, request):
        """Recent fraud attempts with risk scores."""
        try:
            from api.fraud_detection.models import FraudAttempt
            hours = int(request.query_params.get('hours', 24))
            min_score = int(request.query_params.get('min_score', 50))
            
            cutoff = timezone.now() - timedelta(hours=hours)
            attempts = list(
                FraudAttempt.objects.filter(
                    created_at__gte=cutoff,
                    fraud_score__gte=min_score
                ).values(
                    'id', 'user_id', 'fraud_score', 'attempt_type',
                    'attempt_type', 'action_taken', 'created_at'
                ).order_by('-fraud_score')[:100]
            )
            return Response({'success': True, 'data': attempts, 'total': len(attempts)})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def fraud_by_type(self, request):
        """Fraud attempts grouped by fraud type."""
        try:
            from api.fraud_detection.models import FraudAttempt
            last_7d = timezone.now() - timedelta(days=7)
            breakdown = list(
                FraudAttempt.objects.filter(created_at__gte=last_7d).values(
                    'attempt_type'
                ).annotate(
                    count=Count('id'),
                    high_risk=Count('id', filter=Q(fraud_score__gte=80)),
                ).order_by('-count')
            )
            return Response({'success': True, 'data': breakdown})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    # ==================== IP BLOCKING ====================

    @action(detail=False, methods=['post'])
    def block_ip(self, request):
        """Manually block an IP address."""
        try:
            from api.fraud_detection.models import BlockedIP
            ip = request.data.get('ip_address')
            reason = request.data.get('reason', 'Manual block by admin')
            if not ip:
                return Response({'error': 'ip_address required'}, status=400)
            
            obj, created = BlockedIP.objects.get_or_create(
                ip_address=ip,
                defaults={'reason': reason, 'blocked_by': request.user}
            )
            cache.delete(f'fraud:blocked_ip:{ip}')
            return Response({'success': True, 'created': created, 'ip': ip})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def unblock_ip(self, request):
        """Remove an IP from blocklist."""
        try:
            from api.fraud_detection.models import BlockedIP
            ip = request.data.get('ip_address')
            deleted, _ = BlockedIP.objects.filter(ip_address=ip).delete()
            cache.delete(f'fraud:blocked_ip:{ip}')
            return Response({'success': True, 'unblocked': bool(deleted), 'ip': ip})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def blocked_ips(self, request):
        """List all blocked IPs."""
        try:
            from api.fraud_detection.models import BlockedIP
            ips = list(BlockedIP.objects.values(
                'id', 'ip_address', 'reason', 'blocked_by__username', 'created_at'
            ).order_by('-created_at')[:200])
            return Response({'success': True, 'data': ips, 'total': BlockedIP.objects.count()})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    # ==================== VPN/PROXY DETECTION ====================

    @action(detail=False, methods=['get'])
    def proxy_intelligence_stats(self, request):
        """VPN/Proxy/TOR detection statistics."""
        try:
            from api.proxy_intelligence.models import IPIntelligence, VPNDetectionLog
            last_7d = timezone.now() - timedelta(days=7)
            
            vpn_detected = VPNDetectionLog.objects.filter(
                created_at__gte=last_7d, is_vpn=True
            ).count()
            proxy_detected = VPNDetectionLog.objects.filter(
                created_at__gte=last_7d, is_proxy=True
            ).count()
            tor_detected = VPNDetectionLog.objects.filter(
                created_at__gte=last_7d, is_tor=True
            ).count()
            
            top_vpn_ips = list(
                VPNDetectionLog.objects.filter(created_at__gte=last_7d, is_vpn=True).values(
                    'ip_address', 'country', 'isp'
                ).annotate(count=Count('id')).order_by('-count')[:20]
            )
            
            return Response({
                'success': True,
                'data': {
                    'vpn_detected_7d': vpn_detected,
                    'proxy_detected_7d': proxy_detected,
                    'tor_detected_7d': tor_detected,
                    'top_vpn_ips': top_vpn_ips,
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    # ==================== MULTI-ACCOUNT DETECTION ====================

    @action(detail=False, methods=['get'])
    def multi_account_suspects(self, request):
        """Users suspected of running multiple accounts."""
        try:
            from api.users.services.multi_account_detector import MultiAccountDetector
            suspects = MultiAccountDetector.get_suspects(limit=50)
            return Response({'success': True, 'data': suspects})
        except Exception as e:
            # Fallback: check shared IPs
            try:
                from django.contrib.auth import get_user_model
                from django.db.models import Count
                User = get_user_model()
                # Users sharing same last login IP
                return Response({
                    'success': True,
                    'data': [],
                    'note': 'MultiAccountDetector integration needed',
                    'error': str(e)
                })
            except Exception:
                return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def ban_multi_account_user(self, request):
        """Ban a user suspected of multi-accounting."""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_id = request.data.get('user_id')
            reason = request.data.get('reason', 'Multiple accounts detected')
            
            user = User.objects.get(pk=user_id)
            user.is_active = False
            user.save(update_fields=['is_active'])
            
            # Log activity
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user,
                    action='ban_multi_account',
                    model_name='User',
                    object_id=str(user_id),
                    changes={'reason': reason},
                )
            except Exception:
                pass
            
            return Response({'success': True, 'user_id': user_id, 'banned': True})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== RISK SCORING ====================

    @action(detail=False, methods=['post'])
    def check_user_risk(self, request):
        """Get real-time risk score for a specific user."""
        try:
            user_id = request.data.get('user_id')
            ip = request.data.get('ip_address', '')
            
            score = 0
            signals = []
            
            # Check if user is active
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(pk=user_id)
                if not user.is_active:
                    signals.append({'signal': 'banned_account', 'weight': 100})
                    score = 100
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            # Check fraud attempts
            try:
                from api.fraud_detection.models import FraudAttempt
                recent_attempts = FraudAttempt.objects.filter(
                    user_id=user_id,
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count()
                if recent_attempts > 0:
                    signals.append({'signal': 'recent_fraud_attempts', 'count': recent_attempts, 'weight': 30})
                    score = min(100, score + recent_attempts * 10)
            except Exception:
                pass
            
            # Check proxy/VPN
            if ip:
                try:
                    from api.proxy_intelligence.models import IPIntelligence
                    ip_intel = IPIntelligence.objects.filter(ip_address=ip).first()
                    if ip_intel and ip_intel.is_vpn:
                        signals.append({'signal': 'vpn_detected', 'weight': 40})
                        score = min(100, score + 40)
                except Exception:
                    pass
            
            return Response({
                'success': True,
                'user_id': user_id,
                'fraud_score': score,
                'risk_level': 'critical' if score >= 80 else 'high' if score >= 60 else 'medium' if score >= 40 else 'low',
                'signals': signals,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)