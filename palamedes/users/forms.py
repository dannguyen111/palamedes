from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Chapter
from homepage.models import ChapterRequest # To check the approved email

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True) # Make email mandatory
    invite_code = forms.CharField(max_length=10, required=True, help_text="Enter the code sent to your President.")

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'major', 'invite_code')

    def clean_invite_code(self):
        code = self.cleaned_data.get('invite_code')
        try:
            chapter = Chapter.objects.get(invite_code=code)
        except Chapter.DoesNotExist:
            raise forms.ValidationError("Invalid Invite Code.")
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        code = self.cleaned_data.get('invite_code')
        chapter = Chapter.objects.get(invite_code=code)
        
        # LINK USER TO CHAPTER
        user.chapter = chapter

        # --- THE LOGIC YOU ASKED FOR ---
        # Check if this user's email matches the APPROVED request email
        try:
            approved_req = ChapterRequest.objects.get(
                fraternity_name=chapter.name,
                university=chapter.university,
                president_email=user.email, # The matching magic
                is_approved=True
            )
            # Match found! This is the President.
            user.role = 'PRES'
        except ChapterRequest.DoesNotExist:
            # No match found. This is just a regular member.
            user.role = 'NM' # Default to New Member

        if commit:
            user.save()
            # Must save many-to-many data (groups) if using UserCreationForm
            self.save_m2m() 
            
        return user