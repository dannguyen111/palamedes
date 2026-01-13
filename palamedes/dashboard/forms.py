from django import forms
from .models import HousePoint, Due, Reimbursement
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
            status='ACT'
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
        fields = ['user', 'amount', 'description', 'date_for']
        widgets = {
            'date_for': DateInput(),
        }

    def __init__(self, request_user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Base queryset: Everyone in my chapter
        queryset = CustomUser.objects.filter(chapter=request_user.chapter)

        # Check permissions
        user_pos = getattr(request_user, 'position', None)
        can_manage_all = user_pos and user_pos.can_manage_points

        if can_manage_all:
            self.fields['user'].queryset = queryset
            self.fields['user'].label = "Assign to Member" 
        else:
            self.fields['user'].queryset = queryset.filter(status='NM')
            self.fields['user'].label = "Assign to New Member"

class ReimbursementPreApprovalForm(forms.ModelForm):
    class Meta:
        model = Reimbursement
        fields = ['title', 'description'] 

        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class RecieptUploadForm(forms.ModelForm):
    class Meta:
        model = Reimbursement
        fields = ['receipt_image', 'total_amount', 'venmo_id']


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
        ('SELECTED', 'Selected Members (From Directory)'),
    ]
    target_group = forms.ChoiceField(choices=TARGET_CHOICES)

    # Hidden field to store the comma-separated list of IDs passed from the directory
    selected_user_ids = forms.CharField(widget=forms.HiddenInput(), required=False)

    # Optional fields for Pledge Class
    pledge_semester = forms.ChoiceField(choices=[('Fall', 'Fall'), ('Spring', 'Spring')], required=False)
    pledge_year = forms.IntegerField(required=False, help_text="Required if Pledge Class is selected")

class BulkPointForm(forms.Form):
    # Transaction Type Logic
    TRANSACTION_TYPES = [
        ('AWARD', 'Award Points (+)'),
        ('PENALTY', 'Deduct/Fine Points (-)'),
    ]
    type = forms.ChoiceField(choices=TRANSACTION_TYPES, widget=forms.RadioSelect, initial='AWARD')
    
    amount = forms.IntegerField(min_value=1)
    description = forms.CharField(max_length=255)
    date_for = forms.DateField(widget=DateInput())
    
    TARGET_CHOICES = [
        ('ALL', 'Everyone in Chapter'),
        ('ACTIVES', 'All Actives'),
        ('NMS', 'All New Members'),
        ('PLEDGE_CLASS', 'Specific Pledge Class'),
        ('SELECTED', 'Selected Members (From Directory)'),
    ]
    target_group = forms.ChoiceField(choices=TARGET_CHOICES)
    
    # Hidden field to store IDs
    selected_user_ids = forms.CharField(widget=forms.HiddenInput(), required=False)

    # Optional Filters
    pledge_semester = forms.ChoiceField(choices=[('Fall', 'Fall'), ('Spring', 'Spring')], required=False)
    pledge_year = forms.IntegerField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        t_type = cleaned_data.get('type')
        amount = cleaned_data.get('amount')

        # Automatically convert to negative if it's a penalty
        if amount:
            if t_type == 'PENALTY':
                cleaned_data['amount'] = -abs(amount)
            else:
                cleaned_data['amount'] = abs(amount)
        return cleaned_data

