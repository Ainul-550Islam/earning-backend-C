"""Payout Queue URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import PayoutBatchViewSet, PayoutItemViewSet, BulkProcessLogViewSet, WithdrawalPriorityViewSet

router = DefaultRouter()
router.register(r"batches", PayoutBatchViewSet, basename="payoutbatch")
router.register(r"items", PayoutItemViewSet, basename="payoutitem")
router.register(r"logs", BulkProcessLogViewSet, basename="bulkprocesslog")
router.register(r"priorities", WithdrawalPriorityViewSet, basename="withdrawalpriority")

urlpatterns = [path("", include(router.urls))]
