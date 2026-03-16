# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.utils import timezone
from django.conf import settings
import hashlib
import hmac
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .serializers import ProfileSerializer, ProfileUpdateSerializer, SignupSerializer, LoginSerializer
# Serializers (create in serializers.py)
from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from api.admin_panel.models import SystemSettings, AdminAction, Report
from api.users.models import UserProfile
from api.notifications.models import Notice
from api.tasks.models import MasterTask as EarningTask
from api.models import PaymentRequest
from api.models import PaymentHistory
from api.notifications.models import Notification
from django.contrib.auth import get_user_model
User = get_user_model()



class UserSerializer(serializers.ModelSerializer):
    available_balance = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(format="%Y-%m-%d", read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'user_id', 'refer_code', 'profile_picture', 
                  'coin_balance', 'total_earned', 'email', 'is_active', 'date_joined', 'available_balance']

    def get_available_balance(self, obj):
        try:
            return obj.wallet.available_balance
        except Exception:
            return 0

class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ['id', 'message', 'created_at']

class EarningTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = EarningTask
        fields = '__all__'

class PaymentRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = PaymentRequest
        fields = '__all__'
        read_only_fields = ['user', 'status', 'processed_at', 'transaction_id']

class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = ['username', 'amount', 'payment_method', 'paid_at']


# API Views
@api_view(['POST'])
def register(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    refer_code = request.data.get('refer_code')
    
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=400)
    
    user = User.objects.create_user(username=username, password=password, email=email)
    
    # Handle referral
    if refer_code:
        try:
            referrer = User.objects.get(refer_code=refer_code)
            user.referred_by = referrer
            user.save()
            # Give bonus coins
            referrer.coin_balance += 50
            referrer.save()
            user.coin_balance += 20
            user.save()
        except User.DoesNotExist:
            pass
    
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user).data
    })


@api_view(['POST'])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        })
    return Response({'error': 'Invalid credentials'}, status=400)



@api_view(['GET'])
def get_user_info(request):
    user = request.user
    return Response(UserSerializer(user).data)


@api_view(['GET'])
def get_notices(request):
    notices = Notice.objects.filter(is_active=True)[:5]
    return Response(NoticeSerializer(notices, many=True).data)


@api_view(['POST'])
def complete_ad_watch(request):
    user = request.user
    coins = 5  # 5 coins per ad
    
    user.coin_balance += coins
    user.total_earned += coins
    user.save()
    
    EarningTask.objects.create(
        user=user,
        task_type='ad_watch',
        coins_earned=coins
    )
    
    return Response({
        'success': True,
        'coins_earned': coins,
        'new_balance': float(user.coin_balance)
    })


@api_view(['POST'])
def mylead_postback(request):
    """Handle MyLead conversion postback"""
    # Verify signature
    signature = request.GET.get('signature')
    user_id = request.GET.get('user_id')
    payout = float(request.GET.get('payout', 0))
    
    # Create signature to verify
    data = f"{user_id}{payout}{settings.MYLEAD_POSTBACK_SECRET}"
    expected_signature = hashlib.sha256(data.encode()).hexdigest()
    
    if signature != expected_signature:
        return Response({'error': 'Invalid signature'}, status=403)
    
    try:
        user = User.objects.get(user_id=user_id)
        coins = payout * 100  # Convert dollars to coins
        
        user.coin_balance += coins
        user.total_earned += coins
        user.save()
        
        EarningTask.objects.create(
            user=user,
            task_type='app_install',
            coins_earned=coins
        )
        
        return Response({'status': 'success'})
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)


@api_view(['POST'])
def create_payment_request(request):
    user = request.user
    amount = float(request.data.get('amount'))
    coins_needed = amount / settings.COIN_TO_BDT_RATE
    
    if user.coin_balance < coins_needed:
        return Response({'error': 'Insufficient balance'}, status=400)
    
    payment_request = PaymentRequest.objects.create(
        user=user,
        amount=amount,
        coins_deducted=coins_needed,
        payment_method=request.data.get('payment_method'),
        account_number=request.data.get('account_number')
    )
    
    # Deduct coins
    user.coin_balance -= coins_needed
    user.save()
    
    return Response(PaymentRequestSerializer(payment_request).data)


@api_view(['GET'])
def get_payment_requests(request):
    requests = PaymentRequest.objects.filter(user=request.user)
    return Response(PaymentRequestSerializer(requests, many=True).data)


@api_view(['GET'])
def get_payment_history(request):
    """Show recent payments to build trust"""
    history = PaymentHistory.objects.all()[:20]
    return Response(PaymentHistorySerializer(history, many=True).data)


