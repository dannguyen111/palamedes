from django.contrib import admin
from .models import HousePoint, Due, Task, Announcement

@admin.register(HousePoint)
class HousePointAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'reason', 'approved', 'date_submitted')
    list_filter = ('approved', 'user__chapter') # Filter by chapter!

@admin.register(Due)
class DueAdmin(admin.ModelAdmin):
    list_display = ('title', 'amount', 'assigned_to', 'is_paid', 'due_date')
    list_filter = ('is_paid', 'is_template')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assigned_to', 'due_date', 'completed')
    list_filter = ('completed', 'assigned_to')

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'chapter', 'author', 'date_posted')
    list_filter = ('chapter',)