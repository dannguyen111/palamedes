# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Palamedes** is a Django-based Greek Organization Management System. It allows chapters (Greek organizations) to manage member rosters, track house points, manage dues/finances, assign tasks, and communicate via announcements.

**Tech Stack:**
- Django 5.2.8 (Python web framework)
- SQLite for development, PostgreSQL for production
- Django ORM for database modeling
- Crispy Forms + Bootstrap 4 for form rendering
- Stripe for payment processing
- Email backend for email verification and password resets
- AWS S3 support via django-storages for production media

## Architecture

### App Structure

The project is organized into three main Django apps:

1. **homepage** - Public-facing pages (landing page, about, chapter request form)
   - `views.py`: Home view (redirects authenticated users to dashboard), about page, chapter request submission
   - `models.py`: ChapterRequest model for new chapters to request joining
   - `forms.py`: ChapterRequestForm for homepage form
   - `urls.py`: Routes for homepage

2. **users** - Authentication and user management
   - `models.py`: CustomUser (extends AbstractUser with chapter affiliation, position, pledge info, profile fields), Chapter, Position
   - `views.py`: Registration (with email verification), login, account activation, profile updates
   - `forms.py`: CustomUserCreationForm, ProfileUpdateForm
   - `urls.py`: Auth-related URLs
   - **Key feature**: Email-verified registration - users are inactive until they confirm their email

3. **dashboard** - Main application for authenticated users
   - `models.py`: HousePoint (points system with approval workflow), Due (financial tracking), Task (task assignments), Announcement (chapter communications)
   - `views.py`: Dashboard view (summary stats), points submission/approval, dues management, task assignment, announcements
   - `forms.py`: Forms for submitting points, dues, tasks
   - `urls.py`: Dashboard routes

### Data Model

**User Management:**
- CustomUser extends Django's AbstractUser with chapter/position affiliation
- Chapter has name, university, and unique invite codes for new members (nm_invite_code) and active members (active_invite_code)
- Position represents officer roles with permission flags: can_manage_roster, can_manage_finance, can_manage_points, can_manage_tasks, can_create_positions, can_manage_nm_points

**Member Features:**
- **House Points**: Members submit point requests (for new members or actives). Points have approval workflow (PENDING → APPROVED/REJECTED/COUNTERED). For new members, points may require specific manager approval; for actives, any exec can approve.
- **Dues**: Financial tracking. Dues can be templates (assigned to all members) or individual. Stripe integration handles payments.
- **Tasks**: Officers assign tasks to members with due dates.
- **Announcements**: Chapter-specific announcements visible on member dashboard.

### Configuration

- `palamedes/settings.py`: Main Django settings
  - Uses environment variables (.env file) for SECRET_KEY, DEBUG, ALLOWED_HOSTS, database URL
  - Custom user model: AUTH_USER_MODEL = 'users.CustomUser'
  - Installed apps: homepage, users, dashboard, auth, crispy_forms, static files, etc.
  - Email backend configured for password reset and verification emails
- `palamedes/urls.py`: URL routing (admin panel, app includes, password reset URLs, media serving in DEBUG mode)
- `palamedes/wsgi.py` & `asgi.py`: Application entry points

## Development

### Setup

1. **Create virtual environment** and activate it
2. **Install dependencies**: `pip install -r palamedes/requirements.txt`
3. **Create .env file** in the root with:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=True
   ALLOWED_HOSTS=127.0.0.1,localhost
   DATABASE_URL=sqlite:///db.sqlite3
   ```
4. **Run migrations**: `cd palamedes && python manage.py migrate`
5. **Create superuser** (optional): `cd palamedes && python manage.py createsuperuser`
6. **Run dev server**: `cd palamedes && python manage.py runserver`

Server runs at `http://127.0.0.1:8000`

### Common Commands

All commands should be run from the `palamedes/` directory.

**Running the development server:**
```bash
cd palamedes
python manage.py runserver
```

**Database migrations:**
```bash
# Create migration files for model changes
python manage.py makemigrations

# Apply migrations to database
python manage.py migrate

# See migration history
python manage.py showmigrations
```

**Testing:**
```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test homepage
python manage.py test users
python manage.py test dashboard

# Run a specific test class or method
python manage.py test users.tests.RegistrationTest
python manage.py test users.tests.RegistrationTest.test_valid_registration
```

**Django shell (interactive Python with Django context):**
```bash
python manage.py shell
```

**Admin interface:**
```bash
# Access at http://127.0.0.1:8000/admin/ (requires superuser)
```

### Environment Variables

Create a `.env` file in the project root (same level as manage.py) with:
- `SECRET_KEY`: Django secret key (use a strong random string in production)
- `DEBUG`: Set to 'True' for development, 'False' for production
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `DATABASE_URL`: Database connection string (defaults to SQLite in dev)
- `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`: For email verification and password resets

## Important Patterns

### Email Verification

Users registering via the homepage go through email verification:
1. User submits registration form → account created but inactive (is_active=False)
2. Verification email sent with activation link containing uid and token
3. User clicks link → `activate()` view decodes uid and validates token
4. User activated and redirected to login

**Key files:** `users/views.py` (register, activate functions), `users/templates/acc_active_email.html`

### Points Approval Workflow

Points submissions have a status flow: PENDING → APPROVED/REJECTED/COUNTERED

New member vs. active member points may have different approval requirements. Feedback field stores rejection reasons or counter-offer details.

**Key model:** `dashboard/models.py::HousePoint`
**Key views:** `dashboard/views.py` (submit_points, approve_points functions)

### Custom User Model

The CustomUser extends AbstractUser. When querying users, use the CustomUser model, not the default User model:
```python
from users.models import CustomUser
# NOT from django.contrib.auth.models import User
```

Authentication and login work normally with CustomUser since it's configured in settings.py as AUTH_USER_MODEL.

### Forms and Crispy Forms

Forms are rendered with Crispy Forms + Bootstrap 4. Templates should use the `crispy_forms` template tag:
```django
{% load crispy_forms_tags %}
{{ form|crispy }}
```

## Common Development Scenarios

**Adding a new model field:**
1. Add field to model in `app/models.py`
2. Run `python manage.py makemigrations app_name`
3. Review the generated migration file
4. Run `python manage.py migrate`
5. Update forms if needed (`app/forms.py`)
6. Update templates if needed

**Adding a new feature/view:**
1. Add view function to `app/views.py`
2. Add URL route to `app/urls.py`
3. Create template in `app/templates/app/template_name.html`
4. Add link/button to relevant page
5. Test in browser

**Making model changes that affect existing data:**
- Use data migrations (`python manage.py makemigrations --empty app_name --name migration_name`) to handle data transformations
- Test migrations with production-like data

## Testing Notes

- Test files are `app/tests.py` in each app
- Use Django's TestCase class which provides database transaction rollback
- Run tests frequently during development to catch regressions
- Email sending in tests won't actually send; check for message creation instead
