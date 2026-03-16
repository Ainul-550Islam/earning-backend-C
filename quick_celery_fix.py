#!/usr/bin/env python
"""
Quick fix for Celery - Enable ad_networks and create missing models
"""

import os
import sys

def enable_ad_networks_in_settings():
    """Enable api.ad_networks in settings.py"""
    
    print("🔧 Enabling api.ad_networks in settings.py...")
    
    settings_file = 'config/settings.py'
    
    if not os.path.exists(settings_file):
        print(f"❌ {settings_file} not found")
        return False
    
    with open(settings_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already enabled
    if "'api.ad_networks'" in content:
        # Check if commented
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if "'api.ad_networks'" in line and line.strip().startswith('#'):
                # Uncomment
                lines[i] = line.lstrip('# ')
                print("✓ Uncommented api.ad_networks")
                break
            elif "'api.ad_networks'" in line:
                print("✓ api.ad_networks already enabled")
                break
        else:
            print("✓ api.ad_networks found")
        
        # Write back if changed
        if '# ' in line and "'api.ad_networks'" in line:
            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
    else:
        # Add api.ad_networks
        print("➕ Adding api.ad_networks to INSTALLED_APPS")
        
        # Find where to add (before api.offerwall)
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if "'api.offerwall'" in line:
                indent = ' ' * (len(line) - len(line.lstrip()))
                lines.insert(i, f"{indent}'api.ad_networks',      # ✅ For Celery compatibility")
                break
        
        with open(settings_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    
    print("✅ settings.py updated")
    return True

def create_missing_models():
    """Create PostbackLog and KnownBadIP models if missing"""
    
    print("\n🔧 Creating missing models...")
    
    models_file = 'api/ad_networks/models.py'
    
    if not os.path.exists(models_file):
        print(f"❌ {models_file} not found")
        return False
    
    with open(models_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Check for PostbackLog
    if 'class PostbackLog' not in content:
        print("➕ Adding PostbackLog model...")
        
        # Find where to add (after BlacklistedIP)
        lines = content.split('\n')
        
        postbacklog_model = '''
class PostbackLog(models.Model):
    """Log all postback attempts for auditing"""
    request_id = models.CharField(max_length=100, unique=True)
    click_id = models.CharField(max_length=255, null=True, blank=True)
    conversion_id = models.CharField(max_length=255, null=True, blank=True)
    engagement = models.ForeignKey(
        'UserOfferEngagement', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    status = models.CharField(
        max_length=50,
        choices=[
            ('received', 'Received'),
            ('processed', 'Processed'),
            ('duplicate', 'Duplicate'),
            ('no_engagement', 'No Engagement'),
            ('error', 'Error'),
            ('fraud', 'Fraud Detected')
        ]
    )
    raw_data = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_fraud = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request_id']),
            models.Index(fields=['click_id']),
            models.Index(fields=['conversion_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"PostbackLog {self.request_id} - {self.status}"
'''
        
        # Insert after BlacklistedIP
        for i, line in enumerate(lines):
            if 'class BlacklistedIP(models.Model):' in line:
                lines.insert(i + 1, postbacklog_model)
                print("✓ PostbackLog added after BlacklistedIP")
                break
    
    # Check for KnownBadIP
    if 'class KnownBadIP' not in content:
        print("➕ Adding KnownBadIP model...")
        
        knownbadip_model = '''
class KnownBadIP(models.Model):
    """Known bad IP addresses from various sources"""
    ip_address = models.GenericIPAddressField(unique=True)
    threat_type = models.CharField(
        max_length=50,
        choices=[
            ('bot', 'Bot Network'),
            ('vpn', 'VPN/Proxy'),
            ('scanner', 'Port Scanner'),
            ('spam', 'Spam Source'),
            ('malware', 'Malware Distribution'),
            ('phishing', 'Phishing Source'),
            ('ddos', 'DDoS Source'),
            ('credential_stuffing', 'Credential Stuffing'),
        ]
    )
    confidence_score = models.IntegerField(
        default=50,
        help_text="Confidence score (0-100)"
    )
    source = models.CharField(
        max_length=100,
        choices=[
            ('internal', 'Internal Detection'),
            ('ipqualityscore', 'IPQualityScore'),
            ('abuseipdb', 'AbuseIPDB'),
            ('maxmind', 'MaxMind'),
            ('firehol', 'FireHOL'),
            ('custom', 'Custom List'),
        ]
    )
    description = models.TextField(blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['threat_type', 'is_active']),
        ]
        verbose_name = "Known Bad IP"
        verbose_name_plural = "Known Bad IPs"
    
    def __str__(self):
        return f"{self.ip_address} - {self.threat_type}"
'''
        
        # Insert after PostbackLog or at the end
        for i, line in enumerate(lines):
            if 'class PostbackLog(models.Model):' in line:
                # Find the end of PostbackLog class
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith('class '):
                    j += 1
                lines.insert(j, '\n' + knownbadip_model)
                print("✓ KnownBadIP added after PostbackLog")
                break
        else:
            # If PostbackLog not found, add at the end
            lines.append(knownbadip_model)
            print("✓ KnownBadIP added at the end")
    
    # Write back
    with open(models_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print("✅ Missing models created")
    return True

def run_migrations():
    """Run database migrations"""
    
    print("\n🔄 Running migrations...")
    
    commands = [
        "python manage.py makemigrations ad_networks",
        "python manage.py migrate",
    ]
    
    for cmd in commands:
        print(f"\n$ {cmd}")
        result = os.system(cmd)
        if result != 0:
            print(f"⚠️ Command returned: {result}")
    
    print("\n✅ Migrations completed")

def test_system():
    """Test if system works"""
    
    print("\n🧪 Testing system...")
    
    import django
    from django.conf import settings
    
    # Setup Django
    if not settings.configured:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        django.setup()
    
    try:
        # Test imports
        from api.ad_networks.models import BlacklistedIP, PostbackLog, KnownBadIP, UserOfferEngagement, OfferConversion
        print("✅ All models imported successfully")
        
        # Test Celery task import
        from api.tasks.blacklist_tasks import cleanup_expired_blacklist_task
        print("✅ Celery task imported")
        
        # Submit test task
        result = cleanup_expired_blacklist_task.delay(500)
        print(f"✅ Test task submitted: {result.id}")
        
        print("\n🎉 SYSTEM IS WORKING!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 QUICK CELERY FIX")
    print("=" * 60)
    
    # 1. Enable api.ad_networks
    if not enable_ad_networks_in_settings():
        print("❌ Failed to enable api.ad_networks")
        return
    
    # 2. Create missing models
    create_missing_models()
    
    # 3. Run migrations
    run_migrations()
    
    # 4. Test system
    if test_system():
        print("\n" + "=" * 60)
        print("✅ FIX COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\n📋 Next steps:")
        print("1. Start Celery Beat:")
        print("   python -m celery -A earning_backend beat -l info")
        print("\n2. Start Celery Worker:")
        print("   python -m celery -A earning_backend worker -l info -P threads")
        print("\n3. Monitor logs:")
        print("   tail -f logs/celery_worker.log")
    else:
        print("\n❌ Fix failed. Please check errors above.")

if __name__ == "__main__":
    main()