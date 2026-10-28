"""
block_ip_range.py - Management command to block IP ranges.

This command allows administrators to block single IPs, IP ranges, or subnets
with various options for duration, reason, and automatic detection.
"""
from django.db import models
import logging
import ipaddress
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone

from api.rate_limit.services.IPBlockService import IPBlockService
from api.rate_limit.models import IPBlockList

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Block IP addresses, IP ranges, or subnets'
    
    def add_arguments(self, parser):
        # IP specification options
        parser.add_argument(
            '--single-ip',
            type=str,
            help='Block a single IP address'
        )
        parser.add_argument(
            '--ip-range',
            nargs=2,
            metavar=('START_IP', 'END_IP'),
            help='Block an IP range (start and end IP)'
        )
        parser.add_argument(
            '--subnet',
            type=str,
            help='Block a subnet (CIDR notation, e.g., 192.168.1.0/24)'
        )
        
        # Block options
        parser.add_argument(
            '--reason',
            type=str,
            default='manual',
            choices=['manual', 'automatic', 'abuse', 'suspicious', 'security'],
            help='Reason for blocking'
        )
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='Additional description for the block'
        )
        parser.add_argument(
            '--duration-days',
            type=int,
            default=7,
            help='Duration in days (ignored if --permanent)'
        )
        parser.add_argument(
            '--permanent',
            action='store_true',
            help='Create permanent block'
        )
        parser.add_argument(
            '--blocked-by',
            type=str,
            help='Username of admin who is blocking'
        )
        
        # Bulk operations
        parser.add_argument(
            '--from-file',
            type=str,
            help='Load IPs/ranges from file (one per line)'
        )
        parser.add_argument(
            '--auto-block-abusive',
            action='store_true',
            help='Auto-block IPs with high abuse reports'
        )
        parser.add_argument(
            '--abuse-threshold',
            type=int,
            default=5,
            help='Minimum abuse reports for auto-block'
        )
        
        # Utility options
        parser.add_argument(
            '--list-blocks',
            action='store_true',
            help='List current active blocks'
        )
        parser.add_argument(
            '--unblock',
            type=str,
            help='Unblock specific IP address'
        )
        parser.add_argument(
            '--cleanup-expired',
            action='store_true',
            help='Clean up expired blocks'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be blocked without actually doing it'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt'
        )
    
    def handle(self, *args, **options):
        """Execute block command."""
        ip_block_service = IPBlockService()
        
        # List blocks
        if options['list_blocks']:
            self._list_blocks(ip_block_service)
            return
        
        # Unblock IP
        if options['unblock']:
            self._unblock_ip(ip_block_service, options['unblock'])
            return
        
        # Cleanup expired blocks
        if options['cleanup_expired']:
            self._cleanup_expired(ip_block_service)
            return
        
        # Auto-block abusive IPs
        if options['auto_block_abusive']:
            self._auto_block_abusive(ip_block_service, options)
            return
        
        # Get blocking targets
        targets = self._get_blocking_targets(options)
        
        if not targets:
            raise CommandError(
                "Please specify --single-ip, --ip-range, --subnet, --from-file, "
                "--auto-block-abusive, --list-blocks, --unblock, or --cleanup-expired"
            )
        
        # Show what will be blocked
        self._show_blocking_plan(targets, options)
        
        # Confirmation
        if not options['confirm'] and not options['dry_run']:
            self.stdout.write("\n" + "="*60)
            confirm = input(
                self.style.WARNING(
                    "Are you sure you want to proceed? Type 'yes' to continue: "
                )
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return
        
        # Execute blocking
        if options['dry_run']:
            self.stdout.write("\n" + self.style.SUCCESS("DRY RUN - No changes made"))
            return
        
        self._execute_blocking(ip_block_service, targets, options)
    
    def _get_blocking_targets(self, options):
        """Get list of IPs/ranges to block."""
        targets = []
        
        # Single IP
        if options['single_ip']:
            targets.append({
                'type': 'single',
                'ip': options['single_ip']
            })
        
        # IP range
        if options['ip_range']:
            start_ip, end_ip = options['ip_range']
            targets.append({
                'type': 'range',
                'start_ip': start_ip,
                'end_ip': end_ip
            })
        
        # Subnet
        if options['subnet']:
            targets.append({
                'type': 'subnet',
                'subnet': options['subnet']
            })
        
        # From file
        if options['from_file']:
            targets.extend(self._load_from_file(options['from_file']))
        
        return targets
    
    def _load_from_file(self, filename):
        """Load IPs/ranges from file."""
        targets = []
        try:
            with open(filename, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    try:
                        # Try to parse as subnet first
                        if '/' in line:
                            targets.append({
                                'type': 'subnet',
                                'subnet': line,
                                'source': f'line {line_num}'
                            })
                        # Try to parse as range
                        elif '-' in line:
                            start_ip, end_ip = line.split('-', 1)
                            targets.append({
                                'type': 'range',
                                'start_ip': start_ip.strip(),
                                'end_ip': end_ip.strip(),
                                'source': f'line {line_num}'
                            })
                        # Assume single IP
                        else:
                            targets.append({
                                'type': 'single',
                                'ip': line,
                                'source': f'line {line_num}'
                            })
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Warning: Invalid entry on line {line_num}: {line} ({e})"
                            )
                        )
        except FileNotFoundError:
            raise CommandError(f"File not found: {filename}")
        
        return targets
    
    def _show_blocking_plan(self, targets, options):
        """Show what will be blocked."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.WARNING("BLOCKING PLAN:"))
        self.stdout.write("="*60)
        
        for i, target in enumerate(targets, 1):
            if target['type'] == 'single':
                self.stdout.write(f"{i}. 🎯 Single IP: {target['ip']}")
            elif target['type'] == 'range':
                self.stdout.write(f"{i}. 📏 IP Range: {target['start_ip']} - {target['end_ip']}")
            elif target['type'] == 'subnet':
                self.stdout.write(f"{i}. 🌐 Subnet: {target['subnet']}")
            
            if 'source' in target:
                self.stdout.write(f"   📄 Source: {target['source']}")
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.WARNING("BLOCK OPTIONS:"))
        self.stdout.write("="*60)
        self.stdout.write(f"   📝 Reason: {options['reason']}")
        self.stdout.write(f"   📅 Duration: {options['duration_days']} days")
        self.stdout.write(f"   🔒 Permanent: {options['permanent']}")
        if options['description']:
            self.stdout.write(f"   📄 Description: {options['description']}")
        if options['blocked_by']:
            self.stdout.write(f"   👤 Blocked by: {options['blocked_by']}")
    
    def _execute_blocking(self, ip_block_service, targets, options):
        """Execute the blocking operations."""
        blocked_count = 0
        error_count = 0
        
        # Get admin user
        blocked_by_user = None
        if options['blocked_by']:
            try:
                blocked_by_user = User.objects.get(username=options['blocked_by'])
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Warning: User '{options['blocked_by']}' not found, proceeding without admin attribution"
                    )
                )
        
        for target in targets:
            try:
                if target['type'] == 'single':
                    block = ip_block_service.block_ip(
                        ip_address=target['ip'],
                        reason=options['reason'],
                        blocked_by=blocked_by_user,
                        duration_days=options['duration_days'],
                        permanent=options['permanent'],
                        description=options['description']
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Blocked IP: {target['ip']} (ID: {block.id})"
                        )
                    )
                
                elif target['type'] == 'range':
                    block = ip_block_service.block_ip_range(
                        start_ip=target['start_ip'],
                        end_ip=target['end_ip'],
                        reason=options['reason'],
                        blocked_by=blocked_by_user,
                        duration_days=options['duration_days'],
                        permanent=options['permanent'],
                        description=options['description']
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Blocked range: {target['start_ip']} - {target['end_ip']} (ID: {block.id})"
                        )
                    )
                
                elif target['type'] == 'subnet':
                    block = ip_block_service.block_subnet(
                        subnet=target['subnet'],
                        reason=options['reason'],
                        blocked_by=blocked_by_user,
                        duration_days=options['duration_days'],
                        permanent=options['permanent'],
                        description=options['description']
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Blocked subnet: {target['subnet']} (ID: {block.id})"
                        )
                    )
                
                blocked_count += 1
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"   ❌ Error blocking target: {e}"
                    )
                )
                logger.error(f"Error blocking target {target}: {e}")
        
        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS(f"✅ Successfully blocked {blocked_count} target(s)"))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"❌ Failed to block {error_count} target(s)"))
        self.stdout.write("="*60)
    
    def _auto_block_abusive(self, ip_block_service, options):
        """Auto-block IPs with high abuse reports."""
        from api.rate_limit.models import AbuseReport
        
        threshold = options['abuse_threshold']
        
        # Find IPs with abuse reports >= threshold
        abusive_ips = AbuseReport.objects.values('ip_address').annotate(
            report_count=models.Count('id')
        ).filter(report_count__gte=threshold, is_blocked=False)
        
        if not abusive_ips:
            self.stdout.write(
                self.style.SUCCESS("No IPs found meeting the abuse threshold")
            )
            return
        
        self.stdout.write(
            self.style.WARNING(
                f"Found {len(abusive_ips)} IPs with >= {threshold} abuse reports"
            )
        )
        
        # Show targets
        for ip_data in abusive_ips:
            self.stdout.write(
                f"   🎯 {ip_data['ip_address']}: {ip_data['report_count']} reports"
            )
        
        # Confirmation
        if not options['confirm']:
            confirm = input(
                self.style.WARNING(
                    f"Block these {len(abusive_ips)} IPs? Type 'yes' to continue: "
                )
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return
        
        # Block abusive IPs
        blocked_count = 0
        for ip_data in abusive_ips:
            try:
                ip_block_service.block_ip(
                    ip_address=ip_data['ip_address'],
                    reason='automatic',
                    duration_days=30,  # Longer duration for abusive IPs
                    description=f"Auto-blocked due to {ip_data['report_count']} abuse reports"
                )
                blocked_count += 1
                
                # Mark abuse reports as blocked
                AbuseReport.objects.filter(
                    ip_address=ip_data['ip_address']
                ).update(is_blocked=True)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error blocking {ip_data['ip_address']}: {e}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ Auto-blocked {blocked_count} abusive IPs")
        )
    
    def _list_blocks(self, ip_block_service):
        """List current active blocks."""
        blocks = IPBlockList.objects.filter(is_active=True).order_by('-created_at')
        
        if not blocks:
            self.stdout.write(self.style.SUCCESS("No active IP blocks found"))
            return
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.WARNING("ACTIVE IP BLOCKS:"))
        self.stdout.write("="*80)
        
        for block in blocks:
            self.stdout.write(f"\n🔒 Block ID: {block.id}")
            self.stdout.write(f"   📧 Type: {block.block_type}")
            
            if block.ip_address:
                self.stdout.write(f"   🎯 IP: {block.ip_address}")
            if block.ip_range_start and block.ip_range_end:
                self.stdout.write(f"   📏 Range: {block.ip_range_start} - {block.ip_range_end}")
            if block.subnet:
                self.stdout.write(f"   🌐 Subnet: {block.subnet}")
            
            self.stdout.write(f"   📝 Reason: {block.reason}")
            self.stdout.write(f"   📅 Created: {block.created_at}")
            self.stdout.write(f"   📄 Description: {block.description or 'None'}")
            self.stdout.write(f"   🔢 Block count: {block.block_count}")
            
            if block.expires_at:
                self.stdout.write(f"   ⏰ Expires: {block.expires_at}")
            else:
                self.stdout.write("   ⏰ Expires: Never (permanent)")
        
        self.stdout.write(f"\n📊 Total active blocks: {blocks.count()}")
        self.stdout.write("="*80)
    
    def _unblock_ip(self, ip_block_service, ip_address):
        """Unblock a specific IP address."""
        try:
            success = ip_block_service.unblock_ip(ip_address)
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Successfully unblocked IP: {ip_address}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  IP {ip_address} was not blocked")
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error unblocking IP {ip_address}: {e}")
            )
    
    def _cleanup_expired(self, ip_block_service):
        """Clean up expired blocks."""
        try:
            cleaned_count = ip_block_service.cleanup_expired_blocks()
            if cleaned_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Cleaned up {cleaned_count} expired blocks")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("No expired blocks found")
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error cleaning up expired blocks: {e}")
            )
