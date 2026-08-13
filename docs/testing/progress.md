# Test suite progress log

Running log for the multi-session "comprehensive test suite" task. Read this first
when resuming the task in a new session, alongside `docs/testing/codebase-notes.md`
(full codebase map — models/views/forms/urls/settings/known bugs) and the plan file
this task was approved from (`transient-strolling-seahorse.md` in the Claude plans
directory, if still available; this file is the durable source of truth otherwise).

**Bug-handling policy (confirmed with user):** tests pin current behavior, including
known bugs (AttributeErrors when `position is None`, the broken `PLEDGE_CLASS` bulk-dues
branch, a few access-control gaps). No production code fixes as part of this task. See
`codebase-notes.md` §6 "Known bugs / broken code paths" for the full list.

**Environment note:** this machine has no `python`/`py` on PATH by default. Use the
dedicated conda env: `C:\Users\sidan\anaconda3\envs\palamedes\python.exe`. Run commands
from the `palamedes/palamedes/` directory (same level as `manage.py`), e.g.:

```
C:\Users\sidan\anaconda3\envs\palamedes\python.exe manage.py test
C:\Users\sidan\anaconda3\envs\palamedes\python.exe -m coverage run manage.py test
C:\Users\sidan\anaconda3\envs\palamedes\python.exe -m coverage report -m
```

`coverage` was installed into that env directly (not yet via requirements-dev.txt
`pip install -r`, since the env already had it installed ad hoc during Phase 0 setup).

---

## Phase 0 — Test infrastructure — **DONE**

- `palamedes/requirements-dev.txt` added (`-r requirements.txt` + `coverage`).
- `palamedes/.coveragerc` added (source = homepage, dashboard, users, palamedes;
  omits migrations/manage.py/wsgi/asgi/tests).
- `palamedes/palamedes/test_helpers.py` added — shared fixture builders:
  `make_chapter()`, `make_chapter_with_positions()` (seeds the 4 standard Position
  rows: President/Vice President/Treasurer/No Position, matching
  `homepage.admin.approve_requests`), `make_user()`.
- All three apps' `tests.py` boilerplate replaced with `tests/` packages of stub
  files (each stub is just `from django.test import TestCase` + a comment pointing
  at which phase fills it in). Dashboard's view tests are pre-split across 6 files
  (`test_views_dashboard`, `test_views_directory`, `test_views_points_hub`,
  `test_views_points_workflow`, `test_views_dues_workflow`, `test_views_payments`)
  since `dashboard/views.py` has ~20 views — keeps future phase commits small.
- `docs/testing/progress.md` (this file) created.
- Verified: `manage.py test` and `coverage run manage.py test && coverage report`
  both run clean with 0 tests, 0 errors.

Branch: `tests/phase-0-infra`. Merged to `main` via PR #43 (admin override — main
requires a review approval and no CI is configured, so a straight `gh pr merge`
was blocked; user chose to bypass with `--admin`).

## Phase 1 — `homepage` app — **DONE**

24 tests added, homepage app (models.py, forms.py, views.py, admin.py) at **100%**
line coverage.

- `test_models.py` (4 tests): `ChapterRequest.__str__`, `is_approved` default,
  `date_requested` auto-population, direct approval.
- `test_forms.py` (6 tests): `ChapterRequestForm` valid submission, each required
  field's validation error, malformed email, `save()` persistence.
- `test_views.py` (7 tests): `home` (anon vs. authenticated redirect), `about`
  context, `start_chapter` GET/valid-POST/invalid-POST (incl. success message
  and DB row assertions). Had to work around a real environment gotcha:
  `base.html` uses `{% static %}` and WhiteNoise's
  `CompressedManifestStaticFilesStorage` needs a `collectstatic` manifest that
  doesn't exist here, so full-page-rendering tests use
  `override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")`.
  **This same workaround will be needed in every future phase that renders a
  full page** (dashboard templates also extend a base with `{% static %}` —
  confirm/reuse this pattern rather than rediscovering it).
- `test_admin.py` (7 tests): `approve_requests` action — `is_approved` flip,
  Chapter `get_or_create` + invite codes, all 4 Position rows' exact permission
  flags, approval email content/recipient, skip-if-already-approved, idempotent
  on a second run, and backfilling codes onto a pre-existing codeless Chapter.

Branch: `tests/phase-1-homepage`, 4 commits (one per test file), not yet merged —
pending user check-in.

## Phase 2 — `users` app — not started

Stub files ready at `users/tests/{test_models,test_forms,test_views,test_admin}.py`.

## Phase 3 — `dashboard` models & simple forms — not started

Stub files ready at `dashboard/tests/{test_models,test_forms}.py`.

## Phase 4 — `dashboard` read-only/aggregation views — not started

Stub files ready: `test_views_dashboard.py`, `test_views_directory.py`,
`test_views_points_hub.py`.

## Phase 5 — `dashboard` workflow/mutation views — not started

Stub files ready: `test_views_points_workflow.py`, `test_views_dues_workflow.py`.

## Phase 6 — Stripe-integrated payment views — not started

Stub file ready: `test_views_payments.py`.

## Phase 7 — coverage gap-filling & wrap-up — not started

Stub files ready: `users/tests/test_admin.py`, `dashboard/tests/test_admin.py`
(homepage's admin action test is pulled forward into Phase 1 since it's small and
tightly coupled to that app).

---

## Current coverage snapshot (after Phase 1)

`coverage run manage.py test && coverage report -m` (full suite, 24 tests):

- `homepage/`: **100%** across `models.py`, `forms.py`, `views.py`, `admin.py`.
- Everything else (users, dashboard, palamedes settings/urls): unchanged from
  the Phase 0 baseline (module-level-only coverage from imports, no real
  tests yet) — that's Phases 2-7.
- Project `TOTAL`: 48% (up from the Phase 0 baseline of 43%), but this number
  is dominated by dashboard/users still having no real tests — not a
  meaningful project-wide signal until later phases land.
