from django import forms
from .models import ChapterRequest

class ChapterRequestForm(forms.ModelForm):
    class Meta:
        model = ChapterRequest
        fields = ['fraternity_name', 'university', 'president_email']