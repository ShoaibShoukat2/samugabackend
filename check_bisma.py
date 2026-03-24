#!/usr/bin/env python
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import User

print("=== Searching for bisma ===")
users = User.objects.filter(email__icontains='bisma')
for u in users:
    print(f"  email: '{u.email}'")
    print(f"  username: '{u.username}'")
    print(f"  user_type: {u.user_type}")
    print(f"  is_active: {u.is_active}")
    print(f"  has_usable_password: {u.has_usable_password()}")
    print(f"  has_operator_profile: {hasattr(u, 'operator_profile')}")
    print()

if not users.exists():
    print("❌ NO USER FOUND with bisma in email")
    print("\n=== All users in DB ===")
    for u in User.objects.all():
        print(f"  {u.email} | {u.username} | {u.user_type}")
