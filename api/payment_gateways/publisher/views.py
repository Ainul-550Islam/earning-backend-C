# api/payment_gateways/publisher/views.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from .models import PublisherProfile, AdvertiserProfile
from .serializers import PublisherProfileSerializer, AdvertiserProfileSerializer

class PublisherProfileViewSet(BaseViewSet):
    queryset           = PublisherProfile.objects.all().order_by('-created_at')
    serializer_class   = PublisherProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    def get_object(self):
        if self.action in ('my_profile', 'update_postback'):
            profile, _ = PublisherProfile.objects.get_or_create(user=self.request.user)
            return profile
        return super().get_object()

    @action(detail=False, methods=['get','put','patch'])
    def my_profile(self, request):
        profile, _ = PublisherProfile.objects.get_or_create(user=request.user)
        if request.method == 'GET':
            return self.success_response(data=PublisherProfileSerializer(profile).data)
        s = PublisherProfileSerializer(profile, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return self.success_response(data=s.data, message='Profile updated')

    @action(detail=False, methods=['post'])
    def set_postback(self, request):
        """Set publisher's S2S postback URL."""
        url = request.data.get('postback_url', '')
        profile, _ = PublisherProfile.objects.get_or_create(user=request.user)
        profile.postback_url = url
        profile.save(update_fields=['postback_url'])
        return self.success_response(message=f'Postback URL updated: {url}')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        pub = self.get_object()
        pub.status = 'active'
        pub.save()
        return self.success_response(message=f'{pub.user.username} approved as publisher')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def grant_fast_pay(self, request, pk=None):
        pub = self.get_object()
        pub.is_fast_pay_eligible = True
        pub.save()
        return self.success_response(message='Fast Pay eligibility granted')

class AdvertiserProfileViewSet(BaseViewSet):
    queryset           = AdvertiserProfile.objects.all().order_by('-created_at')
    serializer_class   = AdvertiserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=False, methods=['get','put','patch'])
    def my_profile(self, request):
        profile, _ = AdvertiserProfile.objects.get_or_create(user=request.user)
        if request.method == 'GET':
            return self.success_response(data=AdvertiserProfileSerializer(profile).data)
        s = AdvertiserProfileSerializer(profile, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return self.success_response(data=s.data, message='Profile updated')

    @action(detail=False, methods=['post'])
    def add_funds(self, request):
        """Add funds to advertiser balance (triggers payment flow)."""
        from decimal import Decimal
        amount   = Decimal(str(request.data.get('amount', '0')))
        gateway  = request.data.get('gateway', 'stripe')
        if amount <= 0:
            return self.error_response(message='Invalid amount', status_code=400)

        profile, _ = AdvertiserProfile.objects.get_or_create(user=request.user)
        try:
            from api.payment_gateways.services.PaymentFactory import PaymentFactory
            processor = PaymentFactory.get_processor(gateway)
            result    = processor.process_deposit(user=request.user, amount=amount,
                         metadata={'purpose': 'advertiser_balance_topup'})
            return self.success_response(
                data={'payment_url': result.get('payment_url', '')},
                message=f'Payment initiated. After completion your balance will be credited.'
            )
        except Exception as e:
            return self.error_response(message=str(e), status_code=400)
