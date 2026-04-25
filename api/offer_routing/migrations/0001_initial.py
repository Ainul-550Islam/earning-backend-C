"""
Initial migration for offer routing system.

This migration creates all the necessary tables for the comprehensive
offer routing system including models, services, and analytics.
"""

import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # Core Models
        migrations.CreateModel(
            name='OfferRoute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Route Name')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('priority', models.PositiveIntegerField(default=5, verbose_name='Priority')),
                ('max_offers', models.PositiveIntegerField(default=10, verbose_name='Max Offers')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offer_routes', to='auth.user')),
            ],
            options={
                'verbose_name': 'Offer Route',
                'verbose_name_plural': 'Offer Routes',
                'db_table': 'offer_routing_routes',
                'ordering': ['-priority', 'name'],
            },
        ),
        
        migrations.CreateModel(
            name='RouteCondition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(max_length=100, verbose_name='Field Name')),
                ('operator', models.CharField(max_length=50, verbose_name='Operator')),
                ('value', models.TextField(verbose_name='Value')),
                ('is_required', models.BooleanField(default=True, verbose_name='Is Required')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conditions', to='offer_routing.offerroute')),
            ],
            options={
                'verbose_name': 'Route Condition',
                'verbose_name_plural': 'Route Conditions',
                'db_table': 'offer_routing_route_conditions',
            },
        ),
        
        migrations.CreateModel(
            name='RouteAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(max_length=50, verbose_name='Action Type')),
                ('action_value', models.TextField(verbose_name='Action Value')),
                ('priority', models.PositiveIntegerField(default=1, verbose_name='Priority')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='offer_routing.offerroute')),
            ],
            options={
                'verbose_name': 'Route Action',
                'verbose_name_plural': 'Route Actions',
                'db_table': 'offer_routing_route_actions',
                'ordering': ['priority', 'id'],
            },
        ),
        
        # Targeting Models
        migrations.CreateModel(
            name='GeoRouteRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('country', models.CharField(max_length=10, blank=True, null=True, verbose_name='Country')),
                ('region', models.CharField(max_length=100, blank=True, null=True, verbose_name='Region')),
                ('city', models.CharField(max_length=100, blank=True, null=True, verbose_name='City')),
                ('is_include', models.BooleanField(default=True, verbose_name='Is Include')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='geo_rules', to='offer_routing.offerroute')),
            ],
            options={
                'verbose_name': 'Geo Route Rule',
                'verbose_name_plural': 'Geo Route Rules',
                'db_table': 'offer_routing_geo_rules',
            },
        ),
        
        migrations.CreateModel(
            name='DeviceRouteRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_type', models.CharField(max_length=50, verbose_name='Device Type')),
                ('os_type', models.CharField(max_length=50, blank=True, null=True, verbose_name='OS Type')),
                ('browser_type', models.CharField(max_length=50, blank=True, null=True, verbose_name='Browser Type')),
                ('is_include', models.BooleanField(default=True, verbose_name='Is Include')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_rules', to='offer_routing.offerroute')),
            ],
            options={
                'verbose_name': 'Device Route Rule',
                'verbose_name_plural': 'Device Route Rules',
                'db_table': 'offer_routing_device_rules',
            },
        ),
        
        migrations.CreateModel(
            name='UserSegmentRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('segment_type', models.CharField(max_length=50, verbose_name='Segment Type')),
                ('segment_value', models.CharField(max_length=255, verbose_name='Segment Value')),
                ('operator', models.CharField(max_length=50, verbose_name='Operator')),
                ('is_include', models.BooleanField(default=True, verbose_name='Is Include')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='segment_rules', to='offer_routing.offerroute')),
            ],
            options={
                'verbose_name': 'User Segment Rule',
                'verbose_name_plural': 'User Segment Rules',
                'db_table': 'offer_routing_segment_rules',
            },
        ),
        
        migrations.CreateModel(
            name='TimeRouteRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_time', models.DateTimeField(blank=True, null=True, verbose_name='Start Time')),
                ('end_time', models.DateTimeField(blank=True, null=True, verbose_name='End Time')),
                ('start_hour', models.IntegerField(blank=True, null=True, verbose_name='Start Hour')),
                ('end_hour', models.IntegerField(blank=True, null=True, verbose_name='End Hour')),
                ('days_of_week', models.CharField(blank=True, max_length=20, null=True, verbose_name='Days of Week')),
                ('is_include', models.BooleanField(default=True, verbose_name='Is Include')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='time_rules', to='offer_routing.offerroute')),
            ],
            options={
                'verbose_name': 'Time Route Rule',
                'verbose_name_plural': 'Time Route Rules',
                'db_table': 'offer_routing_time_rules',
            },
        ),
        
        migrations.CreateModel(
            name='BehaviorRouteRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(max_length=50, verbose_name='Event Type')),
                ('event_count_min', models.IntegerField(blank=True, null=True, verbose_name='Event Count Min')),
                ('event_count_max', models.IntegerField(blank=True, null=True, verbose_name='Event Count Max')),
                ('time_period_hours', models.IntegerField(default=24, verbose_name='Time Period Hours')),
                ('is_include', models.BooleanField(default=True, verbose_name='Is Include')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='behavior_rules', to='offer_routing.offerroute')),
            ],
            options={
                'verbose_name': 'Behavior Route Rule',
                'verbose_name_plural': 'Behavior Route Rules',
                'db_table': 'offer_routing_behavior_rules',
            },
        ),
        
        # Scoring Models
        migrations.CreateModel(
            name='OfferScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.FloatField(verbose_name='Score')),
                ('epc', models.FloatField(default=0.0, verbose_name='EPC')),
                ('cr', models.FloatField(default=0.0, verbose_name='Conversion Rate')),
                ('relevance', models.FloatField(default=0.0, verbose_name='Relevance')),
                ('freshness', models.FloatField(default=0.0, verbose_name='Freshness')),
                ('calculated_at', models.DateTimeField(auto_now=True, verbose_name='Calculated At')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', to='offer_routing.offerroute')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='offer_scores', to='auth.user')),
            ],
            options={
                'verbose_name': 'Offer Score',
                'verbose_name_plural': 'Offer Scores',
                'db_table': 'offer_routing_scores',
                'ordering': ['-calculated_at'],
            },
        ),
        
        migrations.CreateModel(
            name='OfferScoreConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('epc_weight', models.FloatField(default=0.4, verbose_name='EPC Weight')),
                ('cr_weight', models.FloatField(default=0.3, verbose_name='CR Weight')),
                ('relevance_weight', models.FloatField(default=0.2, verbose_name='Relevance Weight')),
                ('freshness_weight', models.FloatField(default=0.1, verbose_name='Freshness Weight')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_configs', to='offer_routing.offerroute')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_configs', to='auth.user')),
            ],
            options={
                'verbose_name': 'Offer Score Config',
                'verbose_name_plural': 'Offer Score Configs',
                'db_table': 'offer_routing_score_configs',
            },
        ),
        
        migrations.CreateModel(
            name='GlobalOfferRank',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rank_score', models.FloatField(verbose_name='Rank Score')),
                ('rank_position', models.IntegerField(verbose_name='Rank Position')),
                ('rank_date', models.DateField(verbose_name='Rank Date')),
                ('calculated_at', models.DateTimeField(auto_now=True, verbose_name='Calculated At')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='global_ranks', to='offer_routing.offerroute')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='global_ranks', to='auth.user')),
            ],
            options={
                'verbose_name': 'Global Offer Rank',
                'verbose_name_plural': 'Global Offer Ranks',
                'db_table': 'offer_routing_global_ranks',
                'ordering': ['rank_position'],
            },
        ),
        
        migrations.CreateModel(
            name='UserOfferHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed_at', models.DateTimeField(blank=True, null=True, verbose_name='Viewed At')),
                ('clicked_at', models.DateTimeField(blank=True, null=True, verbose_name='Clicked At')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Completed At')),
                ('conversion_value', models.DecimalField(blank=True, decimal_places=2, default=0.0, max_digits=10, verbose_name='Conversion Value')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_history', to='offer_routing.offerroute')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='route_history', to='offer_routing.offerroute')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offer_history', to='auth.user')),
            ],
            options={
                'verbose_name': 'User Offer History',
                'verbose_name_plural': 'User Offer Histories',
                'db_table': 'offer_routing_user_history',
                'ordering': ['-created_at'],
            },
        ),
        
        migrations.CreateModel(
            name='OfferAffinityScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=100, verbose_name='Category')),
                ('score', models.FloatField(verbose_name='Score')),
                ('confidence', models.FloatField(default=0.0, verbose_name='Confidence')),
                ('calculated_at', models.DateTimeField(auto_now=True, verbose_name='Calculated At')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Expires At')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='affinity_scores', to='auth.user')),
            ],
            options={
                'verbose_name': 'Offer Affinity Score',
                'verbose_name_plural': 'Offer Affinity Scores',
                'db_table': 'offer_routing_affinity_scores',
                'ordering': ['-score', '-confidence'],
            },
        ),
        
        # Personalization Models
        migrations.CreateModel(
            name='UserPreferenceVector',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category_weights', models.JSONField(default=dict, verbose_name='Category Weights')),
                ('feature_weights', models.JSONField(default=dict, verbose_name='Feature Weights')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Expires At')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='preference_vectors', to='auth.user')),
            ],
            options={
                'verbose_name': 'User Preference Vector',
                'verbose_name_plural': 'User Preference Vectors',
                'db_table': 'offer_routing_preference_vectors',
            },
        ),
        
        migrations.CreateModel(
            name='ContextualSignal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signal_type', models.CharField(max_length=50, verbose_name='Signal Type')),
                ('value', models.TextField(verbose_name='Value')),
                ('weight', models.FloatField(default=1.0, verbose_name='Weight')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('expires_at', models.DateTimeField(verbose_name='Expires At')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contextual_signals', to='auth.user')),
            ],
            options={
                'verbose_name': 'Contextual Signal',
                'verbose_name_plural': 'Contextual Signals',
                'db_table': 'offer_routing_contextual_signals',
                'ordering': ['-created_at'],
            },
        ),
        
        migrations.CreateModel(
            name='PersonalizationConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('algorithm', models.CharField(default='hybrid', max_length=50, verbose_name='Algorithm')),
                ('collaborative_weight', models.FloatField(default=0.4, verbose_name='Collaborative Weight')),
                ('content_based_weight', models.FloatField(default=0.3, verbose_name='Content-Based Weight')),
                ('hybrid_weight', models.FloatField(default=0.3, verbose_name='Hybrid Weight')),
                ('min_affinity_score', models.FloatField(default=0.1, verbose_name='Min Affinity Score')),
                ('max_offers_per_user', models.IntegerField(default=50, verbose_name='Max Offers Per User')),
                ('real_time_enabled', models.BooleanField(default=True, verbose_name='Real-Time Enabled')),
                ('context_signals_enabled', models.BooleanField(default=True, verbose_name='Context Signals Enabled')),
                ('machine_learning_enabled', models.BooleanField(default=False, verbose_name='Machine Learning Enabled')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personalization_configs', to='auth.user')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personalization_configs', to='auth.user')),
            ],
            options={
                'verbose_name': 'Personalization Config',
                'verbose_name_plural': 'Personalization Configs',
                'db_table': 'offer_routing_personalization_configs',
            },
        ),
        
        # Cap Models
        migrations.CreateModel(
            name='OfferRoutingCap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cap_type', models.CharField(max_length=20, verbose_name='Cap Type')),
                ('cap_value', models.IntegerField(verbose_name='Cap Value')),
                ('current_count', models.IntegerField(default=0, verbose_name='Current Count')),
                ('reset_date', models.DateTimeField(blank=True, null=True, verbose_name='Reset Date')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='routing_caps', to='offer_routing.offerroute')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='routing_caps', to='auth.user')),
            ],
            options={
                'verbose_name': 'Offer Routing Cap',
                'verbose_name_plural': 'Offer Routing Caps',
                'db_table': 'offer_routing_caps',
            },
        ),
        
        migrations.CreateModel(
            name='UserOfferCap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cap_type', models.CharField(max_length=20, verbose_name='Cap Type')),
                ('max_shows_per_day', models.IntegerField(verbose_name='Max Shows Per Day')),
                ('shown_today', models.IntegerField(default=0, verbose_name='Shown Today')),
                ('last_shown_at', models.DateTimeField(blank=True, null=True, verbose_name='Last Shown At')),
                ('reset_date', models.DateField(verbose_name='Reset Date')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_caps', to='offer_routing.offerroute')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offer_caps', to='auth.user')),
            ],
            options={
                'verbose_name': 'User Offer Cap',
                'verbose_name_plural': 'User Offer Caps',
                'db_table': 'offer_routing_user_caps',
            },
        ),
        
        migrations.CreateModel(
            name='CapOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('override_type', models.CharField(max_length=20, verbose_name='Override Type')),
                ('override_cap', models.IntegerField(verbose_name='Override Cap')),
                ('reason', models.TextField(blank=True, null=True, verbose_name='Reason')),
                ('valid_from', models.DateTimeField(verbose_name='Valid From')),
                ('valid_to', models.DateTimeField(verbose_name='Valid To')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cap_overrides', to='offer_routing.offerroute')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cap_overrides', to='auth.user')),
            ],
            options={
                'verbose_name': 'Cap Override',
                'verbose_name_plural': 'Cap Overrides',
                'db_table': 'offer_routing_cap_overrides',
            },
        ),
        
        # Fallback Models
        migrations.CreateModel(
            name='FallbackRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('fallback_type', models.CharField(max_length=50, verbose_name='Fallback Type')),
                ('priority', models.PositiveIntegerField(default=5, verbose_name='Priority')),
                ('category', models.CharField(blank=True, max_length=100, null=True, verbose_name='Category')),
                ('network', models.CharField(blank=True, max_length=100, null=True, verbose_name='Network')),
                ('promotion_code', models.CharField(blank=True, max_length=50, null=True, verbose_name='Promotion Code')),
                ('start_time', models.DateTimeField(blank=True, null=True, verbose_name='Start Time')),
                ('end_time', models.DateTimeField(blank=True, null=True, verbose_name='End Time')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fallback_rules', to='auth.user')),
            ],
            options={
                'verbose_name': 'Fallback Rule',
                'verbose_name_plural': 'Fallback Rules',
                'db_table': 'offer_routing_fallback_rules',
                'ordering': ['priority', 'name'],
            },
        ),
        
        migrations.CreateModel(
            name='DefaultOfferPool',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('pool_type', models.CharField(max_length=50, verbose_name='Pool Type')),
                ('max_offers', models.IntegerField(default=10, verbose_name='Max Offers')),
                ('rotation_strategy', models.CharField(default='random', max_length=20, verbose_name='Rotation Strategy')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('offers', models.ManyToManyField(blank=True, related_name='offer_pools', to='offer_routing.offerroute')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offer_pools', to='auth.user')),
            ],
            options={
                'verbose_name': 'Default Offer Pool',
                'verbose_name_plural': 'Default Offer Pools',
                'db_table': 'offer_routing_offer_pools',
                'ordering': ['name'],
            },
        ),
        
        migrations.CreateModel(
            name='EmptyResultHandler',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('action_type', models.CharField(max_length=50, verbose_name='Action Type')),
                ('action_value', models.TextField(blank=True, null=True, verbose_name='Action Value')),
                ('redirect_url', models.URLField(blank=True, null=True, verbose_name='Redirect URL')),
                ('custom_message', models.TextField(blank=True, null=True, verbose_name='Custom Message')),
                ('priority', models.PositiveIntegerField(default=5, verbose_name='Priority')),
                ('conditions', models.JSONField(default=dict, verbose_name='Conditions')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('is_active', models.BooleanField(default=True, verbose_name='Is Active')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='empty_result_handlers', to='auth.user')),
            ],
            options={
                'verbose_name': 'Empty Result Handler',
                'verbose_name_plural': 'Empty Result Handlers',
                'db_table': 'offer_routing_empty_handlers',
                'ordering': ['priority', 'name'],
            },
        ),
        
        # A/B Test Models
        migrations.CreateModel(
            name='RoutingABTest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('split_percentage', models.IntegerField(default=50, verbose_name='Split Percentage')),
                ('min_sample_size', models.IntegerField(verbose_name='Min Sample Size')),
                ('duration_hours', models.IntegerField(verbose_name='Duration Hours')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='Started At')),
                ('ended_at', models.DateTimeField(blank=True, null=True, verbose_name='Ended At')),
                ('winner', models.CharField(blank=True, max_length=20, null=True, verbose_name='Winner')),
                ('confidence', models.FloatField(blank=True, null=True, verbose_name='Confidence')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('is_active', models.BooleanField(default=False, verbose_name='Is Active')),
                ('control_route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='control_tests', to='offer_routing.offerroute')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_tests', to='auth.user')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ab_tests', to='auth.user')),
                ('variant_route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variant_tests', to='offer_routing.offerroute')),
            ],
            options={
                'verbose_name': 'Routing A/B Test',
                'verbose_name_plural': 'Routing A/B Tests',
                'db_table': 'offer_routing_ab_tests',
                'ordering': ['-created_at'],
            },
        ),
        
        migrations.CreateModel(
            name='ABTestAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('variant', models.CharField(max_length=20, verbose_name='Variant')),
                ('impressions', models.IntegerField(default=0, verbose_name='Impressions')),
                ('clicks', models.IntegerField(default=0, verbose_name='Clicks')),
                ('conversions', models.IntegerField(default=0, verbose_name='Conversions')),
                ('revenue', models.DecimalField(decimal_places=2, default=0.0, max_digits=10, verbose_name='Revenue')),
                ('assigned_at', models.DateTimeField(auto_now_add=True, verbose_name='Assigned At')),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='offer_routing.routingabtest')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ab_test_assignments', to='auth.user')),
            ],
            options={
                'verbose_name': 'A/B Test Assignment',
                'verbose_name_plural': 'A/B Test Assignments',
                'db_table': 'offer_routing_ab_assignments',
                'unique_together': [('user', 'test')],
                'ordering': ['-assigned_at'],
            },
        ),
        
        migrations.CreateModel(
            name='ABTestResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('control_impressions', models.IntegerField(verbose_name='Control Impressions')),
                ('control_clicks', models.IntegerField(verbose_name='Control Clicks')),
                ('control_conversions', models.IntegerField(verbose_name='Control Conversions')),
                ('control_revenue', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Control Revenue')),
                ('control_cr', models.FloatField(verbose_name='Control CR')),
                ('variant_impressions', models.IntegerField(verbose_name='Variant Impressions')),
                ('variant_clicks', models.IntegerField(verbose_name='Variant Clicks')),
                ('variant_conversions', models.IntegerField(verbose_name='Variant Conversions')),
                ('variant_revenue', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Variant Revenue')),
                ('variant_cr', models.FloatField(verbose_name='Variant CR')),
                ('cr_difference', models.FloatField(verbose_name='CR Difference')),
                ('z_score', models.FloatField(verbose_name='Z Score')),
                ('p_value', models.FloatField(verbose_name='P Value')),
                ('is_significant', models.BooleanField(verbose_name='Is Significant')),
                ('confidence_level', models.FloatField(verbose_name='Confidence Level')),
                ('effect_size', models.FloatField(verbose_name='Effect Size')),
                ('winner', models.CharField(max_length=20, verbose_name='Winner')),
                ('winner_confidence', models.FloatField(verbose_name='Winner Confidence')),
                ('analyzed_at', models.DateTimeField(verbose_name='Analyzed At')),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='offer_routing.routingabtest')),
            ],
            options={
                'verbose_name': 'A/B Test Result',
                'verbose_name_plural': 'A/B Test Results',
                'db_table': 'offer_routing_ab_results',
                'ordering': ['-analyzed_at'],
            },
        ),
        
        # Analytics Models
        migrations.CreateModel(
            name='RoutingDecisionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('offer_id', models.IntegerField(verbose_name='Offer ID')),
                ('score', models.FloatField(verbose_name='Score')),
                ('response_time_ms', models.FloatField(verbose_name='Response Time (ms)')),
                ('cache_hit', models.BooleanField(default=False, verbose_name='Cache Hit')),
                ('personalization_applied', models.BooleanField(default=False, verbose_name='Personalization Applied')),
                ('caps_checked', models.BooleanField(default=False, verbose_name='Caps Checked')),
                ('fallback_used', models.BooleanField(default=False, verbose_name='Fallback Used')),
                ('ab_test_variant', models.CharField(blank=True, max_length=20, null=True, verbose_name='A/B Test Variant')),
                ('metadata', models.JSONField(default=dict, verbose_name='Metadata')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='routing_decisions', to='auth.user')),
            ],
            options={
                'verbose_name': 'Routing Decision Log',
                'verbose_name_plural': 'Routing Decision Logs',
                'db_table': 'offer_routing_decision_logs',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'created_at'], name='idx_user_created_at_2001'),
                    models.Index(fields=['offer_id', 'created_at'], name='idx_offer_id_created_at_2002'),
                    models.Index(fields=['created_at'], name='idx_created_at_2003'),
                ],
            },
        ),
        
        migrations.CreateModel(
            name='RoutingInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('insight_type', models.CharField(max_length=50, verbose_name='Insight Type')),
                ('title', models.CharField(max_length=255, verbose_name='Title')),
                ('description', models.TextField(verbose_name='Description')),
                ('severity', models.CharField(max_length=20, verbose_name='Severity')),
                ('recommendation', models.TextField(blank=True, null=True, verbose_name='Recommendation')),
                ('metadata', models.JSONField(default=dict, verbose_name='Metadata')),
                ('is_actionable', models.BooleanField(default=True, verbose_name='Is Actionable')),
                ('is_resolved', models.BooleanField(default=False, verbose_name='Is Resolved')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='Expires At')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='routing_insights', to='auth.user')),
            ],
            options={
                'verbose_name': 'Routing Insight',
                'verbose_name_plural': 'Routing Insights',
                'db_table': 'offer_routing_insights',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['tenant', 'insight_type', 'created_at'], name='idx_tenant_insight_type_cr_e88'),
                    models.Index(fields=['is_actionable', 'is_resolved'], name='idx_is_actionable_is_resol_221'),
                ],
            },
        ),
        
        migrations.CreateModel(
            name='RoutePerformanceStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Date')),
                ('impressions', models.IntegerField(default=0, verbose_name='Impressions')),
                ('clicks', models.IntegerField(default=0, verbose_name='Clicks')),
                ('conversions', models.IntegerField(default=0, verbose_name='Conversions')),
                ('revenue', models.DecimalField(decimal_places=2, default=0.0, max_digits=10, verbose_name='Revenue')),
                ('avg_response_time_ms', models.FloatField(default=0.0, verbose_name='Avg Response Time (ms)')),
                ('cache_hit_rate', models.FloatField(default=0.0, verbose_name='Cache Hit Rate')),
                ('click_through_rate', models.FloatField(default=0.0, verbose_name='Click Through Rate')),
                ('conversion_rate', models.FloatField(default=0.0, verbose_name='Conversion Rate')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('offer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='performance_stats', to='offer_routing.offerroute')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='performance_stats', to='auth.user')),
            ],
            options={
                'verbose_name': 'Route Performance Stat',
                'verbose_name_plural': 'Route Performance Stats',
                'db_table': 'offer_routing_performance_stats',
                'ordering': ['-date'],
                'unique_together': [('tenant', 'offer', 'date')],
            },
        ),
        
        migrations.CreateModel(
            name='OfferExposureStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Date')),
                ('aggregation_type', models.CharField(default='daily', max_length=20, verbose_name='Aggregation Type')),
                ('unique_users_exposed', models.IntegerField(default=0, verbose_name='Unique Users Exposed')),
                ('total_exposures', models.IntegerField(default=0, verbose_name='Total Exposures')),
                ('repeat_exposures', models.IntegerField(default=0, verbose_name='Repeat Exposures')),
                ('avg_exposures_per_user', models.FloatField(default=0.0, verbose_name='Avg Exposures Per User')),
                ('max_exposures_per_user', models.IntegerField(default=0, verbose_name='Max Exposures Per User')),
                ('geographic_distribution', models.JSONField(default=dict, verbose_name='Geographic Distribution')),
                ('device_distribution', models.JSONField(default=dict, verbose_name='Device Distribution')),
                ('hourly_distribution', models.JSONField(default=dict, verbose_name='Hourly Distribution')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exposure_stats', to='offer_routing.offerroute')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exposure_stats', to='auth.user')),
            ],
            options={
                'verbose_name': 'Offer Exposure Stat',
                'verbose_name_plural': 'Offer Exposure Stats',
                'db_table': 'offer_routing_exposure_stats',
                'ordering': ['-date'],
                'unique_together': [('tenant', 'offer', 'date', 'aggregation_type')],
            },
        ),
    ]
