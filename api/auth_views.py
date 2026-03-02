from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import User

def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_admin:
        return redirect('admin_dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)
            
            if user is not None:
                if user.is_admin:
                    login(request, user)
                    return redirect('admin_dashboard')
                else:
                    messages.error(request, 'You do not have admin access.')
            else:
                messages.error(request, 'Invalid email or password.')
        except User.DoesNotExist:
            messages.error(request, 'Invalid email or password.')
    
    return render(request, 'admin_panel/login.html')

def admin_logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('admin_login')
