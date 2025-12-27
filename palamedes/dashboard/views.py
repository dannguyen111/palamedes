from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
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

@login_required
def inbox(request):
    user = request.user
    chapter = user.chapter

    # Direct Requests: Assigned specifically to YOU (e.g. NM asking an Active)
    # OR Requests YOU submitted that were Countered (you need to accept/reject the counter)
    my_action_items = HousePoint.objects.filter(
        chapter=chapter
    ).filter(
        Q(assigned_approver=user, status='PENDING') | 
        Q(submitted_by=user, status='COUNTERED')
    ).order_by('-date_submitted')

    # Exec Queue: Requests from Actives (assigned_approver is None)
    exec_queue = []
    if user.role in ['PRES', 'VPRES']:
        exec_queue = HousePoint.objects.filter(
            chapter=chapter,
            assigned_approver__isnull=True, # No specific person assigned
            status='PENDING'
        ).exclude(submitted_by=user) # Don't show my own requests here

    # History/Watchlist: Recent Active Requests (Read-Only for Actives)
    active_history = []
    if user.role != 'NM':
        active_history = HousePoint.objects.filter(
            chapter=chapter,
            submitted_by__role__in=['ACT', 'EXEC', 'PRES', 'VPRES', 'FIN', 'NME']
        ).exclude(status='PENDING').order_by('-date_submitted')[:10]

    context = {
        'my_action_items': my_action_items,
        'exec_queue': exec_queue,
        'active_history': active_history
    }
    return render(request, 'dashboard/inbox.html', context)

@login_required
def manage_point_request(request, pk):
    point = get_object_or_404(HousePoint, pk=pk)
    
    # Security: Ensure user is allowed to modify this
    is_approver = point.assigned_approver == request.user
    is_exec = request.user.role in ['EXEC', 'PRES', 'VPRES', 'FIN', 'NME'] and point.assigned_approver is None
    is_owner_countering = point.submitted_by == request.user and point.status == 'COUNTERED'

    if not (is_approver or is_exec or is_owner_countering):
        messages.error(request, "You do not have permission to manage this request.")
        return redirect('inbox')

    if request.method == 'POST':
        action = request.POST.get('action')
        feedback = request.POST.get('feedback', '')

        if action == 'approve':
            point.status = 'APPROVED'
            point.feedback = feedback
            point.save()
            messages.success(request, f"Request approved for {point.amount} points.")

        elif action == 'reject':
            point.status = 'REJECTED'
            point.feedback = feedback
            point.save()
            messages.warning(request, "Request rejected.")

        elif action == 'counter':
            try:
                new_amount = int(request.POST.get('new_amount'))
                point.amount = new_amount
                point.feedback = feedback
                
                # SWAP LOGIC: If I am the Approver, send it back to Submitter
                if point.status == 'PENDING':
                    point.status = 'COUNTERED'
                    # Note: We keep assigned_approver as the Active, 
                    # but the Inbox view knows to show it to the Submitter if status is COUNTERED.
                
                # If I am the Submitter (accepting a counter but changing value), send back to Approver
                elif point.status == 'COUNTERED':
                    point.status = 'PENDING'
                
                point.save()
                messages.info(request, f"Counter-offer sent: {new_amount} points.")
            except ValueError:
                messages.error(request, "Invalid amount for counter-offer.")

    return redirect('inbox')