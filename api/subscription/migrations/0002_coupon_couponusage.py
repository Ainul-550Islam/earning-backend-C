"""
Migration: Add Coupon and CouponUsage models.
Generated manually – run after 0001_initial.
"""
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscription", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Coupon",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(help_text="Case-insensitive coupon code.", max_length=50, unique=True, verbose_name="coupon code")),
                ("description", models.CharField(blank=True, max_length=255, verbose_name="description")),
                ("discount_type", models.CharField(choices=[("percent", "Percentage"), ("fixed", "Fixed Amount")], default="percent", max_length=10, verbose_name="discount type")),
                ("discount_value", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="discount value")),
                ("currency", models.CharField(blank=True, choices=[("USD", "US Dollar"), ("EUR", "Euro"), ("GBP", "British Pound"), ("BDT", "Bangladeshi Taka"), ("INR", "Indian Rupee"), ("AUD", "Australian Dollar"), ("CAD", "Canadian Dollar")], default="USD", max_length=3, verbose_name="currency")),
                ("min_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="minimum order amount")),
                ("is_active", models.BooleanField(default=True, verbose_name="active")),
                ("valid_from", models.DateTimeField(default=django.utils.timezone.now, verbose_name="valid from")),
                ("valid_until", models.DateTimeField(blank=True, null=True, verbose_name="valid until")),
                ("max_uses", models.PositiveIntegerField(blank=True, null=True, verbose_name="max uses")),
                ("max_uses_per_user", models.PositiveSmallIntegerField(default=1, verbose_name="max uses per user")),
                ("times_used", models.PositiveIntegerField(default=0, editable=False, verbose_name="times used")),
                ("applicable_plans", models.ManyToManyField(blank=True, related_name="coupons", to="subscription.subscriptionplan", verbose_name="applicable plans")),
            ],
            options={"verbose_name": "coupon", "verbose_name_plural": "coupons", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="coupon",
            index=models.Index(fields=["code"], name="sub_coupon_code_idx"),
        ),
        migrations.AddIndex(
            model_name="coupon",
            index=models.Index(fields=["is_active", "valid_until"], name="sub_coupon_active_idx"),
        ),
        migrations.CreateModel(
            name="CouponUsage",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("discount_applied", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="discount applied")),
                ("coupon", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="usages", to="subscription.coupon", verbose_name="coupon")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="coupon_usages", to=settings.AUTH_USER_MODEL, verbose_name="user")),
                ("subscription", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="coupon_usages", to="subscription.usersubscription", verbose_name="subscription")),
            ],
            options={"verbose_name": "coupon usage", "verbose_name_plural": "coupon usages", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="couponusage",
            index=models.Index(fields=["coupon", "user"], name="sub_couponusage_idx"),
        ),
    ]
