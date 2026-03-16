from api.models import TripRequest, Quote, SpeedboatOperator, User

print("=== ALL QUOTES ===")
for q in Quote.objects.select_related('trip_request__user', 'operator').all():
    print(f"Quote ID : {q.id}")
    print(f"  Status : {q.status}")
    print(f"  Amount : {q.currency} {q.amount}")
    print(f"  Operator: {q.operator.company_name if q.operator else 'None'}")
    print(f"  Trip ID : {q.trip_request.id}")
    print(f"  Trip status: {q.trip_request.status}")
    print(f"  Customer: {q.trip_request.user.email}")
    print()

print("=== TRIPS WITH ACCEPTED STATUS ===")
for t in TripRequest.objects.filter(status__in=['accepted','payment_pending','confirmed','completed']):
    print(f"Trip: {t.id} | status: {t.status} | customer: {t.user.email}")
    for q in t.quotes.all():
        print(f"  Quote: {q.id} | status: {q.status} | operator: {q.operator.company_name if q.operator else 'None'}")
    print()

print("=== ALL OPERATORS ===")
for op in SpeedboatOperator.objects.all():
    print(f"Operator: {op.company_name} | verified: {op.verification_status} | sub: {op.subscription_status}")
    print(f"  Quotes count: {op.quotes.count()} | Accepted: {op.quotes.filter(status='accepted').count()}")
