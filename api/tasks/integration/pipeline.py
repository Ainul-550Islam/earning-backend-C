"""
tasks/integration/pipeline.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DataPipeline — ETL and Cross-System Data Flows
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Defines and executes data pipeline steps for:
- Syncing user data to DataBridge after DB updates
- Aggregating analytics across all task modules
- Feeding ML models with latest features
- Pushing data to external systems (S3, BigQuery, Webhook)

Usage:
    pipeline = DataPipeline.build('user_sync')
    pipeline.run(user_id=123)
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class PipelineStep:
    """A single step in a data pipeline."""

    def __init__(
        self,
        name: str,
        fn: Callable,
        on_error: str = 'continue',  # 'continue' | 'stop' | 'retry'
        depends_on: List[str] = None,
    ):
        self.name       = name
        self.fn         = fn
        self.on_error   = on_error
        self.depends_on = depends_on or []

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self.fn(context)
            logger.debug(f"[Pipeline] Step '{self.name}' OK")
            return {'ok': True, 'result': result}
        except Exception as e:
            logger.error(f"[Pipeline] Step '{self.name}' ERROR: {e}")
            return {'ok': False, 'error': str(e)}


class DataPipeline:
    """
    Composable data pipeline for cross-system data flows.
    Steps execute sequentially; results accumulate in context.
    """

    def __init__(self, name: str):
        self.name  = name
        self.steps: List[PipelineStep] = []

    @classmethod
    def build(cls, pipeline_type: str) -> 'DataPipeline':
        """
        Build a pre-defined pipeline by type.
        Types: 'user_sync', 'offer_sync', 'platform_kpi', 'fraud_check'
        """
        pipeline = cls(name=pipeline_type)
        builder  = _PIPELINE_BUILDERS.get(pipeline_type)
        if builder:
            builder(pipeline)
        return pipeline

    def add_step(
        self,
        name: str,
        fn: Callable,
        on_error: str = 'continue',
        depends_on: List[str] = None,
    ) -> 'DataPipeline':
        """Add a step to the pipeline (fluent API)."""
        self.steps.append(PipelineStep(name=name, fn=fn, on_error=on_error, depends_on=depends_on))
        return self

    def run(self, **initial_context) -> Dict[str, Any]:
        """Execute all pipeline steps in order."""
        context = {**initial_context, '_pipeline': self.name, '_started_at': timezone.now().isoformat()}
        results = {}

        for step in self.steps:
            # Check dependencies
            deps_ok = all(results.get(dep, {}).get('ok', False) for dep in step.depends_on)
            if step.depends_on and not deps_ok:
                logger.warning(f"[Pipeline] Skipping '{step.name}': dependencies not met")
                results[step.name] = {'ok': False, 'error': 'dependency_failed', 'skipped': True}
                continue

            result = step.execute(context)
            results[step.name] = result

            # Merge step result into context for downstream steps
            if result.get('ok') and isinstance(result.get('result'), dict):
                context.update(result['result'])

            if not result['ok'] and step.on_error == 'stop':
                logger.error(f"[Pipeline] '{self.name}' stopped at step '{step.name}'")
                break

        context['_results'] = results
        context['_finished_at'] = timezone.now().isoformat()
        return context

    def run_async(self, **initial_context) -> str:
        """Dispatch the entire pipeline as a Celery task."""
        from celery import current_app
        result = current_app.send_task(
            'tasks.data_pipeline_tasks.run_pipeline',
            kwargs={'pipeline_name': self.name, 'context': initial_context},
            queue='default',
        )
        return result.id


# ─── Pipeline Builders ────────────────────────────────────────────────────────

def _build_user_sync_pipeline(pipeline: DataPipeline) -> None:
    """Sync all user data to DataBridge after any DB update."""

    def load_wallet(ctx):
        from api.tasks.integration.data_bridge import DataBridge
        try:
            from wallet.models import Wallet
            b = Wallet.objects.filter(user_id=ctx['user_id']).values_list('balance', flat=True).first()
            DataBridge.set_user(ctx['user_id'], 'wallet_balance', b, ttl=300)
            return {'wallet_balance': b}
        except ImportError:
            return {}

    def load_kyc(ctx):
        from api.tasks.integration.data_bridge import DataBridge
        try:
            from users.models import KYCVerification
            kyc = KYCVerification.objects.filter(user_id=ctx['user_id'], status='approved').values_list('tier', flat=True).first()
            DataBridge.set_user(ctx['user_id'], 'kyc_tier', kyc or 'none', ttl=3600)
            return {'kyc_tier': kyc or 'none'}
        except ImportError:
            return {}

    def load_publisher_tier(ctx):
        from api.tasks.integration.data_bridge import DataBridge
        from django.core.cache import cache
        tier = cache.get(f'publisher_tier_{ctx["user_id"]}', 'bronze')
        DataBridge.set_user(ctx['user_id'], 'publisher_tier', tier, ttl=3600)
        return {'publisher_tier': tier}

    def load_fraud_score(ctx):
        from django.core.cache import cache
        score = cache.get(f'fraud_score_{ctx["user_id"]}', 0)
        return {'fraud_score': score}

    pipeline.add_step('load_wallet',         load_wallet,         on_error='continue')
    pipeline.add_step('load_kyc',            load_kyc,            on_error='continue')
    pipeline.add_step('load_publisher_tier', load_publisher_tier, on_error='continue')
    pipeline.add_step('load_fraud_score',    load_fraud_score,    on_error='continue')


def _build_offer_sync_pipeline(pipeline: DataPipeline) -> None:
    """Sync offer data to DataBridge after offer update."""

    def load_offer_data(ctx):
        from api.tasks.integration.data_bridge import DataBridge
        offer_id = ctx.get('offer_id')
        try:
            from ad_networks.models import SmartlinkOffer
            offer = SmartlinkOffer.objects.filter(external_id=offer_id).values(
                'epc', 'payout', 'conversion_rate', 'quality_score',
                'daily_cap', 'daily_clicks_used', 'is_active',
            ).first()
            if offer:
                for field, val in offer.items():
                    DataBridge.set_offer(offer_id, field, val, ttl=1800)
                return offer
        except ImportError:
            pass
        return {}

    pipeline.add_step('load_offer_data', load_offer_data, on_error='continue')


def _build_platform_kpi_pipeline(pipeline: DataPipeline) -> None:
    """Aggregate all platform KPIs into DataBridge."""

    def agg_dau(ctx):
        from api.tasks.integration.data_bridge import DataBridge
        from datetime import timedelta
        try:
            from api.tasks.models import UserTaskCompletion
            from django.db.models import Count
            dau = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=timezone.now() - timedelta(days=1),
                    status='completed',
                ).values('user_id').distinct().count()
            )
            DataBridge.set_platform('dau', dau, ttl=300)
            return {'dau': dau}
        except ImportError:
            return {}

    def agg_revenue(ctx):
        from api.tasks.integration.data_bridge import DataBridge
        from datetime import timedelta
        try:
            from api.tasks.models import UserTaskCompletion
            from django.db.models import Sum
            day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            rev = (
                UserTaskCompletion.objects.filter(
                    completed_at__gte=day_start, status='completed'
                ).aggregate(t=Sum('reward_amount'))['t'] or 0
            )
            DataBridge.set_platform('revenue_today', str(rev), ttl=300)
            return {'revenue_today': rev}
        except ImportError:
            return {}

    pipeline.add_step('aggregate_dau',     agg_dau,     on_error='continue')
    pipeline.add_step('aggregate_revenue', agg_revenue, on_error='continue')


_PIPELINE_BUILDERS = {
    'user_sync':     _build_user_sync_pipeline,
    'offer_sync':    _build_offer_sync_pipeline,
    'platform_kpi':  _build_platform_kpi_pipeline,
}
