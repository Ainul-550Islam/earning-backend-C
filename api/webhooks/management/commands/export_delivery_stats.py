"""Export Delivery Stats Management Command

This management command exports webhook delivery statistics to CSV format
for analysis and reporting purposes.
"""

import csv
import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from django.conf import settings

from ...models import WebhookEndpoint, WebhookDeliveryLog
from ...constants import DeliveryStatus


class Command(BaseCommand):
    help = 'Export webhook delivery statistics to CSV format'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to export (default: 30)'
        )
        parser.add_argument(
            '--endpoint-id',
            type=str,
            help='Specific endpoint ID to export (optional)'
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=[s.value for s in DeliveryStatus],
            help='Filter by delivery status (optional)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='exports',
            help='Output directory for CSV files (default: exports)'
        )
        parser.add_argument(
            '--filename',
            type=str,
            help='Custom filename (optional)'
        )
        parser.add_argument(
            '--group-by',
            type=str,
            choices=['day', 'hour', 'endpoint', 'event_type'],
            default='day',
            help='Group statistics by (default: day)'
        )
        parser.add_argument(
            '--include-details',
            action='store_true',
            help='Include detailed delivery logs'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        endpoint_id = options.get('endpoint_id')
        status_filter = options.get('status')
        output_dir = options['output_dir']
        custom_filename = options.get('filename')
        group_by = options['group_by']
        include_details = options['include_details']
        verbose = options['verbose']
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        if verbose:
            self.stdout.write(f"Exporting delivery stats from {start_date} to {end_date}")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if custom_filename:
            filename = f"{custom_filename}.csv"
        else:
            filename = f"webhook_delivery_stats_{timestamp}.csv"
        
        filepath = os.path.join(output_dir, filename)
        
        # Build base query
        query = WebhookDeliveryLog.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Apply filters
        if endpoint_id:
            query = query.filter(endpoint_id=endpoint_id)
            if verbose:
                self.stdout.write(f"Filtering by endpoint: {endpoint_id}")
        
        if status_filter:
            query = query.filter(status=status_filter)
            if verbose:
                self.stdout.write(f"Filtering by status: {status_filter}")
        
        # Export data based on group_by option
        if group_by == 'day':
            self._export_by_day(query, filepath, verbose)
        elif group_by == 'hour':
            self._export_by_hour(query, filepath, verbose)
        elif group_by == 'endpoint':
            self._export_by_endpoint(query, filepath, verbose)
        elif group_by == 'event_type':
            self._export_by_event_type(query, filepath, verbose)
        
        # Export detailed logs if requested
        if include_details:
            details_filename = f"webhook_delivery_details_{timestamp}.csv"
            details_filepath = os.path.join(output_dir, details_filename)
            self._export_detailed_logs(query, details_filepath, verbose)
        
        # Export summary statistics
        summary_filename = f"webhook_delivery_summary_{timestamp}.csv"
        summary_filepath = os.path.join(output_dir, summary_filename)
        self._export_summary_stats(query, summary_filepath, verbose)
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully exported delivery stats to {filepath}")
        )
        
        if include_details:
            self.stdout.write(
                self.style.SUCCESS(f"Detailed logs exported to {details_filepath}")
            )
        
        self.stdout.write(
            self.style.SUCCESS(f"Summary stats exported to {summary_filepath}")
        )
    
    def _export_by_day(self, query, filepath, verbose):
        """Export statistics grouped by day."""
        if verbose:
            self.stdout.write("Exporting statistics grouped by day...")
        
        # Get daily statistics
        daily_stats = query.extra(
            {'date': "date(created_at)"}
        ).values('date').annotate(
            total_count=Count('id'),
            success_count=Count('id', filter=Q(status=DeliveryStatus.SUCCESS)),
            failed_count=Count('id', filter=Q(status=DeliveryStatus.FAILED)),
            avg_response_time=Avg('duration_ms'),
            total_response_time=Sum('duration_ms')
        ).order_by('date')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Date',
                'Total Requests',
                'Success Count',
                'Failed Count',
                'Success Rate (%)',
                'Avg Response Time (ms)',
                'Total Response Time (ms)'
            ])
            
            # Write data
            for stat in daily_stats:
                success_rate = (stat['success_count'] / stat['total_count'] * 100) if stat['total_count'] > 0 else 0
                
                writer.writerow([
                    stat['date'].strftime('%Y-%m-%d'),
                    stat['total_count'],
                    stat['success_count'],
                    stat['failed_count'],
                    round(success_rate, 2),
                    round(stat['avg_response_time'] or 0, 2),
                    stat['total_response_time'] or 0
                ])
    
    def _export_by_hour(self, query, filepath, verbose):
        """Export statistics grouped by hour."""
        if verbose:
            self.stdout.write("Exporting statistics grouped by hour...")
        
        # Get hourly statistics
        hourly_stats = query.extra(
            {'hour': "date_trunc('hour', created_at)"}
        ).values('hour').annotate(
            total_count=Count('id'),
            success_count=Count('id', filter=Q(status=DeliveryStatus.SUCCESS)),
            failed_count=Count('id', filter=Q(status=DeliveryStatus.FAILED)),
            avg_response_time=Avg('duration_ms')
        ).order_by('hour')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Hour',
                'Total Requests',
                'Success Count',
                'Failed Count',
                'Success Rate (%)',
                'Avg Response Time (ms)'
            ])
            
            # Write data
            for stat in hourly_stats:
                success_rate = (stat['success_count'] / stat['total_count'] * 100) if stat['total_count'] > 0 else 0
                
                writer.writerow([
                    stat['hour'].strftime('%Y-%m-%d %H:00'),
                    stat['total_count'],
                    stat['success_count'],
                    stat['failed_count'],
                    round(success_rate, 2),
                    round(stat['avg_response_time'] or 0, 2)
                ])
    
    def _export_by_endpoint(self, query, filepath, verbose):
        """Export statistics grouped by endpoint."""
        if verbose:
            self.stdout.write("Exporting statistics grouped by endpoint...")
        
        # Get endpoint statistics
        endpoint_stats = query.values('endpoint__url', 'endpoint__label').annotate(
            total_count=Count('id'),
            success_count=Count('id', filter=Q(status=DeliveryStatus.SUCCESS)),
            failed_count=Count('id', filter=Q(status=DeliveryStatus.FAILED)),
            avg_response_time=Avg('duration_ms'),
            first_request=Min('created_at'),
            last_request=Max('created_at')
        ).order_by('-total_count')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Endpoint URL',
                'Endpoint Label',
                'Total Requests',
                'Success Count',
                'Failed Count',
                'Success Rate (%)',
                'Avg Response Time (ms)',
                'First Request',
                'Last Request'
            ])
            
            # Write data
            for stat in endpoint_stats:
                success_rate = (stat['success_count'] / stat['total_count'] * 100) if stat['total_count'] > 0 else 0
                
                writer.writerow([
                    stat['endpoint__url'],
                    stat['endpoint__label'] or '',
                    stat['total_count'],
                    stat['success_count'],
                    stat['failed_count'],
                    round(success_rate, 2),
                    round(stat['avg_response_time'] or 0, 2),
                    stat['first_request'].strftime('%Y-%m-%d %H:%M:%S') if stat['first_request'] else '',
                    stat['last_request'].strftime('%Y-%m-%d %H:%M:%S') if stat['last_request'] else ''
                ])
    
    def _export_by_event_type(self, query, filepath, verbose):
        """Export statistics grouped by event type."""
        if verbose:
            self.stdout.write("Exporting statistics grouped by event type...")
        
        # Get event type statistics
        event_type_stats = query.values('event_type').annotate(
            total_count=Count('id'),
            success_count=Count('id', filter=Q(status=DeliveryStatus.SUCCESS)),
            failed_count=Count('id', filter=Q(status=DeliveryStatus.FAILED)),
            avg_response_time=Avg('duration_ms'),
            unique_endpoints=Count('endpoint', distinct=True)
        ).order_by('-total_count')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Event Type',
                'Total Requests',
                'Success Count',
                'Failed Count',
                'Success Rate (%)',
                'Avg Response Time (ms)',
                'Unique Endpoints'
            ])
            
            # Write data
            for stat in event_type_stats:
                success_rate = (stat['success_count'] / stat['total_count'] * 100) if stat['total_count'] > 0 else 0
                
                writer.writerow([
                    stat['event_type'],
                    stat['total_count'],
                    stat['success_count'],
                    stat['failed_count'],
                    round(success_rate, 2),
                    round(stat['avg_response_time'] or 0, 2),
                    stat['unique_endpoints']
                ])
    
    def _export_detailed_logs(self, query, filepath, verbose):
        """Export detailed delivery logs."""
        if verbose:
            self.stdout.write("Exporting detailed delivery logs...")
        
        # Get detailed logs with related data
        detailed_logs = query.select_related(
            'endpoint', 'endpoint__owner'
        ).order_by('-created_at')
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'ID',
                'Created At',
                'Endpoint URL',
                'Endpoint Label',
                'Owner',
                'Event Type',
                'Status',
                'HTTP Status Code',
                'Response Time (ms)',
                'Attempt Number',
                'Max Attempts',
                'Next Retry At',
                'Dispatched At',
                'Completed At',
                'Error Message'
            ])
            
            # Write data
            for log in detailed_logs:
                writer.writerow([
                    str(log.id),
                    log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    log.endpoint.url,
                    log.endpoint.label or '',
                    log.endpoint.owner.username if log.endpoint.owner else '',
                    log.event_type,
                    log.status,
                    log.http_status_code or '',
                    log.duration_ms or '',
                    log.attempt_number,
                    log.max_attempts,
                    log.next_retry_at.strftime('%Y-%m-%d %H:%M:%S') if log.next_retry_at else '',
                    log.dispatched_at.strftime('%Y-%m-%d %H:%M:%S') if log.dispatched_at else '',
                    log.completed_at.strftime('%Y-%m-%d %H:%M:%S') if log.completed_at else '',
                    log.error_message or ''
                ])
    
    def _export_summary_stats(self, query, filepath, verbose):
        """Export summary statistics."""
        if verbose:
            self.stdout.write("Exporting summary statistics...")
        
        # Get overall statistics
        total_count = query.count()
        success_count = query.filter(status=DeliveryStatus.SUCCESS).count()
        failed_count = query.filter(status=DeliveryStatus.FAILED).count()
        pending_count = query.filter(status=DeliveryStatus.PENDING).count()
        retrying_count = query.filter(status=DeliveryStatus.RETRYING).count()
        exhausted_count = query.filter(status=DeliveryStatus.EXHAUSTED).count()
        
        # Get endpoint statistics
        endpoint_count = query.values('endpoint').distinct().count()
        
        # Get event type statistics
        event_type_count = query.values('event_type').distinct().count()
        
        # Get response time statistics
        response_times = query.aggregate(
            avg_response_time=Avg('duration_ms'),
            min_response_time=Min('duration_ms'),
            max_response_time=Max('duration_ms')
        )
        
        # Get date range
        date_range = query.aggregate(
            min_date=Min('created_at'),
            max_date=Max('created_at')
        )
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['Metric', 'Value'])
            
            # Write summary statistics
            writer.writerow(['Total Requests', total_count])
            writer.writerow(['Success Count', success_count])
            writer.writerow(['Failed Count', failed_count])
            writer.writerow(['Pending Count', pending_count])
            writer.writerow(['Retrying Count', retrying_count])
            writer.writerow(['Exhausted Count', exhausted_count])
            writer.writerow(['Success Rate (%)', round((success_count / total_count * 100) if total_count > 0 else 0, 2)])
            writer.writerow(['Unique Endpoints', endpoint_count])
            writer.writerow(['Unique Event Types', event_type_count])
            writer.writerow(['Avg Response Time (ms)', round(response_times['avg_response_time'] or 0, 2)])
            writer.writerow(['Min Response Time (ms)', response_times['min_response_time'] or ''])
            writer.writerow(['Max Response Time (ms)', response_times['max_response_time'] or ''])
            writer.writerow(['Date Range Start', date_range['min_date'].strftime('%Y-%m-%d %H:%M:%S') if date_range['min_date'] else ''])
            writer.writerow(['Date Range End', date_range['max_date'].strftime('%Y-%m-%d %H:%M:%S') if date_range['max_date'] else ''])
