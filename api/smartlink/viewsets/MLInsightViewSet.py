"""
ML Insight ViewSet
Exposes ML rotation and fraud model data to publishers and admins.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..permissions import IsPublisher
from ..services.ml.SmartRotationMLEngine import SmartRotationMLEngine
from ..services.ml.FraudMLScorer import FraudMLScorer
from ..services.antifraud.ClickQualityScore import ClickQualityScore


class MLInsightViewSet(viewsets.GenericViewSet):
    """
    ML model insights — offer scores, fraud signals, quality analysis.

    GET /api/smartlink/ml/offer-scores/{offer_id}/
    GET /api/smartlink/ml/fraud-test/
    POST /api/smartlink/ml/score-click/
    GET /api/smartlink/ml/confidence/{offer_id}/
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ml_engine   = SmartRotationMLEngine()
        self.fraud_ml    = FraudMLScorer()
        self.quality_svc = ClickQualityScore()

    @action(detail=False, methods=['post'], url_path='score-click')
    def score_click(self, request):
        """
        POST /api/smartlink/ml/score-click/
        Score a click for fraud + quality (testing tool for publishers).
        Body: {ip, user_agent, country, device_type, asn, referrer}
        """
        data   = request.data
        ip     = data.get('ip', '1.2.3.4')
        ua     = data.get('user_agent', 'Mozilla/5.0')

        fraud_prob, signals = self.fraud_ml.score_click({
            'ip':          ip,
            'user_agent':  ua,
            'country':     data.get('country', ''),
            'device_type': data.get('device_type', 'mobile'),
            'asn':         data.get('asn', ''),
            'referrer':    data.get('referrer', ''),
        })

        quality = self.quality_svc.calculate({
            'ip':          ip,
            'user_agent':  ua,
            'country':     data.get('country', ''),
            'device_type': data.get('device_type', 'mobile'),
            'is_unique':   True,
            'referrer':    data.get('referrer', ''),
            'publisher_id': request.user.pk,
        })

        fraud_score_100 = self.fraud_ml.score_to_100(fraud_prob)
        return Response({
            'fraud': {
                'probability':  fraud_prob,
                'score_0_100':  fraud_score_100,
                'signals':      signals,
                'action':       'block' if fraud_score_100 >= 85 else 'flag' if fraud_score_100 >= 60 else 'allow',
            },
            'quality': quality,
            'summary': {
                'is_high_quality': quality['score'] >= 75 and fraud_score_100 < 30,
                'recommendation':  quality['recommendation'],
            }
        })

    @action(detail=False, methods=['get'], url_path='confidence')
    def confidence(self, request):
        """
        GET /api/smartlink/ml/confidence/?offer_id=X&country=US&device=mobile
        Returns Thompson Sampling confidence interval for an offer.
        """
        offer_id    = int(request.query_params.get('offer_id', 0))
        country     = request.query_params.get('country', 'US')
        device_type = request.query_params.get('device', 'mobile')

        context = {'country': country, 'device_type': device_type}
        ci = self.ml_engine.get_offer_confidence_interval(offer_id, context)

        anomaly = self.ml_engine.detect_performance_anomaly(offer_id, context)

        return Response({
            'offer_id':           offer_id,
            'context':            context,
            'confidence_interval': ci,
            'anomaly':            anomaly,
        })

    @action(detail=False, methods=['get'], url_path='rotation-explain')
    def rotation_explain(self, request):
        """
        GET /api/smartlink/ml/rotation-explain/?smartlink_id=X&country=BD&device=mobile
        Explain why ML chose a specific offer for a given context.
        """
        from ..models import SmartLink
        sl_id  = int(request.query_params.get('smartlink_id', 0))
        country = request.query_params.get('country', 'US')
        device  = request.query_params.get('device', 'mobile')

        try:
            sl      = SmartLink.objects.get(pk=sl_id, publisher=request.user)
            entries = list(sl.offer_pool.get_active_entries())
            context = {'country': country, 'device_type': device}

            scores = []
            for entry in entries:
                ci = self.ml_engine.get_offer_confidence_interval(entry.offer_id, context)
                scores.append({
                    'offer_id':   entry.offer_id,
                    'weight':     entry.weight,
                    'ci':         ci,
                    'epc_override': float(entry.epc_override) if entry.epc_override else None,
                })

            scores.sort(key=lambda x: x['ci']['mean'], reverse=True)
            return Response({
                'smartlink':    sl.slug,
                'context':      context,
                'offer_scores': scores,
                'winner':       scores[0] if scores else None,
            })
        except SmartLink.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('SmartLink not found.')
