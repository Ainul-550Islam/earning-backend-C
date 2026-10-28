# api/djoyalty/viewsets/advanced/AIPersonalizationViewSet.py
"""
Djoyalty AI Personalization ViewSets -- NEW।
CustomerAIProfileViewSet, PersonalizedOfferViewSet,
AIRecommendationViewSet, ChurnAlertViewSet।

55KB+ of AI logic fully built -- zero API surface until now।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ...models.ai_personalization import (
    CustomerAIProfile, PersonalizedOffer,
    AIRecommendation, ChurnAlert,
)
from ...serializers.AIPersonalizationSerializer import (
    CustomerAIProfileSerializer, CustomerAIProfileSummarySerializer,
    PersonalizedOfferSerializer, PersonalizedOfferClaimSerializer,
    PersonalizedOfferDismissSerializer,
    AIRecommendationSerializer, AIRecommendationClickSerializer,
    ChurnAlertSerializer, ChurnAlertActionSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyBaseViewSet


# ─── Customer AI Profile ───────────────────────────────────────────────────────

class CustomerAIProfileViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET /ai/profiles/            -- admin: list all profiles (filterable)
    GET /ai/profiles/{id}/       -- admin: full profile
    GET /ai/profiles/my-profile/ -- customer: own AI profile summary
    POST /ai/profiles/{id}/recompute/ -- admin: trigger recompute
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = CustomerAIProfileSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        qs = CustomerAIProfile.objects.all().select_related('customer')
        # Admin filters
        risk  = self.request.query_params.get('churn_risk_level')
        seg   = self.request.query_params.get('rfm_segment')
        if risk:
            qs = qs.filter(churn_risk_level=risk)
        if seg:
            qs = qs.filter(rfm_segment=seg)
        return qs.order_by('-churn_probability')

    def get_permissions(self):
        if self.action == 'my_profile':
            return [IsAuthenticated()]
        return [IsLoyaltyAdmin()]

    @action(detail=False, methods=['get'], url_path='my-profile',
            permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        """Customer sees their own AI profile (summary only)."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        profile = CustomerAIProfile.objects.filter(customer=customer).first()
        if not profile:
            return Response({'detail': 'AI profile not yet computed.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CustomerAIProfileSummarySerializer(profile)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='recompute',
            permission_classes=[IsLoyaltyAdmin])
    def recompute(self, request, pk=None):
        """Admin triggers immediate recompute of a customer's AI profile."""
        profile  = get_object_or_404(CustomerAIProfile, pk=pk)
        customer = profile.customer
        try:
            from ...services.AIPersonalizationService import AIPersonalizationService
            AIPersonalizationService.compute_customer_profile(customer=customer)
            profile.refresh_from_db()
            serializer = self.get_serializer(profile)
            return Response({'status': 'recomputed', 'profile': serializer.data})
        except Exception as e:
            return self.err(str(e), http_status=500)


# ─── Personalized Offers ───────────────────────────────────────────────────────

class PersonalizedOfferViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /ai/offers/              -- customer: my active offers
    GET  /ai/offers/{id}/         -- offer detail
    POST /ai/offers/{id}/claim/   -- claim offer
    POST /ai/offers/{id}/view/    -- mark as viewed (track impression)
    POST /ai/offers/{id}/dismiss/ -- dismiss offer
    GET  /ai/offers/admin/        -- admin: all offers (filterable)
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = PersonalizedOfferSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        customer = getattr(self.request, 'loyalty_customer', None)
        if not customer:
            return PersonalizedOffer.objects.none()
        return PersonalizedOffer.objects.filter(
            customer=customer,
            status='active',
            valid_until__gte=timezone.now(),
        ).order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='view')
    def mark_viewed(self, request, pk=None):
        """Track offer impression -- called when offer card rendered."""
        customer = getattr(request, 'loyalty_customer', None)
        offer    = get_object_or_404(PersonalizedOffer, pk=pk, customer=customer)
        if not offer.viewed_at:
            offer.viewed_at = timezone.now()
            offer.save(update_fields=['viewed_at'])
        return Response({'viewed': True})

    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, pk=None):
        """Customer claims a personalized offer."""
        customer = getattr(request, 'loyalty_customer', None)
        offer    = get_object_or_404(
            PersonalizedOffer, pk=pk, customer=customer, status='active'
        )
        serializer = PersonalizedOfferClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if offer.valid_until and offer.valid_until < timezone.now():
            return self.err('Offer has expired.')

        try:
            from ...services.AIPersonalizationService import AIPersonalizationService
            result = AIPersonalizationService.claim_offer(
                offer=offer,
                customer=customer,
                reference=serializer.validated_data.get('reference', ''),
            )
            return Response({
                'status': 'claimed',
                'points_awarded': str(result.get('points_awarded', 0)),
                'message': result.get('message', 'Offer claimed successfully!'),
            })
        except ValueError as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], url_path='dismiss')
    def dismiss(self, request, pk=None):
        """Customer dismisses an offer -- improves AI recommendations."""
        customer = getattr(request, 'loyalty_customer', None)
        offer    = get_object_or_404(PersonalizedOffer, pk=pk, customer=customer, status='active')
        serializer = PersonalizedOfferDismissSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        offer.status       = 'dismissed'
        offer.dismissed_at = timezone.now()
        offer.save(update_fields=['status', 'dismissed_at'])
        return Response({'status': 'dismissed'})

    @action(detail=False, methods=['get'], url_path='admin',
            permission_classes=[IsLoyaltyAdmin])
    def admin_list(self, request):
        """Admin view -- all offers, filterable by trigger/status/risk."""
        qs = PersonalizedOffer.objects.all().select_related('customer')
        trigger = request.query_params.get('trigger')
        status_ = request.query_params.get('status')
        if trigger:
            qs = qs.filter(trigger=trigger)
        if status_:
            qs = qs.filter(status=status_)
        qs = qs.order_by('-created_at')
        page       = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)


