from django.shortcuts import render, redirect, get_object_or_404
import stripe
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from .models import HousePoint, Due, Task, Announcement, Reimbursement
from .forms import NMPointRequestForm, ActivePointRequestForm, DirectPointAssignmentForm, SingleDueForm, BulkDueForm, BulkPointForm, ReimbursementPreApprovalForm, RecieptUploadForm 
from users.models import CustomUser
from django.http import JsonResponse

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
    
    # Determine which form to use based on Status
    if user.status == 'NM':
        FormClass = NMPointRequestForm
    else:
        FormClass = ActivePointRequestForm

    if request.method == 'POST':
        # We pass 'user' to the form init so it can filter the dropdowns
        form = FormClass(user, request.POST) if user.status == 'NM' else FormClass(request.POST)
        
        if form.is_valid():
            point_req = form.save(commit=False)
            point_req.user = user             # The points are for me
            point_req.submitted_by = user     # I submitted it
            point_req.chapter = user.chapter  # Link to chapter
            
            # If Active, no specific approver is set (whoever has the permission will handle)
            # If NM, the form already handled setting 'assigned_approver'
            
            point_req.save()
            messages.success(request, 'Point request submitted successfully!')
            return redirect('dashboard')
    else:
        form = FormClass(user) if user.status == 'NM' else FormClass()

    return render(request, 'dashboard/submit_points.html', {'form': form})

