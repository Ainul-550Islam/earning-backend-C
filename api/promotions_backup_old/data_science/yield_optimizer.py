# =============================================================================
# api/promotions/data_science/yield_optimizer.py
# সর্বোচ্চ লাভের অ্যালগরিদম — Linear Programming (PuLP / SciPy)
# কোন campaign এ কত budget দিলে profit maximize হবে তা calculate করে
# =============================================================================

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

logger = logging.getLogger('data_science.yield_optimizer')


@dataclass
class CampaignAllocation:
    """Campaign এর optimal budget allocation।"""
    campaign_id:     int
    allocated_usd:   float
    expected_profit: float
    expected_roi:    float     # Return on Investment %
    priority_score:  float


@dataclass
class OptimizationResult:
    """Linear programming optimization এর ফলাফল।"""
    allocations:         list[CampaignAllocation]
    total_allocated:     float
    total_expected_profit: float
    total_expected_roi:  float
    solver_status:       str
    optimization_time_ms: float


class YieldOptimizer:
    """
    Linear Programming দিয়ে campaign budget allocation optimize করে।
    Objective: Maximize total profit subject to budget constraints।

    Algorithm: PuLP (open-source LP solver) অথবা SciPy fallback।

    Math model:
        Maximize:  Σ (profit_rate[i] * x[i])
        Subject to:
            Σ x[i] <= total_budget
            min_budget[i] <= x[i] <= max_budget[i]  for all i
            x[i] >= 0
    """

    def optimize(
        self,
        campaigns: list[dict],
        total_budget: float,
        min_allocation_per_campaign: float = 0.0,
    ) -> OptimizationResult:
        """
        Campaign budget allocation optimize করে।

        Args:
            campaigns: [{'id': 1, 'profit_rate': 0.30, 'max_budget': 500, 'min_budget': 10}, ...]
            total_budget: মোট available budget
            min_allocation_per_campaign: প্রতি campaign এ minimum allocation

        Returns:
            OptimizationResult with optimal allocations
        """
        import time
        start = time.monotonic()

        if not campaigns:
            return OptimizationResult([], 0, 0, 0, 'no_campaigns', 0)

        try:
            result = self._optimize_with_pulp(campaigns, total_budget, min_allocation_per_campaign)
        except ImportError:
            logger.info('PuLP not installed — falling back to SciPy greedy algorithm.')
            result = self._optimize_with_scipy(campaigns, total_budget, min_allocation_per_campaign)
        except Exception as e:
            logger.exception(f'LP optimization failed: {e}')
            result = self._greedy_fallback(campaigns, total_budget)

        elapsed = (time.monotonic() - start) * 1000
        result.optimization_time_ms = round(elapsed, 2)

        logger.info(
            f'Yield optimization complete: campaigns={len(campaigns)}, '
            f'total_budget=${total_budget:.2f}, '
            f'expected_profit=${result.total_expected_profit:.2f}, '
            f'ROI={result.total_expected_roi:.1f}%, '
            f'time={elapsed:.1f}ms'
        )
        return result

    def _optimize_with_pulp(
        self, campaigns: list[dict], total_budget: float, min_alloc: float
    ) -> OptimizationResult:
        """PuLP দিয়ে Linear Programming solve করে।"""
        import pulp

        prob = pulp.LpProblem('campaign_budget_allocation', pulp.LpMaximize)

        # Decision variables: x[i] = budget allocated to campaign i
        x = {
            c['id']: pulp.LpVariable(
                f'x_{c["id"]}',
                lowBound = max(min_alloc, c.get('min_budget', 0)),
                upBound  = c.get('max_budget', total_budget),
            )
            for c in campaigns
        }

        # Objective: maximize profit
        prob += pulp.lpSum(c['profit_rate'] * x[c['id']] for c in campaigns)

        # Constraint: total budget
        prob += pulp.lpSum(x[c['id']] for c in campaigns) <= total_budget

        # Solve
        status = pulp.LpStatus[prob.solve(pulp.PULP_CBC_CMD(msg=0))]

        allocations = []
        total_allocated = 0.0
        total_profit    = 0.0

        for c in campaigns:
            alloc   = max(0.0, x[c['id']].varValue or 0.0)
            profit  = alloc * c['profit_rate']
            roi     = (profit / alloc * 100) if alloc > 0 else 0.0
            allocations.append(CampaignAllocation(
                campaign_id     = c['id'],
                allocated_usd   = round(alloc, 2),
                expected_profit = round(profit, 4),
                expected_roi    = round(roi, 2),
                priority_score  = c.get('priority_score', 0.0),
            ))
            total_allocated += alloc
            total_profit    += profit

        overall_roi = (total_profit / total_allocated * 100) if total_allocated > 0 else 0.0
        return OptimizationResult(
            allocations           = sorted(allocations, key=lambda a: a.expected_profit, reverse=True),
            total_allocated       = round(total_allocated, 2),
            total_expected_profit = round(total_profit, 4),
            total_expected_roi    = round(overall_roi, 2),
            solver_status         = status,
            optimization_time_ms  = 0,
        )

    def _optimize_with_scipy(
        self, campaigns: list[dict], total_budget: float, min_alloc: float
    ) -> OptimizationResult:
        """SciPy linprog দিয়ে solve করে (PuLP এর fallback)।"""
        from scipy.optimize import linprog
        import numpy as np

        n = len(campaigns)
        # linprog minimizes, তাই negative profit rate দিই
        c_obj  = [-camp['profit_rate'] for camp in campaigns]
        bounds = [
            (max(min_alloc, camp.get('min_budget', 0)), camp.get('max_budget', total_budget))
            for camp in campaigns
        ]
        # Inequality: sum(x) <= total_budget
        A_ub = [np.ones(n)]
        b_ub = [total_budget]

        res = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')

        allocations     = []
        total_allocated = 0.0
        total_profit    = 0.0

        if res.success:
            for i, c in enumerate(campaigns):
                alloc  = max(0.0, res.x[i])
                profit = alloc * c['profit_rate']
                roi    = (profit / alloc * 100) if alloc > 0 else 0.0
                allocations.append(CampaignAllocation(
                    campaign_id=c['id'], allocated_usd=round(alloc, 2),
                    expected_profit=round(profit, 4), expected_roi=round(roi, 2),
                    priority_score=c.get('priority_score', 0.0),
                ))
                total_allocated += alloc
                total_profit    += profit
        else:
            return self._greedy_fallback(campaigns, total_budget)

        overall_roi = (total_profit / total_allocated * 100) if total_allocated > 0 else 0.0
        return OptimizationResult(
            allocations=sorted(allocations, key=lambda a: a.expected_profit, reverse=True),
            total_allocated=round(total_allocated, 2),
            total_expected_profit=round(total_profit, 4),
            total_expected_roi=round(overall_roi, 2),
            solver_status='optimal', optimization_time_ms=0,
        )

    def _greedy_fallback(self, campaigns: list[dict], total_budget: float) -> OptimizationResult:
        """Greedy হিউরিস্টিক — সবচেয়ে বেশি profit_rate প্রথমে।"""
        sorted_campaigns = sorted(campaigns, key=lambda c: c['profit_rate'], reverse=True)
        remaining        = total_budget
        allocations      = []
        total_profit     = 0.0

        for c in sorted_campaigns:
            max_b = min(c.get('max_budget', remaining), remaining)
            alloc = max(c.get('min_budget', 0), max_b)
            alloc = min(alloc, remaining)
            if alloc > 0:
                profit = alloc * c['profit_rate']
                allocations.append(CampaignAllocation(
                    campaign_id=c['id'], allocated_usd=round(alloc, 2),
                    expected_profit=round(profit, 4),
                    expected_roi=round(c['profit_rate'] * 100, 2),
                    priority_score=c.get('priority_score', 0.0),
                ))
                remaining    -= alloc
                total_profit += profit

        total_allocated = total_budget - remaining
        overall_roi     = (total_profit / total_allocated * 100) if total_allocated > 0 else 0.0
        return OptimizationResult(
            allocations=allocations, total_allocated=round(total_allocated, 2),
            total_expected_profit=round(total_profit, 4),
            total_expected_roi=round(overall_roi, 2),
            solver_status='greedy_heuristic', optimization_time_ms=0,
        )

    def calculate_campaign_roi_metrics(self, campaign_id: int) -> dict:
        """একটি campaign এর historical ROI metrics বের করে।"""
        from django.db.models import Sum, Count, Avg
        from api.promotions.models import (
            TaskSubmission, AdminCommissionLog, CampaignAnalytics
        )
        from api.promotions.choices import SubmissionStatus

        submissions = TaskSubmission.objects.filter(campaign_id=campaign_id)
        stats = submissions.aggregate(
            total=Count('id'),
            approved=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status=SubmissionStatus.APPROVED)),
            total_rewards=Sum('reward_usd'),
        )
        commission = AdminCommissionLog.objects.filter(campaign_id=campaign_id).aggregate(
            total_commission=Sum('commission_usd'),
            total_gross=Sum('gross_amount_usd'),
        )

        total_gross      = float(commission.get('total_gross') or 0)
        total_rewards    = float(stats.get('total_rewards') or 0)
        total_commission = float(commission.get('total_commission') or 0)
        profit_rate      = (total_commission / total_gross) if total_gross > 0 else 0.0
        approval_rate    = (
            (stats['approved'] / stats['total'] * 100)
            if stats['total'] > 0 else 0.0
        )

        return {
            'campaign_id':     campaign_id,
            'total_submissions': stats['total'],
            'approved_count':  stats['approved'],
            'approval_rate':   round(approval_rate, 2),
            'total_rewards_usd': round(total_rewards, 4),
            'total_commission_usd': round(total_commission, 4),
            'profit_rate':     round(profit_rate, 4),
            'roi_percent':     round(profit_rate * 100, 2),
        }


