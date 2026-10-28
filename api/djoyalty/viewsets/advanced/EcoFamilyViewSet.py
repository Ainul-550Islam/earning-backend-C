# api/djoyalty/viewsets/advanced/EcoFamilyViewSet.py
"""
Djoyalty Eco/Family/Charity/Experience ViewSets -- NEW।
FamilyAccountViewSet, EcoViewSet, CharityViewSet,
ExperienceViewSet, ConsentViewSet, ReceiptViewSet।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ...models.family_eco import (
    FamilyAccount, FamilyMember,
    EcoAction, CustomerEcoAction, CustomerEcoStats,
    CharityCause, CharityDonation,
    ExperientialReward, ExperientialRegistration,
    CustomerConsent, ReceiptScan,
)
from ...serializers.EcoFamilySerializer import (
    FamilyAccountSerializer, FamilyMemberSerializer, FamilyInviteSerializer,
    EcoActionSerializer, CustomerEcoActionSerializer,
    EcoActionLogSerializer, CustomerEcoStatsSerializer,
    CharityCauseSerializer, CharityDonationSerializer, CharityDonateSerializer,
    ExperientialRewardSerializer, ExperientialRegistrationSerializer,
    ExperienceRegisterSerializer, ExperienceFeedbackSerializer,
    CustomerConsentSerializer, CustomerConsentUpdateSerializer,
    ReceiptScanSerializer, ReceiptSubmitSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyBaseViewSet


# ─── Family Account ────────────────────────────────────────────────────────────

class FamilyAccountViewSet(DjoyaltyBaseViewSet, viewsets.ModelViewSet):
    """
    GET    /family/                      -- my family account(s)
    POST   /family/                      -- create family account
    GET    /family/{id}/                 -- account detail
    POST   /family/{id}/invite/          -- invite member
    DELETE /family/{id}/members/{mid}/   -- remove member
    POST   /family/{id}/leave/           -- member leaves account
    GET    /family/{id}/transactions/    -- shared transaction history
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = FamilyAccountSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        customer = getattr(self.request, 'loyalty_customer', None)
        if not customer:
            return FamilyAccount.objects.none()
        # Return accounts where customer is owner or member
        from django.db.models import Q
        return FamilyAccount.objects.filter(
            Q(owner=customer) | Q(members__customer=customer, members__is_active=True)
        ).distinct().select_related('owner').prefetch_related('members__customer')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        customer = getattr(self.request, 'loyalty_customer', None)
        account  = serializer.save(owner=customer)
        # Auto-add owner as member
        FamilyMember.objects.create(
            family_account=account, customer=customer,
            role='owner', can_redeem=True, can_transfer=True,
        )

    @action(detail=True, methods=['post'], url_path='invite')
    def invite(self, request, pk=None):
        """Owner invites a new member."""
        account  = get_object_or_404(FamilyAccount, pk=pk)
        customer = getattr(request, 'loyalty_customer', None)
        if account.owner != customer:
            return self.forbidden('Only owner can invite members.')

        current_count = account.members.filter(is_active=True).count()
        if current_count >= account.max_members:
            return Response(
                {'error': f'Maximum members ({account.max_members}) reached.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = FamilyInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from ...services.FamilyAccountService import FamilyAccountService
            member = FamilyAccountService.invite_member(
                account=account,
                invited_by=customer,
                customer_code=serializer.validated_data.get('customer_code'),
                email=serializer.validated_data.get('email'),
                role=serializer.validated_data['role'],
            )
            return Response(FamilyMemberSerializer(member).data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], url_path='leave')
    def leave(self, request, pk=None):
        """Member leaves the family account."""
        account  = get_object_or_404(FamilyAccount, pk=pk)
        customer = getattr(request, 'loyalty_customer', None)
        if account.owner == customer:
            return self.err('Owner cannot leave. Transfer ownership first.')
        member = get_object_or_404(FamilyMember, family_account=account, customer=customer, is_active=True)
        member.is_active = False
        member.save(update_fields=['is_active'])
        return Response({'status': 'left'})

    @action(detail=True, methods=['get'], url_path='transactions')
    def transactions(self, request, pk=None):
        """Shared pool transaction history."""
        account = get_object_or_404(FamilyAccount, pk=pk)
        try:
            from ...services.FamilyAccountService import FamilyAccountService
            txns = FamilyAccountService.get_shared_transactions(account=account, limit=50)
            return Response(txns)
        except Exception as e:
            return self.err(str(e), http_status=500)


# ─── Eco ──────────────────────────────────────────────────────────────────────

class EcoViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /eco/actions/           -- list active eco actions
    POST /eco/actions/{id}/log/  -- log completion
    GET  /eco/my-stats/          -- my eco impact summary
    GET  /eco/my-history/        -- my eco action history
    GET  /eco/leaderboard/       -- eco points leaderboard
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = EcoActionSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return EcoAction.objects.filter(is_active=True).order_by('action_type')

    @action(detail=True, methods=['post'], url_path='log')
    def log_action(self, request, pk=None):
        """Log a completed eco action -- awards green points."""
        eco_action = get_object_or_404(EcoAction, pk=pk, is_active=True)
        customer   = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')

        serializer = EcoActionLogSerializer(data={**request.data, 'eco_action_id': pk})
        serializer.is_valid(raise_exception=True)

        try:
            from ...services.EcoLoyaltyService import EcoLoyaltyService
            record = EcoLoyaltyService.log_action(
                customer=customer,
                eco_action=eco_action,
                proof_url=serializer.validated_data.get('proof_url', ''),
                location=serializer.validated_data.get('location', ''),
            )
            return Response({
                'status': 'logged',
                'points_awarded': str(record.points_awarded),
                'co2_saved_kg': str(record.co2_saved_kg),
                'message': f'Earned {record.points_awarded} green points! 🌱',
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='my-stats')
    def my_stats(self, request):
        """Customer's total eco impact."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        stats, _ = CustomerEcoStats.objects.get_or_create(customer=customer)
        return Response(CustomerEcoStatsSerializer(stats).data)

    @action(detail=False, methods=['get'], url_path='my-history')
    def my_history(self, request):
        """Customer's eco action log."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'history': []})
        qs = CustomerEcoAction.objects.filter(
            customer=customer
        ).select_related('eco_action').order_by('-completed_at')[:50]
        return Response(CustomerEcoActionSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='leaderboard')
    def leaderboard(self, request):
        """Top eco customers by green points earned."""
        limit = min(int(request.query_params.get('limit', 10)), 50)
        top = CustomerEcoStats.objects.filter(
            total_eco_points__gt=0
        ).order_by('-total_eco_points').select_related('customer')[:limit]
        return Response([{
            'rank': i + 1,
            'customer_code': s.customer.code,
            'total_eco_points': str(s.total_eco_points),
            'co2_saved_kg': str(s.total_co2_saved_kg),
            'eco_tier': s.eco_tier,
        } for i, s in enumerate(top)])


# ─── Charity ──────────────────────────────────────────────────────────────────

class CharityViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /charity/causes/           -- list active causes
    GET  /charity/causes/{id}/      -- cause detail
    POST /charity/causes/{id}/donate/ -- donate points
    GET  /charity/my-donations/     -- my donation history
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = CharityCauseSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return CharityCause.objects.filter(is_active=True).order_by('-is_featured', 'name')

    @action(detail=True, methods=['post'], url_path='donate')
    def donate(self, request, pk=None):
        """Customer donates points to a charity."""
        cause    = get_object_or_404(CharityCause, pk=pk, is_active=True)
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')

        serializer = CharityDonateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data['points_to_donate'] < cause.min_donation_points:
            return Response({
                'error': f'Minimum donation is {cause.min_donation_points} points.'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            from ...services.CharityService import CharityService
            donation = CharityService.donate(
                cause=cause,
                customer=customer,
                points=serializer.validated_data['points_to_donate'],
                message=serializer.validated_data.get('message', ''),
                is_anonymous=serializer.validated_data.get('is_anonymous', False),
            )
            return Response({
                'status': 'donated',
                'donation_id': donation.id,
                'points_donated': str(donation.points_donated),
                'currency_value': str(donation.currency_value),
                'message': f'Thank you! You donated {donation.points_donated} points to {cause.name} ❤️',
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='my-donations')
    def my_donations(self, request):
        """Customer's full donation history."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'donations': []})
        qs = CharityDonation.objects.filter(
            customer=customer
        ).select_related('charity').order_by('-donated_at')[:50]
        return Response(CharityDonationSerializer(qs, many=True).data)


# ─── Experiential Rewards ─────────────────────────────────────────────────────

class ExperienceViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /experiences/                  -- list open experiences
    GET  /experiences/{id}/             -- detail
    POST /experiences/{id}/register/    -- register (redeem points)
    POST /experiences/{id}/feedback/    -- post-event feedback
    GET  /experiences/my-registrations/ -- my registrations
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = ExperientialRewardSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return ExperientialReward.objects.filter(
            is_active=True,
            status__in=['upcoming', 'open'],
        ).order_by('event_date')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    @action(detail=True, methods=['post'], url_path='register')
    def register(self, request, pk=None):
        """Register for an experience -- deducts points."""
        experience = get_object_or_404(ExperientialReward, pk=pk, is_active=True)
        customer   = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')

        if experience.slots_remaining <= 0:
            return self.err('No slots remaining.')

        if ExperientialRegistration.objects.filter(
            customer=customer, experience=experience,
            status__in=['registered', 'confirmed']
        ).exists():
            return self.err('Already registered.')

        serializer = ExperienceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            from ...services.ExperienceService import ExperienceService
            registration = ExperienceService.register(
                experience=experience,
                customer=customer,
                special_requests=serializer.validated_data.get('special_requests', ''),
            )
            return Response({
                'status': 'registered',
                'confirmation_code': registration.confirmation_code,
                'points_redeemed': str(registration.points_redeemed),
                'experience': experience.name,
                'event_date': str(experience.event_date),
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], url_path='feedback')
    def feedback(self, request, pk=None):
        """Submit post-event feedback and rating."""
        experience   = get_object_or_404(ExperientialReward, pk=pk)
        customer     = getattr(request, 'loyalty_customer', None)
        registration = get_object_or_404(
            ExperientialRegistration, experience=experience,
            customer=customer, status='attended',
        )
        serializer = ExperienceFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        registration.feedback_rating  = serializer.validated_data['rating']
        registration.feedback_comment = serializer.validated_data.get('comment', '')
        registration.save(update_fields=['feedback_rating', 'feedback_comment'])
        return Response({'status': 'feedback_submitted'})

    @action(detail=False, methods=['get'], url_path='my-registrations')
    def my_registrations(self, request):
        """All experience registrations for current customer."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'registrations': []})
        qs = ExperientialRegistration.objects.filter(
            customer=customer
        ).select_related('experience').order_by('-registered_at')
        return Response(ExperientialRegistrationSerializer(qs, many=True).data)


# ─── Consent ──────────────────────────────────────────────────────────────────

class ConsentViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET   /consent/          -- my current consent settings
    PATCH /consent/update/   -- update consent preferences
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = CustomerConsentSerializer

    def get_queryset(self):
        customer = getattr(self.request, 'loyalty_customer', None)
        if not customer:
            return CustomerConsent.objects.none()
        return CustomerConsent.objects.filter(customer=customer)

    @action(detail=False, methods=['patch'], url_path='update')
    def update_consents(self, request):
        """Bulk update consent preferences."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return self.not_found('Customer not found.')

        serializer = CustomerConsentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consents = serializer.validated_data['consents']
        now = timezone.now()

        updated = []
        for consent_type, is_granted in consents.items():
            obj, _ = CustomerConsent.objects.get_or_create(
                customer=customer, consent_type=consent_type,
                defaults={'source': 'web'},
            )
            obj.is_granted = is_granted
            obj.granted_at = now if is_granted else obj.granted_at
            obj.revoked_at = now if not is_granted else None
            obj.save(update_fields=['is_granted', 'granted_at', 'revoked_at'])
            updated.append(consent_type)

        return Response({'status': 'updated', 'updated': updated})
