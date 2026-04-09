# Djoyalty — Django Loyalty System

## Overview
Full-featured loyalty system: Points, Tiers, Earn Rules, Redemption, Badges, Streaks, Campaigns, Fraud Detection.

## Quick Start
```bash
python manage.py migrate
python manage.py seed_tiers
python manage.py seed_badges
```

## Key Endpoints
- `GET /api/djoyalty/customers/` — Customer list
- `POST /api/djoyalty/points/earn/` — Earn points
- `POST /api/djoyalty/redemptions/redeem/` — Redeem points
- `GET /api/djoyalty/leaderboard/top/` — Leaderboard
- `GET /api/djoyalty/tiers/` — Tier list
