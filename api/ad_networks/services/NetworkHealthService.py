"""
api/ad_networks/services/NetworkHealthService.py
Service for pinging networks and updating health status
SaaS-ready with tenant support
"""

import logging
import json
import requests
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from api.ad_networks.models import (
    AdNetwork, NetworkHealthCheck, NetworkAPILog
)
from api.ad_networks.choices import NetworkStatus
from api.ad_networks.constants import (
    API_TIMEOUT_SECONDS,
    NETWORK_HEALTH_CHECK_INTERVAL,
    CACHE_KEY_PATTERNS
)

logger = logging.getLogger(__name__)


class NetworkHealthService:
    """
    Service for monitoring network health and availability
    """
    
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.session = requests.Session()
        self.session.timeout = API_TIMEOUT_SECONDS
        
        # Setup session headers
        self.session.headers.update({
            'User-Agent': 'AdNetworks-HealthCheck/1.0',
            'Accept': 'application/json'
        })
    
    def check_all_networks(self) -> Dict:
        """
        Check health of all active networks
        """
        try:
            # Get all active networks
            networks = AdNetwork.objects.filter(is_active=True)
            if self.tenant_id:
                networks = networks.filter(tenant_id=self.tenant_id)
            
            total_networks = networks.count()
            healthy_networks = 0
            unhealthy_networks = 0
            results = []
            
            # Check networks in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_network = {
                    executor.submit(self.check_single_network, network): network
                    for network in networks
                }
                
                for future in as_completed(future_to_network):
                    network = future_to_network[future]
                    try:
                        result = future.result(timeout=API_TIMEOUT_SECONDS + 10)
                        results.append({
                            'network_id': network.id,
                            'network_name': network.name,
                            'network_type': network.network_type,
                            'result': result
                        })
                        
                        if result['is_healthy']:
                            healthy_networks += 1
                        else:
                            unhealthy_networks += 1
                            
                    except Exception as e:
                        logger.error(f"Health check failed for {network.name}: {str(e)}")
                        results.append({
                            'network_id': network.id,
                            'network_name': network.name,
                            'network_type': network.network_type,
                            'result': {
                                'is_healthy': False,
                                'error': str(e),
                                'response_time_ms': 0
                            }
                        })
                        unhealthy_networks += 1
            
            # Calculate overall health
            overall_health = (healthy_networks / total_networks * 100) if total_networks > 0 else 0
            
            # Update cache
            cache.set(
                f'network_health_overall_{self.tenant_id or "default"}',
                {
                    'healthy_networks': healthy_networks,
                    'unhealthy_networks': unhealthy_networks,
                    'total_networks': total_networks,
                    'overall_health': overall_health,
                    'last_check': timezone.now().isoformat()
                },
                timeout=NETWORK_HEALTH_CHECK_INTERVAL
            )
            
            logger.info(f"Network health check completed: {healthy_networks}/{total_networks} healthy")
            
            return {
                'success': True,
                'total_networks': total_networks,
                'healthy_networks': healthy_networks,
                'unhealthy_networks': unhealthy_networks,
                'overall_health': round(overall_health, 2),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Network health check failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def check_single_network(self, network: AdNetwork) -> Dict:
        """
        Check health of a single network
        """
        try:
            # Get health check URL
            health_url = self._get_health_check_url(network)
            if not health_url:
                return {
                    'is_healthy': True,
                    'error': 'No health check URL configured',
                    'response_time_ms': 0
                }
            
            # Setup authentication
            headers = self._get_auth_headers(network)
            
            # Make health check request
            start_time = timezone.now()
            response = self.session.get(
                health_url,
                headers=headers,
                timeout=API_TIMEOUT_SECONDS
            )
            end_time = timezone.now()
            
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Determine health status
            is_healthy = response.status_code == 200
            
            # Create health check record
            NetworkHealthCheck.objects.create(
                network=network,
                is_healthy=is_healthy,
                check_type='api_call',
                endpoint_checked=health_url,
                response_time_ms=response_time_ms,
                status_code=response.status_code,
                error=None if is_healthy else f"HTTP {response.status_code}",
                tenant_id=self.tenant_id
            )
            
            # Log API call
            NetworkAPILog.objects.create(
                network=network,
                endpoint='health_check',
                method='GET',
                request_data={},
                response_data={'status_code': response.status_code},
                status_code=response.status_code,
                is_success=is_healthy,
                latency_ms=response_time_ms,
                tenant_id=self.tenant_id
            )
            
            # Update network status if needed
            if not is_healthy:
                self._update_network_status(network, NetworkStatus.MAINTENANCE)
            else:
                self._update_network_status(network, NetworkStatus.ACTIVE)
            
            result = {
                'is_healthy': is_healthy,
                'response_time_ms': response_time_ms,
                'status_code': response.status_code,
                'endpoint': health_url
            }
            
            if not is_healthy:
                result['error'] = f"HTTP {response.status_code}"
            
            return result
            
        except requests.exceptions.Timeout:
            error_msg = f"Health check timeout for {network.name}"
            logger.warning(error_msg)
            
            # Record timeout
            self._record_health_check(network, False, 0, error_msg)
            
            return {
                'is_healthy': False,
                'error': 'Request timeout',
                'response_time_ms': API_TIMEOUT_SECONDS * 1000
            }
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error for {network.name}: {str(e)}"
            logger.warning(error_msg)
            
            # Record connection error
            self._record_health_check(network, False, 0, error_msg)
            
            return {
                'is_healthy': False,
                'error': 'Connection error',
                'response_time_ms': 0
            }
            
        except Exception as e:
            error_msg = f"Health check error for {network.name}: {str(e)}"
            logger.error(error_msg)
            
            # Record general error
            self._record_health_check(network, False, 0, error_msg)
            
            return {
                'is_healthy': False,
                'error': str(e),
                'response_time_ms': 0
            }
    
    def check_network_endpoints(self, network: AdNetwork) -> Dict:
        """
        Check multiple endpoints of a network
        """
        try:
            endpoints = self._get_network_endpoints(network)
            results = []
            
            for endpoint in endpoints:
                try:
                    start_time = timezone.now()
                    response = self.session.get(
                        endpoint['url'],
                        headers=self._get_auth_headers(network),
                        timeout=API_TIMEOUT_SECONDS
                    )
                    end_time = timezone.now()
                    
                    response_time_ms = int((end_time - start_time).total_seconds() * 1000)
                    
                    results.append({
                        'endpoint': endpoint['name'],
                        'url': endpoint['url'],
                        'status_code': response.status_code,
                        'response_time_ms': response_time_ms,
                        'is_healthy': response.status_code == 200,
                        'error': None if response.status_code == 200 else f"HTTP {response.status_code}"
                    })
                    
                except Exception as e:
                    results.append({
                        'endpoint': endpoint['name'],
                        'url': endpoint['url'],
                        'status_code': 0,
                        'response_time_ms': 0,
                        'is_healthy': False,
                        'error': str(e)
                    })
            
            # Calculate overall endpoint health
            healthy_endpoints = sum(1 for r in results if r['is_healthy'])
            total_endpoints = len(results)
            overall_health = (healthy_endpoints / total_endpoints * 100) if total_endpoints > 0 else 0
            
            return {
                'success': True,
                'network_id': network.id,
                'network_name': network.name,
                'overall_health': round(overall_health, 2),
                'healthy_endpoints': healthy_endpoints,
                'total_endpoints': total_endpoints,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Endpoint check failed for {network.name}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def get_network_health_history(self, network_id: int, days: int = 7) -> Dict:
        """
        Get health history for a network
        """
        try:
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Get health checks
            health_checks = NetworkHealthCheck.objects.filter(
                network_id=network_id,
                checked_at__gte=start_date,
                checked_at__lte=end_date
            ).order_by('-checked_at')
            
            # Calculate statistics
            total_checks = health_checks.count()
            healthy_checks = health_checks.filter(is_healthy=True).count()
            avg_response_time = health_checks.aggregate(
                avg_response_time=Avg('response_time_ms')
            )['avg_response_time'] or 0
            
            health_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
            
            # Prepare timeline data
            timeline = []
            for check in health_checks[:100]:  # Last 100 checks
                timeline.append({
                    'timestamp': check.checked_at,
                    'is_healthy': check.is_healthy,
                    'response_time_ms': check.response_time_ms,
                    'error': check.error
                })
            
            return {
                'success': True,
                'network_id': network_id,
                'period_days': days,
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'unhealthy_checks': total_checks - healthy_checks,
                'health_percentage': round(health_percentage, 2),
                'avg_response_time_ms': round(avg_response_time, 2),
                'timeline': timeline
            }
            
        except Exception as e:
            logger.error(f"Failed to get health history: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_health_summary(self, tenant_id: str = None) -> Dict:
        """
        Get overall health summary
        """
        try:
            # Get cache first
            cache_key = f'network_health_overall_{tenant_id or "default"}'
            cached_summary = cache.get(cache_key)
            
            if cached_summary:
                return {
                    'success': True,
                    'cached': True,
                    **cached_summary
                }
            
            # Get all networks
            networks = AdNetwork.objects.filter(is_active=True)
            if tenant_id:
                networks = networks.filter(tenant_id=tenant_id)
            
            # Calculate summary
            total_networks = networks.count()
            active_networks = networks.filter(status=NetworkStatus.ACTIVE).count()
            maintenance_networks = networks.filter(status=NetworkStatus.MAINTENANCE).count()
            suspended_networks = networks.filter(status=NetworkStatus.SUSPENDED).count()
            
            # Get recent health checks
            recent_checks = NetworkHealthCheck.objects.filter(
                checked_at__gte=timezone.now() - timedelta(hours=24)
            )
            
            if tenant_id:
                recent_checks = recent_checks.filter(network__tenant_id=tenant_id)
            
            recent_healthy = recent_checks.filter(is_healthy=True).count()
            recent_total = recent_checks.count()
            recent_health_percentage = (recent_healthy / recent_total * 100) if recent_total > 0 else 0
            
            summary = {
                'total_networks': total_networks,
                'active_networks': active_networks,
                'maintenance_networks': maintenance_networks,
                'suspended_networks': suspended_networks,
                'recent_health_percentage': round(recent_health_percentage, 2),
                'recent_total_checks': recent_total,
                'recent_healthy_checks': recent_healthy,
                'last_updated': timezone.now().isoformat()
            }
            
            # Cache summary
            cache.set(cache_key, summary, timeout=NETWORK_HEALTH_CHECK_INTERVAL)
            
            return {
                'success': True,
                'cached': False,
                **summary
            }
            
        except Exception as e:
            logger.error(f"Failed to get health summary: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def schedule_health_checks(self) -> Dict:
        """
        Schedule periodic health checks
        """
        try:
            # Get networks that need health checks
            check_threshold = timezone.now() - timedelta(minutes=NETWORK_HEALTH_CHECK_INTERVAL // 60)
            
            networks_to_check = AdNetwork.objects.filter(
                Q(last_health_check__isnull=True) | Q(last_health_check__lt=check_threshold),
                is_active=True
            )
            
            if self.tenant_id:
                networks_to_check = networks_to_check.filter(tenant_id=self.tenant_id)
            
            networks_checked = 0
            
            for network in networks_to_check:
                try:
                    result = self.check_single_network(network)
                    if result['is_healthy']:
                        networks_checked += 1
                except Exception as e:
                    logger.error(f"Scheduled health check failed for {network.name}: {str(e)}")
            
            logger.info(f"Scheduled health checks completed: {networks_checked} networks")
            
            return {
                'success': True,
                'networks_checked': networks_checked,
                'total_scheduled': networks_to_check.count()
            }
            
        except Exception as e:
            logger.error(f"Scheduled health checks failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_health_check_url(self, network: AdNetwork) -> Optional[str]:
        """
        Get health check URL for network
        """
        if not network.base_url:
            return None
        
        # Network-specific health check URLs
        health_patterns = {
            'adscend': f'{network.base_url}/v1/ping',
            'offertoro': f'{network.base_url}/v1/ping',
            'adgem': f'{network.base_url}/v1/ping',
            'ayetstudios': f'{network.base_url}/v1/ping',
            'pollfish': f'{network.base_url}/v1/ping',
            'cpxresearch': f'{network.base_url}/v1/ping',
            'bitlabs': f'{network.base_url}/v1/ping',
            'inbrain': f'{network.base_url}/v1/ping',
            'theoremreach': f'{network.base_url}/v1/ping',
            'your_surveys': f'{network.base_url}/v1/ping',
            'toluna': f'{network.base_url}/v1/ping',
            'swagbucks': f'{network.base_url}/v1/ping',
            'prizerebel': f'{network.base_url}/v1/ping',
        }
        
        return health_patterns.get(network.network_type)
    
    def _get_network_endpoints(self, network: AdNetwork) -> List[Dict]:
        """
        Get endpoints to check for a network
        """
        if not network.base_url:
            return []
        
        base_url = network.base_url.rstrip('/')
        
        # Common endpoints to check
        endpoints = [
            {'name': 'health', 'url': f'{base_url}/v1/ping'},
            {'name': 'offers', 'url': f'{base_url}/v1/offers'},
            {'name': 'stats', 'url': f'{base_url}/v1/stats'},
            {'name': 'auth', 'url': f'{base_url}/v1/auth'},
        ]
        
        # Network-specific endpoints
        network_endpoints = {
            'adscend': [
                {'name': 'publishers', 'url': f'{base_url}/v1/publishers'},
                {'name': 'reports', 'url': f'{base_url}/v1/reports'},
            ],
            'offertoro': [
                {'name': 'campaigns', 'url': f'{base_url}/v1/campaigns'},
                {'name': 'payments', 'url': f'{base_url}/v1/payments'},
            ],
            'pollfish': [
                {'name': 'surveys', 'url': f'{base_url}/v1/surveys'},
                {'name': 'respondents', 'url': f'{base_url}/v1/respondents'},
            ],
        }
        
        if network.network_type in network_endpoints:
            endpoints.extend(network_endpoints[network.network_type])
        
        return endpoints
    
    def _get_auth_headers(self, network: AdNetwork) -> Dict:
        """
        Get authentication headers for network
        """
        headers = {}
        
        if network.api_key:
            headers['X-API-Key'] = network.api_key
        
        if network.postback_key:
            headers['Authorization'] = f'Bearer {network.postback_key}'
        
        return headers
    
    def _record_health_check(self, network: AdNetwork, is_healthy: bool, 
                           response_time_ms: int, error: str = None):
        """
        Record health check result
        """
        try:
            NetworkHealthCheck.objects.create(
                network=network,
                is_healthy=is_healthy,
                check_type='api_call',
                endpoint_checked=self._get_health_check_url(network),
                response_time_ms=response_time_ms,
                error=error,
                tenant_id=self.tenant_id
            )
            
            # Update network last health check
            network.last_health_check = timezone.now()
            network.save(update_fields=['last_health_check'])
            
        except Exception as e:
            logger.error(f"Failed to record health check: {str(e)}")
    
    def _update_network_status(self, network: AdNetwork, status: str):
        """
        Update network status based on health
        """
        try:
            # Only update if status is different
            if network.status != status:
                network.status = status
                network.save(update_fields=['status'])
                
                logger.info(f"Updated network status: {network.name} -> {status}")
                
        except Exception as e:
            logger.error(f"Failed to update network status: {str(e)}")
    
    @classmethod
    def get_network_uptime(cls, network_id: int, days: int = 30) -> Dict:
        """
        Calculate network uptime percentage
        """
        try:
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Get health checks
            health_checks = NetworkHealthCheck.objects.filter(
                network_id=network_id,
                checked_at__gte=start_date,
                checked_at__lte=end_date
            )
            
            total_checks = health_checks.count()
            healthy_checks = health_checks.filter(is_healthy=True).count()
            
            uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
            
            # Calculate downtime periods
            downtime_periods = []
            current_downtime = None
            
            for check in health_checks.order_by('checked_at'):
                if not check.is_healthy:
                    if current_downtime is None:
                        current_downtime = {
                            'start': check.checked_at,
                            'end': None,
                            'duration_minutes': 0
                        }
                else:
                    if current_downtime is not None:
                        current_downtime['end'] = check.checked_at
                        current_downtime['duration_minutes'] = int(
                            (current_downtime['end'] - current_downtime['start']).total_seconds() / 60
                        )
                        downtime_periods.append(current_downtime)
                        current_downtime = None
            
            # Close any open downtime period
            if current_downtime is not None:
                current_downtime['end'] = end_date
                current_downtime['duration_minutes'] = int(
                    (current_downtime['end'] - current_downtime['start']).total_seconds() / 60
                )
                downtime_periods.append(current_downtime)
            
            total_downtime_minutes = sum(period['duration_minutes'] for period in downtime_periods)
            
            return {
                'success': True,
                'network_id': network_id,
                'period_days': days,
                'uptime_percentage': round(uptime_percentage, 2),
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'unhealthy_checks': total_checks - healthy_checks,
                'total_downtime_minutes': total_downtime_minutes,
                'total_downtime_hours': round(total_downtime_minutes / 60, 2),
                'downtime_periods': downtime_periods
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate uptime: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def get_health_alerts(cls, tenant_id: str = None) -> Dict:
        """
        Get health alerts for networks
        """
        try:
            alerts = []
            
            # Get networks with recent issues
            recent_threshold = timezone.now() - timedelta(hours=1)
            
            problematic_networks = NetworkHealthCheck.objects.filter(
                checked_at__gte=recent_threshold,
                is_healthy=False
            ).values('network_id').distinct()
            
            if tenant_id:
                problematic_networks = problematic_networks.filter(
                    network__tenant_id=tenant_id
                )
            
            # Get network details
            network_ids = [item['network_id'] for item in problematic_networks]
            networks = AdNetwork.objects.filter(id__in=network_ids)
            
            for network in networks:
                # Get recent failed checks
                failed_checks = NetworkHealthCheck.objects.filter(
                    network=network,
                    checked_at__gte=recent_threshold,
                    is_healthy=False
                ).order_by('-checked_at')[:5]
                
                alerts.append({
                    'network_id': network.id,
                    'network_name': network.name,
                    'network_type': network.network_type,
                    'alert_type': 'health_check_failure',
                    'severity': 'high' if failed_checks.count() >= 3 else 'medium',
                    'message': f"{failed_checks.count()} failed health checks in last hour",
                    'last_failure': failed_checks.first().checked_at if failed_checks.exists() else None,
                    'consecutive_failures': failed_checks.count()
                })
            
            return {
                'success': True,
                'total_alerts': len(alerts),
                'alerts': alerts
            }
            
        except Exception as e:
            logger.error(f"Failed to get health alerts: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'alerts': []
            }
