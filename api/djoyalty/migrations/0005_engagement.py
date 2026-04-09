# api/djoyalty/migrations/0005_engagement.py
"""
Migration: DailyStreak, StreakReward, Badge, UserBadge,
Challenge, ChallengeParticipant, Milestone, UserMilestone
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('djoyalty', '0004_earn_redemption'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # DailyStreak
        migrations.CreateModel(
            name='DailyStreak',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_streak', models.PositiveIntegerField(default=0)),
                ('longest_streak', models.PositiveIntegerField(default=0)),
                ('last_activity_date', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('started_at', models.DateField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_streak', to='djoyalty.customer')),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_dailystreak_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),
        migrations.AlterUniqueTogether(name='dailystreak', unique_together={('tenant', 'customer')}),

        # StreakReward
        migrations.CreateModel(
            name='StreakReward',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('milestone_days', models.PositiveIntegerField()),
                ('points_awarded', models.DecimalField(decimal_places=2, max_digits=12)),
                ('awarded_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='streak_rewards', to='djoyalty.customer')),
                ('streak', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rewards', to='djoyalty.dailystreak')),
            ],
            options={'app_label': 'djoyalty'},
        ),
        migrations.AlterUniqueTogether(name='streakreward', unique_together={('customer', 'milestone_days')}),

        # Badge
        migrations.CreateModel(
            name='Badge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True, null=True)),
                ('icon', models.CharField(default='🏅', max_length=8)),
                ('trigger', models.CharField(choices=[('transaction_count', '💳 Transaction Count'), ('total_spend', '💰 Total Spend'), ('streak_days', '🔥 Streak Days'), ('referrals', '👥 Referrals'), ('tier_reached', '🏆 Tier Reached'), ('custom', '⚡ Custom')], db_index=True, max_length=32)),
                ('threshold', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('points_reward', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('is_unique', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_badge_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty', 'ordering': ['name']},
        ),

        # UserBadge
        migrations.CreateModel(
            name='UserBadge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('awarded_at', models.DateTimeField(auto_now_add=True)),
                ('points_awarded', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('badge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_badges', to='djoyalty.badge')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_badges', to='djoyalty.customer')),
            ],
            options={'app_label': 'djoyalty'},
        ),
        migrations.AlterUniqueTogether(name='userbadge', unique_together={('customer', 'badge')}),

        # Challenge
        migrations.CreateModel(
            name='Challenge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True, null=True)),
                ('challenge_type', models.CharField(choices=[('spend', '💰 Spend Target'), ('visit', '📍 Visit Count'), ('referral', '👥 Referral Count'), ('custom', '⚡ Custom')], max_length=32)),
                ('target_value', models.DecimalField(decimal_places=2, max_digits=12)),
                ('points_reward', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('status', models.CharField(choices=[('active', '🟢 Active'), ('completed', '✅ Completed'), ('failed', '❌ Failed'), ('upcoming', '📅 Upcoming'), ('expired', '⌛ Expired')], db_index=True, default='upcoming', max_length=16)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('max_participants', models.PositiveIntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_challenge_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # ChallengeParticipant
        migrations.CreateModel(
            name='ChallengeParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('progress', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('status', models.CharField(db_index=True, default='active', max_length=16)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('points_awarded', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('challenge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participants', to='djoyalty.challenge')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='challenge_participations', to='djoyalty.customer')),
            ],
            options={'app_label': 'djoyalty'},
        ),
        migrations.AlterUniqueTogether(name='challengeparticipant', unique_together={('challenge', 'customer')}),

        # Milestone
        migrations.CreateModel(
            name='Milestone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('description', models.TextField(blank=True, null=True)),
                ('milestone_type', models.CharField(choices=[('total_spend', 'Total Spend'), ('total_points', 'Total Points'), ('transaction_count', 'Transaction Count'), ('streak_days', 'Streak Days')], max_length=32)),
                ('threshold', models.DecimalField(decimal_places=2, max_digits=12)),
                ('points_reward', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='djoyalty_milestone_tenant', to='tenants.tenant')),
            ],
            options={'app_label': 'djoyalty'},
        ),

        # UserMilestone
        migrations.CreateModel(
            name='UserMilestone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reached_at', models.DateTimeField(auto_now_add=True)),
                ('points_awarded', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_milestones', to='djoyalty.customer')),
                ('milestone', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_milestones', to='djoyalty.milestone')),
            ],
            options={'app_label': 'djoyalty'},
        ),
        migrations.AlterUniqueTogether(name='usermilestone', unique_together={('customer', 'milestone')}),
    ]
