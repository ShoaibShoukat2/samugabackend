"""
Run this on PythonAnywhere to fix operators whose user_type is still 'customer':
  python manage.py shell < fix_operator_user_types.py
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

from api.models import User, SpeedboatOperator

print("=== Fixing operator user_types ===")

# Find all users who have an operator_profile but wrong user_type
operators = SpeedboatOperator.objects.select_related('user').all()
fixed = 0

for op in operators:
    u = op.user
    print(f"Operator: {u.email} | current user_type: {u.user_type} | has_password: {u.has_usable_password()}")
    if u.user_type != 'operator':
        u.user_type = 'operator'
        u.save()
        print(f"  ✅ Fixed: {u.email} → operator")
        fixed += 1

print(f"\nTotal fixed: {fixed}")
print("\n=== All operators after fix ===")
for op in SpeedboatOperator.objects.select_related('user').all():
    u = op.user
    print(f"  {u.email} | user_type: {u.user_type} | active: {u.is_active} | has_password: {u.has_usable_password()}")
