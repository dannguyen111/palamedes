from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ChapterRequestForm

def home(request):
    return render(request, 'homepage/home.html', {'title': 'Home'})

def about(request):
    return render(request, 'homepage/about.html', {'title': 'About'})

def start_chapter(request):
    if request.method == 'POST':
        form = ChapterRequestForm(request.POST)
        if form.is_valid():
            form.save() # Saves to DB instead of emailing
            messages.success(request, 'Your request has been submitted! An admin will contact you shortly.')
            return redirect('home')
    else:
        form = ChapterRequestForm()
    
    return render(request, 'homepage/start_chapter.html', {'form': form, 'title': 'Start Chapter'})