# Palamedes Codebase Notes — Testing Reconnaissance

Purpose: reference map of the entire codebase for planning a multi-phase Django test
suite. No tests exist today (`0%` coverage). This file is descriptive only — no phase
plan, no test code.

All paths below are relative to `palamedes/palamedes/` (the Django project root that
contains `manage.py`) unless stated otherwise.

---

## 1. Tech stack recap

- Django 5.2.8, Python, SQLite (dev) / PostgreSQL via `dj_database_url` + `psycopg2-binary` (prod)
- Custom user model: `AUTH_USER_MODEL = 'users.CustomUser'`
- Crispy Forms + `crispy_bootstrap4` (Bootstrap 4 rendering)
- Stripe SDK (`stripe` package) for Checkout Sessions (dues payment)
- Email: `django.core.mail.backends.smtp.EmailBackend` (Gmail SMTP) — used for registration
  verification email and admin-approval notification email. **Django test runner
  auto-swaps this for `locmem` during `manage.py test`, but note the backend is
  hardcoded to `smtp` in settings, not environment-driven** — worth confirming tests
  actually get locmem (they do, via Django's test runner override), or explicitly set
  `EMAIL_BACKEND` in test settings/override if paranoid.
- `django-storages` + `boto3` for S3 media storage; only activated in settings if
  `AWS_ACCESS_KEY_ID` env var is present, otherwise local `MEDIA_ROOT`/`media/` folder is used.
- `whitenoise` for static files (irrelevant to tests)
- Three apps: `homepage`, `users`, `dashboard`, wired together at `palamedes/urls.py`

---

## 2. `palamedes/settings.py` (project-level config)

- `SECRET_KEY` from env, insecure fallback `'default-insecure-key-for-dev'`
- `DEBUG` from env (`'True'` string check)
- `ALLOWED_HOSTS` from comma-separated env var, defaults `127.0.0.1,localhost`
- `INSTALLED_APPS`: `homepage`, `users`, `dashboard` (custom apps), then standard
  `django.contrib.*` (admin, auth, contenttypes, sessions, messages, staticfiles),
  plus `crispy_forms`, `crispy_bootstrap4`. **No `django.contrib.sites` in
  INSTALLED_APPS**, yet `users/views.py::register` calls
  `django.contrib.sites.shortcuts.get_current_site(request)` — this works because
  Django's `get_current_site` falls back to a `RequestSite` (derived from
  `request.get_host()`) when the `sites` framework isn't installed, so no `SITE_ID`
  is needed. Good to know: tests hitting `register()` don't need the sites app.
- `AUTH_USER_MODEL = 'users.CustomUser'`
- `MIDDLEWARE`: Security, WhiteNoise, Session, Common, CSRF, Auth, Messages, Clickjacking — standard stack.
- `ROOT_URLCONF = 'palamedes.urls'`
- `TEMPLATES`: `APP_DIRS: True`, context processors: request, auth, messages.
- `DATABASES`: `dj_database_url.config(default='sqlite:///.../db.sqlite3', conn_max_age=600)`
  — `DATABASE_URL` env var overrides in prod; tests will use Django's default test-DB
  spin-up regardless (SQLite in-memory unless `DATABASE_URL` is set in the test env).
- `AUTH_PASSWORD_VALIDATORS`: all 4 standard Django validators enabled (UserAttributeSimilarity,
  MinimumLength, CommonPassword, NumericPassword) — relevant for registration-form tests
  using weak passwords (e.g. `'password123'`, all-numeric, username-similar).
- `STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'` —
  can cause `ValueError: Missing staticfiles manifest entry` in tests that render templates
  referencing `{% static %}` files not yet collected; watch for this if tests fail
  oddly on template rendering. May need `WHITENOISE_AUTOREFRESH` or a different storage
  backend override in a test settings module.
- `CRISPY_ALLOWED_TEMPLATE_PACKS` / `CRISPY_TEMPLATE_PACK = "bootstrap4"`
- `EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'`, `EMAIL_HOST = 'smtp.gmail.com'`,
  port 587, TLS, host user/password from env (`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`).
- `LOGIN_REDIRECT_URL = 'dashboard'`, `LOGOUT_REDIRECT_URL = 'home'`, `LOGIN_URL = 'login'`
- `MEDIA_ROOT`/`MEDIA_URL` for profile pics (`media/`, `/media/`)
- `STRIPE_PUBLIC_KEY` — **hardcoded literal test key in settings.py** (not from env).
  `STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')` — empty string default,
  meaning any test that reaches real `stripe.*` calls without mocking will fail/hang
  unless mocked (see Cross-cutting §6).
- AWS S3 block: conditionally sets `DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'`
  only if `AWS_ACCESS_KEY_ID` env var is truthy; otherwise local storage. In a typical
  local/CI test run (no AWS env vars) this branch is **not** exercised — image upload
  tests will use local `MEDIA_ROOT`, so tests writing `CustomUser.image` should clean up
  files or use Django's `override_settings(MEDIA_ROOT=tempdir)`.

## `palamedes/urls.py` (project-level URLs)

| Path | Name | View |
|---|---|---|
| `admin/` | (django admin) | `admin.site.urls` |
| `` (included) | — | `homepage.urls` |
| `` (included) | — | `users.urls` |
| `dashboard/` (included) | — | `dashboard.urls` |
| `password-reset/` | `password_reset` | `auth_views.PasswordResetView` (template `users/password_reset.html`) |
| `password-reset/done/` | `password_reset_done` | `auth_views.PasswordResetDoneView` (template `users/password_reset_done.html`) |
| `password-reset-confirm/<uidb64>/<token>/` | `password_reset_confirm` | `auth_views.PasswordResetConfirmView` (template `users/password_reset_confirm.html`) |
| `password-reset-complete/` | `password_reset_complete` | `auth_views.PasswordResetCompleteView` (template `users/password_reset_complete.html`) |

Plus `static(MEDIA_URL, ...)` appended when `DEBUG=True` (serves media locally).

These are all built-in Django auth views — testable mostly via `assertTemplateUsed` /
flow tests (request reset → check email sent → follow link → set new password), no
custom code to unit test but good integration-test candidates for the "password reset happy path".

---

## 3. App: `homepage`

### Models (`homepage/models.py`)
**`ChapterRequest`**
- `fraternity_name` = CharField(max_length=100)
- `university` = CharField(max_length=100)
- `president_email` = EmailField()
- `date_requested` = DateTimeField(auto_now_add=True)
- `is_approved` = BooleanField(default=False)
- `__str__` → `f"{self.fraternity_name} at {self.university}"`
- No Meta options, no custom validation, no signals.