# =============================================================================
# api/promotions/data_science/trend_analyzer.py
# Market Trend Analysis — Time Series (Moving Average, Seasonality)
# =============================================================================

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger('data_science.trend_analyzer')


@dataclass
class TrendPoint:
    date:        str
    value:       float
    ma_7:        Optional[float] = None    # 7-day moving average
    ma_30:       Optional[float] = None    # 30-day moving average
    trend_dir:   str             = 'flat'  # up, down, flat
    anomaly:     bool            = False


@dataclass
class TrendReport:
    metric:          str
    period:          str
    data_points:     list[TrendPoint]
    overall_trend:   str            # up, down, flat, volatile
    growth_rate:     float          # % change
    peak_date:       Optional[str]
    trough_date:     Optional[str]
    forecast_7d:     Optional[float]
    seasonality:     dict


class TrendAnalyzer:
    """
    Time Series Analysis — Platform এর growth trend analyze করে।
    Simple Moving Average, Exponential Smoothing, Seasonality detection।
    """

    def analyze_submission_trend(
        self,
        campaign_id: int = None,
        days: int = 90,
    ) -> TrendReport:
        """Submission volume এর trend analyze করে।"""
        from django.db.models import Count
        from api.promotions.models import TaskSubmission

        end_date   = date.today()
        start_date = end_date - timedelta(days=days)

        qs = TaskSubmission.objects.filter(submitted_at__date__range=[start_date, end_date])
        if campaign_id:
            qs = qs.filter(campaign_id=campaign_id)

        daily = (
            qs.extra({'day': 'DATE(submitted_at)'})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        values_dict = {str(row['day']): row['count'] for row in daily}
        all_values  = []
        current     = start_date
        while current <= end_date:
            all_values.append(values_dict.get(current.isoformat(), 0))
            current += timedelta(days=1)

        return self._build_trend_report(all_values, start_date, 'daily_submissions')

    def analyze_revenue_trend(self, days: int = 90) -> TrendReport:
        """Revenue trend analyze করে।"""
        from django.db.models import Sum
        from api.promotions.models import AdminCommissionLog

        end_date   = date.today()
        start_date = end_date - timedelta(days=days)

        daily = (
            AdminCommissionLog.objects
            .filter(created_at__date__range=[start_date, end_date])
            .extra({'day': 'DATE(created_at)'})
            .values('day')
            .annotate(revenue=Sum('commission_usd'))
            .order_by('day')
        )

        values_dict = {str(row['day']): float(row['revenue'] or 0) for row in daily}
        all_values  = []
        current     = start_date
        while current <= end_date:
            all_values.append(values_dict.get(current.isoformat(), 0.0))
            current += timedelta(days=1)

        return self._build_trend_report(all_values, start_date, 'daily_revenue')

    def _build_trend_report(
        self,
        values: list[float],
        start_date: date,
        metric: str,
    ) -> TrendReport:
        """Raw values থেকে full trend report তৈরি করে।"""
        n = len(values)
        if n == 0:
            return TrendReport(metric, '', [], 'no_data', 0.0, None, None, None, {})

        # Moving averages
        ma7  = self._moving_average(values, 7)
        ma30 = self._moving_average(values, 30)

        # Anomaly detection (z-score > 2.5)
        anomalies = self._detect_anomalies(values)

        data_points = []
        current     = start_date
        for i, v in enumerate(values):
            trend_dir = 'flat'
            if i > 0:
                if v > values[i-1] * 1.05:
                    trend_dir = 'up'
                elif v < values[i-1] * 0.95:
                    trend_dir = 'down'

            data_points.append(TrendPoint(
                date      = current.isoformat(),
                value     = v,
                ma_7      = ma7[i],
                ma_30     = ma30[i],
                trend_dir = trend_dir,
                anomaly   = anomalies[i],
            ))
            current += timedelta(days=1)

        # Overall trend
        first_half_avg = sum(values[:n//2]) / (n//2) if n > 1 else 0
        second_half_avg = sum(values[n//2:]) / (n - n//2) if n > 1 else 0
        if second_half_avg > first_half_avg * 1.1:
            overall_trend = 'up'
        elif second_half_avg < first_half_avg * 0.9:
            overall_trend = 'down'
        else:
            overall_trend = 'flat'

        growth_rate = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0.0

        # Peak & trough
        peak_idx   = values.index(max(values))
        trough_idx = values.index(min(values))
        peak_date   = (start_date + timedelta(days=peak_idx)).isoformat()
        trough_date = (start_date + timedelta(days=trough_idx)).isoformat()

        # Simple forecast (last MA7 value)
        forecast = ma7[-1] if ma7 and ma7[-1] is not None else values[-1]

        # Seasonality (day of week pattern)
        day_of_week_avg = {}
        for i, v in enumerate(values):
            dow = (start_date + timedelta(days=i)).weekday()
            if dow not in day_of_week_avg:
                day_of_week_avg[dow] = []
            day_of_week_avg[dow].append(v)

        seasonality = {
            ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][k]:
            round(sum(v)/len(v), 2)
            for k, v in day_of_week_avg.items()
        }

        return TrendReport(
            metric        = metric,
            period        = f'{start_date.isoformat()} to {date.today().isoformat()}',
            data_points   = data_points,
            overall_trend = overall_trend,
            growth_rate   = round(growth_rate, 2),
            peak_date     = peak_date,
            trough_date   = trough_date,
            forecast_7d   = round(forecast, 2),
            seasonality   = seasonality,
        )

    @staticmethod
    def _moving_average(values: list[float], window: int) -> list[Optional[float]]:
        result = []
        for i in range(len(values)):
            if i < window - 1:
                result.append(None)
            else:
                window_vals = values[i - window + 1: i + 1]
                result.append(round(sum(window_vals) / window, 4))
        return result

    @staticmethod
    def _detect_anomalies(values: list[float]) -> list[bool]:
        """Z-score > 2.5 হলে anomaly।"""
        if len(values) < 3:
            return [False] * len(values)
        mean   = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std    = variance ** 0.5
        if std == 0:
            return [False] * len(values)
        return [abs((v - mean) / std) > 2.5 for v in values]


# =============================================================================
# api/promotions/data_science/user_clustering.py
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
