"""
Management command to sync offers from providers
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from api.offerwall.models import OfferProvider
from api.offerwall.services.OfferProcessor import OfferProcessorFactory


class Command(BaseCommand):
    help = 'Sync offers from external providers'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            type=str,
            help='Specific provider to sync (name or type)',
        )
        
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all active providers',
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if recently synced',
        )
    
    def handle(self, *args, **options):
        """Execute the command"""
        provider_name = options.get('provider')
        sync_all = options.get('all')
        force = options.get('force')
        
        if not provider_name and not sync_all:
            raise CommandError('Please specify --provider <name> or --all')
        
        # Get providers to sync
        if provider_name:
            try:
                providers = OfferProvider.objects.filter(
                    models.Q(name__iexact=provider_name) |
                    models.Q(provider_type=provider_name),
                    status='active'
                )
                
                if not providers.exists():
                    raise CommandError(f'Provider "{provider_name}" not found or not active')
            
            except Exception as e:
                raise CommandError(f'Error finding provider: {e}')
        
        else:
            providers = OfferProvider.objects.filter(status='active', auto_sync=True)
        
        if not providers.exists():
            self.stdout.write(self.style.WARNING('No providers to sync'))
            return
        
        # Sync each provider
        total_synced = 0
        total_created = 0
        total_updated = 0
        total_errors = 0
        
        for provider in providers:
            self.stdout.write(f'\nSyncing {provider.name}...')
            
            # Check if recently synced
            if not force and provider.last_sync:
                time_since_sync = (timezone.now() - provider.last_sync).total_seconds() / 60
                if time_since_sync < provider.sync_interval_minutes:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Skipped (last sync: {int(time_since_sync)} minutes ago). '
                            f'Use --force to override.'
                        )
                    )
                    continue
            
            try:
                # Create processor and sync
                processor = OfferProcessorFactory.create(provider)
                results = processor.sync_offers()
                
                if results['success']:
                    total_synced += results['synced']
                    total_created += results['created']
                    total_updated += results['updated']
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Synced {results["synced"]} offers '
                            f'({results["created"]} new, {results["updated"]} updated)'
                        )
                    )
                    
                    if results['errors']:
                        total_errors += len(results['errors'])
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⚠ {len(results["errors"])} errors occurred'
                            )
                        )
                
                else:
                    total_errors += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ✗ Sync failed: {results["errors"]}'
                        )
                    )
            
            except Exception as e:
                total_errors += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error: {str(e)}')
                )
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\nSync completed!'))
        self.stdout.write(f'Providers processed: {providers.count()}')
        self.stdout.write(f'Total offers synced: {total_synced}')
        self.stdout.write(f'  - New: {total_created}')
        self.stdout.write(f'  - Updated: {total_updated}')
        
        if total_errors > 0:
            self.stdout.write(
                self.style.WARNING(f'Errors: {total_errors}')
            )