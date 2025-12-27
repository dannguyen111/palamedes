from django import forms
from .models import HousePoint
from users.models import CustomUser

class DateInput(forms.DateInput):
    input_type = 'date'

# Form for New Members (Must select an Active)
class NMPointRequestForm(forms.ModelForm):
    class Meta:
        model = HousePoint
        fields = ['amount', 'description', 'date_for', 'assigned_approver']
        widgets = {
            'date_for': DateInput(),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter the dropdown: Only show Actives from the SAME chapter
        self.fields['assigned_approver'].queryset = CustomUser.objects.filter(
            chapter=user.chapter,
            role__in=['ACT', 'EXEC', 'FIN', 'PRES', 'VPRES', 'NME']
        )
        self.fields['assigned_approver'].label = "Request Approval From"
        self.fields['assigned_approver'].required = True

# Form for Actives (Goes to Execs automatically)
class ActivePointRequestForm(forms.ModelForm):
    class Meta:
        model = HousePoint
        fields = ['amount', 'description', 'date_for']
        widgets = {
            'date_for': DateInput(),
        }

# Form for Actives to penalty/reward NMs directly
class DirectPointAssignmentForm(forms.ModelForm):
    class Meta:
        model = HousePoint
        fields = ['user', 'amount', 'description', 'date_for'] # Select the NM user
        widgets = {
            'date_for': DateInput(),
        }

    def __init__(self, request_user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show New Members from the same chapter
        self.fields['user'].queryset = CustomUser.objects.filter(
            chapter=request_user.chapter,
            role='NM'
        )
        self.fields['user'].label = "Assign to New Member"