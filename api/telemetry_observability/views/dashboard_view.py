"""
Dashboard Widget views for Telemetry Observability.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..models.dashboard_widget import DashboardWidget
from ..serializers.dashboard_serializer import (
    DashboardWidgetSerializer,
    DashboardWidgetCreateSerializer,
    DashboardWidgetUpdateSerializer,
)
from ..services.dashboard_service import DashboardService


class DashboardView(APIView):
    """
    Class-based API view for DashboardWidget CRUD + data retrieval.

    GET    /api/v1/telemetry/dashboards/                   → list widgets
    GET    /api/v1/telemetry/dashboards/<widget_id>/       → retrieve single widget
    POST   /api/v1/telemetry/dashboards/                   → create widget
    PUT    /api/v1/telemetry/dashboards/<widget_id>/       → full update
    PATCH  /api/v1/telemetry/dashboards/<widget_id>/       → partial update
    DELETE /api/v1/telemetry/dashboards/<widget_id>/       → delete widget

    Retrieve live widget data via ?data=true:
    GET    /api/v1/telemetry/dashboards/<widget_id>/?data=true
    """

    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = DashboardService()

    def get(self, request, widget_id=None):
        """
        List all widgets (with optional filters) or retrieve one by ID.
        If ?data=true, also returns live data for that widget.

        Query params (list mode):
            dashboard_id, widget_type, data_source, is_active, limit
        """
        if widget_id is not None:
            widget = self.service.get_widget(widget_id)
            if widget is None:
                return Response(
                    {'error': f'Widget with id {widget_id} not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            response_data = DashboardWidgetSerializer(widget).data

            if request.query_params.get('data', '').lower() == 'true':
                try:
                    hours = int(request.query_params.get('hours', 24))
                except ValueError:
                    hours = 24
                response_data['widget_data'] = self.service.get_widget_data(
                    widget, hours=hours
                )

            return Response(response_data, status=status.HTTP_200_OK)

        # --- List mode ---
        dashboard_id = request.query_params.get('dashboard_id')
        widget_type = request.query_params.get('widget_type')
        data_source = request.query_params.get('data_source')
        is_active = request.query_params.get('is_active')

        is_active_bool = None
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'

        widgets = self.service.get_widgets(
            dashboard_id=int(dashboard_id) if dashboard_id else None,
            widget_type=widget_type,
            data_source=data_source,
            is_active=is_active_bool,
        )
        serializer = DashboardWidgetSerializer(widgets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, widget_id=None):
        """
        Create a new dashboard widget.
        """
        serializer = DashboardWidgetCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        widget = self.service.create_widget(serializer.validated_data)
        return Response(
            DashboardWidgetSerializer(widget).data,
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, widget_id=None):
        """
        Full update of a dashboard widget.
        """
        if widget_id is None:
            return Response(
                {'error': 'widget_id is required for update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        widget = self.service.get_widget(widget_id)
        if widget is None:
            return Response(
                {'error': f'Widget with id {widget_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = DashboardWidgetSerializer(widget, data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, widget_id=None):
        """
        Partial update of a dashboard widget (e.g., move/resize).
        """
        if widget_id is None:
            return Response(
                {'error': 'widget_id is required for partial update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        widget = self.service.get_widget(widget_id)
        if widget is None:
            return Response(
                {'error': f'Widget with id {widget_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = DashboardWidgetUpdateSerializer(widget, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(DashboardWidgetSerializer(widget).data, status=status.HTTP_200_OK)

    def delete(self, request, widget_id=None):
        """
        Delete a dashboard widget by ID.
        """
        if widget_id is None:
            return Response(
                {'error': 'widget_id is required for deletion.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        success = self.service.delete_widget(widget_id)
        if not success:
            return Response(
                {'error': f'Widget with id {widget_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
