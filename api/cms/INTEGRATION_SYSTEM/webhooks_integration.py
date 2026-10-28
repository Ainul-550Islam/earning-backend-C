"""Webhook views stub — real implementations live in CPALeadService."""
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


class CPALeadWebhookView(APIView):
    """CPAlead postback receiver (v2 path)."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            from ..services_new.CPALeadService import CPALeadService
            result = CPALeadService.handle_postback(request)
            return Response(result)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class GenericWebhookView(APIView):
    """Generic webhook receiver for arbitrary sources."""
    permission_classes = [AllowAny]

    def post(self, request, source, *args, **kwargs):
        import logging
        logging.getLogger(__name__).info(f"Webhook received from source={source}")
        return Response({'received': True, 'source': source})


class WalletCallbackView(APIView):
    """Wallet payment callback receiver."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        return Response({'status': 'ok'})
