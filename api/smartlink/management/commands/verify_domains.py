from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Verify all pending custom domains via DNS TXT check'

    def handle(self, *args, **options):
        from ...models.publisher import PublisherDomain
        from ...choices import DomainVerificationStatus
        from ...services.core.DomainService import DomainService

        svc = DomainService()
        pending = PublisherDomain.objects.filter(
            verification_status__in=[
                DomainVerificationStatus.PENDING,
                DomainVerificationStatus.FAILED,
            ]
        )
        self.stdout.write(f'Verifying {pending.count()} domains...\n')

        verified = failed = 0
        for domain_obj in pending:
            try:
                svc.verify(domain_obj)
                self.stdout.write(self.style.SUCCESS(f'  ✅ Verified: {domain_obj.domain}'))
                verified += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Failed: {domain_obj.domain} — {e}'))
                failed += 1

        self.stdout.write(f'\nResult: {verified} verified, {failed} failed.')
