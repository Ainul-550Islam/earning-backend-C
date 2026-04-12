"""
api/ai_engine/PERSONALIZATION/user_segmentation.py
===================================================
User Segmentation Engine — AI-driven user grouping।
K-means clustering + RFM + behavioral rule-based segments।
Marketing automation ও personalization foundation।
"""
import logging
from typing import List, Dict
from django.utils import timezone
logger = logging.getLogger(__name__)

class UserSegmentationEngine:
    """Multi-method user segmentation।"""

    RFM_SEGMENTS = [
        {'name': 'Champions',         'criteria': {'recency_days': 7,  'min_earn': 5000, 'min_offers': 20}},
        {'name': 'Loyal Users',       'criteria': {'recency_days': 14, 'min_earn': 1000, 'min_offers': 10}},
        {'name': 'Potential Loyalists','criteria': {'recency_days': 30, 'min_earn': 200,  'min_offers': 3}},
        {'name': 'New Users',         'criteria': {'max_age_days': 14}},
        {'name': 'At Risk',           'criteria': {'min_inactive': 30,  'min_earn': 100}},
        {'name': 'High Earners',      'criteria': {'min_earn': 10000}},
        {'name': 'Dormant',           'criteria': {'min_inactive': 60}},
        {'name': 'VIP Potential',     'criteria': {'min_referrals': 5,  'recency_days': 30}},
    ]

    def run_segmentation(self, tenant_id=None) -> dict:
        from ..models import UserSegment
        created = 0
        for seg_def in self.RFM_SEGMENTS:
            seg, is_new = UserSegment.objects.update_or_create(
                name=seg_def['name'],
                tenant_id=tenant_id,
                defaults={
                    'method':        'rule_based',
                    'criteria':      seg_def['criteria'],
                    'is_active':     True,
                    'auto_refresh':  True,
                    'last_refreshed': timezone.now(),
                    'description':   self._segment_description(seg_def['name']),
                }
            )
            if is_new: created += 1
            # Refresh user counts
            self._refresh_segment_count(seg, tenant_id)
        return {
            'segments_created':  created,
            'segments_updated':  len(self.RFM_SEGMENTS) - created,
            'total_segments':    len(self.RFM_SEGMENTS),
        }

    def _segment_description(self, name: str) -> str:
        desc = {
            'Champions':          'Highly active, high-earning power users',
            'Loyal Users':        'Regular users with consistent earning',
            'Potential Loyalists': 'Growing users with improving engagement',
            'New Users':          'Recently registered, onboarding phase',
            'At Risk':            'Previously active, now showing churn signals',
            'High Earners':       'Users with highest total earnings',
            'Dormant':            'Inactive for 60+ days — win-back candidates',
            'VIP Potential':      'Active referrers with growth potential',
        }
        return desc.get(name, name)

    def _refresh_segment_count(self, segment, tenant_id):
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            qs   = User.objects.filter(is_active=True)
            if tenant_id:
                qs = qs.filter(tenant_id=tenant_id)
            count = qs.count()
            segment.user_count = max(0, count // max(len(self.RFM_SEGMENTS), 1))
            segment.save(update_fields=['user_count', 'last_refreshed'])
        except Exception as e:
            logger.error(f"Segment count refresh error: {e}")

    def assign_user_to_segment(self, user, tenant_id=None) -> str:
        from ..utils import days_since
        age       = days_since(user.date_joined)
        inactive  = days_since(user.last_login)
        earned    = float(getattr(user, 'total_earned', 0))
        if age <= 14:                  return 'New Users'
        if inactive >= 60:             return 'Dormant'
        if inactive >= 30 and earned >= 100: return 'At Risk'
        if earned >= 10000:            return 'High Earners'
        if earned >= 5000 and inactive <= 7: return 'Champions'
        if earned >= 1000 and inactive <= 14: return 'Loyal Users'
        if earned >= 200 and inactive <= 30:  return 'Potential Loyalists'
        return 'General'

    def get_segment_marketing_actions(self, segment_name: str) -> List[str]:
        actions = {
            'Champions':           ['Feature in success stories','VIP badge','Exclusive offers','Ambassador program'],
            'Loyal Users':         ['Loyalty rewards','Early access to new features','Referral bonus boost'],
            'Potential Loyalists': ['Streak encouragement','Progressive rewards','Goal-based challenges'],
            'New Users':           ['Onboarding tutorial','First-earn bonus','Easy starter offers'],
            'At Risk':             ['Win-back offer','Personal email','Reminder of pending rewards'],
            'High Earners':        ['VIP status upgrade','Higher withdrawal limits','Premium support'],
            'Dormant':             ['Re-activation campaign','Big welcome-back bonus','New feature highlight'],
            'VIP Potential':       ['Referral competition','Network bonus rewards','Exclusive referral tier'],
        }
        return actions.get(segment_name, ['Standard engagement flow'])

    def clustering_segmentation(self, user_features: List[Dict],
                                  n_clusters: int = 5) -> dict:
        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
            import numpy as np
            feature_keys = ['total_earned', 'days_since_login', 'offers_completed', 'referral_count']
            X = np.array([[u.get(k, 0) for k in feature_keys] for u in user_features])
            scaler   = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            km       = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels   = km.fit_predict(X_scaled)
            sizes    = {int(i): int(sum(labels == i)) for i in range(n_clusters)}
            return {
                'method':       'kmeans',
                'n_clusters':   n_clusters,
                'labels':       labels.tolist(),
                'cluster_sizes': sizes,
                'inertia':      round(float(km.inertia_), 2),
            }
        except ImportError:
            return {'method': 'sklearn_unavailable'}
        except Exception as e:
            return {'method': 'error', 'error': str(e)}
