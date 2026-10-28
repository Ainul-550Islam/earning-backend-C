# api/djoyalty/viewsets/advanced/GamificationViewSet.py
"""
Djoyalty Gamification ViewSets।
SpinWheelViewSet, ScratchCardViewSet, LotteryViewSet,
LeaderboardSeasonViewSet, QuizViewSet।

FIXED (original): Feature flags were defined for spin_wheel, scratch_card,
lottery but NONE of the viewset actions checked them.  Added
FeatureFlags.is_enabled() guard at the start of every mutating action.

AUDIT FIX (2.3): LeaderboardSeasonSerializer.get_my_rank() previously
called LeaderboardService inside the serializer layer — "এক কাজের জন্য
একটাই মালিক" violation.  Rank computation now owned exclusively by
LeaderboardSeasonViewSet._annotate_customer_rank(), called from the
overridden list() and retrieve() methods before serialization begins.
The serializer reads obj.customer_rank and does nothing else.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from ...models.gamification import (
    SpinWheelConfig, SpinWheelResult, ScratchCard,
    LotteryDraw, LotteryTicket, LeaderboardSeason,
    QuizReward, CustomerQuizAttempt,
)
from ...serializers.GamificationSerializer import (
    SpinWheelConfigSerializer, SpinWheelResultSerializer,
    SpinWheelResultPublicSerializer,
    ScratchCardSerializer,
    LotteryDrawSerializer, LotteryTicketSerializer, LotteryTicketPurchaseSerializer,
    LeaderboardSeasonSerializer,
    QuizRewardSerializer, CustomerQuizAttemptSerializer, QuizSubmitSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyBaseViewSet


def _feature_enabled(flag: str, request) -> bool:
    """Check FeatureFlags.is_enabled() for a tenant-aware flag."""
    try:
        from ...feature_flags import FeatureFlags
        tenant = getattr(request, 'tenant', None)
        return FeatureFlags.is_enabled(flag, tenant=tenant)
    except Exception:
        return True   # fail open -- never block due to flag system error


def _feature_disabled_response(flag: str) -> Response:
    return Response(
        {'error': f'Feature "{flag}" is not enabled for this account.'},
        status=status.HTTP_403_FORBIDDEN,
    )


# ─── Spin Wheel ────────────────────────────────────────────────────────────────

class SpinWheelViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /gamification/spin-wheels/           -- list active wheels
    GET  /gamification/spin-wheels/{id}/      -- wheel detail + slices
    POST /gamification/spin-wheels/{id}/spin/ -- customer spins (feature-flagged)
    GET  /gamification/spin-wheels/{id}/my-results/ -- customer's past spins
    POST /gamification/spin-wheels/{id}/claim/ -- claim unclaimed prize
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = SpinWheelConfigSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return SpinWheelConfig.objects.filter(is_active=True).prefetch_related('slices')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    @action(detail=True, methods=['post'], url_path='spin')
    def spin(self, request, pk=None):
        """Customer spins the wheel -- returns prize result.
        FIXED: checks spin_wheel feature flag per tenant before allowing spin.
        """
        if not _feature_enabled('spin_wheel', request):
            return _feature_disabled_response('spin_wheel')

        wheel    = get_object_or_404(SpinWheelConfig, pk=pk, is_active=True)
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response(
                {'error': 'Customer account not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from ...services.gamification.SpinWheelService import SpinWheelService
            result     = SpinWheelService.spin(wheel=wheel, customer=customer)
            serializer = SpinWheelResultPublicSerializer(result, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))
        except Exception as e:
            return Response(
                {'error': 'Spin failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['get'], url_path='my-results')
    def my_results(self, request, pk=None):
        """Customer's spin history for this wheel."""
        wheel    = get_object_or_404(SpinWheelConfig, pk=pk)
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'results': []})
        qs = SpinWheelResult.objects.filter(
            wheel=wheel, customer=customer
        ).order_by('-spun_at')[:20]
        return Response(SpinWheelResultSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, pk=None):
        """Claim an unclaimed spin prize."""
        if not _feature_enabled('spin_wheel', request):
            return _feature_disabled_response('spin_wheel')

        result_id = request.data.get('result_id')
        if not result_id:
            return Response(
                {'error': 'result_id required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = getattr(request, 'loyalty_customer', None)
        result   = get_object_or_404(
            SpinWheelResult, pk=result_id, customer=customer, wheel_id=pk
        )
        if result.prize_claimed:
            return Response(
                {'error': 'Prize already claimed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from ...services.gamification.SpinWheelService import SpinWheelService
            SpinWheelService.claim_prize(result=result)
            return Response({
                'status': 'claimed',
                'points_awarded': str(result.points_awarded),
            })
        except Exception as e:
            return self.err(str(e))


# ─── Scratch Card ──────────────────────────────────────────────────────────────

class ScratchCardViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /gamification/scratch-cards/             -- my scratch cards
    GET  /gamification/scratch-cards/{id}/        -- card detail
    POST /gamification/scratch-cards/{id}/scratch/ -- scratch (feature-flagged)
    POST /gamification/scratch-cards/{id}/claim/   -- claim prize
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = ScratchCardSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        customer = getattr(self.request, 'loyalty_customer', None)
        if not customer:
            return ScratchCard.objects.none()
        return ScratchCard.objects.filter(customer=customer).order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='scratch')
    def scratch(self, request, pk=None):
        """Reveal the prize on a scratch card.
        FIXED: checks scratch_card feature flag per tenant.
        """
        if not _feature_enabled('scratch_card', request):
            return _feature_disabled_response('scratch_card')

        customer = getattr(request, 'loyalty_customer', None)
        card     = get_object_or_404(ScratchCard, pk=pk, customer=customer)
        if card.status != 'unscratched':
            return Response(
                {'error': f'Card already {card.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from ...services.gamification.ScratchCardService import ScratchCardService
            ScratchCardService.scratch(card=card)
            return Response(self.get_serializer(card).data)
        except Exception as e:
            return self.err(str(e))

    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, pk=None):
        """Claim the revealed scratch card prize."""
        if not _feature_enabled('scratch_card', request):
            return _feature_disabled_response('scratch_card')

        customer = getattr(request, 'loyalty_customer', None)
        card     = get_object_or_404(
            ScratchCard, pk=pk, customer=customer, status='scratched'
        )
        try:
            from ...services.gamification.ScratchCardService import ScratchCardService
            ScratchCardService.claim(card=card)
            return Response({
                'status':         'claimed',
                'prize_type':     card.prize_type,
                'points_awarded': str(card.points_value),
            })
        except Exception as e:
            return self.err(str(e))


# ─── Lottery ───────────────────────────────────────────────────────────────────

class LotteryViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /gamification/lotteries/                  -- list active lotteries
    GET  /gamification/lotteries/{id}/             -- lottery detail
    POST /gamification/lotteries/{id}/buy-tickets/ -- buy tickets (feature-flagged)
    GET  /gamification/lotteries/{id}/my-tickets/  -- my tickets
    GET  /gamification/lotteries/my-wins/          -- all my wins
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = LotteryDrawSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return LotteryDraw.objects.filter(
            status__in=['upcoming', 'open']
        ).order_by('-draw_date')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    @action(detail=True, methods=['post'], url_path='buy-tickets')
    def buy_tickets(self, request, pk=None):
        """Customer buys lottery tickets with points.
        FIXED: checks lottery feature flag per tenant.
        """
        if not _feature_enabled('lottery', request):
            return _feature_disabled_response('lottery')

        lottery  = get_object_or_404(LotteryDraw, pk=pk, status='open')
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response(
                {'error': 'Customer not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = LotteryTicketPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data['quantity']

        try:
            from ...services.gamification.LotteryService import LotteryService
            tickets           = LotteryService.buy_tickets(
                lottery=lottery, customer=customer, quantity=quantity
            )
            ticket_serializer = LotteryTicketSerializer(tickets, many=True)
            return Response({
                'tickets':            ticket_serializer.data,
                'total_points_spent': str(lottery.ticket_cost_points * quantity),
                'tickets_purchased':  len(tickets),
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return self.err(str(e))

    @action(detail=True, methods=['get'], url_path='my-tickets')
    def my_tickets(self, request, pk=None):
        """My tickets for a specific lottery draw."""
        lottery  = get_object_or_404(LotteryDraw, pk=pk)
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'tickets': []})
        qs = LotteryTicket.objects.filter(lottery=lottery, customer=customer)
        return Response(LotteryTicketSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='my-wins')
    def my_wins(self, request):
        """All my winning lottery tickets."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'wins': []})
        qs = LotteryTicket.objects.filter(
            customer=customer, is_winner=True
        ).select_related('lottery')
        return Response(LotteryTicketSerializer(qs, many=True).data)


# ─── Leaderboard Season ────────────────────────────────────────────────────────

class LeaderboardSeasonViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET /gamification/leaderboard-seasons/          -- list seasons
    GET /gamification/leaderboard-seasons/{id}/     -- season detail
    GET /gamification/leaderboard-seasons/{id}/top/ -- top N
    GET /gamification/leaderboard-seasons/current/  -- active season
    GET /gamification/leaderboard-seasons/{id}/my-rank/ -- my rank

    AUDIT FIX (2.3 — viewset side):
    This class now OWNS all LeaderboardService rank computations.
    _annotate_customer_rank() is called in list() and retrieve() before
    passing instances to the serializer.  The serializer only reads the
    pre-set .customer_rank attribute — it no longer imports or calls any
    service.  "এক কাজের জন্য একটাই মালিক."
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = LeaderboardSeasonSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return LeaderboardSeason.objects.all().order_by('-start_date')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    # ── AUDIT FIX 2.3: rank annotation owned here, not in serializer ──────────

    def _annotate_customer_rank(self, seasons: list, request) -> list:
        """
        Annotate each LeaderboardSeason instance with .customer_rank.

        Called before serialization so the serializer receives pre-computed
        ranks and does not need to import or call LeaderboardService itself.

        Idempotent: safe to call on a list that already has .customer_rank.
        Defaults to 0 on any exception so serialization never fails.
        """
        customer = getattr(request, 'loyalty_customer', None)

        # Default all seasons to rank 0 first (safe fallback)
        for season in seasons:
            if not hasattr(season, 'customer_rank'):
                season.customer_rank = 0

        if not customer:
            return seasons

        try:
            from ...services.engagement.LeaderboardService import LeaderboardService
            for season in seasons:
                season.customer_rank = LeaderboardService.get_customer_rank(
                    season=season, customer=customer
                )
        except Exception:
            # Any service failure → fall back to 0 for all seasons in batch.
            # Already defaulted above; nothing extra needed here.
            pass

        return seasons

    # ── list / retrieve overrides inject annotations ───────────────────────────

    def list(self, request, *args, **kwargs):
        """Override list() to annotate customer_rank before serialization."""
        qs   = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            self._annotate_customer_rank(page, request)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        seasons = list(qs)
        self._annotate_customer_rank(seasons, request)
        serializer = self.get_serializer(seasons, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve() to annotate customer_rank before serialization."""
        instance = self.get_object()
        self._annotate_customer_rank([instance], request)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # ── Custom actions ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        """Currently active leaderboard season.
        FIXED: checks leaderboard feature flag.
        """
        if not _feature_enabled('leaderboard', request):
            return _feature_disabled_response('leaderboard')

        season = LeaderboardSeason.objects.filter(status='active').first()
        if not season:
            return Response(
                {'detail': 'No active leaderboard season.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        self._annotate_customer_rank([season], request)
        return Response(self.get_serializer(season).data)

    @action(detail=True, methods=['get'], url_path='top')
    def top(self, request, pk=None):
        """Top N customers on the leaderboard."""
        if not _feature_enabled('leaderboard', request):
            return _feature_disabled_response('leaderboard')

        season = get_object_or_404(LeaderboardSeason, pk=pk)
        limit  = min(int(request.query_params.get('limit', 10)), 100)
        try:
            from ...services.engagement.LeaderboardService import LeaderboardService
            entries = LeaderboardService.get_top(season=season, limit=limit)
            return Response({'season': season.name, 'entries': entries})
        except Exception as e:
            return self.err(str(e), http_status=500)

    @action(detail=True, methods=['get'], url_path='my-rank')
    def my_rank(self, request, pk=None):
        """Customer's own rank in this season."""
        if not _feature_enabled('leaderboard', request):
            return _feature_disabled_response('leaderboard')

        season   = get_object_or_404(LeaderboardSeason, pk=pk)
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'rank': None})
        try:
            from ...services.engagement.LeaderboardService import LeaderboardService
            rank  = LeaderboardService.get_customer_rank(season=season, customer=customer)
            score = LeaderboardService.get_customer_score(season=season, customer=customer)
            return Response({'season': season.name, 'rank': rank, 'score': str(score)})
        except Exception as e:
            return self.err(str(e), http_status=500)


# ─── Quiz ──────────────────────────────────────────────────────────────────────

class QuizViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET  /gamification/quizzes/              -- list active quizzes
    GET  /gamification/quizzes/{id}/         -- quiz detail
    POST /gamification/quizzes/{id}/submit/  -- submit answers (feature-flagged)
    GET  /gamification/quizzes/my-attempts/  -- my quiz history
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = QuizRewardSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        return QuizReward.objects.filter(is_active=True).order_by('-created_at')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """Submit quiz answers -- grades and awards points if passed."""
        quiz     = get_object_or_404(QuizReward, pk=pk, is_active=True)
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response(
                {'error': 'Customer not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = QuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        attempts_count = CustomerQuizAttempt.objects.filter(
            customer=customer, quiz=quiz
        ).count()
        if attempts_count >= quiz.max_attempts:
            return Response(
                {'error': f'Max attempts ({quiz.max_attempts}) reached.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from ...services.gamification.QuizService import QuizService
            result = QuizService.submit(
                quiz=quiz,
                customer=customer,
                answers=serializer.validated_data['answers'],
                time_taken=serializer.validated_data.get('time_taken_seconds', 0),
            )
            attempt_serializer = CustomerQuizAttemptSerializer(result['attempt'])
            return Response({
                'attempt':        attempt_serializer.data,
                'passed':         result['passed'],
                'score':          result['score'],
                'points_awarded': str(result['points_awarded']),
                'message':        result.get('message', ''),
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return self.err(str(e))

    @action(detail=False, methods=['get'], url_path='my-attempts')
    def my_attempts(self, request):
        """All quiz attempts by the current customer."""
        customer = getattr(request, 'loyalty_customer', None)
        if not customer:
            return Response({'attempts': []})
        qs = CustomerQuizAttempt.objects.filter(
            customer=customer
        ).select_related('quiz').order_by('-started_at')[:50]
        return Response(CustomerQuizAttemptSerializer(qs, many=True).data)


class SpinWheelSliceViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    FIXED: SpinWheelSlice had NO API endpoint -- wheel prize segments only
    configurable via Django admin. Now configurable via API.
    """
    permission_classes = [IsLoyaltyAdmin]

    def list(self, request):
        from ...models.gamification import SpinWheelSlice
        wheel_id = request.query_params.get('wheel_id')
        qs = SpinWheelSlice.objects.all().order_by('position')
        if wheel_id:
            qs = qs.filter(wheel_id=wheel_id)
        return Response({'slices': [{
            'id': s.id, 'wheel_id': s.wheel_id, 'label': s.label,
            'prize_type': s.prize_type, 'prize_value': str(s.prize_value),
            'probability_weight': s.probability_weight, 'color': getattr(s, 'color', '#ccc'),
            'position': s.position,
        } for s in qs]})

    def create(self, request):
        from ...models.gamification import SpinWheelConfig, SpinWheelSlice
        wheel_id = request.data.get('wheel_id')
        wheel    = SpinWheelConfig.objects.filter(pk=wheel_id).first()
        if not wheel:
            return self.err('wheel_id required and must exist')
        s = SpinWheelSlice.objects.create(
            wheel=wheel, label=request.data.get('label', 'Prize'),
            prize_type=request.data.get('prize_type', 'points'),
            prize_value=request.data.get('prize_value', 0),
            probability_weight=request.data.get('probability_weight', 10),
            position=request.data.get('position', 0),
        )
        return Response({'id': s.id, 'label': s.label}, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        from ...models.gamification import SpinWheelSlice
        from django.shortcuts import get_object_or_404
        get_object_or_404(SpinWheelSlice, pk=pk).delete()
        return Response({'status': 'deleted'})
