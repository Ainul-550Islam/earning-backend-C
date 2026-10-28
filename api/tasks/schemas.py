"""
api/tasks/schemas.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Request/Response schemas for the task system API.
DRF Serializer-based schemas used for:
  • Request body validation
  • Response shape documentation (drf-spectacular / drf-yasg)
  • Data transfer between services

All schemas are DRF Serializers (not Pydantic) to stay
consistent with the rest of the Django DRF stack.
"""

from decimal import Decimal
from rest_framework import serializers


# ══════════════════════════════════════════════════════════════════════════════
# TASK SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class TaskCompleteRequestSchema(serializers.Serializer):
    """Request body for POST /tasks/{task_id}/complete/"""
    task_id    = serializers.CharField(max_length=100)
    proof      = serializers.CharField(max_length=2000, required=False, default='')
    extra_data = serializers.DictField(required=False, default=dict)
    device     = serializers.ChoiceField(
        choices=['desktop', 'mobile', 'tablet', 'unknown'],
        required=False, default='desktop'
    )


class TaskCompleteResponseSchema(serializers.Serializer):
    """Response for task completion."""
    status         = serializers.ChoiceField(choices=['success', 'error', 'duplicate', 'fraud_detected'])
    completion_id  = serializers.IntegerField(read_only=True)
    reward_amount  = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    new_balance    = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True, required=False)
    streak         = serializers.IntegerField(required=False)
    xp_awarded     = serializers.IntegerField(required=False)
    level          = serializers.IntegerField(required=False)
    badges_earned  = serializers.ListField(child=serializers.CharField(), required=False)
    timestamp      = serializers.DateTimeField(read_only=True)


class TaskListResponseSchema(serializers.Serializer):
    """Single task item in list endpoint."""
    task_id      = serializers.CharField()
    name         = serializers.CharField()
    category     = serializers.CharField()
    system_type  = serializers.CharField()
    is_active    = serializers.BooleanField()
    is_featured  = serializers.BooleanField()
    reward_info  = serializers.DictField(required=False)
    created_at   = serializers.DateTimeField()


class BulkTaskActionSchema(serializers.Serializer):
    """Request body for bulk activate/deactivate."""
    ids    = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=500)
    action = serializers.ChoiceField(choices=['activate', 'deactivate', 'delete'])


# ══════════════════════════════════════════════════════════════════════════════
# COMPLETION SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class CompletionListItemSchema(serializers.Serializer):
    """Single completion in list endpoint."""
    id            = serializers.IntegerField()
    task_id       = serializers.CharField(source='task.task_id', read_only=True)
    task_name     = serializers.CharField(source='task.name', read_only=True)
    status        = serializers.CharField()
    reward_amount = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    ip_address    = serializers.CharField()
    completed_at  = serializers.DateTimeField()


class CompletionStatsSchema(serializers.Serializer):
    """Aggregated completion statistics."""
    total_completions   = serializers.IntegerField()
    total_earned        = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    avg_reward          = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    today_completions   = serializers.IntegerField()
    today_earned        = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    this_week_earned    = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    current_streak      = serializers.IntegerField()
    level               = serializers.IntegerField()
    xp_points           = serializers.IntegerField()


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT / WALLET SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class WithdrawalRequestSchema(serializers.Serializer):
    """Request body for withdrawal."""
    amount          = serializers.DecimalField(max_digits=18, decimal_places=8, min_value=Decimal('0.01'))
    payment_method  = serializers.ChoiceField(choices=[
        'paypal', 'payoneer', 'usdt_trc20', 'usdt_erc20', 'bitcoin',
        'ethereum', 'bank_wire', 'bank_ach', 'bkash', 'nagad',
        'rocket', 'wise', 'cashapp', 'gift_card',
    ])
    wallet_address  = serializers.CharField(max_length=200, required=False, default='')
    notes           = serializers.CharField(max_length=500, required=False, default='')


class WithdrawalResponseSchema(serializers.Serializer):
    """Response for withdrawal request."""
    status         = serializers.ChoiceField(choices=['queued', 'processing', 'completed', 'failed', 'on_hold'])
    withdrawal_id  = serializers.IntegerField()
    amount         = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    payment_method = serializers.CharField()
    estimated_eta  = serializers.CharField(required=False)
    message        = serializers.CharField(required=False)
    timestamp      = serializers.DateTimeField()


