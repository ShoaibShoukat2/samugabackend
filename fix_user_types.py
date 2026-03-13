#!/usr/bin/env python
"""
Fix user_type for existing users
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import User, SpeedboatOperator

print("🔧 Fixing user types...")
print("-" * 50)

# Fix operators
operators = SpeedboatOperator.objects.all()
print(f"Found {operators.count()} operator profiles")

for operator in operators:
    user = operator.user
    if user.user_type != 'operator':
        print(f"Fixing operator: {user.email}")
        print(f"  Old user_type: {user.user_type}")
        user.user_type = 'operator'
        user.save()
        print(f"  New user_type: operator ✅")
    else:
        print(f"Operator {user.email} already correct ✅")

print()

# Fix regular users (set to customer if null)
regular_users = User.objects.filter(user_type__isnull=True)
print(f"Found {regular_users.count()} users with null user_type")

for user in regular_users:
    print(f"Fixing user: {user.email}")
    user.user_type = 'customer'
    user.save()
    print(f"  Set user_type: customer ✅")

print()

# Fix empty string user_types
empty_users = User.objects.filter(user_type='')
print(f"Found {empty_users.count()} users with empty user_type")

for user in empty_users:
    print(f"Fixing user: {user.email}")
    user.user_type = 'customer'
    user.save()
    print(f"  Set user_type: customer ✅")

print("-" * 50)
print("✅ All user types fixed!")

# Show summary
total_users = User.objects.count()
customers = User.objects.filter(user_type='customer').count()
operators = User.objects.filter(user_type='operator').count()
admins = User.objects.filter(user_type='admin').count()

print(f"\n📊 Summary:")
print(f"Total users: {total_users}")
print(f"Customers: {customers}")
print(f"Operators: {operators}")
print(f"Admins: {admins}")