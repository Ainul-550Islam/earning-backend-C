# Session 10 — `api.webhooks` check error + follow-up audit (2026-09-22)

## Starting point

`python manage.py check` on the outer `earning_backend` project crashed with
an uncaught `ModuleNotFoundError: No module named 'jinja2'`, raised while
`api.webhooks.apps.WebhooksConfig.ready()` imported the root signal handlers:

```
apps.py:ready() → signals/__init__.py → wallet_signals.py
  → services/core/DispatchService.py → services/core/__init__.py
  → TemplateEngine.py → `from jinja2 import ...`
```

**This is not a code bug — it's a missing dependency in the venv.**
`Jinja2>=3.1` is already correctly declared in `requirements.txt`, and
`TemplateEngine` uses it for real, load-bearing functionality (rendering
webhook payload templates, including a security-hardened `calculate_field`
expression evaluator — this isn't decorative). `services/__init__.py`'s own
docstring documents a deliberate, earlier decision in this project to let
service-import errors raise immediately rather than silently degrade to
`None`, specifically because a silent `None` produced worse, harder-to-trace
`AttributeError`s later. Wrapping the `TemplateEngine` import in a
try/except — my first instinct — would have quietly reversed that decision
for no good reason. **The fix is simply to install it:**

```
pip install jinja2
# or, to pick up everything requirements.txt declares:
pip install -r api/webhooks/requirements.txt
```

Verified empirically in a clean sandbox: reproduced the exact reported
traceback with jinja2 absent, then confirmed `manage.py check` passes with
**zero code changes** once it's installed.

## What else this session found and fixed

Once `check` was passing, I built an isolated sandbox for `api.webhooks`
(SQLite, a minimal `tenants` stub for the FK this app's migrations expect —
same permanent constraint as the marketplace audit: the outer project isn't
inside this app-only zip — Celery in eager mode) and ran `makemigrations
--check` (clean, zero drift) and the full test suite (1,260 tests) to see if
anything else was hiding behind the crash. First run: 191 failures. All but
6 turned out to be gaps in my own sandbox settings, not app bugs — worth
recording since they double as the actual required settings for deploying
this app:

- No real Celery app was wired to Django settings (`current_app` fell back
  to Celery's own default `amqp://guest@localhost:5672`), `rest_framework.authtoken`
  wasn't installed, no `REST_FRAMEWORK` block, and the wrong URL prefix — all
  four already correctly documented in this app's own `settings/webhooks_settings.py`, I'd just
  transcribed it incompletely.

With those corrected, 24 real failures remained. Fixed:

1. **`DEFAULT_AUTHENTICATION_CLASSES` ordering (`settings/webhooks_settings.py`)** —
   `SessionAuthentication` was listed before `TokenAuthentication`. DRF's
   `APIView.handle_exception()` uses the *first* authenticator's
   `authenticate_header()` to decide whether an auth failure is reported as
   401 or 403; `SessionAuthentication` doesn't define one, so with the old
   order **every unauthenticated request across the whole API was silently
   downgraded from 401 to 403** (visible as `NotAuthenticated`'s own message
   arriving with a 403 status). This app's own tests (`test_aging.py`,
   `test_views.py`) assert 401 and were right to. Moving `TokenAuthentication`
   first fixes it — confirmed against DRF's source, not just the symptom.
   (4 tests)

2. **`WebhookReplayViewSet.create_batch` (`viewsets/WebhookReplayViewSet.py`)** —
   `batch_size` from `request.data` went straight into `qs[:batch_size]` with
   no type check. A JSON body with `"batch_size": "50"` (a perfectly valid
   string, easy mistake for any API caller) crashed with a bare `TypeError`
   → 500. Now coerced to `int` with a clean 400 on anything invalid. (1 test)

3. **Test client defaulting to multipart (`settings/webhooks_settings.py`)** —
   ~13 test methods across `test_viewsets.py`, `test_api_coverage.py`, and
   `test_missing_coverage.py` post nested dict/list payloads
   (`payload={...}`, `filter_config`, `filters`) via `self.client.post(url,
   data)` with no `format=`. DRF's test client defaults to multipart, which
   can't encode nested data at all. Rather than patch a dozen-plus call
   sites, set `TEST_REQUEST_DEFAULT_FORMAT: 'json'` once — confirmed no test
   in this suite exercises a real file upload (the one `FileField` in
   `AdminWebhookImportSerializer` is only ever posted an empty body), so this
   has no effect on any test's actual intent and none on production request
   parsing (test-client-only setting).

4. **Stale assertions against the pre-envelope response shape
   (`tests/test_views.py`, `tests/test_viewsets.py`)** — 5 tests asserted
   e.g. `assertIn('target_url', response.data)`, left over from before
   `webhook_exception_handler`'s deliberate `{"success": false, "error":
   {..., "detail": {field: [...]}}}` envelope was added project-wide.
   Updated to check `response.data['error']['detail']`.

5. **Missing `pytest.ini`** — `test_missing_coverage.py`'s own
   `ProductionInfrastructureTest` already checks for `pytest.ini` sitting
   next to `requirements.txt`, but it was never added. Added a minimal one.

**Reverted one attempted fix.** I initially made `WebhookEmitAPIView`
return 500 when `DispatchService.emit()` returns `False`, reasoning from the
concurrency test's "10× 200 but 0 delivery logs" symptom. That was wrong: a
`False` here is the *normal, expected* outcome whenever the target endpoint
itself rejects or times out a delivery — exactly what the retry/replay
system exists to handle — and forcing 500 broke 4 other, previously-passing
integration tests that deliberately exercise that path and correctly expect
200. Reverted before it shipped; left a note in the code pointing at this
distinction for next time, since `_emit_sync`'s single `except Exception`
currently can't distinguish "target endpoint said no" from "our own DB call
failed" and collapses both to the same `False` — a real gap, but fixing it
properly means changing `DispatchService.emit()`'s return contract, which
several other call sites (signals, tasks, batch dispatch) also depend on.
Flagging for a dedicated session rather than guessing under time pressure.

## Result

`manage.py check`: clean. `makemigrations --check`: no drift.
Full suite: **1,260/1,260 passing** in isolation. In two full-suite runs
back to back, 1 or 2 of the suite's own dedicated multi-threaded
concurrency tests (`test_complete_webhook_flow_concurrent_requests`,
`test_retry_delivery_concurrent_safety`) intermittently failed under the
full 1,260-test run's system load, but passed 3/3 and 4/4 in isolated
re-runs. This is the same signature as the marketplace audit's own
documented SQLite-concurrency baseline: this sandbox runs SQLite (single
writer, whole-database lock), while the real project runs PostgreSQL —
raising SQLite's busy-timeout narrowed it but didn't eliminate it. Treating
this as a known sandbox artifact rather than an application bug; worth a
real check against Postgres if it's ever seen in the actual deployed stack.

## Noted, not fixed — needs a decision, not a mechanical fix

- **`_emit_sync`'s conflated failure modes** (above) — target-rejected vs.
  internal-error currently return the same `False`.
- **5 models have no `Meta.ordering`** (`WebhookTemplate`, `WebhookSecret`,
  `WebhookFilter`, `InboundWebhookLog`, `InboundWebhook`) — DRF's paginator
  warns (`UnorderedObjectListWarning`) on all of them; pagination can
  legitimately skip or repeat rows across pages without one. Didn't add it
  because it requires a real migration (`AlterModelOptions`), which felt
  like more than this session's ask — flagging since it's a 10-minute fix
  if wanted.
- **`WebhookEndpointViewSet.send_test`** (`views.py`, the `/test/` action)
  has the same shape as the `create_batch`/`WebhookEmitAPIView` issues above
  — it ignores `svc.emit()`'s return value entirely and hardcodes
  `"success": True`. No test currently exercises this, so it's an
  observation, not a verified live bug.
