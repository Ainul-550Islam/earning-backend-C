from django.core.management.base import BaseCommand
from api.admin_panel.dashboard.DataExporter import DataExporter


class Command(BaseCommand):
    help = 'Export users to CSV'
    
    def handle(self, *args, **options):
        file_path = DataExporter.export_data('users')
        self.stdout.write(self.style.SUCCESS(f'Users exported to {file_path}'))