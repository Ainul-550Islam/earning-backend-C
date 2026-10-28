# api/admin_panel/viewsets/AdvertiserPublisherAdminViewSet.py
"""
Admin control for Advertiser Portal and Publisher Tools.
Controls: Advertiser accounts, campaigns, budgets, billing, KYC verification.
Publisher sites, apps, ad units, earnings, traffic quality.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class AdvertiserAdminViewSet(viewsets.ViewSet):
    """
    Full admin control for Advertiser Portal.
    Approve advertisers, manage budgets, review campaigns, billing.
    """
    permission_classes = [IsAdminUser]

    # ==================== OVERVIEW ====================

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Advertiser system overview — total advertisers, active campaigns, spend."""
        try:
            from api.advertiser_portal.models import Advertiser
            from api.advertiser_portal.database_models.campaign_model import Campaign

            total_advertisers = Advertiser.objects.count()
            active_advertisers = Advertiser.objects.filter(status='active').count()
            pending_review = Advertiser.objects.filter(status='QUEUED').count()
            suspended = Advertiser.objects.filter(status='suspended').count()

            last_30d = timezone.now() - timedelta(days=30)
            new_30d = Advertiser.objects.filter(created_at__gte=last_30d).count()

            total_campaigns = Campaign.objects.count() if hasattr(Campaign, 'objects') else 0
            active_campaigns = Campaign.objects.filter(status='active').count() if hasattr(Campaign, 'objects') else 0

            return Response({
                'success': True,
                'data': {
                    'total_advertisers': total_advertisers,
                    'active_advertisers': active_advertisers,
                    'pending_review': pending_review,
                    'suspended': suspended,
                    'new_last_30d': new_30d,
                    'total_campaigns': total_campaigns,
                    'active_campaigns': active_campaigns,
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    # ==================== ADVERTISER ACCOUNTS ====================

    @action(detail=False, methods=['get'])
    def pending_advertisers(self, request):
        """List advertisers pending approval."""
        try:
            from api.advertiser_portal.models import Advertiser
            advertisers = list(Advertiser.objects.filter(status='QUEUED').values(
                'id', 'company_name', 'email', 'business_type',
                'website', 'country', 'created_at', 'total_budget'
            ).order_by('created_at')[:50])
            return Response({'success': True, 'data': advertisers, 'count': len(advertisers)})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_advertiser(self, request):
        """Approve an advertiser account."""
        try:
            from api.advertiser_portal.models import Advertiser
            advertiser_id = request.data.get('advertiser_id')
            note = request.data.get('note', '')

            advertiser = Advertiser.objects.get(pk=advertiser_id)
            advertiser.status = 'active'
            advertiser.approved_by = request.user
            advertiser.approved_at = timezone.now()
            advertiser.admin_note = note
            advertiser.save()

            # Log activity
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user, action='approve_advertiser',
                    model_name='Advertiser', object_id=str(advertiser_id),
                    changes={'company': advertiser.company_name},
                )
            except Exception:
                pass

            return Response({
                'success': True,
                'advertiser_id': advertiser_id,
                'company': advertiser.company_name,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_advertiser(self, request):
        """Reject/suspend an advertiser account."""
        try:
            from api.advertiser_portal.models import Advertiser
            advertiser_id = request.data.get('advertiser_id')
            reason = request.data.get('reason', 'Did not meet requirements')
            action_type = request.data.get('action', 'rejected')  # rejected or suspended

            Advertiser.objects.filter(pk=advertiser_id).update(
                status=action_type,
                rejection_reason=reason,
                rejected_by=request.user,
                rejected_at=timezone.now(),
            )
            return Response({'success': True, 'advertiser_id': advertiser_id, 'status': action_type})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def advertiser_list(self, request):
        """List all advertisers with search/filter."""
        try:
            from api.advertiser_portal.models import Advertiser
            qs = Advertiser.objects.all()

            status_filter = request.query_params.get('status')
            search = request.query_params.get('search')
            country = request.query_params.get('country')

            if status_filter:
                qs = qs.filter(status=status_filter)
            if search:
                qs = qs.filter(
                    Q(company_name__icontains=search) | Q(email__icontains=search)
                )
            if country:
                qs = qs.filter(country=country)

            advertisers = list(qs.values(
                'id', 'company_name', 'email', 'status', 'country',
                'total_spend', 'total_campaigns', 'created_at'
            ).order_by('-created_at')[:100])

            return Response({
                'success': True,
                'data': advertisers,
                'total': qs.count(),
            })
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    # ==================== CAMPAIGNS ====================

    @action(detail=False, methods=['get'])
    def campaign_overview(self, request):
        """All advertiser campaigns with performance."""
        try:
            from api.advertiser_portal.database_models.campaign_model import Campaign
            campaigns = list(
                Campaign.objects.select_related('advertiser').values(
                    'id', 'name', 'status', 'campaign_type',
                    'budget', 'spent', 'clicks', 'conversions',
                    'start_date', 'end_date',
                ).order_by('-created_at')[:100]
            )
            stats = Campaign.objects.aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(status='active')),
                total_spend=Sum('spent'),
                total_conversions=Sum('conversions'),
            )
            return Response({'success': True, 'campaigns': campaigns, 'stats': stats})
        except Exception as e:
            return Response({'success': True, 'campaigns': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def pause_campaign(self, request):
        """Pause an advertiser campaign."""
        try:
            from api.advertiser_portal.database_models.campaign_model import Campaign
            campaign_id = request.data.get('campaign_id')
            reason = request.data.get('reason', 'Paused by admin')
            Campaign.objects.filter(pk=campaign_id).update(
                status='paused', admin_pause_reason=reason
            )
            return Response({'success': True, 'campaign_id': campaign_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== BILLING ====================

    @action(detail=False, methods=['get'])
    def billing_overview(self, request):
        """Advertiser billing and deposit overview."""
        try:
            from api.advertiser_portal.database_models.billing_model import AdvertiserBilling
            last_30d = timezone.now() - timedelta(days=30)

            total_deposits = AdvertiserBilling.objects.filter(
                transaction_type='deposit',
                status='completed',
            ).aggregate(total=Sum('gross_amount'), count=Count('id'))

            pending_deposits = AdvertiserBilling.objects.filter(
                transaction_type='deposit', status='QUEUED'
            ).aggregate(total=Sum('gross_amount'), count=Count('id'))

            recent = list(AdvertiserBilling.objects.filter(
                created_at__gte=last_30d
            ).values(
                'id', 'advertiser__company_name', 'transaction_type',
                'amount', 'status', 'payment_method', 'created_at'
            ).order_by('-created_at')[:50])

            return Response({
                'success': True,
                'total_deposits': total_deposits,
                'pending_deposits': pending_deposits,
                'recent_transactions': recent,
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_deposit(self, request):
        """Approve an advertiser deposit."""
        try:
            from api.advertiser_portal.database_models.billing_model import AdvertiserBilling
            billing_id = request.data.get('billing_id')
            AdvertiserBilling.objects.filter(pk=billing_id, status='QUEUED').update(
                status='completed',
                approved_by=request.user,
                approved_at=timezone.now(),
            )
            return Response({'success': True, 'billing_id': billing_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== TOP SPENDERS ====================

    @action(detail=False, methods=['get'])
    def top_advertisers(self, request):
        """Top advertisers by total spend."""
        try:
            from api.advertiser_portal.models import Advertiser
            top = list(Advertiser.objects.filter(
                status='active'
            ).values('id', 'company_name', 'total_spend', 'total_campaigns').order_by('-total_spend')[:20])
            return Response({'success': True, 'data': top})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})


class PublisherAdminViewSet(viewsets.ViewSet):
    """
    Full admin control for Publisher Tools.
    Approve publishers, manage sites/apps, ad units, earnings, traffic quality.
    """
    permission_classes = [IsAdminUser]

    # ==================== OVERVIEW ====================

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Publisher system overview."""
        try:
            from api.publisher_tools.models import Publisher, Site, App, AdUnit
            return Response({
                'success': True,
                'data': {
                    'total_publishers': Publisher.objects.count(),
                    'active_publishers': Publisher.objects.filter(status='active').count(),
                    'pending_publishers': Publisher.objects.filter(status='QUEUED').count(),
                    'total_sites': Site.objects.count(),
                    'total_apps': App.objects.count(),
                    'total_ad_units': AdUnit.objects.count(),
                    'active_ad_units': AdUnit.objects.filter(is_active=True).count(),
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    @action(detail=False, methods=['get'])
    def pending_publishers(self, request):
        """Publishers awaiting approval."""
        try:
            from api.publisher_tools.models import Publisher
            publishers = list(Publisher.objects.filter(status='QUEUED').values(
                'id', 'name', 'email', 'business_type', 'website',
                'country', 'monthly_pageviews', 'created_at'
            ).order_by('created_at')[:50])
            return Response({'success': True, 'data': publishers})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_publisher(self, request):
        """Approve a publisher account."""
        try:
            from api.publisher_tools.models import Publisher
            publisher_id = request.data.get('publisher_id')
            publisher = Publisher.objects.get(pk=publisher_id)
            publisher.status = 'active'
            publisher.approved_by = request.user
            publisher.approved_at = timezone.now()
            publisher.save()

            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user, action='approve_publisher',
                    model_name='Publisher', object_id=str(publisher_id),
                    changes={'name': publisher.name},
                )
            except Exception:
                pass

            return Response({'success': True, 'publisher_id': publisher_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def suspend_publisher(self, request):
        """Suspend a publisher."""
        try:
            from api.publisher_tools.models import Publisher
            publisher_id = request.data.get('publisher_id')
            reason = request.data.get('reason', 'Policy violation')
            Publisher.objects.filter(pk=publisher_id).update(
                status='suspended', suspension_reason=reason
            )
            return Response({'success': True, 'publisher_id': publisher_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== SITES & APPS ====================

    @action(detail=False, methods=['get'])
    def pending_sites(self, request):
        """Sites pending review."""
        try:
            from api.publisher_tools.models import Site
            sites = list(Site.objects.filter(status='QUEUED').values(
                'id', 'name', 'url', 'category', 'publisher__name',
                'monthly_pageviews', 'created_at'
            ).order_by('created_at')[:50])
            return Response({'success': True, 'data': sites})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_site(self, request):
        """Approve a publisher site."""
        try:
            from api.publisher_tools.models import Site
            site_id = request.data.get('site_id')
            Site.objects.filter(pk=site_id).update(
                status='SUCCESS', approved_by=request.user, approved_at=timezone.now()
            )
            return Response({'success': True, 'site_id': site_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_site(self, request):
        """Reject a publisher site."""
        try:
            from api.publisher_tools.models import Site
            site_id = request.data.get('site_id')
            reason = request.data.get('reason', 'Site does not meet quality standards')
            Site.objects.filter(pk=site_id).update(
                status='FAILED', rejection_reason=reason
            )
            return Response({'success': True, 'site_id': site_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== EARNINGS ====================

    @action(detail=False, methods=['get'])
    def publisher_earnings(self, request):
        """Publisher earnings summary."""
        try:
            from api.publisher_tools.models import PublisherEarning
            last_30d = timezone.now() - timedelta(days=30)

            earnings = list(
                PublisherEarning.objects.filter(
                    date__gte=last_30d.date()
                ).values(
                    'publisher__name', 'date', 'impressions',
                    'clicks', 'revenue', 'rpm'
                ).order_by('-revenue')[:100]
            )
            total = PublisherEarning.objects.filter(
                date__gte=last_30d.date()
            ).aggregate(
                total_revenue=Sum('revenue'),
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
            )
            return Response({'success': True, 'earnings': earnings, 'total': total})
        except Exception as e:
            return Response({'success': True, 'earnings': [], 'error': str(e)})

    # ==================== TRAFFIC QUALITY ====================

    @action(detail=False, methods=['get'])
    def traffic_quality_flags(self, request):
        """Publishers flagged for low traffic quality."""
        try:
            from api.publisher_tools.models import TrafficSafetyLog
            flags = list(TrafficSafetyLog.objects.filter(
                severity__in=['high', 'critical'],
                created_at__gte=timezone.now() - timedelta(days=7)
            ).values(
                'id', 'publisher__name', 'site__name', 'flag_type',
                'severity', 'invalid_traffic_rate', 'created_at'
            ).order_by('-severity', '-created_at')[:50])
            return Response({'success': True, 'data': flags})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    # ==================== TOP PUBLISHERS ====================

    @action(detail=False, methods=['get'])
    def top_publishers(self, request):
        """Top publishers by earnings."""
        try:
            from api.publisher_tools.models import Publisher
            top = list(Publisher.objects.filter(
                status='active'
            ).values('id', 'name', 'total_earnings', 'total_impressions').order_by('-total_earnings')[:20])
            return Response({'success': True, 'data': top})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})