### Forms (`homepage/forms.py`)
**`ChapterRequestForm`** — plain `ModelForm` on `ChapterRequest`, fields:
`['fraternity_name', 'university', 'president_email']`. No custom `clean_*` methods —
straightforward form validation tests (required fields, valid email format).

### Views (`homepage/views.py`)
- **`home(request)`** — GET only (no method branching). If `request.user.is_authenticated`
  → redirect to `dashboard`. Else renders `homepage/home.html` (no context).
- **`about(request)`** — always renders `homepage/about.html` with `{'title': 'About'}`.
- **`start_chapter(request)`** — GET renders empty `ChapterRequestForm` in
  `homepage/start_chapter.html` (context `form`, `title`). POST: validates
  `ChapterRequestForm`; on success calls `form.save()` (persists to DB, does **not**
  email — the comment even says "Saves to DB instead of emailing"), adds a success
  message, redirects to `home`. On invalid form, falls through to re-render the
  template with bound form displaying errors (implicit — no explicit `else` needed
  since the `if form.is_valid()` block returns early only on success).

### URLs (`homepage/urls.py`)
| Path | Name | View |
|---|---|---|
| `` | `home` | `views.home` |
| `about/` | `about` | `views.about` |
| `start/` | `start_chapter` | `views.start_chapter` |

