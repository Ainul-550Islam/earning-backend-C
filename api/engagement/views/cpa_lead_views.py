# engagement/views/cpa_lead_views.py
"""
CPAlead Integration Views
Handles postback callbacks from CPAlead and integrates with engagement system.
"""
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..services import QuestService, AnalyticsService, XPService, CoinService
from ..services.gamification_engine import GamificationEngine
from ..exceptions import EngagementError

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST", "GET"])
def cpa_lead_postback(request):
    """
    CPAlead Postback Handler
    Endpoint: /engagement/cpa-lead/postback/
    
    Expected parameters:
    - user_id: User identifier
    - offer_id: Offer/Task identifier  
    - payout: Amount earned
    - status: conversion status (1=credited, 2=reversed)
    - signature: HMAC signature for verification
    """
    try:
        # Extract postback data
        user_id = request.GET.get('user_id') or request.POST.get('user_id')
        offer_id = request.GET.get('offer_id') or request.POST.get('offer_id') 
        payout = request.GET.get('payout') or request.POST.get('payout')
        status = request.GET.get('status') or request.POST.get('status')
        signature = request.GET.get('signature') or request.POST.get('signature')
        
        if not all([user_id, offer_id, payout, status]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameters'
            }, status=400)
        
        # Verify signature (implementation depends on CPAlead setup)
        if not _verify_signature(request.GET or request.POST, signature):
            return JsonResponse({
                'status': 'error', 
                'message': 'Invalid signature'
            }, status=401)
        
        # Process the conversion
        result = _process_cpa_lead_conversion(user_id, offer_id, payout, status)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Postback processed',
            'result': result
        })
        
    except Exception as exc:
        logger.exception("CPAlead postback processing failed: %s", exc)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def earning_task_complete(request):
    """
    EarningTask Completion Bridge
    Endpoint: /engagement/earning-task/complete/
    
    Called by API app when an earning task is completed.
    Bridges earning completion to engagement quest progress.
    """
    try:
        user = request.user
        task_id = request.data.get('task_id')
        offer_id = request.data.get('offer_id') 
        amount = float(request.data.get('amount', 0))
        xp_awarded = int(request.data.get('xp_awarded', 0))
        
        if not task_id:
            return Response({
                'success': False,
                'error': 'task_id is required'
            }, status=400)
        
        tenant = getattr(user, "tenant", None)
        
        # Record quest action for earning task completion
        quest_result = QuestService.record_action(
            user, 
            action="earn_task", 
            increment=1, 
            tenant=tenant
        )
        
        # Grant XP if specified
        xp_result = None
        if xp_awarded > 0:
            xp_result = XPService.grant(
                user, 
                xp_awarded, 
                source="earning_task",
                ref_id=task_id
            )
        
        # Grant coins if specified (convert amount to coins)
        coins_result = None
        coins_to_grant = 0  # initialize to avoid NameError below
        if amount > 0:
            # Convert payout amount to coins (1:1 ratio or as configured)
            coins_to_grant = _convert_payout_to_coins(amount)
            coins_result = CoinService.add(
                user, 
                coins_to_grant, 
                source="earning_task",
                ref_id=task_id
            )
        
        # Trigger gamification engine
        GamificationEngine.on_earning_complete(
            user, 
            {
                'task_id': task_id,
                'offer_id': offer_id,
                'amount': amount,
                'xp_awarded': xp_awarded,
                'coins_granted': coins_to_grant if amount > 0 else 0
            },
            tenant=tenant
        )
        
        # Record analytics event
        AnalyticsService.record(
            user,
            "earning_task_completed",
            coins_delta=coins_to_grant if amount > 0 else 0,
            xp_delta=xp_awarded,
            value=amount,
            properties={
                'task_id': task_id,
                'offer_id': offer_id,
                'conversion_type': 'earning_task'
            },
            tenant=tenant
        )
        
        return Response({
            'success': True,
            'quest_progress': quest_result,
            'xp_granted': xp_result,
            'coins_granted': {
                'amount': float(coins_result) if coins_result else 0,
                'source': 'earning_task'
            } if coins_result else None
        })
        
    except EngagementError as exc:
        return Response({
            'success': False,
            'error': str(exc.detail),
            'code': exc.default_code
        }, status=exc.status_code)
    except Exception as exc:
        logger.exception("EarningTask completion failed: %s", exc)
        return Response({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


# ── Private Helper Functions ───────────────────────────────────────────────

def _verify_signature(params, signature):
    """
    Verify CPAlead postback signature using HMAC-SHA256.
    Set CPALEAD_SECRET_KEY in Django settings.
    """
    import hmac, hashlib
    from django.conf import settings
    secret_key = getattr(settings, "CPALEAD_SECRET_KEY", "")
    if not secret_key:
        # If no secret configured, skip verification (log warning)
        import logging
        logging.getLogger(__name__).warning("CPALEAD_SECRET_KEY not set — skipping signature verification")
        return True
    if not signature:
        return False
    # Build query string from params for signing
    param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "signature")
    expected = hmac.new(secret_key.encode(), param_str.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _process_cpa_lead_conversion(user_id, offer_id, payout, status):
    """
    Process CPAlead conversion and integrate with engagement system.
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get user by user_id (adjust based on your user identification method)
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.error("User not found for CPAlead conversion: %s", user_id)
            return {'error': 'User not found'}
        
        # Only process credited conversions
        if status != '1':
            logger.info("CPAlead conversion not credited: user=%s, status=%s", user_id, status)
            return {'status': 'ignored', 'reason': 'Not credited'}
        
        tenant = getattr(user, "tenant", None)
        payout_amount = float(payout)
        
        # Convert payout to coins
        coins_granted = _convert_payout_to_coins(payout_amount)
        
        # Grant coins
        new_balance = CoinService.add(
            user, 
            coins_granted, 
            source="cpa_lead",
            ref_id=offer_id
        )
        
        # Grant XP (base XP for conversions)
        xp_granted = max(10, int(payout_amount * 0.1))  # 10% of payout as XP, minimum 10
        xp_result = XPService.grant(
            user, 
            xp_granted, 
            source="cpa_lead",
            ref_id=offer_id
        )
        
        # Record quest action
        quest_result = QuestService.record_action(
            user, 
            action="cpa_conversion", 
            increment=1, 
            tenant=tenant
        )
        
        # Trigger gamification engine
        GamificationEngine.on_earning_complete(
            user, 
            {
                'offer_id': offer_id,
                'payout': payout_amount,
                'coins_granted': coins_granted,
                'xp_granted': xp_granted
            },
            tenant=tenant
        )
        
        # Record analytics
        AnalyticsService.record(
            user,
            "cpa_lead_conversion",
            coins_delta=coins_granted,
            xp_delta=xp_granted,
            value=payout_amount,
            properties={
                'offer_id': offer_id,
                'conversion_type': 'cpa_lead'
            },
            tenant=tenant
        )
        
        logger.info(
            "CPAlead conversion processed: user=%s, offer=%s, payout=%s, coins=%s, xp=%s",
            user.pk, offer_id, payout_amount, coins_granted, xp_granted
        )
        
        return {
            'coins_granted': float(coins_granted),
            'xp_granted': xp_granted,
            'new_balance': float(new_balance),
            'quest_progress': quest_result
        }
        
    except Exception as exc:
        logger.exception("Failed to process CPAlead conversion: %s", exc)
        return {'error': 'Processing failed'}


def _convert_payout_to_coins(payout_amount):
    """
    Convert payout amount to coins.
    Adjust conversion rate as needed for your economy.
    """
    # Default 1:1 conversion (1 payout unit = 1 coin)
    # Adjust this based on your game economy
    conversion_rate = 1.0
    return int(payout_amount * conversion_rate)
