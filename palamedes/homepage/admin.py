from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from .models import ChapterRequest
from users.models import Chapter # Import the Chapter model from the users app
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

        # 3. Mark request as approved
        req.is_approved = True
        req.save()

        # 4. Send the Email (Prints to Console)
        subject = f"Congratulations! {req.fraternity_name} is Approved."
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