# api/support/viewset.py
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
from django.utils import timezone

from .models import SupportTicket, FAQ, SupportAgent, CannedResponse, KBCategory, KBArticle, ChatSession
from .serializers import SupportTicketSerializer, FAQSerializer, SupportSettingsSerializer
from .permissions import IsSupportAgent
from .throttling import TicketCreateThrottle

logger = logging.getLogger(__name__)


class SupportTicketViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ['created_at', 'updated_at', 'priority']
    ordering           = ['-created_at']

    def get_queryset(self):
        from .filters import SupportTicketFilter
        if self.request.user.is_staff:
            qs = SupportTicket.objects.select_related('user', 'assigned_to')
        else:
            qs = SupportTicket.objects.filter(user=self.request.user)
        if self.request.query_params.get('assigned_to') == 'me':
            qs = qs.filter(assigned_to=self.request.user)
        return SupportTicketFilter.apply(qs, self.request.query_params)

    def get_serializer_class(self):
        return SupportTicketSerializer

    def perform_create(self, serializer):
        from .services import ticket_service
        from .hooks import ticket_hooks
        data = {**serializer.validated_data, 'channel': self.request.data.get('channel', 'web')}
        data = ticket_hooks.pre_create(data, self.request.user)
        ticket = ticket_service.create(self.request.user, data)
        serializer.instance = ticket

    def list(self, request, *args, **kwargs):
        qs       = self.get_queryset()
        page     = int(request.query_params.get('page', 1))
        per_page = min(int(request.query_params.get('per_page', 20)), 100)
        total    = qs.count()
        start    = (page-1) * per_page
        data     = SupportTicketSerializer(qs[start:start+per_page], many=True, context={'request':request}).data
        return Response({'results':data, 'count':total, 'page':page, 'has_next':start+per_page<total})

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        from .services import ticket_service
        ticket  = self.get_object()
        content = request.data.get('content', '').strip()
        if not content:
            return Response({'error': 'content required.'}, status=400)
        if not request.user.is_staff and ticket.user != request.user:
            return Response({'detail': 'Access denied.'}, status=403)
        msg = ticket_service.add_message(
            str(ticket.ticket_id), request.user, content,
            is_agent=request.user.is_staff,
            is_internal=request.data.get('is_internal', False),
        )
        from .serializers import TicketMessageSerializer
        return Response(TicketMessageSerializer(msg).data, status=201)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def resolve(self, request, pk=None):
        from .services import ticket_service
        ticket = ticket_service.resolve(pk, request.user, request.data.get('resolution', ''))
        return Response({'success': True, 'ticket_id': ticket.ticket_id})

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        from .validators import validate_csat_rating
        ticket = self.get_object()
        if ticket.user != request.user:
            return Response({'detail': 'Not your ticket.'}, status=403)
        try:
            score = validate_csat_rating(request.data.get('score') or request.data.get('rating'))
        except Exception as e:
            return Response({'error': str(e)}, status=400)
        ticket.satisfaction_rating = score
        ticket.rating_comment      = request.data.get('comment', '')
        ticket.rated_at            = timezone.now()
        ticket.save(update_fields=['satisfaction_rating', 'rating_comment', 'rated_at'])
        return Response({'success': True})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def escalate(self, request, pk=None):
        ticket = self.get_object()
        if ticket.escalated:
            return Response({'detail': 'Already escalated.'}, status=400)
        ticket.escalated    = True
        ticket.escalated_at = timezone.now()
        ticket.priority     = 'urgent'
        ticket.save(update_fields=['escalated', 'escalated_at', 'priority'])
        return Response({'success': True})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdminUser])
    def stats(self, request):
        from .services import ticket_service
        return Response(ticket_service.get_stats())


class FAQViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs  = FAQ.objects.filter(is_active=True)
        q   = self.request.query_params.get('search') or self.request.query_params.get('q')
        cat = self.request.query_params.get('category')
        if q:   qs = qs.filter(Q(question__icontains=q) | Q(answer__icontains=q))
        if cat: qs = qs.filter(category=cat)
        return qs

    def get_serializer_class(self):
        return FAQSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsAdminUser()]
        return [AllowAny()]

    def retrieve(self, request, *args, **kwargs):
        faq = self.get_object()
        faq.view_count += 1
        faq.save(update_fields=['view_count'])
        return Response(FAQSerializer(faq).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def helpful(self, request, pk=None):
        faq = self.get_object()
        if request.data.get('helpful', True):
            faq.helpful_yes += 1
        else:
            faq.helpful_no += 1
        faq.save(update_fields=['helpful_yes', 'helpful_no'])
        return Response({'success': True, 'ratio': faq.helpful_ratio})

    @action(detail=False, methods=['get'])
    def grouped(self, request):
        grouped = {}
        for faq in self.get_queryset():
            grouped.setdefault(faq.category, []).append(
                {'id': faq.id, 'question': faq.question, 'answer': faq.answer}
            )
        return Response(grouped)