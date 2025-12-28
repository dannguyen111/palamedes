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
    # List View Settings
    list_display = ('username', 'email', 'first_name', 'last_name', 'chapter', 'role')
    list_filter = ('chapter', 'role', 'is_staff')
    
    # Edit User Settings (When changing an existing user)
    fieldsets = UserAdmin.fieldsets + (
        ('Fraternity Info', {'fields': ('chapter', 'role', 'major', 'phone_number', 'hometown', 'bio', 'pledge_semester', 'pledge_year')}),
    )
    
    # Create User Settings (This is what you asked for)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Fraternity Info', {'fields': ('chapter', 'role', 'major', 'phone_number', 'hometown', 'bio', 'pledge_semester', 'pledge_year')}),
    )