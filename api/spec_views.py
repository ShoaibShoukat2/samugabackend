"""
Spec-aligned API endpoints for the native app / Telegram mini-app frontend.
Maps to ferry schedules, boat requests, invoices, and assist features.
"""
from datetime import datetime, timedelta, time as dt_time
from decimal import Decimal
import json
import os
import random
import re
import urllib.error
import urllib.request

from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import (
    Schedule, BoatRequest, Passenger, Booking, TripRequest, Quote,
    Payment, Speedboat, SpeedboatOperator, PlatformSettings, SupportMessage,
    User,
)
from .serializers import TripRequestSerializer, UserSerializer

MALDIVES_PLACES = [
    'Velana International Airport (Malé)', 'Malé City', 'Hulhumalé', 'Maafushi Island',
    'Thulusdhoo Island', 'Guraidhoo Island', 'Dhiffushi Island', 'Rasdhoo Island',
    'Ukulhas Island', 'Fulidhoo Island', 'Dhigurah Island', 'Addu City', 'Gan Island',
    'Villingili Ferry Terminal', 'Hulhumalé Ferry Terminal', 'Malé Ferry Terminal',
    'Naifaru Island', 'Dharavandhoo Island', 'Fuvahmulah Island',
]


def _generate_booking_ref():
    now = timezone.now()
    return f"ST-{now.strftime('%y%m%d')}-{random.randint(1000, 9999)}"


def _generate_request_ref():
    now = timezone.now()
    return f"BR-{now.strftime('%y%m%d')}-{now.strftime('%H%M%S')}"


def _run_day_matches(run_days: str, date) -> bool:
    wd = date.weekday()  # Mon=0 ... Fri=4
    if run_days == 'daily':
        return True
    if run_days == 'fri':
        return wd == 4
    if run_days == 'sat-thu':
        return wd != 4
    return True


def _ensure_schedules():
    """Auto-create ferry schedules from verified speedboats if none exist."""
    if Schedule.objects.filter(is_active=True).exists():
        return
    boats = Speedboat.objects.filter(is_active=True, operator__verification_status='verified')
    for boat in boats:
        islands = [i.strip() for i in boat.operator.service_islands.split(',') if i.strip()]
        route_from = islands[0] if islands else 'Malé City'
        route_to = islands[-1] if len(islands) > 1 else 'Maafushi Island'
        Schedule.objects.get_or_create(
            operator=boat.operator,
            boat=boat,
            route_from=route_from,
            route_to=route_to,
            defaults={
                'sched_stops': islands[:5] or [route_from, route_to],
                'departure_time': dt_time(9, 0),
                'price_per_seat': Decimal('350'),
                'available_seats': boat.capacity,
                'run_days': 'daily',
                'is_active': True,
            },
        )


def _schedule_to_search_result(s: Schedule, travel_date, seats_taken: int):
    op = s.operator
    boat = s.boat
    return {
        'id': str(s.id),
        'schedule_id': str(s.id),
        'boat_id': str(boat.id) if boat else None,
        'operator_name': op.company_name,
        'operator_details': {
            'company_name': op.company_name,
            'average_rating': float(op.average_rating),
            'total_ratings': op.total_ratings,
        },
        'boat_name': boat.name if boat else 'Speedboat',
        'name': boat.name if boat else 'Speedboat',
        'route_from': s.route_from,
        'route_to': s.route_to,
        'sched_stops': s.sched_stops,
        'departure_time': s.departure_time.strftime('%H:%M'),
        'price_per_seat': float(s.price_per_seat),
        'base_price': float(s.price_per_seat),
        'available_seats': max(0, s.available_seats - seats_taken),
        'capacity': s.available_seats,
        'travel_date': str(travel_date),
        'run_days': s.run_days,
    }


def _seats_booked(schedule: Schedule, travel_date) -> int:
    return TripRequest.objects.filter(
        booking__schedule=schedule,
        trip_date=travel_date,
        status__in=['accepted', 'payment_pending', 'confirmed'],
    ).aggregate(total=Sum('passenger_count'))['total'] or 0


