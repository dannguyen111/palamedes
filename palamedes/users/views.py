from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import EmailMessage
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # 1. Create user but don't save to DB yet
            user = form.save(commit=False)
            
            # 2. Deactivate until email is confirmed
            user.is_active = False 
            user.save()
            
            # 3. Save Many-to-Many data (required when commit=False)
            form.save_m2m()

            # --- EMAIL VERIFICATION LOGIC ---
            current_site = get_current_site(request)
            mail_subject = 'Activate your Palamedes account.'
            message = render_to_string('users/acc_active_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(
                mail_subject, message, to=[to_email]
            )
            email.send()

            messages.info(request, 'Please confirm your email address to complete the registration.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})

def activate(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        messages.success(request, 'Your account has been activated successfully!')
        return redirect('dashboard')
    else:
        messages.error(request, 'Activation link is invalid!')
        return redirect('register')

@login_required
def profile(request):
    return render(request, 'users/profile.html')