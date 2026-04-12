# Generated migration for api/monetization_tools
# Run: python manage.py migrate monetization_tools

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── AdNetwork ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AdNetwork',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('network_type', models.CharField(
                    choices=[
                        ('admob','Google AdMob'),('facebook','Facebook Audience Network'),
                        ('applovin','AppLovin MAX'),('ironsource','IronSource'),
                        ('unity','Unity Ads'),('vungle','Vungle'),
                        ('chartboost','Chartboost'),('tapjoy','Tapjoy'),
                        ('fyber','Fyber'),('mintegral','Mintegral'),
                        ('pangle','Pangle (TikTok)'),('inmobi','InMobi'),
                        ('adcolony','AdColony'),('custom','Custom Network'),
                    ],
                    max_length=30, unique=True,
                )),
                ('display_name', models.CharField(max_length=100)),
                ('app_id', models.CharField(blank=True, max_length=255, null=True)),
                ('api_key', models.CharField(blank=True, max_length=500, null=True)),
                ('secret_key', models.CharField(blank=True, max_length=500, null=True)),
                ('reporting_api_key', models.CharField(blank=True, max_length=500, null=True)),
                ('postback_url', models.URLField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('priority', models.PositiveSmallIntegerField(default=10)),
                ('floor_price', models.DecimalField(decimal_places=4, default='0.0000', max_digits=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_adnetwork_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_ad_networks', 'ordering': ['priority']},
        ),

        # ── AdCampaign ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AdCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('campaign_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('advertiser_name', models.CharField(blank=True, max_length=200, null=True)),
                ('advertiser_email', models.EmailField(blank=True, null=True)),
                ('total_budget', models.DecimalField(
                    decimal_places=2, max_digits=14,
                    validators=[django.core.validators.MinValueValidator('0.01')]
                )),
                ('daily_budget', models.DecimalField(decimal_places=2, max_digits=14, null=True, blank=True)),
                ('spent_budget', models.DecimalField(decimal_places=2, default='0.00', max_digits=14)),
                ('pricing_model', models.CharField(
                    choices=[('cpm','CPM'),('cpc','CPC'),('cpa','CPA'),('cpi','CPI'),('cpe','CPE'),('flat','Flat Rate')],
                    default='cpm', max_length=10,
                )),
                ('bid_amount', models.DecimalField(decimal_places=4, default='0.0000', max_digits=10)),
                ('target_countries', models.JSONField(blank=True, default=list)),
                ('target_cities', models.JSONField(blank=True, default=list)),
                ('target_languages', models.JSONField(blank=True, default=list)),
                ('target_devices', models.JSONField(blank=True, default=list)),
                ('target_os', models.JSONField(blank=True, default=list)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('draft','Draft'),('active','Active'),('paused','Paused'),('ended','Ended'),('archived','Archived')],
                    default='draft', max_length=20,
                )),
                ('total_impressions', models.BigIntegerField(default=0)),
                ('total_clicks', models.BigIntegerField(default=0)),
                ('total_conversions', models.BigIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_adcampaign_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_ad_campaigns', 'ordering': ['-created_at']},
        ),

        # ── AdUnit ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AdUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('unit_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('ad_format', models.CharField(
                    choices=[
                        ('banner','Banner'),('interstitial','Interstitial'),
                        ('rewarded_video','Rewarded Video'),('native','Native Ad'),
                        ('playable','Playable Ad'),('carousel','Carousel'),
                        ('audio','Audio Ad'),('offerwall','Offerwall'),
                    ],
                    default='banner', max_length=20,
                )),
                ('width', models.IntegerField(blank=True, null=True)),
                ('height', models.IntegerField(blank=True, null=True)),
                ('creative_url', models.URLField(blank=True, null=True)),
                ('destination_url', models.URLField(blank=True, null=True)),
                ('cta_text', models.CharField(blank=True, max_length=100, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_adunit_campaign',
                    to='monetization_tools.adcampaign',
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_adunit_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_ad_units', 'ordering': ['-created_at']},
        ),

        # ── AdPlacement ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='AdPlacement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('screen_name', models.CharField(max_length=200)),
                ('position', models.CharField(
                    choices=[('top','Top'),('bottom','Bottom'),('mid_content','Mid-Content'),
                             ('fullscreen','Fullscreen'),('sidebar','Sidebar'),
                             ('after_action','After User Action'),('on_exit','On Exit Intent')],
                    default='bottom', max_length=20,
                )),
                ('refresh_rate', models.PositiveIntegerField(default=30)),
                ('frequency_cap', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ad_unit', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_adplacement_ad_unit',
                    to='monetization_tools.adunit',
                )),
                ('ad_network', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_adplacement_ad_network',
                    to='monetization_tools.adnetwork',
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_adplacement_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_ad_placements'},
        ),

        # ── Offerwall ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Offerwall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('logo_url', models.URLField(blank=True, null=True)),
                ('embed_url', models.URLField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_featured', models.BooleanField(default=False)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('network', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_offerwall_network',
                    to='monetization_tools.adnetwork',
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_offerwall_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_offerwalls', 'ordering': ['sort_order', 'name']},
        ),

        # ── Offer ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('external_offer_id', models.CharField(db_index=True, max_length=200)),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True, null=True)),
                ('requirements', models.TextField(blank=True, null=True)),
                ('offer_type', models.CharField(max_length=20, default='other')),
                ('status', models.CharField(max_length=10, default='active')),
                ('payout_usd', models.DecimalField(decimal_places=4, max_digits=10)),
                ('point_value', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='USD', max_length=10)),
                ('target_countries', models.JSONField(blank=True, default=list)),
                ('target_devices', models.JSONField(blank=True, default=list)),
                ('target_os', models.JSONField(blank=True, default=list)),
                ('min_age', models.PositiveSmallIntegerField(default=13)),
                ('thumbnail_url', models.URLField(blank=True, null=True)),
                ('tracking_url', models.URLField(blank=True, null=True)),
                ('total_completions', models.PositiveIntegerField(default=0)),
                ('conversion_rate', models.DecimalField(decimal_places=2, default='0.00', max_digits=5)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_hot', models.BooleanField(default=False)),
                ('expiry_date', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('offerwall', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_offer_offerwall',
                    to='monetization_tools.offerwall',
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_offer_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_offers', 'ordering': ['-is_featured', '-point_value']},
        ),

        # ── OfferCompletion ────────────────────────────────────────────────
        migrations.CreateModel(
            name='OfferCompletion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('transaction_id', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('network_transaction_id', models.CharField(blank=True, max_length=200, null=True)),
                ('status', models.CharField(max_length=15, default='pending')),
                ('reward_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('payout_amount', models.DecimalField(decimal_places=4, max_digits=10)),
                ('ip_address', models.GenericIPAddressField()),
                ('device_id', models.CharField(blank=True, max_length=255, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('fraud_score', models.PositiveSmallIntegerField(
                    default=0, validators=[django.core.validators.MaxValueValidator(100)]
                )),
                ('fraud_reason', models.TextField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True, null=True)),
                ('clicked_at', models.DateTimeField()),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('credited_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('offer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_offercompletion_offer',
                    to='monetization_tools.offer',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_offercompletion_user',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_offercompletion_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_offer_completions', 'ordering': ['-created_at']},
        ),

        # ── RewardTransaction ──────────────────────────────────────────────
        migrations.CreateModel(
            name='RewardTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('transaction_id', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('transaction_type', models.CharField(max_length=25)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('balance_before', models.DecimalField(decimal_places=2, max_digits=14)),
                ('balance_after', models.DecimalField(decimal_places=2, max_digits=14)),
                ('description', models.CharField(blank=True, max_length=500, null=True)),
                ('reference_id', models.CharField(blank=True, max_length=200, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_rewardtransaction_user',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_rewardtransaction_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_reward_transactions', 'ordering': ['-created_at']},
        ),

        # ── SubscriptionPlan ───────────────────────────────────────────────
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('plan_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='BDT', max_length=5)),
                ('interval', models.CharField(max_length=10, default='monthly')),
                ('trial_days', models.PositiveSmallIntegerField(default=0)),
                ('features', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('is_popular', models.BooleanField(default=False)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_subscriptionplan_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_subscription_plans', 'ordering': ['sort_order', 'price']},
        ),

        # ── UserSubscription ───────────────────────────────────────────────
        migrations.CreateModel(
            name='UserSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('subscription_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.CharField(max_length=15, default='trial')),
                ('started_at', models.DateTimeField()),
                ('trial_end_at', models.DateTimeField(blank=True, null=True)),
                ('current_period_start', models.DateTimeField()),
                ('current_period_end', models.DateTimeField()),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('cancellation_reason', models.TextField(blank=True, null=True)),
                ('is_auto_renew', models.BooleanField(default=True)),
                ('gateway_subscription_id', models.CharField(blank=True, max_length=300, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='monetization_tools_usersubscription_plan',
                    to='monetization_tools.subscriptionplan',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_usersubscription_user',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_usersubscription_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_user_subscriptions', 'ordering': ['-created_at']},
        ),

        # ── PaymentTransaction ─────────────────────────────────────────────
        migrations.CreateModel(
            name='PaymentTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('txn_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('gateway', models.CharField(max_length=20)),
                ('gateway_txn_id', models.CharField(blank=True, max_length=300, null=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='BDT', max_length=5)),
                ('status', models.CharField(max_length=15, default='initiated')),
                ('purpose', models.CharField(max_length=30, default='other')),
                ('related_object_id', models.CharField(blank=True, max_length=100, null=True)),
                ('gateway_response', models.JSONField(blank=True, default=dict)),
                ('failure_reason', models.TextField(blank=True, null=True)),
                ('initiated_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_paymenttransaction_user',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_paymenttransaction_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_payment_transactions', 'ordering': ['-initiated_at']},
        ),

        # ── UserLevel ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='UserLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('current_level', models.PositiveSmallIntegerField(default=1)),
                ('current_xp', models.PositiveBigIntegerField(default=0)),
                ('total_xp_earned', models.PositiveBigIntegerField(default=0)),
                ('xp_to_next_level', models.PositiveBigIntegerField(default=100)),
                ('level_title', models.CharField(default='Newcomer', max_length=100)),
                ('badges_count', models.PositiveSmallIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monetization_tools_userlevel_user',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_userlevel_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_user_levels'},
        ),

        # ── ABTest ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ABTest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('test_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('status', models.CharField(max_length=15, default='draft')),
                ('winner_criteria', models.CharField(max_length=10, default='ctr')),
                ('variants', models.JSONField(default=list)),
                ('traffic_split', models.PositiveSmallIntegerField(default=50)),
                ('confidence_level', models.DecimalField(decimal_places=2, default='95.00', max_digits=5)),
                ('winner_variant', models.CharField(blank=True, max_length=100, null=True)),
                ('results_summary', models.JSONField(blank=True, default=dict)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='monetization_tools_abtest_tenant',
                    to='tenants.tenant', db_index=True,
                )),
            ],
            options={'db_table': 'mt_ab_tests', 'ordering': ['-created_at']},
        ),

        # ── Indexes ────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='adcampaign',
            index=models.Index(fields=['status', 'start_date'], name='mt_campaign_status_idx'),
        ),
        migrations.AddIndex(
            model_name='offer',
            index=models.Index(fields=['offerwall', 'status'], name='mt_offer_wall_status_idx'),
        ),
        migrations.AddIndex(
            model_name='offercompletion',
            index=models.Index(fields=['user', 'status'], name='mt_completion_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='rewardtransaction',
            index=models.Index(fields=['user', '-created_at'], name='mt_reward_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='usersubscription',
            index=models.Index(fields=['user', 'status'], name='mt_sub_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='paymenttransaction',
            index=models.Index(fields=['user', 'status'], name='mt_pay_user_status_idx'),
        ),
    ]
