# api/promotions/data_science/user_clustering.py
user_clustering.py
# User Quality Clustering — K-Means দিয়ে user segment করে
# =============================================================================

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger('data_science.user_clustering')


@dataclass
class UserCluster:
    cluster_id:       int
    label:            str     # 'champion', 'at_risk', 'new', 'low_value'
    user_count:       int
    avg_trust_score:  float
    avg_success_rate: float
    avg_submissions:  float
    recommended_action: str


@dataclass
class ClusteringResult:
    clusters:           list[UserCluster]
    user_assignments:   dict[int, int]  # user_id → cluster_id
    inertia:            float
    n_clusters:         int
    algorithm:          str


class UserClusteringEngine:
    """
    K-Means Clustering দিয়ে user quality অনুযায়ী segment করে।

    Features used:
    - trust_score (0-100)
    - success_rate (0-100%)
    - total_submissions
    - approved_count / total (approval rate)
    - days_since_last_active

    Clusters (4):
    1. Champions: High trust, high success rate, active
    2. Promising: Medium trust, growing
    3. At Risk: Was good, now inactive or declining
    4. Low Quality: Low trust, low success rate
    """

    N_CLUSTERS = 4
    CLUSTER_LABELS = {
        0: {'label': 'champion',   'action': 'give_bonus_campaigns'},
        1: {'label': 'promising',  'action': 'send_encouragement'},
        2: {'label': 'at_risk',    'action': 're_engagement_campaign'},
        3: {'label': 'low_quality','action': 'restrict_high_value_campaigns'},
    }

    def cluster_users(self, min_submissions: int = 5) -> ClusteringResult:
        """
        User গুলোকে cluster করে।

        Args:
            min_submissions: কমপক্ষে এতগুলো submission আছে এমন user নাও
        """
        users_data = self._load_user_features(min_submissions)
        if len(users_data) < self.N_CLUSTERS:
            logger.warning(f'Not enough users ({len(users_data)}) for clustering.')
            return self._empty_result()

        try:
            return self._cluster_with_sklearn(users_data)
        except ImportError:
            logger.warning('scikit-learn not installed — using simple threshold clustering.')
            return self._threshold_clustering(users_data)

    def _load_user_features(self, min_submissions: int) -> list[dict]:
        """DB থেকে user features load করে।"""
        from api.promotions.models import UserReputation
        from django.utils import timezone
        from datetime import timedelta

        reps = UserReputation.objects.filter(
            total_submissions__gte=min_submissions
        ).select_related('user')

        now     = timezone.now()
        result  = []
        for rep in reps:
            days_inactive = (
                (now - rep.last_active_at).days
                if rep.last_active_at else 365
            )
            result.append({
                'user_id':         rep.user_id,
                'trust_score':     float(rep.trust_score),
                'success_rate':    float(rep.success_rate),
                'total_submissions': float(rep.total_submissions),
                'level':           float(rep.level),
                'days_inactive':   float(days_inactive),
            })
        return result

    def _cluster_with_sklearn(self, users_data: list[dict]) -> ClusteringResult:
        """scikit-learn K-Means দিয়ে cluster করে।"""
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        feature_keys = ['trust_score', 'success_rate', 'total_submissions', 'level', 'days_inactive']
        X            = np.array([[u[k] for k in feature_keys] for u in users_data])
        user_ids     = [u['user_id'] for u in users_data]

        scaler       = StandardScaler()
        X_scaled     = scaler.fit_transform(X)

        kmeans = KMeans(n_clusters=self.N_CLUSTERS, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        # Cluster ভিত্তিক statistics
        clusters_data = {i: {'users': [], 'trust': [], 'success': [], 'submissions': []}
                         for i in range(self.N_CLUSTERS)}

        user_assignments = {}
        for i, (uid, label) in enumerate(zip(user_ids, labels)):
            c_id = int(label)
            clusters_data[c_id]['users'].append(uid)
            clusters_data[c_id]['trust'].append(users_data[i]['trust_score'])
            clusters_data[c_id]['success'].append(users_data[i]['success_rate'])
            clusters_data[c_id]['submissions'].append(users_data[i]['total_submissions'])
            user_assignments[uid] = c_id

        # Cluster label assign (সবচেয়ে বেশি trust score = champion)
        cluster_avg_trust = {
            i: (sum(v['trust']) / len(v['trust'])) if v['trust'] else 0
            for i, v in clusters_data.items()
        }
        sorted_by_trust = sorted(cluster_avg_trust.keys(), key=lambda k: cluster_avg_trust[k], reverse=True)
        label_map = {
            sorted_by_trust[0]: self.CLUSTER_LABELS[0],
            sorted_by_trust[1]: self.CLUSTER_LABELS[1],
            sorted_by_trust[2]: self.CLUSTER_LABELS[2],
            sorted_by_trust[3]: self.CLUSTER_LABELS[3],
        }

        clusters = []
        for c_id, data in clusters_data.items():
            n = len(data['users'])
            if n == 0:
                continue
            meta = label_map.get(c_id, self.CLUSTER_LABELS[3])
            clusters.append(UserCluster(
                cluster_id        = c_id,
                label             = meta['label'],
                user_count        = n,
                avg_trust_score   = round(sum(data['trust']) / n, 2),
                avg_success_rate  = round(sum(data['success']) / n, 2),
                avg_submissions   = round(sum(data['submissions']) / n, 2),
                recommended_action = meta['action'],
            ))

        return ClusteringResult(
            clusters         = sorted(clusters, key=lambda c: c.avg_trust_score, reverse=True),
            user_assignments = user_assignments,
            inertia          = float(kmeans.inertia_),
            n_clusters       = self.N_CLUSTERS,
            algorithm        = 'kmeans_sklearn',
        )

    def _threshold_clustering(self, users_data: list[dict]) -> ClusteringResult:
        """Simple threshold-based clustering (sklearn fallback)।"""
        user_assignments = {}
        cluster_buckets  = {0: [], 1: [], 2: [], 3: []}

        for u in users_data:
            ts = u['trust_score']
            sr = u['success_rate']
            if ts >= 70 and sr >= 80:
                c = 0  # champion
            elif ts >= 50 and sr >= 60:
                c = 1  # promising
            elif u['days_inactive'] > 30:
                c = 2  # at_risk
            else:
                c = 3  # low_quality
            user_assignments[u['user_id']] = c
            cluster_buckets[c].append(u)

        clusters = []
        for c_id, bucket in cluster_buckets.items():
            if not bucket:
                continue
            meta = self.CLUSTER_LABELS[c_id]
            n    = len(bucket)
            clusters.append(UserCluster(
                cluster_id        = c_id,
                label             = meta['label'],
                user_count        = n,
                avg_trust_score   = round(sum(u['trust_score'] for u in bucket) / n, 2),
                avg_success_rate  = round(sum(u['success_rate'] for u in bucket) / n, 2),
                avg_submissions   = round(sum(u['total_submissions'] for u in bucket) / n, 2),
                recommended_action = meta['action'],
            ))

        return ClusteringResult(
            clusters         = sorted(clusters, key=lambda c: c.avg_trust_score, reverse=True),
            user_assignments = user_assignments,
            inertia          = 0.0,
            n_clusters       = self.N_CLUSTERS,
            algorithm        = 'threshold_heuristic',
        )

    def _empty_result(self) -> ClusteringResult:
        return ClusteringResult([], {}, 0.0, 0, 'insufficient_data')

    def get_user_cluster(self, user_id: int) -> Optional[str]:
        """একটি user এর cluster label বের করে।"""
        from django.core.cache import cache
        cached = cache.get(f'ds:cluster:{user_id}')
        if cached:
            return cached

        result = self.cluster_users()
        cluster_id = result.user_assignments.get(user_id)
        if cluster_id is None:
            return None

        label = next(
            (c.label for c in result.clusters if c.cluster_id == cluster_id), None
        )
        cache.set(f'ds:cluster:{user_id}', label, timeout=3600 * 24)
        return label
