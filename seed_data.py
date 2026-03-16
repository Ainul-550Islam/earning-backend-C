"""
Fixed Seed Script v2 - correct field names
Run: exec(open('seed_data.py', encoding='utf-8').read())
"""

import random
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()
now = timezone.now()

print("Seed script starting...")

# ============================================================
# 1. USERS
# ============================================================
print("\n[1] Users...")

users = []
user_data = [
    {"username": "rahul_bd",  "email": "rahul@example.com",  "first_name": "Rahul",  "last_name": "Islam"},
    {"username": "farida99",  "email": "farida@example.com", "first_name": "Farida", "last_name": "Begum"},
    {"username": "karim_x",   "email": "karim@example.com",  "first_name": "Karim",  "last_name": "Hossain"},
    {"username": "sumaiya_m", "email": "sumaiya@example.com","first_name": "Sumaiya","last_name": "Mim"},
    {"username": "tanvir007", "email": "tanvir@example.com", "first_name": "Tanvir", "last_name": "Ahmed"},
]

for ud in user_data:
    u, created = User.objects.get_or_create(
        username=ud["username"],
        defaults={
            "email": ud["email"],
            "first_name": ud["first_name"],
            "last_name": ud["last_name"],
            "balance": Decimal(str(round(random.uniform(10, 500), 2))),
            "total_earned": Decimal(str(round(random.uniform(50, 1000), 2))),
            "is_active": True,
        }
    )
    if created:
        u.set_password("Test1234!")
        u.save()
        print(f"  OK User: {u.username}")
    else:
        print(f"  SKIP User: {u.username}")
    users.append(u)

admin_user = User.objects.filter(username="naha").first()
if admin_user and admin_user not in users:
    users.insert(0, admin_user)

print(f"  Total users: {len(users)}")

# ============================================================
# 2. WALLET TRANSACTIONS
# ============================================================
print("\n[2] Wallet Transactions...")

try:
    from api.wallet.models import Wallet, WalletTransaction, Withdrawal

    for user in users:
        wallet, created = Wallet.objects.get_or_create(user=user)
        if created:
            print(f"  OK Wallet: {user.username}")

        for i in range(4):
            amt = Decimal(str(round(random.uniform(1, 100), 2)))
            bal = wallet.balance or Decimal("0.00")
            try:
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=amt,
                    type=random.choice(["credit", "debit"]),
                    status="completed",
                    description=f"Test transaction #{i+1}",
                    balance_before=bal,
                    balance_after=bal + amt,
                )
            except Exception as e:
                print(f"  WARN WalletTx: {e}")

    for user in users[:4]:
        try:
            Withdrawal.objects.get_or_create(
                user=user,
                defaults={
                    "amount": Decimal(str(round(random.uniform(5, 50), 2))),
                    "status": random.choice(["pending", "approved", "rejected"]),
                }
            )
        except Exception as e:
            print(f"  WARN Withdrawal: {e}")

    print("  OK Wallet done")
except Exception as e:
    print(f"  ERROR Wallet: {e}")

# ============================================================
# 3. TASKS
# ============================================================
print("\n[3] Tasks...")

try:
    from api.tasks.models import MasterTask, UserTaskCompletion

    task_data = [
        {"name": "Watch Video Ad",  "system_type": "video"},
        {"name": "Complete Survey", "system_type": "survey"},
        {"name": "Install App",     "system_type": "install"},
        {"name": "Sign Up Offer",   "system_type": "signup"},
        {"name": "Daily Check-in",  "system_type": "checkin"},
        {"name": "Refer a Friend",  "system_type": "referral"},
        {"name": "Play Mini Game",  "system_type": "game"},
    ]

    tasks = []
    for td in task_data:
        try:
            task, created = MasterTask.objects.get_or_create(
                name=td["name"],
                defaults={
                    "system_type": td["system_type"],
                    "is_active": True,
                    "description": f"Complete this task to earn rewards",
                    "rewards": {"amount": round(random.uniform(0.1, 5.0), 2), "currency": "USD"},
                    "constraints": {},
                    "task_metadata": {},
                    "ui_config": {},
                }
            )
            tasks.append(task)
            if created:
                print(f"  OK Task: {task.name}")
        except Exception as e:
            print(f"  WARN Task ({td['name']}): {e}")

    # Completions - check UserTaskCompletion fields first
    completion_fields = [f.name for f in UserTaskCompletion._meta.get_fields() if hasattr(f, 'column')]
    print(f"  Completion fields: {completion_fields}")

    for user in users:
        for task in random.sample(tasks, min(3, len(tasks))):
            try:
                defaults = {"status": random.choice(["completed", "pending", "approved"])}
                if "reward_amount" in completion_fields:
                    defaults["reward_amount"] = Decimal("1.00")
                if "completed_at" in completion_fields:
                    defaults["completed_at"] = now - timedelta(days=random.randint(0, 15))
                UserTaskCompletion.objects.get_or_create(user=user, task=task, defaults=defaults)
            except Exception as e:
                print(f"  WARN Completion: {e}")

    print("  OK Tasks done")
