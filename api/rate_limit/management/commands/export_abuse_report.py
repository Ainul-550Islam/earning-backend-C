"""
export_abuse_report.py - Management command to export abuse reports.

This command allows administrators to export abuse reports in various formats
with filtering options and comprehensive data analysis.
"""
import csv
import json
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Count, Q, Avg, Max

from api.rate_limit.models import AbuseReport, IPBlockList, RateLimitLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Export abuse reports in various formats'
    
    def add_arguments(self, parser):
        # Output options
        parser.add_argument(
            '--format',
            type=str,
            default='csv',
            choices=['csv', 'json', 'excel'],
            help='Export format (default: csv)'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (default: auto-generated)'
        )
        
        # Date range options
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Export reports from last N days (default: 30)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD format)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD format)'
        )
        
        # Filtering options
        parser.add_argument(
            '--abuse-type',
            type=str,
            choices=['bot', 'rate_limit', 'scraping', 'spam', 'fraud', 'other'],
            help='Filter by abuse type'
        )
        parser.add_argument(
            '--severity',
            type=int,
            choices=[1, 2, 3, 4, 5],
            help='Filter by severity level (1-5)'
        )
        parser.add_argument(
            '--min-severity',
            type=int,
            help='Filter by minimum severity level'
        )
        parser.add_argument(
            '--blocked-only',
            action='store_true',
            help='Export only blocked reports'
        )
        parser.add_argument(
            '--unblocked-only',
            action='store_true',
            help='Export only unblocked reports'
        )
        parser.add_argument(
            '--ip-address',
            type=str,
            help='Filter by specific IP address'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Filter by specific user ID'
        )
        
        # Data options
        parser.add_argument(
            '--include-logs',
            action='store_true',
            help='Include related rate limit logs'
        )
        parser.add_argument(
            '--include-block-info',
            action='store_true',
            help='Include IP block information'
        )
        parser.add_argument(
            '--include-metadata',
            action='store_true',
            default=True,
            help='Include report metadata'
        )
        parser.add_argument(
            '--analysis-only',
            action='store_true',
            help='Export analysis summary only (no detailed reports)'
        )
        
        # Statistics options
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Include statistics summary'
        )
        parser.add_argument(
            '--top-abusers',
            type=int,
            default=10,
            help='Number of top abusers to include (default: 10)'
        )
        
        # Utility options
        parser.add_argument(
            '--list-types',
            action='store_true',
            help='List available abuse types and exit'
        )
        parser.add_argument(
            '--preview',
            action='store_true',
            help='Show preview of data without exporting'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be exported without doing it'
        )
    
    def handle(self, *args, **options):
        """Execute export command."""
        
        # List abuse types
        if options['list_types']:
            self._list_abuse_types()
            return
        
        # Get date range
        start_date, end_date = self._get_date_range(options)
        
        # Build query
        queryset = self._build_queryset(start_date, end_date, options)
        
        # Show preview
        if options['preview']:
            self._show_preview(queryset, options)
            return
        
        # Show statistics
        if options['stats']:
            self._show_statistics(queryset, start_date, end_date, options)
            return
        
        # Analysis only
        if options['analysis_only']:
            self._export_analysis(queryset, start_date, end_date, options)
            return
        
        # Export detailed reports
        self._export_reports(queryset, options)
    
    def _list_abuse_types(self):
        """List available abuse types with counts."""
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("ABUSE TYPES:"))
        self.stdout.write("="*50)
        
        abuse_types = AbuseReport.objects.values('abuse_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        for abuse_type in abuse_types:
            self.stdout.write(
                f"   🏷️  {abuse_type['abuse_type']}: {abuse_type['count']} reports"
            )
        
        self.stdout.write("="*50)
    
    def _get_date_range(self, options):
        """Get start and end dates from options."""
        if options['start_date'] and options['end_date']:
            try:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
                end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                raise CommandError("Invalid date format. Use YYYY-MM-DD")
        else:
            days = options['days']
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
        
        return start_date, end_date
    
    def _build_queryset(self, start_date, end_date, options):
        """Build queryset based on filters."""
        queryset = AbuseReport.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Apply filters
        if options['abuse_type']:
            queryset = queryset.filter(abuse_type=options['abuse_type'])
        
        if options['severity']:
            queryset = queryset.filter(severity=options['severity'])
        
        if options['min_severity']:
            queryset = queryset.filter(severity__gte=options['min_severity'])
        
        if options['blocked_only']:
            queryset = queryset.filter(is_blocked=True)
        
        if options['unblocked_only']:
            queryset = queryset.filter(is_blocked=False)
        
        if options['ip_address']:
            queryset = queryset.filter(ip_address=options['ip_address'])
        
        if options['user_id']:
            queryset = queryset.filter(user_id=options['user_id'])
        
        return queryset.select_related('user').order_by('-created_at')
    
    def _show_preview(self, queryset, options):
        """Show preview of data to be exported."""
        count = queryset.count()
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.WARNING("EXPORT PREVIEW:"))
        self.stdout.write("="*60)
        self.stdout.write(f"📊 Total reports to export: {count}")
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No reports found matching criteria"))
            return
        
        # Show sample records
        self.stdout.write("\n📄 Sample records (first 5):")
        self.stdout.write("-"*60)
        
        for report in queryset[:5]:
            self.stdout.write(f"\n🆔 ID: {report.id}")
            self.stdout.write(f"   🎯 IP: {report.ip_address}")
            self.stdout.write(f"   🏷️  Type: {report.abuse_type}")
            self.stdout.write(f"   ⚠️  Severity: {report.severity}")
            self.stdout.write(f"   📅 Created: {report.created_at}")
            self.stdout.write(f"   🔒 Blocked: {report.is_blocked}")
            if report.user:
                self.stdout.write(f"   👤 User: {report.user.username}")
        
        self.stdout.write("\n" + "="*60)
    
    def _show_statistics(self, queryset, start_date, end_date, options):
        """Show statistics summary."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("ABUSE REPORT STATISTICS:"))
        self.stdout.write("="*60)
        
        # Basic stats
        total_reports = queryset.count()
        blocked_reports = queryset.filter(is_blocked=True).count()
        
        self.stdout.write(f"📊 Total reports: {total_reports}")
        self.stdout.write(f"🔒 Blocked reports: {blocked_reports}")
        self.stdout.write(f"📈 Block rate: {(blocked_reports/total_reports*100):.1f}%" if total_reports > 0 else "📈 Block rate: 0%")
        
        # By abuse type
        self.stdout.write("\n📊 By abuse type:")
        by_type = queryset.values('abuse_type').annotate(count=Count('id')).order_by('-count')
        for item in by_type:
            self.stdout.write(f"   🏷️  {item['abuse_type']}: {item['count']}")
        
        # By severity
        self.stdout.write("\n⚠️  By severity:")
        by_severity = queryset.values('severity').annotate(count=Count('id')).order_by('severity')
        for item in by_severity:
            self.stdout.write(f"   ⚠️  Level {item['severity']}: {item['count']}")
        
        # Top abusers
        self.stdout.write(f"\n🏆 Top {options['top_abusers']} abusers:")
        top_abusers = queryset.values('ip_address').annotate(
            count=Count('id')
        ).order_by('-count')[:options['top_abusers']]
        
        for i, abuser in enumerate(top_abusers, 1):
            self.stdout.write(f"   {i}. 🎯 {abuser['ip_address']}: {abuser['count']} reports")
        
        # Time distribution
        self.stdout.write("\n📅 Daily distribution:")
        daily_counts = queryset.extra(
            {'date': "date(created_at)"}
        ).values('date').annotate(count=Count('id')).order_by('date')
        
        for item in daily_counts[:7]:  # Last 7 days
            self.stdout.write(f"   📅 {item['date']}: {item['count']} reports")
        
        self.stdout.write("="*60)
    
    def _export_analysis(self, queryset, start_date, end_date, options):
        """Export analysis summary only."""
        analysis_data = {
            'export_info': {
                'generated_at': timezone.now().isoformat(),
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_reports': queryset.count()
            },
            'statistics': self._generate_statistics(queryset),
            'trends': self._generate_trends(queryset),
            'recommendations': self._generate_recommendations(queryset)
        }
        
        # Generate output filename
        if not options['output']:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"abuse_analysis_{timestamp}.json"
        else:
            filename = options['output']
        
        # Write analysis
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, default=str)
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ Analysis exported to: {filename}")
        )
    
    def _export_reports(self, queryset, options):
        """Export detailed reports."""
        format_type = options['format']
        
        # Generate output filename
        if not options['output']:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"abuse_reports_{timestamp}.{format_type}"
        else:
            filename = options['output']
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN - Would export to: {filename}")
            )
            return
        
        # Prepare data
        data = self._prepare_export_data(queryset, options)
        
        # Export based on format
        if format_type == 'csv':
            self._export_csv(data, filename, options)
        elif format_type == 'json':
            self._export_json(data, filename, options)
        elif format_type == 'excel':
            self._export_excel(data, filename, options)
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ Exported {len(data)} reports to: {filename}")
        )
    
    def _prepare_export_data(self, queryset, options):
        """Prepare data for export."""
        data = []
        
        for report in queryset:
            row = {
                'id': report.id,
                'ip_address': report.ip_address,
                'abuse_type': report.abuse_type,
                'severity': report.severity,
                'endpoint': report.endpoint,
                'user_agent': report.user_agent,
                'is_blocked': report.is_blocked,
                'is_investigated': report.is_investigated,
                'created_at': report.created_at.isoformat(),
                'last_seen': report.last_seen.isoformat() if report.last_seen else None,
                'report_count': report.report_count,
                'blocked_count': report.blocked_count
            }
            
            # Add user info
            if report.user:
                row['user_id'] = report.user.id
                row['username'] = report.user.username
                row['email'] = report.user.email
            else:
                row['user_id'] = None
                row['username'] = None
                row['email'] = None
            
            # Add metadata
            if options['include_metadata'] and report.metadata:
                row['metadata'] = json.dumps(report.metadata)
            else:
                row['metadata'] = None
            
            # Add block info
            if options['include_block_info']:
                block_info = IPBlockList.objects.filter(
                    ip_address=report.ip_address,
                    is_active=True
                ).first()
                
                if block_info:
                    row['block_id'] = block_info.id
                    row['block_reason'] = block_info.reason
                    row['block_created_at'] = block_info.created_at.isoformat()
                    row['block_expires_at'] = block_info.expires_at.isoformat() if block_info.expires_at else None
                else:
                    row['block_id'] = None
                    row['block_reason'] = None
                    row['block_created_at'] = None
                    row['block_expires_at'] = None
            
            data.append(row)
        
        return data
    
    def _export_csv(self, data, filename, options):
        """Export data to CSV format."""
        if not data:
            return
        
        fieldnames = list(data[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    
    def _export_json(self, data, filename, options):
        """Export data to JSON format."""
        export_data = {
            'export_info': {
                'generated_at': timezone.now().isoformat(),
                'total_records': len(data),
                'format': 'json'
            },
            'reports': data
        }
        
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
    
    def _export_excel(self, data, filename, options):
        """Export data to Excel format."""
        try:
            import pandas as pd
        except ImportError:
            raise CommandError(
                "pandas is required for Excel export. Install with: pip install pandas openpyxl"
            )
        
        if not data:
            return
        
        df = pd.DataFrame(data)
        df.to_excel(filename, index=False, engine='openpyxl')
    
    def _generate_statistics(self, queryset):
        """Generate statistics for analysis."""
        return {
            'total_reports': queryset.count(),
            'blocked_reports': queryset.filter(is_blocked=True).count(),
            'by_type': list(queryset.values('abuse_type').annotate(count=Count('id')).order_by('-count')),
            'by_severity': list(queryset.values('severity').annotate(count=Count('id')).order_by('severity')),
            'average_severity': queryset.aggregate(avg_severity=Avg('severity'))['avg_severity'] or 0
        }
    
    def _generate_trends(self, queryset):
        """Generate trend analysis."""
        # Daily counts for last 30 days
        daily_counts = queryset.extra(
            {'date': "date(created_at)"}
        ).values('date').annotate(count=Count('id')).order_by('date')
        
        return {
            'daily_counts': list(daily_counts),
            'peak_day': daily_counts.order_by('-count').first() if daily_counts else None
        }
    
    def _generate_recommendations(self, queryset):
        """Generate recommendations based on data."""
        recommendations = []
        
        total_reports = queryset.count()
        blocked_rate = (queryset.filter(is_blocked=True).count() / total_reports * 100) if total_reports > 0 else 0
        
        if blocked_rate > 50:
            recommendations.append({
                'type': 'high_block_rate',
                'message': f"High block rate ({blocked_rate:.1f}%). Consider reviewing blocking criteria.",
                'priority': 'medium'
            })
        
        # Check for frequent abusers
        top_abuser = queryset.values('ip_address').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        if top_abuser and top_abuser['count'] > 10:
            recommendations.append({
                'type': 'frequent_abuser',
                'message': f"IP {top_abuser['ip_address']} has {top_abuser['count']} reports. Consider permanent blocking.",
                'priority': 'high'
            })
        
        return recommendations