# Profile Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get user profile"""
    serializer = ProfileSerializer(request.user)
    data = serializer.data
    data['is_staff'] = request.user.is_staff
    data['is_superuser'] = request.user.is_superuser
    return Response(data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user profile (limited fields)"""
    serializer = ProfileUpdateSerializer(
        request.user,
        data=request.data,
        partial=True
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response(ProfileSerializer(request.user).data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_avatar(request):
    """Upload profile picture"""
    if 'avatar' not in request.FILES:
        return Response({'error': 'No avatar file provided'}, status=400)
    
    user = request.user
    user.profile_picture = request.FILES['avatar']
    user.save()
    
    return Response({
        'success': True,
        'avatar_url': user.profile_picture.url
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_phone_change(request):
    """Request phone number change (requires OTP)"""
    new_phone = request.data.get('phone_number')
    
    if not new_phone:
        return Response({'error': 'Phone number required'}, status=400)
    
    # Check if phone already exists
    if User.objects.filter(phone_number=new_phone).exists():
        return Response({'error': 'Phone number already in use'}, status=400)
    
    # Generate and send OTP
    # Implementation depends on SMS service
    otp_code = generate_otp()
    
    # Store OTP in cache/session
    from django.core.cache import cache
    cache.set(f'phone_otp_{request.user.id}', {
        'code': otp_code,
        'phone': new_phone
    }, timeout=300)  # 5 minutes
    
    # Send SMS
    # send_sms(new_phone, f"Your OTP: {otp_code}")
    
    return Response({
        'success': True,
        'message': 'OTP sent to new phone number'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_phone_change(request):
    """Verify OTP and change phone"""
    otp = request.data.get('otp')
    
    # Get stored OTP
    from django.core.cache import cache
    stored = cache.get(f'phone_otp_{request.user.id}')
    
    if not stored:
        return Response({'error': 'OTP expired'}, status=400)
    
    if stored['code'] != otp:
        return Response({'error': 'Invalid OTP'}, status=400)
    
    # Update phone
    request.user.phone_number = stored['phone']
    request.user.is_phone_verified = True
    request.user.save()
    
    # Clear OTP
    cache.delete(f'phone_otp_{request.user.id}')
    
    return Response({
        'success': True,
        'phone_number': request.user.phone_number
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_login_history(request):
    """Get login history (v2)"""
    # This would require a LoginHistory model
    # For now, return mock data
    return Response({
        'history': [
            {
                'device': 'Android',
                'ip': request.user.last_login_ip,
                'location': 'Dhaka, Bangladesh',
                'timestamp': request.user.last_login
            }
        ]
    })
# wallet/services.py

class SignupThrottle(AnonRateThrottle):
    rate = '5/hour'  # 5 signups per hour per IP

class LoginThrottle(AnonRateThrottle):
    rate = '10/hour'  # 10 login attempts per hour


@api_view(['POST'])
@throttle_classes([SignupThrottle])
def signup(request):
    """User signup with rate limiting"""
    serializer = SignupSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'user_id': user.user_id,
                'refer_code': user.refer_code
            },
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@throttle_classes([LoginThrottle])
def login(request):
    """User login with rate limiting"""
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Update last login IP
        user.last_login_ip = get_client_ip(request)
        user.save(update_fields=['last_login_ip'])
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'user': ProfileSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def refresh_token(request):
    """Refresh access token"""
    from rest_framework_simplejwt.serializers import TokenRefreshSerializer
    
    serializer = TokenRefreshSerializer(data=request.data)
    
    if serializer.is_valid():
        return Response(serializer.validated_data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def generate_otp():
    """Generate 6-digit OTP"""
    import random
    return str(random.randint(100000, 999999))
# earning_backend/earning_backend/settings.py














from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal

from .models import (
    Wallet, Transaction, Offer, UserOffer,
    Referral, DailyStats, Withdrawal
)
from .serializers import (
    UserSerializer, UserRegistrationSerializer, WalletSerializer,
    TransactionSerializer, OfferSerializer, UserOfferSerializer,
    UserOfferCreateSerializer, ReferralSerializer, DailyStatsSerializer,
    WithdrawalSerializer, WithdrawalCreateSerializer,
    DashboardStatsSerializer, EarningsChartSerializer
)

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """User management viewset"""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_profile(self, request):
        """Update user profile"""
        user = request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def adjust_balance(self, request, pk=None):
        """Admin: increase or decrease a user's available balance by amount"""
        # Only staff users may adjust balances
        if not request.user.is_staff:
            return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        user = self.get_object()
        amount = request.data.get('amount')
        try:
            amount = Decimal(str(amount))
        except Exception:
            return Response({'detail': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

        wallet = None
        try:
            wallet = user.wallet
        except Exception:
            return Response({'detail': 'User wallet not found'}, status=status.HTTP_400_BAD_REQUEST)

        # apply adjustment (allow negative amounts to decrease)
        wallet.available_balance = F('available_balance') + amount
        wallet.save()
        wallet.refresh_from_db()

        return Response({'available_balance': float(wallet.available_balance)})


@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """User registration endpoint"""
    serializer = UserRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Create welcome notification
        Notification.objects.create(
            user=user,
            notification_type='SUCCESS',
            title='Welcome to Earning Pro!',
            message='Your account has been created successfully. Start earning now!',
            icon='[DONE]'
        )
        
        return Response({
            'message': 'Registration successful',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    """Wallet viewset"""
    
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get wallet balance"""
        wallet, _ = Wallet.objects.get_or_create(user=request.user, defaults={"currency": "BDT"})
        return Response({
            'available_balance': wallet.available_balance,
            'pending_balance': wallet.pending_balance,
            'lifetime_earnings': wallet.total_earned,
            'total_withdrawn': wallet.total_withdrawn
        })


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """Transaction history viewset"""
    
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Transaction.objects.filter(user=self.request.user)
        
        # Filter by type
        transaction_type = self.request.query_params.get('type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by status
        transaction_status = self.request.query_params.get('status')
        if transaction_status:
            queryset = queryset.filter(status=transaction_status)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
        
        return queryset


class OfferViewSet(viewsets.ReadOnlyModelViewSet):
    """Offers viewset"""
    
    queryset = Offer.objects.filter(status='ACTIVE')
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Offer.objects.filter(status='ACTIVE')
        user = self.request.user
        
        # Filter by offer type
        offer_type = self.request.query_params.get('type')
        if offer_type:
            queryset = queryset.filter(offer_type=offer_type)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Featured offers
        featured = self.request.query_params.get('featured')
        if featured == 'true':
            queryset = queryset.filter(featured=True)
        
        # Available for user's country
        if user.country:
            queryset = queryset.filter(
                Q(countries__contains=[user.country]) | Q(countries=[])
            )
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured offers"""
        offers = self.get_queryset().filter(featured=True)[:10]
        serializer = self.get_serializer(offers, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get offer categories"""
        categories = Offer.objects.filter(status='ACTIVE').values_list('category', flat=True).distinct()
        return Response(list(categories))


class UserOfferViewSet(viewsets.ModelViewSet):
    """User offer completions viewset"""
    
    queryset = UserOffer.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserOfferCreateSerializer
        return UserOfferSerializer
    
    def get_queryset(self):
        return UserOffer.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Start an offer"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            user_offer = serializer.save()
            
            # Create notification
            Notification.objects.create(
                user=request.user,
                notification_type='INFO',
                title='Offer Started',
                message=f'You started: {user_offer.offer.title}',
                icon='🎯'
            )
            
            return Response(
                UserOfferSerializer(user_offer).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit offer for review"""
        user_offer = self.get_object()
        
        if user_offer.status != 'STARTED':
            return Response(
                {'error': 'Offer is not in started state'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_offer.status = 'PENDING'
        user_offer.proof_data = request.data.get('proof_data', {})
        user_offer.save()
        
        # Create notification
        Notification.objects.create(
            user=request.user,
            notification_type='INFO',
            title='Offer Submitted',
            message=f'Your completion of "{user_offer.offer.title}" is under review',
            icon='⏳'
        )
        
        return Response(UserOfferSerializer(user_offer).data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark offer as completed (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_offer = self.get_object()
        
        if user_offer.complete():
            # Create notification
            Notification.objects.create(
                user=user_offer.user,
                notification_type='SUCCESS',
                title='Offer Completed!',
                message=f'You earned ${user_offer.reward_earned} from "{user_offer.offer.title}"',
                icon='[MONEY]'
            )
            
            # Referral commission
            if user_offer.user.referred_by:
                try:
                    referral = Referral.objects.get(
                        referrer=user_offer.user.referred_by,
                        referred=user_offer.user
                    )
                    commission = referral.add_commission(user_offer.reward_earned)
                    
                    if commission > 0:
                        Notification.objects.create(
                            user=user_offer.user.referred_by,
                            notification_type='EARNING',
                            title='Referral Commission',
                            message=f'You earned ${commission} from {user_offer.user.username}',
                            icon='💵'
                        )
                except Referral.DoesNotExist:
                    pass
            
            return Response(UserOfferSerializer(user_offer).data)
        
        return Response(
            {'error': 'Failed to complete offer'},
            status=status.HTTP_400_BAD_REQUEST
        )


class ReferralViewSet(viewsets.ReadOnlyModelViewSet):
    """Referral viewset"""
    
    queryset = Referral.objects.all()
    serializer_class = ReferralSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Referral.objects.filter(referrer=self.request.user)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get referral statistics"""
        referrals = self.get_queryset()
        
        return Response({
            'total_referrals': referrals.count(),
            'active_referrals': referrals.filter(is_active=True).count(),
            'total_earned': referrals.aggregate(total=Sum('total_earned'))['total'] or 0,
            'referral_code': request.user.referral_code
        })


class WithdrawalViewSet(viewsets.ModelViewSet):
    """Withdrawal viewset"""
    
    queryset = Withdrawal.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return WithdrawalCreateSerializer
        return WithdrawalSerializer
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Withdrawal.objects.all()
        return Withdrawal.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create withdrawal request"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            withdrawal = serializer.save()
            
            # Create notification
            Notification.objects.create(
                user=request.user,
                notification_type='WITHDRAWAL',
                title='Withdrawal Requested',
                message=f'Your withdrawal of ${withdrawal.amount} is being processed',
                icon='💳'
            )
            
            return Response(
                WithdrawalSerializer(withdrawal).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve withdrawal (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        withdrawal = self.get_object()
        
        if withdrawal.approve(processed_by=request.user):
            # Create notification
            Notification.objects.create(
                user=withdrawal.user,
                notification_type='SUCCESS',
                title='Withdrawal Approved',
                message=f'Your withdrawal of ${withdrawal.amount} has been processed',
                icon='[OK]'
            )
            
            return Response(WithdrawalSerializer(withdrawal).data)
        
        return Response(
            {'error': 'Failed to approve withdrawal'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject withdrawal (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        withdrawal = self.get_object()
        withdrawal.status = 'REJECTED'
        withdrawal.rejection_reason = request.data.get('reason', '')
        withdrawal.processed_at = timezone.now()
        withdrawal.processed_by = request.user
        withdrawal.save()
        
        # Create notification
        Notification.objects.create(
            user=withdrawal.user,
            notification_type='WARNING',
            title='Withdrawal Rejected',
            message=f'Your withdrawal was rejected. Reason: {withdrawal.rejection_reason}',
            icon='[ERROR]'
        )
        
        return Response(WithdrawalSerializer(withdrawal).data)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Get dashboard statistics"""
    user = request.user
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    # Today's stats
    today_stats = DailyStats.objects.filter(user=user, date=today).first()
    yesterday_stats = DailyStats.objects.filter(user=user, date=yesterday).first()
    
    today_earnings = today_stats.earnings if today_stats else Decimal('0.00')
    yesterday_earnings = yesterday_stats.earnings if yesterday_stats else Decimal('0.00')
    
    # Calculate changes
    if yesterday_earnings > 0:
        earnings_change = ((today_earnings - yesterday_earnings) / yesterday_earnings) * 100
    else:
        earnings_change = 0 if today_earnings == 0 else 100
    
    # Weekly earnings
    weekly_stats = DailyStats.objects.filter(
        user=user,
        date__gte=week_ago
    ).order_by('date')
    
    weekly_earnings = [{
        'day': stat.date.strftime('%a'),
        'value': float(stat.earnings),
        'clicks': stat.clicks,
        'conversions': stat.conversions
    } for stat in weekly_stats]
    
    # Recent activities
    recent_transactions = Transaction.objects.filter(
        user=user,
        status='COMPLETED'
    )[:5]
    
    # Available offers
    available_offers = Offer.objects.filter(
        status='ACTIVE'
    ).exclude(
        user_completions__user=user,
        user_completions__status='COMPLETED'
    )[:5]
    
    # Referral stats
    wallet, _ = __import__("api.wallet.models", fromlist=["Wallet"]).Wallet.objects.get_or_create(user=user, defaults={"currency": "BDT"})
    referrals = Referral.objects.filter(referrer=user)
    referral_count = referrals.count()
    referral_earnings = referrals.aggregate(total=Sum('total_earned'))['total'] or Decimal('0.00')
    
    data = {
        'balance': wallet.available_balance,
        'today_earnings': today_earnings,
        'today_change': float(earnings_change),
        'clicks': today_stats.clicks if today_stats else 0,
        'clicks_change': 0,  # Calculate if needed
        'conversions': today_stats.conversions if today_stats else 0,
        'conversions_change': 0,  # Calculate if needed
        'active_users': User.objects.filter(is_active=True).count(),
        'active_change': 0,  # Calculate if needed
        'referrals': referral_count,
        'referral_earnings': referral_earnings,
        'recent_activities': TransactionSerializer(recent_transactions, many=True).data,
        'available_offers': OfferSerializer(available_offers, many=True, context={'request': request}).data,
        'weekly_earnings': weekly_earnings
    }
    
    serializer = DashboardStatsSerializer(data)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def earnings_chart(request):
    """Get earnings chart data"""
    user = request.user
    days = int(request.GET.get('days', 7))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    stats = DailyStats.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    data = [{
        'day': stat.date.strftime('%a'),
        'value': float(stat.earnings),
        'clicks': stat.clicks,
        'conversions': stat.conversions
    } for stat in stats]
    
    serializer = EarningsChartSerializer(data, many=True)
    return Response(serializer.data)


