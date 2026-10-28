"""
api/offerwall/b2b/views.py

Architecture fix: views now delegate all business logic to B2BClientService
and B2BInvoiceService. Views are thin HTTP dispatch layers.
B2B feature gating added for survey_offers and analytics_api.
"""
import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import B2BClient, B2BPlan, B2BUsageRecord, B2BInvoice, B2BOnboarding
from .serializers import (
    B2BPlanSerializer, B2BClientSerializer, B2BClientRegisterSerializer,
    B2BUsageSerializer, B2BInvoiceSerializer,
)
from .services import B2BClientService, B2BInvoiceService

logger = logging.getLogger(__name__)


def _get_client(user):
    """Return B2BClient for user or raise DoesNotExist."""
    return B2BClient.objects.select_related('plan', 'onboarding').get(
        owner=user)


class B2BPlanListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        plans = B2BPlan.objects.filter(is_active=True, is_public=True)
        return Response(B2BPlanSerializer(plans, many=True).data)


class B2BRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, 'b2b_client'):
            return Response(
                {'error': 'already_registered',
                 'detail': 'Your account already has a B2B profile.'},
                status=status.HTTP_409_CONFLICT)

        ser = B2BClientRegisterSerializer(
            data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        client = ser.save()
        logger.info(f'[B2B] registered: {client.company_name}')
        return Response(
            B2BClientSerializer(client, context={'request': request}).data,
            status=status.HTTP_201_CREATED)


class B2BDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            client = _get_client(request.user)
        except B2BClient.DoesNotExist:
            return Response({'error': 'not_registered'},
                            status=status.HTTP_404_NOT_FOUND)

        data = B2BClientService.get_dashboard_data(client)
        data['client'] = B2BClientSerializer(
            client, context={'request': request}).data
        return Response(data)


class B2BUpgradeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            client = _get_client(request.user)
        except B2BClient.DoesNotExist:
            return Response({'error': 'not_registered'},
                            status=status.HTTP_404_NOT_FOUND)

        result = B2BClientService.upgrade_plan(
            client, request.data.get('plan_type', ''))

        if not result['success']:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'plan':    B2BPlanSerializer(result['plan']).data,
            'message': f"Upgraded to {result['plan'].name}",
        })


class B2BUsageHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            client = _get_client(request.user)
        except B2BClient.DoesNotExist:
            return Response({'error': 'not_registered'},
                            status=status.HTTP_404_NOT_FOUND)

        months  = min(int(request.query_params.get('months', 6)), 24)
        records = B2BUsageRecord.objects.filter(client=client).order_by(
            '-period_year', '-period_month')[:months]
        return Response(B2BUsageSerializer(records, many=True).data)


class B2BInvoiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id=None):
        try:
            client = _get_client(request.user)
        except B2BClient.DoesNotExist:
            return Response({'error': 'not_registered'},
                            status=status.HTTP_404_NOT_FOUND)

        if invoice_id:
            try:
                inv = client.invoices.get(id=invoice_id)
                return Response(B2BInvoiceSerializer(inv).data)
            except B2BInvoice.DoesNotExist:
                return Response({'error': 'not_found'},
                                status=status.HTTP_404_NOT_FOUND)

        invoices = client.invoices.all()[:24]
        return Response(B2BInvoiceSerializer(invoices, many=True).data)


class B2BAdminClientListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        qs = B2BClient.objects.select_related(
            'plan', 'owner', 'onboarding').all()

        if s := request.query_params.get('status'):
            qs = qs.filter(status=s)
        if p := request.query_params.get('plan_type'):
            qs = qs.filter(plan__plan_type=p)

        return Response({'count': qs.count(),
                         'results': B2BClientSerializer(
                             qs[:100], many=True,
                             context={'request': request}).data})


class B2BAdminClientActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, client_id, action):
        if not request.user.is_staff:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        try:
            client = B2BClient.objects.get(id=client_id)
        except B2BClient.DoesNotExist:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        if action == 'verify':
            return Response(B2BClientService.verify_client(client, request.user))
        if action == 'activate':
            return Response(B2BClientService.activate_client(client))
        if action == 'suspend':
            return Response(B2BClientService.suspend_client(
                client, request.data.get('reason', '')))

        return Response({'error': 'unknown_action',
                         'valid': ['verify', 'activate', 'suspend']},
                        status=status.HTTP_400_BAD_REQUEST)


class B2BAdminGenerateInvoicesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_staff:
            return Response({'error': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        now   = timezone.now()
        year  = int(request.data.get('year',  now.year))
        month = int(request.data.get('month', now.month))

        if not (1 <= month <= 12):
            return Response({'error': 'invalid_month'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Delegated entirely to service layer
        result = B2BInvoiceService.generate_for_period(year, month)
        return Response(result)


class B2BOnboardingStepView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            client = _get_client(request.user)
        except B2BClient.DoesNotExist:
            return Response({'error': 'not_registered'},
                            status=status.HTTP_404_NOT_FOUND)

        step   = request.data.get('step', '')
        result = B2BClientService.complete_onboarding_step(client, step)
        if not result.get('success'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
