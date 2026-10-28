"""
Alert views for Telemetry Observability.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..models.alert import Alert
from ..serializers.alert_serializer import (
    AlertSerializer,
    AlertCreateSerializer,
    AlertAcknowledgeSerializer,
    AlertStatisticsSerializer,
    AlertBatchCreateSerializer,
)
from ..services.alert_service import AlertService


class AlertView(APIView):
    """
    Class-based API view for Alert CRUD + actions.

    GET    /api/v1/telemetry/alerts/                     → list alerts
    GET    /api/v1/telemetry/alerts/<alert_id>/          → retrieve single alert
    POST   /api/v1/telemetry/alerts/                     → create alert
    PUT    /api/v1/telemetry/alerts/<alert_id>/          → update alert
    DELETE /api/v1/telemetry/alerts/<alert_id>/          → delete alert

    Action-style (via query param ?action=acknowledge|resolve):
    POST   /api/v1/telemetry/alerts/<alert_id>/?action=acknowledge
    POST   /api/v1/telemetry/alerts/<alert_id>/?action=resolve
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = AlertService()

    def get(self, request, alert_id=None):
        """
        List all alerts (with optional filters) or retrieve one by ID.

        Query params (list mode):
            alert_type, severity, status, source, service, environment, limit
        """
        if alert_id is not None:
            try:
                alert = Alert.objects.get(id=alert_id)
            except Alert.DoesNotExist:
                return Response(
                    {'error': f'Alert with id {alert_id} not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = AlertSerializer(alert)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # --- List mode ---
        alert_type = request.query_params.get('alert_type')
        severity = request.query_params.get('severity')
        alert_status = request.query_params.get('status')
        source = request.query_params.get('source')
        service_name = request.query_params.get('service')
        environment = request.query_params.get('environment')

        try:
            limit = int(request.query_params.get('limit', 100))
        except ValueError:
            return Response(
                {'error': "'limit' must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        alerts = self.service.get_alerts(
            alert_type=alert_type,
            severity=severity,
            status=alert_status,
            source=source,
            service=service_name,
            environment=environment,
            limit=limit,
        )
        serializer = AlertSerializer(alerts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, alert_id=None):
        """
        Create a new alert, or perform an action on an existing one.

        If alert_id is present and ?action=acknowledge → acknowledge the alert.
        If alert_id is present and ?action=resolve    → resolve the alert.
        Otherwise                                      → create a new alert.
        Supports batch via ?batch=true.
        """
        action = request.query_params.get('action')

        if alert_id is not None and action == 'acknowledge':
            serializer = AlertAcknowledgeSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            success = self.service.acknowledge_alert(
                alert_id, serializer.validated_data['user']
            )
            if not success:
                return Response(
                    {'error': f'Alert with id {alert_id} not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            alert = Alert.objects.get(id=alert_id)
            return Response(AlertSerializer(alert).data, status=status.HTTP_200_OK)

        if alert_id is not None and action == 'resolve':
            success = self.service.resolve_alert(alert_id)
            if not success:
                return Response(
                    {'error': f'Alert with id {alert_id} not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            alert = Alert.objects.get(id=alert_id)
            return Response(AlertSerializer(alert).data, status=status.HTTP_200_OK)

        # --- Create mode ---
        if request.query_params.get('batch', '').lower() == 'true':
            batch_serializer = AlertBatchCreateSerializer(data=request.data)
            if not batch_serializer.is_valid():
                return Response(batch_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            alerts = self.service.batch_create_alerts(
                batch_serializer.validated_data['alerts']
            )
            return Response(
                AlertSerializer(alerts, many=True).data,
                status=status.HTTP_201_CREATED,
            )

        serializer = AlertCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        alert = self.service.create_alert(serializer.validated_data)
        return Response(AlertSerializer(alert).data, status=status.HTTP_201_CREATED)

    def put(self, request, alert_id=None):
        """
        Update an existing alert (status, severity, metadata).
        """
        if alert_id is None:
            return Response(
                {'error': 'alert_id is required for update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            alert = Alert.objects.get(id=alert_id)
        except Alert.DoesNotExist:
            return Response(
                {'error': f'Alert with id {alert_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = AlertSerializer(alert, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, alert_id=None):
        """
        Delete an alert by ID.
        """
        if alert_id is None:
            return Response(
                {'error': 'alert_id is required for deletion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            alert = Alert.objects.get(id=alert_id)
        except Alert.DoesNotExist:
            return Response(
                {'error': f'Alert with id {alert_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        alert.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