except Exception as e:
    print(f"  ERROR Tasks: {e}")

# ============================================================
# 4. ANALYTICS
# ============================================================
print("\n[4] Analytics...")

try:
    from api.analytics.models import UserAnalytics, RevenueAnalytics, Dashboard

    # UserAnalytics - per user per period
    for user in users:
        try:
            UserAnalytics.objects.get_or_create(
                user=user,
                period="monthly",
                period_start=now.date().replace(day=1),
                defaults={
                    "period_end": now.date(),
                    "login_count": random.randint(5, 30),
                    "active_days": random.randint(3, 28),
                    "tasks_completed": random.randint(2, 20),
                    "tasks_attempted": random.randint(5, 25),
                    "earnings_total": Decimal(str(round(random.uniform(5, 100), 2))),
                    "earnings_from_tasks": Decimal(str(round(random.uniform(2, 50), 2))),
                    "earnings_from_referrals": Decimal(str(round(random.uniform(0, 20), 2))),
                    "referrals_sent": random.randint(0, 5),
                    "referrals_joined": random.randint(0, 3),
                }
            )
        except Exception as e:
            print(f"  WARN UserAnalytics ({user.username}): {e}")

    # RevenueAnalytics - per period
    for i in range(30):
        day = now - timedelta(days=i)
        try:
            RevenueAnalytics.objects.get_or_create(
                period="daily",
                period_start=day.date(),
                defaults={
                    "period_end": day.date(),
                    "revenue_total": Decimal(str(round(random.uniform(100, 1000), 2))),
                    "revenue_by_source": {"ads": round(random.uniform(50, 500), 2), "offers": round(random.uniform(30, 300), 2)},
                    "cost_total": Decimal(str(round(random.uniform(20, 200), 2))),
                    "cost_breakdown": {},
                    "gross_profit": Decimal(str(round(random.uniform(80, 800), 2))),
                    "net_profit": Decimal(str(round(random.uniform(50, 600), 2))),
                    "profit_margin": round(random.uniform(0.3, 0.7), 2),
                    "active_users": random.randint(20, 200),
                    "total_withdrawals": Decimal(str(round(random.uniform(10, 100), 2))),
                }
            )
        except Exception as e:
            pass  # duplicate dates skip silently

    try:
        Dashboard.objects.get_or_create(
            name="Main Dashboard",
            defaults={"description": "Primary admin dashboard", "is_default": True, "created_by": users[0]}
        )
    except Exception as e:
        print(f"  WARN Dashboard: {e}")

    print("  OK Analytics done")
except Exception as e:
    print(f"  ERROR Analytics: {e}")

# ============================================================
# 5. REFERRAL
# ============================================================
print("\n[5] Referral...")

try:
    from api.referral.models import Referral, ReferralEarning

    for user in users[1:]:
        try:
            ref, created = Referral.objects.get_or_create(
                referred_user=user,
                defaults={
                    "referrer": users[0],
                    "signup_bonus_given": True,
                    "total_commission_earned": Decimal(str(round(random.uniform(1, 10), 2))),
                }
            )
            if created:
                print(f"  OK Referral: {users[0].username} -> {user.username}")
        except Exception as e:
            print(f"  WARN Referral: {e}")

    print("  OK Referral done")
except Exception as e:
    print(f"  ERROR Referral: {e}")

# ============================================================
# 6. KYC
# ============================================================
print("\n[6] KYC...")

