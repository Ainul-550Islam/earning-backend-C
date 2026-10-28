"""
tasks/views_new_models.py
Missing CRUD ViewSets for 6 models with 0 view coverage:
  TaskLock, ProofSubmission, TaskDispute,
  TaskEventLog, TaskDependency, TaskInventory, FraudSignal
Import these into urls.py router.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from .models import (
    TaskLock, ProofSubmission, TaskDispute, TaskEventLog,
    TaskDependency, TaskInventory, FraudSignal,
)
from .serializers_new_models import (
    TaskLockSerializer, ProofSubmissionSerializer, TaskDisputeSerializer,
    TaskEventLogSerializer, TaskDependencySerializer,
    TaskInventorySerializer, FraudSignalSerializer,
)


class TaskLockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only view of task locks.
    Admins see all; users see only their own locks.
    POST /tasks/{id}/acquire_lock/  → acquire exclusive lock
    POST /tasks/{id}/release_lock/ → release lock
    """
    serializer_class = TaskLockSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = TaskLock.objects.select_related('task', 'user')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        # Only active locks by default
        return qs.filter(released_at__isnull=True)

    @action(detail=False, methods=['post'], url_path='acquire')
    def acquire(self, request):
        """Acquire an exclusive lock on a task."""
        task_id = request.data.get('task_id')
        if not task_id:
            return Response({'error': 'task_id required'}, status=400)
        from .models import MasterTask
        try:
            task = MasterTask.objects.get(pk=task_id, is_active=True)
        except MasterTask.DoesNotExist:
            return Response({'error': 'Task not found'}, status=404)

        # Check existing active exclusive lock
        existing = TaskLock.objects.filter(
            task=task,
            lock_type=TaskLock.LockType.EXCLUSIVE,
            released_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exclude(user=request.user).first()

        if existing:
            return Response({
                'error': 'Task is locked by another user',
                'expires_at': existing.expires_at,
                'time_remaining': existing.time_remaining_seconds,
            }, status=409)

        lock, created = TaskLock.objects.get_or_create(
            task=task,
            user=request.user,
            released_at=None,
            defaults={
                'lock_type': TaskLock.LockType.EXCLUSIVE,
                'expires_at': timezone.now() + timezone.timedelta(minutes=30),
            }
        )
        return Response(TaskLockSerializer(lock).data,
                        status=201 if created else 200)

    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """Release a held lock."""
        lock = self.get_object()
        if lock.user != request.user and not request.user.is_staff:
            return Response({'error': 'Cannot release another user\'s lock'}, status=403)
        lock.release(reason='user_manual_release')
        return Response({'status': 'released'})


class ProofSubmissionViewSet(viewsets.ModelViewSet):
    """
    CRUD for proof submissions.
    Users: create + retrieve own. Admins: full access + verify/reject actions.
    FraudGate is evaluated on every create() before the proof is persisted.
    """
    serializer_class = ProofSubmissionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Override create to run FraudGate before persisting proof.
        Uses handle_proof_submission_with_fraud_gate() from services_fraud_gate.py.
        """
        from .services_fraud_gate import handle_proof_submission_with_fraud_gate

        task_id    = request.data.get('task')
        proof_data = request.data.get('proof_data', {})
        ip_address = request.META.get('REMOTE_ADDR', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        if not task_id:
            return Response({'error': 'task field is required'}, status=status.HTTP_400_BAD_REQUEST)

        success, error_msg, proof = handle_proof_submission_with_fraud_gate(
            user_id    = request.user.id,
            task_id    = task_id,
            proof_data = proof_data,
            ip_address = ip_address,
            user_agent = user_agent,
        )

        if not success:
            return Response(
                {'error': error_msg or 'Proof submission rejected by fraud gate',
                 'error_code': 'FRAUD_GATE_REJECTED'},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response(
            ProofSubmissionSerializer(proof).data,
            status=status.HTTP_201_CREATED
        )

    def get_queryset(self):
        qs = ProofSubmission.objects.select_related('task', 'user', 'reviewed_by')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(verification_status=status_filter)
        return qs.order_by('-submitted_at')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        proof = self.get_object()
        proof.mark_verified(reviewed_by=request.user)
        return Response({'status': 'verified'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        proof = self.get_object()
        reason = request.data.get('reason', '')
        if not reason:
            return Response({'error': 'reason required'}, status=400)
        proof.mark_rejected(reason=reason, reviewed_by=request.user)
        return Response({'status': 'rejected'})

    @action(detail=True, methods=['get'])
    def integrity(self, request, pk=None):
        """Verify proof has not been tampered with."""
        proof = self.get_object()
        return Response({'integrity_ok': proof.verify_hash()})


class TaskDisputeViewSet(viewsets.ModelViewSet):
    """
    Dispute management.
    Users: create disputes on own completions. Admins: full access + resolve.
    """
    serializer_class = TaskDisputeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = TaskDispute.objects.select_related('user_task_completion', 'reported_by', 'assigned_to')
        if not self.request.user.is_staff:
            qs = qs.filter(reported_by=self.request.user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        severity = self.request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity)
        return qs.order_by('-reported_at')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def resolve(self, request, pk=None):
        dispute = self.get_object()
        dispute.status = TaskDispute.DisputeStatus.RESOLVED
        dispute.save(update_fields=['status'])
        return Response({'status': 'resolved'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def escalate(self, request, pk=None):
        dispute = self.get_object()
        level = request.data.get('level', 2)
        reason = request.data.get('reason', '')
        escalation = dispute.create_escalation(level=level, reason=reason, reviewed_by=request.user)
        return Response({'escalation_id': str(escalation.id), 'level': level})


class TaskEventLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Immutable audit trail. Read-only for all. Admins see all events."""
    serializer_class = TaskEventLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['event_type', 'actor_type']

    def get_queryset(self):
        qs = TaskEventLog.objects.select_related('task', 'user').order_by('-created_at')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        event_type = self.request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)
        task_id = self.request.query_params.get('task_id')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs


