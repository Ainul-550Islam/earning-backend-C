# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from django.contrib.auth import authenticate
from django.utils import timezone
from django.conf import settings
import hashlib
import hmac
from rest_framework.decorators import throttle_classes
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from django.db.models import Sum


# Serializers
# from api.users.serializers import UserSerializer, ProfileSerializer, ProfileUpdateSerializer, SignupSerializer, LoginSerializer
from api.users.serializers import UserSerializer, UserProfileSerializer
from django.contrib.auth import get_user_model
from api.models import EarningTask

User = get_user_model()

# API Views

@api_view(['POST'])
@throttle_classes([AnonRateThrottle])
def register(request):
    """User registration with referral support"""
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    refer_code = request.data.get('refer_code')
    
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=400)
    
    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already exists'}, status=400)
    
    # Create user
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email
    )
    
    # Handle referral code
    if refer_code:
        try:
            # Try to find referrer by referral code
            referrer = User.objects.get(referral_code=refer_code)
            user.referred_by = referrer
            user.save()
            
            # Process referral bonus
            try:
                from api.referral.services import ReferralService
                ReferralService.process_signup_bonus(user, referrer)
            except ImportError:
                print("ReferralService not available")
                pass
                
        except User.DoesNotExist:
            print(f"Referrer with code {refer_code} not found")
            pass
    
    # Create authentication token
    token, _ = Token.objects.get_or_create(user=user)
    
    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
        'message': 'Registration successful'
    })


