# api/djoyalty/viewsets/advanced/ReceiptSocialViewSet.py
"""
Djoyalty Receipt + Social ViewSets -- NEW।
ReceiptViewSet, SocialShareViewSet, ReviewViewSet, QRCodeViewSet।

All models were built -- all had ZERO API endpoints।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ...models.family_eco import ReceiptScan, ReceiptEarnRule
from ...models.social import (
    SocialShareReward, CustomerSocialAction,
    ReviewReward, CustomerReview,
    QRCodeEarn, QRCodeScan,
)
from ...serializers.EcoFamilySerializer import (
    ReceiptScanSerializer, ReceiptSubmitSerializer, ReceiptEarnRuleSerializer,
)
from ...serializers.SocialSerializer import (
    SocialShareRewardSerializer, CustomerSocialActionSerializer,
    ReviewRewardSerializer, CustomerReviewSerializer,
    CustomerReviewCreateSerializer,
    QRCodeEarnSerializer, QRCodeScanSerializer,
    QRCodeScanSubmitSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyBaseViewSet


# ─── Receipt Scan ─────────────────────────────────────────────────────────────

class ReceiptViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /receipts/                  -- my submitted receipts
    GET  /receipts/{id}/             -- receipt detail + status
    POST /receipts/submit/           -- submit receipt for scanning
    GET  /receipts/earn-rules/       -- active receipt earn rules (public)
    GET  /receipts/admin/pending/    -- admin: pending for review
    POST /receipts/admin/{id}/approve/ -- admin: approve + award points
    POST /receipts/admin/{id}/reject/  -- admin: reject with reason
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = ReceiptScanSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        customer = getattr(self.request, 'loyalty_customer', None)
        if not customer:
            return ReceiptScan.objects.none()
        return ReceiptScan.objects.filter(customer=customer).order_by('-submitted_at')

    @action(detail=False, methods=['post'], url_path='submit')
    def submit(self, request):
        """Submit receipt image URL for OCR + earn processing."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')

        serializer = ReceiptSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from ...services.ReceiptScanService import ReceiptScanService
            receipt = ReceiptScanService.submit(
                customer=customer,
                receipt_image_url=serializer.validated_data['receipt_image_url'],
                channel=serializer.validated_data.get('channel', 'app'),
            )
            response_serializer = ReceiptScanSerializer(receipt)
            return Response({
                'status': 'submitted',
                'receipt': response_serializer.data,
                'message': 'Receipt submitted! We\'ll process it shortly.',
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='earn-rules')
    def earn_rules(self, request):
        """List active receipt earn rules."""
        qs = ReceiptEarnRule.objects.filter(is_active=True).order_by('name')
        return Response(ReceiptEarnRuleSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='admin/pending',
            permission_classes=[IsLoyaltyAdmin])
    def admin_pending(self, request):
        """Admin: receipts awaiting manual review."""
        qs = ReceiptScan.objects.filter(
            status='pending'
        ).select_related('customer').order_by('-submitted_at')
        return Response({
            'count':    qs.count(),
            'receipts': ReceiptScanSerializer(qs[:50], many=True).data,
        })

    @action(detail=True, methods=['post'], url_path='approve',
            permission_classes=[IsLoyaltyAdmin])
    def admin_approve(self, request, pk=None):
        """Admin approves receipt and awards points."""
        receipt = get_object_or_404(ReceiptScan, pk=pk, status='pending')
        try:
            from ...services.ReceiptScanService import ReceiptScanService
            result = ReceiptScanService.approve(
                receipt=receipt,
                approved_by=str(request.user),
                points_override=request.data.get('points_override'),
            )
            return Response({
                'status': 'approved',
                'points_awarded': str(result['points_awarded']),
            })
        except Exception as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], url_path='reject',
            permission_classes=[IsLoyaltyAdmin])
    def admin_reject(self, request, pk=None):
        """Admin rejects receipt with reason."""
        receipt = get_object_or_404(ReceiptScan, pk=pk, status='pending')
        reason  = request.data.get('reason', 'Invalid receipt.')
        receipt.status           = 'rejected'
        receipt.rejection_reason = reason
        receipt.processed_at     = timezone.now()
        receipt.save(update_fields=['status', 'rejection_reason', 'processed_at'])
        return Response({'status': 'rejected', 'reason': reason})


