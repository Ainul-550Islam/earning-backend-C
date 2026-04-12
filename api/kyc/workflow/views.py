# kyc/workflow/views.py  ── WORLD #1
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from .models import KYCWorkflow, KYCWorkflowStep, KYCWorkflowRun, DEFAULT_WORKFLOWS


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def workflow_list(request):
    tenant = getattr(request.user, 'tenant', None)
    if request.method == 'GET':
        qs = KYCWorkflow.objects.filter(tenant=tenant).order_by('-created_at')
        return Response([{
            'id':          w.id, 'name': w.name, 'status': w.status,
            'is_default':  w.is_default, 'version': w.version,
            'total_runs':  w.total_runs, 'pass_count': w.pass_count,
            'step_count':  w.steps.count(),
        } for w in qs])

    # POST — create workflow
    template = request.data.get('template')
    if template and template in DEFAULT_WORKFLOWS:
        tpl = DEFAULT_WORKFLOWS[template]
        wf  = KYCWorkflow.objects.create(
            tenant=tenant, name=tpl['name'], status='draft', created_by=request.user,
        )
        for step_data in tpl['steps']:
            KYCWorkflowStep.objects.create(workflow=wf, **step_data)
        return Response({'id': wf.id, 'name': wf.name, 'message': f'Workflow created from {template} template'}, status=201)

    wf = KYCWorkflow.objects.create(
        tenant=tenant, name=request.data.get('name', 'New Workflow'),
        description=request.data.get('description', ''),
        created_by=request.user,
    )
    return Response({'id': wf.id, 'name': wf.name}, status=201)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def workflow_detail(request, wf_id):
    try:
        wf = KYCWorkflow.objects.get(id=wf_id)
    except KYCWorkflow.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        steps = [{
            'id': s.id, 'step_type': s.step_type, 'name': s.name,
            'order': s.order, 'is_enabled': s.is_enabled,
            'is_required': s.is_required, 'condition': s.condition, 'config': s.config,
        } for s in wf.steps.order_by('order')]
        return Response({'id': wf.id, 'name': wf.name, 'status': wf.status, 'steps': steps,
                         'total_runs': wf.total_runs, 'pass_count': wf.pass_count})

    if request.method == 'DELETE':
        wf.status = 'archived'; wf.save(); return Response({'message': 'Archived'})

    if 'name' in request.data: wf.name = request.data['name']
    if 'status' in request.data:
        if request.data['status'] == 'active': wf.activate()
        else: wf.status = request.data['status']; wf.save()
    return Response({'id': wf.id, 'status': wf.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def workflow_activate(request, wf_id):
    try:
        wf = KYCWorkflow.objects.get(id=wf_id)
        wf.activate()
        return Response({'message': f'Workflow "{wf.name}" activated'})
    except KYCWorkflow.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def workflow_run(request, wf_id):
    """Execute a workflow for current user's KYC"""
    from kyc.models import KYC
    try:
        wf  = KYCWorkflow.objects.get(id=wf_id, status='active')
        kyc = KYC.objects.get(user=request.user)
    except KYCWorkflow.DoesNotExist:
        return Response({'error': 'Workflow not found or not active'}, status=404)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC not found'}, status=404)

    from .engine import WorkflowEngine
    engine = WorkflowEngine(wf, kyc, request.user)
    result = engine.execute()
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def workflow_runs(request, wf_id):
    runs = KYCWorkflowRun.objects.filter(workflow_id=wf_id).order_by('-started_at')[:50]
    return Response([{
        'id':          r.id, 'user': r.user.username, 'status': r.status,
        'final_decision': r.final_decision,
        'duration_seconds': r.duration_seconds, 'started_at': r.started_at,
    } for r in runs])


@api_view(['GET'])
def workflow_templates(request):
    """Available workflow templates"""
    return Response([{
        'key':   k,
        'name':  v['name'],
        'steps': len(v['steps']),
    } for k, v in DEFAULT_WORKFLOWS.items()])
