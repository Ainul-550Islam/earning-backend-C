from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.optimize_images')

class Command(BaseCommand):
    help = 'Optimize unprocessed proof screenshots'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=500)

    def handle(self, *args, **options):
        from api.promotions.models import TaskSubmission
        from api.promotions.optimization.image_optimizer import ImageOptimizer
        import requests
        optimizer = ImageOptimizer()
        optimized = saved_kb = 0

        subs = TaskSubmission.objects.filter(proof_image_optimized=False).values('id','proof_screenshot_url')[:options['limit']]
        for sub in subs:
            try:
                resp  = requests.get(sub['proof_screenshot_url'], timeout=10)
                orig  = len(resp.content)
                result = optimizer.optimize(resp.content, output_format='webp')
                saved_kb += (orig - result.output_bytes) // 1024
                optimized += 1
                TaskSubmission.objects.filter(pk=sub['id']).update(proof_image_optimized=True)
            except Exception: pass

        self.stdout.write(self.style.SUCCESS(f'Optimized {optimized} images, saved {saved_kb}KB'))
