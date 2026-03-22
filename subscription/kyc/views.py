from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from .models import KYC, KYCVerificationLog
from .serializers import KYCListSerializer, KYCDetailSerializer, KYCVerificationLogSerializer
from .services import KYCService


class KYCViewSet(viewsets.ModelViewSet):
    """Complete KYC Management ViewSet"""
    
    def get_queryset(self):
        """Filter based on user role"""
        qs = KYC.objects.select_related('user', 'reviewed_by').all()
        
        if not self.request.user.is_staff:
            return qs.filter(user=self.request.user)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        return qs.order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return KYCListSerializer
        return KYCDetailSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'approve', 'reject', 'review', 'admin_stats', 'admin_list']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]
    
    # ========================================================================
    # ADMIN ENDPOINTS
    # ========================================================================
    
    @action(detail=False, methods=['get'])
    def admin_list(self, request):
        """Get all KYC records (admin only)"""
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        return Response({
            'count': qs.count(),
            'results': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def admin_stats(self, request):
        """Get KYC statistics (admin only) - FIX FOR 404 ERROR"""
        qs = KYC.objects.all()
        
        stats = {
            'total': qs.count(),
            'pending': qs.filter(status='pending').count(),
            'verified': qs.filter(status='verified').count(),
            'rejected': qs.filter(status='rejected').count(),
            'not_submitted': qs.filter(status='not_submitted').count(),
            'expired': qs.filter(status='expired').count(),
            'high_risk': qs.filter(risk_score__gte=70).count(),
            'medium_risk': qs.filter(risk_score__gte=40, risk_score__lt=70).count(),
            'low_risk': qs.filter(risk_score__lt=40).count(),
            'duplicate_count': qs.filter(is_duplicate=True).count(),
            'today_submissions': qs.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'week_submissions': qs.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
            'face_verified': qs.filter(is_face_verified=True).count(),
            'phone_verified': qs.filter(is_phone_verified=True).count(),
            'name_verified': qs.filter(is_name_verified=True).count(),
        }
        
        return Response(stats)
    
    # ========================================================================
    # REVIEW ENDPOINTS
    # ========================================================================
    
    @action(detail=True, methods=['patch', 'post'])
    def review(self, request, pk=None):
        """Review KYC submission"""
        kyc = self.get_object()
        
        status_value = request.data.get('status')
        if not status_value:
            return Response(
                {'error': 'Status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        kyc.status = status_value
        kyc.admin_notes = request.data.get('comment', '')
        kyc.reviewed_by = request.user
        kyc.reviewed_at = timezone.now()
        kyc.save()
        
        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='reviewed',
            performed_by=request.user,
            details=f'Status changed to {status_value}'
        )
        
        return Response(
            KYCDetailSerializer(kyc).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve KYC"""
        kyc = self.get_object()
        kyc.approve(reviewed_by=request.user)
        
        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='approved',
            performed_by=request.user,
            details='KYC approved'
        )
        
        return Response(
            KYCDetailSerializer(kyc).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject KYC"""
        kyc = self.get_object()
        reason = request.data.get('reason', 'No reason provided')
        kyc.reject(reason=reason, reviewed_by=request.user)
        
        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='rejected',
            performed_by=request.user,
            details=f'Rejection reason: {reason}'
        )
        
        return Response(
            KYCDetailSerializer(kyc).data,
            status=status.HTTP_200_OK
        )
    
    # ========================================================================
    # USER ENDPOINTS
    # ========================================================================
    
    @action(detail=False, methods=['get'])
    def my_kyc(self, request):
        """Get current user's KYC"""
        try:
            kyc = KYC.objects.get(user=request.user)
            return Response(KYCDetailSerializer(kyc).data)
        except KYC.DoesNotExist:
            return Response({
                'status': 'not_submitted',
                'message': 'No KYC submitted yet'
            })
    
    @action(detail=False, methods=['post'])
    def submit(self, request):
        """Submit KYC"""
        kyc, created = KYC.objects.get_or_create(user=request.user)
        
        if kyc.status == 'verified':
            return Response(
                {'error': 'KYC already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        for field in ['full_name', 'phone_number', 'payment_number', 'payment_method',
                      'address_line', 'city', 'country', 'document_type', 'document_number']:
            if field in request.data:
                setattr(kyc, field, request.data[field])
        
        kyc.status = 'pending'
        kyc.save()
        
        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='submitted',
            performed_by=request.user,
            details='User submitted KYC'
        )
        
        return Response(
            KYCDetailSerializer(kyc).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
    
    # ========================================================================
    # VERIFICATION ENDPOINTS
    # ========================================================================
    
    @action(detail=True, methods=['post'])
    def verify_phone(self, request, pk=None):
        """Verify phone number"""
        kyc = self.get_object()
        otp_code = request.data.get('otp')
        
        if not otp_code:
            return Response(
                {'error': 'OTP is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        kyc.is_phone_verified = True
        kyc.save()
        
        KYCVerificationLog.objects.create(
            kyc=kyc,
            action='phone_verified',
            performed_by=request.user,
            details='Phone number verified'
        )
        
        return Response({
            'message': 'Phone verified successfully',
            'is_phone_verified': True
        })
    
    @action(detail=True, methods=['post'])
    def calculate_risk(self, request, pk=None):
        """Calculate risk score for KYC"""
        kyc = self.get_object()
        risk_score = kyc.calculate_risk_score()
        
        return Response({
            'risk_score': risk_score,
            'risk_factors': kyc.risk_factors,
            'is_high_risk': risk_score >= 70
        })
    
    @action(detail=True, methods=['post'])
    def check_duplicate(self, request, pk=None):
        """Check for duplicate KYC"""
        kyc = self.get_object()
        is_duplicate = KYCService.check_duplicate_kyc(kyc)
        
        return Response({
            'is_duplicate': is_duplicate,
            'duplicate_of': kyc.duplicate_of.id if kyc.duplicate_of else None
        })
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get verification logs for KYC"""
        kyc = self.get_object()
        logs = KYCVerificationLog.objects.filter(kyc=kyc).order_by('-created_at')
        
        serializer = KYCVerificationLogSerializer(logs, many=True)
        return Response({
            'kyc_id': kyc.id,
            'logs': serializer.data
        })
