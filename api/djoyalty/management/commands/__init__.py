# api/djoyalty/management/commands/__init__.py
"""
Djoyalty management commands:
- expire_points         : Process expired loyalty points
- evaluate_tiers        : Re-evaluate all customer tiers
- seed_tiers            : Seed default Bronze→Diamond tiers
- seed_earn_rules       : Seed default earn rules
- seed_badges           : Seed default badges
- recalculate_balances  : Audit & fix points balances from ledger
- generate_insights     : Generate daily insight report
- reset_streaks         : Reset broken streaks
- sync_partners         : Sync partner merchant data
- export_loyalty_data   : GDPR export for a customer
"""
