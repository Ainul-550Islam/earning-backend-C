"""
api/ai_engine/PERSONALIZATION/user_clustering.py
=================================================
User Clustering — behavioral patterns এর ভিত্তিতে users group করো।
K-Means, DBSCAN, Hierarchical clustering।
Marketing segments, targeting groups তৈরিতে ব্যবহার।
"""

import logging
import math
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class UserClusterer:
    """
    User behavioral clustering engine।
    Unsupervised ML দিয়ে natural user groups discover করো।
    """

    # Predefined business-meaningful segment templates
    SEGMENT_TEMPLATES = {
        "champions":         {"earn_score": 0.9, "recency": 0.9, "engagement": 0.9},
        "loyal_users":       {"earn_score": 0.7, "recency": 0.7, "engagement": 0.8},
        "potential_loyalists": {"earn_score": 0.5, "recency": 0.8, "engagement": 0.6},
        "at_risk":           {"earn_score": 0.6, "recency": 0.3, "engagement": 0.3},
        "hibernating":       {"earn_score": 0.3, "recency": 0.1, "engagement": 0.1},
        "new_users":         {"earn_score": 0.1, "recency": 1.0, "engagement": 0.5},
        "high_value_new":    {"earn_score": 0.2, "recency": 0.9, "engagement": 0.8},
        "lost":              {"earn_score": 0.1, "recency": 0.0, "engagement": 0.0},
    }

    def cluster(self, user_features: List[List[float]],
                 n_clusters: int = 5,
                 method: str = "kmeans") -> dict:
        """User features cluster করো।"""
        if not user_features:
            return {"labels": [], "n_clusters": 0, "method": method}

        if method == "kmeans":
            return self._kmeans(user_features, n_clusters)
        elif method == "dbscan":
            return self._dbscan(user_features)
        elif method == "hierarchical":
            return self._hierarchical(user_features, n_clusters)
        else:
            return self._kmeans(user_features, n_clusters)

    def _kmeans(self, features: List[List[float]], n_clusters: int) -> dict:
        """K-Means clustering।"""
        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            X      = np.array(features)
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            km     = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = km.fit_predict(X_scaled)

            cluster_sizes = {}
            for lbl in labels:
                cluster_sizes[int(lbl)] = cluster_sizes.get(int(lbl), 0) + 1

            # Silhouette score
            silhouette = 0.0
            if len(set(labels)) > 1 and len(labels) > n_clusters:
                from sklearn.metrics import silhouette_score
                silhouette = float(silhouette_score(X_scaled, labels))

            return {
                "labels":         labels.tolist(),
                "n_clusters":     n_clusters,
                "cluster_sizes":  cluster_sizes,
                "inertia":        round(float(km.inertia_), 2),
                "silhouette_score": round(silhouette, 4),
                "method":         "kmeans",
                "quality":        "good" if silhouette >= 0.50 else "acceptable" if silhouette >= 0.30 else "poor",
            }
        except ImportError:
            logger.warning("sklearn not available. Using simple clustering.")
            return self._simple_cluster(features, n_clusters)
        except Exception as e:
            logger.error(f"K-Means error: {e}")
            return self._simple_cluster(features, n_clusters)

    def _dbscan(self, features: List[List[float]]) -> dict:
        """DBSCAN density-based clustering।"""
        try:
            from sklearn.cluster import DBSCAN
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            X        = np.array(features)
            X_scaled = StandardScaler().fit_transform(X)
            db       = DBSCAN(eps=0.5, min_samples=5).fit(X_scaled)
            labels   = db.labels_

            n_clusters  = len(set(labels)) - (1 if -1 in labels else 0)
            noise_count = sum(1 for l in labels if l == -1)

            return {
                "labels":      labels.tolist(),
                "n_clusters":  n_clusters,
                "noise_points": noise_count,
                "method":      "dbscan",
            }
        except Exception as e:
            logger.error(f"DBSCAN error: {e}")
            return {"labels": [0] * len(features), "n_clusters": 1, "method": "dbscan_fallback"}

    def _hierarchical(self, features: List[List[float]], n_clusters: int) -> dict:
        """Hierarchical clustering।"""
        try:
            from sklearn.cluster import AgglomerativeClustering
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            X_scaled = StandardScaler().fit_transform(np.array(features))
            agg      = AgglomerativeClustering(n_clusters=n_clusters).fit(X_scaled)
            labels   = agg.labels_

            sizes = {}
            for l in labels:
                sizes[int(l)] = sizes.get(int(l), 0) + 1

            return {"labels": labels.tolist(), "n_clusters": n_clusters, "cluster_sizes": sizes, "method": "hierarchical"}
        except Exception as e:
            return self._simple_cluster(features, n_clusters)

    def _simple_cluster(self, features: List[List[float]], n_clusters: int) -> dict:
        """Fallback: simple distance-based clustering।"""
        n = len(features)
        if n == 0:
            return {"labels": [], "n_clusters": 0, "method": "simple"}
        labels = [i % n_clusters for i in range(n)]
        sizes  = {i: labels.count(i) for i in range(n_clusters)}
        return {"labels": labels, "n_clusters": n_clusters, "cluster_sizes": sizes, "method": "simple_fallback"}

    def extract_user_features(self, user, extra_data: dict = None) -> List[float]:
        """User DB record থেকে clustering features extract করো।"""
        from ..utils import days_since
        extra = extra_data or {}

        account_age   = days_since(user.date_joined)
        days_inactive = days_since(user.last_login)
        balance       = float(getattr(user, "coin_balance", 0))
        total_earned  = float(getattr(user, "total_earned", 0))
        offers_done   = float(extra.get("offers_completed", 0))
        referrals     = float(extra.get("referral_count", 0))
        streak        = float(extra.get("streak_days", 0))

        # Normalize features to 0-1
        return [
            min(1.0, account_age / 365),
            max(0.0, 1.0 - days_inactive / 90),
            min(1.0, balance / 10000),
            min(1.0, total_earned / 50000),
            min(1.0, offers_done / 100),
            min(1.0, referrals / 20),
            min(1.0, streak / 30),
        ]

    def assign_segment(self, user_vector: List[float]) -> str:
        """User feature vector → segment name।"""
        if len(user_vector) < 3:
            return "unknown"

        recency    = user_vector[1] if len(user_vector) > 1 else 0.5
        earn_score = user_vector[3] if len(user_vector) > 3 else 0.3
        engagement = user_vector[4] if len(user_vector) > 4 else 0.3

        best_seg   = "unknown"
        best_dist  = float("inf")

        for seg_name, template in self.SEGMENT_TEMPLATES.items():
            dist = math.sqrt(
                (recency    - template["recency"])    ** 2 +
                (earn_score - template["earn_score"]) ** 2 +
                (engagement - template["engagement"]) ** 2
            )
            if dist < best_dist:
                best_dist = dist
                best_seg  = seg_name

        return best_seg

    def find_optimal_k(self, features: List[List[float]],
                        k_range: range = None) -> dict:
        """Elbow method দিয়ে optimal K খুঁজো।"""
        k_range = k_range or range(2, min(11, len(features)))

        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            X_scaled = StandardScaler().fit_transform(np.array(features))
            inertias = []

            for k in k_range:
                km = KMeans(n_clusters=k, random_state=42, n_init=5)
                km.fit(X_scaled)
                inertias.append(float(km.inertia_))

            # Find elbow
            if len(inertias) >= 3:
                diffs1 = [inertias[i] - inertias[i+1] for i in range(len(inertias)-1)]
                diffs2 = [diffs1[i] - diffs1[i+1] for i in range(len(diffs1)-1)]
                elbow_idx = diffs2.index(max(diffs2)) + 2
                optimal_k = list(k_range)[elbow_idx]
            else:
                optimal_k = list(k_range)[0] + 1

            return {
                "optimal_k":     optimal_k,
                "k_range":       list(k_range),
                "inertias":      [round(i, 2) for i in inertias],
                "method":        "elbow",
            }
        except Exception as e:
            return {"optimal_k": 5, "error": str(e)}
