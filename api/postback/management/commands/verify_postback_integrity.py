from django.core.management.base import BaseCommand
from django.utils import timezone

from api.postback.models import PostbackLog, PostbackInsight, PostbackTemplate, PostbackIPWhitelist, PostbackRateLimit
from api.postback.services import TemplateService


class Command(BaseCommand):
    help = 'Verify integrity hashes for postback models and detect tampering'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            choices=['all', 'postbacklog', 'insight', 'template', 'ipwhitelist', 'ratelimit'],
            default='all',
            help='Which model to verify (default: all)'
        )
        parser.add_argument(
            '--network',
            type=str,
            help='Network key to filter by (optional)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of recent days to check (default: 7)'
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Regenerate hashes for invalid records'
        )

    def handle(self, *args, **options):
        model_type = options['model']
        network_key = options['network']
        days = options['days']
        fix_invalid = options['fix']

        self.stdout.write(f"Verifying integrity for model: {model_type}")

        if model_type in ['all', 'postbacklog']:
            self._verify_postback_logs(network_key, days, fix_invalid)

        if model_type in ['all', 'insight']:
            self._verify_insights(network_key, days, fix_invalid)

        if model_type in ['all', 'template']:
            self._verify_templates(network_key, fix_invalid)

        if model_type in ['all', 'ipwhitelist']:
            self._verify_ip_whitelists(network_key, fix_invalid)

        if model_type in ['all', 'ratelimit']:
            self._verify_rate_limits(network_key, fix_invalid)

        self.stdout.write(self.style.SUCCESS("Integrity verification completed"))

    def _verify_postback_logs(self, network_key, days, fix_invalid):
        """Verify PostbackLog integrity hashes."""
        self.stdout.write("\n=== Verifying PostbackLog ===")
        
        queryset = PostbackLog.objects.all()
        if network_key:
            queryset = queryset.filter(network__network_key=network_key)
        if days:
            cutoff = timezone.now() - timezone.timedelta(days=days)
            queryset = queryset.filter(created_at__gte=cutoff)

        total = queryset.count()
        valid = 0
        invalid = 0

        self.stdout.write(f"Checking {total} PostbackLog records...")

        for i, log in enumerate(queryset):
            if log.verify_integrity():
                valid += 1
            else:
                invalid += 1
                if fix_invalid:
                    log.integrity_hash = log.generate_integrity_hash()
                    log.save(update_fields=['integrity_hash'])
                    self.stdout.write(f"  Fixed hash for log {log.pk}")

            if (i + 1) % 1000 == 0:
                self.stdout.write(f"  Processed {i + 1}/{total} records...")

        self.stdout.write(f"PostbackLog: {valid} valid, {invalid} invalid")
        if invalid > 0 and not fix_invalid:
            self.stdout.write(self.style.WARNING(f"  Use --fix to regenerate {invalid} invalid hashes"))

    def _verify_insights(self, network_key, days, fix_invalid):
        """Verify PostbackInsight integrity hashes."""
        self.stdout.write("\n=== Verifying PostbackInsight ===")
        
        queryset = PostbackInsight.objects.all()
        if network_key:
            queryset = queryset.filter(network__network_key=network_key)
        if days:
            cutoff = timezone.now() - timezone.timedelta(days=days)
            queryset = queryset.filter(created_at__gte=cutoff)

        total = queryset.count()
        valid = 0
        invalid = 0

        self.stdout.write(f"Checking {total} PostbackInsight records...")

        for insight in queryset:
            if insight.verify_integrity():
                valid += 1
            else:
                invalid += 1
                if fix_invalid:
                    insight.integrity_hash = insight.generate_integrity_hash()
                    insight.save(update_fields=['integrity_hash'])
                    self.stdout.write(f"  Fixed hash for insight {insight.network.network_key} - {insight.date}")

        self.stdout.write(f"PostbackInsight: {valid} valid, {invalid} invalid")
        if invalid > 0 and not fix_invalid:
            self.stdout.write(self.style.WARNING(f"  Use --fix to regenerate {invalid} invalid hashes"))

    def _verify_templates(self, network_key, fix_invalid):
        """Verify PostbackTemplate integrity hashes."""
        self.stdout.write("\n=== Verifying PostbackTemplate ===")
        
        if network_key:
            networks = [network_key]
        else:
            networks = PostbackTemplate.objects.values_list('network__network_key', flat=True).distinct()

        total_valid = 0
        total_invalid = 0

        for net_key in networks:
            try:
                from api.postback.models import NetworkPostbackConfig
                network = NetworkPostbackConfig.objects.get(network_key=net_key)
                results = TemplateService.batch_verify_integrity(network)
                
                total_valid += results['valid']
                total_invalid += results['invalid']
                
                self.stdout.write(f"  {net_key}: {results['valid']} valid, {results['invalid']} invalid")
                
                if fix_invalid and results['invalid'] > 0:
                    for template_info in results['invalid_templates']:
                        template = PostbackTemplate.objects.get(id=template_info['id'])
                        template.integrity_hash = template.generate_integrity_hash()
                        template.save(update_fields=['integrity_hash'])
                        self.stdout.write(f"    Fixed hash for template {template_info['name']}")

            except NetworkPostbackConfig.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"  Network {net_key} not found"))
                continue

        self.stdout.write(f"PostbackTemplate: {total_valid} valid, {total_invalid} invalid")
        if total_invalid > 0 and not fix_invalid:
            self.stdout.write(self.style.WARNING(f"  Use --fix to regenerate {total_invalid} invalid hashes"))

    def _verify_ip_whitelists(self, network_key, fix_invalid):
        """Verify PostbackIPWhitelist integrity hashes."""
        self.stdout.write("\n=== Verifying PostbackIPWhitelist ===")
        
        queryset = PostbackIPWhitelist.objects.all()
        if network_key:
            queryset = queryset.filter(network__network_key=network_key)

        total = queryset.count()
        valid = 0
        invalid = 0

        self.stdout.write(f"Checking {total} PostbackIPWhitelist records...")

        for whitelist in queryset:
            if whitelist.verify_integrity():
                valid += 1
            else:
                invalid += 1
                if fix_invalid:
                    whitelist.integrity_hash = whitelist.generate_integrity_hash()
                    whitelist.save(update_fields=['integrity_hash'])
                    self.stdout.write(f"  Fixed hash for whitelist {whitelist.ip_address}")

        self.stdout.write(f"PostbackIPWhitelist: {valid} valid, {invalid} invalid")
        if invalid > 0 and not fix_invalid:
            self.stdout.write(self.style.WARNING(f"  Use --fix to regenerate {invalid} invalid hashes"))

    def _verify_rate_limits(self, network_key, fix_invalid):
        """Verify PostbackRateLimit integrity hashes."""
        self.stdout.write("\n=== Verifying PostbackRateLimit ===")
        
        queryset = PostbackRateLimit.objects.all()
        if network_key:
            queryset = queryset.filter(network__network_key=network_key)

        total = queryset.count()
        valid = 0
        invalid = 0

        self.stdout.write(f"Checking {total} PostbackRateLimit records...")

        for rate_limit in queryset:
            if rate_limit.verify_integrity():
                valid += 1
            else:
                invalid += 1
                if fix_invalid:
                    rate_limit.integrity_hash = rate_limit.generate_integrity_hash()
                    rate_limit.save(update_fields=['integrity_hash'])
                    self.stdout.write(f"  Fixed hash for rate limit {rate_limit.name}")

        self.stdout.write(f"PostbackRateLimit: {valid} valid, {invalid} invalid")
        if invalid > 0 and not fix_invalid:
            self.stdout.write(self.style.WARNING(f"  Use --fix to regenerate {invalid} invalid hashes"))
