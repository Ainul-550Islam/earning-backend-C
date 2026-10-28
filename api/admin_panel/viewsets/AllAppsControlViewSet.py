# api/admin_panel/viewsets/AllAppsControlViewSet.py
"""
AllAppsControlViewSet — Admin control hub for ALL remaining apps.
Controls: KYC, DJoyalty, Advertiser Portal, Publisher Tools, Ad Networks,
Analytics, Alerts, Audit Logs, Localization, Behavior Analytics,
Auto Mod, CMS, Messaging, Version Control, Postback, Offer Inventory, Gamification.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ==================== KYC ADMIN ====================

class KYCAdminViewSet(viewsets.ViewSet):
    """Admin control for KYC (Identity Verification)."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        try:
            from api.kyc.models import KYC
            pending = KYC.objects.filter(status='QUEUED').count()
            approved = KYC.objects.filter(status='SUCCESS').count()
            rejected = KYC.objects.filter(status='FAILED').count()
            return Response({'success': True, 'data': {
                'pending': pending, 'approved': approved, 'rejected': rejected,
                'total': KYC.objects.count(),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def pending_kyc(self, request):
        try:
            from api.kyc.models import KYC
            kyc_list = list(KYC.objects.filter(status='QUEUED').values(
                'id', 'user_id', 'kyc_type', 'submitted_at', 'document_type'
            ).order_by('submitted_at')[:50])
            return Response({'success': True, 'data': kyc_list})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_kyc(self, request):
        try:
            from api.kyc.models import KYC
            kyc_id = request.data.get('kyc_id')
            kyc = KYC.objects.get(pk=kyc_id)
            kyc.status = 'approved'
            kyc.reviewed_by = request.user
            kyc.reviewed_at = timezone.now()
            kyc.save()
            return Response({'success': True, 'kyc_id': kyc_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_kyc(self, request):
        try:
            from api.kyc.models import KYC
            kyc_id = request.data.get('kyc_id')
            reason = request.data.get('reason', 'Document rejected')
            kyc = KYC.objects.get(pk=kyc_id)
            kyc.status = 'rejected'
            kyc.rejection_reason = reason
            kyc.reviewed_by = request.user
            kyc.reviewed_at = timezone.now()
            kyc.save()
            return Response({'success': True, 'kyc_id': kyc_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== DJOYALTY (POINTS/REWARDS) ADMIN ====================

class DJoyaltyAdminViewSet(viewsets.ViewSet):
    """Admin control for DJoyalty — points, tiers, badges, achievements."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def points_overview(self, request):
        try:
            from api.djoyalty.models.points import Points
            total_issued = Points.objects.filter(transaction_type='earn').aggregate(total=Sum('gross_amount'))['total'] or 0
            total_redeemed = Points.objects.filter(transaction_type='redeem').aggregate(total=Sum('gross_amount'))['total'] or 0
            return Response({'success': True, 'data': {
                'total_points_issued': float(total_issued),
                'total_points_redeemed': float(total_redeemed),
                'outstanding': float(total_issued - total_redeemed),
            }})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def grant_points(self, request):
        """Manually grant points to a user."""
        try:
            from api.djoyalty.models.points import Points
            user_id = request.data.get('user_id')
            amount = float(request.data.get('amount', 0))
            reason = request.data.get('reason', 'Admin grant')
            Points.objects.create(
                user_id=user_id, amount=amount,
                transaction_type='earn', description=reason, granted_by=request.user
            )
            return Response({'success': True, 'user_id': user_id, 'points_granted': amount})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def deduct_points(self, request):
        """Deduct points from a user."""
        try:
            from api.djoyalty.models.points import Points
            user_id = request.data.get('user_id')
            amount = float(request.data.get('amount', 0))
            reason = request.data.get('reason', 'Admin deduction')
            Points.objects.create(
                user_id=user_id, amount=-amount,
                transaction_type='adjust', description=reason, granted_by=request.user
            )
            return Response({'success': True, 'user_id': user_id, 'points_deducted': amount})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def tier_overview(self, request):
        """User tier distribution."""
        try:
            from api.djoyalty.models.tiers import Tier
            tiers = list(Tier.objects.values('name', 'min_points', 'max_points', 'user_count').order_by('min_points'))
            return Response({'success': True, 'data': tiers})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Top users by points."""
        try:
            from api.djoyalty.models.core import Customer
            top = list(Customer.objects.order_by('-total_points').values(
                'user_id', 'total_points', 'tier', 'created_at'
            )[:50])
            return Response({'success': True, 'data': top})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


# ==================== AD NETWORKS ADMIN ====================

class AdNetworkAdminViewSet(viewsets.ViewSet):
    """Admin control for Ad Networks (AdMob, Unity Ads, IronSource, AppLovin)."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def networks_overview(self, request):
        try:
            from api.ad_networks.models import AdNetwork
            networks = list(AdNetwork.objects.values(
                'id', 'name', 'network_type', 'is_active',
                'total_revenue', 'total_impressions', 'fill_rate'
            ))
            return Response({'success': True, 'data': networks})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_network(self, request):
        try:
            from api.ad_networks.models import AdNetwork
            network_id = request.data.get('network_id')
            network = AdNetwork.objects.get(pk=network_id)
            network.is_active = not network.is_active
            network.save(update_fields=['is_active'])
            return Response({'success': True, 'is_active': network.is_active, 'network': network.name})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def offers_by_network(self, request):
        try:
            from api.ad_networks.models import Offer, AdNetwork
            network_id = request.query_params.get('network_id')
            qs = Offer.objects.filter(is_active=True)
            if network_id:
                qs = qs.filter(ad_network_id=network_id)
            offers = list(qs.values(
                'id', 'title', 'offer_type', 'payout', 'daily_cap',
                'ad_network__name', 'total_conversions'
            )[:100])
            return Response({'success': True, 'data': offers})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


# ==================== ANALYTICS ADMIN ====================

class AnalyticsAdminViewSet(viewsets.ViewSet):
    """Admin control for Analytics — revenue, user, engagement metrics."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def revenue_analytics(self, request):
        try:
            from api.analytics.models import RevenueAnalytics
            last_30d = timezone.now() - timedelta(days=30)
            data = list(RevenueAnalytics.objects.filter(
                date__gte=last_30d.date()
            ).values('date', 'total_revenue', 'ad_revenue', 'offer_revenue', 'user_count').order_by('date'))
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def user_analytics(self, request):
        try:
            from api.analytics.models import UserAnalytics
            last_30d = timezone.now() - timedelta(days=30)
            data = list(UserAnalytics.objects.filter(
                date__gte=last_30d.date()
            ).values('date', 'new_users', 'active_users', 'churned_users', 'retention_rate').order_by('date'))
            return Response({'success': True, 'data': data})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


# ==================== ALERTS ADMIN ====================

class AlertsAdminViewSet(viewsets.ViewSet):
    """Admin control for Alerts — alert rules, incidents, notifications."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def active_alerts(self, request):
        try:
            from api.alerts.models import AlertLog
            alerts = list(AlertLog.objects.filter(
                status='active'
            ).values('id', 'alert_type', 'severity', 'message', 'created_at').order_by('-created_at')[:50])
            return Response({'success': True, 'data': alerts})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def acknowledge_alert(self, request):
        try:
            from api.alerts.models import AlertLog
            alert_id = request.data.get('alert_id')
            AlertLog.objects.filter(pk=alert_id).update(
                status='acknowledged', acknowledged_by=request.user, acknowledged_at=timezone.now()
            )
            return Response({'success': True, 'alert_id': alert_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== AUDIT LOGS ADMIN ====================

class AuditLogAdminViewSet(viewsets.ViewSet):
    """Admin control for Audit Logs — full system audit trail."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def recent_logs(self, request):
        try:
            from api.audit_logs.models import AuditLog
            hours = int(request.query_params.get('hours', 24))
            cutoff = timezone.now() - timedelta(hours=hours)
            logs = list(AuditLog.objects.filter(
                created_at__gte=cutoff
            ).values('id', 'user_id', 'action', 'resource', 'ip_address', 'created_at').order_by('-created_at')[:200])
            return Response({'success': True, 'data': logs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def audit_summary(self, request):
        try:
            from api.audit_logs.models import AuditLog
            last_24h = timezone.now() - timedelta(hours=24)
            by_action = list(AuditLog.objects.filter(created_at__gte=last_24h).values('action').annotate(count=Count('id')).order_by('-count')[:20])
            return Response({'success': True, 'by_action': by_action, 'total_24h': AuditLog.objects.filter(created_at__gte=last_24h).count()})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})


# ==================== CMS ADMIN ====================

class CMSAdminViewSet(viewsets.ViewSet):
    """Admin control for CMS — pages, banners, content management."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def all_pages(self, request):
        try:
            from api.cms.models import ContentPage
            pages = list(ContentPage.objects.values(
                'id', 'title', 'slug', 'status', 'language', 'updated_at'
            ).order_by('-updated_at')[:100])
            return Response({'success': True, 'data': pages})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def toggle_page(self, request):
        try:
            from api.cms.models import ContentPage
            page_id = request.data.get('page_id')
            page = ContentPage.objects.get(pk=page_id)
            page.status = 'published' if page.status == 'draft' else 'draft'
            page.save(update_fields=['status'])
            return Response({'success': True, 'page_id': page_id, 'status': page.status})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== VERSION CONTROL ADMIN ====================

class VersionControlAdminViewSet(viewsets.ViewSet):
    """Admin control for App Version & Update Policy."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def update_policies(self, request):
        try:
            from api.version_control.models import AppUpdatePolicy
            policies = list(AppUpdatePolicy.objects.values(
                'id', 'platform', 'current_version', 'min_version',
                'force_update', 'update_message', 'is_active'
            ))
            return Response({'success': True, 'data': policies})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def set_force_update(self, request):
        try:
            from api.version_control.models import AppUpdatePolicy
            platform = request.data.get('platform', 'android')
            force = request.data.get('force_update', True)
            version = request.data.get('min_version')
            
            policy = AppUpdatePolicy.objects.filter(platform=platform).first()
            if policy:
                policy.force_update = force
                if version:
                    policy.min_version = version
                policy.save()
                return Response({'success': True, 'platform': platform, 'force_update': force})
            return Response({'error': f'No policy found for {platform}'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== GAMIFICATION ADMIN ====================

class GamificationAdminViewSet(viewsets.ViewSet):
    """Admin control for Gamification — leaderboards, contests, badges."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def leaderboard_stats(self, request):
        try:
            from api.gamification.models import LeaderboardSnapshot
            snapshot = LeaderboardSnapshot.objects.order_by('-created_at').first()
            return Response({
                'success': True,
                'data': snapshot.data if snapshot else {},
                'last_updated': snapshot.created_at.isoformat() if snapshot else None,
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def refresh_leaderboard(self, request):
        """Manually refresh the leaderboard snapshot."""
        try:
            from api.gamification.models import LeaderboardSnapshot
            from django.contrib.auth import get_user_model
            User = get_user_model()
            # Build fresh leaderboard
            top_users = list(User.objects.filter(is_active=True).order_by(
                '-total_earnings'
            ).values('id', 'username', 'total_earnings')[:100])
            LeaderboardSnapshot.objects.create(data={'top_users': top_users, 'generated_at': timezone.now().isoformat()})
            return Response({'success': True, 'refreshed': True, 'entries': len(top_users)})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== OFFER INVENTORY ADMIN ====================

class OfferInventoryAdminViewSet(viewsets.ViewSet):
    """Admin control for Offer Inventory — offer catalog, approval, compliance."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        try:
            from api.offer_inventory.models import Offer
            offers = list(Offer.objects.filter(status='pending_review').values(
                'id', 'title', 'offer_type', 'payout', 'advertiser', 'submitted_at'
            ).order_by('submitted_at')[:50])
            return Response({'success': True, 'data': offers})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_offer(self, request):
        try:
            from api.offer_inventory.models import Offer
            offer_id = request.data.get('offer_id')
            Offer.objects.filter(pk=offer_id).update(
                status='active', approved_by=request.user, approved_at=timezone.now()
            )
            return Response({'success': True, 'offer_id': offer_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== POSTBACK ADMIN ====================

class PostbackAdminViewSet(viewsets.ViewSet):
    """Admin control for Postback Engine — conversion tracking, postback logs."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def postback_logs(self, request):
        try:
            from api.postback.models import PostbackLog
            last_24h = timezone.now() - timedelta(hours=24)
            logs = list(PostbackLog.objects.filter(
                created_at__gte=last_24h
            ).values(
                'id', 'network', 'offer_id', 'click_id', 'status',
                'payout', 'created_at', 'error_message'
            ).order_by('-created_at')[:200])
            
            summary = PostbackLog.objects.filter(created_at__gte=last_24h).aggregate(
                total=Count('id'),
                success=Count('id', filter=Q(status='success')),
                failed=Count('id', filter=Q(status='failed')),
                total_payout=Sum('payout'),
            )
            return Response({'success': True, 'data': logs, 'summary': summary})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def retry_failed_postbacks(self, request):
        """Retry all failed postbacks from the last N hours."""
        try:
            from api.postback.models import PostbackLog
            hours = int(request.data.get('hours', 6))
            cutoff = timezone.now() - timedelta(hours=hours)
            count = PostbackLog.objects.filter(
                created_at__gte=cutoff, status='failed'
            ).update(status='pending_retry')
            return Response({'success': True, 'queued_for_retry': count})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== LOCALIZATION ADMIN ====================

class LocalizationAdminViewSet(viewsets.ViewSet):
    """Admin control for Localization — languages, currencies, geo-targeting."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def supported_languages(self, request):
        try:
            from api.localization.models import Language
            langs = list(Language.objects.values('code', 'name', 'is_active', 'is_default'))
            return Response({'success': True, 'data': langs})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def supported_currencies(self, request):
        try:
            from api.localization.models import Currency
            currencies = list(Currency.objects.values('code', 'name', 'symbol', 'exchange_rate', 'is_active'))
            return Response({'success': True, 'data': currencies})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def update_exchange_rate(self, request):
        try:
            from api.localization.models import Currency
            currency_code = request.data.get('code')
            new_rate = float(request.data.get('rate'))
            Currency.objects.filter(code=currency_code).update(exchange_rate=new_rate)
            return Response({'success': True, 'code': currency_code, 'rate': new_rate})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==================== WALLET ADMIN ====================

class WalletAdminViewSet(viewsets.ViewSet):
    """Admin control for User Wallets — balances, transactions, adjustments."""
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def wallet_overview(self, request):
        try:
            from api.wallet.models.core import Wallet
            from django.db.models import Sum, Count, Avg
            stats = Wallet.objects.aggregate(
                total_wallets=Count('id'),
                total_balance=Sum('current_balance'),
                avg_balance=Avg('balance'),
                zero_balance=Count('id', filter=Q(balance=0)),
            )
            return Response({'success': True, 'data': stats})
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def adjust_wallet_balance(self, request):
        """Manually adjust a user's wallet balance (admin tool)."""
        try:
            from api.wallet.models.core import Wallet, WalletTransaction
            user_id = request.data.get('user_id')
            amount = float(request.data.get('amount', 0))
            reason = request.data.get('reason', 'Admin adjustment')
            
            wallet = Wallet.objects.get(user_id=user_id)
            old_balance = float(wallet.current_balance)
            wallet.current_balance += amount
            wallet.save(update_fields=['balance'])
            
            # Create transaction record
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type='adjustment',
                description=reason,
                performed_by=request.user,
            )
            
            # Log
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user, action='wallet_adjustment',
                    model_name='Wallet', object_id=str(wallet.pk),
                    changes={'old_balance': old_balance, 'adjustment': amount, 'reason': reason},
                )
            except Exception:
                pass
            
            return Response({
                'success': True,
                'user_id': user_id,
                'old_balance': old_balance,
                'adjustment': amount,
                'new_balance': float(wallet.current_balance),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def top_earners(self, request):
        """Top users by total earnings."""
        try:
            from api.wallet.models.core import Wallet
            top = list(Wallet.objects.order_by('-total_earned').values(
                'user_id', 'balance', 'total_earned', 'total_withdrawn'
            )[:50])
            return Response({'success': True, 'data': top})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['get'])
    def suspicious_wallets(self, request):
        """Wallets with unusually high balances or rapid earning."""
        try:
            from api.wallet.models.core import Wallet
            from django.db.models import F
            suspicious = list(Wallet.objects.filter(
                balance__gt=F('user__admin_wallet_limit') if False else 10000
            ).values('user_id', 'balance', 'total_earned', 'created_at').order_by('-balance')[:50])
            return Response({'success': True, 'data': suspicious})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})