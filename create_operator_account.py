"""
Run this on PythonAnywhere to create the operator account.
Usage:
  cd ~/samugabackend
  python create_operator_account.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import User, SpeedboatOperator, OperatorSubscription
from django.utils import timezone
from datetime import date

OPERATOR_EMAIL    = 'bisma@gmail.com'
OPERATOR_PASSWORD = 'bisma123'
FIRST_NAME        = 'Bisma'
LAST_NAME         = 'Operator'
COMPANY_NAME      = 'Bisma Travels'
SERVICE_ISLANDS   = 'Male, Hulhumale'

print(f"\n🔍 Checking: {OPERATOR_EMAIL}")

user = User.objects.filter(email__iexact=OPERATOR_EMAIL).first()

if user:
    print(f"✅ User exists: {user.email} | type: {user.user_type}")
    user.user_type = 'operator'
    user.set_password(OPERATOR_PASSWORD)
    user.save()
    print("🔧 Fixed user_type + password reset")
else:
    print("➕ Creating user...")
    user = User(
        email=OPERATOR_EMAIL,
        username=OPERATOR_EMAIL,
        first_name=FIRST_NAME,
        last_name=LAST_NAME,
        user_type='operator',
        is_active=True,
    )
    user.set_password(OPERATOR_PASSWORD)
    user.save()
    print(f"✅ User created: {user.email}")

# Operator profile
if hasattr(user, 'operator_profile'):
    operator = user.operator_profile
    print(f"✅ Operator profile: {operator.company_name} | {operator.verification_status} | {operator.subscription_status}")
else:
    print("➕ Creating operator profile...")
    operator = SpeedboatOperator.objects.create(
        user=user,
        company_name=COMPANY_NAME,
        contact_person=f"{FIRST_NAME} {LAST_NAME}",
        phone_number='0000000000',
        email=OPERATOR_EMAIL,
        service_islands=SERVICE_ISLANDS,
        verification_status='verified',
        subscription_status='active',
    )
    print(f"✅ Operator profile created: {operator.company_name}")

# Active subscription
try:
    from dateutil.relativedelta import relativedelta
    active_sub = operator.subscriptions.filter(end_date__gte=date.today()).first()
    if not active_sub:
        today = date.today()
        OperatorSubscription.objects.create(
            operator=operator,
            plan='basic',
            amount=0,
            start_date=today,
            end_date=today + relativedelta(months=1),
            payment_status='paid',
            paid_at=timezone.now(),
        )
        operator.subscription_status = 'active'
        operator.save()
        print("✅ Free 1-month subscription granted")
    else:
        print(f"✅ Subscription active until: {active_sub.end_date}")
except Exception as e:
    print(f"⚠️  Subscription step skipped: {e}")

print(f"\n🎉 Done! Login with:")
print(f"   Email:    {OPERATOR_EMAIL}")
print(f"   Password: {OPERATOR_PASSWORD}")
print(f"   Type:     operator\n")
