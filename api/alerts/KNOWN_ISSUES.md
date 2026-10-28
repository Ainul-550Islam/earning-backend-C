# Production readiness and known issues - build 2026-10-03

This replaces `KNOWN_ISSUES_2026-10-02.md`. Every item that file listed as "NOT fixed" is fixed
(see "Previously open items" below).

## What was verified for this build

| Check | Result |
|---|---|
| `python -m compileall`, import of every non-test module | clean (`settings.py` is a template that intentionally raises without `DJANGO_SECRET_KEY`) |
| `manage.py check`, `check --deploy` (hardened settings) | no issues |
| `makemigrations alerts --check` | no drift |
| `audit_routes --module-prefix api.alerts` | 0 problems |
| Test suite, SQLite | 1704 passed |
| Test suite, **PostgreSQL 16**, database built by the real migration chain | 1704 passed |
| Fresh `migrate` on PostgreSQL 16, no override variables | OK (0001-0014) |
| Upgrade `0012 -> 0014` with legacy rows / empty legacy tables / removed-0014 recorded | aborts / passes / aborts, as designed |
| App under a bare host `REST_FRAMEWORK` (no throttle rates, default auth order) | 163-test API subset passes |
| bandit (`-x tests,docs`) | 0 HIGH, 0 MEDIUM; remaining LOW: `try/except: pass` (30), `random` (13), test/placeholder passwords (9), subprocess/xml import notices (2) |

## NOT verified here (do these in staging before go-live)

* A real Celery worker/beat with a broker, a real Redis cache, and real Slack/SMS/e-mail/webhook receivers
  (tests run Celery eagerly, LocMem cache, mocked HTTP).
* Django 4.2 / 5.0 and Python versions other than 3.12 (tested: Django 5.1, DRF 3.15, Celery 5.6).
* Your actual production database. The upgrade path was exercised on a synthetic database at migration 0012.
  Take a backup, then read `python manage.py migrate --plan` before `migrate`.
* Load / performance behaviour.

## Behaviour changes you must know about

| Area | Now |
|---|---|
| Migration `0013` | Runs automatically when every legacy table is empty (fresh installs). If any legacy row exists it refuses until you set `CONFIRM_LEGACY_MODEL_DELETION=1`. |
| Tenant FK | All 37 `tenant` columns point at `tenants.Tenant` again (matches migrations 0001/0002). The optional `0014_review_required_tenant_fk_retarget` is **removed** and `TENANT_FK_RETARGET_CONFIRMED` is no longer read. |
| Migration `0002` | Creates the PostgreSQL `btree_gin` extension (needed by the GIN index on `AlertRule.name`; a fresh `migrate` failed on PostgreSQL before). Trusted extension since PostgreSQL 13; older servers need a superuser. |
| Migration `0014_noise_effectiveness_and_log_related_name` | Adds `AlertNoise.effectiveness_score` (additive) and `AlertLog.rule` `related_name='logs'` (no SQL). Refuses to run on a database that recorded the removed 0014 (below). |
| Tenant isolation | `X-Tenant-ID` is honoured only for superusers and service accounts (`user.is_service_account`). Set `ENABLE_MULTI_TENANT = True` so a non-privileged user whose tenant cannot be resolved gets **no** rows (default `False` keeps single-tenant installs unchanged). The six silent no-op fallbacks for `TenantIsolationMixin` are gone: a broken import now fails loudly. |
| Webhook API | Management endpoints and `/webhooks/outgoing/*` are admin-only; secrets/credential headers are masked; URLs must be public http(s) (SSRF guard; `ALERTS_ALLOW_PRIVATE_WEBHOOK_URLS = True` opts out); redirects are not followed; 2xx counts as delivered. `incoming` needs `webhook_id` plus `X-Signature` = HMAC-SHA256(secret, raw body); signature checks fail closed when no secret exists. |
| Channel `config` | Credential-like keys (`token`, `secret`, `password`, `api_key`, `webhook_url`, ...) are returned as `********`. Sending the mask back keeps the stored value. Stored values are still plain JSON in the database (no encryption at rest). |
| Error responses | HTTP 5xx bodies and service result dicts no longer contain exception text (`Internal server error` / `Operation failed`); details go to the log. 4xx validation messages are unchanged. |
| Background work | The task scheduler, the performance monitor thread and health-check start-up no longer start at import. Opt in with `TASK_SCHEDULER_CONFIG['auto_start']=True`, `PERFORMANCE_MONITORING_CONFIG['auto_start']=True`, `ALERTS_PERFORMANCE_MONITOR_AUTOSTART=True`, or call `health_check.start_health_checks()`. Prefer Celery beat over the in-process scheduler (it would run once per worker). |
| Script escalation | Disabled unless `ESCALATION_SCRIPT_ALLOWED_DIRS = ['/opt/alerts/scripts']` is set; only files inside those directories run, without a shell. |
| App start-up | No database access in `ready()` for `migrate`/`makemigrations`/`collectstatic`/`check`/...; integration permissions are created in a `post_migrate` hook. |
| Backup / restore / bridges | SQL identifiers are validated and quoted (`sql_utils.py`); restore only touches tables that exist; zip members are extracted to a private temp directory. |
| `settings.py` template | `DEBUG` defaults to off, `SECRET_KEY` and DB password have no insecure defaults. |

