# api/admin_panel/endpoint.py
"""
Admin Panel Endpoint Registry & Discovery.
Maps all admin_panel API endpoints for documentation, monitoring, toggling.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class AdminEndpoint:
    """Represents a single admin API endpoint."""
    path: str
    method: str
    name: str
    description: str
    category: str
    requires_superadmin: bool = False
    is_bulk: bool = False
    is_realtime: bool = False
    throttle_scope: str = 'admin_user'
    cache_ttl: int = 0


# ==================== ALL ADMIN ENDPOINTS ====================
ADMIN_ENDPOINTS: List[AdminEndpoint] = [
    # Real-time Dashboard
    AdminEndpoint('/realtime-dashboard/live-kpis/', 'GET', 'live_kpis', 'Live KPI snapshot (30s cache)', 'dashboard', is_realtime=True, cache_ttl=30),
    AdminEndpoint('/realtime-dashboard/revenue-stream/', 'GET', 'revenue_stream', 'Per-minute revenue data', 'dashboard', is_realtime=True),
    AdminEndpoint('/realtime-dashboard/fraud-live/', 'GET', 'fraud_live', 'Last 10min fraud alerts', 'dashboard', is_realtime=True),
    AdminEndpoint('/realtime-dashboard/activity-feed/', 'GET', 'activity_feed', 'Last 50 admin actions', 'dashboard'),
    AdminEndpoint('/realtime-dashboard/integration-status/', 'GET', 'integration_status', 'All 50 apps health', 'dashboard'),
    AdminEndpoint('/realtime-dashboard/registration-pulse/', 'GET', 'registration_pulse', 'Per-minute registrations', 'dashboard'),
    # Cross-app actions
    AdminEndpoint('/cross-app/ban-user/', 'POST', 'ban_user', 'Ban user + freeze wallet + cancel payouts', 'users'),
    AdminEndpoint('/cross-app/bulk-ban/', 'POST', 'bulk_ban', 'Bulk ban up to 5000 users', 'users', is_bulk=True, throttle_scope='admin_bulk'),
    AdminEndpoint('/cross-app/approve-withdrawal/', 'POST', 'approve_withdrawal', 'Approve + notify user', 'payout'),
    AdminEndpoint('/cross-app/send-broadcast/', 'POST', 'send_broadcast', 'Send to all/filtered users', 'messaging'),
    AdminEndpoint('/cross-app/enable-maintenance/', 'POST', 'enable_maintenance', 'Enable maintenance mode system-wide', 'system', requires_superadmin=True),
    AdminEndpoint('/cross-app/sync-wallet/', 'POST', 'sync_wallet', 'Sync wallet from transactions', 'wallet'),
    AdminEndpoint('/cross-app/integration-health/', 'GET', 'integration_health', 'All apps health check', 'system'),
    # Settings
    AdminEndpoint('/settings/', 'GET', 'settings_list', 'System settings singleton', 'settings'),
    AdminEndpoint('/settings/public/', 'GET', 'settings_public', 'Public settings (no auth)', 'settings', cache_ttl=3600),
    AdminEndpoint('/settings/app-config/', 'GET', 'app_config', 'Mobile app config', 'settings', cache_ttl=300),
    AdminEndpoint('/settings/payment-gateways/', 'GET', 'gateways', 'bKash/Nagad/Stripe status', 'settings'),
    AdminEndpoint('/settings/referral/', 'GET', 'referral_settings', 'Referral commission config', 'settings'),
    AdminEndpoint('/settings/reward-points/', 'GET', 'reward_points', 'Points per action config', 'settings'),
    AdminEndpoint('/settings/withdrawal/', 'GET', 'withdrawal_settings', 'Withdrawal rules', 'settings'),
    AdminEndpoint('/settings/toggle-maintenance/', 'POST', 'toggle_maintenance', 'Toggle maintenance mode', 'settings', requires_superadmin=True),
    AdminEndpoint('/settings/clear-cache/', 'POST', 'clear_cache', 'Clear system cache', 'settings', requires_superadmin=True),
    # Payout
    AdminEndpoint('/payout-admin/pending/', 'GET', 'pending_withdrawals', 'Pending withdrawal requests', 'payout'),
    AdminEndpoint('/payout-admin/approve/', 'POST', 'approve_withdrawal', 'Approve single withdrawal', 'payout'),
    AdminEndpoint('/payout-admin/bulk-approve/', 'POST', 'bulk_approve', 'Bulk approve withdrawals', 'payout', is_bulk=True),
    AdminEndpoint('/payout-admin/reject/', 'POST', 'reject_withdrawal', 'Reject + refund to wallet', 'payout'),
    AdminEndpoint('/payout-admin/gateway-stats/', 'GET', 'gateway_stats', 'bKash/Nagad/Rocket breakdown', 'payout'),
    # Fraud
    AdminEndpoint('/fraud-control/rules/', 'GET', 'fraud_rules', 'All fraud detection rules', 'fraud'),
    AdminEndpoint('/fraud-control/attempts/', 'GET', 'recent_fraud_attempts', 'Recent fraud events', 'fraud'),
    AdminEndpoint('/fraud-control/block-ip/', 'POST', 'block_ip', 'Block an IP address', 'fraud'),
    AdminEndpoint('/fraud-control/unblock-ip/', 'POST', 'unblock_ip', 'Remove IP from blocklist', 'fraud'),
    AdminEndpoint('/fraud-control/proxy-stats/', 'GET', 'proxy_stats', 'VPN/Proxy/TOR statistics', 'fraud'),
    AdminEndpoint('/fraud-control/check-user-risk/', 'POST', 'check_user_risk', 'Real-time user risk score', 'fraud'),
    # Users
    AdminEndpoint('/user-management/search/', 'GET', 'user_search', 'Search by username/email/phone/IP', 'users'),
    AdminEndpoint('/user-management/user-detail/', 'GET', 'user_detail', '360° user view', 'users'),
    AdminEndpoint('/user-management/ban-user/', 'POST', 'ban_user', 'Ban + freeze wallet', 'users'),
    AdminEndpoint('/user-management/unban-user/', 'POST', 'unban_user', 'Restore access', 'users'),
    AdminEndpoint('/user-management/user-stats-overview/', 'GET', 'user_stats', 'Registration stats, countries', 'users', cache_ttl=300),
    AdminEndpoint('/user-management/suspicious-users/', 'GET', 'suspicious_users', 'Users with fraud flags', 'users'),
    # WebSocket
    AdminEndpoint('ws://domain/ws/admin/dashboard/', 'WS', 'ws_dashboard', 'Live dashboard WebSocket', 'realtime', is_realtime=True),
    AdminEndpoint('ws://domain/ws/admin/fraud/alerts/', 'WS', 'ws_fraud', 'Live fraud alerts WebSocket', 'realtime', is_realtime=True),
    AdminEndpoint('ws://domain/ws/admin/health/', 'WS', 'ws_health', 'System health WebSocket', 'realtime', is_realtime=True),
]


def get_endpoints_by_category() -> Dict[str, List[AdminEndpoint]]:
    result = {}
    for ep in ADMIN_ENDPOINTS:
        result.setdefault(ep.category, []).append(ep)
    return result


def get_endpoint_count() -> Dict[str, int]:
    cats = get_endpoints_by_category()
    return {cat: len(eps) for cat, eps in cats.items()}


def get_total_endpoint_count() -> int:
    return len(ADMIN_ENDPOINTS)