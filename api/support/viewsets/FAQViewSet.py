# api/support/viewsets/FAQViewSet.py  — WORLD #1
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.db.models import Q

logger = logging.getLogger(__name__)


class FAQViewSet(viewsets.ModelViewSet):
    """
    GET    /api/support/faqs/             — public list (grouped by category)
    POST   /api/support/faqs/             — admin create
    GET    /api/support/faqs/{id}/        — detail + increment views
    PUT    /api/support/faqs/{id}/        — admin update
    DELETE /api/support/faqs/{id}/        — admin delete
    POST   /api/support/faqs/{id}/helpful/  — vote helpful/not helpful
    GET    /api/support/faqs/grouped/       — grouped by category
    GET    /api/support/faqs/search/        — search FAQs
    """
    permission_classes = [AllowAny]

    def get_queryset(self):
        from api.support.models import FAQ
        qs = FAQ.objects.filter(is_active=True)
        cat = self.request.query_params.get('category')
        q   = self.request.query_params.get('q') or self.request.query_params.get('search')
        if cat: qs = qs.filter(category=cat)
        if q:   qs = qs.filter(Q(question__icontains=q)|Q(answer__icontains=q))
        return qs.order_by('order','-created_at')

    def get_serializer_class(self):
        from api.support.serializers import FAQSerializer
        return FAQSerializer

    def get_permissions(self):
        if self.action in ('create','update','partial_update','destroy'):
            return [IsAuthenticated(), IsAdminUser()]
        return [AllowAny()]

    def retrieve(self, request, *args, **kwargs):
        from api.support.serializers import FAQSerializer
        faq = self.get_object()
        faq.view_count += 1
        faq.save(update_fields=['view_count'])
        return Response(FAQSerializer(faq).data)

    def list(self, request, *args, **kwargs):
        from api.support.serializers import FAQSerializer
        qs   = self.get_queryset()
        flat = FAQSerializer(qs, many=True).data
        grouped = {}
        for faq in qs:
            grouped.setdefault(faq.category, []).append({
                'id': faq.id, 'question': faq.question, 'answer': faq.answer
            })
        return Response({'results': flat, 'grouped': grouped, 'count': len(flat)})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def helpful(self, request, pk=None):
        faq = self.get_object()
        is_helpful = request.data.get('helpful', True)
        if is_helpful:
            faq.helpful_yes += 1
        else:
            faq.helpful_no += 1
        faq.save(update_fields=['helpful_yes','helpful_no'])
        return Response({'success': True, 'ratio': faq.helpful_ratio})

    @action(detail=False, methods=['get'])
    def grouped(self, request):
        from api.support.models import FAQ
        from api.support.serializers import FAQSerializer
        qs = FAQ.objects.filter(is_active=True).order_by('order')
        grouped = {}
        for faq in qs:
            grouped.setdefault(faq.category, []).append(FAQSerializer(faq).data)
        return Response(grouped)