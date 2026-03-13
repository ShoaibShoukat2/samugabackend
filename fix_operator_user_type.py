#!/usr/bin/env python
"""
Quick script to fix user_type for operators
Run this if operator users are showing as 'customer'
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import User, SpeedboatOperator

# Find all users who have operator profiles but user_type is not 'operator'
operators = SpeedboatOperator.objects.all()

print(f"Found {operators.count()} operator profiles")
print("-" * 50)

fixed_count = 0
for operator in operators:
    user = operator.user
    if user.user_type != 'operator':
        print(f"Fixing user: {user.email}")
        print(f"  Old user_type: {user.user_type}")
        user.user_type = 'operator'
        user.save()
        print(f"  New user_type: operator ✅")
        fixed_count += 1
    else:
        print(f"User {user.email} already has correct user_type ✅")

print("-" * 50)
print(f"Fixed {fixed_count} users")
print("Done!")
