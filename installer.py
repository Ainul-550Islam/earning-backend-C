#!/usr/bin/env python
"""
EarningApp White-label Installer
Run: python installer.py
"""
import os
import sys
import subprocess

print("""
╔══════════════════════════════════════╗
║   EarningApp White-label Installer   ║
║   Version 1.0                        ║
╚══════════════════════════════════════╝
""")

# Collect info
print("��� Please fill in your app details:\n")
app_name = input("App Name (e.g. MyEarningApp): ").strip() or "EarningApp"
domain = input("Your Domain (e.g. myapp.com): ").strip() or "localhost"
admin_email = input("Admin Email: ").strip()
admin_password = input("Admin Password: ").strip()
primary_color = input("Primary Color (default #007bff): ").strip() or "#007bff"
plan = input("Plan [basic/pro/enterprise] (default basic): ").strip() or "basic"

print("\n��� Setting up database...\n")
subprocess.run([sys.executable, "manage.py", "migrate", "--no-input"], check=True)

print("��� Creating tenant...\n")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
import django
django.setup()

from api.tenants.models import Tenant, TenantSettings
from django.contrib.auth import get_user_model

User = get_user_model()

tenant, created = Tenant.objects.get_or_create(
    domain=domain,
    defaults={
        'name': app_name,
        'plan': plan,
        'primary_color': primary_color,
        'admin_email': admin_email,
        'is_active': True,
        'max_users': 100 if plan == 'basic' else 1000,
    }
)

print(f"✅ Tenant created: {tenant.name}")
print(f"��� API Key: {tenant.api_key}")

# Create superuser
if not User.objects.filter(email=admin_email).exists():
    user = User.objects.create_superuser(
        username=admin_email.split('@')[0],
        email=admin_email,
        password=admin_password,
        tenant=tenant,
    )
    print(f"✅ Admin user created: {admin_email}")

print("""
╔══════════════════════════════════════════╗
║   ✅ Installation Complete!              ║
║                                          ║
║   Admin Panel: /admin/                   ║
║   API Docs:    /api/docs/                ║
║   API Key:     (shown above)             ║
╚══════════════════════════════════════════╝
""")
