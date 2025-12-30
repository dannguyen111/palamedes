from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from .models import ChapterRequest
from users.models import Chapter, Position
import secrets # To generate the invite code

def approve_requests(modeladmin, request, queryset):
    for req in queryset:
        if req.is_approved:
            continue # Skip if already approved

        # 1. Generate a random invite code (8 characters)
        code = secrets.token_hex(4).upper()

        # 2. Create the actual Chapter in the database
        # We use get_or_create to prevent duplicates if you click twice
        chapter, created = Chapter.objects.get_or_create(
            name=req.fraternity_name,
            university=req.university,
            defaults={'invite_code': code}
        )

        # Create default positions for the chapter
        Position.objects.create(
            chapter=chapter, title="President",
            can_manage_roster=True, can_manage_finance=True, 
            can_manage_points=True, can_manage_tasks=True, can_create_positions=True
        )
        
        # Vice President: Can do everything EXCEPT create positions/change President
        Position.objects.create(
            chapter=chapter, title="Vice President",
            can_manage_roster=True, can_manage_finance=False, 
            can_manage_points=True, can_manage_tasks=True, can_create_positions=False
        )

        # Treasurer: Money only
        Position.objects.create(
            chapter=chapter, title="Treasurer",
            can_manage_roster=False, can_manage_finance=True, 
            can_manage_points=False, can_manage_tasks=False, can_create_positions=False
        )

        # No position
        Position.objects.create(
            chapter=chapter, title="No Position",
            can_manage_roster=False, can_manage_finance=False, 
            can_manage_points=False, can_manage_tasks=False, can_create_positions=False
        )

        # 4. Mark request as approved
        req.is_approved = True
        req.save()

        # 5. Send the Email (Prints to Console)
        subject = f"Palamedes: {req.fraternity_name} at {req.university} is Approved."
        message = f"""
        Hello President,

        Your chapter request for {req.fraternity_name} at {req.university} has been approved.

        Your Invite Code is: {chapter.invite_code}

        Please register your President account here:
        http://127.0.0.1:8000/register/
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