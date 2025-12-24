# platform/models.py
from django.db import models
from django.conf import settings

class HousePoint(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points')
    amount = models.IntegerField()
    reason = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date_submitted = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} pts"

class Due(models.Model):
    title = models.CharField(max_length=100) # e.g. "Fall 2025 Dues"
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    # If true, this is a template charge assigned to everyone
    is_template = models.BooleanField(default=False)
    # If linked to a specific user (an individual bill)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='dues')
    is_paid = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.title} - ${self.amount}"

class Task(models.Model):
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()
    completed = models.BooleanField(default=False)
    
    def __str__(self):
        return self.title