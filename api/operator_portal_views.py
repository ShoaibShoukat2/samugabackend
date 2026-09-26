"""Public operator portal: register, sign in, and pay the monthly plan outside the iOS app."""
import calendar
from datetime import date, timedelta

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import OperatorSubscription, PlatformSettings, SpeedboatOperator, User

MAX_PROOF_BYTES = 5 * 1024 * 1024
ALLOWED_PROOF_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}


def _days_left(operator):
    if not operator or not operator.subscription_expires_at:
        return 0
    expiry = operator.subscription_expires_at.date()
    return (expiry - date.today()).days


def _add_month(day):
    month = day.month + 1
    year = day.year
    if month > 12:
        month = 1
        year += 1
    last = calendar.monthrange(year, month)[1]
    return day.replace(year=year, month=month, day=min(day.day, last))


def _next_period(operator):
    today = date.today()
    if operator.subscription_expires_at and operator.subscription_expires_at.date() >= today:
        start = operator.subscription_expires_at.date() + timedelta(days=1)
    else:
        start = today
    end = _add_month(start) - timedelta(days=1)
    return start, end


def _grant_trial(operator, settings):
    today = date.today()
    free_end = today + timedelta(days=settings.free_trial_days - 1)
    OperatorSubscription.objects.create(
        operator=operator,
        plan='basic',
        amount=0,
        start_date=today,
        end_date=free_end,
        payment_status='paid',
        paid_at=timezone.now(),
    )
    operator.subscription_status = 'active'
    operator.subscription_expires_at = timezone.datetime.combine(
        free_end, timezone.datetime.min.time()
    ).replace(tzinfo=timezone.get_current_timezone())
    operator.save(update_fields=['subscription_status', 'subscription_expires_at'])
    return free_end


def _find_user(email):
    return User.objects.filter(email__iexact=email.strip()).first()


def _login_user(request, user):
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')


