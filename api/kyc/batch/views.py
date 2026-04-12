# kyc/batch/views.py  ── WORLD #1
"""Batch verification API views."""
import csv, io, json
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.utils import timezone
from .models import BatchVerificationJob, BatchVerificationRecord


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def batch_jobs(request):
    """List all batch jobs / create new batch job"""
    if request.method == 'GET':
        qs = BatchVerificationJob.objects.filter(
            requested_by=request.user
        ).order_by('-created_at')[:20]
        return Response([{
            'id':            j.id,
            'job_type':      j.job_type,
            'status':        j.status,
            'total_records': j.total_records,
            'processed_count': j.processed_count,
            'success_count': j.success_count,
            'failed_count':  j.failed_count,
            'progress_pct':  j.progress_pct,
            'created_at':    j.created_at,
            'completed_at':  j.completed_at,
        } for j in qs])

    # POST — create batch job
    job_type    = request.data.get('job_type', 'api_bulk')
    tenant      = getattr(request.user, 'tenant', None)
    input_file  = request.FILES.get('file')

    job = BatchVerificationJob.objects.create(
        requested_by=request.user,
        tenant=tenant,
        job_type=job_type,
        config=json.loads(request.data.get('config', '{}')),
    )

    if input_file:
        job.input_file = input_file
        # Parse CSV to count records
        try:
            content = input_file.read().decode('utf-8-sig')
            reader  = csv.DictReader(io.StringIO(content))
            rows    = list(reader)
            job.total_records = len(rows)
            # Create batch records
            for i, row in enumerate(rows, 1):
                BatchVerificationRecord.objects.create(
                    job=job, row_number=i,
                    external_id=row.get('external_id', ''),
                    input_data=row,
                )
        except Exception as e:
            job.error_log = str(e)
        job.save()

    # Trigger async processing
    try:
        from kyc.tasks.kyc_tasks import process_batch_job
        process_batch_job.delay(job.id)
    except Exception:
        pass

    return Response({
        'id':            job.id,
        'status':        job.status,
        'total_records': job.total_records,
        'message':       'Batch job created. Processing will start shortly.',
    }, status=202)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def batch_job_status(request, job_id):
    """Get batch job progress"""
    try:
        job = BatchVerificationJob.objects.get(id=job_id)
    except BatchVerificationJob.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    return Response({
        'id':              job.id,
        'status':          job.status,
        'total_records':   job.total_records,
        'processed_count': job.processed_count,
        'success_count':   job.success_count,
        'failed_count':    job.failed_count,
        'skipped_count':   job.skipped_count,
        'progress_pct':    job.progress_pct,
        'result_file':     job.result_file.url if job.result_file else None,
        'started_at':      job.started_at,
        'completed_at':    job.completed_at,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def batch_job_records(request, job_id):
    """Get individual records from a batch job"""
    records = BatchVerificationRecord.objects.filter(job_id=job_id).order_by('row_number')
    status_f = request.query_params.get('status')
    if status_f: records = records.filter(status=status_f)
    return Response([{
        'row':         r.row_number,
        'external_id': r.external_id,
        'status':      r.status,
        'kyc_id':      r.kyc_id,
        'error':       r.error,
    } for r in records[:500]])
