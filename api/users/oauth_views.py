import requests
import hashlib
import logging
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction, IntegrityError
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)
User = get_user_model()

REDIRECT_URI = 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'
FRONTEND_URL = 'https://earning-frontend-v2.vercel.app'

def get_device_fingerprint(request):
    """Generate device fingerprint for fraud detection."""
    components = [
        request.META.get("HTTP_USER_AGENT", ""),
        request.META.get("HTTP_ACCEPT_LANGUAGE", ""),
        request.META.get("HTTP_ACCEPT_ENCODING", ""),
        request.META.get("REMOTE_ADDR", ""),
    ]
    raw = "|".join(components)
    return hashlib.sha256(raw.encode()).hexdigest()

def check_fraud_multiple_accounts(request, user, email):
    """Flag if same device tries multiple Gmail accounts."""
    try:
        from api.fraud_detection.models import DeviceFingerprint, FraudAttempt
        fingerprint = get_device_fingerprint(request)
        ip = request.META.get("REMOTE_ADDR", "")

        device, created = DeviceFingerprint.objects.get_or_create(
            device_hash=fingerprint,
            defaults={"ip_address": ip, "user": user}
        )

        if not created and device.user and device.user != user:
            logger.warning(
                f"[FRAUD] Device {fingerprint[:16]} tried multiple accounts: "
                f"existing={device.user.email}, new={email}"
            )
            try:
                FraudAttempt.objects.create(
                    user=user,
                    attempt_type="multiple_accounts",
                    ip_address=ip,
                    details={"device_fingerprint": fingerprint, "conflicting_email": device.user.email},
                )
            except Exception as e:
                logger.error(f"[FRAUD] Could not create FraudAttempt: {e}")
    except Exception as e:
        logger.error(f"[FRAUD] Fraud check failed: {e}")

def get_or_create_user(email, user_info):
    """
    ONE GMAIL = ONE ACCOUNT.
    Database-level unique constraint on email ensures no duplicates.
    """
    with transaction.atomic():
        try:
            user = User.objects.get(email=email)
            logger.info(f"[OAUTH] Existing user logged in: {email}")
            return user, False
        except User.DoesNotExist:
            pass

        base_username = email.split("@")[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        try:
            user = User.objects.create_user(
                email=email,
                username=username,
                first_name=user_info.get("given_name", ""),
                last_name=user_info.get("family_name", ""),
            )
            logger.info(f"[OAUTH] New user created: {email}")
            return user, True
        except IntegrityError:
            user = User.objects.get(email=email)
            logger.warning(f"[OAUTH] Race condition handled for: {email}")
            return user, False

def google_login(request):
    """Store intent in session before redirecting to Google."""
    intent = request.session.pop("oauth_intent", "login")
    request.session["oauth_intent"] = intent
    from social_django.views import auth
    return auth(request, "google-oauth2")

def google_callback(request):
    """Main Google OAuth2 callback handler."""
    code = request.GET.get("code")
    if not code:
        logger.error("[OAUTH] No code in callback")
        return redirect(FRONTEND_URL + "/login?error=no_code")

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
            "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=10,
    )

    if token_response.status_code != 200:
        logger.error(f"[OAUTH] Token exchange failed: {token_response.text}")
        return redirect(FRONTEND_URL + "/login?error=token_failed")

    access_token = token_response.json().get("access_token")
    if not access_token:
        return redirect(FRONTEND_URL + "/login?error=no_access_token")

    user_info_response = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": "Bearer " + access_token},
        timeout=10,
    )

    if user_info_response.status_code != 200:
        return redirect(FRONTEND_URL + "/login?error=user_info_failed")

    user_info = user_info_response.json()
    email = user_info.get("email")

    if not email:
        return redirect(FRONTEND_URL + "/login?error=no_email")

    if not user_info.get("verified_email", False):
        return redirect(FRONTEND_URL + "/login?error=email_not_verified")

    user, created = get_or_create_user(email, user_info)

    check_fraud_multiple_accounts(request, user, email)

    refresh = RefreshToken.for_user(user)
    access_jwt = str(refresh.access_token)
    refresh_jwt = str(refresh)

    logger.info(f"[OAUTH] Login successful: {email} (new={created})")

    intent = request.session.pop("oauth_intent", "login")

    if intent == "signup" and not created:
        return redirect(FRONTEND_URL + "/login?error=email_already_registered")

    return redirect(
        FRONTEND_URL + "/oauth-callback?access=" + access_jwt + "&refresh=" + refresh_jwt + "&new_user=" + str(created).lower()
    )
