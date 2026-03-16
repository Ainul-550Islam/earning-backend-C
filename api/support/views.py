# api/support/views.py  —  COMPLETE CRUD (all endpoints)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import SupportSettings, SupportTicket, FAQ
from .serializers import SupportSettingsSerializer, SupportTicketSerializer, FAQSerializer


# ═══════════════════════════════ SETTINGS ══════════════════════════════════════

@api_view(['GET', 'PUT', 'PATCH'])
def get_support_settings(request):
    """
    GET  /support/settings/  — public
    PUT  /support/settings/  — admin only  ✅ FIXED: was GET only
    """
    settings_obj, _ = SupportSettings.objects.get_or_create(id=1)

    if request.method == 'GET':
        app_version = request.GET.get('version_code', 1)
        needs_update = int(app_version) < settings_obj.latest_version_code
        data = SupportSettingsSerializer(settings_obj).data
        data['needs_update'] = needs_update
        return Response(data)

    # PUT / PATCH — admin only
    if not request.user.is_staff:
        return Response({'detail': 'Admin only.'}, status=403)

    serializer = SupportSettingsSerializer(
        settings_obj, data=request.data,
        partial=(request.method == 'PATCH')
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ═══════════════════════════════ TICKETS ═══════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def tickets_list_create(request):
    """
    GET  /support/tickets/  — list my tickets (staff sees all)  ✅ FIXED
    POST /support/tickets/  — create ticket                     ✅ FIXED: was /create-ticket/
    """
    if request.method == 'GET':
        if request.user.is_staff:
            qs = SupportTicket.objects.all()
            # Staff filters
            s = request.query_params.get('status')
            p = request.query_params.get('priority')
            c = request.query_params.get('category')
            q = request.query_params.get('search')
            if s: qs = qs.filter(status=s)
            if p: qs = qs.filter(priority=p)
            if c: qs = qs.filter(category=c)
            if q: qs = qs.filter(subject__icontains=q) | qs.filter(description__icontains=q)
        else:
            qs = SupportTicket.objects.filter(user=request.user)
        return Response(SupportTicketSerializer(qs, many=True).data)

    # POST — create
    serializer = SupportTicketSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    ticket = serializer.save(user=request.user)
    return Response({
        'success':   True,
        'ticket_id': ticket.ticket_id,
        'id':        ticket.id,
        'message':   'Ticket created successfully.',
        **SupportTicketSerializer(ticket).data,
    }, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def ticket_detail(request, ticket_id):
    """
    GET    /support/tickets/{id}/  — get detail    ✅
    PATCH  /support/tickets/{id}/  — update        ✅ FIXED: was missing
    DELETE /support/tickets/{id}/  — delete        ✅ FIXED: was missing
    """
    # Support both UUID id and ticket_id string
    try:
        if str(ticket_id).startswith('TKT'):
            ticket = SupportTicket.objects.get(ticket_id=ticket_id)
        else:
            ticket = SupportTicket.objects.get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return Response({'error': 'Ticket not found'}, status=404)

    # Non-staff can only access own tickets
    if not request.user.is_staff and ticket.user != request.user:
        return Response({'detail': 'Not your ticket.'}, status=403)

    if request.method == 'GET':
        return Response(SupportTicketSerializer(ticket).data)

    if request.method == 'PATCH':
        # Users can only update description; staff can update status/priority
        allowed = ['description'] if not request.user.is_staff else [
            'status', 'priority', 'description', 'admin_response'
        ]
        data = {k: v for k, v in request.data.items() if k in allowed}
        serializer = SupportTicketSerializer(ticket, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    if request.method == 'DELETE':
        ticket.delete()
        return Response({'success': True}, status=204)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminUser])
def ticket_respond(request, ticket_id):
    """
    PATCH /support/tickets/{id}/respond/  — admin response  ✅ FIXED: was missing
    """
    try:
        ticket = SupportTicket.objects.get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return Response({'error': 'Ticket not found'}, status=404)

    admin_response = request.data.get('admin_response', '')
    if not admin_response:
        return Response({'error': 'admin_response is required'}, status=400)

    ticket.admin_response    = admin_response
    ticket.admin_responded_at = timezone.now()
    ticket.status            = 'in_progress' if ticket.status == 'open' else ticket.status
    ticket.save()
    return Response(SupportTicketSerializer(ticket).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def ticket_stats(request):
    """
    GET /support/tickets/stats/  — dashboard stats  ✅ FIXED: was missing
    """
    qs = SupportTicket.objects.all()
    return Response({
        'total':       qs.count(),
        'open':        qs.filter(status='open').count(),
        'in_progress': qs.filter(status='in_progress').count(),
        'resolved':    qs.filter(status='resolved').count(),
        'closed':      qs.filter(status='closed').count(),
        'urgent':      qs.filter(priority='urgent').count(),
        'high':        qs.filter(priority='high').count(),
        'unanswered':  qs.filter(admin_response='').count(),
    })


# ═══════════════════════════════ FAQ ═══════════════════════════════════════════

@api_view(['GET', 'POST'])
def faqs_list_create(request):
    """
    GET  /support/faqs/  — public list (grouped by category)
    POST /support/faqs/  — admin create  ✅ FIXED: was missing
    """
    if request.method == 'GET':
        faqs = FAQ.objects.filter(is_active=True)
        # Return both grouped (for frontend display) and flat list
        flat = FAQSerializer(faqs, many=True).data
        grouped = {}
        for faq in faqs:
            if faq.category not in grouped:
                grouped[faq.category] = []
            grouped[faq.category].append({'id': faq.id, 'question': faq.question, 'answer': faq.answer})
        return Response({'results': flat, 'grouped': grouped, 'count': len(flat)})

    # POST — admin only
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({'detail': 'Admin only.'}, status=403)

    serializer = FAQSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    faq = serializer.save()
    return Response(FAQSerializer(faq).data, status=201)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def faq_detail(request, faq_id):
    """
    GET    /support/faqs/{id}/  ✅ FIXED: was missing
    PUT    /support/faqs/{id}/  ✅ FIXED: was missing
    PATCH  /support/faqs/{id}/  ✅ FIXED: was missing
    DELETE /support/faqs/{id}/  ✅ FIXED: was missing
    """
    try:
        faq = FAQ.objects.get(id=faq_id)
    except FAQ.DoesNotExist:
        return Response({'error': 'FAQ not found'}, status=404)

    if request.method == 'GET':
        return Response(FAQSerializer(faq).data)

    # Write ops — admin only
    if not request.user.is_authenticated or not request.user.is_staff:
        return Response({'detail': 'Admin only.'}, status=403)

    if request.method in ('PUT', 'PATCH'):
        serializer = FAQSerializer(faq, data=request.data, partial=(request.method == 'PATCH'))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    if request.method == 'DELETE':
        faq.delete()
        return Response({'success': True}, status=204)