from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import HousePoint, Due, Task, Announcement
from .forms import NMPointRequestForm, ActivePointRequestForm, DirectPointAssignmentForm

@login_required
def dashboard(request):
    user = request.user
    
    # Calculate Total Approved Points
    points_data = HousePoint.objects.filter(user=user, status='APPROVED').aggregate(Sum('amount'))
    total_points = points_data['amount__sum'] or 0 
    
    # Calculate Total Dues Owed
    dues_data = Due.objects.filter(assigned_to=user, is_paid=False).aggregate(Sum('amount'))
    dues_balance = dues_data['amount__sum'] or 0.00
    
    # Count Pending Tasks
    pending_tasks_count = Task.objects.filter(assigned_to=user, completed=False).count()
    
    # Get Chapter Announcements (Recent 5)
    if user.chapter:
        announcements = Announcement.objects.filter(chapter=user.chapter).order_by('-date_posted')[:5]
    else:
        announcements = []

    context = {
        'total_points': total_points,
        'dues_balance': dues_balance,
        'pending_tasks_count': pending_tasks_count,
        'announcements': announcements
    }
    
    return render(request, 'dashboard/dashboard.html', context)

@login_required
def submit_points(request):
    user = request.user
    
    # Determine which form to use based on Role
    if user.role == 'NM':
        FormClass = NMPointRequestForm
    else:
        FormClass = ActivePointRequestForm

    if request.method == 'POST':
        # We pass 'user' to the form init so it can filter the dropdowns
        form = FormClass(user, request.POST) if user.role == 'NM' else FormClass(request.POST)
        
        if form.is_valid():
            point_req = form.save(commit=False)
            point_req.user = user             # The points are for me
            point_req.submitted_by = user     # I submitted it
            point_req.chapter = user.chapter  # Link to chapter
            
            # If Active, no specific approver is set (implies Execs)
            # If NM, the form already handled setting 'assigned_approver'
            
            point_req.save()
            messages.success(request, 'Point request submitted successfully!')
            return redirect('dashboard')
    else:
        form = FormClass(user) if user.role == 'NM' else FormClass()

    return render(request, 'dashboard/submit_points.html', {'form': form})

# View for Actives to give points to NMs directly
@login_required
def assign_points(request):
    if request.user.role == 'NM':
        messages.error(request, "You do not have permission to do that.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = DirectPointAssignmentForm(request.user, request.POST)
        if form.is_valid():
            point = form.save(commit=False)
            point.submitted_by = request.user
            point.chapter = request.user.chapter
            point.status = 'APPROVED' # Auto-approve!
            point.save()
            messages.success(request, f"Points assigned to {point.user.username}!")
            return redirect('dashboard')
    else:
        form = DirectPointAssignmentForm(request.user)
    
    return render(request, 'dashboard/assign_points.html', {'form': form})