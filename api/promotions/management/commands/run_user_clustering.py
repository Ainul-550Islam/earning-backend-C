from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.clustering')

class Command(BaseCommand):
    help = 'Run K-Means clustering to segment users by quality'

    def add_arguments(self, parser):
        parser.add_argument('--k', type=int, default=5, help='Number of clusters')

    def handle(self, *args, **options):
        from api.promotions.data_science.user_clustering import UserClusterer
        clusterer = UserClusterer()
        result    = clusterer.cluster_users(n_clusters=options['k'])
        self.stdout.write(self.style.SUCCESS(
            f"Clustering done: {result.get('n_clusters')} clusters, {result.get('n_users',0)} users"
        ))
