"""
tasks/integration/__init__.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Central Integration Hub
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Single import point for the entire integration layer.
All tasks, services, and external systems connect through here.

Usage:
    from api.tasks.integration import DataBridge, EventBus, SharedContext

    # Share data between tasks
    DataBridge.set('user_123_earnings', 45.50, ttl=3600)
    earnings = DataBridge.get('user_123_earnings')

    # Fire events
    EventBus.emit('user.task_completed', {'user_id': 123, 'task_id': 'TASK_001'})

    # Cross-system context
    ctx = SharedContext.for_user(123)
    ctx.wallet_balance   # live wallet balance
    ctx.fraud_score      # latest fraud score
    ctx.kyc_tier         # KYC verification level
"""

from api.tasks.integration.event_bus import EventBus
from api.tasks.integration.data_bridge import DataBridge
from api.tasks.integration.shared_context import SharedContext, UserContext
from api.tasks.integration.registry import IntegrationRegistry, register_handler
from api.tasks.integration.pipeline import DataPipeline

__all__ = [
    'EventBus',
    'DataBridge',
    'SharedContext',
    'UserContext',
    'IntegrationRegistry',
    'register_handler',
    'DataPipeline',
]

__version__ = '1.0.0'
