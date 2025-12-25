from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CustomUserCreationForm # Import our new form

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            role = user.get_role_display()
            messages.success(request, f'Account created for {username}! You are registered as: {role}')
            return redirect('home') # Redirect to home (or login page later)
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})