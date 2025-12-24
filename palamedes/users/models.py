# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class Chapter(models.Model):
    name = models.CharField(max_length=100, help_text="e.g. Theta Chi")
    university = models.CharField(max_length=100, help_text="e.g. UC Riverside")
    # This code allows new members to join the right house
    invite_code = models.CharField(max_length=10, unique=True) 

    def __str__(self):
        return f"{self.name} - {self.university}"

class CustomUser(AbstractUser):
    # Role Constants
    ROLE_CHOICES = [
        ('NM', 'New Member'),
        ('ACT', 'Active'),
        ('EXEC', 'Executive/Admin'),
        ('FIN', 'Treasurer'),
        ('PRES', 'President'),
        ('VPRES', 'Vice President'),
        ('NME', 'New Member Educator'),
    ]

    # Link every user to a Chapter
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='members', null=True, blank=True)
    
    # Extra Profile Fields (for Brother Discovery)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='NM')
    major = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    hometown = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"