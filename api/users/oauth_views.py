import requests
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()
REDIRECT_URI = 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'
FRONTEND_URL = 'https://earning-frontend-v2.vercel.app'

def google_callback(request):
    code = request.GET.get('code')
    if not code:
        return redirect(FRONTEND_URL + '/login?error=no_code')
    token_response = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
        'client_secret': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI,
    })
    if token_response.status_code != 200:
        return redirect(FRONTEND_URL + '/login?error=token_failed')
    access_token = token_response.json().get('access_token')
    user_info = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': 'Bearer ' + access_token}
    ).json()
    email = user_info.get('email')
    if not email:
        return redirect(FRONTEND_URL + '/login?error=no_email')
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = base_username + str(counter)
            counter += 1
        user = User.objects.create_user(email=email, username=username,
            first_name=user_info.get('given_name', ''),
            last_name=user_info.get('family_name', ''))
    refresh = RefreshToken.for_user(user)
    return redirect(FRONTEND_URL + '/oauth-callback?access=' + str(refresh.access_token) + '&refresh=' + str(refresh))
