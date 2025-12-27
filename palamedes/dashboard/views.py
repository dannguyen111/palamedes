from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import HousePoint, Due, Task, Announcement

@login_required
def dashboard(request):
    user = request.user
    
    # 1. Calculate Total Approved Points
    # aggregate returns a dictionary like {'amount__sum': 50}
    points_data = HousePoint.objects.filter(user=user, approved=True).aggregate(Sum('amount'))
    total_points = points_data['amount__sum'] or 0 # specific 'or 0' handles if they have no points
    
    # 2. Calculate Total Dues Owed
    dues_data = Due.objects.filter(assigned_to=user, is_paid=False).aggregate(Sum('amount'))
    dues_balance = dues_data['amount__sum'] or 0.00
    
    # 3. Count Pending Tasks
    pending_tasks_count = Task.objects.filter(assigned_to=user, completed=False).count()
    
    # 4. Get Chapter Announcements (Recent 5)
    # We filter by the user's chapter so they don't see other houses' news
    announcements = Announcement.objects.filter(chapter=user.chapter).order_by('-date_posted')[:5]

    context = {
        'total_points': total_points,
        'dues_balance': dues_balance,
        'pending_tasks_count': pending_tasks_count,
        'announcements': announcements
    }
    
    return render(request, 'dashboard/dashboard.html', context)