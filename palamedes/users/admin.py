from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Chapter

# Register the Chapter model so you can create/edit chapters manually if needed
@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('name', 'university', 'invite_code')
    search_fields = ('name', 'university')

# Register the CustomUser model
# Inherited from UserAdmin = keep the password hashing functionality
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # What I see in the user list view
    list_display = ('username', 'email', 'chapter', 'role', 'is_staff')
    list_filter = ('chapter', 'role', 'is_staff')
    
    # Controls what fields I see when editing a user
    fieldsets = UserAdmin.fieldsets + (
        ('Profile Picture', {'fields': ('image',)}),
        ('Fraternity Info', {'fields': ('chapter', 'role', 'major', 'phone_number', 'hometown', 'bio')}),
    )
    
    # Controls what fields I see when creating a user
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Fraternity Info', {'fields': ('chapter', 'role', 'major', 'phone_number', 'hometown', 'bio')}),
    )