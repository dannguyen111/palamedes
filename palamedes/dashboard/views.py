from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from .models import HousePoint, Due, Task, Announcement
from .forms import NMPointRequestForm, ActivePointRequestForm, DirectPointAssignmentForm, SingleDueForm, BulkDueForm
from users.models import CustomUser

@login_required
def dashboard(request):
    user = request.user
    
    # Calculate Total Approved Points
    points_data = HousePoint.objects.filter(user=user, status='APPROVED').aggregate(Sum('amount'))
    total_points = points_data['amount__sum'] or 0 

    pending_data = HousePoint.objects.filter(user=user, status='PENDING').aggregate(Sum('amount'))
    pending_points = pending_data['amount__sum'] or 0
    
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

    # My Action Items
    my_action_items = HousePoint.objects.filter(
        chapter=chapter
    ).filter(
        Q(assigned_approver=user, status='PENDING') | 
        Q(submitted_by=user, status='COUNTERED')
    ).order_by('-date_submitted')

    # Exec Queue
    exec_queue = []
    if user.role in ['PRES', 'VPRES']:
        exec_queue = HousePoint.objects.filter(
            chapter=chapter,
            assigned_approver__isnull=True,
            status='PENDING'
        ).exclude(submitted_by=user)

    # HISTORY: All requests involving me (Sender, Recipient, or Approver)
    # Filter: "Show every active, pending, rejected request... that involves the active user"
    history_qs = HousePoint.objects.filter(
        chapter=chapter
    ).filter(
        Q(user=user) |                 # I am the recipient
        Q(submitted_by=user) |         # I submitted it
        Q(assigned_approver=user)      # I approved/rejected/am assigned to it
    ).order_by('-updated_at')          # Sort by last action date

    context = {
        'my_action_items': my_action_items,
        'exec_queue': exec_queue,
        'history': history_qs
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
            point.assigned_approver = request.user 
            point.save()
            messages.success(request, f"Request approved for {point.amount} points.")

        elif action == 'reject':
            point.status = 'REJECTED'
            point.feedback = feedback
            point.assigned_approver = request.user
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

@login_required
def chapter_ledger(request):
    user = request.user
    chapter = user.chapter

    # Leaderboards (Group by User, Sum Amount)
    # We only count APPROVED points
    leaderboard_data = CustomUser.objects.filter(chapter=chapter).annotate(
        total_points=Coalesce(
            Sum('points_received__amount', filter=Q(points_received__status='APPROVED')),
            0
        )
    ).order_by('-total_points')

    # Separate into two lists in Python
    active_leaderboard = [u for u in leaderboard_data if u.role != 'NM']
    nm_leaderboard = [u for u in leaderboard_data if u.role == 'NM']

    # Mother Log (Every request ever)
    # Only Actives can see the full log
    full_log = []
    if user.role != 'NM':
        full_log = HousePoint.objects.filter(chapter=chapter).order_by('-date_submitted')
    # NM can see NM logs
    else:
        full_log = HousePoint.objects.filter(chapter=chapter, user__role='NM').order_by('-date_submitted')

    context = {
        'active_leaderboard': active_leaderboard,
        'nm_leaderboard': nm_leaderboard,
        'full_log': full_log
    }
    return render(request, 'dashboard/ledger.html', context)

@login_required
def points_hub(request):
    # Potentially pass 'pending_count' if we want to show badges on the menu
    return render(request, 'dashboard/points_hub.html')

@login_required
def dues_dashboard(request):
    user = request.user
    
    # Security: Only Treasurer/Exec can see the management tools
    is_treasurer = user.role in ['FIN']
    
    # My Personal Bill
    my_dues = Due.objects.filter(assigned_to=user, is_paid=False).order_by('due_date')
    my_history = Due.objects.filter(assigned_to=user, is_paid=True).order_by('-due_date')

    total_due = my_dues.aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'my_dues': my_dues,
        'my_history': my_history,
        'is_treasurer': is_treasurer,
        'total_due': total_due
    }
    return render(request, 'dashboard/dues_dashboard.html', context)

@login_required
def manage_dues_creation(request):
    # Security Check
    if request.user.role not in ['FIN']:
        messages.error(request, "Access Denied.")
        return redirect('dues_dashboard')

    single_form = SingleDueForm(request.user)
    bulk_form = BulkDueForm()

    if request.method == 'POST':
        # Check which form was submitted
        if 'submit_single' in request.POST:
            single_form = SingleDueForm(request.user, request.POST)
            if single_form.is_valid():
                due = single_form.save(commit=False)
                # Amount sign is already handled in form.clean()
                due.save()
                messages.success(request, f"Transaction created for {due.assigned_to.username}")
                return redirect('dues_dashboard')
        
        elif 'submit_bulk' in request.POST:
            bulk_form = BulkDueForm(request.POST)
            if bulk_form.is_valid():
                data = bulk_form.cleaned_data
                target = data['target_group']
                users_to_charge = []

                # Logic to find users
                base_qs = CustomUser.objects.filter(chapter=request.user.chapter)
                
                if target == 'ALL':
                    users_to_charge = base_qs
                elif target == 'ACTIVES':
                    users_to_charge = base_qs.exclude(role='NM')
                elif target == 'NMS':
                    users_to_charge = base_qs.filter(role='NM')
                elif target == 'PLEDGE_CLASS':
                    sem = data.get('pledge_semester')
                    yr = data.get('pledge_year')
                    if sem and yr:
                        users_to_charge = base_qs.filter(pledge_semester=sem, pledge_year=yr)
                    else:
                        messages.error(request, "Please specify Semester and Year.")
                        return redirect('manage_dues_creation')

                # Create the records
                count = 0
                for u in users_to_charge:
                    Due.objects.create(
                        title=data['title'],
                        amount=data['amount'],
                        due_date=data['due_date'],
                        assigned_to=u
                    )
                    count += 1
                
                messages.success(request, f"Bulk charge assigned to {count} members.")
                return redirect('dues_dashboard')

    context = {
        'single_form': single_form,
        'bulk_form': bulk_form
    }
    return render(request, 'dashboard/manage_dues.html', context)

@login_required
def pay_due(request, pk):
    due = get_object_or_404(Due, pk=pk)
    
    # Ideally, this integrates with Stripe/Venmo
    # For now, we just mark it as paid (Treasurer only) 
    # OR create a "Mark Paid" request logic later.
    # Let's assume ONLY Treasurer can mark things paid for now.
    
    if request.user.role in ['FIN']:
        due.is_paid = True
        due.save()
        messages.success(request, "Marked as Paid.")
    else:
        messages.error(request, "Only the Treasurer can verify payments.")
        
    return redirect('dues_dashboard')