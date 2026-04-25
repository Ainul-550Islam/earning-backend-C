"""
api/ad_networks/views_modern_features.py
ViewSets for modern features based on internet research
SaaS-ready with tenant support
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
import json

from .models_modern_features import (
    RealTimeBid, PredictiveAnalytics, PrivacyCompliance, ProgrammaticCampaign,
    MLFraudDetection, CrossPlatformAttribution, DynamicCreative, VoiceAd,
    Web3Transaction, MetaverseAd
)
from .serializers_modern_features import (
    RealTimeBidSerializer, PredictiveAnalyticsSerializer, PrivacyComplianceSerializer,
    ProgrammaticCampaignSerializer, MLFraudDetectionSerializer,
    CrossPlatformAttributionSerializer, DynamicCreativeSerializer, VoiceAdSerializer,
    Web3TransactionSerializer, MetaverseAdSerializer,
    RealTimeBidFilterSerializer, PredictiveAnalyticsFilterSerializer
)
from .permissions import IsAdNetworkAdmin, IsTenantUser
from .filters import RealTimeBidFilter, PredictiveAnalyticsFilter


# ==================== MODERN FEATURES VIEWSETS ====================

class RealTimeBidViewSet(viewsets.ModelViewSet):
    """ViewSet for Real-time Bidding"""
    
    queryset = RealTimeBid.objects.all()
    serializer_class = RealTimeBidSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['bid_type', 'ad_network', 'offer', 'user']
    search_fields = ['bid_id', 'user__username', 'offer__title']
    ordering = ['-bid_time']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple bids at once"""
        serializer = self.get_serializer(data=request.data, many=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def place_bid(self, request, pk=None):
        """Place a real-time bid"""
        bid = self.get_object()
        bid.win_notification_sent = True
        bid.save()
        return Response({'status': 'bid placed', 'bid_id': bid.bid_id})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get RTB statistics"""
        queryset = self.get_queryset()
        stats = {
            'total_bids': queryset.count(),
            'successful_bids': queryset.filter(win_notification_sent=True).count(),
            'average_bid_amount': queryset.aggregate(avg=Avg('bid_amount'))['avg'] or 0,
            'average_response_time': queryset.aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
            'win_rate': queryset.filter(win_notification_sent=True).count() / queryset.count() if queryset.count() > 0 else 0,
        }
        return Response(stats)


class PredictiveAnalyticsViewSet(viewsets.ModelViewSet):
    """ViewSet for Predictive Analytics"""
    
    queryset = PredictiveAnalytics.objects.all()
    serializer_class = PredictiveAnalyticsSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['model_type', 'offer', 'confidence_score']
    search_fields = ['prediction_id', 'offer__title', 'model_name']
    ordering = ['-last_trained_at']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'])
    def train_model(self, request, pk=None):
        """Train ML model for prediction"""
        prediction = self.get_object()
        
        # Mock training process
        prediction.last_trained_at = timezone.now()
        prediction.training_data_points += 100
        prediction.save()
        
        return Response({
            'status': 'model trained',
            'prediction_id': prediction.prediction_id,
            'trained_at': prediction.last_trained_at
        })
    
    @action(detail=False, methods=['get'])
    def model_performance(self, request):
        """Get model performance metrics"""
        queryset = self.get_queryset()
        
        # Calculate accuracy
        predictions_with_actual = queryset.filter(actual_value__isnull=False)
        total_predictions = predictions_with_actual.count()
        
        if total_predictions > 0:
            accurate_predictions = 0
            for pred in predictions_with_actual:
                if abs(pred.actual_value - pred.prediction_value) / pred.prediction_value < 0.1:  # 10% tolerance
                    accurate_predictions += 1
            
            accuracy_rate = accurate_predictions / total_predictions
        else:
            accuracy_rate = 0
        
        stats = {
            'total_predictions': total_predictions,
            'accuracy_rate': accuracy_rate,
            'average_confidence': queryset.aggregate(avg=Avg('confidence_score'))['avg'] or 0,
            'models_trained': queryset.count(),
        }
        return Response(stats)


class PrivacyComplianceViewSet(viewsets.ModelViewSet):
    """ViewSet for Privacy Compliance"""
    
    queryset = PrivacyCompliance.objects.all()
    serializer_class = PrivacyComplianceSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['compliance_framework', 'consent_given', 'do_not_sell']
    search_fields = ['consent_id', 'user__username', 'consent_purpose']
    ordering = ['-consent_timestamp']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=False, methods=['post'])
    def record_consent(self, request):
        """Record user consent"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def revoke_consent(self, request, pk=None):
        """Revoke user consent"""
        consent = self.get_object()
        consent.consent_given = False
        consent.data_deletion_requested = True
        consent.save()
        return Response({'status': 'consent revoked', 'consent_id': consent.consent_id})
    
    @action(detail=False, methods=['get'])
    def compliance_report(self, request):
        """Get compliance report"""
        queryset = self.get_queryset()
        
        stats = {
            'total_consents': queryset.count(),
            'active_consents': queryset.filter(consent_given=True).count(),
            'gdpr_compliant': queryset.filter(compliance_framework='gdpr', consent_given=True).count(),
            'ccpa_compliant': queryset.filter(compliance_framework='ccpa', consent_given=True).count(),
            'do_not_sell_count': queryset.filter(do_not_sell=True).count(),
        }
        return Response(stats)


class ProgrammaticCampaignViewSet(viewsets.ModelViewSet):
    """ViewSet for Programmatic Campaigns"""
    
    queryset = ProgrammaticCampaign.objects.all()
    serializer_class = ProgrammaticCampaignSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['bidding_strategy', 'ad_network', 'demand_side_platform']
    search_fields = ['campaign_id', 'name', 'supply_side_platform']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'])
    def launch_campaign(self, request, pk=None):
        """Launch programmatic campaign"""
        campaign = self.get_object()
        # Mock launch process
        return Response({
            'status': 'campaign launched',
            'campaign_id': campaign.campaign_id,
            'launched_at': timezone.now()
        })
    
    @action(detail=True, methods=['post'])
    def pause_campaign(self, request, pk=None):
        """Pause programmatic campaign"""
        campaign = self.get_object()
        # Mock pause process
        return Response({
            'status': 'campaign paused',
            'campaign_id': campaign.campaign_id,
            'paused_at': timezone.now()
        })
    
    @action(detail=False, methods=['get'])
    def campaign_performance(self, request):
        """Get campaign performance metrics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_campaigns': queryset.count(),
            'active_campaigns': queryset.count(),  # Mock active status
            'total_spend': queryset.aggregate(total=Sum('spend'))['total'] or 0,
            'total_impressions': queryset.aggregate(total=Sum('impressions'))['total'] or 0,
            'total_clicks': queryset.aggregate(total=Sum('clicks'))['total'] or 0,
            'total_conversions': queryset.aggregate(total=Sum('conversions'))['total'] or 0,
            'average_ctr': queryset.aggregate(avg=Avg('clicks'))['avg'] or 0,  # Mock CTR
            'conversion_rate': queryset.aggregate(avg=Avg('conversions'))['avg'] or 0,  # Mock conversion rate
        }
        return Response(stats)


class MLFraudDetectionViewSet(viewsets.ModelViewSet):
    """ViewSet for ML Fraud Detection"""
    
    queryset = MLFraudDetection.objects.all()
    serializer_class = MLFraudDetectionSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['fraud_type', 'risk_level', 'action_taken']
    search_fields = ['detection_id', 'user__username', 'ip_address', 'device_fingerprint']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'])
    def review_detection(self, request, pk=None):
        """Review fraud detection"""
        detection = self.get_object()
        detection.reviewed_by = request.user
        detection.reviewed_at = timezone.now()
        detection.review_notes = request.data.get('review_notes', '')
        detection.save()
        return Response({
            'status': 'detection reviewed',
            'detection_id': detection.detection_id,
            'reviewed_by': request.user.username
        })
    
    @action(detail=False, methods=['get'])
    def fraud_statistics(self, request):
        """Get fraud detection statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_detections': queryset.count(),
            'high_risk_detections': queryset.filter(risk_level='high').count(),
            'critical_detections': queryset.filter(risk_level='critical').count(),
            'blocked_users': queryset.filter(action_taken='block').count(),
            'fraud_types': dict(queryset.values('fraud_type').annotate(count=Count('fraud_type'))),
            'average_risk_score': queryset.aggregate(avg=Avg('risk_score'))['avg'] or 0,
        }
        return Response(stats)


