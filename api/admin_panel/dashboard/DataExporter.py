import csv
from django.http import HttpResponse
from api.users.models import User
import os
from django.conf import settings


class DataExporter:
    
    @staticmethod
    def export_data(export_type='users'):
        """Export data to CSV"""
        file_path = os.path.join(settings.MEDIA_ROOT, 'exports', f'{export_type}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv')
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        if export_type == 'users':
            return DataExporter._export_users(file_path)
        
        return file_path
    
    @staticmethod
    def _export_users(file_path):
        """Export users to CSV"""
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ID', 'Username', 'Email', 'Phone', 'Balance', 'Verified', 'Created At'])
            
            for user in User.objects.all():
                writer.writerow([
                    user.id,
                    user.username,
                    user.email,
                    user.phone,
                    user.balance,
                    user.is_verified,
                    user.created_at
                ])
        
        return file_path