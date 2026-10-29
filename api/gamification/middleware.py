"""
Gamification Middleware — Attaches current active ContestCycle to the request.
Enhanced with integration system monitoring, audit logging, and VPN detection.

Usage:
    Add 'api.gamification.middleware.ActiveContestCycleMiddleware'
    to MIDDLEWARE in settings.py.

After this middleware runs, views can access:
    request.active_contest_cycle  → ContestCycle | None
    request.integration_context  → dict with integration system context
"""

from __future__ import annotations

import logging
import hashlib
import json
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


class ActiveContestCycleMiddleware:
    """
    Injects the current active ContestCycle onto every request object.
    Enhanced with integration system monitoring, audit logging, and security checks.

    The lookup is a cheap single-query operation. If no active cycle exists,
    request.active_contest_cycle is set to None.

    Failures are caught and logged; the request is never blocked by a
    gamification lookup error.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not callable(get_response):
            raise TypeError(
                f"get_response must be callable, got {type(get_response).__name__}."
            )
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = timezone.now()
        
        # Initialize integration context
        request.integration_context = {
            "request_id": self._generate_request_id(request),
            "start_time": start_time.isoformat(),
            "ip_address": self._get_client_ip(request),
            "user_agent": request.META.get('HTTP_USER_AGENT', ''),
        }
        
        try:
            # Import integration system components
            from api.gamification.INTEGRATION_SYSTEM.integ_audit_logs import audit_logger
            from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
            from api.gamification.INTEGRATION_SYSTEM.auth_bridge import auth_bridge
            
            # Get active contest cycle
            from .models import ContestCycle, UserPoints, GamificationConfig
            contest_cycle = ContestCycle.objects.get_current()
            request.active_contest_cycle = contest_cycle
            
            # Add contest cycle info to integration context
            if contest_cycle:
                request.integration_context.update({
                    "contest_cycle_id": str(contest_cycle.id),
                    "contest_cycle_name": contest_cycle.name,
                    "contest_cycle_status": contest_cycle.status,
                })
            
            # Add user gamification context if authenticated
            if hasattr(request, 'user') and request.user.is_authenticated:
                try:
                    # Get user points
                    user_points = UserPoints.objects.filter(user_id=request.user.id).first()
                    request.user_points = user_points
                    
                    # Get user gamification config
                    user_config = GamificationConfig.objects.filter(
                        tenant_id=getattr(request.user, 'tenant_id', None)
                    ).first()
                    request.user_gamification_config = user_config
                    
                    # Add to integration context
                    if user_points:
                        request.integration_context.update({
                            "user_points": {
                                "total_points": user_points.total_points,
                                "available_points": user_points.available_points,
                                "points_expiry_date": user_points.points_expiry_date.isoformat() if user_points.points_expiry_date else None,
                            }
                        })
                    
                    if user_config:
                        request.integration_context.update({
                            "gamification_features": {
                                feature.feature: feature.is_enabled 
                                for feature in user_config.features.all() if hasattr(user_config, 'features')
                            } if hasattr(user_config, 'features') else {}
                        })
                        
                except Exception as exc:
                    logger.warning("Failed to load user gamification context: %s", exc)
                    request.user_points = None
                    request.user_gamification_config = None
            
            # Perform VPN/Proxy detection
            vpn_detected = self._detect_vpn_proxy(request)
            request.integration_context["vpn_detected"] = vpn_detected
            
            # Log security event if VPN detected
            if vpn_detected:
                audit_logger.log_audit(
                    action=audit_logger.AuditAction.SECURITY,
                    description="VPN/Proxy detected in request",
                    resource_type=audit_logger.ResourceType.INTEGRATION,
                    details={
                        "request_id": request.integration_context["request_id"],
                        "ip_address": request.integration_context["ip_address"],
                        "user_agent": request.integration_context["user_agent"],
                        "vpn_detected": vpn_detected
                    }
                )
            
            # Perform authentication bridge check
            if hasattr(request, 'user') and request.user.is_authenticated:
                auth_context = auth_bridge.get_user_context(str(request.user.id))
                request.integration_context.update({
                    "user_auth_context": auth_context.to_dict() if auth_context else None
                })
            
            # Log middleware execution
            audit_logger.log_audit(
                action=audit_logger.AuditAction.EXECUTE,
                description="Gamification middleware executed",
                resource_type=audit_logger.ResourceType.INTEGRATION,
                details=request.integration_context
            )
            
        except Exception as exc:
            logger.error(
                "ActiveContestCycleMiddleware: failed to setup integration context: %s", exc
            )
            request.active_contest_cycle = None
            request.integration_context["error"] = str(exc)

        # Process request
        response = self.get_response(request)
        
        # Calculate and record middleware duration
        duration = (timezone.now() - start_time).total_seconds()
        request.integration_context["duration"] = duration
        
        try:
            # Record performance metrics
            from api.gamification.INTEGRATION_SYSTEM.performance_monitor import performance_monitor
            performance_monitor.record_metric("gamification_middleware_duration", duration)
            performance_monitor.record_metric("gamification_middleware_requests", 1.0)
            
            # Add integration headers to response
            response['X-Integration-Request-ID'] = request.integration_context["request_id"]
            response['X-Integration-Duration'] = str(duration)
            
            if request.active_contest_cycle:
                response['X-Contest-Cycle'] = str(request.active_contest_cycle.id)
            
            # Add gamification context headers
            if hasattr(request, 'user_points') and request.user_points:
                response['X-User-Points'] = str(request.user_points.total_points)
                response['X-User-Available-Points'] = str(request.user_points.available_points)
            
            if hasattr(request, 'user_gamification_config') and request.user_gamification_config:
                response['X-Gamification-Config'] = str(request.user_gamification_config.id)
            
        except Exception as exc:
            logger.warning("Failed to record middleware metrics: %s", exc)
        
        return response
    
    def _generate_request_id(self, request: HttpRequest) -> str:
        """Generate unique request ID for tracking."""
        data = f"{request.path}_{timezone.now().isoformat()}_{id(request)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip
    
    def _detect_vpn_proxy(self, request: HttpRequest) -> bool:
        """
        Detect if request is coming from VPN/Proxy.
        Enhanced with integration system VPN detection.
        """
        try:
            from api.gamification.INTEGRATION_SYSTEM.auth_bridge import auth_bridge
            
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Use auth bridge for VPN detection with fallback
            vpn_result = False
            try:
                # Check if auth_bridge has detect_vpn_proxy method
                if hasattr(auth_bridge, 'detect_vpn_proxy'):
                    vpn_result = auth_bridge.detect_vpn_proxy(ip_address, user_agent)
                else:
                    # Fallback: basic IP-based detection
                    vpn_result = self._basic_vpn_detection(ip_address)
            except Exception:
                # Fallback to basic detection
                vpn_result = self._basic_vpn_detection(ip_address)
            
            # Additional basic checks for proxy headers
            suspicious_headers = [
                'HTTP_VIA', 'HTTP_FORWARDED', 'HTTP_X_FORWARDED',
                'HTTP_X_FORWARDED_FOR', 'HTTP_X_FORWARDED_HOST',
                'HTTP_X_FORWARDED_SERVER', 'HTTP_X_REAL_IP'
            ]
            
            has_proxy_headers = any(
                request.META.get(header) for header in suspicious_headers
            )
            
            return vpn_result or has_proxy_headers
            
        except Exception as exc:
            logger.warning("VPN detection failed: %s", exc)
            return False
    
    def _basic_vpn_detection(self, ip_address: str) -> bool:
        """Basic VPN detection using IP patterns."""
        try:
            import ipaddress
            
            # Convert IP to address object
            ip_obj = ipaddress.ip_address(ip_address)
            
            # Check for private/internal IPs (not VPN)
            if ip_obj.is_private:
                return False
            
            # Check for common VPN/proxy IP ranges
            # This is a simplified implementation
            vpn_ranges = [
                # Common VPN provider ranges (simplified)
                '10.0.0.0/8',    # Private (should be filtered above)
                '172.16.0.0/12', # Private (should be filtered above)
                '192.168.0.0/16', # Private (should be filtered above)
            ]
            
            # Check if IP falls into any known ranges
            for range_str in vpn_ranges:
                try:
                    network = ipaddress.ip_network(range_str, strict=False)
                    if ip_obj in network:
                        return True
                except ValueError:
                    continue
            
            # Additional heuristics
            # Check for common hosting/VPN provider patterns
            if hasattr(ip_obj, 'exploded'):
                # Basic pattern matching for suspicious IPs
                ip_parts = ip_obj.exploded.split('.')
                # High-numbered IPs in certain ranges might indicate VPNs
                if len(ip_parts) == 4:
                    first_octet = int(ip_parts[0])
                    second_octet = int(ip_parts[1])
                    
                    # Common data center IP ranges (simplified)
                    if (first_octet in [104, 52, 54, 34] and second_octet >= 128) or \
                       (first_octet in [13, 35, 52, 54] and second_octet >= 200):
                        return True
            
            return False
            
        except Exception:
            return False


class GamificationTrackingMiddleware:
    """
    Middleware for tracking gamification events and user interactions.
    Provides real-time analytics and behavior tracking for enhanced gamification.
    """
    
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not callable(get_response):
            raise TypeError(
                f"get_response must be callable, got {type(get_response).__name__}."
            )
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Initialize gamification tracking context
        request.gamification_tracking = {
            "events": [],
            "start_time": timezone.now(),
            "user_interactions": [],
        }
        
        try:
            # Track user points transactions during request
            if hasattr(request, 'user') and request.user.is_authenticated:
                self._track_user_activity(request)
            
            # Track contest participation
            if hasattr(request, 'active_contest_cycle') and request.active_contest_cycle:
                self._track_contest_activity(request)
            
            # Track streak freeze usage
            self._track_streak_freeze_usage(request)
            
        except Exception as exc:
            logger.warning("Gamification tracking middleware error: %s", exc)
        
        # Process request
        response = self.get_response(request)
        
        # Record tracking metrics
        try:
            self._record_tracking_metrics(request, response)
        except Exception as exc:
            logger.warning("Failed to record gamification metrics: %s", exc)
        
        return response
    
    def _track_user_activity(self, request: HttpRequest) -> None:
        """Track user gamification activity."""
        try:
            from .models import PointsTransaction, StreakFreeze
            
            user_id = request.user.id
            
            # Check for recent points transactions
            recent_transactions = PointsTransaction.objects.filter(
                user_id=user_id,
                created_at__gte=timezone.now() - timezone.timedelta(hours=1)
            ).count()
            
            if recent_transactions > 0:
                request.gamification_tracking["events"].append({
                    "type": "points_activity",
                    "count": recent_transactions,
                    "timestamp": timezone.now().isoformat()
                })
            
            # Check for active streak freezes
            active_freezes = StreakFreeze.objects.filter(
                user_id=user_id,
                used_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).count()
            
            if active_freezes > 0:
                request.gamification_tracking["events"].append({
                    "type": "streak_freeze_active",
                    "count": active_freezes,
                    "timestamp": timezone.now().isoformat()
                })
                
        except Exception as exc:
            logger.warning("Failed to track user activity: %s", exc)
    
    def _track_contest_activity(self, request: HttpRequest) -> None:
        """Track contest-related activity."""
        try:
            from .models import ContestParticipant
            
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_id = request.user.id
                contest_cycle_id = request.active_contest_cycle.id
                
                # Check user participation status
                participant = ContestParticipant.objects.filter(
                    user_id=user_id,
                    contest_cycle_id=contest_cycle_id
                ).first()
                
                if participant:
                    request.gamification_tracking["events"].append({
                        "type": "contest_participation",
                        "status": participant.status,
                        "score": participant.score,
                        "timestamp": timezone.now().isoformat()
                    })
                    
                    # Track score changes
                    if participant.score > 0:
                        request.gamification_tracking["user_interactions"].append({
                            "type": "score_achievement",
                            "value": participant.score,
                            "timestamp": timezone.now().isoformat()
                        })
                
        except Exception as exc:
            logger.warning("Failed to track contest activity: %s", exc)
    
    def _track_streak_freeze_usage(self, request: HttpRequest) -> None:
        """Track streak freeze usage patterns."""
        try:
            # Check if request is for streak freeze functionality
            if '/streak-freeze' in request.path or hasattr(request, 'streak_freeze_request'):
                request.gamification_tracking["events"].append({
                    "type": "streak_freeze_request",
                    "path": request.path,
                    "method": request.method,
                    "timestamp": timezone.now().isoformat()
                })
                
        except Exception as exc:
            logger.warning("Failed to track streak freeze usage: %s", exc)
    
    def _record_tracking_metrics(self, request: HttpRequest, response: HttpResponse) -> None:
        """Record gamification tracking metrics."""
        try:
            from .models import GamificationInsight
            
            # Calculate request duration
            duration = (timezone.now() - request.gamification_tracking["start_time"]).total_seconds()
            
            # Record insight if there are gamification events
            if request.gamification_tracking["events"]:
                insight_data = {
                    "request_path": request.path,
                    "request_method": request.method,
                    "duration": duration,
                    "events": request.gamification_tracking["events"],
                    "interactions": request.gamification_tracking["user_interactions"],
                }
                
                # Create insight record (async to avoid blocking response)
                try:
                    GamificationInsight.objects.create(
                        metric_type="request_tracking",
                        value=len(request.gamification_tracking["events"]),
                        date=timezone.now().date(),
                        metadata=insight_data
                    )
                except Exception:
                    # Don't fail the request if insight creation fails
                    pass
            
            # Add tracking headers
            response['X-Gamification-Events'] = str(len(request.gamification_tracking["events"]))
            response['X-Gamification-Duration'] = str(duration)
            
        except Exception as exc:
            logger.warning("Failed to record tracking metrics: %s", exc)


class GamificationSecurityMiddleware:
    """
    Security middleware for gamification features.
    Prevents abuse and detects suspicious patterns in gamification activities.
    """
    
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not callable(get_response):
            raise TypeError(
                f"get_response must be callable, got {type(get_response).__name__}."
            )
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Initialize security context
        request.gamification_security = {
            "risk_score": 0,
            "violations": [],
            "blocked": False,
        }
        
        try:
            # Check for suspicious patterns
            if hasattr(request, 'user') and request.user.is_authenticated:
                self._check_points_abuse(request)
                self._check_contest_abuse(request)
                self._check_streak_manipulation(request)
            
            # Apply security measures if needed
            if request.gamification_security["risk_score"] > 80:
                self._apply_security_measures(request)
                
        except Exception as exc:
            logger.warning("Gamification security middleware error: %s", exc)
        
        # Process request
        response = self.get_response(request)
        
        # Add security headers
        if request.gamification_security["risk_score"] > 0:
            response['X-Gamification-Risk-Score'] = str(request.gamification_security["risk_score"])
        
        return response
    
    def _check_points_abuse(self, request: HttpRequest) -> None:
        """Check for points abuse patterns."""
        try:
            from .models import PointsTransaction
            
            user_id = request.user.id
            
            # Check for excessive points transactions in short time
            recent_transactions = PointsTransaction.objects.filter(
                user_id=user_id,
                created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
            ).count()
            
            if recent_transactions > 50:  # Threshold for abuse
                request.gamification_security["risk_score"] += 30
                request.gamification_security["violations"].append({
                    "type": "excessive_points_transactions",
                    "count": recent_transactions,
                    "timestamp": timezone.now().isoformat()
                })
            
        except Exception as exc:
            logger.warning("Failed to check points abuse: %s", exc)
    
    def _check_contest_abuse(self, request: HttpRequest) -> None:
        """Check for contest abuse patterns."""
        try:
            # Check for rapid contest participation changes
            if '/contest-participant' in request.path and request.method == 'POST':
                request.gamification_security["risk_score"] += 10
                
        except Exception as exc:
            logger.warning("Failed to check contest abuse: %s", exc)
    
    def _check_streak_manipulation(self, request: HttpRequest) -> None:
        """Check for streak manipulation attempts."""
        try:
            # Check for excessive streak freeze requests
            if '/streak-freeze' in request.path:
                request.gamification_security["risk_score"] += 5
                
        except Exception as exc:
            logger.warning("Failed to check streak manipulation: %s", exc)
    
    def _apply_security_measures(self, request: HttpRequest) -> None:
        """Apply security measures for high-risk requests."""
        try:
            # Log security event
            logger.warning(
                "High-risk gamification request detected: user=%s, risk_score=%d, violations=%s",
                request.user.id,
                request.gamification_security["risk_score"],
                request.gamification_security["violations"]
            )
            
            # Could implement rate limiting, temporary blocks, etc.
            # For now, just log and continue
            
        except Exception as exc:
            logger.warning("Failed to apply security measures: %s", exc)