class WalletBalanceSchema(serializers.Serializer):
    """Wallet balance response."""
    balance         = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    pending         = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    total_earned    = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    total_withdrawn = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    currency        = serializers.CharField(default='USD')


class CryptoWithdrawalRequestSchema(serializers.Serializer):
    """Request body for USDT/Crypto withdrawal."""
    amount          = serializers.DecimalField(max_digits=18, decimal_places=8, min_value=Decimal('0.01'))
    crypto_type     = serializers.ChoiceField(choices=[
        'usdt_trc20', 'usdt_erc20', 'bitcoin', 'ethereum', 'bnb', 'matic'
    ])
    wallet_address  = serializers.CharField(max_length=200)
    network         = serializers.CharField(max_length=20, required=False, default='')


# ══════════════════════════════════════════════════════════════════════════════
# OFFER / CPA SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class OfferWallRequestSchema(serializers.Serializer):
    """Query params for offer wall."""
    country    = serializers.CharField(max_length=2, required=False, default='US')
    device     = serializers.ChoiceField(
        choices=['desktop', 'mobile', 'tablet'],
        required=False, default='desktop'
    )
    os         = serializers.CharField(max_length=20, required=False, default='')
    category   = serializers.CharField(max_length=50, required=False, default='')
    page_size  = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)


class OfferItemSchema(serializers.Serializer):
    """Single offer in offerwall response."""
    offer_id        = serializers.CharField()
    name            = serializers.CharField()
    description     = serializers.CharField(required=False)
    payout          = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    epc             = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    cvr             = serializers.FloatField()
    quality_score   = serializers.FloatField()
    category        = serializers.CharField()
    icon_url        = serializers.URLField(required=False)
    offer_url       = serializers.URLField()
    is_featured     = serializers.BooleanField()


class PostbackRequestSchema(serializers.Serializer):
    """S2S postback query parameters."""
    click_id        = serializers.CharField(max_length=100)
    offer_id        = serializers.CharField(max_length=100)
    transaction_id  = serializers.CharField(max_length=200, required=False, default='')
    payout          = serializers.CharField(max_length=20, required=False, default='0')
    status          = serializers.ChoiceField(
        choices=['approved', 'rejected', 'pending'],
        required=False, default='approved'
    )
    pub_id          = serializers.CharField(max_length=50, required=False, default='')
    country         = serializers.CharField(max_length=2, required=False, default='')


class PostbackResponseSchema(serializers.Serializer):
    """Response for S2S postback."""
    status         = serializers.CharField()
    click_id       = serializers.CharField()
    payout         = serializers.CharField()
    credited       = serializers.BooleanField()
    message        = serializers.CharField(required=False)
    timestamp      = serializers.DateTimeField()


# ══════════════════════════════════════════════════════════════════════════════
# MONITORING SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class WorkerHealthSchema(serializers.Serializer):
    """Worker health status."""
    worker_id       = serializers.CharField()
    hostname        = serializers.CharField()
    status          = serializers.CharField()
    active_tasks    = serializers.IntegerField()
    concurrency     = serializers.IntegerField()
    load_pct        = serializers.FloatField()
    last_heartbeat  = serializers.DateTimeField()
    queues          = serializers.ListField(child=serializers.CharField())


class QueueDepthSchema(serializers.Serializer):
    """Queue depth snapshot."""
    queue_name  = serializers.CharField()
    depth       = serializers.IntegerField()
    checked_at  = serializers.DateTimeField()


class TaskStatsSchema(serializers.Serializer):
    """Task performance statistics."""
    task_name       = serializers.CharField()
    total_runs      = serializers.IntegerField()
    successes       = serializers.IntegerField()
    failures        = serializers.IntegerField()
    success_rate    = serializers.FloatField()
    avg_duration_s  = serializers.FloatField()
    p95_duration_s  = serializers.FloatField()
    last_run_at     = serializers.DateTimeField(allow_null=True)


class DLQEntrySchema(serializers.Serializer):
    """Dead letter queue entry."""
    id              = serializers.IntegerField()
    task_name       = serializers.CharField()
    task_id         = serializers.CharField()
    failure_reason  = serializers.CharField()
    retry_count     = serializers.IntegerField()
    reprocess_status = serializers.CharField()
    failed_at       = serializers.DateTimeField()
    exception       = serializers.CharField()