# View for Actives to give points to NMs directly
@login_required
def assign_points(request):
    has_permission = (request.user.status != 'NM') or (request.user.position and request.user.position.can_manage_points)

    if not has_permission:
        messages.error(request, "You do not have permission to do that.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = DirectPointAssignmentForm(request.user, request.POST)
        if form.is_valid():
            point = form.save(commit=False)
            point.submitted_by = request.user
            point.assigned_approver = request.user
            point.chapter = request.user.chapter
            point.status = 'APPROVED' # Auto-approve!
            point.save()
            messages.success(request, f"Points assigned to {point.user.username}!")
            return redirect('dashboard')
    else:
        form = DirectPointAssignmentForm(request.user)
    
    return render(request, 'dashboard/assign_points.html', {'form': form})

# @login_required
# def inbox(request):
#     user = request.user
#     chapter = user.chapter

#     # My Action Items
#     my_action_items = HousePoint.objects.filter(
#         chapter=chapter
#     ).filter(
#         Q(assigned_approver=user, status='PENDING') | 
#         Q(submitted_by=user, status='COUNTERED')
#     ).order_by('-date_submitted')

#     # Exec Queue
#     exec_queue = []
#     if user.position.can_manage_points:
#         exec_queue = HousePoint.objects.filter(
#             chapter=chapter,
#             assigned_approver__isnull=True,
#             status='PENDING'
#         ).exclude(submitted_by=user)

#     # HISTORY: All requests involving me (Sender, Recipient, or Approver)
#     # Filter: "Show every active, pending, rejected request... that involves the active user"
#     history_qs = HousePoint.objects.filter(
#         chapter=chapter
#     ).filter(
#         Q(user=user) |                 # I am the recipient
#         Q(submitted_by=user) |         # I submitted it
#         Q(assigned_approver=user)      # I approved/rejected/am assigned to it
#     ).order_by('-updated_at')          # Sort by last action date

#     context = {
#         'my_action_items': my_action_items,
#         'exec_queue': exec_queue,
#         'history': history_qs
#     }
#     return render(request, 'dashboard/inbox.html', context)

@login_required
def manage_point_request(request, pk):
    point = get_object_or_404(HousePoint, pk=pk)
    
    # Security: Ensure user is allowed to modify this
    is_approver = point.assigned_approver == request.user
    is_top2 = request.user.position.can_manage_points and point.assigned_approver is None
    is_owner_countering = point.submitted_by == request.user and point.status == 'COUNTERED'

    if not (is_approver or is_top2 or is_owner_countering):
        messages.error(request, "You do not have permission to manage this request.")
        return redirect('points_hub')

    if request.method == 'POST':
        action = request.POST.get('action')
        feedback = request.POST.get('feedback', '')

        if action == 'approve':
            point.status = 'APPROVED'
            point.feedback = feedback
            if point.submitted_by == request.user:
                pass
            else:
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
                    point.assigned_approver = request.user
                
                # If I am the Submitter (accepting a counter but changing value), send back to Approver
                elif point.status == 'COUNTERED':
                    point.status = 'PENDING'
                
                point.save()
                messages.info(request, f"Counter-offer sent: {new_amount} points.")
            except ValueError:
                messages.error(request, "Invalid amount for counter-offer.")

    return redirect('points_hub')

# @login_required
# def chapter_ledger(request):
#     user = request.user
#     chapter = user.chapter

#     # Leaderboards (Group by User, Sum Amount)
#     # We only count APPROVED points
#     leaderboard_data = CustomUser.objects.filter(chapter=chapter).annotate(
#         total_points=Coalesce(
#             Sum('points_received__amount', filter=Q(points_received__status='APPROVED')),
#             0
#         )
#     ).order_by('-total_points')

#     # Separate into two lists in Python
#     active_leaderboard = [u for u in leaderboard_data if u.status == 'ACT']
#     nm_leaderboard = [u for u in leaderboard_data if u.status == 'NM']

#     # Mother Log (Every request ever)
#     # Only Actives can see the full log
#     full_log = []
#     if user.status != 'NM':
#         full_log = HousePoint.objects.filter(chapter=chapter).order_by('-date_submitted')
#     # NM can see NM logs
#     else:
#         full_log = HousePoint.objects.filter(chapter=chapter, user__status='NM').order_by('-date_submitted')
#     context = {
#         'active_leaderboard': active_leaderboard,
#         'nm_leaderboard': nm_leaderboard,
#         'full_log': full_log
#     }
#     return render(request, 'dashboard/ledger.html', context)

@login_required
def points_hub(request):
    user = request.user
    chapter = user.chapter

    # Summary Stats
    total_points = user.points_received.filter(status='APPROVED').aggregate(Sum('amount'))['amount__sum'] or 0

    # Inbox Logic
    my_action_items = HousePoint.objects.filter(
        chapter=chapter
    ).filter(
        Q(assigned_approver=user, status='PENDING') | 
        Q(submitted_by=user, status='COUNTERED')
    ).order_by('-date_submitted')

    exec_queue = []
    if user.position and user.position.can_manage_points:
        exec_queue = HousePoint.objects.filter(
            chapter=chapter,
            assigned_approver__isnull=True,
            status='PENDING'
        ).exclude(submitted_by=user)

    # Leaderboards
    leaderboard_data = CustomUser.objects.filter(chapter=chapter).annotate(
        total_points_val=Coalesce(
            Sum('points_received__amount', filter=Q(points_received__status='APPROVED')),
            0
        )
    ).order_by('-total_points_val')

    active_leaderboard = [u for u in leaderboard_data if u.status != 'NM']
    nm_leaderboard = [u for u in leaderboard_data if u.status == 'NM']

    # MOTHER LOGS (Split & Filtered)
    
    # Base Query
    base_logs = HousePoint.objects.filter(chapter=chapter)
    
    # Dropdown Data
    all_members = CustomUser.objects.filter(chapter=chapter).order_by('first_name')
    approvers_list = all_members.exclude(status='NM') 

    # A. Apply Filters to Base Query
    recipient_id = request.GET.get('recipient', '')
    if recipient_id and recipient_id.isdigit():
        base_logs = base_logs.filter(user_id=recipient_id)
        
    approver_id = request.GET.get('approver', '')
    if approver_id and approver_id.isdigit():
        base_logs = base_logs.filter(assigned_approver_id=approver_id)

    # B. Apply Sorting
    sort_param = request.GET.get('sort', '-date_submitted') 
    if sort_param in ['amount', '-amount', 'date_submitted', '-date_submitted']:
        base_logs = base_logs.order_by(sort_param)
    else:
        base_logs = base_logs.order_by('-date_submitted')

    # C. Split into Two Separate Lists
    nm_logs = base_logs.filter(user__status='NM')[:50]
    active_logs = base_logs.exclude(user__status='NM')[:50]

    context = {
        'total_points': total_points,
        'my_action_items': my_action_items,
        'exec_queue': exec_queue,
        'active_leaderboard': active_leaderboard,
        'nm_leaderboard': nm_leaderboard,
        
        'nm_logs': nm_logs,
        'active_logs': active_logs,
        
        'chapter_members': all_members,
        'approvers_list': approvers_list,
        'current_recipient': int(recipient_id) if recipient_id.isdigit() else None,
        'current_approver': int(approver_id) if approver_id.isdigit() else None,
        'current_sort': sort_param
    }
    
    return render(request, 'dashboard/points_hub.html', context)

@login_required
def dues_dashboard(request):
    user = request.user
    
    # Security: Only People with Managing dues permission can see Treasurer View
    is_treasurer = user.position.can_manage_finance
    
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

def _helper_single_transaction(request, single_form):
    if single_form.is_valid():
        saved_due = single_form.save()
        messages.success(request, f'Charge was assigned to {saved_due.assigned_to} successfully.')
        return redirect('dues_dashboard')
    return None

def _helper_bulk_transaction(request, bulk_form):
    if bulk_form.is_valid():
        data = bulk_form.cleaned_data
        target_group = data['target_group'] 
        users_to_charge = []
        members = CustomUser.objects.filter(chapter = request.user.chapter)

        if target_group == 'ALL':
            users_to_charge = members
        elif target_group == 'ACTIVES':
            users_to_charge = members.exclude(status = 'NM')
        elif target_group == 'NMS':
            users_to_charge = members.filter(status = 'NM')
        elif target_group == 'PLEDGE_CLASS':
            sem, year = members.get('pledge_semester'), members.get('pledge_year')

            if sem and year:
                users_to_charge = members.filer(pledge_semester = sem, pledge_year = year)
        elif target_group == 'SELECTED':
            id_string = data.get('selected_user_ids', '')
            if id_string:
                id_list = id_string.split(',')
                users_to_charge = members.filter(id__in=id_list)

        count = 0 
        for u in users_to_charge:
            Due.objects.create(
                title=data['title'],
                amount=data['amount'],
                due_date=data['due_date'],
                assigned_to=u
            )
            count += 1

        messages.success(request, f'Bulk charge assigned to {count} members.')
        return redirect('dues_dashboard')
    return None

@login_required
def manage_dues_creation(request):
    # Security Check
    if not (request.user.position and request.user.position.can_manage_finance):
        messages.error(request, "Access Denied.")
        return redirect('dues_dashboard')

    single_form = SingleDueForm(request.user)
    bulk_form = BulkDueForm()
    # Default tab
    active_tab = 'single'
    if request.method == 'POST':
        single_form = SingleDueForm(request.user, request.POST)
        if 'submit_single' in request.POST:
            result = _helper_single_transaction(request, single_form)

            if result:
                return result
    
    # Handle "Pre-fill" from Directory Selection
    initial_data = {}
    if request.method == 'POST' and 'directory_selection' in request.POST:
        active_tab = 'bulk'
        # Get list of IDs from the directory checkboxes
        selected_ids = request.POST.getlist('selected_members')
        if selected_ids:
            initial_data = {
                'target_group': 'SELECTED',
                'selected_user_ids': ','.join(selected_ids)
            }
            messages.info(request, f"Selected {len(selected_ids)} members for billing.")
    
    bulk_form = BulkDueForm(initial=initial_data)

    # Handle Form Submission (Creating the Dues)
    if request.method == 'POST' and 'submit_bulk' in request.POST:
        bulk_form = BulkDueForm(request.POST)
        active_tab = 'bulk'
        result = _helper_bulk_transaction(request, bulk_form)

        if result:
            return result

    context = {
        'single_form': single_form,
        'bulk_form': bulk_form,
        'active_tab': active_tab
    }
    return render(request, 'dashboard/manage_dues.html', context)

stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def payment_page(request, pk):
    due = get_object_or_404(Due, pk = pk, assigned_to = request.user)

    context = {
        'due' : due, 
        'stripe_api_key' : stripe.api_key
    }

    return render(request, 'dashboard/payment_page.html', context)

@login_required
def create_bulk_checkout_session(request):
    if request.POST:
        ids = request.POST.getlist('due_ids')

        dues = Due.objects.filter(pk__in = ids, assigned_to = request.user)

        stripe_line_items = []
        valid_due_ids = []

        for due in dues:
            temp = {
                        'price_data' : {
                            'currency' : 'usd',
                            'product_data' : {
                                'name' : due.title
                            },
                            'unit_amount_decimal' : due.amount * 100
                        }, 
                        'quantity' : 1,
                    }

            stripe_line_items.append(temp)
            valid_due_ids.append(str(due.id))

        try:
            bulk_checkout = stripe.checkout.Session.create(
                line_items = stripe_line_items,
                mode = 'payment',
                metadata = {
                    'user_id' : request.user.id,
                    'payment_type': 'bulk_payment',
                    'due_ids_str': ",".join(valid_due_ids)
                },
                success_url=request.build_absolute_uri(reverse('payment_success')) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(reverse('dashboard')),
            )
            return redirect(bulk_checkout.url, code = 303)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return redirect('dashboard')



@login_required
def process_payment(request, pk):
    if request.POST:
        due = get_object_or_404(Due, pk = pk, assigned_to = request.user)

        amount_str = request.POST.get('due_amount') 
        amount = int(float(amount_str) * 100)
        title = due.title

        try:
            checkout_session = stripe.checkout.Session.create(
                line_items=[
                    {
                        'price_data' : {
                            'currency' : 'usd',
                            'product_data' : {
                                'name' : title
                            },
                            'unit_amount_decimal' : amount
                        }, 
                        'quantity' : 1,
                    }
                ],

                mode='payment',
                metadata={
                    'due_id': due.pk,      
                    'user_id': request.user.id,
                    'payment_type': 'single'
                },
                success_url=request.build_absolute_uri(reverse('payment_success')) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(reverse('payment_page', args=[pk])),

            )

            return redirect(checkout_session.url, code = 303)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return redirect('dashboard')

@login_required
def payment_success(request):
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, "Missing payment session information. Please try again.")
        return redirect('dashboard')

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        messages.error(request, "There was a problem verifying your payment. Please contact support if this persists.")
        return redirect('dashboard')

    processed_sessions = request.session.get('processed_sessions', [])

    if session.metadata['payment_type'] == 'bulk_payment':
        due_ids_str = session.metadata.get('due_ids_str')
        if due_ids_str:
            due_ids = due_ids_str.split(',')

            dues_paid = Due.objects.filter(pk__in = due_ids, assigned_to = request.user) 

            for due in dues_paid:   
                due.is_paid = True
                due.amount = 0
                due.save()
            return render(request, 'dashboard/successful_payment.html', {'dues': dues_paid})

    amount_paid = Decimal(session.amount_total) / Decimal(100)
    due_id = session.metadata['due_id']

    due = get_object_or_404(Due, pk = due_id)

    context = {
    'due':due,
    'amount_paid': amount_paid
    }


    if session_id in processed_sessions:
        return render(request, 'dashboard/successful_payment.html', context) 

    processed_sessions.append(session_id)
    request.session['processed_sessions'] = processed_sessions
    request.session.modified = True

    due.amount -= amount_paid

    if due.amount <= 0:
        due.is_paid = True
    due.save()


    return render(request, 'dashboard/successful_payment.html', context)

