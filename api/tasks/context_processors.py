"""
api/tasks/context_processors.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Django template context processors for the task system.
Injects task-related data into all template contexts
(useful for base templates showing wallet balance, streak, etc.)

Add to settings.py:
    TEMPLATES[0]['OPTIONS']['context_processors'] += [
        'api.tasks.context_processors.task_context',
        'api.tasks.context_processors.gamification_context',
    ]
"""

import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


def task_context(request) -> dict:
    """
    Inject core task data into template context.
    Only runs for authenticated users.
    """
    ctx = {
        'task_wallet_balance':  None,
        'task_fraud_score':     0,
        'task_kyc_tier':        'none',
        'task_publisher_tier':  'bronze',
        'task_is_vip':          False,
        'task_is_suspended':    False,
    }

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return ctx

    user_id = request.user.pk
    try:
        ctx['task_wallet_balance'] = cache.get(f'wallet_balance_{user_id}')
        ctx['task_fraud_score']    = int(cache.get(f'fraud_score_{user_id}', 0))
        ctx['task_kyc_tier']       = cache.get(f'kyc_tier_{user_id}', 'none')
        ctx['task_publisher_tier'] = cache.get(f'publisher_tier_{user_id}', 'bronze')
        ctx['task_is_vip']         = bool(cache.get(f'user_is_vip_{user_id}', False))
        ctx['task_is_suspended']   = bool(cache.get(f'user_suspended_{user_id}', False))
    except Exception as e:
        logger.debug(f"[CTX PROC] task_context: {e}")

    return ctx


def gamification_context(request) -> dict:
    """Inject gamification data (level, XP, streak, badges) into context."""
    ctx = {
        'task_level':       1,
        'task_xp':          0,
        'task_streak':      0,
        'task_badges':      [],
        'task_user_segment': 'new_user',
    }

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return ctx

    user_id = request.user.pk
    try:
        ctx['task_level']        = int(cache.get(f'user_level_{user_id}', 1))
        ctx['task_xp']           = int(cache.get(f'user_xp_{user_id}', 0))
        ctx['task_streak']       = int(cache.get(f'user_streak_{user_id}', 0))
        ctx['task_badges']       = list(cache.get(f'user_badges_{user_id}') or [])
        ctx['task_user_segment'] = cache.get(f'user_segment_{user_id}', 'new_user')
    except Exception as e:
        logger.debug(f"[CTX PROC] gamification_context: {e}")

    return ctx


def tenant_context(request) -> dict:
    """Inject tenant information into template context."""
    ctx = {
        'tenant': None,
        'tenant_id': None,
        'tenant_name': None,
        'tenant_domain': None,
        'tenant_features': {},
        'tenant_limits': {},
    }
    
    try:
        # Get tenant from request if available
        if hasattr(request, 'tenant_context'):
            tenant_ctx = request.tenant_context
            ctx.update({
                'tenant': tenant_ctx,
                'tenant_id': tenant_ctx.get('tenant_id'),
                'tenant_name': tenant_ctx.get('tenant_name'),
                'tenant_domain': tenant_ctx.get('domain'),
                'tenant_features': tenant_ctx.get('features', {}),
                'tenant_limits': tenant_ctx.get('resource_limits', {}),
            })
        
        # Fallback: try to get tenant from user
        elif hasattr(request, 'user') and request.user.is_authenticated:
            try:
                from tenants.models import Tenant
                user_tenant_id = getattr(request.user, 'tenant_id', None)
                if user_tenant_id:
                    tenant = Tenant.objects.filter(id=user_tenant_id, is_active=True).first()
                    if tenant:
                        ctx.update({
                            'tenant': tenant,
                            'tenant_id': tenant.id,
                            'tenant_name': tenant.name,
                            'tenant_domain': tenant.domain,
                            'tenant_features': tenant.get_feature_flags(),
                            'tenant_limits': tenant.enforce_resource_limits(),
                        })
            except Exception:
                pass
                
    except Exception as e:
        logger.debug(f"[CTX PROC] tenant_context: {e}")
    
    return ctx


def platform_stats_context(request) -> dict:
    """Inject platform-wide stats for admin dashboard templates."""
    ctx = {'platform_kpis': {}}
    if not hasattr(request, 'user') or not request.user.is_staff:
        return ctx
    try:
        from api.tasks.integration.data_bridge import DataBridge
        ctx['platform_kpis'] = DataBridge.get_platform_snapshot()
    except Exception as e:
        logger.debug(f"[CTX PROC] platform_stats_context: {e}")
    return ctx
