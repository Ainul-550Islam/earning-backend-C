from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Recalculate all EPC scores for all offer/geo/device combinations'

    def add_arguments(self, parser):
        parser.add_argument('--smartlink-id', type=int, help='Recalculate only for this SmartLink ID')
        parser.add_argument('--days', type=int, default=7, help='Look-back days for calculation (default: 7)')

    def handle(self, *args, **options):
        from ...services.rotation.EPCOptimizer import EPCOptimizer
        self.stdout.write('Recalculating EPC scores...')
        optimizer = EPCOptimizer()
        sl_id = options.get('smartlink_id')
        count = optimizer.recalculate_scores(smartlink_id=sl_id)
        self.stdout.write(self.style.SUCCESS(f'✅ Recalculated {count} offer/geo/device EPC combos.'))
