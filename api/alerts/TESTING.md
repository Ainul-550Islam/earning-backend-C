# Running the tests

The package is a Django app that lives at `api/alerts/` inside your project; its tests need your
project settings (the app list must include `api.alerts.apps.AlertsConfig`, and a `tenants` app,
because every `tenant` column is a FK to `tenants.Tenant`).

    pip install -r api/alerts/requirements-dev.txt
    python -m pytest api/alerts/tests -q                  # whole suite
    python -m pytest api/alerts/tests/test_tenant_isolation_security.py -q

* `conftest.py` pins `ROOT_URLCONF = 'api.alerts.urls'` for every test, so the suite passes wherever
  your project mounts the API (e.g. `/api/alerts/`).
* Run the suite on PostgreSQL before releasing: SQLite does not enforce varchar lengths or GIN/BRIN indexes.
* Production migration check (read-only): `python manage.py migrate --plan` and
  `python manage.py makemigrations alerts --check --dry-run` (must report no changes).
* Static checks used for this build: `python -m compileall -q api/alerts`, `python -m pyflakes api/alerts`,
  `bandit -r api/alerts -x api/alerts/tests,api/alerts/docs`.
