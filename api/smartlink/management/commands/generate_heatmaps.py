import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Build geo heatmap data for all active SmartLinks'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Build heatmaps for last N days (default: 7)')
        parser.add_argument('--smartlink-slug', type=str, help='Build only for specific slug')

    def handle(self, *args, **options):
        from ...models import SmartLink
        from ...services.analytics.HeatmapService import HeatmapService

        svc = HeatmapService()
        days = options['days']
        today = timezone.now().date()

        if options['smartlink_slug']:
            try:
                smartlinks = [SmartLink.objects.get(slug=options['smartlink_slug'])]
            except SmartLink.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"SmartLink '{options['smartlink_slug']}' not found."))
                return
        else:
            smartlinks = list(SmartLink.objects.filter(is_active=True, is_archived=False))

        total = 0
        for sl in smartlinks:
            for i in range(days):
                date = today - datetime.timedelta(days=i)
                try:
                    svc.build_heatmap_for_date(sl, date)
                    total += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Error for [{sl.slug}] {date}: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'✅ Built heatmaps for {len(smartlinks)} SmartLinks × {days} days = {total} entries.'
        ))