try:
    from api.kyc.models import KYC

    for user in users[1:4]:
        try:
            KYC.objects.get_or_create(
                user=user,
                defaults={
                    "status": random.choice(["pending", "approved", "rejected"]),
                    "document_type": random.choice(["nid", "passport"]),
                    "full_name": f"{user.first_name} {user.last_name}",
                    "phone_number": f"017{random.randint(10000000, 99999999)}",
                    "country": "BD",
                    "city": "Dhaka",
                }
            )
            print(f"  OK KYC: {user.username}")
        except Exception as e:
            print(f"  WARN KYC {user.username}: {e}")

    print("  OK KYC done")
except Exception as e:
    print(f"  ERROR KYC: {e}")

# ============================================================
# 7. CMS
# ============================================================
print("\n[7] CMS...")

try:
    from api.cms.models import SiteSettings, FAQCategory, FAQ

    # SiteSettings uses key-value format
    settings_data = [
        ("site_name", "EarnApp", "text", "general"),
        ("site_tagline", "Earn Money Online", "text", "general"),
        ("maintenance_mode", "false", "boolean", "system"),
        ("min_withdrawal", "5.00", "number", "payment"),
        ("referral_bonus", "2.00", "number", "referral"),
    ]
    for key, value, dtype, category in settings_data:
        try:
            SiteSettings.objects.get_or_create(
                key=key,
                defaults={"value": value, "data_type": dtype, "category": category, "is_public": True}
            )
        except Exception as e:
            print(f"  WARN Setting ({key}): {e}")
    print("  OK SiteSettings done")

    try:
        cat, _ = FAQCategory.objects.get_or_create(name="General", defaults={"order": 1})
        faqs = [
            ("How to withdraw money?", "Go to Withdrawal section and enter amount.", "How to withdraw"),
            ("What is minimum withdrawal?", "Minimum $5 can be withdrawn.", "Minimum $5"),
            ("How much is referral bonus?", "You get $2 for each referral.", "$2 per referral"),
            ("How to complete tasks?", "Go to Tasks section and complete any task.", "Visit Tasks section"),
        ]
        for q, detailed, short in faqs:
            FAQ.objects.get_or_create(
                question=q,
                defaults={
                    "short_answer": short,
                    "detailed_answer": detailed,
                    "category": cat,
                    "is_active": True,
                    "slug": q.lower().replace(" ", "-").replace("?", "")[:50],
                }
            )
        print("  OK FAQs done")
    except Exception as e:
        print(f"  WARN FAQ: {e}")

except Exception as e:
    print(f"  ERROR CMS: {e}")

# ============================================================
# 8. SUPPORT TICKETS
# ============================================================
print("\n[8] Support Tickets...")

try:
    from api.support.models import SupportTicket

    tickets = [
        ("Withdrawal not received", "I made a withdrawal 3 days ago but didn't receive it."),
        ("Account banned wrongly",  "My account was banned but I didn't do anything wrong."),
        ("Task not credited",       "I completed a task but reward was not added."),
        ("App crash issue",         "The app crashes when I try to open offers."),
    ]

    for user in users[:4]:
        subject, desc = random.choice(tickets)
        try:
            SupportTicket.objects.create(
                user=user,
                subject=subject,
                description=desc,
                status=random.choice(["open", "in_progress", "resolved"]),
                priority=random.choice(["low", "medium", "high"]),
            )
            print(f"  OK Ticket: {user.username}")
        except Exception as e:
            print(f"  WARN Ticket: {e}")

    print("  OK Support done")
except Exception as e:
    print(f"  ERROR Support: {e}")

# ============================================================
# 9. FRAUD DETECTION
# ============================================================
print("\n[9] Fraud Detection...")

try:
    from api.fraud_detection.models import FraudRule, UserRiskProfile

    for rname in ["Multiple Account Detection", "VPN/Proxy Detection", "Rapid Task Completion"]:
        try:
            FraudRule.objects.get_or_create(
                name=rname,
                defaults={"is_active": True, "action": "flag", "severity": random.choice(["low", "medium", "high"])}
            )
        except Exception as e:
            print(f"  WARN FraudRule: {e}")

    for user in users:
        try:
            UserRiskProfile.objects.get_or_create(
                user=user,
                defaults={
                    "risk_score": random.randint(0, 30),
                    "risk_level": random.choice(["low", "low", "medium", "high"]),
                    "is_flagged": random.choice([False, False, False, True]),
                }
            )
        except Exception as e:
            pass

    print("  OK Fraud Detection done")
except Exception as e:
    print(f"  ERROR Fraud Detection: {e}")