class CrossPlatformAttributionViewSet(viewsets.ModelViewSet):
    """ViewSet for Cross-Platform Attribution"""
    
    queryset = CrossPlatformAttribution.objects.all()
    serializer_class = CrossPlatformAttributionSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['attribution_model', 'source_platform', 'attributed_network']
    search_fields = ['attribution_id', 'user__username', 'source_campaign']
    ordering = ['-conversion_time']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=False, methods=['post'])
    def create_attribution(self, request):
        """Create cross-platform attribution"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def attribution_report(self, request):
        """Get attribution report"""
        queryset = self.get_queryset()
        
        stats = {
            'total_attributions': queryset.count(),
            'attribution_models': dict(queryset.values('attribution_model').annotate(count=Count('attribution_model'))),
            'total_conversion_value': queryset.aggregate(total=Sum('conversion_value'))['total'] or 0,
            'top_platforms': dict(queryset.values('source_platform').annotate(count=Count('source_platform')).order_by('-count')[:5]),
            'attribution_window_avg': queryset.aggregate(avg=Avg('attribution_window_hours'))['avg'] or 0,
        }
        return Response(stats)


class DynamicCreativeViewSet(viewsets.ModelViewSet):
    """ViewSet for Dynamic Creative"""
    
    queryset = DynamicCreative.objects.all()
    serializer_class = DynamicCreativeSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['creative_type', 'optimization_goal', 'test_group']
    search_fields = ['creative_id', 'base_creative_url', 'optimization_model']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'])
    def optimize_creative(self, request, pk=None):
        """Run AI optimization for creative"""
        creative = self.get_object()
        # Mock optimization process
        return Response({
            'status': 'optimization started',
            'creative_id': creative.creative_id,
            'optimization_model': creative.optimization_model,
            'started_at': timezone.now()
        })
    
    @action(detail=True, methods=['post'])
    def declare_winner(self, request, pk=None):
        """Declare A/B test winner"""
        creative = self.get_object()
        creative.is_winner = True
        creative.confidence_level = request.data.get('confidence_level', 0.95)
        creative.save()
        return Response({
            'status': 'winner declared',
            'creative_id': creative.creative_id,
            'confidence_level': creative.confidence_level
        })
    
    @action(detail=False, methods=['get'])
    def creative_performance(self, request):
        """Get creative performance metrics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_creatives': queryset.count(),
            'active_tests': queryset.filter(test_group__isnull=False).count(),
            'winners': queryset.filter(is_winner=True).count(),
            'average_ctr': queryset.aggregate(avg=Avg('ctr'))['avg'] or 0,
            'average_conversion_rate': queryset.aggregate(avg=Avg('conversion_rate'))['avg'] or 0,
            'total_impressions': queryset.aggregate(total=Sum('impressions'))['total'] or 0,
            'total_clicks': queryset.aggregate(total=Sum('clicks'))['total'] or 0,
        }
        return Response(stats)


