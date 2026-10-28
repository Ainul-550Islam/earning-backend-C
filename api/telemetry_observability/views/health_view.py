"""
Health Status views for Telemetry Observability.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..models.health_status import HealthStatus
from ..serializers.health_serializer import (
    HealthStatusSerializer,
    HealthStatusCreateSerializer,
)


class HealthView(APIView):
    """
    Class-based API view for HealthStatus CRUD operations.

    GET    /api/v1/telemetry/health/                        → list all health statuses
    GET    /api/v1/telemetry/health/<service_name>/         → get health for a specific service
    POST   /api/v1/telemetry/health/                        → create or update health status
    PUT    /api/v1/telemetry/health/<service_name>/         → update health for a service
    DELETE /api/v1/telemetry/health/<service_name>/         → delete health record
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, service_name=None):
        """
        List all health statuses or retrieve a specific service's health.

        Query params (list mode):
            component_name, status, environment, limit
        """
        if service_name is not None:
            component_name = request.query_params.get('component_name')
            environment = request.query_params.get('environment')

            queryset = HealthStatus.objects.filter(service_name=service_name)
            if component_name:
                queryset = queryset.filter(component_name=component_name)
            if environment:
                queryset = queryset.filter(environment=environment)

            statuses = list(queryset.order_by('-last_check'))
            if not statuses:
                return Response(
                    {'error': f'No health records found for service "{service_name}".'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = HealthStatusSerializer(statuses, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # --- List mode ---
        queryset = HealthStatus.objects.all()

        health_status = request.query_params.get('status')
        environment = request.query_params.get('environment')

        if health_status:
            queryset = queryset.filter(status=health_status)
        if environment:
            queryset = queryset.filter(environment=environment)

        try:
            limit = int(request.query_params.get('limit', 100))
        except ValueError:
            return Response(
                {'error': "'limit' must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = queryset.order_by('-last_check')[:limit]
        serializer = HealthStatusSerializer(results, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, service_name=None):
        """
        Create or update a health status record.
        Uses update_or_create based on (service_name, component_name, environment).
        """
        serializer = HealthStatusCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        obj, created = HealthStatus.objects.update_or_create(
            service_name=data['service_name'],
            component_name=data.get('component_name', ''),
            environment=data.get('environment', 'production'),
            defaults={
                'status': data.get('status', 'unknown'),
                'health_score': data.get('health_score', 100),
                'uptime': data.get('uptime', 0.0),
                'response_time_ms': data.get('response_time_ms'),
                'error_rate': data.get('error_rate', 0.0),
                'metadata': data.get('metadata', {}),
            },
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(HealthStatusSerializer(obj).data, status=response_status)

    def put(self, request, service_name=None):
        """
        Update a health status record for a specific service.
        """
        if service_name is None:
            return Response(
                {'error': 'service_name is required for update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        component_name = request.query_params.get('component_name', '')
        environment = request.query_params.get('environment', 'production')

        try:
            health = HealthStatus.objects.get(
                service_name=service_name,
                component_name=component_name,
                environment=environment,
            )
        except HealthStatus.DoesNotExist:
            return Response(
                {'error': f'Health record for service "{service_name}" not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = HealthStatusSerializer(health, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, service_name=None):
        """
        Delete health status records for a specific service.
        """
        if service_name is None:
            return Response(
                {'error': 'service_name is required for deletion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted_count, _ = HealthStatus.objects.filter(
            service_name=service_name
        ).delete()
        if deleted_count == 0:
            return Response(
                {'error': f'No health records found for service "{service_name}".'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {'deleted': deleted_count, 'service_name': service_name},
            status=status.HTTP_200_OK,
        )
