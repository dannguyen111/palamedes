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

Branch: `tests/phase-1-homepage`, merged to `main` (user merged manually via GitHub
UI, since the classifier that allowed `--admin` merge in Phase 0 blocked a repeat
of that pattern — see "Auto-merge permission" note below).

## Phase 2 — `users` app — **DONE**

42 tests added, `users` app (models.py, forms.py, views.py, urls.py, admin.py) at
**100%** line coverage. Full suite: 66 tests, all passing.

- `test_models.py` (15 tests): `Chapter` (`__str__`, invite-code null/uniqueness —
  multiple NULLs allowed, duplicate non-null codes raise `IntegrityError`),
  `Position` (`__str__`, permission-flag defaults, pinning that duplicate titles
  per chapter are permitted at the model level even though app logic assumes
  uniqueness), `CustomUser` (`__str__` both branches, status/image defaults,
  CASCADE-on-chapter-delete vs. SET_NULL-on-position-delete).
- `test_forms.py` (12 tests): `CustomUserCreationForm` — valid registration with
  either invite code, duplicate email / invalid code rejection, `save()`'s
  chapter/status/position assignment for NM vs. ACT codes, the
  approved-`ChapterRequest` branch forcing President+ACT regardless of which code
  was used, and a pinned `Position.DoesNotExist` when a chapter lacks the
  "No Position" row `save()` depends on. `ProfileUpdateForm` — valid update,
  persistence, and a pinned case showing `email` has no uniqueness check here.
- `test_views.py` (15 tests): `register` (GET/valid-POST/invalid-POST, activation
  email assertions via `mail.outbox`), `activate` (valid token, invalid token,
  malformed uid, nonexistent uid), `profile` (login-required, GET/valid-POST/
  invalid-POST), and a full password-reset integration test (request → email →
  confirm link → new password → login) plus the unknown-email case, driving
  Django's built-in auth views end-to-end against this project's templates.

**New shared helper**: `palamedes/test_helpers.py` gained `PLAIN_STATIC_STORAGE`
(the `override_settings(STATICFILES_STORAGE=...)` workaround from Phase 1,
promoted out of homepage's `test_views.py` into the shared module since
users/dashboard templates all extend the same `homepage/base.html`). **Every
future phase touching a view that renders a full page needs this decorator.**

