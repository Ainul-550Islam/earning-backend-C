# views.py - Bulletproof & Defensive Coding

from django.shortcuts import get_object_or_404
from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from django.db.models import Sum, Count, Q
from .models import Customer, Txn, Event
from .serializers import (
    CustomerSerializer, CustomerDetailSerializer,
    TxnSerializer, EventSerializer
)


class CustomerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    """
    Customer CRUD - Bulletproof with Null Object Pattern
    """
    queryset = Customer.objects.all().order_by('-created_at')
    serializer_class = CustomerSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'firstname', 'lastname', 'email', 'phone']
    ordering_fields = ['created_at', 'code', 'city']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CustomerDetailSerializer
        return CustomerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Null Object Pattern - ডিফল্ট ফিল্টার
        newsletter = self.request.query_params.get('newsletter', None)
        city = self.request.query_params.get('city', None)

        if newsletter is not None:
            qs = qs.filter(newsletter=newsletter.lower() == 'true')
        if city:
            qs = qs.filter(city__icontains=city)

        return qs.prefetch_related('transactions', 'events')

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Customer এর transaction statistics"""
        customer = get_object_or_404(Customer, pk=pk)
        txns = customer.transactions.all()

        data = {
            'total_transactions': txns.count(),
            'total_spent': float(txns.aggregate(s=Sum('value'))['s'] or 0),
            'full_price_count': txns.filter(is_discount=False).count(),
            'discount_count': txns.filter(is_discount=True).count(),
            'spending_count': txns.filter(value__lt=0).count(),
            'event_count': customer.events.count(),
        }
        return Response(data)

    @action(detail=False, methods=['get'])
    def newsletter_subscribers(self, request):
        """Newsletter subscribers list"""
        qs = self.get_queryset().filter(newsletter=True)
        serializer = self.get_serializer(qs, many=True)
        return Response({
            'count': qs.count(),
            'results': serializer.data
        })


class TxnViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    """
    Transaction CRUD - Manager গুলো ব্যবহার করে
    """
    queryset = Txn.objects.all().order_by('-timestamp')
    serializer_class = TxnSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['customer__code', 'customer__email']
    ordering_fields = ['timestamp', 'value']

    def get_queryset(self):
        qs = super().get_queryset()
        txn_type = self.request.query_params.get('type', None)

        # Custom Manager গুলো ব্যবহার
        if txn_type == 'full':
            return Txn.txn_full.all()
        elif txn_type == 'discount':
            return Txn.txn_discount.all()
        elif txn_type == 'spending':
            return Txn.spending.all()

        customer_id = self.request.query_params.get('customer', None)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        return qs.select_related('customer')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Transaction summary statistics"""
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'total_value': float(qs.aggregate(s=Sum('value'))['s'] or 0),
            'full_price': Txn.txn_full.count(),
            'discounted': Txn.txn_discount.count(),
            'spending': Txn.spending.count(),
        })


class EventViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    """
    Event CRUD - Anonymous event support সহ
    """
    queryset = Event.objects.all().order_by('-timestamp')
    serializer_class = EventSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['action', 'description', 'customer__code']
    ordering_fields = ['timestamp', 'action']

    def get_queryset(self):
        qs = super().get_queryset()
        action_filter = self.request.query_params.get('action', None)
        customer_id = self.request.query_params.get('customer', None)
        anonymous = self.request.query_params.get('anonymous', None)

        if action_filter:
            qs = qs.filter(action__icontains=action_filter)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if anonymous == 'true':
            qs = qs.filter(customer=None)

        return qs.select_related('customer')

    @action(detail=False, methods=['get'])
    def by_action(self, request):
        """Action অনুযায়ী group করা events"""
        data = (
            Event.objects.values('action')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        return Response(list(data))