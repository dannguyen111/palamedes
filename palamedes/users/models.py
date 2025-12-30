# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from PIL import Image

class Chapter(models.Model):
    name = models.CharField(max_length=100, help_text="e.g. Theta Chi")
    university = models.CharField(max_length=100, help_text="e.g. UC Riverside")
    # This code allows new members to join the right house
    invite_code = models.CharField(max_length=10, unique=True) 

    def __str__(self):
        return f"{self.name} - {self.university}"
    
class Position(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='positions')
    title = models.CharField(max_length=50)
    
    # Permissions (Boolean Flags)
    can_manage_roster = models.BooleanField(default=False, help_text="Can invite/remove members and change their positions.")
    can_manage_finance = models.BooleanField(default=False, help_text="Can create dues and mark items as paid.")
    can_manage_points = models.BooleanField(default=False, help_text="Can approve/deny point requests.")
    can_manage_tasks = models.BooleanField(default=False, help_text="Can assign tasks to others.")
    can_create_positions = models.BooleanField(default=False, help_text="Can create new officer roles (President only).")
    
    def __str__(self):
        return f"{self.title} ({self.chapter.name})"

class CustomUser(AbstractUser):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='members', null=True, blank=True)
    
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    STATUS_CHOICES = [('NM', 'New Member'), ('ACT', 'Active')]
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, default='NM')

    # Profile Fields
    major = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    hometown = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    image = models.ImageField(upload_to='profile_pics/', default='default.jpg')

    SEMESTER_CHOICES = [('Fall', 'Fall'), ('Spring', 'Spring')]
    pledge_semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES, blank=True, null=True)
    pledge_year = models.IntegerField(blank=True, null=True, help_text="e.g. 2025")
    
    def __str__(self):
        if self.position: return f"{self.username} ({self.position.title})"
        return self.username
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.image:
            img = Image.open(self.image.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.image.path)