@login_required
def make_payment_treasurer(request, pk):
    if request.user.position.can_manage_finance:
        due = get_object_or_404(Due, pk=pk)
        context = {
            'due' : due
        }

        return render(request, 'dashboard/paid_treasurer.html', context)

@login_required
def mark_paid(request, pk):
    due = get_object_or_404(Due, pk=pk)
    
    if request.user.position.can_manage_finance:
        amount = request.POST.get('amount')
        if not amount:
            payment_amount = due.amount
        else:
            try:
                payment_amount = int(amount)
            except (TypeError, ValueError):
                messages.error(request, "Invalid payment amount. Please enter a whole number.")
                return redirect('brothers_due', due.assigned_to.pk)
            if payment_amount < 0:
                messages.error(request, "Invalid payment amount. Amount cannot be negative.")
                return redirect('brothers_due', due.assigned_to.pk)

        due.amount -= payment_amount

        if due.amount <= 0:
            due.is_paid = True
        due.save()

        if due.amount <= 0:
            messages.success(request, "Marked as Paid.")
        else:
            messages.success(request, f'The due has been updated. {due.assigned_to.first_name }  {due.assigned_to.last_name } still has {due.amount} left to pay.')
    else:
        messages.error(request, "Only people with permission can verify payments.")
        
    return redirect('brothers_due', due.assigned_to.pk)

