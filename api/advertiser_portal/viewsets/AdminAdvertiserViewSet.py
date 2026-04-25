"""
Admin Advertiser ViewSet

ViewSet for admin management of all advertisers,
including comprehensive admin operations.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.db import transaction

from ..models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification
from ..models.billing import AdvertiserWallet, AdvertiserInvoice
from ..models.campaign import AdCampaign
from ..models.offer import AdvertiserOffer
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None
try:
    from ..services import AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None
from ..serializers import AdvertiserSerializer, AdvertiserProfileSerializer
from ..permissions import IsAdminUser
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdminAdvertiserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for admin management of all advertisers.
    
    Provides comprehensive admin operations for
    managing all advertisers in the system.
    """
    
    queryset = Advertiser.objects.all()
    serializer_class = AdvertiserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on admin permissions."""
        # Admin can see all advertisers
        return Advertiser.objects.all().select_related('profile', 'wallet')
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """
        Suspend advertiser account.
        
        Admin action to suspend advertiser.
        """
        advertiser = self.get_object()
        reason = request.data.get('reason', 'Administrative suspension')
        
        try:
            advertiser_service = AdvertiserService()
            suspended_advertiser = advertiser_service.suspend_advertiser(advertiser, reason)
            
            return Response({
                'detail': 'Advertiser suspended successfully',
                'status': suspended_advertiser.status,
                'suspended_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error suspending advertiser: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """
        Reactivate suspended advertiser account.
        
        Admin action to reactivate advertiser.
        """
        advertiser = self.get_object()
        
        if advertiser.status != 'suspended':
            return Response(
                {'detail': 'Account is not suspended'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            advertiser_service = AdvertiserService()
            reactivated_advertiser = advertiser_service.reactivate_advertiser(advertiser)
            
            return Response({
                'detail': 'Advertiser reactivated successfully',
                'status': reactivated_advertiser.status,
                'reactivated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error reactivating advertiser: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Verify advertiser account.
        
        Admin action to manually verify advertiser.
        """
        advertiser = self.get_object()
        
        if advertiser.verification_status == 'verified':
            return Response(
                {'detail': 'Advertiser is already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            advertiser.verification_status = 'verified'
            advertiser.verified_at = timezone.now()
            advertiser.save()
            
            return Response({
                'detail': 'Advertiser verified successfully',
                'verification_status': advertiser.verification_status,
                'verified_at': advertiser.verified_at.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error verifying advertiser: {e}")
            return Response(
                {'detail': 'Failed to verify advertiser'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def unverify(self, request, pk=None):
        """
        Unverify advertiser account.
        
        Admin action to unverify advertiser.
        """
        advertiser = self.get_object()
        reason = request.data.get('reason', 'Administrative action')
        
        try:
            advertiser.verification_status = 'pending'
            advertiser.verified_at = None
            advertiser.save()
            
            return Response({
                'detail': 'Advertiser unverified successfully',
                'verification_status': advertiser.verification_status,
                'reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error unverifying advertiser: {e}")
            return Response(
                {'detail': 'Failed to unverify advertiser'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def comprehensive_profile(self, request, pk=None):
        """
        Get comprehensive advertiser profile.
        
        Returns complete advertiser information including
        profile, wallet, campaigns, offers, and statistics.
        """
        advertiser = self.get_object()
        
        try:
            # Get basic advertiser info
            advertiser_data = AdvertiserSerializer(advertiser).data
            
            # Get profile
            profile = None
            try:
                profile = advertiser.profile
                profile_data = AdvertiserProfileSerializer(profile).data
            except AdvertiserProfile.DoesNotExist:
                profile_data = None
            
            # Get wallet
            wallet = None
            try:
                wallet = advertiser.wallet
                wallet_data = {
                    'id': wallet.id,
                    'balance': float(wallet.balance),
                    'credit_limit': float(wallet.credit_limit),
                    'available_balance': float(wallet.available_balance),
                    'is_active': wallet.is_active,
                    'is_suspended': wallet.is_suspended,
                    'auto_refill_enabled': wallet.auto_refill_enabled,
                }
            except AdvertiserWallet.DoesNotExist:
                wallet_data = None
            
            # Get campaigns count
            campaigns_count = AdCampaign.objects.filter(advertiser=advertiser).count()
            active_campaigns_count = AdCampaign.objects.filter(
                advertiser=advertiser,
                status='active'
            ).count()
            
            # Get offers count
            offers_count = AdvertiserOffer.objects.filter(advertiser=advertiser).count()
            active_offers_count = AdvertiserOffer.objects.filter(
                advertiser=advertiser,
                status='active'
            ).count()
            
            # Get invoices count
            invoices_count = AdvertiserInvoice.objects.filter(advertiser=advertiser).count()
            outstanding_invoices_count = AdvertiserInvoice.objects.filter(
                advertiser=advertiser,
                status__in=['sent', 'overdue']
            ).count()
            
            # Get verification status
            verification_status = AdvertiserVerification.objects.filter(
                advertiser=advertiser
            ).order_by('-submitted_at').first()
            
            verification_data = None
            if verification_status:
                verification_data = {
                    'status': verification_status.status,
                    'submitted_at': verification_status.submitted_at.isoformat(),
                    'approved_at': verification_status.approved_at.isoformat() if verification_status.approved_at else None,
                    'rejected_at': verification_status.rejected_at.isoformat() if verification_status.rejected_at else None,
                    'rejection_reason': verification_status.rejection_reason,
                }
            
            return Response({
                'advertiser': advertiser_data,
                'profile': profile_data,
                'wallet': wallet_data,
                'verification': verification_data,
                'statistics': {
                    'campaigns_count': campaigns_count,
                    'active_campaigns_count': active_campaigns_count,
                    'offers_count': offers_count,
                    'active_offers_count': active_offers_count,
                    'invoices_count': invoices_count,
                    'outstanding_invoices_count': outstanding_invoices_count,
                },
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting comprehensive profile: {e}")
            return Response(
                {'detail': 'Failed to get comprehensive profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def financial_summary(self, request, pk=None):
        """
        Get advertiser financial summary.
        
        Returns comprehensive financial information.
        """
        advertiser = self.get_object()
        
        try:
            billing_service = AdvertiserBillingService()
            
            # Get wallet information
            wallet_info = billing_service.get_wallet_balance(advertiser)
            
            # Get billing summary
            days = int(request.query_params.get('days', 90))
            billing_summary = billing_service.get_billing_summary(advertiser, days)
            
            # Get recent invoices
            recent_invoices = AdvertiserInvoice.objects.filter(
                advertiser=advertiser
            ).order_by('-created_at')[:10]
            
            invoices_data = []
            for invoice in recent_invoices:
                invoices_data.append({
                    'id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'period': invoice.period,
                    'total_amount': float(invoice.total_amount),
                    'status': invoice.status,
                    'due_date': invoice.due_date.isoformat(),
                    'created_at': invoice.created_at.isoformat(),
                })
            
            return Response({
                'wallet': wallet_info,
                'billing_summary': billing_summary,
                'recent_invoices': invoices_data,
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting financial summary: {e}")
            return Response(
                {'detail': 'Failed to get financial summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def adjust_balance(self, request, pk=None):
        """
        Adjust advertiser wallet balance.
        
        Admin action to manually adjust balance.
        """
        advertiser = self.get_object()
        
        try:
            billing_service = AdvertiserBillingService()
            
            amount = request.data.get('amount')
            reason = request.data.get('reason', 'Administrative adjustment')
            
            if not amount:
                return Response(
                    {'detail': 'Amount is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process adjustment
            if amount > 0:
                # Credit adjustment
                transaction = billing_service.process_deposit(
                    advertiser,
                    amount,
                    'admin_credit',
                    'admin',
                    f'admin_adjustment_{timezone.now().timestamp()}'
                )
            else:
                # Debit adjustment
                transaction = billing_service.charge_wallet(
                    advertiser,
                    abs(amount),
                    reason,
                    f'admin_adjustment_{timezone.now().timestamp()}'
                )
            
            return Response({
                'detail': 'Balance adjusted successfully',
                'amount': float(amount),
                'reason': reason,
                'new_balance': float(billing_service.get_wallet_balance(advertiser)['current_balance'])
            })
            
        except Exception as e:
            logger.error(f"Error adjusting balance: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def suspend_wallet(self, request, pk=None):
        """
        Suspend advertiser wallet.
        
        Admin action to suspend wallet operations.
        """
        advertiser = self.get_object()
        
        try:
            wallet = advertiser.wallet
            wallet.is_suspended = True
            wallet.save()
            
            return Response({
                'detail': 'Wallet suspended successfully',
                'is_suspended': True
            })
            
        except Exception as e:
            logger.error(f"Error suspending wallet: {e}")
            return Response(
                {'detail': 'Failed to suspend wallet'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def unsuspend_wallet(self, request, pk=None):
        """
        Unsuspend advertiser wallet.
        
        Admin action to unsuspend wallet operations.
        """
        advertiser = self.get_object()
        
        try:
            wallet = advertiser.wallet
            wallet.is_suspended = False
            wallet.save()
            
            return Response({
                'detail': 'Wallet unsuspended successfully',
                'is_suspended': False
            })
            
        except Exception as e:
            logger.error(f"Error unsuspending wallet: {e}")
            return Response(
                {'detail': 'Failed to unsuspend wallet'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def dashboard_overview(self, request):
        """
        Get admin dashboard overview.
        
        Returns system-wide advertiser statistics.
        """
        try:
            # Get overall statistics
            total_advertisers = Advertiser.objects.count()
            active_advertisers = Advertiser.objects.filter(status='active').count()
            suspended_advertisers = Advertiser.objects.filter(status='suspended').count()
            verified_advertisers = Advertiser.objects.filter(verification_status='verified').count()
            pending_verification = Advertiser.objects.filter(verification_status='pending').count()
            
            # Get financial statistics
            billing_service = AdvertiserBillingService()
            
            # Get total wallet balances
            wallets = AdvertiserWallet.objects.all()
            total_balance = wallets.aggregate(total=Sum('balance'))['total'] or 0
            total_credit_limit = wallets.aggregate(total=Sum('credit_limit'))['total'] or 0
            
            # Get recent registrations
            recent_registrations = Advertiser.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count()
            
            # Get top advertisers by spend
            top_spenders = []
            # This would implement actual spend tracking
            # For now, return placeholder data
            
            return Response({
                'advertiser_statistics': {
                    'total_advertisers': total_advertisers,
                    'active_advertisers': active_advertisers,
                    'suspended_advertisers': suspended_advertisers,
                    'verified_advertisers': verified_advertisers,
                    'pending_verification': pending_verification,
                    'recent_registrations': recent_registrations,
                },
                'financial_statistics': {
                    'total_balance': float(total_balance),
                    'total_credit_limit': float(total_credit_limit),
                    'top_spenders': top_spenders,
                },
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting dashboard overview: {e}")
            return Response(
                {'detail': 'Failed to get dashboard overview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def pending_verifications(self, request):
        """
        Get pending verifications.
        
        Returns list of advertisers pending verification.
        """
        try:
            pending_advertisers = Advertiser.objects.filter(
                verification_status='pending'
            ).select_related('profile')
            
            pending_data = []
            for advertiser in pending_advertisers:
                # Get verification documents
                verification_docs = AdvertiserVerification.objects.filter(
                    advertiser=advertiser
                ).order_by('-submitted_at')
                
                advertiser_data = AdvertiserSerializer(advertiser).data
                advertiser_data['verification_documents'] = [
                    {
                        'id': doc.id,
                        'document_type': doc.document_type,
                        'submitted_at': doc.submitted_at.isoformat(),
                        'status': doc.status,
                    }
                    for doc in verification_docs
                ]
                
                pending_data.append(advertiser_data)
            
            return Response({
                'pending_advertisers': pending_data,
                'count': len(pending_data),
                'generated_at': timezone.now().isoformat(),
            })
            
        except Exception as e:
            logger.error(f"Error getting pending verifications: {e}")
            return Response(
                {'detail': 'Failed to get pending verifications'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_suspend(self, request):
        """
        Bulk suspend multiple advertisers.
        
        Admin action to suspend multiple advertisers.
        """
        advertiser_ids = request.data.get('advertiser_ids', [])
        reason = request.data.get('reason', 'Bulk administrative suspension')
        
        if not advertiser_ids:
            return Response(
                {'detail': 'No advertiser IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            advertiser_service = AdvertiserService()
            
            results = {
                'suspended': 0,
                'failed': 0,
                'errors': []
            }
            
            for advertiser_id in advertiser_ids:
                try:
                    advertiser = Advertiser.objects.get(id=advertiser_id)
                    advertiser_service.suspend_advertiser(advertiser, reason)
                    results['suspended'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'advertiser_id': advertiser_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk suspend: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_reactivate(self, request):
        """
        Bulk reactivate multiple advertisers.
        
        Admin action to reactivate multiple advertisers.
        """
        advertiser_ids = request.data.get('advertiser_ids', [])
        
        if not advertiser_ids:
            return Response(
                {'detail': 'No advertiser IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            advertiser_service = AdvertiserService()
            
            results = {
                'reactivated': 0,
                'failed': 0,
                'errors': []
            }
            
            for advertiser_id in advertiser_ids:
                try:
                    advertiser = Advertiser.objects.get(id=advertiser_id)
                    if advertiser.status == 'suspended':
                        advertiser_service.reactivate_advertiser(advertiser)
                        results['reactivated'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({
                            'advertiser_id': advertiser_id,
                            'error': f'Cannot reactivate advertiser in {advertiser.status} status'
                        })
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'advertiser_id': advertiser_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk reactivate: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_verify(self, request):
        """
        Bulk verify multiple advertisers.
        
        Admin action to verify multiple advertisers.
        """
        advertiser_ids = request.data.get('advertiser_ids', [])
        
        if not advertiser_ids:
            return Response(
                {'detail': 'No advertiser IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            results = {
                'verified': 0,
                'failed': 0,
                'errors': []
            }
            
            for advertiser_id in advertiser_ids:
                try:
                    advertiser = Advertiser.objects.get(id=advertiser_id)
                    advertiser.verification_status = 'verified'
                    advertiser.verified_at = timezone.now()
                    advertiser.save()
                    results['verified'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'advertiser_id': advertiser_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk verify: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        status = request.query_params.get('status')
        verification_status = request.query_params.get('verification_status')
        search = request.query_params.get('search')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if verification_status:
            queryset = queryset.filter(verification_status=verification_status)
        
        if search:
            queryset = queryset.filter(
                Q(company_name__icontains=search) |
                Q(contact_email__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
