# =============================================================================
# auto_mod/management/commands/bulk_scan_submissions.py
# =============================================================================

"""
Django management command to scan all pending submissions.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from ...models import SuspiciousSubmission, ProofScanner
from ...choices import ScanType, ScanStatus, SubmissionType, ModerationStatus
from ...services import BotService
from ...exceptions import ScanFailedError
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scan all pending submissions with appropriate scanners'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--submission-type',
            type=str,
            choices=[choice[0] for choice in SubmissionType.choices],
            help='Filter by submission type'
        )
        parser.add_argument(
            '--scan-type',
            type=str,
            choices=[choice[0] for choice in ScanType.choices],
            help='Specific scan type to run'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of submissions to process in each batch'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be scanned without actually scanning'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-scan of already scanned submissions'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=300,
            help='Timeout in seconds for each scan (default: 300)'
        )
        parser.add_argument(
            '--priority',
            type=str,
            choices=['low', 'normal', 'high', 'critical'],
            default='normal',
            help='Priority for queue items'
        )
    
    def handle(self, *args, **options):
        """Execute the bulk scan command."""
        self.stdout.write(
            self.style.SUCCESS('Starting bulk scan of pending submissions...')
        )
        
        # Get filter parameters
        submission_type = options.get('submission_type')
        scan_type = options.get('scan_type')
        batch_size = options.get('batch_size', 100)
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)
        timeout = options.get('timeout', 300)
        priority = options.get('priority', 'normal')
        
        try:
            # Get pending submissions
            queryset = self._get_pending_submissions(submission_type, force)
            total_count = queryset.count()
            
            if total_count == 0:
                self.stdout.write(
                    self.style.WARNING('No pending submissions found to scan.')
                )
                return
            
            self.stdout.write(
                f'Found {total_count} submissions to scan'
            )
            
            if dry_run:
                self._show_dry_run_preview(queryset, scan_type)
                return
            
            # Process submissions in batches
            results = self._process_submissions(
                queryset, scan_type, batch_size, timeout, priority
            )
            
            # Display results
            self._display_results(results)
            
        except Exception as exc:
            logger.error(f"Bulk scan failed: {exc}")
            raise CommandError(f"Bulk scan failed: {exc}")
    
    def _get_pending_submissions(self, submission_type, force):
        """Get queryset of pending submissions."""
        queryset = SuspiciousSubmission.objects.filter(
            status=ModerationStatus.PENDING
        )
        
        if submission_type:
            queryset = queryset.filter(submission_type=submission_type)
        
        if not force:
            # Exclude submissions that already have recent scans
            recent_scans = ProofScanner.objects.filter(
                status=ScanStatus.SUCCESS,
                completed_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).values_list('submission_id', flat=True)
            
            queryset = queryset.exclude(id__in=recent_scans)
        
        return queryset.order_by('created_at')
    
    def _show_dry_run_preview(self, queryset, scan_type):
        """Show what would be scanned in dry run mode."""
        self.stdout.write(self.style.WARNING('DRY RUN - No actual scanning will occur'))
        
        # Group by submission type
        type_counts = {}
        for submission in queryset:
            type_counts[submission.submission_type] = type_counts.get(submission.submission_type, 0) + 1
        
        self.stdout.write('\nSubmissions to scan by type:')
        for sub_type, count in type_counts.items():
            self.stdout.write(f'  {sub_type}: {count}')
        
        if scan_type:
            self.stdout.write(f'\nScan type: {scan_type}')
        else:
            # Show recommended scan types
            self.stdout.write('\nRecommended scan types:')
            for sub_type, count in type_counts.items():
                recommended = self._get_recommended_scan_type(sub_type)
                self.stdout.write(f'  {sub_type}: {recommended}')
        
        self.stdout.write(f'\nTotal submissions: {queryset.count()}')
    
    def _get_recommended_scan_type(self, submission_type):
        """Get recommended scan type for submission type."""
        scan_mapping = {
            SubmissionType.IMAGE: ScanType.IMAGE_ANALYSIS,
            SubmissionType.TEXT: ScanType.TEXT_ANALYSIS,
            SubmissionType.DOCUMENT: ScanType.OCR,
            SubmissionType.VIDEO: ScanType.IMAGE_ANALYSIS,  # Frame analysis
            SubmissionType.AUDIO: ScanType.TEXT_ANALYSIS,   # Transcription
        }
        return scan_mapping.get(submission_type, ScanType.IMAGE_ANALYSIS)
    
    def _process_submissions(self, queryset, scan_type, batch_size, timeout, priority):
        """Process submissions in batches."""
        bot_service = BotService()
        results = {
            'total': queryset.count(),
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        offset = 0
        while offset < queryset.count():
            batch = queryset[offset:offset + batch_size]
            
            self.stdout.write(
                f'Processing batch {offset//batch_size + 1}: {len(batch)} submissions'
            )
            
            for submission in batch:
                try:
                    result = self._scan_submission(
                        submission, scan_type, bot_service, timeout, priority
                    )
                    
                    results['processed'] += 1
                    
                    if result['success']:
                        results['successful'] += 1
                    else:
                        results['failed'] += 1
                        if result['error']:
                            results['errors'].append({
                                'submission_id': str(submission.pk),
                                'content_id': submission.content_id,
                                'error': result['error']
                            })
                
                except Exception as exc:
                    results['failed'] += 1
                    results['errors'].append({
                        'submission_id': str(submission.pk),
                        'content_id': submission.content_id,
                        'error': str(exc)
                    })
                    logger.error(f"Failed to scan submission {submission.pk}: {exc}")
            
            offset += batch_size
            
            # Progress update
            progress = (results['processed'] / results['total']) * 100
            self.stdout.write(
                f'Progress: {results["processed"]}/{results["total"]} '
                f'({progress:.1f}%)'
            )
        
        return results
    
    def _scan_submission(self, submission, scan_type, bot_service, timeout, priority):
        """Scan a single submission."""
        try:
            # Determine scan type if not specified
            if not scan_type:
                scan_type = self._get_recommended_scan_type(submission.submission_type)
            
            # Check if submission already has recent successful scan
            if not self._should_scan(submission, scan_type):
                return {
                    'success': False,
                    'skipped': True,
                    'reason': 'Recent successful scan exists'
                }
            
            # Create scanner record
            scanner = ProofScanner.objects.create(
                submission=submission,
                scan_type=scan_type,
                status=ScanStatus.PENDING,
                initiated_by=None  # System initiated
            )
            
            # Execute scan
            if scan_type == ScanType.OCR:
                result = bot_service.run_ocr_scan(submission)
            elif scan_type == ScanType.IMAGE_ANALYSIS:
                result = bot_service.run_image_scan(submission)
            elif scan_type == ScanType.TEXT_ANALYSIS:
                result = bot_service.run_text_analysis(submission)
            else:
                raise ValueError(f"Unsupported scan type: {scan_type}")
            
            # Update scanner with results
            if result.get('status') == 'success':
                scanner.mark_completed(ScanStatus.SUCCESS, result)
                
                # Update submission with scan results
                self._update_submission_with_scan_results(submission, scan_type, result)
                
                return {
                    'success': True,
                    'scanner_id': str(scanner.pk),
                    'scan_type': scan_type,
                    'result': result
                }
            else:
                scanner.mark_completed(ScanStatus.FAILED, result)
                return {
                    'success': False,
                    'scanner_id': str(scanner.pk),
                    'scan_type': scan_type,
                    'error': result.get('error', 'Unknown error')
                }
        
        except ScanFailedError as exc:
            if 'scanner' in locals():
                scanner.mark_completed(ScanStatus.FAILED, {'error': str(exc)})
            return {
                'success': False,
                'error': str(exc)
            }
        except Exception as exc:
            if 'scanner' in locals():
                scanner.mark_completed(ScanStatus.FAILED, {'error': str(exc)})
            return {
                'success': False,
                'error': str(exc)
            }
    
    def _should_scan(self, submission, scan_type):
        """Check if submission should be scanned."""
        # Check for recent successful scan of same type
        recent_scan = ProofScanner.objects.filter(
            submission=submission,
            scan_type=scan_type,
            status=ScanStatus.SUCCESS,
            completed_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).first()
        
        return recent_scan is None
    
    def _update_submission_with_scan_results(self, submission, scan_type, result):
        """Update submission with scan results."""
        with transaction.atomic():
            if scan_type == ScanType.OCR and 'extracted_text' in result:
                submission.metadata['ocr_text'] = result['extracted_text']
                submission.metadata['ocr_confidence'] = result.get('confidence', 0)
            
            elif scan_type == ScanType.IMAGE_ANALYSIS and 'analysis' in result:
                analysis = result['analysis']
                submission.metadata['image_analysis'] = analysis
                
                # Update risk score based on analysis
                if analysis.get('suspicious_content'):
                    submission.risk_score = min(10.0, submission.risk_score + 2.0)
                elif analysis.get('confidence', 0) > 0.9:
                    submission.risk_score = max(0.0, submission.risk_score - 1.0)
            
            elif scan_type == ScanType.TEXT_ANALYSIS and 'analysis' in result:
                analysis = result['analysis']
                submission.metadata['text_analysis'] = analysis
                
                # Update risk score based on analysis
                toxicity = analysis.get('toxicity_score', 0)
                if toxicity > 0.7:
                    submission.risk_score = min(10.0, submission.risk_score + toxicity * 2)
                elif toxicity < 0.1:
                    submission.risk_score = max(0.0, submission.risk_score - 0.5)
            
            submission.save(update_fields=['metadata', 'risk_score'])
    
    def _display_results(self, results):
        """Display scan results summary."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('BULK SCAN RESULTS'))
        self.stdout.write('='*50)
        
        self.stdout.write(f"Total submissions: {results['total']}")
        self.stdout.write(f"Processed: {results['processed']}")
        self.stdout.write(
            self.style.SUCCESS(f"Successful: {results['successful']}")
        )
        
        if results['failed'] > 0:
            self.stdout.write(
                self.style.ERROR(f"Failed: {results['failed']}")
            )
        
        if results['skipped'] > 0:
            self.stdout.write(
                self.style.WARNING(f"Skipped: {results['skipped']}")
            )
        
        # Success rate
        if results['processed'] > 0:
            success_rate = (results['successful'] / results['processed']) * 100
            self.stdout.write(f"Success rate: {success_rate:.1f}%")
        
        # Show errors if any
        if results['errors']:
            self.stdout.write('\n' + self.style.ERROR('ERRORS:'))
            for error in results['errors'][:10]:  # Show first 10 errors
                self.stdout.write(
                    f"  {error['content_id']}: {error['error']}"
                )
            
            if len(results['errors']) > 10:
                self.stdout.write(f"  ... and {len(results['errors']) - 10} more errors")
        
        self.stdout.write('='*50)
        
        # Log summary
        logger.info(
            f"Bulk scan completed: {results['successful']}/{results['processed']} "
            f"successful, {results['failed']} failed"
        )
