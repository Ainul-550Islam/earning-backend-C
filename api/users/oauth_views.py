import requests
from django.shortcuts import redirect
from django.contrib.auth import login
from django.conf import settings
from social_django.utils import load_backend, load_strategy

REDIRECT_URI = 'https://earning-backend-c-production.up.railway.app/auth/social/complete/google-oauth2/'

def google_callback(request):
    code = request.GET.get('code')
    if not code:
        return redirect('https://earning-frontend-v2.vercel.app/login?error=no_code')
    
    token_response = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
        'client_secret': settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI,
    })
    
    if token_response.status_code != 200:
        return redirect(f'https://earning-frontend-v2.vercel.app/login?error=token_failed&detail={token_response.text}')
    
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    
    user_response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    
    if user_response.status_code != 200:
        return redirect('https://earning-frontend-v2.vercel.app/login?error=user_info_failed')
    
    user_data = user_response.json()
    
    strategy = load_strategy(request)
    backend = load_backend(strategy, 'google-oauth2', redirect_uri=REDIRECT_URI)
    
    try:
        user = backend.do_auth(access_token, response=user_data)
        if user:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('https://earning-frontend-v2.vercel.app/dashboard')
    except Exception as e:
        return redirect(f'https://earning-frontend-v2.vercel.app/login?error={str(e)}')
    
    return redirect('https://earning-frontend-v2.vercel.app/login?error=auth_failed')
