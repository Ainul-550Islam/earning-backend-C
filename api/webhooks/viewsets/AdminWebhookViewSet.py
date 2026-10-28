"""Admin Webhook ViewSet

This module contains the ViewSet for admin webhook operations.

FIXES APPLIED:
    [ADM-01] IsAdminUser used in two @action permission_classes but was
             never imported — NameError on first admin API call.
             Fix: added to rest_framework.permissions import line.

    [ADM-02] global_statistics used models.Avg without importing Avg from
             django.db.models — NameError at runtime.
             Fix: added `from django.db.models import Avg`.

    [ADM-03] global_statistics reassigned `successful_deliveries` from an
             int (count) to a QuerySet, so the Response body serialised an
             ORM queryset object instead of a number.
             Fix: renamed the queryset variable to `successful_logs_qs`.

    [ADM-04] export_data and import_data referenced endpoint.timeout_seconds
             and endpoint.rate_limit_per_min which do not exist on
             WebhookEndpoint.  This caused AttributeError on export and
             TypeError on import.
             Fix: removed those columns from the CSV and the create kwargs.
"""

from django.db.models import Avg
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser   # FIX [ADM-01]
from rest_framework.response import Response

from ..filters import AdminWebhookFilter
from ..models import WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog
from ..permissions import IsSuperUser
from ..serializers import (
    AdminWebhookEndpointSerializer,
    AdminWebhookSubscriptionSerializer,
    AdminWebhookDeliveryLogSerializer,
    AdminWebhookBatchOperationSerializer,
    AdminWebhookStatsSerializer,
    AdminWebhookHealthCheckSerializer,
    AdminWebhookHealthCheckResultSerializer,
    AdminWebhookCleanupSerializer,
    AdminWebhookExportSerializer,
    AdminWebhookImportSerializer,
    AdminWebhookTestSerializer,
    AdminWebhookTestResultSerializer,
)


