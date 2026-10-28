# Engagement World #1 — Django App

**Gamification engine** for reward-based platforms (CPAlead-style).  
Features: Daily Check-In · Spin Wheel · XP/Levels · Leaderboard · Achievements · Quests · Challenges · Coin Shop · Referrals · Push Notifications.

---

## Quick Start

### 1. Install dependencies

```bash
pip install djangorestframework celery redis firebase-admin factory-boy pytest-django
```

### 2. Add to INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    "rest_framework",
    "engagement",
]
```

### 3. Add URL routes

```python
# urls.py (root)
from django.urls import path, include

urlpatterns = [
    ...
    path("engagement/", include("engagement.urls", namespace="engagement")),
]
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Seed default data (one command does everything)

```bash
python manage.py engagement_setup
```

This runs in order:
- `seed_achievements` — 22 achievement definitions
- `seed_leaderboard_rewards` — daily/weekly/monthly tiers
- `seed_quests` — 8 default quests
- `seed_shop` — 7 shop items

### 6. Add Celery Beat schedule

```python
# settings.py
from engagement.celery_beat import ENGAGEMENT_BEAT_SCHEDULE

CELERY_BEAT_SCHEDULE = {
    **ENGAGEMENT_BEAT_SCHEDULE,
}
```

### 7. (Optional) Firebase Push Notifications

```python
# settings.py
FIREBASE_CREDENTIALS_PATH = "/path/to/serviceAccount.json"
# OR via environment dict:
FIREBASE_CREDENTIALS_DICT = json.loads(os.environ["FIREBASE_CREDENTIALS"])
```

---

## Settings Reference

```python
# All optional — sensible defaults are in constants.py
ENGAGEMENT_CHECKIN_BASE_COINS   = 5      # coins for day-1 check-in
ENGAGEMENT_CHECKIN_MAX_STREAK   = 7      # streak multiplier caps here
ENGAGEMENT_SPIN_MAX_PER_DAY     = 5      # max spin-wheel uses daily
ENGAGEMENT_LEVEL_XP_BASE        = 100    # XP needed for level 1→2
ENGAGEMENT_LEVEL_XP_GROWTH      = 1.5   # XP growth factor per level
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/engagement/` | Daily dashboard stats |
| GET | `/engagement/stats/` | Engagement score (0–100) |
| POST | `/engagement/daily-checkin/` | Perform today's check-in |
| GET | `/engagement/checkins/` | Check-in history |
| GET | `/engagement/checkins/stats/` | Check-in platform stats |
| POST | `/engagement/spin-wheel/` | Execute one spin |
| GET | `/engagement/spins/` | Spin history |
| GET | `/engagement/spins/stats/` | Spin platform stats |
| GET | `/engagement/leaderboard/` | Today's leaderboard |
| GET | `/engagement/leaderboard/seasons/` | Season list |
| GET | `/engagement/achievements/` | All achievements + status |
| GET | `/engagement/achievements/mine/` | My unlocked achievements |
| POST | `/engagement/achievements/<id>/claim/` | Claim achievement reward |
| GET | `/engagement/xp/` | My XP & level |
| GET | `/engagement/xp/history/` | XP transaction log |
| GET | `/engagement/quests/` | My active quests |
| POST | `/engagement/quests/<id>/claim/` | Claim quest reward |
| GET | `/engagement/challenges/` | Active public challenges |
| POST | `/engagement/challenges/<id>/join/` | Join a challenge |
| GET | `/engagement/shop/` | Coin shop items |
| POST | `/engagement/shop/purchase/` | Buy an item |
| GET | `/engagement/shop/inventory/` | My inventory |
| GET | `/engagement/referrals/` | My referrals + code |
| POST | `/engagement/referrals/register/` | Register referral code |
| GET | `/engagement/notifications/` | My notifications |
| POST | `/engagement/notifications/read-all/` | Mark all read |
| POST | `/engagement/notifications/push-token/` | Register FCM token |

---

## File Structure

```
engagement/
├── __init__.py
├── apps.py                  # AppConfig + signal registration
├── admin.py                 # Autodiscovery redirect
├── constants.py             # All magic numbers
├── exceptions.py            # EngagementError subclasses
├── urls.py                  # All 40+ URL patterns
├── celery_beat.py           # Periodic task schedule
├── conftest.py              # Pytest configuration
│
├── models/                  # 11 model files
├── serializers/             # 11 serializer files
├── views/                   # 11 view files
├── services/                # 12 service files (including push_fcm)
├── signals/                 # Custom signals + handlers
├── tasks/                   # Celery tasks (daily + notifications)
├── admin/                   # 10 rich admin files
├── utils/                   # Cache, pagination, throttling, permissions
├── tests/                   # 10 test files + factories
├── migrations/              # Initial migration
└── management/commands/     # 8 management commands
```

---

## Running Tests

```bash
pip install pytest pytest-django factory-boy
pytest engagement/tests/ -v
```

---

## Architecture: How Events Flow

```
User Action (API call)
    ↓
View Layer (views/*.py)
    ↓
Service Layer (services/*_service.py)
    → CoinService.add()          ← atomic F() expression
    → XPService.grant()          ← fires level_up_signal
    → QuestService.record_action() ← auto-completes quests
    ↓
GamificationEngine.on_*()
    → AchievementService.check_and_unlock()
    → NotificationService.send()
    ↓
Celery (async push, daily resets, leaderboard rebuilds)
```
