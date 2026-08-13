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

Branch: `tests/phase-0-infra`. Not yet merged to `main` — pending user check-in.

## Phase 1 — `homepage` app — not started

Stub files ready at `homepage/tests/{test_models,test_forms,test_views,test_admin}.py`.

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

## Current coverage snapshot

Not yet measured with real tests (0 tests exist beyond stubs as of Phase 0).