@api_view(['POST'])
@throttle_classes([AnonRateThrottle])
def login(request):
    """User login"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({'error': 'Username and password required'}, status=400)
    
    user = authenticate(username=username, password=password)
    
    if user is not None:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })
    
    return Response({'error': 'Invalid credentials'}, status=401)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    """Get user profile"""
    user = request.user
    return Response(UserSerializer(user).data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user profile"""
    user = request.user
    serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response(UserSerializer(user).data)
    
    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_ad_watch(request):
    """Complete ad watching and earn coins"""
    user = request.user
    coins = 5  # Fixed reward for ad watch
    
    # Update user balance
    user.balance += coins
    user.total_earned += coins
    user.save()
    
    # Create earning task record
    task = EarningTask.objects.create(
        user=user,
        task_type='ad_watch',
        coins_earned=coins,
        status='completed'
    )
    
    # Process referral commission if user was referred
    if hasattr(user, 'referred_by') and user.referred_by:
        try:
            from api.referral.services import ReferralService
            ReferralService.process_lifetime_commission(user, coins, task)
        except ImportError:
            print("ReferralService not available")
            pass
    
    return Response({
        'success': True,
        'coins_earned': coins,
        'new_balance': float(user.balance),
        'task_id': task.id,
        'message': 'Ad watch completed successfully'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_balance(request):
    """Get user coin balance"""
    user = request.user
    return Response({
        'balance': float(user.balance),
        'total_earned': float(user.total_earned),
        'username': user.username
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_earning_history(request):
    """Get user earning history"""
    user = request.user
    tasks = EarningTask.objects.filter(user=user).order_by('-created_at')[:50]
    
    history = []
    for task in tasks:
        history.append({
            'id': task.id,
            'task_type': task.task_type,
            'coins_earned': float(task.coins_earned),
            'status': task.status,
            'created_at': task.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return Response({
        'total_tasks': len(history),
        'history': history
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """User logout - delete token"""
    try:
        request.user.auth_token.delete()
    except (AttributeError, Token.DoesNotExist):
        pass
    
    return Response({'message': 'Logout successful'})


# Referral related views (without admin registration)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_referral_stats(request):
    """Get user's referral statistics"""
    user = request.user
    
    try:
        # Get all users referred by this user
        from api.referral.models import Referral, ReferralEarning
        
        referrals = Referral.objects.filter(referrer=user)
        
        # Calculate total earnings from referrals
        total_commission = ReferralEarning.objects.filter(
            referrer=user
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Get recent commission earnings
        recent_earnings = ReferralEarning.objects.filter(referrer=user).order_by('-created_at')[:10]
        
        return Response({
            'total_referrals': referrals.count(),
            'total_commission_earned': float(total_commission),
            'refer_code': user.referral_code if hasattr(user, 'referral_code') else None,
            'referrals': [
                {
                    'username': r.referred_user.username if r.referred_user else 'Unknown',
                    'commission_earned': float(r.total_commission_earned),
                    'joined_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for r in referrals
            ],
            'recent_earnings': [
                {
                    'from_user': e.referred_user.username if e.referred_user else 'Unknown',
                    'amount': float(e.amount),
                    'date': e.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for e in recent_earnings
            ]
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=500)

# ─── Admin: All Referrals List ─────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_referrals_list(request):
    """Admin: get all referrals with pagination"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)
    
    from api.referral.models import Referral, ReferralEarning
    
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    search = request.query_params.get('search', '')
    
    qs = Referral.objects.select_related('referrer', 'referred_user').order_by('-created_at')
    if search:
        qs = qs.filter(
            referrer__username__icontains=search
        ) | qs.filter(referred_user__username__icontains=search)
        qs = qs.distinct()
    
    total = qs.count()
    start = (page - 1) * page_size
    referrals = qs[start:start + page_size]
    
    data = [
        {
            'id': r.id,
            'referrer': r.referrer.username,
            'referrer_id': r.referrer.id,
            'referred_user': r.referred_user.username if r.referred_user else 'Deleted',
            'referred_user_id': r.referred_user.id if r.referred_user else None,
            'signup_bonus_given': r.signup_bonus_given,
            'total_commission_earned': float(r.total_commission_earned),
            'joined_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        for r in referrals
    ]
    
    return Response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'results': data,
    })


# ─── Admin: Global Referral Stats ─────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_referral_overview(request):
    """Admin: overall referral program stats"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)
    
    from api.referral.models import Referral, ReferralEarning, ReferralSettings
    
    total_referrals = Referral.objects.count()
    total_commission = ReferralEarning.objects.aggregate(total=Sum('amount'))['total'] or 0
    active_referrers = Referral.objects.values('referrer').distinct().count()
    
    # Top referrers
    from django.db.models import Count
    top_referrers = (
        Referral.objects.values('referrer__username', 'referrer__id')
        .annotate(count=Count('id'), total=Sum('total_commission_earned'))
        .order_by('-count')[:10]
    )
    
    settings_obj = ReferralSettings.objects.first()
    
    return Response({
        'total_referrals': total_referrals,
        'total_commission_paid': float(total_commission),
        'active_referrers': active_referrers,
        'program_active': settings_obj.is_active if settings_obj else False,
        'settings': {
            'direct_signup_bonus': float(settings_obj.direct_signup_bonus) if settings_obj else 20,
            'referrer_signup_bonus': float(settings_obj.referrer_signup_bonus) if settings_obj else 50,
            'lifetime_commission_rate': float(settings_obj.lifetime_commission_rate) if settings_obj else 10,
        } if settings_obj else None,
        'top_referrers': [
            {
                'username': t['referrer__username'],
                'id': t['referrer__id'],
                'referral_count': t['count'],
                'total_earned': float(t['total'] or 0),
            }
            for t in top_referrers
        ],
    })


# ─── Admin: Settings CRUD ──────────────────────────────────────────────────────
@api_view(['GET', 'POST', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def admin_referral_settings(request):
    """Admin: get or update referral program settings"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)
    
    from api.referral.models import ReferralSettings
    
    settings_obj, _ = ReferralSettings.objects.get_or_create(pk=1)
    
    if request.method == 'GET':
        return Response({
            'id': settings_obj.pk,
            'direct_signup_bonus': float(settings_obj.direct_signup_bonus),
            'referrer_signup_bonus': float(settings_obj.referrer_signup_bonus),
            'lifetime_commission_rate': float(settings_obj.lifetime_commission_rate),
            'is_active': settings_obj.is_active,
        })
    
    # POST / PUT / PATCH — update
    fields = ['direct_signup_bonus', 'referrer_signup_bonus', 'lifetime_commission_rate', 'is_active']
    for field in fields:
        if field in request.data:
            setattr(settings_obj, field, request.data[field])
    settings_obj.save()
    
    return Response({
        'id': settings_obj.pk,
        'direct_signup_bonus': float(settings_obj.direct_signup_bonus),
        'referrer_signup_bonus': float(settings_obj.referrer_signup_bonus),
        'lifetime_commission_rate': float(settings_obj.lifetime_commission_rate),
        'is_active': settings_obj.is_active,
    })


# ─── Admin: Delete Referral ────────────────────────────────────────────────────
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def admin_delete_referral(request, referral_id):
    """Admin: delete a referral record"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)
    
    from api.referral.models import Referral
    try:
        r = Referral.objects.get(id=referral_id)
        r.delete()
        return Response({'success': True})
    except Referral.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)


# ─── Admin: Recent Earnings ────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_recent_earnings(request):
    """Admin: recent commission earnings"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)
    
    from api.referral.models import ReferralEarning
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    
    qs = ReferralEarning.objects.select_related('referrer', 'referred_user').order_by('-created_at')
    total = qs.count()
    start = (page - 1) * page_size
    earnings = qs[start:start + page_size]
    
    return Response({
        'total': total,
        'page': page,
        'results': [
            {
                'id': e.id,
                'referrer': e.referrer.username,
                'referred_user': e.referred_user.username if e.referred_user else 'Deleted',
                'amount': float(e.amount),
                'commission_rate': float(e.commission_rate),
                'date': e.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for e in earnings
        ],
    })


# ─── Admin: Create Referral Manually ─────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_create_referral(request):
    """Admin: manually create a referral relationship"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)

    from api.referral.models import Referral, ReferralSettings
    referrer_username = request.data.get('referrer_username', '').strip()
    referred_username = request.data.get('referred_username', '').strip()

    if not referrer_username or not referred_username:
        return Response({'error': 'Both referrer_username and referred_username are required'}, status=400)

    try:
        referrer = User.objects.get(username=referrer_username)
    except User.DoesNotExist:
        return Response({'error': f'User "{referrer_username}" not found'}, status=404)

    try:
        referred = User.objects.get(username=referred_username)
    except User.DoesNotExist:
        return Response({'error': f'User "{referred_username}" not found'}, status=404)

    if referrer == referred:
        return Response({'error': 'Referrer and referred user cannot be the same'}, status=400)

    if Referral.objects.filter(referred_user=referred).exists():
        return Response({'error': f'"{referred_username}" already has a referrer'}, status=400)

    give_bonus = request.data.get('give_bonus', False)
    settings_obj = ReferralSettings.objects.first()

    from django.db import transaction
    with transaction.atomic():
        referral = Referral.objects.create(
            referrer=referrer,
            referred_user=referred,
            signup_bonus_given=give_bonus,
        )
        if give_bonus and settings_obj and settings_obj.is_active:
            from django.db.models import F
            User.objects.filter(pk=referrer.pk).update(balance=F('balance') + settings_obj.referrer_signup_bonus)
            User.objects.filter(pk=referred.pk).update(balance=F('balance') + settings_obj.direct_signup_bonus)

    return Response({
        'success': True,
        'referral': {
            'id': referral.id,
            'referrer': referrer.username,
            'referred_user': referred.username,
            'signup_bonus_given': referral.signup_bonus_given,
            'created_at': referral.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
    }, status=201)


# ─── Admin: Give Signup Bonus Manually ───────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_give_bonus(request, referral_id):
    """Admin: manually give signup bonus for a referral"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)

    from api.referral.models import Referral, ReferralSettings
    try:
        referral = Referral.objects.select_related('referrer', 'referred_user').get(id=referral_id)
    except Referral.DoesNotExist:
        return Response({'error': 'Referral not found'}, status=404)

    if referral.signup_bonus_given:
        return Response({'error': 'Signup bonus already given for this referral'}, status=400)

    settings_obj = ReferralSettings.objects.first()
    if not settings_obj:
        return Response({'error': 'Referral settings not configured'}, status=400)

    from django.db import transaction
    from django.db.models import F
    with transaction.atomic():
        User.objects.filter(pk=referral.referrer.pk).update(balance=F('balance') + settings_obj.referrer_signup_bonus)
        User.objects.filter(pk=referral.referred_user.pk).update(balance=F('balance') + settings_obj.direct_signup_bonus)
        referral.signup_bonus_given = True
        referral.save()

    return Response({
        'success': True,
        'referrer_bonus': float(settings_obj.referrer_signup_bonus),
        'referred_bonus': float(settings_obj.direct_signup_bonus),
    })


# ─── Admin: Adjust Commission ─────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_adjust_commission(request, referral_id):
    """Admin: manually add or deduct commission for a referral"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)

    from api.referral.models import Referral, ReferralEarning
    try:
        referral = Referral.objects.select_related('referrer').get(id=referral_id)
    except Referral.DoesNotExist:
        return Response({'error': 'Referral not found'}, status=404)

    amount = request.data.get('amount')
    note = request.data.get('note', 'Manual adjustment by admin')

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return Response({'error': 'Invalid amount'}, status=400)

    from django.db import transaction
    from django.db.models import F
    from decimal import Decimal

    with transaction.atomic():
        referral.total_commission_earned = F('total_commission_earned') + Decimal(str(amount))
        referral.save()
        if amount > 0:
            User.objects.filter(pk=referral.referrer.pk).update(balance=F('balance') + Decimal(str(amount)))
        ReferralEarning.objects.create(
            referral=referral,
            referrer=referral.referrer,
            referred_user=referral.referred_user,
            amount=Decimal(str(abs(amount))),
            commission_rate=Decimal('0'),
            source_task=None,
        )

    referral.refresh_from_db()
    return Response({
        'success': True,
        'new_total_commission': float(referral.total_commission_earned),
        'amount_adjusted': amount,
    })


# ─── Admin: Delete Earning ────────────────────────────────────────────────────
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def admin_delete_earning(request, earning_id):
    """Admin: delete a commission earning record"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)

    from api.referral.models import ReferralEarning
    try:
        e = ReferralEarning.objects.get(id=earning_id)
        e.delete()
        return Response({'success': True})
    except ReferralEarning.DoesNotExist:
        return Response({'error': 'Earning not found'}, status=404)


# ─── Admin: Search Users (for referral assignment) ────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_search_users(request):
    """Admin: search users by username for referral assignment"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)

    q = request.query_params.get('q', '').strip()
    if len(q) < 2:
        return Response({'results': []})

    users = User.objects.filter(username__icontains=q).values('id', 'username', 'email')[:15]
    return Response({'results': list(users)})


# ─── Admin: Stats by Date Range ───────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_stats_by_date(request):
    """Admin: referral earnings grouped by day"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)

    from api.referral.models import ReferralEarning
    from django.db.models.functions import TruncDate
    from django.db.models import Count

    days = int(request.query_params.get('days', 30))

    from django.utils import timezone
    from datetime import timedelta
    since = timezone.now() - timedelta(days=days)

    data = (
        ReferralEarning.objects
        .filter(created_at__gte=since)
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('date')
    )

    return Response({
        'days': days,
        'data': [
            {
                'date': str(d['date']),
                'total_commission': float(d['total']),
                'count': d['count'],
            }
            for d in data
        ],
    })


# ─── Admin: Toggle Program Active ────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_toggle_program(request):
    """Admin: quickly toggle referral program on/off"""
    if not request.user.is_staff:
        return Response({'error': 'Permission denied'}, status=403)

    from api.referral.models import ReferralSettings
    settings_obj, _ = ReferralSettings.objects.get_or_create(pk=1)
    settings_obj.is_active = not settings_obj.is_active
    settings_obj.save()
    return Response({'is_active': settings_obj.is_active})
