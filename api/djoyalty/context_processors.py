# api/djoyalty/context_processors.py
"""
Djoyalty Context Processors -- Django template context processors।
Add to TEMPLATES[0]['OPTIONS']['context_processors'] in settings।

Usage in templates:
    {{ loyalty.balance }}
    {{ loyalty.tier }}
    {{ loyalty.unread_notifications }}
"""


def loyalty_context(request):
    """
    Inject loyalty data into every template context।
    Only runs if request has a customer attached।
    """
    ctx = {
        'loyalty': {
            'enabled': False,
            'balance': 0,
            'tier': None,
            'tier_name': '',
            'unread_notifications': 0,
            'streak_days': 0,
        }
    }

    # Only inject for authenticated views with customer
    customer = getattr(request, 'loyalty_customer', None)
    if not customer:
        return ctx

    try:
        from .models.points import LoyaltyPoints
        from .models.notifications import NotificationCenter

        lp = LoyaltyPoints.objects.filter(customer=customer).first()
        ut = customer.user_tiers.filter(is_current=True).select_related('tier').first()
        streak = customer.streaks.filter(is_active=True).first()
        unread = NotificationCenter.objects.filter(customer=customer, is_read=False).count()

        ctx['loyalty'] = {
            'enabled': True,
            'customer_code': customer.code,
            'balance': lp.balance if lp else 0,
            'tier': ut.tier if ut else None,
            'tier_name': ut.tier.name if ut else 'Bronze',
            'unread_notifications': unread,
            'streak_days': streak.current_streak if streak else 0,
        }
    except Exception:
        pass

    return ctx


def loyalty_features(request):
    """Inject feature flags into templates।"""
    try:
        from .registry import features
        return {'loyalty_features': features.all_flags()}
    except Exception:
        return {'loyalty_features': {}}
