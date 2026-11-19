from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from .models import ChapterRequest
from users.models import Chapter, Position
import secrets # To generate the invite code

# Positions every new chapter starts with: title -> permission flags.
DEFAULT_POSITIONS = {
    "President": dict(
        can_manage_roster=True, can_manage_finance=True, can_manage_nm_points=True,
        can_manage_points=True, can_manage_tasks=True, can_create_positions=True,
    ),
    # Vice President: Can do everything EXCEPT create positions/change President
    "Vice President": dict(
        can_manage_roster=True, can_manage_finance=False, can_manage_nm_points=True,
        can_manage_points=True, can_manage_tasks=True, can_create_positions=False,
    ),
    # Treasurer: Money only
    "Treasurer": dict(
        can_manage_roster=False, can_manage_finance=True, can_manage_nm_points=False,
        can_manage_points=False, can_manage_tasks=False, can_create_positions=False,
    ),
    "No Position": dict(
        can_manage_roster=False, can_manage_finance=False, can_manage_nm_points=False,
        can_manage_points=False, can_manage_tasks=False, can_create_positions=False,
    ),
}

def approve_requests(modeladmin, request, queryset):
    for req in queryset:
        if req.is_approved:
            continue # Skip if already approved
        # One transaction per request: if anything fails (e.g. the email),
        # this request is left untouched instead of half-approved.
        with transaction.atomic():
            _approve_one(req)

def _approve_one(req):
    """Approve one ChapterRequest: create its chapter, invite codes and
    default positions, then email the president."""
    # 1. Generate a random invite code (8 characters)
    nm_code = secrets.token_hex(4).upper()
    active_code = secrets.token_hex(4).upper()

    # 2. Create the actual Chapter in the database
    # We use get_or_create to prevent duplicates if you click twice
    chapter, created = Chapter.objects.get_or_create(
        name=req.fraternity_name,
        university=req.university,
        defaults={
            'nm_invite_code': nm_code,
            'active_invite_code': active_code
        }
    )

    if not created and (not chapter.nm_invite_code or not chapter.active_invite_code):
        chapter.nm_invite_code = nm_code
        chapter.active_invite_code = active_code
        chapter.save()

    # 3. Create the default positions, skipping any the chapter already
    # has (a second request for the same chapter must not duplicate them).
    for title, flags in DEFAULT_POSITIONS.items():
        Position.objects.get_or_create(chapter=chapter, title=title, defaults=flags)

    # 4. Mark request as approved
    req.is_approved = True
    req.save()

    # 5. Send the Email (Prints to Console)
    subject = f"Palamedes: {req.fraternity_name} at {req.university} is Approved."
    message = f"""
    Hello President,

    Your chapter request for {req.fraternity_name} at {req.university} has been approved.

    Your Invite Codes are:
    - Active Member Code: {chapter.active_invite_code}
    - New Member Code: {chapter.nm_invite_code}

    Please register your President account here using the Active code:
    https://palamedes-5af1.onrender.com/register/
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [req.president_email], # Sends to the president
        fail_silently=False,
    )

approve_requests.short_description = "Approve selected requests & Create Chapter"

@admin.register(ChapterRequest)
class ChapterRequestAdmin(admin.ModelAdmin):
    list_display = ('fraternity_name', 'university', 'date_requested', 'is_approved')
    actions = [approve_requests]