# api/admin_panel/dashboard/DataExporter.py
"""Data exporter for admin dashboard — exports users, transactions, etc. to CSV."""
import csv
import os
from django.conf import settings
from django.utils import timezone


class DataExporter:

    @staticmethod
    def export_data(export_type='users'):
        """Export data to CSV file. Returns file path."""
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(export_dir, f'{export_type}_{timestamp}.csv')

        if export_type == 'users':
            return DataExporter._export_users(file_path)
        elif export_type == 'transactions':
            return DataExporter._export_transactions(file_path)
        elif export_type == 'withdrawals':
            return DataExporter._export_withdrawals(file_path)
        else:
            # Generic empty export
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['export_type', 'status'])
                writer.writerow([export_type, 'no_handler'])
            return file_path

    @staticmethod
    def _export_users(file_path: str) -> str:
        """Export users to CSV."""
        from api.users.models import User
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'ID', 'Username', 'Email', 'First Name', 'Last Name',
                'Is Active', 'Is Staff', 'Date Joined',
            ])
            for user in User.objects.all().iterator(chunk_size=500):
                writer.writerow([
                    user.id,
                    user.username,
                    user.email,
                    user.first_name,
                    user.last_name,
                    user.is_active,
                    user.is_staff,
                    user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else '',
                ])
        return file_path

    @staticmethod
    def _export_transactions(file_path: str) -> str:
        """Export transactions to CSV."""
        try:
            from api.transactions.models import Transaction
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['ID', 'User', 'Type', 'Amount', 'Status', 'Created At'])
                for tx in Transaction.objects.all().iterator(chunk_size=500):
                    writer.writerow([
                        tx.id,
                        tx.user.username if tx.user else '',
                        tx.transaction_type,
                        tx.amount,
                        tx.status,
                        tx.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    ])
        except ImportError:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(['error', 'Transaction model not available'])
        return file_path

    @staticmethod
    def _export_withdrawals(file_path: str) -> str:
        """Export withdrawals to CSV."""
        try:
            from api.withdrawals.models import Withdrawal
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['ID', 'User', 'Amount', 'Method', 'Status', 'Created At'])
                for wd in Withdrawal.objects.all().iterator(chunk_size=500):
                    writer.writerow([
                        wd.id,
                        wd.user.username if wd.user else '',
                        wd.amount,
                        getattr(wd, 'payment_method', ''),
                        wd.status,
                        wd.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    ])
        except ImportError:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(['error', 'Withdrawal model not available'])
        return file_path