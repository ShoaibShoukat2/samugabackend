"""
Run on PythonAnywhere:
  cd ~/samugabackend && python manage.py shell < debug_accepted.py
"""
from api.models import Quote, TripRequest, SpeedboatOperator

print("=== QUOTE STATUS BREAKDOWN ===")
for status in ['pending', 'accepted', 'rejected', 'expired']:
    count = Quote.objects.filter(status=status).count()
    print(f"  {status}: {count}")

print("\n=== TRIP STATUS BREAKDOWN ===")
for status in ['pending', 'quoted', 'accepted', 'payment_pending', 'confirmed', 'completed']:
    count = TripRequest.objects.filter(status=status).count()
    print(f"  {status}: {count}")

print("\n=== ACCEPTED QUOTES DETAIL ===")
for q in Quote.objects.filter(status='accepted').select_related('operator', 'trip_request__user'):
    print(f"  Quote {q.id}")
    print(f"    Operator: {q.operator.company_name if q.operator else 'None'}")
    print(f"    Trip: {q.trip_request.id} | status={q.trip_request.status}")
    print(f"    Customer: {q.trip_request.user.first_name} {q.trip_request.user.last_name}")
    print(f"    Amount: {q.currency} {q.amount}")

print("\n=== TRIPS WITH ACCEPTED STATUS ===")
for t in TripRequest.objects.filter(status__in=['accepted', 'payment_pending', 'confirmed']):
    aq = t.quotes.filter(status='accepted').first()
    print(f"  Trip {t.id} | status={t.status}")
    print(f"    Accepted quote: {aq.operator.company_name if aq and aq.operator else 'NONE'}")
