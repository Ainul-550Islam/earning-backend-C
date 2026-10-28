# api/referral/context_processors.py
# Django template context processors for referral module
# Makes referral data available in all templates automatically
# ============================================================


def referral_context(request):
    """
    Inject referral data into every Django template context.
    Add to settings.py:
        TEMPLATES[0]['OPTIONS']['context_processors'] += [
            'api.referral.context_processors.referral_context',
        ]
    """
    context = {
        'referral_program_active': False,
        'user_referral_code': '',
        'user_referral_link': '',
        'active_campaign': None,
        'referral_stats': {},
    }

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return context

    try:
        from django.core.cache import cache
        from api.referral.models import ReferralSettings

        settings = cache.get('referral_settings')
        if not settings:
            settings = ReferralSettings.objects.first()

        if settings and settings.is_active:
            context['referral_program_active'] = True

        # User referral code
        from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
        bridge = get_bridge()
        code = bridge.get_referral_code(request.user)
        if code:
            from django.conf import settings as django_settings
            base = getattr(django_settings, 'FRONTEND_URL', '')
            context['user_referral_code'] = code
            context['user_referral_link'] = f'{base}/go/{code}/'

        # Active campaign
        campaign = bridge.get_active_campaign()
        if campaign:
            context['active_campaign'] = {
                'name': campaign.name,
                'multiplier': float(campaign.bonus_multiplier),
                'end_date': campaign.end_date.isoformat(),
            }

    except Exception:
        pass

    return context