### Admin (`homepage/admin.py`)
- `ChapterRequestAdmin`: `list_display = ('fraternity_name', 'university', 'date_requested', 'is_approved')`,
  custom admin **action** `approve_requests` (bulk action, significant logic — see below).
  - `approve_requests(modeladmin, request, queryset)`: for each selected `ChapterRequest`
    not already approved: generates two random invite codes via `secrets.token_hex(4).upper()`
    (nm + active); `Chapter.objects.get_or_create(name=..., university=..., defaults={codes})`;
    if chapter already existed but is missing a code, backfills both codes; creates **4
    hardcoded `Position` rows** for the chapter — `"President"` (all permissions True),
    `"Vice President"` (all True except `can_manage_finance` and `can_create_positions`),
    `"Treasurer"` (only `can_manage_finance` True), `"No Position"` (all False); marks
    `req.is_approved = True` and saves; sends a real email via `send_mail(...)` to
    `req.president_email` from `settings.DEFAULT_FROM_EMAIL` (**note:
    `DEFAULT_FROM_EMAIL` is never explicitly set in settings.py**, so it falls back to
    Django's default `'webmaster@localhost'` — worth checking in a test that this
    doesn't error). This admin action is **the only place `Position` rows with title
    `"President"` / `"No Position"` get created** in the whole app (outside of manual
    admin/shell usage) — `CustomUserCreationForm.save()` in `users/forms.py` depends on
    these exact titles existing (`Position.objects.get(chapter=chapter, title="President")`
    and `title="No Position"`), so **registration tests must pre-create these Position
    rows as fixtures** (either by calling this admin action or creating them directly)
    or `CustomUserCreationForm.save()` will raise `Position.DoesNotExist`.
  - Skips already-approved requests (`continue`).

### Migrations
- `homepage/migrations/`: `0001_initial.py` only (1 migration — model created once, no churn).

### Templates referenced
`homepage/home.html`, `homepage/about.html`, `homepage/start_chapter.html`, plus a `homepage/base.html` base template (not directly rendered by a view, extended by others).

---

## 4. App: `users`

### Models (`users/models.py`)

**`Chapter`**
- `name` = CharField(max_length=100)
- `university` = CharField(max_length=100)
- `nm_invite_code` = CharField(max_length=10, unique=True, null=True, blank=True)
- `active_invite_code` = CharField(max_length=10, unique=True, null=True, blank=True)
- `__str__` → `f"{self.name} - {self.university}"`
- Note: both invite codes are nullable+unique — Django allows multiple NULLs under a
  unique constraint, but two non-null duplicate codes across different chapters
  should raise `IntegrityError` — good edge-case test.

**`Position`**
- `chapter` = FK(Chapter, on_delete=CASCADE, related_name='positions')
- `title` = CharField(max_length=50)
- Boolean permission flags (all default=False): `can_manage_roster`, `can_manage_finance`,
  `can_manage_points`, `can_manage_tasks`, `can_create_positions`, `can_manage_nm_points`
- `__str__` → `f"{self.title} ({self.chapter.name})"`
- No `unique_together` on `(chapter, title)` — duplicate-titled positions per chapter
  are technically allowed by the model, even though app logic (`Position.objects.get(...)`)
  assumes uniqueness of well-known titles like "President"/"No Position" per chapter.
  This is a latent bug worth a test to document current (permissive) behavior.

**`CustomUser`** (extends `AbstractUser`)
- `chapter` = FK(Chapter, on_delete=CASCADE, related_name='members', null=True, blank=True)
- `position` = FK(Position, on_delete=SET_NULL, null=True, blank=True, related_name='members')
- `status` = CharField(max_length=3, choices=`STATUS_CHOICES` = `[('NM','New Member'),('ACT','Active')]`, default='NM')
- `major` = CharField(max_length=100, blank=True)
- `phone_number` = CharField(max_length=15, blank=True)
- `hometown` = CharField(max_length=100, blank=True)
- `bio` = TextField(blank=True, max_length=500)
- `image` = ImageField(upload_to='profile_pics/', default='default.jpg') — **no actual
  `default.jpg` file guaranteed to exist on disk**; check whether templates/tests that
  read `.image.url` on a user with no uploaded pic fail (likely fine since ImageField
  just stores a path string, doesn't validate existence at save time, but `PIL`-based
  code would fail — see below).
- `pledge_semester` = CharField(max_length=10, choices=`SEMESTER_CHOICES` = `[('Fall','Fall'),('Spring','Spring')]`, blank=True, null=True)
- `pledge_year` = IntegerField(blank=True, null=True)
- `__str__` → full name if both first/last set, else `username`
- **`save()` override is commented out** (dead code — would have resized the profile
  image via PIL to 300x300 thumbnail on save). Since it's commented out, **no image
  resizing actually happens** — don't write tests expecting thumbnailing behavior.
- `from PIL import Image` import exists but is currently unused (dead import) since the
  save override is commented out.
- No custom `clean()`.

### Forms (`users/forms.py`)

**`CustomUserCreationForm(UserCreationForm)`**
- Overrides `email` (required EmailField), `first_name` (required, max 30), `last_name`
  (required, max 150), adds `invite_code` (required CharField max 10, not a model field).
- `Meta`: model=CustomUser, fields=`('username', 'email', 'first_name', 'last_name')`
  (password1/password2 come from base `UserCreationForm`).
- `clean_email()`: raises `ValidationError` if a `CustomUser` with that exact email
  already exists (case-sensitive exact match, not case-insensitive — test worth noting).
- `clean_invite_code()`: raises `ValidationError("Invalid Invite Code.")` unless a
  `Chapter` exists with that code as either `nm_invite_code` OR `active_invite_code`.
- `save(commit=True)`: Complex — after building the user, re-looks-up the `Chapter` by
  the invite code (via `Q(nm_invite_code=code) | Q(active_invite_code=code)`, assumes
  exactly one match — **would raise `MultipleObjectsReturned` if somehow two chapters
  shared a code, though the model's `unique=True` should prevent that in practice**);
  sets `user.chapter`; determines `assigned_status` = `'ACT'` if code matches
  `chapter.active_invite_code` else `'NM'`; then tries to find an **approved**
  `ChapterRequest` matching `fraternity_name=chapter.name`, `university=chapter.university`,
  `president_email=user.email`, `is_approved=True` — if found, force-assigns
  `Position` "President" and `status='ACT'` **regardless of which invite code was
  used**; if not found (the `DoesNotExist` except branch, which is the common path),
  assigns `Position.objects.get(chapter=chapter, title="No Position")` and
  `status=assigned_status`. **Both branches call `Position.objects.get(...)` with a
  hardcoded title string and will raise `Position.DoesNotExist` if that Position row
  isn't present for the chapter** — tests need to seed `Position` rows named
  `"President"` and `"No Position"` for any chapter used in registration tests. If
  `commit`, saves user and calls `self.save_m2m()`.

**`ProfileUpdateForm(forms.ModelForm)`**
- `Meta`: model=CustomUser, fields=`['first_name', 'last_name', 'email', 'image', 'major', 'phone_number', 'hometown', 'bio']`
- No custom validation — plain ModelForm; note `email` here has **no uniqueness check**
  unlike registration (a user could update their email to collide with another user's
  — model's `AbstractUser.email` isn't unique by default in Django, so this would
  actually succeed, another good edge-case test).

### Views (`users/views.py`)
- **`register(request)`**: POST — binds `CustomUserCreationForm`; on valid: builds user
  with `commit=False`, sets `is_active=False`, saves, calls `form.save_m2m()`; builds
  email verification link (`urlsafe_base64_encode(force_bytes(user.pk))` + `default_token_generator.make_token(user)`),
  renders `users/acc_active_email.html`, sends via `EmailMessage(...).send()` to the
  submitted email; adds info message; redirects to `login`. **On invalid form**, falls
  through and re-renders `users/register.html` with bound form (implicit, no explicit else).
  GET: renders empty form in `users/register.html`.
- **`activate(request, uidb64, token)`**: decodes `uidb64` → pk, looks up user;
  catches `(TypeError, ValueError, OverflowError, User.DoesNotExist)` → `user=None`.
  If user found and `default_token_generator.check_token(user, token)` passes: sets
  `is_active=True`, saves, logs the user in (`login(request, user)`), success message,
  redirect `dashboard`. Else: error message, redirect `register`. Good branches to test:
  valid token, invalid/tampered token, nonexistent uid, malformed base64 uid.
- **`profile(request)`** — `@login_required`. POST: binds `ProfileUpdateForm` with
  `request.POST, request.FILES, instance=request.user`; on valid, saves, success
  message, redirects to `profile` (self-redirect, avoids POST-GET resubmission). On
  invalid, falls through to render with bound form + errors (context only has `p_form`,
  no explicit invalid-branch render call — reuses the render at the bottom). GET:
  renders form pre-filled with `instance=request.user`.

### URLs (`users/urls.py`)
| Path | Name | View |
|---|---|---|
| `register/` | `register` | `user_views.register` |
| `profile/` | `profile` | `user_views.profile` |
| `login/` | `login` | `auth_views.LoginView` (template `users/login.html`) |
| `logout/` | `logout` | `auth_views.LogoutView` (template `users/logout.html`) |
| `activate/<uidb64>/<token>/` | `activate` | `user_views.activate` |

### Admin (`users/admin.py`)
- `PositionAdmin`: list_display of title/chapter/permission flags, filter by chapter, search by title/chapter name.
- `ChapterAdmin`: list_display name/university/codes, search by name/university.
- `CustomUserAdmin(UserAdmin)`: list_display adds chapter/status/position; list_filter
  chapter/status/is_staff; extends `fieldsets`/`add_fieldsets` with a "Fraternity Info"
  group (chapter, status, position, major, phone_number, hometown, bio, pledge_semester,
  pledge_year). Mostly declarative — low test priority beyond "admin pages load"
  smoke tests if desired.

### Migrations
- `users/migrations/`: `0001_initial.py`, `0002_remove_chapter_invite_code_and_more.py`,
  `0003_position_can_manage_nm_points.py` — 3 migrations (moderate churn: invite-code
  field was renamed/restructured at some point, and `can_manage_nm_points` was added later).

### Templates referenced
`users/register.html`, `users/profile.html`, `users/login.html`, `users/logout.html`,
`users/acc_active_email.html` (email body, not a page), `users/password_reset*.html` (4 templates, used by project-level auth views).

---

## 5. App: `dashboard`

### Models (`dashboard/models.py`)

**`HousePoint`**
- `STATUS_CHOICES` = `[('PENDING','Pending Approval'),('APPROVED','Approved'),('REJECTED','Rejected'),('COUNTERED','Counter-Offer Made')]`
- `user` = FK(AUTH_USER_MODEL, CASCADE, related_name='points_received') — recipient
- `chapter` = FK(Chapter, CASCADE, related_name='house_points', null=True)
- `submitted_by` = FK(AUTH_USER_MODEL, CASCADE, related_name='points_submitted', null=True)
- `assigned_approver` = FK(AUTH_USER_MODEL, SET_NULL, null=True, blank=True, related_name='points_to_approve')
- `amount` = IntegerField() (no validators — can be negative, e.g. penalties)
- `description` = CharField(max_length=200)
- `date_for` = DateField(default=timezone.now)
- `date_submitted` = DateTimeField(auto_now_add=True)
- `status` = CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
- `feedback` = TextField(blank=True)
- `updated_at` = DateTimeField(auto_now=True)
- `__str__` → `f"{self.user.username} - {self.amount} - {self.get_status_display()}"`
- No Meta, no clean(), no signals.

**`Due`**
- `title` = CharField(max_length=100)
- `amount` = DecimalField(max_digits=10, decimal_places=2)
- `due_date` = DateField()
- `is_template` = BooleanField(default=False) (appears unused elsewhere in views —
  no view filters on `is_template`; likely vestigial/future field)
- `assigned_to` = FK(AUTH_USER_MODEL, CASCADE, null=True, blank=True, related_name='dues')
- `is_paid` = BooleanField(default=False)
- `__str__` → `f"{self.title} - ${self.amount}"`

**`Task`**
- `assigned_to` = FK(AUTH_USER_MODEL, CASCADE, related_name='tasks')
- `assigned_by` = FK(AUTH_USER_MODEL, SET_NULL, null=True, related_name='created_tasks')
- `title` = CharField(max_length=200)
- `description` = TextField()
- `due_date` = DateTimeField()
- `completed` = BooleanField(default=False)
- `__str__` → `self.title`
- **No views or forms in `dashboard/views.py` or `dashboard/forms.py` reference `Task`
  at all** — the model exists and is dashboard-counted (`pending_tasks_count` in the
  `dashboard` view) but there is no create/complete/list view for tasks. Only testable
  via direct model creation + the dashboard summary count, and via admin.

**`Announcement`**
- `chapter` = FK(Chapter, CASCADE, related_name='announcements')
- `author` = FK(AUTH_USER_MODEL, CASCADE)
- `title` = CharField(max_length=100)
- `content` = TextField()
- `date_posted` = DateTimeField(auto_now_add=True)
- `__str__` → `f"{self.title} - {self.chapter.name}"`
- **No create/edit view exists** for Announcement either — only read via the `dashboard`
  view's "Recent 5" query. Only creatable via admin or direct ORM in tests.

### Forms (`dashboard/forms.py`)
- **`DateInput(forms.DateInput)`**: sets `input_type = 'date'` — shared widget.
- **`NMPointRequestForm(ModelForm)`** on HousePoint, fields `['amount','description','date_for','assigned_approver']`.
  `__init__(self, user, *args, **kwargs)` filters `assigned_approver` queryset to
  Actives (`status='ACT'`) in `user.chapter`; relabels to "Request Approval From";
  forces `required=True`.
- **`ActivePointRequestForm(ModelForm)`** on HousePoint, fields `['amount','description','date_for']` — plain, no approver field (auto-routed to "any exec" in the view).
- **`DirectPointAssignmentForm(ModelForm)`** on HousePoint, fields `['user','amount','description','date_for']`.
  `__init__(self, request_user, *args, **kwargs)`: if `request_user.position.can_manage_points`
  → `user` field queryset = whole chapter, label "Assign to Member"; else → queryset
  restricted to `status='NM'` members, label "Assign to New Member". Uses
  `getattr(request_user, 'position', None)` defensively (handles `position=None` cleanly, unlike several views).
- **`SingleDueForm(ModelForm)`** on Due, fields `['title','amount','due_date','assigned_to']`,
  plus a non-model `type` ChoiceField (`CHARGE`/`AID`, RadioSelect, initial `CHARGE`).
  `__init__(self, user, ...)` restricts `assigned_to` queryset to `user.chapter` members,
  forces required. `clean()`: if `type == 'AID'` forces `amount` negative
  (`-abs(amount)`), else forces positive (`abs(amount)`) — sign is auto-corrected
  regardless of what the user typed, good behavior to test both directions.
- **`BulkDueForm(forms.Form)`** (plain Form, not ModelForm): `title`, `amount`
  (DecimalField 2 dp), `due_date`, `target_group` (choices `ALL/ACTIVES/NMS/PLEDGE_CLASS/SELECTED`),
  `selected_user_ids` (HiddenInput, CharField, not required — comma-joined ID string),
  `pledge_semester`/`pledge_year` (optional, used only when target_group=PLEDGE_CLASS).
  No `clean()` override — validity of pledge fields when `PLEDGE_CLASS` chosen is
  **not enforced by the form** (only checked ad hoc in the view, see below).
- **`BulkPointForm(forms.Form)`**: mirrors BulkDueForm shape — `type` (AWARD/PENALTY
  RadioSelect), `amount` (IntegerField min_value=1), `description`, `date_for`,
  `target_group` (same 5 choices), `selected_user_ids`, `pledge_semester`, `pledge_year`.
  `clean()`: negates `amount` if `type == 'PENALTY'`, else forces positive.

### Views (`dashboard/views.py`) — all `@login_required` except `dues_member`

- **`dashboard(request)`**: aggregates `HousePoint` APPROVED sum for user →
  `total_points` (0 if None via `or 0`); PENDING sum → `pending_points` (computed but
  **not actually included in the context dict** — dead variable, note for test:
  template gets `total_points`, `dues_balance`, `pending_tasks_count`, `announcements`
  only); `Due` unpaid sum for user → `dues_balance`; `Task` incomplete count for user
  → `pending_tasks_count`; last 5 `Announcement`s for `user.chapter` ordered by
  `-date_posted`, or `[]` if user has no chapter. Renders `dashboard/dashboard.html`.

- **`submit_points(request)`**: picks `NMPointRequestForm` if `user.status == 'NM'`
  else `ActivePointRequestForm`. POST: NM form instantiated with `(user, request.POST)`,
  Active form with `(request.POST)` only. On valid: `commit=False`, sets `user`,
  `submitted_by`, `chapter` from request context, saves; success message; redirect
  `dashboard`. Invalid → falls through, re-renders `dashboard/submit_points.html`
  with bound form. GET: instantiates empty form (NM variant needs `user` arg).

- **`assign_points(request)`**: permission check —
  `has_permission = (request.user.status != 'NM') or (request.user.position and request.user.position.can_manage_points)`
  (i.e., any Active can assign directly to NMs; NMs need explicit
  `can_manage_points` permission — unusual but as coded). If not permitted: error
  message, redirect `dashboard`. POST: `DirectPointAssignmentForm(request.user, request.POST)`;
  on valid, `commit=False`, sets `submitted_by`/`assigned_approver` = request.user,
  `chapter`, **`status='APPROVED'` (auto-approved, no workflow)**; saves; success
  message naming `point.user.username`; redirect `dashboard`. GET: empty form.
  Renders `dashboard/assign_points.html`.

- **`manage_point_request(request, pk)`**: `get_object_or_404(HousePoint, pk=pk)`.
  Permission logic (any of three must be true):
  `is_approver` (assigned_approver == request.user),
  `is_top2` (`request.user.position.can_manage_points` **and**
  `point.assigned_approver is None` — **will raise `AttributeError` if
  `request.user.position` is `None`**, since it's accessed unguarded — edge case /
  latent bug worth a test),
  `is_owner_countering` (submitted_by == request.user and status == 'COUNTERED').
  If none: error message, redirect `points_hub`. POST `action` param drives branching:
  - `'approve'`: status→APPROVED, feedback set; if approver **is** the original
    submitter (self-approval scenario) leaves `assigned_approver` untouched, else sets
    it to `request.user`; saves; success message with `point.amount`.
  - `'reject'`: status→REJECTED, feedback set, `assigned_approver`=request.user, saves; warning message.
  - `'counter'`: parses `new_amount = int(request.POST.get('new_amount'))` (raises
    `ValueError` caught → error message "Invalid amount for counter-offer." if not a
    valid int, e.g. missing/blank/non-numeric); sets amount+feedback; if currently
    `PENDING` → becomes `COUNTERED` with `assigned_approver=request.user` (approver
    counters submitter); if currently `COUNTERED` → becomes `PENDING` again (submitter
    counters back, ping-pong workflow); saves; info message.
  - No `action` matched (or GET) → just redirects `points_hub` with no changes/messages.
  Always redirects to `points_hub` (never renders own template directly).

- **`points_hub(request)`**: Complex aggregation view.
  - `total_points` = user's approved points sum.
  - `my_action_items`: HousePoints in user's chapter where
    (`assigned_approver=user AND status=PENDING`) OR (`submitted_by=user AND status=COUNTERED`).
  - `exec_queue`: only populated if `user.position and user.position.can_manage_points`
    — chapter HousePoints with `assigned_approver__isnull=True, status=PENDING`,
    excluding ones submitted by the user themself (self-approval prevention for the "any exec" pool).
  - Leaderboards: annotates all chapter `CustomUser`s with `total_points_val` =
    `Coalesce(Sum('points_received__amount', filter=Q(status='APPROVED')), 0)`, ordered
    descending; split in Python into `active_leaderboard` (status != NM) and
    `nm_leaderboard` (status == NM) — good test target for the Coalesce/annotate logic
    (users with zero points should show 0, not be excluded).
  - "Mother logs": `base_logs` = all chapter HousePoints; optional GET filters
    `recipient` (by `user_id`, only applied if `.isdigit()`) and `approver` (by
    `assigned_approver_id`, same digit guard); optional `sort` GET param restricted to
    an allow-list (`amount`, `-amount`, `date_submitted`, `-date_submitted`) else
    defaults to `-date_submitted` (prevents arbitrary-field SQL-injection-via-ordering,
    good to confirm with a test using an invalid sort value); split into `nm_logs`
    (`user__status='NM'`, first 50) and `active_logs` (excludes NM, first 50).
  - Also builds `chapter_members` (all, ordered by first_name) and `approvers_list`
    (excludes NM) for dropdowns.
  - Context includes `current_recipient`/`current_approver` as ints or `None`, and `current_sort`.
  - Renders `dashboard/points_hub.html`.

- **`dues_dashboard(request)`**: `is_treasurer = user.position.can_manage_finance` —
  **unguarded attribute access; raises `AttributeError` if `user.position is None`**
  (e.g. brand-new user with no assigned position) — notable bug/edge case to test.
  `my_dues` (unpaid, ordered by due_date), `my_history` (paid, ordered by
  `-due_date`), `total_due` = sum of unpaid. Renders `dashboard/dues_dashboard.html`.

- **`_helper_single_transaction(request, single_form)`** (not a view, private helper):
  if form valid, saves `Due`, success message naming `assigned_to`, redirects
  `dues_dashboard`; else returns `None` (caller falls through).

- **`_helper_bulk_transaction(request, bulk_form)`** (private helper): if form valid,
  resolves `target_group` to a queryset of `CustomUser`s in `request.user.chapter`:
  `ALL` → all members; `ACTIVES` → exclude NM; `NMS` → filter NM;
  **`PLEDGE_CLASS` → `sem, year = members.get('pledge_semester'), members.get('pledge_year')`
  then `members.filer(...)` — both of these are bugs**: `members` is a QuerySet, not a
  dict, so `.get('pledge_semester')` is invalid usage of `QuerySet.get()` (which expects
  field lookups, not a bare string) and will raise `TypeError`/`FieldError`; and
  `.filer` is a typo for `.filter` which will raise `AttributeError`. **The
  `PLEDGE_CLASS` bulk-dues branch is currently broken/dead code** — a test exercising
  it should be expected to surface this exception (worth flagging explicitly rather
  than "fixing" during a testing-only pass, per task scope — just document it as a
  known-broken path so future test authors don't assume it works). `SELECTED` →
  parses `selected_user_ids` comma-string into an ID list, filters by `id__in`. Then
  loops creating a `Due` per user with `title`/`amount`/`due_date`/`assigned_to`;
  counts created; success message; redirects `dues_dashboard`. Returns `None` if form invalid.

- **`manage_dues_creation(request)`**: permission check
  `request.user.position and request.user.position.can_manage_finance` — this one
  **is** guarded with `and`, avoiding the AttributeError seen elsewhere. If not
  permitted: error message, redirect `dues_dashboard`. Handles two independent forms
  in one view via POST key sniffing: `'submit_single' in request.POST` → binds
  `SingleDueForm(request.user, request.POST)`, delegates to
  `_helper_single_transaction`; `'directory_selection' in request.POST` → pre-fills
  `bulk_form` initial data (`target_group='SELECTED'`, joined `selected_user_ids`) from
  `request.POST.getlist('selected_members')`, sets `active_tab='bulk'`, info message
  with count; `'submit_bulk' in request.POST` → binds `BulkDueForm(request.POST)`,
  `active_tab='bulk'`, delegates to `_helper_bulk_transaction`. Renders
  `dashboard/manage_dues.html` with `single_form`, `bulk_form`, `active_tab`. Multiple
  independent POST branches — needs several distinct test cases (single valid, single
  invalid, bulk directory-handoff, bulk valid all/actives/nms/selected, bulk invalid, bulk pledge-class-broken).

- **`payment_page(request, pk)`**: `get_object_or_404(Due, pk=pk, assigned_to=request.user)`
  (404s if the due isn't the requesting user's — good security-boundary test). Renders
  `dashboard/payment_page.html` with `due` and `stripe_api_key` (module-level
  `stripe.api_key = settings.STRIPE_SECRET_KEY` set once at import time, line 359 —
  **note this means changing `STRIPE_SECRET_KEY` via `override_settings` mid-test-suite
  won't retroactively update `stripe.api_key`** unless the module is reloaded or the
  view re-sets it; something to be careful of when mocking Stripe).

- **`create_bulk_checkout_session(request)`**: `if request.POST:` (truthy check on
  QueryDict, not `request.method == 'POST'` — an empty POST body would be falsy and
  skip the block, edge case). Gets `due_ids` list from POST, filters `Due`s belonging
  to `request.user` matching those ids, builds Stripe line items
  (`unit_amount_decimal = due.amount * 100`, note **not integer-cast**, Decimal math),
  calls `stripe.checkout.Session.create(...)` with `metadata` including joined
  `due_ids_str`, `success_url`/`cancel_url` via `reverse()`. On success, redirects to
  `bulk_checkout.url` (303). On any `Exception`, returns `JsonResponse({'error': str(e)}, status=500)`
  — **must mock `stripe.checkout.Session.create`** in tests (both success and
  exception-raising mock cases). Falls through to `redirect('dashboard')` if not POST.

- **`process_payment(request, pk)`**: similar single-due Stripe Checkout Session
  creation; `due = get_object_or_404(Due, pk=pk, assigned_to=request.user)`;
  `amount = int(float(request.POST.get('due_amount')) * 100)` (would raise on
  missing/non-numeric `due_amount` — uncaught `TypeError`/`ValueError`, another edge case);
  creates session with `metadata` (`due_id`, `user_id`, `payment_type='single'`);
  redirects to Stripe URL on success, JSON 500 on exception. Falls through to
  `redirect('dashboard')` if not POST.

- **`payment_success(request)`**: reads `session_id` from GET; missing → error
  message, redirect `dashboard`. Retrieves `stripe.checkout.Session.retrieve(session_id)`
  — wrapped in try/except catching **any** `Exception` → error message, redirect
  `dashboard` (must mock both success and failure retrieval). Branches on
  `session.metadata['payment_type']`:
  - `'bulk_payment'`: parses `due_ids_str`, fetches matching `Due`s owned by
    `request.user`, marks each `is_paid=True` and **`amount=0`** (zeroes the balance
    outright rather than decrementing — differs from the single-payment path below),
    renders `dashboard/successful_payment.html` with `dues` list. **No dedup/session-replay
    guard on this bulk branch** (unlike the single-payment branch below) — refreshing
    this URL would re-zero already-paid dues harmlessly (idempotent since already 0/paid)
    but doesn't append to `processed_sessions`, worth testing.
  - Otherwise (single payment, implicit): computes `amount_paid = Decimal(session.amount_total)/100`;
    `due_id = session.metadata['due_id']`; `get_object_or_404(Due, pk=due_id)` (**no
    `assigned_to` filter here**, unlike `payment_page`/`process_payment` — a user could
    view another user's due's success page if they had a valid session_id, minor
    authorization gap worth a test); checks `request.session['processed_sessions']`
    list — if `session_id` already present, renders success template without mutating
    anything (idempotency guard, replay-safe); else appends session_id to the list,
    marks session modified, **decrements** `due.amount -= amount_paid`, sets
    `is_paid=True` if `<= 0`, saves, renders success template. Good test matrix:
    fresh single payment (full/partial), replayed single payment (session_id reused),
    bulk payment, missing session_id, Stripe retrieve exception, missing/malformed metadata.

- **`make_payment_treasurer(request, pk)`**: `get_object_or_404(Due, pk=pk)` (no
  ownership/permission check on who can view — accessible to any logged-in user for
  any due, this looks like a "treasurer confirms payment" screen but has **no
  permission gate at all**, unlike `mark_paid` which does check `can_manage_finance`
  — worth flagging as an access-control gap). Renders `dashboard/paid_treasurer.html`.

- **`mark_paid(request, pk)`**: `get_object_or_404(Due, pk=pk)`. If
  `request.user.position.can_manage_finance` (**unguarded — `AttributeError` if
  `position is None`**): reads optional `amount` from POST — blank/missing → pays
  full `due.amount`; else tries `int(amount)`, catches `(TypeError, ValueError)` →
  error message + redirect `brothers_due` for that due's owner; negative amount →
  error message + redirect (same); otherwise decrements `due.amount -= payment_amount`,
  marks paid if `<=0`, saves; success message (different text if fully paid vs.
  partial, including remaining balance and the assignee's name). Else (no permission):
  error message, no mutation. **Always** redirects to `brothers_due` (named URL
  `brothers_due` taking `due.assigned_to.pk`) regardless of branch/outcome.

- **`directory(request)`**: lists chapter members ordered by `status, last_name,
  first_name`; optional `q` GET param filters by icontains across
  first_name/last_name/major/hometown (OR'd); optional `status` GET param exact-filters.
  Renders `dashboard/directory.html`.

- **`unpaid_directory(request)`**: chapter members with at least one unpaid `Due`
  (`dues__is_paid=False`), `.distinct()`, annotated with `total_dues = Sum('dues__amount')`
  — **note**: since the base filter already restricts to unpaid dues, but the `Sum`
  annotation isn't filtered by `is_paid=False` specifically, if a member has some paid
  and some unpaid dues, `total_dues` would sum **all** their dues rows (paid + unpaid)
  because the annotation aggregates over the full joined `dues` relation shaped by the
  `filter()`, not scoped separately — this is a subtle Django ORM gotcha (the filter()
  call constrains the join used by the annotate) worth a dedicated test with a member
  who has both paid and unpaid dues to confirm actual behavior. Optional `filter` GET
  param (icontains on name/major/hometown) and `status` GET param (exact). Renders
  `dashboard/unpaid_directory.html`.

- **`dues_member(request, pk)`**: **no `@login_required` decorator** (only view in the
  file besides none — double-check: yes, this is the sole unprotected view). Fetches
  `CustomUser` by pk (404 if missing), all their `Due`s ordered by `is_paid, due_date`.
  Renders `dashboard/member_dues_details.html`. **Accessible to anonymous users** and
  cross-chapter (no chapter check) — significant access-control gap worth explicit
  security-boundary tests (anonymous access, cross-chapter access).

- **`brother_profile(request, pk)`**: fetches `CustomUser` by pk (404 if missing); if
  `brother.chapter != request.user.chapter` → error message, redirect `dashboard`
  (cross-chapter protection, unlike `dues_member` above). Renders
  `dashboard/brother_profile.html`.

- **`manage_points_creation(request)`**: permission check
  `request.user.position and request.user.position.can_manage_points` (guarded). Not
  permitted → error, redirect `dashboard`. Handles directory-handoff pre-fill (same
  pattern as dues) and `'submit_bulk_points' in request.POST` branch: resolves
  `target_group` the same way as bulk dues (`ALL`/`ACTIVES`/`NMS`/`PLEDGE_CLASS`/`SELECTED`)
  — **this one's `PLEDGE_CLASS` branch is correctly implemented**
  (`base_qs.filter(pledge_semester=..., pledge_year=...)`, no typo, unlike the dues
  version), loops creating `HousePoint`s with `status='APPROVED'`,
  `assigned_approver=request.user` (auto-approved bulk admin action); success message
  with count; redirect `dashboard`. Renders `dashboard/manage_points.html`.

- **`edit_log_point(request, pk)`**: `get_object_or_404(HousePoint, pk=pk)`.
  Permission: `can_edit_all` (guarded `can_manage_points`) OR `can_edit_nm` (guarded
  `can_manage_nm_points` AND `point.user.status == 'NM'`). Not permitted → error,
  redirect `points_hub`. POST: tries `int(request.POST.get('amount'))`, catches
  `ValueError` → error message; else sets `point.amount`, saves, success message.
  Always redirects `points_hub`.

### URLs (`dashboard/urls.py`) — all mounted under `dashboard/`
| Path | Name | View |
|---|---|---|
| `` | `dashboard` | `views.dashboard` |
| `points/` | `points_hub` | `views.points_hub` |
| `points/submit/` | `submit_points` | `views.submit_points` |
| `points/assign/` | `assign_points` | `views.assign_points` |
| `points/manage/<int:pk>/` | `manage_point` | `views.manage_point_request` |
| `dues/` | `dues_dashboard` | `views.dues_dashboard` |
| `dues/paid/<int:pk>/` | `make_mark_paid` | `views.make_payment_treasurer` |
| `dues/checkout_treasurer/<int:pk>/` | `mark_paid` | `views.mark_paid` |
| `dues/unpaid_directory/` | `unpaid_directory` | `views.unpaid_directory` |
| `dues/brothers_due/<int:pk>/` | `brothers_due` | `views.dues_member` |
| `dues/manage/` | `manage_dues_creation` | `views.manage_dues_creation` |
| `dues/payment_success/` | `payment_success` | `views.payment_success` |
| `dues/checkout/<int:pk>/` | `create_checkout_session` | `views.process_payment` |
| `dues/create_bulk_checkout_session/` | `create_bulk_checkout_session` | `views.create_bulk_checkout_session` |
| `dues/payment_page/<int:pk>/` | `payment_page` | `views.payment_page` |
| `directory/` | `brother_directory` | `views.directory` |
| `directory/member/<int:pk>/` | `brother_profile` | `views.brother_profile` |
| `points/manage/` | `manage_points_creation` | `views.manage_points_creation` |
| `points/edit_log/<int:pk>/` | `edit_log_point` | `views.edit_log_point` |

Note two commented-out/dead routes in the file: `inbox/` (`views.inbox`) and
`ledger/` (`views.chapter_ledger`) — corresponding templates (`inbox.html`,
`ledger.html`) exist on disk but **no view functions exist for them** in
`views.py` — dead templates, not testable as routes.

### Admin (`dashboard/admin.py`)
- `HousePointAdmin`: list_display (user, amount, status, submitted_by,
  assigned_approver, date_submitted), filter by status/chapter, search
  user__username/description.
- `DueAdmin`: list_display (title, amount, assigned_to, is_paid, due_date), filter is_paid/is_template.
- `TaskAdmin`: list_display (title, assigned_to, due_date, completed), filter completed/assigned_to.
- `AnnouncementAdmin`: list_display (title, chapter, author, date_posted), filter chapter.
- All purely declarative, no custom actions/methods.

### Migrations
- `dashboard/migrations/`: `0001_initial.py`, `0002_initial.py` — 2 migrations (low churn; unusual to have two "_initial" named migrations, but only 2 files total).

### Templates referenced by views
`dashboard/dashboard.html`, `dashboard/submit_points.html`, `dashboard/assign_points.html`,
`dashboard/points_hub.html`, `dashboard/dues_dashboard.html`, `dashboard/manage_dues.html`,
`dashboard/payment_page.html`, `dashboard/successful_payment.html`,
`dashboard/paid_treasurer.html`, `dashboard/directory.html`, `dashboard/unpaid_directory.html`,
`dashboard/member_dues_details.html`, `dashboard/brother_profile.html`,
`dashboard/manage_points.html`. Also a partial: `dashboard/partials/point_row.html`
(likely included by points_hub, not directly rendered by a view — check with
`assertTemplateUsed` only if it's actually `{% include %}`d). Dead templates with no
view (`inbox.html`, `ledger.html`) as noted above.

---

## 6. Cross-cutting concerns

### Auth & permission patterns
- Most dashboard views use `@login_required` (redirects to `LOGIN_URL='login'` if anonymous).
- **`dues_member` is the one dashboard view with no `@login_required`** — accessible anonymously.
- Permission checks are **inconsistent** in how they guard against `position=None`:
  - Guarded (safe): `assign_points` (`request.user.position and ...`),
    `manage_dues_creation`, `manage_points_creation`, `edit_log_point`,
    `DirectPointAssignmentForm.__init__` (uses `getattr(..., None)`).
  - **Unguarded (will raise `AttributeError` if `user.position is None`)**:
    `dues_dashboard` (`user.position.can_manage_finance`),
    `manage_point_request`'s `is_top2` check (`request.user.position.can_manage_points`),
    `mark_paid` (`request.user.position.can_manage_finance`).
  - This inconsistency is a strong candidate for a shared "user with no position"
    fixture, run against every permission-gated view to see which ones 500 vs. gracefully deny.
- Chapter-scoping (multi-tenancy) is enforced in some views (`brother_profile`,
  most queries filtered by `request.user.chapter`) but **not** in others
  (`dues_member` has zero scoping; `payment_success`'s single-due branch fetches by
  pk with no `assigned_to`/chapter filter). Worth a deliberate "cross-tenant leakage" test sweep.

### External services to mock
1. **Stripe** (`dashboard/views.py`): `stripe.checkout.Session.create` (2 call sites:
   `create_bulk_checkout_session`, `process_payment`) and `stripe.checkout.Session.retrieve`
   (`payment_success`). `stripe.api_key` is set once at module import from
   `settings.STRIPE_SECRET_KEY` (empty string in dev/test unless env var set). Use
   `unittest.mock.patch('dashboard.views.stripe.checkout.Session.create')` /
   `.retrieve` style mocks (patch where imported/used, i.e. in the `dashboard.views`
   namespace) to avoid real network calls. Mock both success-object shapes (with
   `.url`, `.amount_total`, `.metadata` as needed) and exception-raising cases.
2. **Email** (`users/views.py::register`, `homepage/admin.py::approve_requests`):
   Django's test runner auto-switches `EMAIL_BACKEND` to
   `django.core.mail.backends.locmem.EmailBackend` during `manage.py test`, so tests
   can assert against `django.core.mail.outbox` rather than mocking SMTP directly. No
   explicit mock needed, just use `django.core.mail.outbox` assertions.
3. **File uploads** (`CustomUser.image`): local `MEDIA_ROOT` used in dev/test (no AWS
   env vars present in typical test env) — use `override_settings(MEDIA_ROOT=<tempdir>)`
   plus `SimpleUploadedFile` for profile-picture upload tests, and clean up written
   files (Django doesn't auto-delete uploaded test files from disk).
4. **`secrets.token_hex`** (`homepage/admin.py::approve_requests`): not strictly
   necessary to mock (deterministic-enough with regex/length assertions), but can be
   patched for deterministic invite-code assertions if desired.
5. No other third-party API calls found (no Twilio, no other payment processors, no
   external REST calls beyond Stripe).

### Messages framework
Used pervasively via `django.contrib.messages` (`success`, `error`, `warning`, `info`)
across almost every view with a mutation or permission denial. Tests can assert via
`response.context['messages']` or by checking redirected-to page's rendered content,
or directly inspect `list(get_messages(response.wsgi_request))`.

### Known bugs / broken code paths (do not silently "fix" while writing tests — document via tests that pin current behavior, or flag explicitly if the task later asks for fixes)
- `_helper_bulk_transaction` (`dashboard/views.py`) `PLEDGE_CLASS` branch:
  `members.get('pledge_semester')` and `members.filer(...)` — both invalid, will raise.
- `dues_dashboard`, `manage_point_request` (`is_top2`), `mark_paid`: unguarded
  `request.user.position.<flag>` access — `AttributeError` when `position is None`.
- `dashboard` view computes `pending_points` but never puts it in the template context (dead code, harmless).
- `payment_success` single-payment branch has no `assigned_to`/ownership filter on the `Due` lookup.
- `make_payment_treasurer` has no permission check at all (any logged-in user can view any due's "mark paid" screen, though it appears to be read-only/display-only based on the view code — confirm template doesn't expose a mutation form without a corresponding permission-checked POST handler).
- `dues_member` has no `@login_required` and no chapter scoping.
- Dead templates `inbox.html`, `ledger.html` with corresponding commented-out URL routes and no view functions — not testable/relevant.
- `CustomUser.save()` PIL-based image-thumbnailing override is commented out (dead code) — don't test for thumbnailing.

---

## 7. Existing test infrastructure

- All three apps have only Django's default boilerplate `tests.py`
  (`from django.test import TestCase` + a comment, zero actual tests).
- `palamedes/requirements.txt` contents (file is UTF-16 encoded — note for anyone
  editing it with tools that assume UTF-8): `asgiref`, `certifi`,
  `charset-normalizer`, `click`, `colorama`, `crispy-bootstrap4`, `dj-database-url`,
  `Django`, `django-crispy-forms`, `gunicorn`, `idna`, `packaging`, `pillow`,
  `psycopg2-binary`, `python-dotenv`, `requests`, `sqlparse`, `stripe`,
  `typing_extensions`, `urllib3`, `whitenoise`, `boto3`, `django-storages`.
  **No `coverage`, `pytest`, `pytest-django`, `factory_boy`, `faker`, or `responses`/`requests-mock`
  listed** — these would need to be added (likely to a separate `requirements-dev.txt`
  or added to the main file) before a coverage-driven test phase can run
  `coverage run manage.py test && coverage report`.
- No `pytest.ini`, `setup.cfg`, `tox.ini`, `.coveragerc`, or `pyproject.toml` anywhere in the repo.
- No `.github/workflows/` directory — **no CI configured at all**. Tests would currently only run locally via `python manage.py test`.

---

## 8. Complexity ranking (easy → hard) for future test-phase planning

**Easiest (pure model / form unit tests, no request cycle, no external services)**
- `homepage.ChapterRequest` model fields/`__str__`/defaults.
- `users.Chapter`, `users.Position` model fields/`__str__`/uniqueness constraints.
- `dashboard.HousePoint`, `Due`, `Task`, `Announcement` model fields/`__str__`/defaults.
- `homepage.ChapterRequestForm` validation (required fields, email format).
- `dashboard` plain forms without request-dependent `__init__`: `ActivePointRequestForm`,
  `BulkDueForm`, `BulkPointForm` (`clean()` sign-flipping logic is a nice deterministic unit test).

**Easy-medium (forms/views requiring a logged-in user + fixtures, but no external services)**
- `users.CustomUser` model (needs a `Chapter`+`Position` fixture but otherwise plain).
- `homepage` views: `home` (auth branch), `about`, `start_chapter` (form success/invalid).
- `users.ProfileUpdateForm`, `users.profile` view (GET/POST, needs `SimpleUploadedFile` for image field coverage).
- `dashboard.directory`, `unpaid_directory`, `brother_profile` (read-only, filter/search logic, chapter-scoping assertions).
- `dashboard.dashboard` (aggregation view) — needs multiple fixture rows to exercise Sum/Coalesce paths meaningfully.
- `dashboard.points_hub` — larger fixture setup (multiple users/points across statuses) but no external services; good candidate for a dedicated "fixture-heavy" test module given how much it aggregates (leaderboards, mother logs, filters, sort allow-list).

**Medium (multi-branch workflow views, several permission paths, some latent bugs to pin down)**
- `dashboard.submit_points`, `assign_points`, `manage_point_request` (approve/reject/counter/counter-back state machine — worth enumerating every status transition), `edit_log_point`.
- `dashboard.manage_dues_creation` / `manage_points_creation` and their private helpers — many independent POST-key-driven branches, including the known-broken `PLEDGE_CLASS` dues path and the working `PLEDGE_CLASS` points path (asymmetry worth explicit contrast tests).
- `dashboard.mark_paid` — several numeric edge cases (missing amount, non-numeric, negative, overpayment→is_paid flip) plus the unguarded-`position` bug.
- `users.register` / `users.activate` — email verification token flow (valid/invalid/expired/tampered token, nonexistent uid, already-active user), plus dependency on pre-seeded `Position` rows ("President"/"No Position") via `CustomUserCreationForm.save()`. Requires `django.core.mail.outbox` assertions.
- `homepage.admin.approve_requests` admin action — multi-step side effects (Chapter get_or_create, 4 Position rows, is_approved flip, email send) best tested via `Model.approve_requests(None, request, ChapterRequest.objects.filter(...))` direct call or via Django admin test client POST to the changelist action endpoint.

**Hardest (Stripe-integrated, session-state-dependent, multiple exception paths to mock)**
- `dashboard.payment_page`, `create_bulk_checkout_session`, `process_payment`,
  `payment_success` — require mocking `stripe.checkout.Session.create`/`.retrieve`
  with varying return shapes (metadata dict contents differ per payment_type),
  simulating exceptions for the `except Exception` branches, and manipulating
  `request.session['processed_sessions']` to test the replay-idempotency guard on the
  single-payment path (and confirming the bulk path's lack of an equivalent guard).
  This cluster likely deserves its own dedicated test phase/module given the mocking
  setup overhead (a shared Stripe-mock helper/fixture would pay off across ~4 tests).
