from django.core.management.base import BaseCommand
from api.admin_panel.dashboard.DashboardService import DashboardService


class Command(BaseCommand):
    help = 'Generate dashboard report'
    
    def handle(self, *args, **options):
        stats = DashboardService.get_dashboard_stats()
        
        self.stdout.write(self.style.SUCCESS('=== Dashboard Statistics ==='))
        for key, value in stats.items():
            self.stdout.write(f'{key}: {value}')