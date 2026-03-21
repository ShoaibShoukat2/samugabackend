from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import timedelta
from .models import (User, TripRequest, Quote, Payment, Booking, SupportMessage, 
                    Notification, SpeedboatOperator, Speedboat, OperatorSubscription, 
                    OperatorRating, PlatformRevenue, PlatformSettings)
from decimal import Decimal

def is_admin(user):
    return user.is_authenticated and user.is_admin

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Get statistics
    total_trips = TripRequest.objects.count()
    pending_trips = TripRequest.objects.filter(status='pending').count()
    confirmed_bookings = TripRequest.objects.filter(status='confirmed').count()
    pending_payments = Payment.objects.filter(status='pending').count()
    total_users = User.objects.filter(is_admin=False).count()
    
    # Marketplace statistics
    total_operators = SpeedboatOperator.objects.count()
    verified_operators = SpeedboatOperator.objects.filter(verification_status='verified').count()
    pending_operators = SpeedboatOperator.objects.filter(verification_status='pending').count()
    active_subscriptions = SpeedboatOperator.objects.filter(subscription_status='active').count()
    
    # Revenue statistics
    monthly_subscription_revenue = PlatformRevenue.objects.filter(
        revenue_type='subscription',
        created_at__month=timezone.now().month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_commission_revenue = PlatformRevenue.objects.filter(
        revenue_type='commission',
        created_at__month=timezone.now().month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Recent trips
    recent_trips = TripRequest.objects.select_related('user').order_by('-created_at')[:10]
    
    # Pending payments
    pending_payment_list = Payment.objects.filter(status='pending').select_related('trip_request__user')[:5]
    
    # Recent support messages
    recent_messages = SupportMessage.objects.filter(is_admin_reply=False, read=False).select_related('user')[:5]
    
    context = {
        'total_trips': total_trips,
        'pending_trips': pending_trips,
        'confirmed_bookings': confirmed_bookings,
        'pending_payments': pending_payments,
        'total_users': total_users,
        'total_operators': total_operators,
        'verified_operators': verified_operators,
        'pending_operators': pending_operators,
        'active_subscriptions': active_subscriptions,
        'monthly_subscription_revenue': monthly_subscription_revenue,
        'monthly_commission_revenue': monthly_commission_revenue,
        'recent_trips': recent_trips,
        'pending_payment_list': pending_payment_list,
        'recent_messages': recent_messages,
    }
    
    return render(request, 'admin_panel/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def accepted_requests(request):
    """Shows all trips that have been accepted by an operator — full assignment details"""
    status_filter = request.GET.get('status', 'all')
    try:
        # Step 1: fetch trips — only select_related('user'), no prefetch
        qs = TripRequest.objects.filter(
            status__in=['accepted', 'payment_pending', 'confirmed', 'completed']
        ).select_related('user').order_by('-updated_at')

        if status_filter != 'all':
            qs = qs.filter(status=status_filter)

        trips = list(qs)
        trip_ids = [t.id for t in trips]

        # Step 2: fetch accepted quotes separately — select_related only on direct FK fields
        accepted_quotes_qs = Quote.objects.filter(
            trip_request_id__in=trip_ids,
            status='accepted'
        ).select_related('operator', 'boat')
        aq_map = {str(q.trip_request_id): q for q in accepted_quotes_qs}

        # Step 3: fetch payments separately
        try:
            from .models import Payment as P2
            payments_qs = P2.objects.filter(trip_request_id__in=trip_ids)
            pay_map = {str(p.trip_request_id): p for p in payments_qs}
        except Exception:
            pay_map = {}

        # Step 4: fetch bookings separately
        try:
            bookings_qs = Booking.objects.filter(trip_request_id__in=trip_ids)
            book_map = {str(b.trip_request_id): b for b in bookings_qs}
        except Exception:
            book_map = {}

        trip_data = []
        for trip in trips:
            tid = str(trip.id)
            trip_data.append({
                'trip': trip,
                'accepted_quote': aq_map.get(tid),
                'payment': pay_map.get(tid),
                'booking': book_map.get(tid),
            })

        stats = {
            'total': len(trip_data),
            'awaiting_payment': sum(1 for d in trip_data if d['trip'].status == 'accepted'),
            'payment_pending': sum(1 for d in trip_data if d['trip'].status == 'payment_pending'),
            'confirmed': sum(1 for d in trip_data if d['trip'].status == 'confirmed'),
            'completed': sum(1 for d in trip_data if d['trip'].status == 'completed'),
        }

        context = {
            'trip_data': trip_data,
            'stats': stats,
            'status_filter': status_filter,
            'filter_tabs': [
                ('all', 'All Assigned', 'bg-blue-600'),
                ('accepted', 'Awaiting Payment', 'bg-orange-500'),
                ('payment_pending', 'Payment Pending', 'bg-purple-600'),
                ('confirmed', 'Confirmed', 'bg-green-600'),
                ('completed', 'Completed', 'bg-gray-600'),
            ],
        }
        return render(request, 'admin_panel/accepted_requests.html', context)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return render(request, 'admin_panel/accepted_requests.html', {
            'trip_data': [],
            'error': str(e),
            'stats': {'total': 0, 'awaiting_payment': 0, 'payment_pending': 0, 'confirmed': 0, 'completed': 0},
            'status_filter': status_filter,
            'filter_tabs': [('all', 'All Assigned', 'bg-blue-600')],
        })


@login_required
@user_passes_test(is_admin)
def trip_requests_list(request):
    status_filter = request.GET.get('status', 'all')
    try:
        from django.db import connection

        # Step 1: fetch trips via raw SQL — zero ORM UUID traversal
        status_clause = ''
        params = []
        if status_filter != 'all':
            status_clause = "WHERE tr.status = %s"
            params.append(status_filter)

        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT tr.id, tr.trip_type, tr.pickup_location, tr.destination,
                       tr.trip_date, tr.trip_time, tr.passenger_count,
                       tr.status, tr.created_at, tr.updated_at,
                       u.first_name, u.last_name, u.email, u.phone_number
                FROM api_triprequest tr
                JOIN api_user u ON tr.user_id = u.id
                {status_clause}
                ORDER BY tr.created_at DESC
            """, params)
            cols = [c[0] for c in cursor.description]
            trip_rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

        trip_ids = [r['id'] for r in trip_rows]

        # Step 2: fetch quotes + operator names via raw SQL
        quotes_map: dict = {}
        if trip_ids:
            placeholders = ','.join(['%s'] * len(trip_ids))
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT q.trip_request_id, q.status, q.amount, q.currency,
                           COALESCE(op.company_name, '') as operator_name,
                           COALESCE(op.phone_number, '') as operator_phone
                    FROM api_quote q
                    LEFT JOIN api_speedboatoperator op ON q.operator_id = op.id
                    WHERE q.trip_request_id IN ({placeholders})
                """, [str(i) for i in trip_ids])
                for row in cursor.fetchall():
                    tid = str(row[0])
                    quotes_map.setdefault(tid, []).append({
                        'status': row[1],
                        'amount': row[2],
                        'currency': row[3],
                        'operator_name': row[4],
                        'operator_phone': row[5],
                    })

        # Step 3: attach quotes to trip dicts
        for trip in trip_rows:
            trip['trip_quotes'] = quotes_map.get(str(trip['id']), [])
            trip['accepted_quote'] = next(
                (q for q in trip['trip_quotes'] if q['status'] == 'accepted'), None
            )

        context = {
            'trips': trip_rows,
            'status_filter': status_filter,
            'filter_tabs': [
                ('all', 'All', 'bg-blue-600'),
                ('pending', 'Pending', 'bg-yellow-600'),
                ('quoted', 'Quoted', 'bg-blue-500'),
                ('accepted', 'Accepted', 'bg-orange-500'),
                ('payment_pending', 'Payment Pending', 'bg-purple-600'),
                ('confirmed', 'Confirmed', 'bg-green-600'),
                ('completed', 'Completed', 'bg-gray-600'),
            ],
        }
        return render(request, 'admin_panel/trip_requests.html', context)
    except Exception as e:
        import traceback; traceback.print_exc()
        return render(request, 'admin_panel/trip_requests.html', {
            'trips': [], 'error': str(e), 'status_filter': status_filter,
            'filter_tabs': [('all', 'All', 'bg-blue-600')],
        })

@login_required
@user_passes_test(is_admin)
def send_quote_view(request, trip_id):
    trip = get_object_or_404(TripRequest, id=trip_id)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        currency = request.POST.get('currency', 'USD')
        operator_name = request.POST.get('operator_name')
        operator_contact = request.POST.get('operator_contact')
        notes = request.POST.get('notes', '')
        valid_days = int(request.POST.get('valid_days', 7))
        
        # Create or update quote
        quote, created = Quote.objects.update_or_create(
            trip_request=trip,
            defaults={
                'amount': Decimal(amount),
                'currency': currency,
                'operator_name': operator_name,
                'operator_contact': operator_contact,
                'notes': notes,
                'valid_until': timezone.now() + timedelta(days=valid_days)
            }
        )
        
        # Update trip status
        trip.status = 'quoted'
        trip.save()
        
        # Create notification for user
        currency_symbol = '$' if currency == 'USD' else 'MVR'
        Notification.objects.create(
            user=trip.user,
            title='Quote Received',
            message=f'You have received a quote of {currency_symbol}{amount} for your {trip.trip_type} trip',
            trip_request=trip
        )
        
        messages.success(request, 'Quote sent successfully!')
        return redirect('admin_trip_requests')
    
    context = {
        'trip': trip,
    }
    
    return render(request, 'admin_panel/send_quote.html', context)

@login_required
@user_passes_test(is_admin)
def payments_list(request):
    status_filter = request.GET.get('status', 'all')
    
    payments = Payment.objects.select_related('trip_request__user').order_by('-created_at')
    
    if status_filter != 'all':
        payments = payments.filter(status=status_filter)
    
    context = {
        'payments': payments,
        'status_filter': status_filter,
    }
    
    return render(request, 'admin_panel/payments.html', context)

@login_required
@user_passes_test(is_admin)
def verify_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'reject':
            # Reject payment
            payment.status = 'failed'
            payment.save()
            
            # Update trip status back to accepted
            trip = payment.trip_request
            trip.status = 'accepted'
            trip.save()
            
            # Notify user
            Notification.objects.create(
                user=trip.user,
                title='Payment Rejected',
                message=f'Your payment for {trip.trip_type} trip was rejected. Please resubmit with correct details.',
                trip_request=trip
            )
            
            messages.warning(request, 'Payment rejected. Customer has been notified.')
            return redirect('admin_payments')
        
        elif action == 'approve':
            # Approve payment
            payment.status = 'verified'
            payment.verified_at = timezone.now()
            payment.save()
            
            # Update trip status
            trip = payment.trip_request
            trip.status = 'confirmed'
            trip.save()
            
            # Generate booking
            import random
            booking_code = f"ST{random.randint(100000, 999999)}"
            
            # Find the accepted quote (operator's quote that was accepted)
            accepted_quote = trip.quotes.filter(status='accepted').first()
            
            booking = Booking.objects.create(
                trip_request=trip,
                booking_code=booking_code,
                selected_quote=accepted_quote,
            )
            
            # Generate QR code
            import qrcode
            from io import BytesIO
            from django.core.files import File
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(booking_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            booking.qr_code.save(f'{booking_code}.png', File(buffer), save=True)
            
            # Notify customer
            Notification.objects.create(
                user=trip.user,
                title='Booking Confirmed',
                message=f'Your booking is confirmed! Booking code: {booking_code}',
                trip_request=trip
            )
            
            # Notify the operator whose quote was accepted
            if accepted_quote and accepted_quote.operator:
                Notification.objects.create(
                    user=accepted_quote.operator.user,
                    title='Payment Confirmed — Trip Ready',
                    message=f'Payment verified for your {trip.trip_type} trip on {trip.trip_date}. '
                            f'Customer: {trip.user.first_name} {trip.user.last_name}. '
                            f'Booking code: {booking_code}',
                    trip_request=trip
                )
            
            messages.success(request, f'Payment approved and booking {booking_code} created!')
            return redirect('admin_payments')
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'admin_panel/verify_payment.html', context)

@login_required
@user_passes_test(is_admin)
def bookings_list(request):
    bookings = Booking.objects.select_related('trip_request__user').order_by('-created_at')
    
    context = {
        'bookings': bookings,
    }
    
    return render(request, 'admin_panel/bookings.html', context)

@login_required
@user_passes_test(is_admin)
def support_messages(request):
    conversations = []
    users_with_messages = User.objects.filter(support_messages__isnull=False).distinct()
    
    for user in users_with_messages:
        messages_list = SupportMessage.objects.filter(user=user).order_by('created_at')
        unread_count = messages_list.filter(is_admin_reply=False, read=False).count()
        
        conversations.append({
            'user': user,
            'messages': messages_list,
            'unread_count': unread_count,
            'last_message': messages_list.last()
        })
    
    context = {
        'conversations': conversations,
    }
    
    return render(request, 'admin_panel/support.html', context)

@login_required
@user_passes_test(is_admin)
def send_support_reply(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        message_text = request.POST.get('message')
        
        SupportMessage.objects.create(
            user=user,
            message=message_text,
            is_admin_reply=True
        )
        
        # Mark user messages as read
        SupportMessage.objects.filter(user=user, is_admin_reply=False, read=False).update(read=True)
        
        messages.success(request, 'Reply sent successfully!')
        return redirect('admin_support')
    
    return redirect('admin_support')

@login_required
@user_passes_test(is_admin)
def users_list(request):
    users = User.objects.filter(is_admin=False).order_by('-date_joined')
    
    context = {
        'users': users,
    }
    
    return render(request, 'admin_panel/users.html', context)

# ============ MARKETPLACE ADMIN VIEWS ============

@login_required
@user_passes_test(is_admin)
def operators_list(request):
    status_filter = request.GET.get('status', 'all')
    
    operators = SpeedboatOperator.objects.select_related('user').order_by('-created_at')
    
    if status_filter != 'all':
        operators = operators.filter(verification_status=status_filter)
    
    context = {
        'operators': operators,
        'status_filter': status_filter,
    }
    
    return render(request, 'admin_panel/operators.html', context)

@login_required
@user_passes_test(is_admin)
def operator_detail(request, operator_id):
    operator = get_object_or_404(SpeedboatOperator, id=operator_id)
    boats = operator.boats.all()
    subscriptions = operator.subscriptions.order_by('-created_at')
    quotes = operator.quotes.select_related('trip_request').order_by('-created_at')[:10]
    ratings = operator.received_ratings.select_related('customer', 'booking').order_by('-created_at')[:10]
    
    context = {
        'operator': operator,
        'boats': boats,
        'subscriptions': subscriptions,
        'quotes': quotes,
        'ratings': ratings,
    }
    
    return render(request, 'admin_panel/operator_detail.html', context)

@login_required
@user_passes_test(is_admin)
def verify_operator(request, operator_id):
    operator = get_object_or_404(SpeedboatOperator, id=operator_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        
        if action == 'approve':
            operator.verification_status = 'verified'
            operator.save()
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Operator Account Approved',
                message=f'Congratulations! Your operator account has been approved. You can now receive trip requests.'
            )
            
            messages.success(request, f'Operator {operator.company_name} has been approved!')
            
        elif action == 'reject':
            operator.verification_status = 'rejected'
            operator.save()
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Operator Account Rejected',
                message=f'Your operator account application has been rejected. Reason: {notes}'
            )
            
            messages.warning(request, f'Operator {operator.company_name} has been rejected.')
            
        elif action == 'suspend':
            operator.verification_status = 'suspended'
            operator.subscription_status = 'cancelled'
            operator.save()
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Account Suspended',
                message=f'Your operator account has been suspended. Reason: {notes}'
            )
            
            messages.warning(request, f'Operator {operator.company_name} has been suspended.')
        
        return redirect('admin_operators')
    
    context = {
        'operator': operator,
    }
    
    return render(request, 'admin_panel/verify_operator.html', context)

@login_required
@user_passes_test(is_admin)
def subscriptions_list(request):
    status_filter = request.GET.get('status', 'all')
    settings = PlatformSettings.get()

    subscriptions = OperatorSubscription.objects.select_related('operator__user').order_by('-created_at')

    if status_filter != 'all':
        subscriptions = subscriptions.filter(payment_status=status_filter)

    # Stats
    total_paid = OperatorSubscription.objects.filter(payment_status='paid').count()
    total_pending = OperatorSubscription.objects.filter(payment_status='pending').count()
    total_revenue = OperatorSubscription.objects.filter(payment_status='paid').aggregate(
        total=Sum('amount'))['total'] or 0

    context = {
        'subscriptions': subscriptions,
        'status_filter': status_filter,
        'settings': settings,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'total_revenue': total_revenue,
    }

    return render(request, 'admin_panel/subscriptions.html', context)

@login_required
@user_passes_test(is_admin)
def verify_subscription(request, subscription_id):
    subscription = get_object_or_404(OperatorSubscription, id=subscription_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            subscription.payment_status = 'paid'
            subscription.paid_at = timezone.now()
            subscription.save()
            
            # Update operator subscription status
            operator = subscription.operator
            operator.subscription_status = 'active'
            operator.subscription_expires_at = timezone.datetime.combine(
                subscription.end_date,
                timezone.datetime.min.time()
            ).replace(tzinfo=timezone.get_current_timezone())
            operator.save()
            
            # Create revenue record
            PlatformRevenue.objects.create(
                revenue_type='subscription',
                amount=subscription.amount,
                currency='MVR',
                subscription=subscription,
                description=f'Subscription payment from {operator.company_name}'
            )
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Subscription Activated',
                message=f'Your subscription has been activated until {subscription.end_date.strftime("%B %d, %Y")}'
            )
            
            messages.success(request, f'Subscription approved for {operator.company_name}!')
            
        elif action == 'reject':
            subscription.payment_status = 'overdue'
            subscription.save()
            
            # Update operator subscription status
            operator = subscription.operator
            operator.subscription_status = 'expired'
            operator.save()
            
            # Notify operator
            Notification.objects.create(
                user=operator.user,
                title='Subscription Payment Rejected',
                message='Your subscription payment was rejected. Please resubmit with correct payment proof.'
            )
            
            messages.warning(request, f'Subscription rejected for {operator.company_name}.')
        
        return redirect('admin_subscriptions')
    
    context = {
        'subscription': subscription,
    }
    
    return render(request, 'admin_panel/verify_subscription.html', context)

@login_required
@user_passes_test(is_admin)
def marketplace_quotes(request):
    status_filter = request.GET.get('status', 'all')
    
    try:
        # Get quotes without select_related to avoid UUID errors
        quotes = Quote.objects.select_related('trip_request__user').order_by('-created_at')
        
        if status_filter != 'all':
            quotes = quotes.filter(status=status_filter)
        
        context = {
            'quotes': quotes,
            'status_filter': status_filter,
        }
        
        return render(request, 'admin_panel/marketplace_quotes.html', context)
    except Exception as e:
        print(f"Error in marketplace_quotes: {e}")
        # Return empty quotes if there's an error
        context = {
            'quotes': Quote.objects.none(),
            'status_filter': status_filter,
        }
        return render(request, 'admin_panel/marketplace_quotes.html', context)

@login_required
@user_passes_test(is_admin)
def revenue_dashboard(request):
    current_month = timezone.now().month
    current_year = timezone.now().year

    subscription_revenue = PlatformRevenue.objects.filter(
        revenue_type='subscription',
        created_at__month=current_month,
        created_at__year=current_year
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Recent revenue records
    recent_revenues = PlatformRevenue.objects.select_related(
        'subscription__operator'
    ).order_by('-created_at')[:20]

    active_operators = SpeedboatOperator.objects.filter(subscription_status='active').count()
    expired_operators = SpeedboatOperator.objects.filter(subscription_status='expired').count()

    settings = PlatformSettings.get()
    projected_subscription = active_operators * settings.subscription_price

    context = {
        'subscription_revenue': subscription_revenue,
        'total_monthly_revenue': subscription_revenue,
        'recent_revenues': recent_revenues,
        'active_operators': active_operators,
        'expired_operators': expired_operators,
        'projected_subscription': projected_subscription,
        'settings': settings,
    }

    return render(request, 'admin_panel/revenue_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def platform_settings(request):
    settings = PlatformSettings.get()

    if request.method == 'POST':
        subscription_fee = request.POST.get('subscription_fee', '450.0')
        free_trial_days = request.POST.get('free_trial_days', '30')
        try:
            settings.subscription_price = Decimal(subscription_fee)
            settings.free_trial_days = int(free_trial_days)
            settings.updated_by = request.user
            settings.save()
            messages.success(request, 'Platform settings updated successfully!')
        except Exception as e:
            messages.error(request, f'Error saving settings: {e}')
        return redirect('admin_platform_settings')

    context = {
        'settings': settings,
    }
    return render(request, 'admin_panel/platform_settings.html', context)


@login_required
@user_passes_test(is_admin)
def ratings_list(request):
    """Admin view — all customer ratings with operator and customer details"""
    operator_filter = request.GET.get('operator', '')
    rating_filter = request.GET.get('rating', '')

    ratings = OperatorRating.objects.select_related(
        'customer', 'operator', 'booking__trip_request'
    ).order_by('-created_at')

    if operator_filter:
        ratings = ratings.filter(operator__company_name__icontains=operator_filter)
    if rating_filter:
        ratings = ratings.filter(rating=rating_filter)

    context = {
        'ratings': ratings,
        'operator_filter': operator_filter,
        'rating_filter': rating_filter,
    }
    return render(request, 'admin_panel/ratings.html', context)