# ─── AI Recommendations ────────────────────────────────────────────────────────

class AIRecommendationViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /ai/recommendations/              -- customer: my recommendations
    POST /ai/recommendations/{id}/click/   -- track click
    GET  /ai/recommendations/refresh/      -- regenerate my recommendations
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = AIRecommendationSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        customer = getattr(self.request, 'loyalty_customer', None)
        if not customer:
            return AIRecommendation.objects.none()
        return AIRecommendation.objects.filter(
            customer=customer,
        ).filter(
            models_expires_at_null_or_gte=True  # simplified
        ).order_by('position', '-relevance_score')[:20]

    def get_queryset(self):
        customer = getattr(self.request, 'loyalty_customer', None)
        if not customer:
            return AIRecommendation.objects.none()
        from django.db.models import Q
        return AIRecommendation.objects.filter(
            customer=customer,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        ).order_by('position', '-relevance_score')[:20]

    @action(detail=True, methods=['post'], url_path='click')
    def click(self, request, pk=None):
        """Track recommendation click."""
        customer   = getattr(request, 'loyalty_customer', None)
        rec        = get_object_or_404(AIRecommendation, pk=pk, customer=customer)
        if not rec.is_clicked:
            rec.is_clicked = True
            rec.clicked_at = timezone.now()
            rec.save(update_fields=['is_clicked', 'clicked_at'])
        return Response({'clicked': True, 'action_url': rec.action_url})

    @action(detail=False, methods=['post'], url_path='refresh')
    def refresh(self, request):
        """Trigger AI recommendation refresh for current customer."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')
        try:
            from ...services.AIPersonalizationService import AIPersonalizationService
            AIPersonalizationService.generate_recommendations(customer=customer)
            return Response({'status': 'refreshed'})
        except Exception as e:
            return self.err(str(e), http_status=500)


# ─── Churn Alerts ─────────────────────────────────────────────────────────────

class ChurnAlertViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    Admin only:
    GET  /ai/churn-alerts/              -- list unresolved alerts
    GET  /ai/churn-alerts/{id}/         -- alert detail
    POST /ai/churn-alerts/{id}/action/  -- take action (send offer / resolve)
    GET  /ai/churn-alerts/summary/      -- risk level counts
    """
    permission_classes = [IsLoyaltyAdmin]
    serializer_class   = ChurnAlertSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        qs = ChurnAlert.objects.filter(is_resolved=False).select_related('customer', 'offer')
        risk = self.request.query_params.get('risk_level')
        if risk:
            qs = qs.filter(risk_level=risk)
        return qs.order_by('-churn_probability', '-detected_at')

    @action(detail=True, methods=['post'], url_path='action')
    def take_action(self, request, pk=None):
        """Admin takes action on a churn alert."""
        alert      = get_object_or_404(ChurnAlert, pk=pk)
        serializer = ChurnAlertActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_type = serializer.validated_data['action']
        note        = serializer.validated_data.get('note', '')

        try:
            from ...services.AIPersonalizationService import AIPersonalizationService
            result = AIPersonalizationService.handle_churn_alert_action(
                alert=alert,
                action=action_type,
                performed_by=str(request.user),
                note=note,
            )
            alert.refresh_from_db()
            return Response({
                'status': 'action_taken',
                'action': action_type,
                'alert': ChurnAlertSerializer(alert).data,
                'result': result,
            })
        except Exception as e:
            return self.err(str(e), http_status=500)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Dashboard summary: count by risk level."""
        from django.db.models import Count
        counts = ChurnAlert.objects.filter(is_resolved=False).values(
            'risk_level'
        ).annotate(count=Count('id'))
        return Response({
            'total_unresolved': ChurnAlert.objects.filter(is_resolved=False).count(),
            'by_risk_level': {item['risk_level']: item['count'] for item in counts},
        })
