import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agawo_junior.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = 'admin'
password = 'YourSecurePassword123'  # <-- Change this to your desired password!

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email='', password=password)
    print("Superuser created successfully online!")
else:
    print("Superuser already exists!")
