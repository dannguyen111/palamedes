from django import forms
from .models import HousePoint, Due
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

class SingleDueForm(forms.ModelForm):
    # We add a "Type" field to help the UI, though it saves to 'amount'
    TRANSACTION_TYPES = [
        ('CHARGE', 'Charge (Bill)'),
        ('AID', 'Scholarship/Aid (Credit)'),
    ]
    type = forms.ChoiceField(choices=TRANSACTION_TYPES, widget=forms.RadioSelect, initial='CHARGE')

    class Meta:
        model = Due
        fields = ['title', 'amount', 'due_date', 'assigned_to']
        widgets = {
            'due_date': DateInput(),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show members of my chapter
        self.fields['assigned_to'].queryset = CustomUser.objects.filter(chapter=user.chapter)
        self.fields['assigned_to'].required = True

    def clean(self):
        cleaned_data = super().clean()
        t_type = cleaned_data.get('type')
        amount = cleaned_data.get('amount')

        if amount:
            # If it's AID, make sure amount is negative
            if t_type == 'AID':
                cleaned_data['amount'] = -abs(amount)
            # If it's CHARGE, make sure amount is positive
            else:
                cleaned_data['amount'] = abs(amount)
        return cleaned_data

# Bulk Charge Form
class BulkDueForm(forms.Form):
    title = forms.CharField(max_length=100)
    amount = forms.DecimalField(decimal_places=2)
    due_date = forms.DateField(widget=DateInput())
    
    TARGET_CHOICES = [
        ('ALL', 'Everyone in Chapter'),
        ('ACTIVES', 'All Actives'),
        ('NMS', 'All New Members'),
        ('PLEDGE_CLASS', 'Specific Pledge Class'),
    ]
    target_group = forms.ChoiceField(choices=TARGET_CHOICES)

    # Optional fields for Pledge Class
    pledge_semester = forms.ChoiceField(choices=[('Fall', 'Fall'), ('Spring', 'Spring')], required=False)
    pledge_year = forms.IntegerField(required=False, help_text="Required if Pledge Class is selected")