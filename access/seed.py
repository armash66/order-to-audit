import os
from django.contrib.auth.models import User, Group
from django.db import transaction


# Existing credentials are never reset by container restarts or repeated seeding.
@transaction.atomic
def seed_logins():
    names = [("salesman_a","salesman"),("salesman_b","salesman"),("admin","admin"),("production","production"),("accountant","accountant"),("owner","owner")]
    for name, role in names:
        group,_=Group.objects.get_or_create(name=role)
        user,created=User.objects.get_or_create(username=name)
        if created or not user.has_usable_password():
            user.set_password(os.environ.get("DEMO_PASSWORD","DemoPass123!"))
            user.save(update_fields=["password"])
        user.groups.add(group)
