from django.shortcuts import render
from django.contrib.auth.forms import UserCreationForm

# Create your views here.
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            # Redirect to a success page or log in the user
    else:
        form = UserCreationForm()
    return render(request, 'users/register.html', {'form': form})