@login_required
def directory(request):
    user = request.user
    chapter = request.user.chapter
    members = CustomUser.objects.filter(chapter=chapter).order_by('status', 'last_name', 'first_name')

    query = request.GET.get('q')
    if query:
        members = members.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) |
            Q(major__icontains=query) |
            Q(hometown__icontains=query)
        )

    status_filter = request.GET.get('status')
    if status_filter:
        members = members.filter(status=status_filter)
    
    context = {
        'members': members,
        'search_query': query or ""
    }
    return render(request, 'dashboard/directory.html', context)

@login_required
def unpaid_directory(request):
    if request.user.position.can_manage_finance:
        user = request.user
        chapter = request.user.chapter 
        members = CustomUser.objects.filter(dues__is_paid = False, chapter = chapter).distinct() \
            .annotate(total_dues=Sum('dues__amount')
        )

        member_filter = request.GET.get('filter')
        if member_filter:
            members = members.filter(
                Q(first_name__icontains = member_filter) |
                Q(last_name__icontains = member_filter) |
                Q(major__icontains = member_filter) |
                Q(hometown__icontains = member_filter)
        )

        status_filter = request.GET.get('status')
        if status_filter:
            members = members.filter(status=status_filter)

        context = {
            'members' : members, 
            'search_query' : member_filter or ""
        }

        return render(request, 'dashboard/unpaid_directory.html', context)