# ─── Social Share ─────────────────────────────────────────────────────────────

class SocialShareViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /social/share-rules/             -- active share reward rules
    POST /social/share-rules/{id}/track/  -- track a share, earn points
    GET  /social/my-shares/               -- my share history
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = SocialShareRewardSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return SocialShareReward.objects.filter(is_active=True).order_by('platform')

    @action(detail=True, methods=['post'], url_path='track')
    def track(self, request, pk=None):
        """Track a social share -> award points if valid."""
        rule     = get_object_or_404(SocialShareReward, pk=pk, is_active=True)
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')

        share_url = request.data.get('share_url', '')
        platform  = request.data.get('platform', rule.platform)

        # Daily limit check
        from django.utils import timezone
        today_count = CustomerSocialAction.objects.filter(
            customer=customer,
            share_reward=rule,
            created_at__date=timezone.now().date(),
        ).count()
        if today_count >= rule.max_per_day:
            return Response(
                {'error': f'Daily share limit ({rule.max_per_day}) reached.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from ...services.social.SocialShareService import SocialShareService
            action_record = SocialShareService.track_share(
                customer=customer, rule=rule,
                share_url=share_url, platform=platform,
            )
            return Response({
                'status': 'tracked',
                'points_awarded': str(action_record.points_awarded),
                'platform': platform,
                'message': f'Earned {action_record.points_awarded} points for sharing! 🎉',
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='my-shares')
    def my_shares(self, request):
        """Customer's social share history."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'shares': []})
        qs = CustomerSocialAction.objects.filter(
            customer=customer
        ).select_related('share_reward').order_by('-created_at')[:50]
        return Response(CustomerSocialActionSerializer(qs, many=True).data)


# ─── Review Reward ────────────────────────────────────────────────────────────

class ReviewViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /reviews/rules/            -- active review reward rules
    POST /reviews/submit/           -- submit a product/service review
    GET  /reviews/my-reviews/       -- customer's review history
    GET  /reviews/admin/pending/    -- admin: reviews awaiting approval
    POST /reviews/admin/{id}/approve/ -- approve + award points
    POST /reviews/admin/{id}/reject/  -- reject review
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = ReviewRewardSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return ReviewReward.objects.filter(is_active=True)

    @action(detail=False, methods=['post'], url_path='submit')
    def submit(self, request):
        """Customer submits a review."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')

        serializer = CustomerReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if already reviewed same product/order
        existing = CustomerReview.objects.filter(
            customer=customer,
            product_id=serializer.validated_data.get('product_id'),
        ).first()
        if existing:
            return Response(
                {'error': 'You have already reviewed this product.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        review = serializer.save(
            customer=customer,
            tenant=getattr(customer, 'tenant', None),
            status='pending',
        )
        return Response({
            'status':    'submitted',
            'review_id': review.id,
            'message':   'Review submitted! Points will be awarded after approval.',
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='my-reviews')
    def my_reviews(self, request):
        """Customer's submitted reviews."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'reviews': []})
        qs = CustomerReview.objects.filter(
            customer=customer
        ).order_by('-created_at')[:50]
        return Response(CustomerReviewSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='admin/pending',
            permission_classes=[IsLoyaltyAdmin])
    def admin_pending(self, request):
        """Admin: reviews pending approval."""
        qs = CustomerReview.objects.filter(
            status='pending'
        ).select_related('customer').order_by('-created_at')
        return Response({
            'count':   qs.count(),
            'reviews': CustomerReviewSerializer(qs[:50], many=True).data,
        })

    @action(detail=True, methods=['post'], url_path='approve',
            permission_classes=[IsLoyaltyAdmin])
    def admin_approve(self, request, pk=None):
        """Admin approves review + awards points."""
        review = get_object_or_404(CustomerReview, pk=pk, status='pending')
        try:
            from ...services.social.ReviewService import ReviewService
            result = ReviewService.approve(review=review, approved_by=str(request.user))
            return Response({
                'status': 'approved',
                'points_awarded': str(result.get('points_awarded', 0)),
            })
        except Exception as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], url_path='reject',
            permission_classes=[IsLoyaltyAdmin])
    def admin_reject(self, request, pk=None):
        """Admin rejects a review."""
        review  = get_object_or_404(CustomerReview, pk=pk, status='pending')
        reason  = request.data.get('reason', 'Does not meet review guidelines.')
        review.status             = 'rejected'
        review.rejection_reason   = reason
        review.save(update_fields=['status', 'rejection_reason'])
        return Response({'status': 'rejected'})


# ─── QR Code ─────────────────────────────────────────────────────────────────

class QRCodeViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /qr/earn-codes/            -- list active QR earn campaigns
    POST /qr/scan/                  -- customer scans a QR code -> earn points
    GET  /qr/my-scans/              -- scan history
    GET  /qr/admin/codes/           -- admin: all QR codes
    POST /qr/admin/generate/        -- admin: generate new QR code
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = QRCodeEarnSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return QRCodeEarn.objects.filter(is_active=True).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='scan')
    def scan(self, request):
        """Customer scans QR code -- validates and awards points."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')

        serializer = QRCodeScanSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']

        qr = QRCodeEarn.objects.filter(code=code, is_active=True).first()
        if not qr:
            return Response(
                {'error': 'Invalid or expired QR code.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check single-use
        if qr.single_use and QRCodeScan.objects.filter(qr_code=qr, customer=customer).exists():
            return Response(
                {'error': 'This QR code has already been used.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check max scans
        if qr.max_scans and QRCodeScan.objects.filter(qr_code=qr).count() >= qr.max_scans:
            return Response(
                {'error': 'This QR code has reached its maximum scan limit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from ...services.QRCodeService import QRCodeService
            scan_record = QRCodeService.process_scan(
                qr_code=qr,
                customer=customer,
                location=serializer.validated_data.get('location', ''),
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            return Response({
                'status': 'scanned',
                'points_awarded': str(scan_record.points_awarded),
                'qr_name': qr.name,
                'message': f'Earned {scan_record.points_awarded} points! ✅',
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='my-scans')
    def my_scans(self, request):
        """Customer's QR scan history."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'scans': []})
        qs = QRCodeScan.objects.filter(
            customer=customer
        ).select_related('qr_code').order_by('-scanned_at')[:50]
        return Response(QRCodeScanSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='admin/codes',
            permission_classes=[IsLoyaltyAdmin])
    def admin_codes(self, request):
        """Admin: list all QR codes with scan stats."""
        qs = QRCodeEarn.objects.all().order_by('-created_at')
        from django.db.models import Count
        qs = qs.annotate(total_scans=Count('scans'))
        return Response(QRCodeEarnSerializer(qs[:100], many=True).data)

    @action(detail=False, methods=['post'], url_path='admin/generate',
            permission_classes=[IsLoyaltyAdmin])
    def admin_generate(self, request):
        """Admin generates a new QR earn code."""
        try:
            from ...services.QRCodeService import QRCodeService
            qr = QRCodeService.generate(
                name=request.data.get('name', 'QR Campaign'),
                points_value=request.data.get('points_value', 0),
                earn_type=request.data.get('earn_type', 'fixed'),
                max_scans=request.data.get('max_scans'),
                single_use=request.data.get('single_use', False),
                valid_from=request.data.get('valid_from'),
                valid_until=request.data.get('valid_until'),
                tenant_id=request.data.get('tenant_id'),
            )
            return Response(QRCodeEarnSerializer(qr).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return self.err(str(e))
