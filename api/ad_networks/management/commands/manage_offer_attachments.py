"""
api/ad_networks/management/commands/manage_offer_attachments.py
Management command for managing offer attachments
SaaS-ready with tenant support
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import os
import hashlib

from ad_networks.models import OfferAttachment, Offer


class Command(BaseCommand):
    help = 'Manage offer attachments - cleanup, stats, and maintenance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['stats', 'cleanup', 'verify', 'reorder', 'delete-orphaned'],
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
            '--offer-id',
            type=int,
            help='Specific offer ID to process'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        tenant_id = options['tenant_id']
        dry_run = options['dry_run']
        offer_id = options['offer_id']
        
        self.stdout.write(f"=== Offer Attachments Management ===")
        self.stdout.write(f"Action: {action}")
        self.stdout.write(f"Tenant ID: {tenant_id}")
        self.stdout.write(f"Dry Run: {dry_run}")
        if offer_id:
            self.stdout.write(f"Offer ID: {offer_id}")
        self.stdout.write("=" * 40)
        
        if action == 'stats':
            self.show_stats(tenant_id, offer_id)
        elif action == 'cleanup':
            self.cleanup_attachments(tenant_id, offer_id, dry_run)
        elif action == 'verify':
            self.verify_attachments(tenant_id, offer_id)
        elif action == 'reorder':
            self.reorder_attachments(tenant_id, offer_id, dry_run)
        elif action == 'delete-orphaned':
            self.delete_orphaned_attachments(tenant_id, dry_run)
    
    def show_stats(self, tenant_id, offer_id=None):
        """Show attachment statistics"""
        self.stdout.write("Attachment Statistics:")
        self.stdout.write("-" * 30)
        
        queryset = OfferAttachment.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        if offer_id:
            queryset = queryset.filter(offer_id=offer_id)
        
        # Overall stats
        total_count = queryset.count()
        total_size = queryset.aggregate(
            total_size=models.Sum('file_size')
        )['total_size'] or 0
        
        self.stdout.write(f"Total Attachments: {total_count}")
        self.stdout.write(f"Total Size: {self._format_size(total_size)}")
        
        # By file type
        by_type = queryset.values('file_type').annotate(
            count=models.Count('id'),
            size=models.Sum('file_size')
        ).order_by('-count')
        
        self.stdout.write("\nBy File Type:")
        for item in by_type:
            self.stdout.write(f"  {item['file_type']}: {item['count']} files, {self._format_size(item['size'])}")
        
        # By status
        active_count = queryset.filter(is_active=True).count()
        primary_count = queryset.filter(is_primary=True).count()
        
        self.stdout.write(f"\nStatus:")
        self.stdout.write(f"  Active: {active_count}")
        self.stdout.write(f"  Primary: {primary_count}")
        
        # By offer
        if not offer_id:
            offer_counts = queryset.values('offer__title').annotate(
                count=models.Count('id')
            ).order_by('-count')[:10]
            
            self.stdout.write(f"\nTop 10 Offers by Attachments:")
            for item in offer_counts:
                self.stdout.write(f"  {item['offer__title']}: {item['count']}")
    
    def cleanup_attachments(self, tenant_id, offer_id=None, dry_run=False):
        """Clean up invalid attachments"""
        self.stdout.write("Cleaning up attachments:")
        self.stdout.write("-" * 30)
        
        queryset = OfferAttachment.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        if offer_id:
            queryset = queryset.filter(offer_id=offer_id)
        
        # Find attachments with missing files
        missing_files = []
        for attachment in queryset:
            if not attachment.file or not os.path.exists(attachment.file.path):
                missing_files.append(attachment)
        
        if missing_files:
            self.stdout.write(f"Found {len(missing_files)} attachments with missing files")
            if dry_run:
                self.stdout.write("DRY RUN - No files will be deleted")
            else:
                with transaction.atomic():
                    for attachment in missing_files:
                        self.stdout.write(f"Deleting: {attachment.filename}")
                        attachment.delete()
                self.stdout.write(f"Deleted {len(missing_files)} invalid attachments")
        else:
            self.stdout.write("No attachments with missing files found")
        
        # Find duplicate attachments
        duplicates = self._find_duplicates(queryset)
        if duplicates:
            self.stdout.write(f"\nFound {len(duplicates)} duplicate attachments")
            if dry_run:
                self.stdout.write("DRY RUN - No duplicates will be removed")
            else:
                with transaction.atomic():
                    for duplicate_group in duplicates:
                        # Keep the first one, delete the rest
                        for attachment in duplicate_group[1:]:
                            self.stdout.write(f"Deleting duplicate: {attachment.filename}")
                            attachment.delete()
                self.stdout.write(f"Removed {sum(len(g) - 1 for g in duplicates)} duplicates")
        else:
            self.stdout.write("No duplicate attachments found")
    
    def verify_attachments(self, tenant_id, offer_id=None):
        """Verify attachment integrity"""
        self.stdout.write("Verifying attachments:")
        self.stdout.write("-" * 30)
        
        queryset = OfferAttachment.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        if offer_id:
            queryset = queryset.filter(offer_id=offer_id)
        
        issues = []
        
        for attachment in queryset:
            attachment_issues = []
            
            # Check file exists
            if not attachment.file or not os.path.exists(attachment.file.path):
                attachment_issues.append("Missing file")
            
            # Check file size matches
            if attachment.file and os.path.exists(attachment.file.path):
                actual_size = os.path.getsize(attachment.file.path)
                if actual_size != attachment.file_size:
                    attachment_issues.append(f"Size mismatch: {actual_size} vs {attachment.file_size}")
            
            # Check file hash
            if attachment.file and os.path.exists(attachment.file.path):
                actual_hash = self._calculate_file_hash(attachment.file.path)
                if actual_hash != attachment.file_hash:
                    attachment_issues.append("Hash mismatch")
            
            # Check for multiple primary attachments
            if attachment.is_primary:
                primary_count = OfferAttachment.objects.filter(
                    offer=attachment.offer,
                    is_primary=True,
                    tenant_id=attachment.tenant_id
                ).count()
                if primary_count > 1:
                    attachment_issues.append("Multiple primary attachments for offer")
            
            if attachment_issues:
                issues.append({
                    'attachment': attachment,
                    'issues': attachment_issues
                })
        
        if issues:
            self.stdout.write(f"Found {len(issues)} attachments with issues:")
            for item in issues:
                self.stdout.write(f"  {item['attachment'].filename}: {', '.join(item['issues'])}")
        else:
            self.stdout.write("All attachments verified successfully")
    
    def reorder_attachments(self, tenant_id, offer_id=None, dry_run=False):
        """Reorder attachments by display_order"""
        self.stdout.write("Reordering attachments:")
        self.stdout.write("-" * 30)
        
        queryset = OfferAttachment.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        if offer_id:
            queryset = queryset.filter(offer_id=offer_id)
        
        # Group by offer
        offers = {}
        for attachment in queryset:
            if attachment.offer_id not in offers:
                offers[attachment.offer_id] = []
            offers[attachment.offer_id].append(attachment)
        
        reordered_count = 0
        for offer_id, attachments in offers.items():
            # Sort by current display_order, then by created_at
            attachments.sort(key=lambda x: (x.display_order or 999, x.created_at))
            
            # Reorder
            for index, attachment in enumerate(attachments):
                new_order = index + 1
                if attachment.display_order != new_order:
                    if dry_run:
                        self.stdout.write(f"Would reorder {attachment.filename} to position {new_order}")
                    else:
                        attachment.display_order = new_order
                        attachment.save(update_fields=['display_order'])
                        reordered_count += 1
        
        if dry_run:
            self.stdout.write("DRY RUN - No attachments were reordered")
        else:
            self.stdout.write(f"Reordered {reordered_count} attachments")
    
    def delete_orphaned_attachments(self, tenant_id, dry_run=False):
        """Delete attachments for non-existent offers"""
        self.stdout.write("Deleting orphaned attachments:")
        self.stdout.write("-" * 30)
        
        queryset = OfferAttachment.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Find attachments with non-existent offers
        orphaned = []
        for attachment in queryset:
            try:
                attachment.offer
            except Offer.DoesNotExist:
                orphaned.append(attachment)
        
        if orphaned:
            self.stdout.write(f"Found {len(orphaned)} orphaned attachments")
            if dry_run:
                self.stdout.write("DRY RUN - No attachments will be deleted")
            else:
                with transaction.atomic():
                    for attachment in orphaned:
                        self.stdout.write(f"Deleting orphaned: {attachment.filename}")
                        # Delete file
                        if attachment.file and hasattr(attachment.file, 'delete'):
                            attachment.file.delete(save=False)
                        # Delete thumbnail
                        if attachment.thumbnail and hasattr(attachment.thumbnail, 'delete'):
                            attachment.thumbnail.delete(save=False)
                        # Delete attachment
                        attachment.delete()
                self.stdout.write(f"Deleted {len(orphaned)} orphaned attachments")
        else:
            self.stdout.write("No orphaned attachments found")
    
    def _find_duplicates(self, queryset):
        """Find duplicate attachments by file hash"""
        duplicates = []
        seen = {}
        
        for attachment in queryset:
            if attachment.file_hash:
                if attachment.file_hash in seen:
                    seen[attachment.file_hash].append(attachment)
                else:
                    seen[attachment.file_hash] = [attachment]
        
        # Only return groups with more than 1 attachment
        for hash_value, attachments in seen.items():
            if len(attachments) > 1:
                duplicates.append(attachments)
        
        return duplicates
    
    def _calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"


# Add required imports
from django.db import models