class AdminWebhookViewSet(viewsets.ModelViewSet):
    """ViewSet for admin webhook operations (superadmin only)."""

    queryset            = WebhookEndpoint.objects.all()
    permission_classes  = [IsAuthenticated, IsSuperUser]
    filter_backends     = [DjangoFilterBackend]
    filterset_class     = AdminWebhookFilter

    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        # All admin CRUD paths use the same rich serializer; extend here
        # if write vs read serializers diverge in the future.
        return AdminWebhookEndpointSerializer

    # ─────────────────────────────────────────────────────────────────────────
    #  Statistics
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path='global-statistics')
    def global_statistics(self, request):
        """Get global webhook statistics."""
        # ── Endpoint counts ───────────────────────────────────────────────────
        total_endpoints     = WebhookEndpoint.objects.count()
        active_endpoints    = WebhookEndpoint.objects.filter(status="active").count()
        inactive_endpoints  = WebhookEndpoint.objects.filter(status="inactive").count()
        suspended_endpoints = WebhookEndpoint.objects.filter(status="suspended").count()

        # ── Subscription counts ───────────────────────────────────────────────
        total_subscriptions  = WebhookSubscription.objects.count()
        active_subscriptions = WebhookSubscription.objects.filter(is_active=True).count()

        # ── Delivery counts ───────────────────────────────────────────────────
        total_deliveries    = WebhookDeliveryLog.objects.count()
        # FIX [ADM-03]: keep this as a plain int — do NOT reuse the variable
        # name below for the queryset, otherwise the Response serialises an
        # ORM queryset object instead of the numeric count.
        successful_count    = WebhookDeliveryLog.objects.filter(status="success").count()
        failed_count        = WebhookDeliveryLog.objects.filter(status="failed").count()
        success_rate        = (
            round(successful_count / total_deliveries * 100, 2)
            if total_deliveries > 0
            else 0
        )

        # ── Performance ───────────────────────────────────────────────────────
        # FIX [ADM-02]: use the imported Avg directly; `models.Avg` was a
        # NameError because `models` was never imported from django.db.
        successful_logs_qs = WebhookDeliveryLog.objects.filter(status="success")
        avg_response_time  = (
            successful_logs_qs.aggregate(avg=Avg("response_time_ms"))["avg"] or 0
            if successful_logs_qs.exists()
            else 0
        )

        return Response({
            "total_endpoints":      total_endpoints,
            "active_endpoints":     active_endpoints,
            "inactive_endpoints":   inactive_endpoints,
            "suspended_endpoints":  suspended_endpoints,
            "total_subscriptions":  total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "total_deliveries":     total_deliveries,
            "successful_deliveries": successful_count,   # now always an int
            "failed_deliveries":    failed_count,
            "success_rate":         success_rate,
            "avg_response_time":    round(avg_response_time, 2),
        })

    # ─────────────────────────────────────────────────────────────────────────
    #  Batch Operations
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path='batch-operation')
    def batch_operation(self, request):
        """Perform batch operations on endpoints."""
        serializer = AdminWebhookBatchOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        endpoint_ids = serializer.validated_data["endpoint_ids"]
        operation    = serializer.validated_data["operation"]

        try:
            endpoints = WebhookEndpoint.objects.filter(id__in=endpoint_ids)

            if operation == "activate":
                updated_count = endpoints.update(status="active")
                message = f"Activated {updated_count} endpoints"

            elif operation == "deactivate":
                updated_count = endpoints.update(status="inactive")
                message = f"Deactivated {updated_count} endpoints"

            elif operation == "suspend":
                updated_count = endpoints.update(status="suspended")
                message = f"Suspended {updated_count} endpoints"

            elif operation == "test":
                from ..services.core.DispatchService import DispatchService
                dispatch_service = DispatchService()
                results = []
                for endpoint in endpoints:
                    try:
                        result = dispatch_service.emit(
                            endpoint=endpoint,
                            event_type="webhook.admin.test",
                            payload={"admin_test": True, "timestamp": timezone.now().isoformat()},
                        )
                        results.append(
                            f"{endpoint.label or endpoint.target_url}: "
                            f"{'Success' if result else 'Failed'}"
                        )
                    except Exception as exc:
                        results.append(
                            f"{endpoint.label or endpoint.target_url}: Error — {exc}"
                        )
                return Response({"success": True, "message": "Test results", "results": results})

            elif operation == "rotate_secret":
                from ..services.core.SecretRotationService import SecretRotationService
                rotation_service = SecretRotationService()
                rotated_count = 0
                for endpoint in endpoints:
                    try:
                        rotation_service.rotate_secret(endpoint)
                        rotated_count += 1
                    except Exception:
                        continue
                message       = f"Rotated secrets for {rotated_count} endpoints"
                updated_count = rotated_count

            elif operation == "check_health":
                from ..services.analytics import HealthMonitorService
                health_service = HealthMonitorService()
                results = []
                for endpoint in endpoints:
                    try:
                        health = health_service.check_endpoint_health(endpoint)
                        health_status = "Healthy" if health["is_healthy"] else "Unhealthy"
                        results.append(
                            f"{endpoint.label or endpoint.target_url}: {health_status}"
                        )
                    except Exception as exc:
                        results.append(
                            f"{endpoint.label or endpoint.target_url}: Error — {exc}"
                        )
                return Response({
                    "success": True,
                    "message": "Health check results",
                    "results": results,
                })

            else:
                return Response(
                    {"error": f"Unknown operation: {operation}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({
                "success":       True,
                "message":       message,
                "updated_count": updated_count,
            })

        except Exception as exc:
            return Response(
                {"success": False, "error": str(exc), "message": "Batch operation failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  Health
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path='health-check-all')
    def health_check_all(self, request):
        """Perform health check on all endpoints."""
        serializer = AdminWebhookHealthCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        endpoint_ids  = serializer.validated_data.get("endpoint_ids")
        all_endpoints = serializer.validated_data.get("all_endpoints", False)

        try:
            from ..services.analytics import HealthMonitorService
            health_service = HealthMonitorService()

            if all_endpoints:
                endpoints = WebhookEndpoint.objects.all()
            elif endpoint_ids:
                endpoints = WebhookEndpoint.objects.filter(id__in=endpoint_ids)
            else:
                endpoints = WebhookEndpoint.objects.filter(status="active")

            results = []
            for endpoint in endpoints:
                try:
                    health_result = health_service.check_endpoint_health(endpoint)
                    results.append({
                        "endpoint_id":       str(endpoint.id),
                        "endpoint_label":    endpoint.label,
                        "endpoint_url":      endpoint.target_url,
                        "is_healthy":        health_result["is_healthy"],
                        "status_code":       health_result.get("status_code"),
                        "response_time_ms":  health_result.get("response_time_ms"),
                        "error":             health_result.get("error"),
                        "checked_at":        timezone.now().isoformat(),
                    })
                except Exception as exc:
                    results.append({
                        "endpoint_id":    str(endpoint.id),
                        "endpoint_label": endpoint.label,
                        "endpoint_url":   endpoint.target_url,
                        "is_healthy":     False,
                        "error":          str(exc),
                        "checked_at":     timezone.now().isoformat(),
                    })

            return Response({
                "success":         True,
                "results":         results,
                "total_endpoints": len(results),
            })

        except Exception as exc:
            return Response(
                {"success": False, "error": str(exc), "message": "Health check failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  Cleanup
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path='cleanup-data')
    def cleanup_data(self, request):
        """Clean up old webhook data."""
        serializer = AdminWebhookCleanupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        operation = serializer.validated_data["operation"]
        days      = serializer.validated_data["days"]

        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)

            if operation == "exhausted_logs":
                deleted_count = WebhookDeliveryLog.objects.filter(
                    status="exhausted", created_at__lt=cutoff_date
                ).delete()[0]
                message = f"Cleaned up {deleted_count} exhausted logs"

            elif operation == "failed_logs":
                deleted_count = WebhookDeliveryLog.objects.filter(
                    status="failed", created_at__lt=cutoff_date
                ).delete()[0]
                message = f"Cleaned up {deleted_count} failed logs"

            elif operation == "old_logs":
                deleted_count = WebhookDeliveryLog.objects.filter(
                    created_at__lt=cutoff_date
                ).delete()[0]
                message = f"Cleaned up {deleted_count} old logs"

            elif operation == "health_logs":
                from ..models import WebhookHealthLog
                deleted_count = WebhookHealthLog.objects.filter(
                    checked_at__lt=cutoff_date
                ).delete()[0]
                message = f"Cleaned up {deleted_count} health logs"

            elif operation == "analytics":
                from ..models import WebhookAnalytics
                deleted_count = WebhookAnalytics.objects.filter(
                    date__lt=cutoff_date.date()
                ).delete()[0]
                message = f"Cleaned up {deleted_count} analytics records"

            elif operation == "all_data":
                from ..models import WebhookHealthLog, WebhookAnalytics
                delivery_deleted  = WebhookDeliveryLog.objects.filter(
                    created_at__lt=cutoff_date
                ).delete()[0]
                health_deleted    = WebhookHealthLog.objects.filter(
                    checked_at__lt=cutoff_date
                ).delete()[0]
                analytics_cutoff  = timezone.now() - timedelta(days=365)
                analytics_deleted = WebhookAnalytics.objects.filter(
                    date__lt=analytics_cutoff.date()
                ).delete()[0]
                message = (
                    f"Cleaned up {delivery_deleted} delivery logs, "
                    f"{health_deleted} health logs, "
                    f"{analytics_deleted} analytics records"
                )

            else:
                return Response(
                    {"error": f"Unknown operation: {operation}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({
                "success":     True,
                "message":     message,
                "cutoff_date": cutoff_date.isoformat(),
                "days":        days,
            })

        except Exception as exc:
            return Response(
                {"success": False, "error": str(exc), "message": "Data cleanup failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  Export
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path='export-data')
    def export_data(self, request):
        """Export webhook data to CSV."""
        serializer = AdminWebhookExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        export_type   = serializer.validated_data["export_type"]
        export_format = serializer.validated_data["format"]
        date_from     = serializer.validated_data.get("date_from")
        date_to       = serializer.validated_data.get("date_to")

        try:
            import csv
            import os
            from datetime import datetime

            export_dir = "exports"
            os.makedirs(export_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename  = f"webhook_{export_type}_{timestamp}.{export_format}"
            filepath  = os.path.join(export_dir, filename)

            if export_type == "endpoints":
                queryset = WebhookEndpoint.objects.all()
                if date_from:
                    queryset = queryset.filter(created_at__gte=date_from)
                if date_to:
                    queryset = queryset.filter(created_at__lte=date_to)

                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    # FIX [ADM-04]: removed timeout_seconds and rate_limit_per_min
                    # columns — these fields do not exist on WebhookEndpoint and
                    # caused AttributeError on every export call.
                    writer.writerow([
                        "ID", "Label", "URL", "Status", "HTTP Method",
                        "Max Retries", "Verify SSL", "Owner", "Created At",
                    ])
                    for ep in queryset:
                        writer.writerow([
                            str(ep.id),
                            ep.label or "",
                            ep.target_url,
                            ep.status,
                            ep.http_method,
                            ep.max_retries,
                            ep.verify_ssl,
                            ep.owner.username if ep.owner else "",
                            ep.created_at.isoformat(),
                        ])

            elif export_type == "subscriptions":
                queryset = WebhookSubscription.objects.all()
                if date_from:
                    queryset = queryset.filter(created_at__gte=date_from)
                if date_to:
                    queryset = queryset.filter(created_at__lte=date_to)

                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "ID", "Endpoint", "Event Type", "Is Active",
                        "Filters", "Created At",
                    ])
                    for sub in queryset:
                        writer.writerow([
                            str(sub.id),
                            str(sub.endpoint.id),
                            sub.event_type,
                            sub.is_active,
                            str(sub.filters) if sub.filters else "",
                            sub.created_at.isoformat(),
                        ])

            elif export_type == "delivery_logs":
                queryset = WebhookDeliveryLog.objects.all()
                if date_from:
                    queryset = queryset.filter(created_at__gte=date_from)
                if date_to:
                    queryset = queryset.filter(created_at__lte=date_to)

                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "ID", "Endpoint", "Event Type", "Status",
                        "HTTP Status Code", "Duration (ms)", "Error Message",
                        "Attempt Number", "Created At",
                    ])
                    for log in queryset:
                        writer.writerow([
                            str(log.id),
                            str(log.endpoint.id),
                            log.event_type,
                            log.status,
                            log.http_status_code,
                            log.response_time_ms,
                            log.error_message or "",
                            log.attempt_number,
                            log.created_at.isoformat(),
                        ])

            else:
                return Response(
                    {"error": f"Unknown export type: {export_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({
                "success":     True,
                "message":     f"Data exported to {filepath}",
                "filename":    filename,
                "export_type": export_type,
                "format":      export_format,
            })

        except Exception as exc:
            return Response(
                {"success": False, "error": str(exc), "message": "Data export failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  Import
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path='import-data')
    def import_data(self, request):
        """Import webhook data from CSV."""
        serializer = AdminWebhookImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        import_type = serializer.validated_data["import_type"]
        file        = serializer.validated_data["file"]
        overwrite   = serializer.validated_data["overwrite"]

        try:
            import csv
            import json

            content = file.read().decode("utf-8")

            if import_type == "endpoints":
                reader         = csv.DictReader(content.splitlines())
                imported_count = 0
                errors         = []

                for row in reader:
                    try:
                        # FIX [ADM-04]: timeout_seconds and rate_limit_per_min
                        # do not exist on WebhookEndpoint — removed from kwargs
                        # to prevent TypeError on create/update_or_create.
                        endpoint_data = {
                            "label":       row.get("Label", ""),
                            "target_url":  row["URL"],
                            "status":      row.get("Status", "active"),
                            "http_method": row.get("HTTP Method", "POST"),
                            "max_retries": int(row.get("Max Retries", 3)),
                            "verify_ssl":  row.get("Verify SSL", "True").lower() == "true",
                            "owner":       request.user,
                        }
                        if overwrite:
                            WebhookEndpoint.objects.update_or_create(
                                target_url=endpoint_data["target_url"],
                                defaults=endpoint_data,
                            )
                        else:
                            WebhookEndpoint.objects.create(**endpoint_data)
                        imported_count += 1
                    except Exception as exc:
                        errors.append(f"Row {reader.line_num}: {exc}")

                return Response({
                    "success":        True,
                    "message":        f"Imported {imported_count} endpoints",
                    "imported_count": imported_count,
                    "errors":         errors,
                })

            elif import_type == "subscriptions":
                reader         = csv.DictReader(content.splitlines())
                imported_count = 0
                errors         = []

                for row in reader:
                    try:
                        subscription_data = {
                            "endpoint":   WebhookEndpoint.objects.get(id=row["Endpoint"]),
                            "event_type": row["Event Type"],
                            "is_active":  row.get("Is Active", "True").lower() == "true",
                            "filters":    json.loads(row.get("Filters", "{}")),
                        }
                        if overwrite:
                            WebhookSubscription.objects.update_or_create(
                                endpoint=subscription_data["endpoint"],
                                event_type=subscription_data["event_type"],
                                defaults=subscription_data,
                            )
                        else:
                            WebhookSubscription.objects.create(**subscription_data)
                        imported_count += 1
                    except Exception as exc:
                        errors.append(f"Row {reader.line_num}: {exc}")

                return Response({
                    "success":        True,
                    "message":        f"Imported {imported_count} subscriptions",
                    "imported_count": imported_count,
                    "errors":         errors,
                })

            else:
                return Response(
                    {"error": f"Unknown import type: {import_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as exc:
            return Response(
                {"success": False, "error": str(exc), "message": "Data import failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  Test Endpoint
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path='test-endpoint')
    def test_endpoint(self, request):
        """Test an endpoint."""
        serializer = AdminWebhookTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        endpoint_id    = serializer.validated_data["endpoint_id"]
        test_payload   = serializer.validated_data.get("test_payload")
        custom_headers = serializer.validated_data.get("custom_headers")

        try:
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id)

            if not test_payload:
                test_payload = {
                    "admin_test": True,
                    "timestamp":  timezone.now().isoformat(),
                    "message":    "Admin test webhook",
                }

            headers = {"Content-Type": "application/json", "X-Admin-Test": "True"}
            if custom_headers:
                headers.update(custom_headers)

            from ..services.core.DispatchService import DispatchService
            dispatch_service = DispatchService()

            start_time = timezone.now()
            result     = dispatch_service.emit(
                endpoint=endpoint,
                event_type="webhook.admin.test",
                payload=test_payload,
                headers=headers,
            )
            end_time        = timezone.now()
            processing_time = (end_time - start_time).total_seconds()

            delivery_log = WebhookDeliveryLog.objects.filter(
                endpoint=endpoint,
                event_type="webhook.admin.test",
                created_at__gte=start_time,
            ).first()

            result_data = {
                "success":         result,
                "endpoint_id":     str(endpoint_id),
                "endpoint_label":  endpoint.label,
                "endpoint_url":    endpoint.target_url,
                "processing_time": processing_time,
                "test_payload":    test_payload,
                "tested_at":       end_time.isoformat(),
            }
            if result and delivery_log:
                result_data["status_code"]      = delivery_log.http_status_code
                result_data["response_time_ms"] = delivery_log.response_time_ms
                result_data["response_body"]    = delivery_log.response_body
            elif not result:
                result_data["error"] = "Test webhook failed"

            return Response(result_data)

        except WebhookEndpoint.DoesNotExist:
            return Response(
                {"success": False, "error": "Endpoint not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            return Response(
                {"success": False, "error": str(exc), "message": "Test webhook failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  System Health
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path='system-health')
    def system_health(self, request):
        """Get system health overview."""
        try:
            from django.db import connection
            connection.ensure_connection()

            redis_status = "unknown"
            try:
                from django.core.cache import cache
                cache.set("health_check", "ok", 10)
                redis_status = "ok" if cache.get("health_check") == "ok" else "error"
            except Exception:
                redis_status = "unavailable"

            celery_status = "unknown"
            try:
                from celery import current_app
                celery_status = "ok" if current_app else "error"
            except Exception:
                celery_status = "unavailable"

            total_endpoints  = WebhookEndpoint.objects.count()
            total_deliveries = WebhookDeliveryLog.objects.count()

            from datetime import timedelta
            recent_deliveries = WebhookDeliveryLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()

            return Response({
                "database_status":        "ok",
                "redis_status":           redis_status,
                "celery_status":          celery_status,
                "total_endpoints":        total_endpoints,
                "total_deliveries":       total_deliveries,
                "recent_deliveries_1h":   recent_deliveries,
                "system_time":            timezone.now().isoformat(),
            })

        except Exception as exc:
            return Response(
                {"database_status": "error", "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ─────────────────────────────────────────────────────────────────────────
    #  Integration System Actions
    # ─────────────────────────────────────────────────────────────────────────

    @action(
        detail=False,
        methods=["get"],
        url_path="integration-status",
        # FIX [ADM-01]: IsAdminUser is now imported at module level — no more
        # NameError when this action is first called.
        permission_classes=[IsAdminUser],
    )
    def integration_status(self, request):
        """
        GET /webhooks/admin/webhooks/integration-status/
        Returns the current state of the enterprise integration system.
        """
        from ..INTEGRATION_SYSTEM import is_enabled, get_integration_safe, IntegrationStatus
        from dataclasses import asdict
        from django.core.cache import cache

        if not is_enabled():
            return Response({"enabled": False, "message": "Integration disabled in settings."})

        integ  = get_integration_safe()
        health = integ.health_check()
        cached = cache.get("integ:last_sync_stats", {})

        s = IntegrationStatus(
            enabled      = True,
            connected    = health.get("status") == "ok",
            last_sync    = cached.get("timestamp"),
            synced_count = cached.get("synced", 0),
            failed_count = cached.get("failed", 0),
            health       = health,
        )
        return Response(asdict(s))

    @action(
        detail=False,
        methods=["post"],
        url_path="integration-sync",
        # FIX [ADM-01]: IsAdminUser is now imported at module level.
        permission_classes=[IsAdminUser],
        url_name="integration-sync",
    )
    def integration_sync_now(self, request):
        """
        POST /webhooks/admin/webhooks/integration-sync/
        Trigger an immediate full integration sync via Celery task.
        """
        from ..INTEGRATION_SYSTEM import is_enabled
        from ..tasks.integration_sync_tasks import sync_all_endpoints_with_integration

        if not is_enabled():
            return Response({"error": "Integration disabled."}, status=status.HTTP_400_BAD_REQUEST)

        task = sync_all_endpoints_with_integration.delay()
        return Response({"status": "queued", "task_id": task.id}, status=status.HTTP_202_ACCEPTED)

    def get_queryset(self):
        """FIX: this override was scoping to `owner=self.request.user` -
        meaning a superuser could only ever see/manage endpoints *they*
        personally owned through the admin panel, never other users'
        endpoints. Confirmed via a real HTTP round-trip: an admin with no
        endpoints of their own got an empty list and a 404 on a real
        endpoint's detail URL. That directly contradicts this viewset's
        own purpose (IsSuperUser-gated, with force-dispatch/suspend/
        integration-sync actions - all platform-wide moderation, not
        self-service) and the class's own `queryset` attribute above,
        which already correctly says `.all()`. Removing the erroneous
        narrowing rather than leaving two contradictory sources of truth."""
        return WebhookEndpoint.objects.all()
