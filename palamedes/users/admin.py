from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Chapter

# Register the Chapter model so you can create/edit chapters manually if needed
@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('name', 'university', 'invite_code')
    search_fields = ('name', 'university')

# Register the CustomUser model
# We inherit from UserAdmin so we keep the password hashing functionality
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # This controls what you see in the list of users
    list_display = ('username', 'email', 'chapter', 'role', 'is_staff')
    list_filter = ('chapter', 'role', 'is_staff')
    
    # This controls what fields you see when editing a user
    fieldsets = UserAdmin.fieldsets + (
        ('Fraternity Info', {'fields': ('chapter', 'role', 'major', 'phone_number', 'hometown', 'bio')}),
    )
    
    # This controls what fields you see when CREATING a new user in admin
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Fraternity Info', {'fields': ('chapter', 'role', 'major', 'phone_number', 'hometown', 'bio')}),
    )