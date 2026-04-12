from rest_framework.routers import SimpleRouter as DefaultRouter
from .views import TenantViewSet, TenantBillingViewSet

router = DefaultRouter()
router.register(r"tenants", TenantViewSet, basename="tenant")
router.register(r"tenant-billing", TenantBillingViewSet, basename="tenant-billing")

urlpatterns = router.urls
