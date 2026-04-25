# api/payment_gateways/smartlink/views.py
from django.shortcuts import redirect
from django.http import HttpResponseRedirect, HttpResponse
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from core.views import BaseViewSet
from .models import SmartLink, SmartLinkRotation
from .SmartRouter import SmartRouter
from rest_framework import serializers


class SmartLinkSerializer(serializers.ModelSerializer):
    url          = serializers.ReadOnlyField()
    publisher    = serializers.StringRelatedField(read_only=True)
    class Meta:
        model  = SmartLink
        fields = ['id','name','slug','url','status','rotation_mode','offer_types',
                  'categories','min_payout','target_countries','target_devices',
                  'fallback_url','total_clicks','total_conversions','total_earnings',
                  'epc','publisher','created_at']
        read_only_fields = ['slug','total_clicks','total_conversions','total_earnings','epc']


class SmartLinkViewSet(BaseViewSet):
    """Publisher SmartLink management."""
    queryset           = SmartLink.objects.all().order_by('-created_at')
    serializer_class   = SmartLinkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(publisher=self.request.user)

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        link = self.get_object()
        from api.payment_gateways.tracking.models import Click, Conversion
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(days=7)

        data = {
            'total_clicks':      link.total_clicks,
            'total_conversions': link.total_conversions,
            'total_earnings':    float(link.total_earnings),
            'epc':               float(link.epc),
            'url':               link.url,
            'rotation_mode':     link.rotation_mode,
        }
        return self.success_response(data=data)


def smartlink_redirect(request, slug):
    """
    Public SmartLink redirect endpoint.
    GET /go/{slug}/ → detect visitor → route to best offer
    """
    try:
        link = SmartLink.objects.get(slug=slug, status='active')
    except SmartLink.DoesNotExist:
        return HttpResponse('Link not found', status=404)

    ip      = request.META.get('HTTP_X_FORWARDED_FOR','').split(',')[0].strip() \
              or request.META.get('REMOTE_ADDR','')
    ua      = request.META.get('HTTP_USER_AGENT','')
    country = request.META.get('HTTP_CF_IPCOUNTRY','').upper()

    from api.payment_gateways.targeting.DeviceDetector import DeviceDetector
    device_info = DeviceDetector().detect(ua)
    device      = device_info['device_type']
    os_name     = device_info['os_name']

    router = SmartRouter()
    result = router.route(link, country, device, os_name, ip)

    redirect_url = result.get('redirect_url') or link.fallback_url or '/'
    return HttpResponseRedirect(redirect_url)
