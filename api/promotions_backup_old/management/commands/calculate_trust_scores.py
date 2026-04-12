from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.trust_scores')

class Command(BaseCommand):
    help = 'Recalculate trust scores for all active users'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1000)

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from api.promotions.governance.trust_score import TrustScoreEngine
        from api.promotions.governance.reputation_system import ReputationSystem
        User  = get_user_model()
        engine = TrustScoreEngine()
        rep    = ReputationSystem()
        users  = User.objects.filter(is_active=True).values_list('id', flat=True)[:options['limit']]
        updated = level_ups = 0

        for uid in users:
            score   = engine.recalculate_and_save(uid)
            result  = rep.check_level_up(uid, score)
            updated += 1
            if result.get('leveled_up'):
                level_ups += 1

        self.stdout.write(self.style.SUCCESS(f'Trust scores updated: {updated} users, {level_ups} level-ups'))
