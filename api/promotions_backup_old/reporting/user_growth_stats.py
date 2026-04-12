# api/promotions/reporting/user_growth_stats.py
import logging
from django.core.cache import cache
logger = logging.getLogger('reporting.users')

class UserGrowthStats:
    def overview(self, days: int = 30) -> dict:
        ck = f'report:users:{days}'
        if cache.get(ck): return cache.get(ck)
        try:
            from django.contrib.auth import get_user_model
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count
            from api.promotions.models import UserReputation
            User  = get_user_model()
            since = timezone.now() - timedelta(days=days)
            total = User.objects.count()
            new   = User.objects.filter(date_joined__gte=since).count()
            active = User.objects.filter(last_login__gte=since).count()
            r = {
                'days': days, 'total_users': total,
                'new_users': new, 'active_users': active,
                'activation_rate': round(active/max(total,1)*100,2),
                'growth_rate':     round(new/max(total-new,1)*100,2),
                'by_country':      dict(User.objects.values('country').annotate(c=Count('id')).order_by('-c').values_list('country','c')[:10]),
                'trust_distribution': {
                    'trusted':    UserReputation.objects.filter(trust_score__gte=80).count(),
                    'good':       UserReputation.objects.filter(trust_score__gte=60,trust_score__lt=80).count(),
                    'fair':       UserReputation.objects.filter(trust_score__gte=40,trust_score__lt=60).count(),
                    'poor':       UserReputation.objects.filter(trust_score__lt=40).count(),
                },
            }
            cache.set(ck, r, timeout=3600)
            return r
        except Exception as e:
            return {'days': days, 'error': str(e)}