class DLQRequeueSchema(serializers.Serializer):
    """Request to requeue DLQ entries."""
    ids     = serializers.ListField(child=serializers.IntegerField(), required=False)
    all_pending = serializers.BooleanField(required=False, default=False)
    notes   = serializers.CharField(max_length=500, required=False, default='')


# ══════════════════════════════════════════════════════════════════════════════
# GAMIFICATION SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class LeaderboardEntrySchema(serializers.Serializer):
    """Single leaderboard entry."""
    rank          = serializers.IntegerField()
    user_id       = serializers.IntegerField()
    username      = serializers.CharField()
    total_earned  = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    completions   = serializers.IntegerField()
    level         = serializers.IntegerField()
    avatar_url    = serializers.URLField(required=False, allow_null=True)


class UserProfileSchema(serializers.Serializer):
    """User gamification profile."""
    user_id         = serializers.IntegerField()
    username        = serializers.CharField()
    level           = serializers.IntegerField()
    xp_points       = serializers.IntegerField()
    xp_to_next_level = serializers.IntegerField()
    current_streak  = serializers.IntegerField()
    longest_streak  = serializers.IntegerField()
    total_earned    = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    badges          = serializers.ListField(child=serializers.CharField())
    publisher_tier  = serializers.CharField()
    is_vip          = serializers.BooleanField()
    traffic_tier    = serializers.CharField()


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class PlatformKPISchema(serializers.Serializer):
    """Platform-wide KPI snapshot."""
    dau                 = serializers.IntegerField()
    mau                 = serializers.IntegerField()
    revenue_today       = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    revenue_this_week   = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    revenue_this_month  = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    completion_rate     = serializers.FloatField()
    avg_reward          = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    active_campaigns    = serializers.IntegerField()
    active_offers       = serializers.IntegerField()
    fraud_rate_today    = serializers.FloatField()
    generated_at        = serializers.DateTimeField()


class RevenueChartSchema(serializers.Serializer):
    """Data point for revenue chart."""
    date     = serializers.DateField()
    revenue  = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)
    count    = serializers.IntegerField()


# ══════════════════════════════════════════════════════════════════════════════
# WORKFLOW SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowTriggerSchema(serializers.Serializer):
    """Request to trigger a workflow manually."""
    workflow_id = serializers.IntegerField()
    context     = serializers.DictField(required=False, default=dict)
    async_run   = serializers.BooleanField(required=False, default=True)


class WorkflowInstanceSchema(serializers.Serializer):
    """Workflow instance status."""
    id          = serializers.IntegerField()
    workflow_id = serializers.IntegerField()
    status      = serializers.CharField()
    started_at  = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)
    error       = serializers.CharField(allow_blank=True)
    steps_log   = serializers.ListField(child=serializers.DictField())


# ══════════════════════════════════════════════════════════════════════════════
# COMMON RESPONSE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class SuccessResponseSchema(serializers.Serializer):
    """Generic success response."""
    status    = serializers.CharField(default='success')
    message   = serializers.CharField(required=False)
    data      = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField()


class ErrorResponseSchema(serializers.Serializer):
    """Generic error response."""
    status    = serializers.CharField(default='error')
    error     = serializers.CharField()
    message   = serializers.CharField()
    code      = serializers.CharField(required=False)
    details   = serializers.DictField(required=False)
    timestamp = serializers.DateTimeField()


class PaginatedSchema(serializers.Serializer):
    """Paginated list wrapper."""
    pagination = serializers.DictField()
    results    = serializers.ListField()


__all__ = [
    'TaskCompleteRequestSchema', 'TaskCompleteResponseSchema', 'TaskListResponseSchema',
    'BulkTaskActionSchema', 'CompletionListItemSchema', 'CompletionStatsSchema',
    'WithdrawalRequestSchema', 'WithdrawalResponseSchema', 'WalletBalanceSchema',
    'CryptoWithdrawalRequestSchema', 'OfferWallRequestSchema', 'OfferItemSchema',
    'PostbackRequestSchema', 'PostbackResponseSchema',
    'WorkerHealthSchema', 'QueueDepthSchema', 'TaskStatsSchema',
    'DLQEntrySchema', 'DLQRequeueSchema',
    'LeaderboardEntrySchema', 'UserProfileSchema',
    'PlatformKPISchema', 'RevenueChartSchema',
    'WorkflowTriggerSchema', 'WorkflowInstanceSchema',
    'SuccessResponseSchema', 'ErrorResponseSchema', 'PaginatedSchema',
]