def dues_member(request, pk):
    if request.user.position.can_manage_finance:
        brother = get_object_or_404(CustomUser, pk=pk)
        dues = Due.objects.filter(assigned_to=brother).order_by('is_paid', 'due_date')

        context = {
            'brother' : brother, 
            'dues' : dues
        }

        return render(request, 'dashboard/member_dues_details.html', context)



@login_required
def brother_profile(request, pk):
    # Fetch the specific brother or show 404
    brother = get_object_or_404(CustomUser, pk=pk)
    
    # Only allow viewing members of the SAME chapter
    if brother.chapter != request.user.chapter:
        messages.error(request, "You cannot view profiles from other chapters.")
        return redirect('dashboard')

    context = {
        'brother': brother
    }
    return render(request, 'dashboard/brother_profile.html', context)

@login_required
def manage_points_creation(request):
    # Check Permission
    if not (request.user.position and request.user.position.can_manage_points):
        messages.error(request, "Access Denied.")
        return redirect('dashboard')

    # Handle "Handoff" from Directory
    initial_data = {}
    if request.method == 'POST' and 'directory_selection' in request.POST:
        selected_ids = request.POST.getlist('selected_members')
        if selected_ids:
            initial_data = {
                'target_group': 'SELECTED',
                'selected_user_ids': ','.join(selected_ids)
            }
            messages.info(request, f"Selected {len(selected_ids)} members for point assignment.")
    
    form = BulkPointForm(initial=initial_data)

    # Handle Submission
    if request.method == 'POST' and 'submit_bulk_points' in request.POST:
        form = BulkPointForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # Find Users (Reusing logic from Dues)
            target = data['target_group']
            base_qs = CustomUser.objects.filter(chapter=request.user.chapter)
            users_to_update = []

            if target == 'ALL': users_to_update = base_qs
            elif target == 'ACTIVES': users_to_update = base_qs.exclude(status='NM')
            elif target == 'NMS': users_to_update = base_qs.filter(status='NM')
            elif target == 'PLEDGE_CLASS':
                if data['pledge_semester'] and data['pledge_year']:
                    users_to_update = base_qs.filter(pledge_semester=data['pledge_semester'], pledge_year=data['pledge_year'])
            elif target == 'SELECTED':
                id_string = data.get('selected_user_ids', '')
                if id_string:
                    users_to_update = base_qs.filter(id__in=id_string.split(','))

            # Execute
            count = 0
            for u in users_to_update:
                HousePoint.objects.create(
                    user=u,
                    submitted_by=request.user,
                    chapter=request.user.chapter,
                    amount=data['amount'],
                    description=data['description'],
                    date_for=data['date_for'],
                    status='APPROVED', # Admin actions are auto-approved
                    assigned_approver=request.user 
                )
                count += 1
            
            messages.success(request, f"Successfully processed points for {count} members.")
            return redirect('dashboard')

    return render(request, 'dashboard/manage_points.html', {'form': form})