# ============================================================
# 10. ENGAGEMENT
# ============================================================
print("\n[10] Engagement...")

try:
    from api.engagement.models import DailyCheckIn, Leaderboard

    for user in users:
        for i in range(7):
            try:
                DailyCheckIn.objects.get_or_create(
                    user=user,
                    date=(now - timedelta(days=i)).date(),
                    defaults={"reward_amount": Decimal("0.10"), "streak_day": i + 1}
                )
            except Exception:
                pass

    try:
        Leaderboard.objects.get_or_create(
            name="Weekly Top Earners",
            defaults={"period": "weekly", "is_active": True}
        )
    except Exception as e:
        print(f"  WARN Leaderboard: {e}")

    print("  OK Engagement done")
except Exception as e:
    print(f"  ERROR Engagement: {e}")

# ============================================================
# 11. AD NETWORKS
# ============================================================
print("\n[11] Ad Networks...")

try:
    from api.ad_networks.models import AdNetwork

    for name in ["AdMob", "IronSource", "Unity Ads", "AppLovin"]:
        try:
            AdNetwork.objects.get_or_create(
                name=name,
                defaults={"is_active": True, "revenue_share": Decimal(str(round(random.uniform(0.3, 0.7), 2)))}
            )
        except Exception as e:
            print(f"  WARN AdNetwork ({name}): {e}")

    print("  OK Ad Networks done")
except Exception as e:
    print(f"  ERROR Ad Networks: {e}")

# ============================================================
# 12. ALERTS
# ============================================================
print("\n[12] Alerts...")

try:
    from api.alerts.models import AlertRule, AlertLog, SystemHealthCheck

    for rname, severity in [("High Fraud Rate", "critical"), ("Low Revenue", "high"), ("Server Down", "critical")]:
        try:
            rule, created = AlertRule.objects.get_or_create(
                name=rname,
                defaults={"is_active": True, "severity": severity}
            )
            if created:
                try:
                    AlertLog.objects.create(
                        rule=rule,
                        message=f"Alert triggered: {rname}",
                        severity=severity,
                    )
                except Exception:
                    pass
        except Exception as e:
            print(f"  WARN AlertRule: {e}")

    for service in ["API Server", "Database", "Cache", "Celery"]:
        try:
            SystemHealthCheck.objects.get_or_create(
                service_name=service,
                defaults={"status": "healthy", "response_time_ms": random.randint(20, 300), "checked_at": now}
            )
        except Exception:
            pass

    print("  OK Alerts done")
except Exception as e:
    print(f"  ERROR Alerts: {e}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "="*50)
print("SEED COMPLETE! Summary:")
print("="*50)

summary = [
    ("Users",            lambda: User.objects.count()),
    ("Wallets",          lambda: __import__('api.wallet.models', fromlist=['Wallet']).Wallet.objects.count()),
    ("WalletTx",         lambda: __import__('api.wallet.models', fromlist=['WalletTransaction']).WalletTransaction.objects.count()),
    ("Tasks",            lambda: __import__('api.tasks.models', fromlist=['MasterTask']).MasterTask.objects.count()),
    ("Task Completions", lambda: __import__('api.tasks.models', fromlist=['UserTaskCompletion']).UserTaskCompletion.objects.count()),
    ("Notifications",    lambda: __import__('api.notifications.models', fromlist=['Notification']).Notification.objects.count()),
    ("UserAnalytics",    lambda: __import__('api.analytics.models', fromlist=['UserAnalytics']).UserAnalytics.objects.count()),
    ("RevenueAnalytics", lambda: __import__('api.analytics.models', fromlist=['RevenueAnalytics']).RevenueAnalytics.objects.count()),
    ("Referrals",        lambda: __import__('api.referral.models', fromlist=['Referral']).Referral.objects.count()),
    ("Support Tickets",  lambda: __import__('api.support.models', fromlist=['SupportTicket']).SupportTicket.objects.count()),
    ("KYC Records",      lambda: __import__('api.kyc.models', fromlist=['KYC']).KYC.objects.count()),
    ("FAQ",              lambda: __import__('api.cms.models', fromlist=['FAQ']).FAQ.objects.count()),
]

for label, fn in summary:
    try:
        print(f"  {label}: {fn()}")
    except Exception:
        pass

print("\nDone! Refresh your dashboard now!")