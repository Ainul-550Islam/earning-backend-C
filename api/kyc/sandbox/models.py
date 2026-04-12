# kyc/sandbox/models.py  ── WORLD #1
"""
Sandbox environment — Jumio/Sumsub সব provider-ই sandbox দেয়।
Developers এটা দিয়ে test করে without affecting production data.
"""
from django.db import models
from django.conf import settings


class SandboxConfig(models.Model):
    """Per-tenant sandbox configuration."""
    tenant           = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='sandbox_config', null=True, blank=True)
    is_sandbox_mode  = models.BooleanField(default=False, db_index=True)
    sandbox_api_key  = models.CharField(max_length=100, null=True, blank=True)

    # Behavior overrides in sandbox
    auto_approve_all     = models.BooleanField(default=False, help_text="Auto-approve all KYC in sandbox")
    auto_reject_pattern  = models.CharField(max_length=50, blank=True, help_text="Name pattern to auto-reject", null=True)
    ocr_confidence_override = models.FloatField(default=0.95)
    face_match_override  = models.FloatField(default=0.92)
    liveness_override    = models.CharField(max_length=10, default='success', null=True, blank=True)
    pep_test_names       = models.JSONField(default=list, blank=True, help_text="Names that trigger PEP hit in sandbox")
    sanctions_test_names = models.JSONField(default=list, blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'kyc_sandbox_configs'
        verbose_name = 'Sandbox Config'

    def __str__(self):
        mode = 'SANDBOX' if self.is_sandbox_mode else 'PRODUCTION'
        return f"[{mode}] {self.tenant}"


class SandboxTestCase(models.Model):
    """Pre-defined test cases for sandbox."""
    SCENARIO = [
        ('happy_path',       'Happy path — verified successfully'),
        ('pep_hit',          'PEP detected'),
        ('sanctions_hit',    'Sanctions list hit'),
        ('duplicate',        'Duplicate document'),
        ('low_quality',      'Low image quality'),
        ('face_mismatch',    'Face does not match'),
        ('liveness_fail',    'Liveness check failed'),
        ('under_age',        'User under 18'),
        ('expired_doc',      'Expired document'),
        ('fraud_suspected',  'High-risk fraud score'),
    ]
    name         = models.CharField(max_length=100, null=True, blank=True)
    scenario     = models.CharField(max_length=30, choices=SCENARIO, null=True, blank=True)
    description  = models.TextField(blank=True)
    test_data    = models.JSONField(default=dict, help_text="Input data for this test case")
    expected_outcome = models.JSONField(default=dict)
    is_active    = models.BooleanField(default=True)

    class Meta:
        db_table = 'kyc_sandbox_test_cases'
        verbose_name = 'Sandbox Test Case'

    def __str__(self):
        return f"TestCase[{self.scenario}] {self.name}"


# ──────────────────────────────────────────────────────────
# kyc/sandbox/views.py
# ──────────────────────────────────────────────────────────
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response


@api_view(['GET'])
def sandbox_status(request):
    """Check if sandbox mode is active for current tenant."""
    tenant = getattr(getattr(request, 'user', None), 'tenant', None)
    is_sandbox = False
    if tenant:
        try:
            config = SandboxConfig.objects.get(tenant=tenant)
            is_sandbox = config.is_sandbox_mode
        except SandboxConfig.DoesNotExist:
            pass
    return Response({
        'sandbox_mode': is_sandbox,
        'message': 'SANDBOX — All verifications are simulated. No real data processed.' if is_sandbox
                   else 'PRODUCTION — Live KYC verification active.',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sandbox_test_cases(request):
    """List all sandbox test cases with test data."""
    cases = SandboxTestCase.objects.filter(is_active=True)
    return Response([{
        'id':          c.id,
        'name':        c.name,
        'scenario':    c.scenario,
        'description': c.description,
        'test_data':   c.test_data,
        'expected':    c.expected_outcome,
    } for c in cases])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sandbox_run_test(request, test_case_id):
    """Run a sandbox test case against the KYC API."""
    try:
        tc = SandboxTestCase.objects.get(id=test_case_id, is_active=True)
    except SandboxTestCase.DoesNotExist:
        return Response({'error': 'Test case not found'}, status=404)
    return Response({
        'test_case':       tc.name,
        'scenario':        tc.scenario,
        'expected':        tc.expected_outcome,
        'simulated_result': tc.expected_outcome,
        'message':         f'Sandbox simulation for: {tc.scenario}',
    })


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdminUser])
def sandbox_config(request):
    """Get/update sandbox configuration for current tenant."""
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant'}, status=400)
    config, _ = SandboxConfig.objects.get_or_create(tenant=tenant)
    if request.method == 'GET':
        return Response({
            'is_sandbox_mode':     config.is_sandbox_mode,
            'auto_approve_all':    config.auto_approve_all,
            'auto_reject_pattern': config.auto_reject_pattern,
            'liveness_override':   config.liveness_override,
            'pep_test_names':      config.pep_test_names,
        })
    # PUT — update
    for field in ['is_sandbox_mode', 'auto_approve_all', 'auto_reject_pattern',
                  'liveness_override', 'pep_test_names', 'sanctions_test_names']:
        if field in request.data:
            setattr(config, field, request.data[field])
    config.save()
    return Response({'message': 'Sandbox config updated', 'is_sandbox_mode': config.is_sandbox_mode})
