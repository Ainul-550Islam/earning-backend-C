"""
api/ad_networks/migrations/0005_offerattachment_userwallet_and_more.py
Add OfferAttachment and UserWallet models with complete field definitions
SaaS-ready with tenant support
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ad_networks', '0004_blacklistedip_tenant_knownbadip_tenant_and_more'),
    ]

    operations = [
        # ==================== OFFER ATTACHMENT MODEL ====================
        
        migrations.CreateModel(
            name='OfferAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.CharField(default='default', db_index=True, max_length=100, verbose_name='Tenant ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('is_active', models.BooleanField(default=True, db_index=True, verbose_name='Is Active')),
                ('file', models.FileField(upload_to='offer_attachments/%Y/%m/', verbose_name='File')),
                ('filename', models.CharField(max_length=255, verbose_name='Filename')),
                ('original_filename', models.CharField(max_length=255, verbose_name='Original Filename')),
                ('file_type', models.CharField(choices=[('image', 'Image'), ('document', 'Document'), ('video', 'Video'), ('audio', 'Audio'), ('other', 'Other')], default='other', max_length=20, verbose_name='File Type')),
                ('mime_type', models.CharField(max_length=100, verbose_name='MIME Type')),
                ('file_size', models.BigIntegerField(verbose_name='File Size (bytes)')),
                ('file_hash', models.CharField(db_index=True, max_length=64, unique=True, verbose_name='File Hash')),
                ('width', models.PositiveIntegerField(blank=True, null=True, verbose_name='Width (pixels)')),
                ('height', models.PositiveIntegerField(blank=True, null=True, verbose_name='Height (pixels)')),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='offer_attachments/thumbnails/%Y/%m/', verbose_name='Thumbnail')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('is_primary', models.BooleanField(default=False, db_index=True, verbose_name='Is Primary')),
                ('display_order', models.PositiveIntegerField(default=0, verbose_name='Display Order')),
                ('download_count', models.PositiveIntegerField(default=0, verbose_name='Download Count')),
                ('last_downloaded_at', models.DateTimeField(blank=True, null=True, verbose_name='Last Downloaded At')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='ad_networks.offer', verbose_name='Offer')),
            ],
            options={
                'verbose_name': 'Offer Attachment',
                'verbose_name_plural': 'Offer Attachments',
                'db_table': 'ad_networks_offer_attachment',
                'ordering': ['display_order', 'created_at'],
                'indexes': [
                    models.Index(fields=['tenant_id', 'file_type'], name='adnet_auto_idx_001'),
                    models.Index(fields=['tenant_id', 'is_primary'], name='adnet_auto_idx_002'),
                    models.Index(fields=['file_hash'], name='adnet_auto_idx_003'),
                ],
            },
        ),

        # ==================== USER WALLET MODEL ====================
        
        migrations.CreateModel(
            name='UserWallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant_id', models.CharField(default='default', db_index=True, max_length=100, verbose_name='Tenant ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('is_active', models.BooleanField(default=True, db_index=True, verbose_name='Is Active')),
                ('current_balance', models.DecimalField(decimal_places=2, default=0.00, max_digits=15, verbose_name='Current Balance')),
                ('total_earned', models.DecimalField(decimal_places=2, default=0.00, max_digits=15, verbose_name='Total Earned')),
                ('total_withdrawn', models.DecimalField(decimal_places=2, default=0.00, max_digits=15, verbose_name='Total Withdrawn')),
                ('pending_balance', models.DecimalField(decimal_places=2, default=0.00, max_digits=15, verbose_name='Pending Balance')),
                ('currency', models.CharField(default='BDT', max_length=3, verbose_name='Currency')),
                ('is_frozen', models.BooleanField(default=False, db_index=True, verbose_name='Is Frozen')),
                ('freeze_reason', models.TextField(blank=True, null=True, verbose_name='Freeze Reason')),
                ('frozen_at', models.DateTimeField(blank=True, null=True, verbose_name='Frozen At')),
                ('unfrozen_at', models.DateTimeField(blank=True, null=True, verbose_name='Unfrozen At')),
                ('daily_limit', models.DecimalField(decimal_places=2, default=5000.00, max_digits=15, verbose_name='Daily Limit')),
                ('monthly_limit', models.DecimalField(decimal_places=2, default=100000.00, max_digits=15, verbose_name='Monthly Limit')),
                ('last_transaction_at', models.DateTimeField(blank=True, null=True, verbose_name='Last Transaction At')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'User Wallet',
                'verbose_name_plural': 'User Wallets',
                'db_table': 'ad_networks_user_wallet',
                'indexes': [
                    models.Index(fields=['tenant_id', 'user'], name='adnet_auto_idx_004'),
                    models.Index(fields=['tenant_id', 'is_active'], name='adnet_auto_idx_005'),
                    models.Index(fields=['tenant_id', 'is_frozen'], name='adnet_auto_idx_006'),
                    models.Index(fields=['tenant_id', 'currency'], name='adnet_auto_idx_007'),
                ],
            },
        ),

        # ==================== ADD INDEXES TO EXISTING MODELS ====================
        
        # Add indexes to Offer model for better performance

        # Add indexes to UserOfferEngagement model

        # Add indexes to OfferConversion model

        # Add indexes to OfferClick model

        # Add indexes to OfferReward model

        # Add indexes to AdNetwork model

        # ==================== ADD CONSTRAINTS ====================
        
        # Add check constraints for wallet balances
        migrations.RunSQL(
            "ALTER TABLE ad_networks_user_wallet ADD CONSTRAINT chk_wallet_current_balance_nonnegative CHECK (current_balance >= 0);",
            reverse_sql="ALTER TABLE ad_networks_user_wallet DROP CONSTRAINT IF EXISTS chk_wallet_current_balance_nonnegative;"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE ad_networks_user_wallet ADD CONSTRAINT chk_wallet_total_earned_nonnegative CHECK (total_earned >= 0);",
            reverse_sql="ALTER TABLE ad_networks_user_wallet DROP CONSTRAINT IF EXISTS chk_wallet_total_earned_nonnegative;"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE ad_networks_user_wallet ADD CONSTRAINT chk_wallet_total_withdrawn_nonnegative CHECK (total_withdrawn >= 0);",
            reverse_sql="ALTER TABLE ad_networks_user_wallet DROP CONSTRAINT IF EXISTS chk_wallet_total_withdrawn_nonnegative;"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE ad_networks_user_wallet ADD CONSTRAINT chk_wallet_pending_balance_nonnegative CHECK (pending_balance >= 0);",
            reverse_sql="ALTER TABLE ad_networks_user_wallet DROP CONSTRAINT IF EXISTS chk_wallet_pending_balance_nonnegative;"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE ad_networks_user_wallet ADD CONSTRAINT chk_wallet_daily_limit_positive CHECK (daily_limit > 0);",
            reverse_sql="ALTER TABLE ad_networks_user_wallet DROP CONSTRAINT IF EXISTS chk_wallet_daily_limit_positive;"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE ad_networks_user_wallet ADD CONSTRAINT chk_wallet_monthly_limit_positive CHECK (monthly_limit > 0);",
            reverse_sql="ALTER TABLE ad_networks_user_wallet DROP CONSTRAINT IF EXISTS chk_wallet_monthly_limit_positive;"
        ),

        # Add check constraints for offer attachment
        migrations.RunSQL(
            "ALTER TABLE ad_networks_offer_attachment ADD CONSTRAINT chk_attachment_file_size_positive CHECK (file_size > 0);",
            reverse_sql="ALTER TABLE ad_networks_offer_attachment DROP CONSTRAINT IF EXISTS chk_attachment_file_size_positive;"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE ad_networks_offer_attachment ADD CONSTRAINT chk_attachment_display_order_nonnegative CHECK (display_order >= 0);",
            reverse_sql="ALTER TABLE ad_networks_offer_attachment DROP CONSTRAINT IF EXISTS chk_attachment_display_order_nonnegative;"
        ),
        
        migrations.RunSQL(
            "ALTER TABLE ad_networks_offer_attachment ADD CONSTRAINT chk_attachment_download_count_nonnegative CHECK (download_count >= 0);",
            reverse_sql="ALTER TABLE ad_networks_offer_attachment DROP CONSTRAINT IF EXISTS chk_attachment_download_count_nonnegative;"
        ),

        # ==================== ADD TRIGGERS ====================
        
        # Add trigger to update wallet updated_at field
        migrations.RunSQL(
            """
            CREATE OR REPLACE FUNCTION update_wallet_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language plpgsql;
            
            CREATE TRIGGER wallet_updated_at_trigger
                BEFORE UPDATE ON ad_networks_user_wallet
                FOR EACH ROW
                EXECUTE FUNCTION update_wallet_updated_at();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS wallet_updated_at_trigger ON ad_networks_user_wallet; DROP FUNCTION IF EXISTS update_wallet_updated_at();"
        ),

        # Add trigger to update attachment updated_at field
        migrations.RunSQL(
            """
            CREATE OR REPLACE FUNCTION update_attachment_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language plpgsql;
            
            CREATE TRIGGER attachment_updated_at_trigger
                BEFORE UPDATE ON ad_networks_offer_attachment
                FOR EACH ROW
                EXECUTE FUNCTION update_attachment_updated_at();
            """,
            reverse_sql="DROP TRIGGER IF EXISTS attachment_updated_at_trigger ON ad_networks_offer_attachment; DROP FUNCTION IF EXISTS update_attachment_updated_at();"
        ),

        # ==================== ADD VIEWS ====================
        
        # Create view for wallet statistics
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW ad_networks_wallet_stats AS
            SELECT 
                tenant_id,
                COUNT(*) as total_wallets,
                COUNT(CASE WHEN is_active = true THEN 1 END) as active_wallets,
                COUNT(CASE WHEN is_frozen = true THEN 1 END) as frozen_wallets,
                SUM(current_balance) as total_balance,
                SUM(total_earned) as total_earned,
                SUM(total_withdrawn) as total_withdrawn,
                SUM(pending_balance) as total_pending,
                AVG(current_balance) as avg_balance,
                MAX(current_balance) as max_balance,
                MIN(current_balance) as min_balance
            FROM ad_networks_user_wallet
            GROUP BY tenant_id;
            """,
            reverse_sql="DROP VIEW IF EXISTS ad_networks_wallet_stats;"
        ),

        # Create view for offer attachment statistics
        migrations.RunSQL(
            """
            CREATE OR REPLACE VIEW ad_networks_attachment_stats AS
            SELECT 
                tenant_id,
                offer_id,
                COUNT(*) as total_attachments,
                COUNT(CASE WHEN is_primary = true THEN 1 END) as primary_attachments,
                COUNT(CASE WHEN file_type = 'image' THEN 1 END) as image_attachments,
                COUNT(CASE WHEN file_type = 'document' THEN 1 END) as document_attachments,
                COUNT(CASE WHEN file_type = 'video' THEN 1 END) as video_attachments,
                COUNT(CASE WHEN file_type = 'audio' THEN 1 END) as audio_attachments,
                COUNT(CASE WHEN file_type = 'other' THEN 1 END) as other_attachments,
                SUM(file_size) as total_size,
                AVG(file_size) as avg_size,
                SUM(download_count) as total_downloads
            FROM ad_networks_offer_attachment
            WHERE is_active = true
            GROUP BY tenant_id, offer_id;
            """,
            reverse_sql="DROP VIEW IF EXISTS ad_networks_attachment_stats;"
        ),

        # ==================== INITIAL DATA ====================
        
        # Create default wallets for existing users
        migrations.RunPython(
            migrations.RunPython.noop,  # Placeholder for creating default wallets
            reverse_code=migrations.RunPython.noop,
        ),
    ]

    def create_default_wallets(apps, schema_editor):
        """
        Create default wallets for existing users
        """
        from django.contrib.auth import get_user_model
        from django.db import transaction
        
        User = get_user_model()
        UserWallet = apps.get_model('ad_networks', 'UserWallet')
        
        with transaction.atomic():
            # Get all users who don't have wallets
            users_without_wallets = User.objects.filter(wallet__isnull=True)
            
            for user in users_without_wallets:
                UserWallet.objects.create(
                    user=user,
                    tenant_id=getattr(user, 'tenant_id', 'default'),
                    current_balance=0.00,
                    total_earned=0.00,
                    total_withdrawn=0.00,
                    pending_balance=0.00,
                    currency='BDT',
                    is_active=True,
                    is_frozen=False,
                    daily_limit=5000.00,
                    monthly_limit=100000.00,
                )

    def reverse_create_default_wallets(apps, schema_editor):
        """
        Reverse: Delete created wallets
        """
        UserWallet = apps.get_model('ad_networks', 'UserWallet')
        UserWallet.objects.all().delete()