## Databases that applied the removed 0014

Run `python manage.py showmigrations alerts`. If `0014_review_required_tenant_fk_retarget` was ever `[X]`
(you set `TENANT_FK_RETARGET_CONFIRMED=1`), the tenant foreign keys in that database point at the user table.
`migrate` will stop with an explanatory error. Restore the constraints to `tenants.Tenant` first
(drop the FK on each `*_tenant_id` column of the `alerts_*` tables and re-add it referencing `tenants_tenant`),
after verifying the stored values really are tenant ids; then re-run `migrate`.

## Previously open items - all fixed

1. `update_noise_effectiveness` -> `AlertNoise.effectiveness_score` added (0-1 fraction; admin shows the live percentage).
2. `services/core.py` reverse name `logs` -> `AlertLog.rule` now uses `related_name='logs'`; the rule-performance report also had an annotation clashing with `AlertRule.avg_processing_time` (it returned `[]` silently).
3. Performance monitor: nested-histogram `int + dict` error and missing `cpu_warning` / `memory_*` / `disk_*` / `response_time_*` threshold keys (alerts never fired).
4. Audit log: enum vs string handling, JSON-lines filtering, and five event types / two severities used by signals that did not exist.
5. `sync_manager`: wrong `register_integration(...)` call replaced by an update of the registered target.
6. Inbound webhook: raw body is read before `request.data`.
7. `create_scheduled_report`: accepts legacy keys, defaults dates, tolerates empty config; `AlertReport.schedule_next_run` handles dict recurrence patterns.
8. `conftest.py` fixtures `alert_rule` / `alert_report` build valid objects.

## Known limitations

* Webhooks registered through `/webhooks/register/` live in the memory of the process that received the call.
  With several workers each has its own registry; use `AlertChannel(channel_type='webhook')` for durable delivery.
* `X-Tenant-ID` and tenant ids are parsed as integers (the `tenants.Tenant` primary key is assumed to be an integer).
* `A_TO_Z_COMPONENTS_ANALYSIS.md` and `FINAL_TEST_COVERAGE_REPORT.md` are historical snapshots and may not match this build.
* Removed from the package (they referenced a `test_settings` module that was never shipped): `manage.py`, `run_tests.py`,
  `test_runner.py`, `test_verification.py`, `test_settings.py.legacy_unused`, `DJANGO_TEST_STATUS.md` (replaced by `TESTING.md`).
  `requirements.txt` now lists runtime needs only; see `requirements-optional.txt` and `requirements-dev.txt`.
