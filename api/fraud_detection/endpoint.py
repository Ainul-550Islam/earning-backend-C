# =============================================================================
# fraud_detection/endpoint.py
# =============================================================================
"""
API Endpoint Layer for Fraud Detection System.

Provides REST API endpoints for external fraud database integration,
real-time fraud detection, and administrative functions.
"""

from __future__ import annotations
import json

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request

from api.fraud_detection.interactors import get_interactor
from api.fraud_detection.webhooks import threat_intelligence_aggregator
from api.fraud_detection.sanctions import sanctions_manager, ip_reputation_checker
from api.fraud_detection.compliance import aml_compliance_manager, fraud_reporting_manager
from api.fraud_detection.encryption import encrypt_sensitive_data
from api.fraud_detection.exceptions import FraudDetectionError, WebhookError, IntegrationError
from api.fraud_detection.constants import RISK_THRESHOLDS
from api.fraud_detection.serializers import (
    FraudDetectionRequestSerializer, FraudCaseSerializer,
    FraudAlertSerializer, RiskProfileSerializer
)


logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def fraud_detection_webhook(request: Request) -> JsonResponse:
    """
    Webhook endpoint for external fraud detection systems.
    
    Receives fraud alerts and threat intelligence from external systems.
    """
    try:
        # Parse JSON payload
        payload = request.body.decode('utf-8')
        data = {}
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook payload: {e}")
            return JsonResponse(
                {'error': 'Invalid JSON payload', 'status': 'error'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify webhook signature if configured
        signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')
        webhook_secret = getattr(settings, 'FRAUD_WEBHOOK_SECRET', '')
        
        if webhook_secret and signature:
            import hmac
            import hashlib
            
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(expected_signature, signature.replace('sha256=', '')):
                logger.error("Webhook signature verification failed")
                return JsonResponse(
                    {'error': 'Invalid signature', 'status': 'error'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        
        # Process webhook based on type
        webhook_type = data.get('webhook_type', 'unknown')
        
        if webhook_type == 'fraud_alert':
            result = _process_fraud_alert_webhook(data)
        elif webhook_type == 'threat_intelligence':
            result = _process_threat_intelligence_webhook(data)
        elif webhook_type == 'sanctions_update':
            result = _process_sanctions_update_webhook(data)
        else:
            logger.warning(f"Unknown webhook type: {webhook_type}")
            result = {'status': 'ignored', 'reason': 'Unknown webhook type'}
        
        return JsonResponse(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error processing fraud detection webhook: {e}")
        return JsonResponse(
            {'error': 'Internal server error', 'status': 'error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comprehensive_fraud_detection(request: Request) -> Response:
    """
    Comprehensive fraud detection endpoint.
    
    Performs multi-layered fraud analysis including multi-account detection,
    pattern analysis, risk assessment, and compliance screening.
    """
    try:
        # Validate request data
        serializer = FraudDetectionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid request data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        user_id = validated_data['user_id']
        transaction_data = validated_data.get('transaction_data', {})
        context = validated_data.get('context', {})
        
        # Execute comprehensive fraud detection workflow
        fraud_detector = get_interactor('fraud_detection')
        detection_result = fraud_detector.execute(user_id, transaction_data, context)
        
        # Format response
        response_data = {
            'status': 'success',
            'detection_result': detection_result,
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except FraudDetectionError as e:
        logger.error(f"Fraud detection error: {e}")
        return Response(
            {'error': 'Fraud detection failed', 'details': str(e)},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    except Exception as e:
        logger.error(f"Unexpected error in fraud detection: {e}")
        return Response(
            {'error': 'Internal server error', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ip_reputation_check(request: Request) -> Response:
    """
    IP reputation checking endpoint.
    
    Checks IP address against multiple threat intelligence sources
    and returns aggregated reputation data.
    """
    try:
        ip_address = request.data.get('ip_address')
        if not ip_address:
            return Response(
                {'error': 'IP address is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        additional_data = request.data.get('additional_data', {})
        
        # Get external reputation data
        external_result = threat_intelligence_aggregator.aggregate_ip_reputation(
            ip_address, additional_data
        )
        
        # Get internal reputation data
        internal_result = ip_reputation_checker.analyze_ip_geolocation(ip_address)
        
        # Combine results
        combined_result = {
            'ip_address': ip_address,
            'external_reputation': external_result,
            'internal_reputation': internal_result,
            'overall_risk_score': max(
                external_result.get('aggregated_reputation', {}).get('overall_score', 0),
                internal_result.get('risk_score', 0)
            ),
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(combined_result, status=status.HTTP_200_OK)
        
    except IntegrationError as e:
        logger.error(f"IP reputation integration error: {e}")
        return Response(
            {'error': 'Integration failed', 'details': str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        logger.error(f"Unexpected error in IP reputation check: {e}")
        return Response(
            {'error': 'Internal server error', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sanctions_screening(request: Request) -> Response:
    """
    Sanctions screening endpoint.
    
    Screens transactions against sanctions lists, high-risk countries,
    and blocked entities.
    """
    try:
        # Validate request data
        required_fields = ['user_id', 'transaction_data']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {'error': f'Missing required field: {field}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        user_id = request.data['user_id']
        transaction_data = request.data['transaction_data']
        
        # Perform sanctions screening
        screening_result = sanctions_manager.screen_transaction(transaction_data)
        
        # Perform AML compliance check
        aml_result = aml_compliance_manager.monitor_transaction_limits(transaction_data)
        
        # Combine results
        combined_result = {
            'user_id': user_id,
            'sanctions_screening': screening_result,
            'aml_compliance': aml_result,
            'overall_compliance': screening_result['passed'] and aml_result['compliant'],
            'risk_level': 'high' if not (screening_result['passed'] and aml_result['compliant']) else 'low',
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(combined_result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Unexpected error in sanctions screening: {e}")
        return Response(
            {'error': 'Internal server error', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fraud_case_management(request: Request) -> Response:
    """
    Fraud case management endpoint.
    
    Handles fraud case lifecycle operations including assignment,
    investigation, resolution, and escalation.
    """
    try:
        # Validate request data
        required_fields = ['case_id', 'action']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {'error': f'Missing required field: {field}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        case_id = request.data['case_id']
        action = request.data['action']
        action_data = request.data.get('action_data', {})
        
        # Execute case management workflow
        case_manager = get_interactor('fraud_case_management')
        management_result = case_manager.execute(case_id, action, action_data)
        
        return Response(management_result, status=status.HTTP_200_OK)
        
    except FraudDetectionError as e:
        logger.error(f"Fraud case management error: {e}")
        return Response(
            {'error': 'Case management failed', 'details': str(e)},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    except Exception as e:
        logger.error(f"Unexpected error in fraud case management: {e}")
        return Response(
            {'error': 'Internal server error', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fraud_analytics(request: Request) -> Response:
    """
    Fraud analytics endpoint.
    
    Provides fraud detection analytics, statistics, and trends.
    """
    try:
        # Get query parameters
        days = int(request.GET.get('days', 30))
        user_id = request.GET.get('user_id')
        
        # Validate days parameter
        if days < 1 or days > 365:
            return Response(
                {'error': 'Days parameter must be between 1 and 365'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Get analytics data (simplified - would query actual databases)
        analytics_data = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'summary_statistics': {
                'total_detections': 0,
                'high_risk_cases': 0,
                'fraud_cases_opened': 0,
                'fraud_cases_resolved': 0,
                'average_risk_score': 0.0
            },
            'risk_distribution': {
                'low': 0,
                'medium': 0,
                'high': 0,
                'critical': 0
            },
            'detection_trends': [],
            'compliance_metrics': {
                'sar_reports_filed': 0,
                'aml_compliance_rate': 0.0,
                'sanctions_screening_passed': 0
            }
        }
        
        # Filter by user if specified
        if user_id:
            analytics_data['user_specific'] = {
                'user_id': user_id,
                'user_risk_score': 0,
                'user_alerts_count': 0,
                'user_cases_count': 0
            }
        
        return Response(analytics_data, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response(
            {'error': 'Invalid parameter value', 'details': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error in fraud analytics: {e}")
        return Response(
            {'error': 'Internal server error', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def risk_profile_update(request: Request) -> Response:
    """
    Risk profile update endpoint.
    
    Updates user risk profiles based on various triggers and events.
    """
    try:
        # Validate request data
        required_fields = ['user_id', 'update_trigger']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {'error': f'Missing required field: {field}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        user_id = request.data['user_id']
        update_trigger = request.data['update_trigger']
        trigger_data = request.data.get('trigger_data', {})
        
        # Execute risk profile update workflow
        risk_updater = get_interactor('risk_profile_update')
        update_result = risk_updater.execute(user_id, update_trigger, trigger_data)
        
        return Response(update_result, status=status.HTTP_200_OK)
        
    except FraudDetectionError as e:
        logger.error(f"Risk profile update error: {e}")
        return Response(
            {'error': 'Risk profile update failed', 'details': str(e)},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
    except Exception as e:
        logger.error(f"Unexpected error in risk profile update: {e}")
        return Response(
            {'error': 'Internal server error', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@require_http_methods(["POST"])
def external_fraud_report(request: Request) -> JsonResponse:
    """
    External fraud report submission endpoint.
    
    Receives fraud reports from external systems and databases.
    """
    try:
        # Parse JSON payload
        payload = request.body.decode('utf-8')
        data = {}
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in fraud report: {e}")
            return JsonResponse(
                {'error': 'Invalid JSON payload', 'status': 'error'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate required fields
        required_fields = ['report_id', 'fraud_type', 'severity', 'fraud_data']
        for field in required_fields:
            if field not in data:
                return JsonResponse(
                    {'error': f'Missing required field: {field}', 'status': 'error'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Process fraud report
        report_result = _process_external_fraud_report(data)
        
        return JsonResponse(report_result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error processing external fraud report: {e}")
        return JsonResponse(
            {'error': 'Internal server error', 'status': 'error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health_check(request: Request) -> Response:
    """
    System health check endpoint.
    
    Returns the health status of the fraud detection system components.
    """
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'components': {
                'database': 'healthy',
                'webhooks': 'healthy',
                'encryption': 'healthy',
                'compliance': 'healthy'
            },
            'metrics': {
                'active_cases': 0,
                'recent_alerts': 0,
                'system_load': 0.0,
                'response_time_ms': 0
            }
        }
        
        # Check webhook connectivity
        try:
            # Simple connectivity test
            client_count = len(threat_intelligence_aggregator.clients)
            health_status['components']['webhooks'] = 'healthy' if client_count > 0 else 'degraded'
        except Exception as e:
            logger.error(f"Webhook health check failed: {e}")
            health_status['components']['webhooks'] = 'unhealthy'
        
        # Check database connectivity (simplified)
        try:
            from api.fraud_detection.models import FraudRule
            rule_count = FraudRule.objects.count()
            health_status['metrics']['active_rules'] = rule_count
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status['components']['database'] = 'unhealthy'
        
        # Determine overall status
        component_statuses = list(health_status['components'].values())
        if 'unhealthy' in component_statuses:
            health_status['status'] = 'unhealthy'
        elif 'degraded' in component_statuses:
            health_status['status'] = 'degraded'
        
        return Response(health_status, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Unexpected error in health check: {e}")
        return Response(
            {'status': 'unhealthy', 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Helper functions for webhook processing

def _process_fraud_alert_webhook(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process fraud alert webhook from external system."""
    try:
        alert_data = data.get('alert_data', {})
        
        # Validate alert data
        required_fields = ['alert_id', 'severity', 'user_id', 'alert_type']
        for field in required_fields:
            if field not in alert_data:
                return {
                    'status': 'error',
                    'reason': f'Missing required field in alert_data: {field}'
                }
        
        # Create internal fraud alert
        from api.fraud_detection.repositories import fraud_alert_repository
        
        alert_create_data = {
            'user_id': alert_data['user_id'],
            'alert_type': alert_data['alert_type'],
            'severity_score': _convert_severity_to_score(alert_data['severity']),
            'description': alert_data.get('description', ''),
            'details': alert_data,
            'source': 'external_webhook',
            'acknowledged': False
        }
        
        created_alert = fraud_alert_repository.create(**alert_create_data)
        
        # Send notifications if high severity
        notifications_sent = []
        if alert_data['severity'].lower() in ['high', 'critical']:
            try:
                fraud_report = fraud_reporting_manager.create_fraud_report({
                    'user_id': alert_data['user_id'],
                    'severity': alert_data['severity'],
                    'risk_score': alert_create_data['severity_score'],
                    'summary': f"External fraud alert: {alert_data.get('description', 'No description')}",
                    'evidence': alert_data
                })
                notifications_sent = fraud_report.get('notifications_sent', [])
            except Exception as e:
                logger.error(f"Failed to send fraud alert notifications: {e}")
        
        return {
            'status': 'processed',
            'alert_id': created_alert.pk,
            'internal_alert_id': created_alert.pk,
            'notifications_sent': notifications_sent,
            'processed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing fraud alert webhook: {e}")
        return {
            'status': 'error',
            'reason': str(e)
        }


def _process_threat_intelligence_webhook(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process threat intelligence webhook from external system."""
    try:
        threat_data = data.get('threat_data', {})
        
        # Validate threat data
        if 'threat_id' not in threat_data:
            return {
                'status': 'error',
                'reason': 'Missing threat_id in threat_data'
            }
        
        # Process threat intelligence update
        threat_type = threat_data.get('threat_type', 'unknown')
        
        if threat_type == 'ip_reputation':
            # Update IP reputation cache
            ip_address = threat_data.get('ip_address')
            if ip_address:
                # In practice, this would update internal reputation databases
                logger.info(f"Updated IP reputation for {ip_address}")
        
        elif threat_type == 'sanctions_update':
            # Update sanctions lists
            sanctions_manager._load_high_risk_countries()  # Refresh sanctions data
            logger.info("Updated sanctions lists from external source")
        
        return {
            'status': 'processed',
            'threat_id': threat_data['threat_id'],
            'threat_type': threat_type,
            'processed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing threat intelligence webhook: {e}")
        return {
            'status': 'error',
            'reason': str(e)
        }


def _process_sanctions_update_webhook(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process sanctions update webhook from external system."""
    try:
        update_data = data.get('update_data', {})
        
        # Validate update data
        if 'update_id' not in update_data:
            return {
                'status': 'error',
                'reason': 'Missing update_id in update_data'
            }
        
        # Update sanctions configuration
        sanctions_manager._load_high_risk_countries()
        sanctions_manager._load_blocked_countries()
        
        return {
            'status': 'processed',
            'update_id': update_data['update_id'],
            'sanctions_updated': True,
            'processed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing sanctions update webhook: {e}")
        return {
            'status': 'error',
            'reason': str(e)
        }


def _process_external_fraud_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process external fraud report submission."""
    try:
        report_id = data['report_id']
        fraud_type = data['fraud_type']
        severity = data['severity']
        fraud_data = data['fraud_data']
        
        # Create fraud case from external report
        from api.fraud_detection.repositories import fraud_case_repository
        
        case_data = {
            'case_type': 'external_report',
            'risk_score': _convert_severity_to_score(severity),
            'status': 'open',
            'description': f"External fraud report: {fraud_type}",
            'evidence_summary': fraud_data,
            'severity': severity.lower(),
            'detection_method': 'external_report',
            'external_report_id': report_id
        }
        
        created_case = fraud_case_repository.create(**case_data)
        
        # Send notifications
        notifications_sent = []
        try:
            fraud_report = fraud_reporting_manager.create_fraud_report({
                'case_id': created_case.pk,
                'user_id': fraud_data.get('user_id'),
                'severity': severity,
                'risk_score': case_data['risk_score'],
                'summary': f"External fraud report received: {fraud_type}",
                'evidence': fraud_data
            })
            notifications_sent = fraud_report.get('notifications_sent', [])
        except Exception as e:
            logger.error(f"Failed to send external fraud report notifications: {e}")
        
        return {
            'status': 'processed',
            'case_id': created_case.pk,
            'internal_case_id': created_case.pk,
            'notifications_sent': notifications_sent,
            'processed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing external fraud report: {e}")
        return {
            'status': 'error',
            'reason': str(e)
        }


def _convert_severity_to_score(severity: str) -> int:
    """Convert severity level to risk score."""
    severity_mapping = {
        'low': 25,
        'medium': 50,
        'high': 75,
        'critical': 95
    }
    return severity_mapping.get(severity.lower(), 50)
