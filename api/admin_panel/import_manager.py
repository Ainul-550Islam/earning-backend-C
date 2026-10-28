# api/admin_panel/import_manager.py
"""Bulk CSV/Excel import for offers, users, configs — admin controlled."""
from __future__ import annotations
import csv, io, logging
from typing import Any, Dict, List, Tuple
from django.utils import timezone

logger = logging.getLogger(__name__)


class ImportManager:
    """Bulk data import with validation and dry-run support."""

    @classmethod
    def import_users_csv(cls, csv_data: str, dry_run: bool = True) -> Dict:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        reader = csv.DictReader(io.StringIO(csv_data))
        results = {'created': 0, 'skipped': 0, 'errors': [], 'dry_run': dry_run}
        for row in reader:
            username = row.get('username', '').strip()
            email    = row.get('email', '').strip()
            if not username or not email:
                results['errors'].append({'row': row, 'error': 'Missing username or email'})
                continue
            if User.objects.filter(username=username).exists():
                results['skipped'] += 1
                continue
            if not dry_run:
                User.objects.create_user(username=username, email=email,
                                          password=row.get('password', 'ChangeMe123!'))
            results['created'] += 1
        return results

    @classmethod
    def import_offers_csv(cls, csv_data: str, dry_run: bool = True, actor=None) -> Dict:
        from api.offer_inventory.models import Offer
        reader = csv.DictReader(io.StringIO(csv_data))
        results = {'created': 0, 'updated': 0, 'errors': [], 'dry_run': dry_run}
        for row in reader:
            title = row.get('title', '').strip()
            payout = row.get('payout', '0')
            if not title:
                results['errors'].append({'row': row, 'error': 'Missing title'})
                continue
            if not dry_run:
                obj, created = Offer.objects.update_or_create(
                    title=title,
                    defaults={'payout': payout, 'is_active': row.get('is_active', '1') == '1'}
                )
                if created: results['created'] += 1
                else: results['updated'] += 1
            else:
                results['created'] += 1
        return results

    @classmethod
    def import_system_config_csv(cls, csv_data: str, dry_run: bool = True, actor=None) -> Dict:
        from api.admin_panel.models.config import SystemConfig
        reader = csv.DictReader(io.StringIO(csv_data))
        results = {'updated': 0, 'created': 0, 'errors': [], 'dry_run': dry_run}
        for row in reader:
            key = row.get('key', '').strip()
            value = row.get('value', '')
            if not key:
                results['errors'].append({'row': row, 'error': 'Missing key'})
                continue
            if not dry_run:
                _, created = SystemConfig.objects.update_or_create(
                    key=key,
                    defaults={'value': value, 'group': row.get('group', 'general')}
                )
                if created: results['created'] += 1
                else: results['updated'] += 1
            else:
                results['updated'] += 1
        return results

import_manager = ImportManager()