from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, TxnViewSet, EventViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'transactions', TxnViewSet, basename='txn')
router.register(r'events', EventViewSet, basename='event')

urlpatterns = [
    path('', include(router.urls)),
]