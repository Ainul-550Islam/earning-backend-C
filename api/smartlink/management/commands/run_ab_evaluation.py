from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Evaluate all running A/B tests for statistical significance'

    def add_arguments(self, parser):
        parser.add_argument('--apply-winners', action='store_true', help='Auto-apply winners to SmartLinks')

    def handle(self, *args, **options):
        from ...models import ABTestResult
        from ...choices import ABTestStatus
        from ...services.rotation.ABTestService import ABTestService

        svc = ABTestService()
        running = ABTestResult.objects.filter(status=ABTestStatus.RUNNING)
        self.stdout.write(f'Evaluating {running.count()} running A/B tests...\n')

        winners = 0
        for result in running:
            data = svc.evaluate_significance(result)
            if data.get('significant'):
                winners += 1
                w = data['winner']
                self.stdout.write(self.style.SUCCESS(
                    f'  ✅ Winner: [{result.smartlink.slug}] → {w.name} '
                    f'uplift={data["uplift"]:.2f}% confidence={data["confidence"]:.3f}'
                ))
                if options['apply_winners']:
                    svc.apply_winner(result)
                    self.stdout.write(f'     → Winner applied automatically.')
            else:
                self.stdout.write(f'  ⏳ [{result.smartlink.slug}] — not significant yet')

        self.stdout.write(self.style.SUCCESS(f'\nDone! {winners} winners found.'))