class VoiceAdViewSet(viewsets.ModelViewSet):
    """ViewSet for Voice Ads"""
    
    queryset = VoiceAd.objects.all()
    serializer_class = VoiceAdSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['voice_platform', 'ad_format', 'audio_format']
    search_fields = ['ad_id', 'voice_platform', 'target_genres']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'])
    def play_ad(self, request, pk=None):
        """Simulate voice ad play"""
        ad = self.get_object()
        ad.plays += 1
        ad.save()
        return Response({
            'status': 'ad played',
            'ad_id': ad.ad_id,
            'total_plays': ad.plays
        })
    
    @action(detail=False, methods=['get'])
    def voice_performance(self, request):
        """Get voice ad performance metrics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_voice_ads': queryset.count(),
            'total_plays': queryset.aggregate(total=Sum('plays'))['total'] or 0,
            'total_completions': queryset.aggregate(total=Sum('completions'))['total'] or 0,
            'completion_rate': 0,  # Mock calculation
            'platform_distribution': dict(queryset.values('voice_platform').annotate(count=Count('voice_platform'))),
        }
        return Response(stats)


class Web3TransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for Web3 Transactions"""
    
    queryset = Web3Transaction.objects.all()
    serializer_class = Web3TransactionSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['blockchain_network', 'status', 'ad_network']
    search_fields = ['transaction_hash', 'contract_address', 'function_called']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'])
    def confirm_transaction(self, request, pk=None):
        """Confirm blockchain transaction"""
        transaction = self.get_object()
        transaction.status = 'confirmed'
        transaction.block_number = request.data.get('block_number')
        transaction.save()
        return Response({
            'status': 'transaction confirmed',
            'transaction_hash': transaction.transaction_hash,
            'block_number': transaction.block_number
        })
    
    @action(detail=False, methods=['get'])
    def blockchain_stats(self, request):
        """Get blockchain transaction statistics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_transactions': queryset.count(),
            'confirmed_transactions': queryset.filter(status='confirmed').count(),
            'pending_transactions': queryset.filter(status='pending').count(),
            'failed_transactions': queryset.filter(status='failed').count(),
            'total_volume': queryset.aggregate(total=Sum('amount'))['total'] or 0,
            'blockchain_distribution': dict(queryset.values('blockchain_network').annotate(count=Count('blockchain_network'))),
            'average_gas_fee': queryset.aggregate(avg=Avg('gas_fee'))['avg'] or 0,
        }
        return Response(stats)


class MetaverseAdViewSet(viewsets.ModelViewSet):
    """ViewSet for Metaverse Ads"""
    
    queryset = MetaverseAd.objects.all()
    serializer_class = MetaverseAdSerializer
    permission_classes = [IsAdNetworkAdmin]
    filterset_fields = ['metaverse_platform', 'placement_type', 'asset_type']
    search_fields = ['ad_id', 'virtual_world', 'metaverse_platform']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by tenant"""
        queryset = super().get_queryset()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(tenant_id=tenant_id)
    
    @action(detail=True, methods=['post'])
    def place_ad(self, request, pk=None):
        """Place metaverse ad"""
        ad = self.get_object()
        # Mock placement process
        return Response({
            'status': 'ad placed',
            'ad_id': ad.ad_id,
            'virtual_world': ad.virtual_world,
            'placed_at': timezone.now()
        })
    
    @action(detail=False, methods=['get'])
    def metaverse_performance(self, request):
        """Get metaverse ad performance metrics"""
        queryset = self.get_queryset()
        
        stats = {
            'total_metaverse_ads': queryset.count(),
            'total_views': queryset.aggregate(total=Sum('views'))['total'] or 0,
            'total_interactions': queryset.aggregate(total=Sum('interactions'))['total'] or 0,
            'interaction_rate': 0,  # Mock calculation
            'platform_distribution': dict(queryset.values('metaverse_platform').annotate(count=Count('metaverse_platform'))),
            'placement_distribution': dict(queryset.values('placement_type').annotate(count=Count('placement_type'))),
        }
        return Response(stats)


