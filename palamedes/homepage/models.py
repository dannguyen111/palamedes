from django.db import models

class ChapterRequest(models.Model):
    fraternity_name = models.CharField(max_length=100)
    university = models.CharField(max_length=100)
    president_email = models.EmailField()
    date_requested = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.fraternity_name} at {self.university}"