@login_required
def reimbursement_list(request):
    requests = Reimbursement.objects.filter(requestor = request.user)

    context = {
        'requests' : requests
    }

    return render(request, 'dashboard/reimbursement_list.html', context)

@login_required
def create_pre_buy(request):
    if request.method == 'POST':
        buy_form = ReimbursementPreApprovalForm(request.POST) 

        if buy_form.is_valid():
            req = buy_form.save(commit = False)
            req.requestor = request.user
            req.status = 'PENDING_SPENDING'
            req.save()
            messages.success(request, f'Your request to buy the following items has been successfully submitted. Please wait for the approval.')
            return redirect('reimbursement_list')
    else:
        buy_form = ReimbursementPreApprovalForm()

    return render(request, 'dashboard/reimbursement_form.html', {'form': buy_form, 'title': 'New Request'})

@login_required
def create_upload_receipt(request, pk):
    req = get_object_or_404(Reimbursement, pk=pk, requestor = request.user)
    if request.method == 'POST':
        upload_form = RecieptUploadForm(request.POST, request.FILES, instance = req)

        if upload_form.is_valid():
            req = upload_form.save(commit = False) 
            req.status = 'PENDING_REIMBURSEMENT'
            req.save()

            messages.success(request, f'Your request for the reimbursement has been successfully submitted. Please wait for the approval')
            return redirect('reimbursement_list')
    else:
        upload_form = RecieptUploadForm(instance = req)

    context = {
        'form' : upload_form,
        'title' : f'Upload recipt for {req.title}' 
    } 
    return render(request, 'dashboard/reimbursement_form.html', context)

@login_required
def treasurer_reimbursements(request):
    if request.user.position.can_manage_finance:
        items = Reimbursement.objects.filter(status__in=['PENDING_SPENDING', 'PENDING_REIMBURSEMENT']
        ).order_by('-created_at')

        context = {
            'items' : items
        }

        return render(request ,'dashboard/treasurer_reimbursements.html', context)

@login_required
def approve_reimbursement(request, pk):
    if request.user.position.can_manage_finance:
        req = get_object_or_404(Reimbursement, pk=pk)
        if req.status == 'PENDING_SPENDING':
            req.status = 'APPROVED_BUY'
            messages.success(request, f"Approved spending for {req.requestor.first_name}")
        elif req.status == 'PENDING_REIMBURSEMENT':
            req.status = 'APPROVED_REIMBURSEMENT'
            messages.success(request, f"Approved reimbursement for {req.requestor.first_name}")
        req.save()
        return redirect('treasurer_reimbursements')

@login_required
def all_reimbursements(request):
    if request.user.position.can_manage_finance:
        items = Reimbursement.objects.all()

        context = {
            'items' : items
        }

        return render(request, 'dashboard/all_reimbursements.html', context)

@login_required
def reject_reimbursement(request, pk):
    if request.user.position.can_manage_finance:
        req = get_object_or_404(Reimbursement, pk=pk)
        if req.status == 'PENDING_SPENDING':
            req.status = 'REJECTED_BUY'
            messages.success(request, f"Rejected spending for {req.requestor.first_name}")
        elif req.status == 'PENDING_REIMBURSEMENT':
            req.status = 'REJECTED_REIMBURSEMNET'
            messages.success(request, f"Rejected reimbursement for {req.requestor.first_name}")
        req.save()
        return redirect('treasurer_reimbursements')

@login_required
def get_reimbursement_info(request, pk):
    if request.user.position.can_manage_finance:
        req = get_object_or_404(Reimbursement, pk = pk)
        context = {
            'item' : req
        }

    return render(request, 'dashboard/reimbursement_info.html', context)