def _trip_to_booking_dict(trip: TripRequest):
    booking = getattr(trip, 'booking', None)
    payment = getattr(trip, 'payment', None)
    ref = booking.booking_code if booking else _generate_booking_ref()
    display_status = trip.status
    if trip.status == 'accepted':
        display_status = 'pending_payment'
    elif trip.status == 'payment_pending':
        display_status = 'pending_confirmation'
    elif trip.status == 'confirmed':
        display_status = 'confirmed'
    elif trip.status == 'cancelled':
        display_status = 'cancelled'

    return {
        'id': str(trip.id),
        'trip_id': str(trip.id),
        'booking_ref': ref,
        'pickup_location': trip.pickup_location,
        'destination': trip.destination,
        'route_from': trip.pickup_location,
        'route_to': trip.destination,
        'travel_date': str(trip.trip_date),
        'trip_date': str(trip.trip_date),
        'trip_time': str(trip.trip_time),
        'passenger_count': trip.passenger_count,
        'status': display_status,
        'trip_status': trip.status,
        'special_notes': trip.special_notes,
        'payment': {'status': payment.status} if payment else None,
        'booking': {
            'booking_code': ref,
            'ticket_url': booking.ticket_url if booking else '',
            'status': booking.status if booking else display_status,
        } if booking else None,
        'quotes': [],
        'created_at': trip.created_at.isoformat(),
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def places_search(request):
    q = (request.query_params.get('q') or '').strip()
    if len(q) < 1:
        return Response([])
    results = [p for p in MALDIVES_PLACES if q.lower() in p.lower()][:6]
    return Response([{'id': f'p{i}', 'name': n} for i, n in enumerate(results)])


@api_view(['GET'])
@permission_classes([AllowAny])
def search_boats(request):
    route_from = (request.query_params.get('from') or '').strip()
    route_to = (request.query_params.get('to') or '').strip()
    date_str = request.query_params.get('date')
    try:
        travel_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.now().date()
    except ValueError:
        travel_date = timezone.now().date()

    _ensure_schedules()
    schedules = Schedule.objects.filter(is_active=True).select_related('operator', 'boat')

    if route_from:
        schedules = schedules.filter(
            Q(route_from__icontains=route_from.split()[0]) |
            Q(sched_stops__icontains=route_from.split()[0])
        )
    if route_to:
        schedules = schedules.filter(
            Q(route_to__icontains=route_to.split()[0]) |
            Q(sched_stops__icontains=route_to.split()[0])
        )

    results = []
    for s in schedules:
        if not _run_day_matches(s.run_days, travel_date):
            continue
        taken = _seats_booked(s, travel_date)
        if s.available_seats - taken <= 0:
            continue
        results.append(_schedule_to_search_result(s, travel_date, taken))

    return Response(results)


@api_view(['GET'])
@permission_classes([AllowAny])
def ferry_operators(request):
    _ensure_schedules()
    schedules = Schedule.objects.filter(is_active=True).select_related('operator', 'boat')
    travel_date = timezone.now().date()
    return Response([
        _schedule_to_search_result(s, travel_date, _seats_booked(s, travel_date))
        for s in schedules if _run_day_matches(s.run_days, travel_date)
    ])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_booking(request):
    data = request.data
    schedule_id = data.get('schedule_id')
    passenger_count = int(data.get('passenger_count', 1))
    passengers = data.get('passengers') or []
    contact = data.get('contact_number') or request.user.phone_number or ''

    if not contact:
        return Response({'error': 'Contact number is required'}, status=status.HTTP_400_BAD_REQUEST)
    if len(passengers) < passenger_count:
        return Response({'error': 'All passenger names are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            schedule = Schedule.objects.select_for_update().get(id=schedule_id, is_active=True)
            travel_date = datetime.strptime(data.get('travel_date') or data.get('trip_date'), '%Y-%m-%d').date()
            if not _run_day_matches(schedule.run_days, travel_date):
                return Response({'error': 'No service on this date'}, status=status.HTTP_400_BAD_REQUEST)

            taken = _seats_booked(schedule, travel_date)
            remaining = schedule.available_seats - taken
            if passenger_count > remaining:
                return Response(
                    {'error': 'Not enough seats — another passenger just booked. Please try again.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            trip = TripRequest.objects.create(
                user=request.user,
                trip_type='transfer',
                pickup_location=data.get('pickup_location') or schedule.route_from,
                destination=data.get('destination') or schedule.route_to,
                trip_date=travel_date,
                trip_time=schedule.departure_time,
                passenger_count=passenger_count,
                special_notes=data.get('special_notes', ''),
                preferred_currency='MVR',
                status='accepted',
            )

            total = schedule.price_per_seat * passenger_count
            quote = Quote.objects.create(
                trip_request=trip,
                operator=schedule.operator,
                boat=schedule.boat,
                amount=total,
                currency='MVR',
                pickup_time=schedule.departure_time,
                status='accepted',
                valid_until=timezone.now() + timedelta(days=7),
                bank_name='BML',
                account_number=PlatformSettings.get().bml_account,
                account_name='Samuga Travels',
            )

            ref = _generate_booking_ref()
            while Booking.objects.filter(booking_code=ref).exists():
                ref = _generate_booking_ref()

            booking = Booking.objects.create(
                trip_request=trip,
                selected_quote=quote,
                schedule=schedule,
                booking_code=ref,
                status='pending_payment',
            )

            for i, p in enumerate(passengers[:passenger_count]):
                Passenger.objects.create(
                    trip_request=trip,
                    name=p.get('name', ''),
                    nationality_id=p.get('nationality_id', p.get('nationality', '')),
                    order=i,
                )

            if contact and not request.user.phone_number:
                request.user.phone_number = contact
                request.user.save(update_fields=['phone_number'])

        return Response({
            'booking_ref': ref,
            'trip_id': str(trip.id),
            'total_amount': float(total),
            'currency': 'MVR',
            'status': 'pending_payment',
        }, status=status.HTTP_201_CREATED)
    except Schedule.DoesNotExist:
        return Response({'error': 'Schedule not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    trips = TripRequest.objects.filter(user=request.user).select_related('booking', 'payment').order_by('-created_at')
    return Response([_trip_to_booking_dict(t) for t in trips])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def invoice_detail(request, ref):
    try:
        booking = Booking.objects.select_related('trip_request', 'selected_quote', 'schedule').get(booking_code=ref)
    except Booking.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if booking.trip_request.user != request.user and not request.user.is_admin:
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    settings = PlatformSettings.get()
    trip = booking.trip_request
    quote = booking.selected_quote
    return Response({
        'booking_ref': ref,
        'total_amount': float(quote.amount if quote else 0),
        'currency': quote.currency if quote else 'MVR',
        'bml_account': settings.bml_account,
        'mib_account': settings.mib_account,
        'account_holder': 'Samuga Travels',
        'route': f"{trip.pickup_location} → {trip.destination}",
        'travel_date': str(trip.trip_date),
        'status': booking.status,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_slip(request, ref):
    try:
        booking = Booking.objects.select_related('trip_request', 'selected_quote').get(booking_code=ref)
    except Booking.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    trip = booking.trip_request
    if trip.user != request.user:
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    amount = booking.selected_quote.amount if booking.selected_quote else request.data.get('amount', 0)
    payment_data = {
        'trip_request': str(trip.id),
        'payment_method': request.data.get('payment_method', 'bml'),
        'amount': amount,
        'currency': request.data.get('currency', 'MVR'),
        'transaction_id': request.data.get('transaction_id', ''),
    }
    if request.FILES.get('payment_proof'):
        payment_data['payment_proof'] = request.FILES['payment_proof']
    elif request.FILES.get('slip'):
        payment_data['payment_proof'] = request.FILES['slip']

    from .serializers import PaymentSerializer
    serializer = PaymentSerializer(data=payment_data)
    if serializer.is_valid():
        serializer.save()
        trip.status = 'payment_pending'
        trip.save(update_fields=['status'])
        booking.status = 'pending_confirmation'
        booking.save(update_fields=['status'])
        return Response({'message': 'Payment slip uploaded', 'status': 'pending_confirmation'})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def booking_status(request, ref):
    try:
        booking = Booking.objects.select_related('trip_request').get(booking_code=ref)
    except Booking.DoesNotExist:
        trips = TripRequest.objects.filter(user=request.user)
        for t in trips:
            if str(t.id).startswith(ref[:8]):
                return Response(_trip_to_booking_dict(t))
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if booking.trip_request.user != request.user:
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
    data = _trip_to_booking_dict(booking.trip_request)
    data['trip_id'] = str(booking.trip_request_id)
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_boat_request(request):
    data = request.data
    ref = _generate_request_ref()
    while BoatRequest.objects.filter(request_ref=ref).exists():
        ref = _generate_request_ref()

    br = BoatRequest.objects.create(
        request_ref=ref,
        customer=request.user,
        route_from=data.get('route_from') or data.get('pickup_location', ''),
        route_to=data.get('route_to') or data.get('destination', ''),
        travel_date=data.get('travel_date') or data.get('trip_date'),
        preferred_time=data.get('preferred_time', 'Flexible'),
        passenger_count=int(data.get('passenger_count', 1)),
        trip_type='return' if str(data.get('trip_type', '')).lower() == 'return' else 'oneway',
        contact_number=data.get('contact_number', ''),
        pickup_jetty=data.get('pickup_jetty', ''),
        notes=data.get('notes') or data.get('special_notes', ''),
        status='open',
    )

    trip = TripRequest.objects.create(
        user=request.user,
        trip_type='transfer',
        pickup_location=br.route_from,
        destination=br.route_to,
        trip_date=br.travel_date,
        trip_time=dt_time(9, 0),
        passenger_count=br.passenger_count,
        special_notes=f"[{br.trip_type}] {br.notes}",
        preferred_currency='MVR',
        status='pending',
    )
    br.linked_trip = trip
    br.save(update_fields=['linked_trip'])

    return Response({'request_ref': ref, 'id': str(br.id), 'status': 'open'}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_boat_requests(request):
    reqs = BoatRequest.objects.filter(customer=request.user).order_by('-created_at')
    return Response([{
        'id': str(r.id),
        'request_ref': r.request_ref,
        'route_from': r.route_from,
        'route_to': r.route_to,
        'travel_date': str(r.travel_date),
        'passenger_count': r.passenger_count,
        'status': r.status,
        'trip_id': str(r.linked_trip_id) if r.linked_trip_id else None,
    } for r in reqs])


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    if request.method == 'GET':
        return Response(UserSerializer(request.user, context={'request': request}).data)
    user = request.user
    for field in ('first_name', 'last_name', 'phone_number', 'email'):
        if field in request.data:
            setattr(user, field, request.data[field])
    user.save()
    return Response(UserSerializer(user, context={'request': request}).data)


def handle_support_ask(request):
    message = (request.data.get('message') or '').strip()
    if not message:
        return Response({'reply': 'Please type a question about routes, bookings, tickets, or private boats.'})
    SupportMessage.objects.create(user=request.user, message=f'[Samuga Assist] {message}')
    reply = _assist_reply(message, request.user)
    if not reply or reply.strip().lower() == message.lower():
        reply = _fallback_assist_reply(message, request.user)
    SupportMessage.objects.create(user=request.user, message=reply, is_admin_reply=True)
    return Response({'reply': reply})


def handle_human_support(request):
    msg = request.data.get('message', 'Customer requested human support')
    SupportMessage.objects.create(user=request.user, message=f'[Human Support Request] {msg}')
    return Response({'reply': 'Support request sent. We will contact you on Telegram.', 'message': 'Support request sent. We will contact you on Telegram.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def support_ask(request):
    return handle_support_ask(request)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def support_human(request):
    return handle_human_support(request)


@api_view(['GET'])
@permission_classes([AllowAny])
def assist_settings(request):
    s = PlatformSettings.get()
    return Response({'greeting': s.assist_greeting, 'avatar_url': s.assist_avatar_url})


ISLAND_ALIASES = {
    'male': 'Malé City',
    'malé': 'Malé City',
    'mle': 'Malé City',
    'airport': 'Velana International Airport (Malé)',
    'via': 'Velana International Airport (Malé)',
    'hulhule': 'Velana International Airport (Malé)',
    'hulhumale': 'Hulhumalé',
    'hulhumalé': 'Hulhumalé',
    'maafushi': 'Maafushi Island',
    'thulusdhoo': 'Thulusdhoo Island',
    'guraidhoo': 'Guraidhoo Island',
    'dhiffushi': 'Dhiffushi Island',
    'rasdhoo': 'Rasdhoo Island',
    'ukulhas': 'Ukulhas Island',
    'fulidhoo': 'Fulidhoo Island',
    'dhigurah': 'Dhigurah Island',
    'addu': 'Addu City',
    'gan': 'Gan Island',
    'villingili': 'Villingili Ferry Terminal',
    'naifaru': 'Naifaru Island',
    'dharavandhoo': 'Dharavandhoo Island',
    'fuvahmulah': 'Fuvahmulah Island',
}


def _extract_islands(message: str):
    q = message.lower()
    found = []
    for alias, place in ISLAND_ALIASES.items():
        if re.search(rf'\b{re.escape(alias)}\b', q) and place not in found:
            found.append(place)
    for place in MALDIVES_PLACES:
        key = place.split('(')[0].replace('Island', '').replace('City', '').replace('Ferry Terminal', '').strip().lower()
        if len(key) >= 4 and key in q and place not in found:
            found.append(place)
    return found[:2]


def _route_assist_reply(message: str):
    q = message.lower()
    islands = _extract_islands(message)
    from_name = to_name = None
    m = re.search(r'(.+?)\s+(?:to|se|→|->)\s+(.+)', q, re.I)
    if m and len(islands) >= 2:
        from_name, to_name = islands[0], islands[1]
    elif len(islands) == 2:
        from_name, to_name = islands[0], islands[1]
    elif len(islands) == 1 and any(w in q for w in ('to ', 'from ', 'ferry', 'boat', 'route', 'jaana', 'jana')):
        to_name = islands[0]
        from_name = 'Malé City'

    if not from_name and not to_name:
        return None

    _ensure_schedules()
    travel_date = timezone.now().date()
    schedules = Schedule.objects.filter(is_active=True).select_related('operator', 'boat')
    if from_name:
        key = from_name.split()[0]
        schedules = schedules.filter(Q(route_from__icontains=key) | Q(sched_stops__icontains=key))
    if to_name:
        key = to_name.split()[0]
        schedules = schedules.filter(Q(route_to__icontains=key) | Q(sched_stops__icontains=key))

    lines = []
    for s in schedules[:4]:
        if not _run_day_matches(s.run_days, travel_date):
            continue
        taken = _seats_booked(s, travel_date)
        seats = max(0, s.available_seats - taken)
        lines.append(
            f"• {s.route_from} → {s.route_to} at {s.departure_time.strftime('%H:%M')} — "
            f"MVR {s.price_per_seat:.0f}/seat ({seats} seats), {s.operator.company_name}"
        )
    if lines:
        dest = to_name or from_name
        return (
            f"I found boats for {dest}:\n" + '\n'.join(lines)
            + '\n\nOpen Search, pick FROM/TO and a date, then tap Book this boat.'
        )
    dest = f'{from_name} to {to_name}' if from_name and to_name else (to_name or from_name)
    return (
        f'No public schedule is listed right now for {dest}. '
        'Use Search to check other dates, or Home → Private Hire for a private boat.'
    )


def _llm_assist_reply(message: str, user: User):
    gemini_key = os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', '')
    openai_key = os.environ.get('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', '')
    upcoming = TripRequest.objects.filter(
        user=user, status__in=['accepted', 'payment_pending', 'confirmed']
    ).count()
    system = (
        'You are Samuga Assist for SamugaTravels, a Maldives boat and ferry booking app. '
        'Answer in the same language the user used (English, Dhivehi, or Urdu/Roman Urdu). '
        'Keep replies under 80 words. Help with routes, seat bookings, payments (MVR bank transfer + slip), '
        'boarding QR tickets, and private boat hire. '
        f'The customer is {user.first_name or "a guest"} with {upcoming} active booking(s). '
        'App steps: Search tab → FROM/TO/date → Book this boat. Pay: My Trips → Active & Pending → Tap to Pay. '
        'Tickets: Upcoming → View Ticket. Private hire: Home → Private Hire. '
        'Never repeat the user message back as the answer.'
    )
    if gemini_key:
        body = json.dumps({
            'system_instruction': {'parts': [{'text': system}]},
            'contents': [{'parts': [{'text': message}]}],
            'generationConfig': {'temperature': 0.4, 'maxOutputTokens': 220},
        }).encode()
        req = urllib.request.Request(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
            text = (
                data.get('candidates', [{}])[0]
                .get('content', {})
                .get('parts', [{}])[0]
                .get('text', '')
                .strip()
            )
            if text and text.lower() != message.lower():
                return text
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, OSError):
            return None

    if openai_key:
        body = json.dumps({
            'model': 'gpt-4o-mini',
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': message},
            ],
            'max_tokens': 220,
            'temperature': 0.4,
        }).encode()
        req = urllib.request.Request(
            'https://api.openai.com/v1/chat/completions',
            data=body,
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {openai_key}'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
            text = (data.get('choices', [{}])[0].get('message', {}) or {}).get('content', '').strip()
            if text and text.lower() != message.lower():
                return text
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, OSError):
            return None
    return None


def _fallback_assist_reply(message: str, user: User) -> str:
    q = message.lower()
    upcoming = TripRequest.objects.filter(
        user=user, status__in=['accepted', 'payment_pending', 'confirmed']
    ).count()

    route_reply = _route_assist_reply(message)
    if route_reply:
        return route_reply

    if any(w in q for w in ('salam', 'salaam', 'hello', 'hi ', 'hey', 'assalam')):
        name = user.first_name or 'there'
        extra = f' You have {upcoming} active booking(s).' if upcoming else ''
        return f"Hi {name}! I'm Samuga Assist.{extra} Ask me about routes, bookings, payments, tickets, or private boats."

    if any(w in q for w in ('book', 'search', 'seat', 'reserve', 'booking')):
        return 'Use the Search tab → pick FROM and TO islands → choose a date → tap Book this boat. For a whole boat, go Home → Private Hire.'

    if any(w in q for w in ('pay', 'payment', 'slip', 'transfer', 'mvr', 'bank')):
        return 'Go to My Trips → Active & Pending → Tap to Pay. Transfer the exact MVR amount to the shown account, then upload your bank slip.'

    if any(w in q for w in ('ticket', 'qr', 'boarding', 'check in', 'check-in')):
        return 'Confirmed trips appear under My Trips → Upcoming. Tap View Ticket to show your boarding QR at the jetty.'

    if any(w in q for w in ('cancel', 'refund', 'change')):
        return 'For cancellations or refunds please tap Talk to Support so a human agent can help.'

    if any(w in q for w in ('private', 'hire', 'charter', 'whole boat', 'speedboat')):
        return 'For a private speedboat, open Home → Private Hire, enter your route, date, and passenger count. Operators will send quotes.'

    if any(w in q for w in ('price', 'cost', 'kitna', 'keemat', 'fare', 'how much')):
        return 'Seat prices depend on the route and boat. Search FROM/TO and a date to see live MVR fares. Private hire quotes come from operators after you submit a request.'

    if any(w in q for w in ('ferry', 'schedule', 'time', 'departure')):
        return 'Open Search or Ferries to see today’s departures, times, and seats. Tell me a route like “Male to Maafushi” and I will check it.'

    if upcoming:
        return f'You have {upcoming} active booking(s). I can help with payment, tickets, or finding another route. What do you need?'

    return (
        'I can help with searching routes, booking seats, payments, tickets, and private boat requests. '
        'Try “Male to Maafushi”, “how do I pay?”, or tap Talk to Support for a human.'
    )


def _assist_reply(message: str, user: User) -> str:
    llm = _llm_assist_reply(message, user)
    if llm:
        return llm
    return _fallback_assist_reply(message, user)
