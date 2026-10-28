# api/admin_panel/viewsets/BulkActionViewSet.py
"""BulkActionViewSet — bulk approve/reject/delete/ban on any model."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.apps import apps
from django.utils import timezone

from ..constants import BULK_ACTION_MAX_IDS


class BulkActionViewSet(viewsets.ViewSet):
    """
    Perform bulk operations on any model.
    POST /api/admin-panel/bulk-actions/execute/
    Body: {model: 'app.Model', action: 'approve', ids: [1,2,3], params: {}}
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['post'])
    def execute(self, request):
        """Execute a bulk action on selected records."""
        model_path = request.data.get('model', '')
        action_type = request.data.get('action', '')
        ids = request.data.get('ids', [])
        params = request.data.get('params', {})

        # Validation
        if not model_path or not action_type or not ids:
            return Response(
                {'error': 'model, action, and ids are all required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if len(ids) > BULK_ACTION_MAX_IDS:
            return Response(
                {'error': f'Too many IDs. Maximum {BULK_ACTION_MAX_IDS} per bulk action.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Dispatch to handler
        handler = self._get_handler(action_type)
        if not handler:
            return Response(
                {'error': f'Unknown action type: "{action_type}". '
                          f'Allowed: approve, reject, delete, ban, unban, verify, activate, deactivate, send_notification'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            return Response({'error': f'Model "{model_path}" not found: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = handler(Model, ids, params, request.user)
            # Log bulk action
            self._log_bulk_action(request.user, action_type, model_path, ids, result)
            return Response({'success': True, 'action': action_type, 'model': model_path, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_handler(self, action_type: str):
        handlers = {
            'approve': self._handle_approve,
            'reject': self._handle_reject,
            'delete': self._handle_delete,
            'ban': self._handle_ban,
            'unban': self._handle_unban,
            'verify': self._handle_verify,
            'activate': self._handle_activate,
            'deactivate': self._handle_deactivate,
            'send_notification': self._handle_send_notification,
            'export': self._handle_export,
        }
        return handlers.get(action_type)

    def _handle_approve(self, Model, ids, params, actor):
        status_field = params.get('status_field', 'status')
        approved_value = params.get('approved_value', 'approved')
        updated = Model.objects.filter(pk__in=ids).update(**{status_field: approved_value})
        return {'updated': updated, 'field': status_field, 'value': approved_value}

    def _handle_reject(self, Model, ids, params, actor):
        status_field = params.get('status_field', 'status')
        rejected_value = params.get('rejected_value', 'rejected')
        reason = params.get('reason', '')
        update_kwargs = {status_field: rejected_value}
        if reason and hasattr(Model, 'rejection_reason'):
            update_kwargs['rejection_reason'] = reason
        updated = Model.objects.filter(pk__in=ids).update(**update_kwargs)
        return {'updated': updated, 'field': status_field, 'value': rejected_value}

    def _handle_delete(self, Model, ids, params, actor):
        if not actor.is_superuser:
            raise PermissionError('Only superadmins can bulk delete records.')
        deleted, breakdown = Model.objects.filter(pk__in=ids).delete()
        return {'deleted': deleted, 'breakdown': breakdown}

    def _handle_ban(self, Model, ids, params, actor):
        updates = {}
        if hasattr(Model, 'is_active'):
            updates['is_active'] = False
        if hasattr(Model, 'account_status'):
            updates['account_status'] = 'banned'
        if not updates:
            raise ValueError(f'Model {Model.__name__} has no is_active or account_status field.')
        updated = Model.objects.filter(pk__in=ids).update(**updates)
        return {'banned': updated}

    def _handle_unban(self, Model, ids, params, actor):
        updates = {}
        if hasattr(Model, 'is_active'):
            updates['is_active'] = True
        if hasattr(Model, 'account_status'):
            updates['account_status'] = 'active'
        if not updates:
            raise ValueError(f'Model {Model.__name__} has no is_active or account_status field.')
        updated = Model.objects.filter(pk__in=ids).update(**updates)
        return {'unbanned': updated}

    def _handle_verify(self, Model, ids, params, actor):
        field = params.get('field', 'email_verified')
        updated = Model.objects.filter(pk__in=ids).update(**{field: True})
        return {'verified': updated, 'field': field}

    def _handle_activate(self, Model, ids, params, actor):
        updated = Model.objects.filter(pk__in=ids).update(is_active=True)
        return {'activated': updated}

    def _handle_deactivate(self, Model, ids, params, actor):
        updated = Model.objects.filter(pk__in=ids).update(is_active=False)
        return {'deactivated': updated}

    def _handle_send_notification(self, Model, ids, params, actor):
        """Send a notification to selected users."""
        title = params.get('title', 'Admin Notification')
        message = params.get('message', '')
        notification_type = params.get('type', 'INFO')
        if not message:
            raise ValueError('message is required for send_notification action.')
        # Create a SiteNotification targeting these users
        from ..models.core import SiteNotification
        notif = SiteNotification.objects.create(
            title=title,
            message=message,
            notification_type=notification_type,
            is_active=True,
        )
        return {'notification_id': notif.pk, 'sent_to_count': len(ids)}

    def _handle_export(self, Model, ids, params, actor):
        """Queue an export for selected record IDs."""
        fmt = params.get('format', 'csv')
        from ..models.reports import DataExport
        export = DataExport.objects.create(
            model_name=f'{Model._meta.app_label}.{Model.__name__}',
            filters={'pk__in': ids},
            format=fmt,
            status='queued',
            requested_by=actor,
            label=f'Bulk Export {Model.__name__}',
        )
        try:
            from ..tasks import process_data_export
            process_data_export.delay(str(export.export_id))
        except Exception:
            from ..tasks.data_export_tasks import process_export
            process_export(str(export.export_id))
        return {'export_id': str(export.export_id), 'status': 'queued'}

    def _log_bulk_action(self, actor, action_type, model_path, ids, result):
        try:
            from ..models.activity import AdminActivity
            AdminActivity.log(
                actor=actor,
                action=f'bulk_{action_type}',
                model_name=model_path,
                changes={'ids': ids[:20], 'total': len(ids), 'result': result},
            )
        except Exception:
            pass

    @action(detail=False, methods=['get'])
    def available_actions(self, request):
        """List all available bulk action types."""
        return Response({
            'actions': [
                {'key': 'approve', 'label': 'Approve', 'requires_superadmin': False},
                {'key': 'reject', 'label': 'Reject', 'requires_superadmin': False},
                {'key': 'delete', 'label': 'Delete', 'requires_superadmin': True},
                {'key': 'ban', 'label': 'Ban Users', 'requires_superadmin': False},
                {'key': 'unban', 'label': 'Unban Users', 'requires_superadmin': False},
                {'key': 'verify', 'label': 'Mark Verified', 'requires_superadmin': False},
                {'key': 'activate', 'label': 'Activate', 'requires_superadmin': False},
                {'key': 'deactivate', 'label': 'Deactivate', 'requires_superadmin': False},
                {'key': 'send_notification', 'label': 'Send Notification', 'requires_superadmin': False},
                {'key': 'export', 'label': 'Export Selected', 'requires_superadmin': False},
            ]
        })