def _operator_for(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return SpeedboatOperator.objects.filter(user=user).first()


def _context(request, **extra):
    settings = PlatformSettings.get()
    user = request.user if request.user.is_authenticated else None
    operator = _operator_for(user)
    pending = None
    latest = None
    if operator:
        pending = operator.subscriptions.filter(payment_status='pending').order_by('-created_at').first()
        latest = operator.subscriptions.order_by('-created_at').first()
    ctx = {
        'settings': settings,
        'operator': operator,
        'pending': pending,
        'latest': latest,
        'days_left': _days_left(operator) if operator else 0,
        'panel': extra.pop('panel', 'register'),
        'form': extra.pop('form', {}),
        'error': extra.pop('error', ''),
        'success': extra.pop('success', ''),
    }
    ctx.update(extra)
    return ctx


def _handle_register(request):
    data = request.POST
    form = {
        'first_name': data.get('first_name', '').strip(),
        'last_name': data.get('last_name', '').strip(),
        'email': data.get('email', '').strip().lower(),
        'phone_number': data.get('phone_number', '').strip(),
        'company_name': data.get('company_name', '').strip(),
        'business_license': data.get('business_license', '').strip(),
        'service_islands': data.get('service_islands', '').strip(),
    }
    password = data.get('password', '')
    confirm = data.get('confirm_password', '')

    if not form['first_name'] or not form['email'] or not form['company_name'] or not form['service_islands']:
        return _context(request, panel='register', form=form, error='Please fill in all required fields.')
    if '@' not in form['email'] or '.' not in form['email'].split('@')[-1]:
        return _context(request, panel='register', form=form, error='Enter a valid email address.')
    if len(password) < 6:
        return _context(request, panel='register', form=form, error='Password must be at least 6 characters.')
    if password != confirm:
        return _context(request, panel='register', form=form, error='Passwords do not match.')
    if _find_user(form['email']):
        return _context(request, panel='register', form=form, error='An account with this email already exists. Sign in instead.')
    if form['phone_number'] and User.objects.filter(phone_number=form['phone_number']).exists():
        return _context(request, panel='register', form=form, error='An account with this phone number already exists.')

    settings = PlatformSettings.get()
    with transaction.atomic():
        user = User(
            username=form['email'],
            email=form['email'],
            first_name=form['first_name'],
            last_name=form['last_name'],
            phone_number=form['phone_number'] or None,
            user_type='operator',
        )
        user.set_password(password)
        user.save()
        operator = SpeedboatOperator.objects.create(
            user=user,
            company_name=form['company_name'],
            contact_person=f"{form['first_name']} {form['last_name']}".strip(),
            phone_number=form['phone_number'] or form['email'],
            email=form['email'],
            business_license=form['business_license'],
            service_islands=form['service_islands'],
        )
        free_end = _grant_trial(operator, settings)

    _login_user(request, user)
    return _context(
        request,
        panel='account',
        success=f'Welcome aboard. Your first {settings.free_trial_days} days are free, until {free_end.strftime("%d %b %Y")}.',
    )


def _handle_login(request):
    email = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '')
    form = {'email': email}
    if not email or not password:
        return _context(request, panel='login', form=form, error='Email and password are required.')

    user = authenticate(request, username=email, password=password)
    if not user:
        user_obj = _find_user(email)
        if user_obj and user_obj.check_password(password) and user_obj.is_active:
            user = user_obj
    if not user:
        return _context(request, panel='login', form=form, error='Email or password is incorrect.')
    if not user.is_active:
        return _context(request, panel='login', form=form, error='This account is disabled. Contact support.')

    if user.user_type != 'operator' and _operator_for(user):
        user.user_type = 'operator'
        user.save(update_fields=['user_type'])

    _login_user(request, user)
    if not _operator_for(user):
        return _context(
            request,
            panel='complete',
            form={'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name},
            error='This email is a customer account. Add your business details to become an operator.',
        )
    return _context(request, panel='account', success='Signed in.')


def _handle_complete(request):
    user = request.user
    if not user.is_authenticated:
        return _context(request, panel='login', error='Sign in first.')
    if _operator_for(user):
        return _context(request, panel='account')

    form = {
        'company_name': request.POST.get('company_name', '').strip(),
        'phone_number': request.POST.get('phone_number', '').strip(),
        'business_license': request.POST.get('business_license', '').strip(),
        'service_islands': request.POST.get('service_islands', '').strip(),
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
    }
    if not form['company_name'] or not form['service_islands'] or not form['phone_number']:
        return _context(request, panel='complete', form=form, error='Company name, phone, and islands are required.')

    settings = PlatformSettings.get()
    with transaction.atomic():
        user.user_type = 'operator'
        if not user.phone_number and form['phone_number']:
            if User.objects.filter(phone_number=form['phone_number']).exclude(pk=user.pk).exists():
                return _context(request, panel='complete', form=form, error='That phone number is already in use.')
            user.phone_number = form['phone_number']
        user.save()
        operator = SpeedboatOperator.objects.create(
            user=user,
            company_name=form['company_name'],
            contact_person=f"{user.first_name} {user.last_name}".strip() or form['company_name'],
            phone_number=form['phone_number'],
            email=user.email,
            business_license=form['business_license'],
            service_islands=form['service_islands'],
        )
        free_end = _grant_trial(operator, settings)

    return _context(
        request,
        panel='account',
        success=f'Operator account created. Your first {settings.free_trial_days} days are free, until {free_end.strftime("%d %b %Y")}.',
    )


def _handle_pay(request):
    user = request.user
    operator = _operator_for(user)
    if not operator:
        return _context(request, panel='login', error='Sign in with your operator account to submit a payment.')
    if operator.subscriptions.filter(payment_status='pending').exists():
        return _context(request, panel='account', error='A payment is already waiting for review. We will activate your plan once it is checked.')

    proof = request.FILES.get('payment_proof')
    if not proof:
        return _context(request, panel='account', error='Upload a photo of your bank transfer.')
    if proof.size > MAX_PROOF_BYTES:
        return _context(request, panel='account', error='That image is too large. Use a photo under 5 MB.')
    content_type = (proof.content_type or '').lower()
    if content_type and content_type not in ALLOWED_PROOF_TYPES:
        return _context(request, panel='account', error='Upload a JPG, PNG, or WEBP image of the transfer.')

    settings = PlatformSettings.get()
    start, end = _next_period(operator)
    reference = request.POST.get('transaction_id', '').strip()

    OperatorSubscription.objects.create(
        operator=operator,
        plan='basic',
        amount=settings.subscription_price,
        start_date=start,
        end_date=end,
        payment_status='pending',
        payment_proof=proof,
    )
    note = f' Reference: {reference}.' if reference else ''
    return _context(
        request,
        panel='account',
        success=f'Payment received.{note} We will review it within 24 hours and then activate your plan.',
    )


@require_http_methods(['GET', 'POST'])
def operator_portal(request):
    if request.method == 'GET':
        if request.user.is_authenticated and _operator_for(request.user):
            return render(request, 'operators/portal.html', _context(request, panel='account'))
        if request.user.is_authenticated:
            return render(request, 'operators/portal.html', _context(request, panel='complete'))
        panel = request.GET.get('tab', 'register')
        if panel not in ('register', 'login'):
            panel = 'register'
        return render(request, 'operators/portal.html', _context(request, panel=panel))

    action = request.POST.get('action')
    if action == 'logout':
        logout(request)
        return redirect('operator_portal')
    if action == 'register':
        ctx = _handle_register(request)
    elif action == 'login':
        ctx = _handle_login(request)
    elif action == 'complete':
        ctx = _handle_complete(request)
    elif action == 'pay':
        ctx = _handle_pay(request)
    else:
        ctx = _context(request, error='Something went wrong. Please try again.')
    return render(request, 'operators/portal.html', ctx)
