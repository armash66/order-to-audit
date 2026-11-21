"""Admin account provisioning and first-use password changes."""
import re
from sqlalchemy import select, update, text
from api import database
from api.native import authorize, audit, insert_row, now, required_integer, table
from api.sales.services import get_row
from api.seed import password_hash
from api.services import user_by_name, verify_password

ROLES = ("salesman", "admin", "production", "accountant", "owner")


def password_rule(password, username):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError("Use a password of 12 to 128 characters.")
    if username.casefold() in password.casefold() or password == "DemoPass123!":
        raise ValueError("Choose a password unrelated to the username or demo password.")


def accounts(user):
    authorize(user, ["admin"])
    with database.transaction() as conn:
        return [dict(row) for row in conn.execute(text("""SELECT u.id,u.username,u.first_name,
            u.email,u.is_active,g.name AS role,COALESCE(s.must_change_password,FALSE) AS must_change_password
            FROM auth_user u JOIN auth_user_groups ug ON ug.user_id=u.id
            JOIN auth_group g ON g.id=ug.group_id
            LEFT JOIN factory_accountsecurity s ON s.user_id=u.id
            WHERE u.username<>'benchmark-seed' ORDER BY u.username""")).mappings()]


# One role and a temporary password are set in one transaction; no role is self-assigned.
def create(data, user):
    authorize(user, ["admin"])
    if not isinstance(data["username"], str) or not isinstance(data["name"], str):
        raise ValueError("Username and name must be text.")
    username = data["username"].strip().lower()
    name = data["name"].strip()
    role = data["role"]
    password = data["temporary_password"]
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", username) or not 1 <= len(name) <= 150:
        raise ValueError("Use a unique lowercase username and a display name.")
    if role not in ROLES:
        raise ValueError("Choose one supported role.")
    password_rule(password, username)
    with database.transaction() as conn:
        if conn.execute(text("SELECT 1 FROM auth_user WHERE username=:name"), {"name": username}).first():
            raise ValueError("Username is already in use.")
        group = conn.execute(text("SELECT id FROM auth_group WHERE name=:name"), {"name": role}).scalar_one()
        identifier = insert_row(conn, "auth_user", username=username, first_name=name,
            last_name="", email="", password=password_hash(password),
            is_superuser=False, is_staff=False, is_active=True, date_joined=now(), last_login=None)
        insert_row(conn, "auth_user_groups", user_id=identifier, group_id=group)
        conn.execute(table(conn, "factory_accountsecurity").insert().values(
            user_id=identifier, must_change_password=True))
        audit(conn, user, "account.create", "auth.User", identifier, {},
              {"username": username, "role": role, "active": True})
        return identifier


# Disabling an account makes every existing token fail on its next request.
def set_active(data, user):
    authorize(user, ["admin"])
    identifier = required_integer(data["id"], 1)
    active = data["active"]
    if type(active) is not bool or identifier == user["id"]:
        raise ValueError("Cannot change your own account or use a non-boolean state.")
    with database.transaction() as conn:
        target = get_row(conn, "auth_user", identifier)
        if target["is_staff"] or target["username"] == "benchmark-seed":
            raise ValueError("Protected service account.")
        conn.execute(update(table(conn, "auth_user")).where(table(conn, "auth_user").c.id == identifier)
                     .values(is_active=active))
        audit(conn, user, "account.active", "auth.User", identifier,
              {"active": target["is_active"]}, {"active": active})
        return identifier


# Reset rotates the stored hash and forces a fresh password before work resumes.
def reset(data, user):
    authorize(user, ["admin"])
    identifier = required_integer(data["id"], 1)
    if identifier == user["id"]:
        raise ValueError("Use your own password-change form.")
    with database.transaction() as conn:
        target = get_row(conn, "auth_user", identifier)
        if target["is_staff"]:
            raise ValueError("Protected service account.")
        password = data["temporary_password"]
        password_rule(password, target["username"])
        if verify_password(password, target["password"]):
            raise ValueError("Choose a different temporary password.")
        users = table(conn, "auth_user")
        conn.execute(update(users).where(users.c.id == identifier).values(password=password_hash(password)))
        security = table(conn, "factory_accountsecurity")
        if conn.execute(select(security).where(security.c.user_id == identifier)).first():
            conn.execute(update(security).where(security.c.user_id == identifier)
                         .values(must_change_password=True))
        else:
            conn.execute(security.insert().values(user_id=identifier, must_change_password=True))
        audit(conn, user, "account.reset", "auth.User", identifier, {},
              {"must_change_password": True})
        return identifier


# A password change invalidates the old token because its hash is part of the signature version.
def change_password(data, user):
    password_rule(data["new_password"], user["username"])
    with database.transaction() as conn:
        target = get_row(conn, "auth_user", user["id"])
        if not verify_password(data["old_password"], target["password"]):
            raise ValueError("Current password is incorrect.")
        if verify_password(data["new_password"], target["password"]):
            raise ValueError("Choose a different password.")
        users = table(conn, "auth_user")
        conn.execute(update(users).where(users.c.id == user["id"])
                     .values(password=password_hash(data["new_password"])))
        security = table(conn, "factory_accountsecurity")
        conn.execute(update(security).where(security.c.user_id == user["id"])
                     .values(must_change_password=False))
        audit(conn, user, "account.password_change", "auth.User", user["id"], {},
              {"must_change_password": False})
        return user_by_name(conn, user["username"])
