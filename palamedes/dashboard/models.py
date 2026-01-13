# platform/models.py
from django.db import models
from django.conf import settings
from users.models import Chapter
from django.utils import timezone

class HousePoint(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COUNTERED', 'Counter-Offer Made'),
    ]

    # Who is this point for?
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points_received')
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='house_points', null=True)
    
    # Who submitted it?
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='points_submitted', null=True)
    
    # Who needs to approve this?
    # If Null, "Any Exec" can approve it (for Active requests)
    assigned_approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='points_to_approve')
    
    amount = models.IntegerField()
    description = models.CharField(max_length=200)
    date_for = models.DateField(default=timezone.now, help_text="When did this happen?")
    date_submitted = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # For the negotiation loop
    feedback = models.TextField(blank=True, help_text="Reason for rejection or counter-offer details.")
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} - {self.get_status_display()}"

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

class Reimbursement(models.Model):
    STATUS_CHOICES = [
        ('PENDING_SPENDING', 'Pending Approval to buy'),
        ('APPROVED_BUY', 'Approved to buy'),
        ('REJECTED_BUY', 'Rejected to buy'),
        ('PENDING_REIMBURSEMENT', 'Pending Reimbursement'),
        ('APPROVED_REIMBURSEMENT', 'Approved Reimbursement'),
        ('REJECTED_REIMBURSEMNET', 'Rejected Reimbursement')
    ]

    requestor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, null = True)
    description = models.TextField(blank=False, help_text = 'What will you be buying and for what reason?')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default = 0 ) 
    status = models.CharField(max_length = 30, choices = STATUS_CHOICES)
    receipt_image = models.ImageField(upload_to = 'receipts/', null = True)
    created_at = models.DateTimeField(auto_now_add=True)
    venmo_id = models.CharField(max_length = 250, null = True)

    def __str__(self):
        return f"{self.title} - {self.requester}"


class Task(models.Model):
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()
    completed = models.BooleanField(default=False)
    
    def __str__(self):
        return self.title
    
class Announcement(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='announcements')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    content = models.TextField()
    date_posted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.chapter.name}"