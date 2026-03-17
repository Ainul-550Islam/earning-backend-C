import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='AinulIslam').exists():
    User.objects.create_superuser('AinulIslam', 'ainul10islam100@gmail.com', '99998888')
    print('Superuser created!')
else:
    print('Superuser already exists!')
