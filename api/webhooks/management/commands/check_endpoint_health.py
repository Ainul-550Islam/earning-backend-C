"""Check Endpoint Health Management Command

This Django management command performs manual health checks
on all webhook endpoints to verify their status.
"""

import logging
from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string

from ...services.analytics import HealthMonitorService
from ...models import WebhookEndpoint

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to check webhook endpoint health.
    Performs manual health checks on all active endpoints.
    """
    
    help = 'Perform manual health checks on all webhook endpoints'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--endpoint-id',
            type=int,
            help='Check specific endpoint ID (optional)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Health check timeout in seconds',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed health check results',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        endpoint_id = options.get('endpoint_id')
        timeout = options['timeout']
        verbose = options['verbose']
        
        self.stdout.write("Starting webhook endpoint health checks...")
        
        try:
            health_service = HealthMonitorService()
            
            if endpoint_id:
                # Check specific endpoint
                try:
                    endpoint = WebhookEndpoint.objects.get(id=endpoint_id)
                    result = health_service.check_endpoint_health(endpoint)
                    
                    self._display_result(result, verbose)
                    
                except WebhookEndpoint.DoesNotExist:
                    self.stderr.write(
                        self.style.ERROR(f"Webhook endpoint with ID {endpoint_id} not found")
                    )
            else:
                # Check all active endpoints
                endpoints = WebhookEndpoint.objects.filter(status='active')
                
                if not endpoints.exists():
                    self.stdout.write("No active webhook endpoints found")
                    return
                
                results = health_service.check_all_endpoints()
                
                # Display results
                if verbose:
                    self.stdout.write("\nDetailed Health Check Results:")
                    self.stdout.write("=" * 50)
                    
                    for result in results:
                        self._display_result(result, True)
                        
                    # Summary
                    healthy_count = sum(1 for r in results if r['is_healthy'])
                    total_count = len(results)
                    
                    self.stdout.write("\nSummary:")
                    self.stdout.write(f"  Total endpoints checked: {total_count}")
                    self.stdout.write(f"  Healthy endpoints: {healthy_count}")
                    self.stdout.write(f"  Unhealthy endpoints: {total_count - healthy_count}")
                    self.stdout.write("=" * 50)
                else:
                    # Simple output
                    for result in results:
                        status = "✓ Healthy" if result['is_healthy'] else "✗ Unhealthy"
                        self.stdout.write(f"{status}: {result['url']}")
                        
                        if not result['is_healthy']:
                            self.stdout.write(f"  Error: {result.get('error', 'Unknown error')}")
            
            self.stdout.write("Health checks completed!")
            
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Health check failed: {e}")
            )
            logger.error(f"Health check command failed: {e}")
    
    def _display_result(self, result, verbose=False):
        """Display individual health check result."""
        status = "✓ Healthy" if result['is_healthy'] else "✗ Unhealthy"
        
        self.stdout.write(f"{status}: {result['url']}")
        
        if verbose:
            self.stdout.write(f"  Response time: {result.get('response_time_ms', 'N/A')}ms")
            self.stdout.write(f"  Status code: {result.get('status_code', 'N/A')}")
            
            if not result['is_healthy']:
                self.stdout.write(f"  Error: {result.get('error', 'Unknown error')}")
        
        self.stdout.write(f"  Checked at: {result['checked_at']}")
