from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter
from .viewsets import RedemptionCodeViewSet, RewardItemViewSet, UserInventoryViewSet
from .views import MyInventoryView, PublicItemCatalogView

app_name = "inventory"

router = DefaultRouter()
router.register(r"items", RewardItemViewSet, basename="item")
router.register(r"user-inventory", UserInventoryViewSet, basename="user-inventory")
router.register(r"codes", RedemptionCodeViewSet, basename="code")

urlpatterns = [
    path("", include(router.urls)),
    path("catalog/", PublicItemCatalogView.as_view(), name="catalog"),
    path("mine/", MyInventoryView.as_view(), name="my-inventory"),
]