# ==================== USER-FACING VIEWSETS ====================

class UserPrivacyComplianceViewSet(viewsets.ModelViewSet):
    """User-facing privacy compliance ViewSet"""
    
    serializer_class = PrivacyComplianceSerializer
    permission_classes = [IsTenantUser]
    
    def get_queryset(self):
        """Filter by current user and tenant"""
        queryset = PrivacyCompliance.objects.all()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(user=self.request.user, tenant_id=tenant_id)
    
    @action(detail=False, methods=['get'])
    def my_consents(self, request):
        """Get user's consent records"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_consent_preferences(self, request):
        """Update user consent preferences"""
        user = request.user
        tenant_id = getattr(request, 'tenant_id', 'default')
        
        # Update or create consent record
        consent_data = {
            'user': user,
            'tenant_id': tenant_id,
            'compliance_framework': request.data.get('framework', 'gdpr'),
            'consent_given': request.data.get('consent_given', True),
            'consent_purpose': request.data.get('purpose', 'Marketing and Analytics'),
            'data_retention_days': request.data.get('data_retention_days', 365),
            'do_not_sell': request.data.get('do_not_sell', False),
        }
        
        serializer = self.get_serializer(data=consent_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserAttributionViewSet(viewsets.ModelViewSet):
    """User-facing attribution ViewSet"""
    
    serializer_class = CrossPlatformAttributionSerializer
    permission_classes = [IsTenantUser]
    
    def get_queryset(self):
        """Filter by current user and tenant"""
        queryset = CrossPlatformAttribution.objects.all()
        tenant_id = getattr(self.request, 'tenant_id', 'default')
        return queryset.filter(user=self.request.user, tenant_id=tenant_id)
    
    @action(detail=False, methods=['get'])
    def my_attributions(self, request):
        """Get user's attribution records"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# ==================== EXPORTS ====================

__all__ = [
    # Admin ViewSets
    'RealTimeBidViewSet',
    'PredictiveAnalyticsViewSet',
    'PrivacyComplianceViewSet',
    'ProgrammaticCampaignViewSet',
    'MLFraudDetectionViewSet',
    'CrossPlatformAttributionViewSet',
    'DynamicCreativeViewSet',
    'VoiceAdViewSet',
    'Web3TransactionViewSet',
    'MetaverseAdViewSet',
    
    # User-facing ViewSets
    'UserPrivacyComplianceViewSet',
    'UserAttributionViewSet',
]
