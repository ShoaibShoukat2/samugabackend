"""
Run this on PythonAnywhere bash console to debug and fix login issues:
  python manage.py shell < debug_and_fix_login.py

This script:
1. Shows all users and their login state
2. Fixes user_type for operators
3. Fixes username mismatch (username must equal email for login to work)
"""
from api.models import User, SpeedboatOperator

print("=" * 60)
print("ALL USERS IN DATABASE")
print("=" * 60)
for u in User.objects.all():
    has_op = hasattr(u, 'operator_profile')
    print(f"""
Email     : {u.email}
Username  : {u.username}
user_type : {u.user_type}
is_active : {u.is_active}
has_pass  : {u.has_usable_password()}
is_operator_profile: {has_op}
username==email: {u.username == u.email}
""")

print("=" * 60)
print("FIXING ISSUES")
print("=" * 60)

fixed = 0
for u in User.objects.all():
    changed = False

    # Fix 1: username must match email for authenticate() to work
    if u.email and u.username != u.email:
        print(f"🔧 Fixing username for {u.email}: '{u.username}' → '{u.email}'")
        u.username = u.email
        changed = True

    # Fix 2: user_type must be 'operator' if they have an operator profile
    if hasattr(u, 'operator_profile') and u.user_type != 'operator':
        print(f"🔧 Fixing user_type for {u.email}: '{u.user_type}' → 'operator'")
        u.user_type = 'operator'
        changed = True

    if changed:
        u.save()
        fixed += 1
        print(f"  ✅ Saved")

print(f"\nTotal records fixed: {fixed}")

print("\n" + "=" * 60)
print("FINAL STATE")
print("=" * 60)
for u in User.objects.all():
    print(f"{u.email} | username={u.username} | type={u.user_type} | active={u.is_active} | has_pass={u.has_usable_password()}")
