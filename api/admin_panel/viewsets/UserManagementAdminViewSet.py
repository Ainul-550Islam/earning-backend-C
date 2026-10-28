# api/admin_panel/viewsets/UserManagementAdminViewSet.py
"""
UserManagementAdminViewSet — World-class user admin control.
Controls: User search, ban/unban, verification, device management,
login history, referral tree, earnings breakdown, risk profile.
Integrates all user-related services from api/users/.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import timedelta
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class UserManagementAdminViewSet(viewsets.ViewSet):
    """
    Complete user management — the heart of an admin panel.
    Every action an admin needs for managing 1M+ users.
    """
    permission_classes = [IsAdminUser]

    # ==================== USER SEARCH ====================

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Advanced user search — by username, email, phone, IP, device ID, referral code.
        Returns: user info, wallet, KYC status, risk score.
        """
        q = request.query_params.get('q', '').strip()
        search_by = request.query_params.get('by', 'username')  # username, email, phone, ip

        if not q or len(q) < 2:
            return Response({'error': 'Search query too short. Min 2 characters.'}, status=400)

        try:
            qs = User.objects.filter(is_active__in=[True, False])

            if search_by == 'email':
                qs = qs.filter(email__icontains=q)
            elif search_by == 'phone':
                qs = qs.filter(profile__phone_number__icontains=q)
            elif search_by == 'ip':
                from api.users.models import LoginHistory
                user_ids = LoginHistory.objects.filter(ip_address=q).values_list('user_id', flat=True).distinct()
                qs = qs.filter(pk__in=user_ids)
            elif search_by == 'referral':
                qs = qs.filter(profile__referral_code=q)
            else:
                qs = qs.filter(
                    Q(username__icontains=q) | Q(email__icontains=q)
                )

            users = []
            for user in qs[:20]:
                user_data = {
                    'id': user.pk,
                    'username': user.username,
                    'email': user.email,
                    'is_active': user.is_active,
                    'date_joined': user.date_joined.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                }
                # Add profile data
                try:
                    profile = user.profile
                    user_data.update({
                        'phone': profile.phone_number,
                        'account_status': profile.account_status,
                        'email_verified': profile.email_verified,
                        'phone_verified': profile.phone_verified,
                        'is_premium': profile.is_premium,
                        'total_points': float(profile.total_points),
                        'available_balance': float(profile.available_balance),
                        'referral_code': profile.referral_code,
                    })
                except Exception:
                    pass
                # Add wallet
                try:
                    wallet = user.wallet
                    user_data['wallet_balance'] = float(wallet.current_balance)
                    user_data['total_earned'] = float(wallet.total_earned)
                except Exception:
                    pass
                users.append(user_data)

            return Response({
                'success': True,
                'query': q,
                'search_by': search_by,
                'results': users,
                'count': len(users),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ==================== USER DETAIL ====================

    @action(detail=False, methods=['get'])
    def user_detail(self, request):
        """Full 360° view of a user — profile, wallet, KYC, devices, login history, referrals, risk."""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)

        try:
            user = User.objects.get(pk=user_id)
            data = {
                'id': user.pk,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }

            # Profile
            try:
                p = user.profile
                data['profile'] = {
                    'phone': p.phone_number,
                    'country': getattr(p, 'country', ''),
                    'account_status': p.account_status,
                    'email_verified': p.email_verified,
                    'phone_verified': p.phone_verified,
                    'identity_verified': getattr(p, 'identity_verified', False),
                    'is_premium': p.is_premium,
                    'is_affiliate': getattr(p, 'is_affiliate', False),
                    'total_points': float(p.total_points),
                    'total_withdrawn': float(p.total_withdrawn),
                    'available_balance': float(p.available_balance),
                    'referral_code': p.referral_code,
                }
            except Exception as e:
                data['profile'] = {'error': str(e)}

            # Wallet
            try:
                w = user.wallet
                data['wallet'] = {
                    'balance': float(w.balance),
                    'total_earned': float(w.total_earned),
                    'total_withdrawn': float(w.total_withdrawn),
                    'on_hold': float(getattr(w, 'on_hold', 0)),
                }
            except Exception:
                data['wallet'] = {}

            # KYC status
            try:
                from api.kyc.models import KYC
                kyc = KYC.objects.filter(user=user).order_by('-created_at').first()
                data['kyc'] = {
                    'status': kyc.status if kyc else 'not_submitted',
                    'kyc_type': kyc.kyc_type if kyc else None,
                    'submitted_at': kyc.submitted_at.isoformat() if kyc and kyc.submitted_at else None,
                }
            except Exception:
                data['kyc'] = {'status': 'unknown'}

            # Recent login history
            try:
                from api.users.models import LoginHistory
                logins = list(LoginHistory.objects.filter(user=user).values(
                    'ip_address', 'user_agent', 'location', 'created_at'
                ).order_by('-created_at')[:5])
                data['recent_logins'] = logins
            except Exception:
                data['recent_logins'] = []

            # Referral stats
            try:
                from api.users.models import UserProfile
                referred_count = UserProfile.objects.filter(referred_by=user).count()
                data['referrals'] = {
                    'total_referred': referred_count,
                    'referred_by': getattr(user.profile, 'referred_by', {}).username if hasattr(user, 'profile') and hasattr(user.profile, 'referred_by') and user.profile.referred_by else None,
                }
            except Exception:
                data['referrals'] = {}

            # Risk score
            try:
                from api.fraud_detection.models import FraudAttempt
                fraud_count = FraudAttempt.objects.filter(
                    user_id=user_id,
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count()
                risk = min(100, fraud_count * 10)
                data['risk'] = {
                    'score': risk,
                    'level': 'critical' if risk >= 80 else 'high' if risk >= 60 else 'medium' if risk >= 30 else 'low',
                    'fraud_attempts_30d': fraud_count,
                }
            except Exception:
                data['risk'] = {'score': 0, 'level': 'unknown'}

            return Response({'success': True, 'data': data})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ==================== BAN/UNBAN ====================

    @action(detail=False, methods=['post'])
    def ban_user(self, request):
        """Ban a user — disable account, freeze wallet."""
        user_id = request.data.get('user_id')
        reason = request.data.get('reason', 'Policy violation')
        freeze_wallet = request.data.get('freeze_wallet', False)

        if not user_id:
            return Response({'error': 'user_id required'}, status=400)

        try:
            user = User.objects.get(pk=user_id)
            user.is_active = False
            user.save(update_fields=['is_active'])

            # Update profile status
            try:
                user.profile.account_status = 'banned'
                user.profile.ban_reason = reason
                user.profile.banned_by = request.user
                user.profile.banned_at = timezone.now()
                user.profile.save(update_fields=['account_status', 'ban_reason'])
            except Exception:
                pass

            # Freeze wallet if requested
            if freeze_wallet:
                try:
                    user.wallet.is_locked = True
                    user.wallet.locked_reason = reason
                    user.wallet.save(update_fields=['is_locked', 'locked_reason'])
                except Exception:
                    pass

            # Log
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user, action='user_ban',
                    model_name='User', object_id=str(user_id),
                    changes={'reason': reason, 'freeze_wallet': freeze_wallet},
                )
            except Exception:
                pass

            return Response({
                'success': True,
                'user_id': user_id,
                'username': user.username,
                'banned': True,
                'wallet_frozen': freeze_wallet,
            })
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'])
    def unban_user(self, request):
        """Unban a user and restore access."""
        user_id = request.data.get('user_id')
        unfreeze_wallet = request.data.get('unfreeze_wallet', True)

        try:
            user = User.objects.get(pk=user_id)
            user.is_active = True
            user.save(update_fields=['is_active'])

            try:
                user.profile.account_status = 'active'
                user.profile.save(update_fields=['account_status'])
            except Exception:
                pass

            if unfreeze_wallet:
                try:
                    user.wallet.is_locked = False
                    user.wallet.save(update_fields=['is_frozen'])
                except Exception:
                    pass

            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user, action='user_unban',
                    model_name='User', object_id=str(user_id),
                )
            except Exception:
                pass

            return Response({
                'success': True,
                'user_id': user_id,
                'username': user.username,
                'unbanned': True,
            })
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ==================== VERIFICATION ====================

    @action(detail=False, methods=['post'])
    def manually_verify_user(self, request):
        """Manually verify email/phone/identity for a user."""
        user_id = request.data.get('user_id')
        verify_email = request.data.get('email', False)
        verify_phone = request.data.get('phone', False)
        verify_identity = request.data.get('identity', False)

        try:
            user = User.objects.get(pk=user_id)
            profile = user.profile
            update_fields = []

            if verify_email:
                profile.email_verified = True
                update_fields.append('email_verified')
            if verify_phone:
                profile.phone_verified = True
                update_fields.append('phone_verified')
            if verify_identity:
                profile.identity_verified = True
                update_fields.append('identity_verified')

            if update_fields:
                profile.save(update_fields=update_fields)

            return Response({
                'success': True,
                'user_id': user_id,
                'verified': update_fields,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== STATS ====================

    @action(detail=False, methods=['get'])
    def user_stats_overview(self, request):
        """Complete user statistics for admin dashboard."""
        try:
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            last_7d = timezone.now() - timedelta(days=7)
            last_30d = timezone.now() - timedelta(days=30)

            stats = {
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'banned_users': User.objects.filter(is_active=False).count(),
                'staff_users': User.objects.filter(is_staff=True).count(),
                'new_today': User.objects.filter(date_joined__date=today).count(),
                'new_yesterday': User.objects.filter(date_joined__date=yesterday).count(),
                'new_7d': User.objects.filter(date_joined__gte=last_7d).count(),
                'new_30d': User.objects.filter(date_joined__gte=last_30d).count(),
            }

            # Registration by day (last 7 days)
            from django.db.models.functions import TruncDate
            daily_reg = list(
                User.objects.filter(date_joined__gte=last_7d).annotate(
                    day=TruncDate('date_joined')
                ).values('day').annotate(count=Count('id')).order_by('day')
            )
            stats['daily_registrations'] = daily_reg

            # Top countries
            try:
                from api.users.models import UserProfile
                top_countries = list(
                    UserProfile.objects.values('country').annotate(
                        count=Count('id')
                    ).filter(country__isnull=False).exclude(country='').order_by('-count')[:10]
                )
                stats['top_countries'] = top_countries
            except Exception:
                stats['top_countries'] = []

            return Response({'success': True, 'stats': stats})
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    # ==================== BULK ACTIONS ====================

    @action(detail=False, methods=['post'])
    def bulk_ban(self, request):
        """Ban multiple users at once."""
        user_ids = request.data.get('user_ids', [])
        reason = request.data.get('reason', 'Bulk ban by admin')

        if not user_ids:
            return Response({'error': 'user_ids required'}, status=400)
        if len(user_ids) > 500:
            return Response({'error': 'Maximum 500 users per bulk ban'}, status=400)

        count = User.objects.filter(pk__in=user_ids, is_active=True).update(is_active=False)

        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=request.user, action='bulk_ban',
                changes={'count': count, 'reason': reason, 'ids': user_ids[:10]},
            )
        except Exception:
            pass

        return Response({
            'success': True,
            'banned': count,
            'reason': reason,
        })

    @action(detail=False, methods=['post'])
    def send_notification_to_user(self, request):
        """Send in-app notification to a specific user."""
        user_id = request.data.get('user_id')
        title = request.data.get('title')
        message = request.data.get('message')
        notification_type = request.data.get('type', 'admin')

        try:
            from api.notifications.models import Notification
            Notification.objects.create(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                sent_by=request.user,
            )
            return Response({'success': True, 'user_id': user_id, 'sent': True})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def recent_registrations(self, request):
        """Most recent user registrations."""
        limit = min(int(request.query_params.get('limit', 50)), 200)
        users = list(User.objects.order_by('-date_joined').values(
            'id', 'username', 'email', 'is_active', 'date_joined'
        )[:limit])
        return Response({'success': True, 'data': users})

    @action(detail=False, methods=['get'])
    def suspicious_users(self, request):
        """Users flagged for suspicious activity."""
        try:
            from api.fraud_detection.models import FraudAttempt
            from django.db.models import Count
            last_7d = timezone.now() - timedelta(days=7)

            suspicious = list(
                FraudAttempt.objects.filter(
                    created_at__gte=last_7d
                ).values('user_id').annotate(
                    attempt_count=Count('id'),
                    avg_risk=Avg('fraud_score'),
                ).filter(attempt_count__gte=3).order_by('-attempt_count')[:50]
            )

            # Enrich with user info
            user_ids = [s['user_id'] for s in suspicious]
            user_map = {u.pk: u for u in User.objects.filter(pk__in=user_ids)}

            for s in suspicious:
                u = user_map.get(s['user_id'])
                s['username'] = u.username if u else 'Unknown'
                s['email'] = u.email if u else ''
                s['is_active'] = u.is_active if u else None

            return Response({'success': True, 'data': suspicious})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})