import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import User

# Create admin user
email = "admin@samugatravels.com"
password = "admin123"

try:
    user = User.objects.get(email=email)
    print(f"✅ Admin user already exists: {email}")
except User.DoesNotExist:
    user = User.objects.create_user(
        username="admin",
        email=email,
        password=password,
        first_name="Admin",
        last_name="User",
        is_admin=True,
        is_staff=True,
        is_superuser=True
    )
    print(f"✅ Admin user created successfully!")
    print(f"   Email: {email}")
    print(f"   Password: {password}")
    print(f"\n🌐 Access admin panel at: http://localhost:8000/api/admin-panel/login/")
