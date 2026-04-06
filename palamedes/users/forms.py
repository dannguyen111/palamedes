from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if any user already exists with this exact email
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def clean_invite_code(self):
        code = self.cleaned_data.get('invite_code')
        # Check if the code matches EITHER an active or nm code
        if not Chapter.objects.filter(Q(nm_invite_code=code) | Q(active_invite_code=code)).exists():
            raise forms.ValidationError("Invalid Invite Code.")
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        code = self.cleaned_data.get('invite_code')
        chapter = Chapter.objects.get(Q(nm_invite_code=code) | Q(active_invite_code=code))
        
        # LINK USER TO CHAPTER
        user.chapter = chapter

        # Determine default status based on which code they used
        if code == chapter.active_invite_code:
            assigned_status = 'ACT'
        else:
            assigned_status = 'NM'

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
            user.status = assigned_status

        if commit:
            user.save()
            # Must save many-to-many data (groups) if using UserCreationForm
            self.save_m2m() 
            
        return user
    
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'image', 'major', 'phone_number', 'hometown', 'bio']