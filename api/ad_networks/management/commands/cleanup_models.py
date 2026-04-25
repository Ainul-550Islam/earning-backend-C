"""
api/ad_networks/management/commands/cleanup_models.py
Management command for cleaning up all models
SaaS-ready with tenant support
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
import datetime

from ad_networks.models import (
    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
    OfferConversion, OfferWall, AdNetworkWebhookLog,
    NetworkStatistic, UserOfferLimit, OfferSyncLog,
    SmartOfferRecommendation, OfferPerformanceAnalytics,
    FraudDetectionRule, BlacklistedIP, KnownBadIP, OfferClick,
    OfferReward, NetworkAPILog, OfferTag, OfferTagging,
    NetworkHealthCheck, OfferDailyLimit, OfferAttachment, UserWallet
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Clean up all models - remove old data, fix inconsistencies, and optimize'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['stats', 'cleanup-old', 'fix-orphaned', 'optimize', 'verify', 'archive'],
            required=True,
            help='Action to perform'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            default='default',
            help='Tenant ID to process (default: all tenants)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform dry run without making changes'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Days for old data cleanup (default: 90)'
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Specific model to process'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        tenant_id = options['tenant_id']
        dry_run = options['dry_run']
        days = options['days']
        model_name = options['model']
        
        self.stdout.write(f"=== Models Cleanup Management ===")
        self.stdout.write(f"Action: {action}")
        self.stdout.write(f"Tenant ID: {tenant_id}")
        self.stdout.write(f"Dry Run: {dry_run}")
        self.stdout.write(f"Days: {days}")
        if model_name:
            self.stdout.write(f"Model: {model_name}")
        self.stdout.write("=" * 40)
        
        if action == 'stats':
            self.show_stats(tenant_id, model_name)
        elif action == 'cleanup-old':
            self.cleanup_old_data(tenant_id, days, model_name, dry_run)
        elif action == 'fix-orphaned':
            self.fix_orphaned_records(tenant_id, model_name, dry_run)
        elif action == 'optimize':
            self.optimize_models(tenant_id, model_name, dry_run)
        elif action == 'verify':
            self.verify_models(tenant_id, model_name)
        elif action == 'archive':
            self.archive_old_data(tenant_id, days, model_name, dry_run)
    
    def show_stats(self, tenant_id, model_name=None):
        """Show statistics for all models"""
        self.stdout.write("Model Statistics:")
        self.stdout.write("-" * 30)
        
        models_to_check = self._get_models_to_check(model_name)
        
        for model_class, model_name_display in models_to_check:
            queryset = model_class.objects.all()
            if tenant_id != 'all':
                if hasattr(model_class, 'tenant_id'):
                    queryset = queryset.filter(tenant_id=tenant_id)
            
            count = queryset.count()
            
            # Get additional stats based on model
            extra_stats = self._get_model_stats(model_class, queryset)
            
            self.stdout.write(f"\n{model_name_display}:")
            self.stdout.write(f"  Total Records: {count}")
            for key, value in extra_stats.items():
                self.stdout.write(f"  {key}: {value}")
    
    def cleanup_old_data(self, tenant_id, days, model_name=None, dry_run=False):
        """Clean up old data based on age"""
        self.stdout.write(f"Cleaning up data older than {days} days:")
        self.stdout.write("-" * 30)
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        models_to_check = self._get_models_to_check(model_name)
        
        total_deleted = 0
        
        for model_class, model_name_display in models_to_check:
            queryset = model_class.objects.all()
            if tenant_id != 'all':
                if hasattr(model_class, 'tenant_id'):
                    queryset = queryset.filter(tenant_id=tenant_id)
            
            # Filter by created_at or updated_at if available
            if hasattr(model_class, 'created_at'):
                old_records = queryset.filter(created_at__lt=cutoff_date)
            elif hasattr(model_class, 'timestamp'):
                old_records = queryset.filter(timestamp__lt=cutoff_date)
            else:
                continue
            
            count = old_records.count()
            if count > 0:
                self.stdout.write(f"  {model_name_display}: {count} old records")
                if not dry_run:
                    with transaction.atomic():
                        old_records.delete()
                    total_deleted += count
                else:
                    total_deleted += count
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would delete {total_deleted} records")
        else:
            self.stdout.write(f"Deleted {total_deleted} old records")
    
    def fix_orphaned_records(self, tenant_id, model_name=None, dry_run=False):
        """Fix orphaned records"""
        self.stdout.write("Fixing orphaned records:")
        self.stdout.write("-" * 30)
        
        models_to_check = self._get_models_to_check(model_name)
        total_fixed = 0
        
        for model_class, model_name_display in models_to_check:
            queryset = model_class.objects.all()
            if tenant_id != 'all':
                if hasattr(model_class, 'tenant_id'):
                    queryset = queryset.filter(tenant_id=tenant_id)
            
            orphaned = self._find_orphaned_records(model_class, queryset)
            
            if orphaned:
                self.stdout.write(f"  {model_name_display}: {len(orphaned)} orphaned records")
                if not dry_run:
                    with transaction.atomic():
                        for record in orphaned:
                            record.delete()
                    total_fixed += len(orphaned)
                else:
                    total_fixed += len(orphaned)
        
        if dry_run:
            self.stdout.write(f"DRY RUN - Would delete {total_fixed} orphaned records")
        else:
            self.stdout.write(f"Deleted {total_fixed} orphaned records")
    
    def optimize_models(self, tenant_id, model_name=None, dry_run=False):
        """Optimize models - update statistics, indexes, etc."""
        self.stdout.write("Optimizing models:")
        self.stdout.write("-" * 30)
        
        models_to_check = self._get_models_to_check(model_name)
        
        for model_class, model_name_display in models_to_check:
            self.stdout.write(f"  {model_name_display}:")
            
            # Update display orders for models that have it
            if hasattr(model_class, 'display_order'):
                self._update_display_orders(model_class, tenant_id, dry_run)
            
            # Update calculated fields
            self._update_calculated_fields(model_class, tenant_id, dry_run)
            
            # Recalculate statistics
            if model_name_display == 'Network Statistics':
                self._recalculate_network_stats(tenant_id, dry_run)
    
    def verify_models(self, tenant_id, model_name=None):
        """Verify model integrity"""
        self.stdout.write("Verifying model integrity:")
        self.stdout.write("-" * 30)
        
        models_to_check = self._get_models_to_check(model_name)
        issues_found = 0
        
        for model_class, model_name_display in models_to_check:
            self.stdout.write(f"\n{model_name_display}:")
            
            queryset = model_class.objects.all()
            if tenant_id != 'all':
                if hasattr(model_class, 'tenant_id'):
                    queryset = queryset.filter(tenant_id=tenant_id)
            
            model_issues = self._verify_model_integrity(model_class, queryset)
            
            if model_issues:
                issues_found += len(model_issues)
                for issue in model_issues:
                    self.stdout.write(f"  - {issue}")
            else:
                self.stdout.write("  No issues found")
        
        if issues_found == 0:
            self.stdout.write("\nAll models verified successfully")
        else:
            self.stdout.write(f"\nFound {issues_found} total issues")
    
    def archive_old_data(self, tenant_id, days, model_name=None, dry_run=False):
        """Archive old data instead of deleting"""
        self.stdout.write(f"Archiving data older than {days} days:")
        self.stdout.write("-" * 30)
        
        # This is a placeholder for archiving functionality
        # In a real implementation, this would move data to archive tables
        self.stdout.write("Archive functionality not yet implemented")
        self.stdout.write("Use cleanup-old action to delete old data")
    
    def _get_models_to_check(self, model_name=None):
        """Get list of models to check"""
        models = [
            (AdNetwork, 'Ad Networks'),
            (OfferCategory, 'Offer Categories'),
            (Offer, 'Offers'),
            (UserOfferEngagement, 'User Engagements'),
            (OfferConversion, 'Conversions'),
            (OfferWall, 'Offer Walls'),
            (AdNetworkWebhookLog, 'Webhook Logs'),
            (NetworkStatistic, 'Network Statistics'),
            (UserOfferLimit, 'User Limits'),
            (OfferSyncLog, 'Sync Logs'),
            (SmartOfferRecommendation, 'Recommendations'),
            (OfferPerformanceAnalytics, 'Performance Analytics'),
            (FraudDetectionRule, 'Fraud Rules'),
            (BlacklistedIP, 'Blacklisted IPs'),
            (KnownBadIP, 'Known Bad IPs'),
            (OfferClick, 'Offer Clicks'),
            (OfferReward, 'Offer Rewards'),
            (NetworkAPILog, 'API Logs'),
            (OfferTag, 'Offer Tags'),
            (OfferTagging, 'Offer Taggings'),
            (NetworkHealthCheck, 'Health Checks'),
            (OfferDailyLimit, 'Daily Limits'),
            (OfferAttachment, 'Offer Attachments'),
            (UserWallet, 'User Wallets')
        ]
        
        if model_name:
            model_map = {
                'adnetwork': AdNetwork,
                'offercategory': OfferCategory,
                'offer': Offer,
                'userofferengagement': UserOfferEngagement,
                'offerconversion': OfferConversion,
                'offerwall': OfferWall,
                'adnetworkwebhooklog': AdNetworkWebhookLog,
                'networkstatistic': NetworkStatistic,
                'userofferlimit': UserOfferLimit,
                'offersynclog': OfferSyncLog,
                'smarofferrecommendation': SmartOfferRecommendation,
                'offerperformanceanalytics': OfferPerformanceAnalytics,
                'frauddetectionrule': FraudDetectionRule,
                'blacklistedip': BlacklistedIP,
                'knownbadip': KnownBadIP,
                'offerclick': OfferClick,
                'offerreward': OfferReward,
                'networkapilog': NetworkAPILog,
                'offertag': OfferTag,
                'offertagging': OfferTagging,
                'networkhealthcheck': NetworkHealthCheck,
                'offerdailylimit': OfferDailyLimit,
                'offerattachment': OfferAttachment,
                'userwallet': UserWallet
            }
            
            if model_name.lower() in model_map:
                models = [(model_map[model_name.lower()], model_name.title())]
            else:
                self.stdout.write(f"Model '{model_name}' not found")
                models = []
        
        return models
    
    def _get_model_stats(self, model_class, queryset):
        """Get additional statistics for a model"""
        stats = {}
        
        if model_class == Offer:
            stats['Active'] = queryset.filter(is_active=True).count()
            stats['Expired'] = queryset.filter(expires_at__lt=timezone.now()).count()
            stats['By Category'] = queryset.values('category__name').annotate(
                count=models.Count('id')
            ).count()
        
        elif model_class == UserOfferEngagement:
            stats['Completed'] = queryset.filter(status='completed').count()
            stats['Pending'] = queryset.filter(status='pending').count()
            stats['By Status'] = queryset.values('status').annotate(
                count=models.Count('id')
            ).count()
        
        elif model_class == OfferConversion:
            stats['Approved'] = queryset.filter(conversion_status='approved').count()
            stats['Pending'] = queryset.filter(conversion_status='pending').count()
            stats['Rejected'] = queryset.filter(conversion_status='rejected').count()
        
        elif model_class == UserWallet:
            stats['Active'] = queryset.filter(is_active=True).count()
            stats['Frozen'] = queryset.filter(is_frozen=True).count()
            stats['Total Balance'] = queryset.aggregate(
                total=models.Sum('current_balance')
            )['total'] or 0
        
        elif model_class == OfferAttachment:
            stats['By Type'] = queryset.values('file_type').annotate(
                count=models.Count('id')
            ).count()
            stats['Primary'] = queryset.filter(is_primary=True).count()
        
        return stats
    
    def _find_orphaned_records(self, model_class, queryset):
        """Find orphaned records for a model"""
        orphaned = []
        
        # Check for records with invalid foreign keys
        for field in model_class._meta.get_fields():
            if field.many_to_one or field.one_to_one:
                field_name = field.name
                related_model = field.related_model
                
                # Skip if it's a reverse relation or doesn't exist
                if not hasattr(model_class, field_name):
                    continue
                
                # Check for records with null foreign keys that shouldn't be null
                if not field.null:
                    null_records = queryset.filter(**{f"{field_name}__isnull": True})
                    orphaned.extend(null_records)
                
                # Check for records pointing to non-existent objects
                valid_ids = related_model.objects.values_list('id', flat=True)
                invalid_records = queryset.exclude(**{f"{field_name}__in": valid_ids})
                orphaned.extend(invalid_records)
        
        return orphaned
    
    def _update_display_orders(self, model_class, tenant_id, dry_run):
        """Update display orders for models"""
        if model_class in [OfferAttachment, OfferTag]:
            # Group by parent object and reorder
            if model_class == OfferAttachment:
                parent_field = 'offer'
            elif model_class == OfferTag:
                parent_field = None  # Tags don't have a parent field
            
            if parent_field:
                queryset = model_class.objects.all()
                if tenant_id != 'all':
                    queryset = queryset.filter(tenant_id=tenant_id)
                
                # Group by parent
                parents = {}
                for obj in queryset:
                    parent_id = getattr(obj, f"{parent_field}_id")
                    if parent_id not in parents:
                        parents[parent_id] = []
                    parents[parent_id].append(obj)
                
                # Reorder each group
                for parent_id, objects in parents.items():
                    objects.sort(key=lambda x: x.display_order or 999)
                    for index, obj in enumerate(objects):
                        new_order = index + 1
                        if obj.display_order != new_order:
                            if not dry_run:
                                obj.display_order = new_order
                                obj.save(update_fields=['display_order'])
    
    def _update_calculated_fields(self, model_class, tenant_id, dry_run):
        """Update calculated fields"""
        if model_class == UserWallet:
            queryset = model_class.objects.all()
            if tenant_id != 'all':
                queryset = queryset.filter(tenant_id=tenant_id)
            
            for wallet in queryset:
                # Update calculated fields if needed
                pass  # Add specific calculations as needed
    
    def _recalculate_network_stats(self, tenant_id, dry_run):
        """Recalculate network statistics"""
        # Placeholder for network statistics recalculation
        pass
    
    def _verify_model_integrity(self, model_class, queryset):
        """Verify model integrity"""
        issues = []
        
        # Check for required fields
        for field in model_class._meta.fields:
            if not field.null and not field.blank and not field.default:
                # Check for empty values
                if field.name in ['name', 'title', 'description']:
                    empty_records = queryset.filter(**{f"{field.name}__in": ['', None]})
                    if empty_records.exists():
                        issues.append(f"Empty {field.name} field found")
        
        # Check for duplicate unique fields
        for field in model_class._meta.fields:
            if field.unique:
                # This is a simplified check - in practice you'd need more complex logic
                pass
        
        # Model-specific checks
        if model_class == Offer:
            # Check for offers with invalid dates
            invalid_dates = queryset.filter(expires_at__lt=timezone.now(), is_active=True)
            if invalid_dates.exists():
                issues.append(f"{invalid_dates.count()} offers are expired but still active")
        
        elif model_class == UserWallet:
            # Check for negative balances
            negative_balances = queryset.filter(current_balance__lt=0)
            if negative_balances.exists():
                issues.append(f"{negative_balances.count()} wallets have negative balance")
        
        return issues


# Add required imports
from django.db import models
