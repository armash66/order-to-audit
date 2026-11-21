"""Idempotent section-five masters, opening document and demo accounts without Django."""

import os
import secrets
import hashlib
import base64
from sqlalchemy import select, text
from api import database
from api.native import table, insert_row, factory_lock, now
from api.inventory.services import post_receipt
from api.services import user_by_name


# Existing fixture edits are conflicts, never silently overwritten during startup.
def ensure(conn, name, lookup, values, defaults=None):
    target = table(conn, name)
    query = select(target)
    for field, value in lookup.items():
        query = query.where(target.c[field] == value)
    old = conn.execute(query).mappings().first()
    if old:
        if any(old[field] != value for field, value in values.items()):
            raise ValueError(f"Changed benchmark fixture: {name} {lookup}")
        return dict(old)
    identifier = insert_row(conn, name, **(defaults or {}), **lookup, **values)
    return dict(
        conn.execute(select(target).where(target.c.id == identifier)).mappings().one()
    )


def password_hash(password):
    salt = secrets.token_urlsafe(16)
    iterations = 1000000
    encoded = base64.b64encode(
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    ).decode()
    return f"pbkdf2_sha256${iterations}${salt}${encoded}"


# Credentials retain the existing compatible PBKDF2 format; usable passwords are never reset.
def seed_logins(conn):
    names = [
        ("salesman_a", "salesman"),
        ("salesman_b", "salesman"),
        ("admin", "admin"),
        ("production", "production"),
        ("accountant", "accountant"),
        ("owner", "owner"),
    ]
    defaults = {
        "is_superuser": False,
        "first_name": "",
        "last_name": "",
        "email": "",
        "is_staff": False,
        "is_active": True,
        "date_joined": now(),
        "last_login": None,
    }
    for username, role in names:
        group = ensure(conn, "auth_group", {"name": role}, {})
        users = table(conn, "auth_user")
        user = (
            conn.execute(select(users).where(users.c.username == username))
            .mappings()
            .first()
        )
        if user is None:
            identifier = insert_row(
                conn,
                "auth_user",
                username=username,
                password=password_hash(os.environ.get("DEMO_PASSWORD", "DemoPass123!")),
                **defaults,
            )
        else:
            identifier = user["id"]
            if not user["password"] or user["password"].startswith("!"):
                from sqlalchemy import update

                conn.execute(
                    update(users)
                    .where(users.c.id == identifier)
                    .values(
                        password=password_hash(
                            os.environ.get("DEMO_PASSWORD", "DemoPass123!")
                        )
                    )
                )
        ensure(
            conn,
            "auth_user_groups",
            {"user_id": identifier, "group_id": group["id"]},
            {},
        )


def seed_benchmark():
    with database.transaction() as conn:
        conn.execute(
            text(
                "INSERT INTO inventory_factorycontrol(id,last_sequence,tolerance_bps) VALUES (1,0,300) ON CONFLICT(id) DO NOTHING"
            )
        )
        factory_lock(conn)
        ensure(
            conn,
            "auth_user",
            {"username": "benchmark-seed"},
            {"is_staff": True, "is_active": True, "password": "!"},
            {
                "is_superuser": False,
                "first_name": "",
                "last_name": "",
                "email": "",
                "date_joined": now(),
                "last_login": None,
            },
        )
        actor = user_by_name(conn, "benchmark-seed")
        data = [
            ("FLOUR", "Flour", "raw", "g", 100000, 420000),
            ("OIL", "Cooking oil", "raw", "ml", 30000, 420000),
            ("SPICE", "Spice mix", "raw", "g", 5000, 100000),
            ("POUCH", "200 g pouch", "packaging", "piece", 500, 125000),
            ("CARTON", "Carton", "packaging", "piece", 30, 45000),
            ("MURUKKU200", "Murukku 200 g", "finished", "piece", 50, None),
        ]
        items = {}
        opening = []
        for code, name, category, unit, quantity, value in data:
            item = ensure(
                conn,
                "inventory_item",
                {"code": code},
                {"name": name, "category": category, "base_unit": unit},
            )
            items[code] = item
            opening.append(
                {"item": item["id"], "quantity": quantity, "value_paise": value}
            )
            for display, factor in (
                [("kg", 1000)] if unit == "g" else [("L", 1000)] if unit == "ml" else []
            ):
                ensure(
                    conn,
                    "inventory_unitconversion",
                    {"item_id": item["id"], "unit": display},
                    {"numerator": factor, "denominator": 1},
                )
        for unit, factor in [("packet", 1), ("carton", 20)]:
            ensure(
                conn,
                "inventory_unitconversion",
                {"item_id": items["MURUKKU200"]["id"], "unit": unit},
                {"numerator": factor, "denominator": 1},
            )
        sku = ensure(
            conn,
            "inventory_sku",
            {"item_id": items["MURUKKU200"]["id"]},
            {"pack_size_g": 200, "price_paise": 5000, "hsn": "99999999"},
        )
        recipe = ensure(
            conn, "inventory_recipe", {"code": "MURUKKU200-RECIPE", "version": 1}, {}
        )
        bom = ensure(
            conn,
            "inventory_bom",
            {"sku_id": sku["id"], "version": 1},
            {"expected_packets": 200, "recipe_id": recipe["id"]},
        )
        for code, quantity in [
            ("FLOUR", 40000),
            ("OIL", 10000),
            ("SPICE", 1200),
            ("POUCH", 200),
            ("CARTON", 10),
        ]:
            raw = items[code]["category"] == "raw"
            ensure(
                conn,
                "inventory_recipeline" if raw else "inventory_bomline",
                {
                    "recipe_id" if raw else "bom_id": (
                        recipe["id"] if raw else bom["id"]
                    ),
                    "item_id": items[code]["id"],
                },
                {"quantity": quantity},
            )
        ensure(
            conn,
            "inventory_supplier",
            {"code": "FLOUR-SUPPLIER"},
            {"name": "Demo Flour Supplier"},
        )
        for code, name, state, gstin in [
            ("A", "Demo Retailer A", "33", "33BBBBB0000B1Z0"),
            ("B", "Demo Distributor B", "29", "29CCCCC0000C1Z0"),
        ]:
            ensure(
                conn,
                "inventory_customer",
                {"code": code},
                {"name": name, "state_code": state, "gstin": gstin},
            )
        identifier = post_receipt(
            {"date": "2026-11-19", "lines": opening},
            actor,
            "benchmark-opening-v1",
            kind="opening",
        )
        seed_logins(conn)
        return identifier
