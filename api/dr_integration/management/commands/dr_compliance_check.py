from django.core.management.base import BaseCommand
from dr_integration.services import DRSecurityBridge

class Command(BaseCommand):
    help = 'Run DR compliance check'
    def add_arguments(self, parser):
        parser.add_argument('--framework', default='HIPAA',
                             choices=['HIPAA','PCI_DSS','SOC2','ISO27001','GDPR','NIST_CSF'])
    def handle(self, *args, **options):
        result = DRSecurityBridge().check_compliance(options['framework'])
        compliant = result.get('compliant', False)
        icon = '✅' if compliant else '❌'
        self.stdout.write(f"\n{icon} {options['framework']}: {'COMPLIANT' if compliant else 'NON-COMPLIANT'}")
        for gap in result.get('gaps', []): self.stdout.write(f"  ⚠️  {gap}")
        if not compliant: raise SystemExit(1)
