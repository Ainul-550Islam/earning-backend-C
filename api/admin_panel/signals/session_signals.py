# api/admin_panel/signals/session_signals.py
"""Signals: on Django login/logout → track AdminSession."""
import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def on_admin_login(sender, request, user, **kwargs):
    """Create/update AdminSession on admin login."""
    if not (user.is_staff or user.is_superuser):
        return
    try:
        from ..models.activity import AdminSession, AdminActivity
        from ..utils import get_client_ip, get_user_agent

        ip = get_client_ip(request)
        ua = get_user_agent(request)
        session_key = request.session.session_key or ''

        if session_key:
            AdminSession.objects.update_or_create(
                user=user,
                session_key=session_key,
                defaults={
                    'ip': ip,
                    'user_agent': ua,
                    'started_at': timezone.now(),
                    'last_seen': timezone.now(),
                    'is_active': True,
                    'status': 'active',
                }
            )

        # Log login activity
        AdminActivity.log(
            actor=user,
            action='admin_login',
            ip=ip,
            user_agent=ua,
            method='POST',
            path=request.path if request else '/admin/',
            status='success',
        )
        logger.info(f"Admin login: {user.username} from {ip}")
    except Exception as e:
        logger.debug(f"AdminSession login tracking error: {e}")


@receiver(user_logged_out)
def on_admin_logout(sender, request, user, **kwargs):
    """Mark AdminSession as logged out on logout."""
    if not user or not (user.is_staff or user.is_superuser):
        return
    try:
        from ..models.activity import AdminSession, AdminActivity
        from ..utils import get_client_ip, get_user_agent

        ip = get_client_ip(request) if request else ''
        ua = get_user_agent(request) if request else ''
        session_key = request.session.session_key if request else ''

        if session_key:
            AdminSession.objects.filter(
                user=user,
                session_key=session_key,
                is_active=True,
            ).update(
                is_active=False,
                status='logged_out',
                ended_at=timezone.now(),
            )

        AdminActivity.log(
            actor=user,
            action='admin_logout',
            ip=ip,
            user_agent=ua,
            method='POST',
            path='/admin/logout/',
            status='success',
        )
        logger.info(f"Admin logout: {user.username}")
    except Exception as e:
        logger.debug(f"AdminSession logout tracking error: {e}")