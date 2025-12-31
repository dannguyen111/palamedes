from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Chapter, Position
from homepage.models import ChapterRequest # To check the approved email

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True) # Make email mandatory
    first_name = forms.CharField(required=True, max_length=30)
    last_name = forms.CharField(required=True, max_length=150)
    invite_code = forms.CharField(max_length=10, required=True, help_text="Enter the code sent to your President.")

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name')

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

        # Check if this user's email matches the APPROVED request email
        try:
            approved_req = ChapterRequest.objects.get(
                fraternity_name=chapter.name,
                university=chapter.university,
                president_email=user.email,
                is_approved=True
            )
            user.position = Position.objects.get(chapter=chapter, title="President")
            user.status = 'ACT'
        except ChapterRequest.DoesNotExist:
            user.position = Position.objects.get(chapter=chapter, title="No Position")
            user.status = 'NM'

        if commit:
            user.save()
            # Must save many-to-many data (groups) if using UserCreationForm
            self.save_m2m() 
            
        return user
    
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'image', 'major', 'phone_number', 'hometown', 'bio']