from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Chapter, Position

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'chapter', 'can_manage_finance', 'can_manage_points', 'can_manage_roster', 'can_manage_tasks', 'can_create_positions')
    list_filter = ('chapter',)
    search_fields = ('title', 'chapter__name')

@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('name', 'university', 'invite_code')
    search_fields = ('name', 'university')

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # List View Settings
    list_display = ('username', 'email', 'first_name', 'last_name', 'chapter', 'status', 'position')
    list_filter = ('chapter', 'status', 'is_staff')
    
    # Edit User Settings (When changing an existing user)
    fieldsets = UserAdmin.fieldsets + (
        ('Fraternity Info', {'fields': ('chapter', 'status', 'position', 'major', 'phone_number', 'hometown', 'bio', 'pledge_semester', 'pledge_year')}),
    )
    
    # Create User Settings
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Fraternity Info', {'fields': ('chapter', 'status', 'position', 'major', 'phone_number', 'hometown', 'bio', 'pledge_semester', 'pledge_year')}),
    )