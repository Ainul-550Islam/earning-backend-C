# Install (Git Bash, from the repo root = folder with manage.py)

    git checkout -b alerts-dropin-20261003
    # 1. back up the database first (pg_dump / your provider's snapshot) - migration 0013 deletes legacy tables when they are empty
    mv api/alerts ../alerts_backup_20261003          # backup OUTSIDE the package tree
    python -m zipfile -e /path/to/api_alerts_dropin_2026-10-03.zip api/     # creates api/alerts/
    pip install -r api/alerts/requirements.txt       # plus requirements-optional.txt entries you use

    python manage.py check
    python manage.py showmigrations alerts           # 0014_review_required_tenant_fk_retarget must NOT be [X] (see KNOWN_ISSUES.md)
    python manage.py migrate --plan                  # READ the plan first
    python manage.py makemigrations alerts --check --dry-run      # expect: No changes detected
    python manage.py audit_routes --module-prefix api.alerts      # expect: TOTAL PROBLEMS: 0
    python manage.py migrate
    python -m pytest api/alerts/tests -q             # needs your project settings to include api.alerts

Requirements of the host project: an installed `tenants` app (`tenants.Tenant`), PostgreSQL (the `btree_gin` extension is created by
migration 0002), and `'api.alerts.apps.AlertsConfig'` in `INSTALLED_APPS`.

Settings this build reads (all optional): `ENABLE_MULTI_TENANT` (set True for multi-tenant), `ESCALATION_SCRIPT_ALLOWED_DIRS`,
`ALERTS_ALLOW_PRIVATE_WEBHOOK_URLS`, `ALERTS_PERFORMANCE_THRESHOLDS`, `ALERTS_PERFORMANCE_MONITOR_AUTOSTART`,
`TASK_SCHEDULER_CONFIG['auto_start']`, `PERFORMANCE_MONITORING_CONFIG['auto_start']`.

Modules other apps import from the old package:

    grep -rhoE "(from|import) api\.alerts[A-Za-z_.]*" api --include=*.py --exclude-dir=alerts --exclude-dir=migrations | sort -u