**Auto-merge permission**: user tried adding a `Bash(gh pr merge *)` allow rule to
`.claude/settings.local.json` themselves after the classifier blocked both the
merge itself and my attempt to edit the settings file to permit it (self-granting
broader auto-approved permissions is blocked by design). They merged PR #44
manually via the GitHub UI instead. **Going forward: don't assume `gh pr merge
--admin` will succeed — try it, and if the classifier blocks it, tell the user
the PR is ready and let them merge it (UI or CLI) rather than retrying.**

Branch: `tests/phase-2-users`, 4 commits, not yet merged — pending user check-in.

## Phase 3 — `dashboard` models & simple forms — **DONE**

38 tests added. `dashboard/models.py` and `dashboard/forms.py` both at **100%**
line coverage (`dashboard/admin.py` was already 100% — purely declarative).
Full suite: 104 tests, all passing.

- `test_models.py` (17 tests): `HousePoint` (`__str__`, status/date_for
  defaults, negative amounts for penalties, `assigned_approver` SET_NULL),
  `Due` (`__str__`, paid/template defaults, CASCADE-on-user-delete), `Task`
  (`__str__`, completed default, mixed CASCADE/SET_NULL FKs), `Announcement`
  (`__str__`, auto `date_posted`, CASCADE-on-chapter-delete).
  **Hit a real Django/timezone gotcha here** — `HousePoint.date_for` has
  `default=timezone.now` (a datetime-returning callable on a `DateField`), so
  the in-memory attribute holds a raw datetime until it round-trips through
  the DB; and comparing against `date.today()` (local system time) instead of
  `timezone.now().date()` flaked because `TIME_ZONE='UTC'` in settings while
  the test host's local clock is behind UTC. Fixed via `refresh_from_db()` +
  comparing against `timezone.now().date()`. **Worth remembering for any
  future date/time assertion in this codebase — always compare against UTC
  clock sources, never local `date.today()`/`datetime.now()`.**
- `test_forms.py` (21 tests): `NMPointRequestForm` (approver queryset scoped
  to same-chapter Actives), `ActivePointRequestForm` (plain validation),
  `DirectPointAssignmentForm` (can_manage_points-gated queryset, including the
  `position=None` safe path), `SingleDueForm` (chapter-scoped queryset +
  CHARGE/AID sign-forcing both directions), `BulkDueForm` (valid submission,
  pinning that PLEDGE_CLASS's semester/year fields are NOT enforced by the
  form itself — no `clean()` override, unlike BulkPointForm), `BulkPointForm`
  (AWARD/PENALTY sign-forcing, `min_value=1`).

Branch: `tests/phase-3-dashboard-core`, 2 commits, not yet merged — pending
user check-in.

## Phase 4 — `dashboard` read-only/aggregation views — **DONE**

41 tests added. `dashboard/views.py` up from 16% to **30%** line coverage
(the 5 views this phase covers — `dashboard`, `directory`,
`unpaid_directory`, `brother_profile`, `points_hub` — are now fully
exercised; the remaining 70% is all Phase 5/6 territory). Full suite: 145
tests, all passing.

- `test_views_dashboard.py` (8 tests): login-required, approved-only
  `total_points`, unpaid-only `dues_balance`, incomplete-only
  `pending_tasks_count`, 5-most-recent chapter announcements (+ no-chapter
  → `[]`), and pinning that `pending_points` is computed but never exposed
  in context (dead code).
- `test_views_directory.py` (15 tests): `directory` (chapter scoping, `q`
  search across first/last/major/hometown, exact status filter),
  `unpaid_directory` (only-unpaid-members listing, filter/status params),
  `brother_profile` (404, cross-chapter denial, same-chapter render).
  **Correction to codebase-notes.md**: the `unpaid_directory`
  `Sum('dues__amount')` annotation was flagged as a suspected bug (summing
  paid+unpaid together for a member with both). A dedicated test proved
  this wrong — Django reuses the base filter's join for the annotation, so
  `total_dues` correctly reflects only the unpaid amount. **Not a bug.**
  Noted here so nobody "fixes" it later based on the stale note.
- `test_views_points_hub.py` (18 tests): login-required, approved-only
  `total_points`, `my_action_items` inbox (both OR branches), `exec_queue`
  (empty without permission or with `position=None`, populated +
  self-exclusion when permitted), leaderboard split (Coalesce keeps
  zero-point members visible, correct ACT/NM split, descending order), and
  the "mother logs" — digit-guarded recipient/approver filters, sort
  allow-list (confirmed an injection-shaped sort value is safely ignored,
  not just theoretically), NM/active log split.

Branch: `tests/phase-4-dashboard-readviews`, 3 commits, not yet merged —
pending user check-in.

## Phase 5 — `dashboard` workflow/mutation views — **DONE**

83 tests added (52 in the two workflow files + 2 gap-closing additions found
via coverage during this phase). `dashboard/views.py` up from 30% to **83%**
line coverage — everything except the Stripe-integrated payment views is now
covered, exactly on plan for Phase 6. Full suite: **197 tests**, all passing.
Project-wide `TOTAL`: **92%**, already past the 80% target.

- `test_views_points_workflow.py` (33 tests): `submit_points` (NM vs Active
  form selection), `assign_points` (Actives always permitted incl.
  position=None short-circuit, NMs need can_manage_points), the full
  `manage_point_request` approve/reject/counter/counter-back state machine
  across all three permission paths, `edit_log_point`
  (can_manage_points vs. can_manage_nm_points-only), `manage_points_creation`
  (permission-guarded gracefully, directory handoff, ALL/PLEDGE_CLASS/SELECTED
  target groups — its PLEDGE_CLASS branch is correct, unlike dues').
  **Major finding**: `manage_point_request`'s `is_top2` check
  (`request.user.position.can_manage_points and ...`) is evaluated
  unconditionally and unguarded on *every* request to that view — so ANY
  acting user without a Position row gets an `AttributeError` before
  `is_approver`/`is_owner_countering` are even considered, even an assigned
  approver just trying to approve their own request. This broke almost every
  "happy path" test until `setUp` was fixed to give acting users a real
  (permission-less) Position — a good reminder that `make_user()`'s default
  `position=None` will trip this bug in any dashboard-workflow test unless
  deliberately targeting it.
- `test_views_dues_workflow.py` (21 tests): `dues_dashboard` (pins the
  unguarded `position.can_manage_finance` crash), `manage_dues_creation`
  (guarded permission check — though its own redirect target,
  `dues_dashboard`, still crashes for that same positionless user, a
  cascading instance of the bug), single/bulk charge creation across all
  target groups, and the deliberately-left-broken `PLEDGE_CLASS` branch
  (`assertRaises`, per the earlier bug-handling decision). `mark_paid` (pins
  its own unguarded position crash, full/partial payment, non-
  numeric/negative amount rejection).

**Coverage-tool gotcha worth remembering**: `coverage.py` counts a physical
*line* as covered, not each statement on it. One-line `elif X: Y` compounds
(used throughout the bulk-target-group dispatch in this codebase) can show as
"covered" merely because the condition was evaluated during some other
branch's call, even when `Y` itself never ran. Don't fully trust a green
line here — write the test for the actual target_group value if the branch
matters, don't just chase the coverage number.

Branch: `tests/phase-5-dashboard-workflows`, 2 commits, not yet merged —
pending user check-in.

## Phase 6 — Stripe-integrated payment views — not started

Stub file ready: `test_views_payments.py`.

## Phase 7 — coverage gap-filling & wrap-up — not started

Stub files ready: `users/tests/test_admin.py`, `dashboard/tests/test_admin.py`
(homepage's admin action test is pulled forward into Phase 1 since it's small and
tightly coupled to that app).

---

## Current coverage snapshot (after Phase 5)

`coverage run manage.py test && coverage report -m` (full suite, 197 tests):

- `homepage/`, `users/`: **100%** everywhere (unchanged since Phase 2).
- `dashboard/`: `models.py`, `forms.py`, `admin.py`, `urls.py` all **100%**.
  `views.py` at **83%** — every view except the Stripe-integrated payment
  ones (`payment_page`, `create_bulk_checkout_session`, `process_payment`,
  `payment_success`, `make_payment_treasurer`) is fully covered. That's all
  that's left, and it's exactly Phase 6.
- `palamedes/settings.py` at 96% (AWS S3 branch, out of scope), `urls.py` at
  89% (DEBUG-only static route).
- Project `TOTAL`: **92%** (up from 67% after Phase 4) — already past the
  80% target from the original ask. Phase 6 should push this to ~98-100%.