class TaskDependencyViewSet(viewsets.ModelViewSet):
    """Task prerequisite management. Admin only for create/update/delete."""
    serializer_class = TaskDependencySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = TaskDependency.objects.select_related('dependent_task', 'prerequisite_task')
        task_id = self.request.query_params.get('task_id')
        if task_id:
            qs = qs.filter(dependent_task_id=task_id)
        return qs.filter(is_active=True)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated],
            url_path='check/(?P<task_id>[^/.]+)')
    def check_user(self, request, task_id=None):
        """Check if authenticated user satisfies all dependencies for a task."""
        from .models import MasterTask
        try:
            task = MasterTask.objects.get(pk=task_id)
        except MasterTask.DoesNotExist:
            return Response({'error': 'Task not found'}, status=404)

        deps = TaskDependency.objects.filter(dependent_task=task, is_active=True)
        results = []
        all_satisfied = True
        for dep in deps:
            from .models import UserTaskCompletion
            satisfied = UserTaskCompletion.objects.filter(
                user=request.user,
                task=dep.prerequisite_task,
                status='completed',
            ).exists()
            if not satisfied:
                all_satisfied = False
            results.append({
                'dependency_type': dep.dependency_type,
                'prerequisite_task': str(dep.prerequisite_task),
                'satisfied': satisfied,
            })
        return Response({'all_satisfied': all_satisfied, 'dependencies': results})


class TaskInventoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Task inventory / supply management. Read for all, admin writes."""
    serializer_class = TaskInventorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = TaskInventory.objects.select_related('task')
        exhausted = self.request.query_params.get('exhausted')
        if exhausted == 'true':
            qs = qs.filter(is_exhausted=True)
        elif exhausted == 'false':
            qs = qs.filter(is_exhausted=False)
        return qs

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reset(self, request, pk=None):
        """Manually reset inventory counters."""
        inv = self.get_object()
        inv.filled_slots = 0
        inv.spent_usd = 0
        inv.is_exhausted = False
        inv.last_reset_at = timezone.now()
        inv.save(update_fields=['filled_slots', 'spent_usd', 'is_exhausted', 'last_reset_at'])
        return Response({'status': 'reset', 'available_slots': inv.total_slots})


class FraudSignalViewSet(viewsets.ReadOnlyModelViewSet):
    """Fraud signal audit trail. Users see own, admins see all + resolve appeals."""
    serializer_class = FraudSignalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = FraudSignal.objects.select_related('user').order_by('-triggered_at')
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        signal_type = self.request.query_params.get('signal_type')
        if signal_type:
            qs = qs.filter(signal_type=signal_type)
        appealed = self.request.query_params.get('appealed')
        if appealed == 'true':
            qs = qs.filter(is_appealed=True)
        return qs

    @action(detail=True, methods=['post'])
    def appeal(self, request, pk=None):
        """User submits an appeal on a fraud signal."""
        signal = self.get_object()
        if signal.user != request.user:
            return Response({'error': 'Cannot appeal another user\'s signal'}, status=403)
        notes = request.data.get('notes', '')
        signal.is_appealed = True
        signal.appeal_notes = notes
        signal.save(update_fields=['is_appealed', 'appeal_notes'])
        return Response({'status': 'appeal_submitted'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def resolve_appeal(self, request, pk=None):
        """Admin resolves a fraud signal appeal."""
        signal = self.get_object()
        resolution = request.data.get('resolution_notes', '')
        signal.appeal_resolved = True
        signal.resolution_notes = resolution
        signal.save(update_fields=['appeal_resolved', 'resolution_notes'])
        return Response({'status': 'appeal_resolved'})
