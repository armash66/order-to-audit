import base64
import hashlib
import hmac
from fastapi import HTTPException
from sqlalchemy import text


# Verify the existing Django PBKDF2 format without importing Django or changing hashes.
def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = base64.b64encode(
            hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), int(iterations)
            )
        ).decode()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def user_by_name(conn, username):
    user = (
        conn.execute(
            text(
                "SELECT id, username, password, is_active, is_staff FROM auth_user WHERE username=:name"
            ),
            {"name": username},
        )
        .mappings()
        .first()
    )
    if not user or not user["is_active"]:
        return None
    roles = (
        conn.execute(
            text(
                "SELECT g.name FROM auth_group g JOIN auth_user_groups ug ON ug.group_id=g.id WHERE ug.user_id=:id"
            ),
            {"id": user["id"]},
        )
        .scalars()
        .all()
    )
    return dict(user, roles=roles)


def require_stock(user):
    if not user["is_staff"] and not set(user["roles"]) & {
        "admin",
        "production",
        "accountant",
        "owner",
    }:
        raise HTTPException(403, "Your role cannot access stock.")


# Serialize base units and paise as decimal strings to preserve bigint precision in JavaScript.
def stock_summary(conn, user):
    require_stock(user)
    rows = conn.execute(
        text(
            """SELECT i.id, i.code, i.name, i.category, i.base_unit,
        COALESCE(SUM(m.quantity),0)::text AS quantity,
        CASE WHEN COUNT(m.id) FILTER (WHERE m.value_paise IS NULL)>0 THEN NULL
             ELSE COALESCE(SUM(m.value_paise),0)::text END AS value_paise
        FROM inventory_item i LEFT JOIN inventory_stockmovement m ON m.item_id=i.id
        GROUP BY i.id ORDER BY i.category, i.code"""
        )
    ).mappings()
    return [dict(row) for row in rows]


def item_ledger(conn, user, code):
    require_stock(user)
    item = (
        conn.execute(
            text(
                "SELECT id, code, name, base_unit FROM inventory_item WHERE code=:code"
            ),
            {"code": code},
        )
        .mappings()
        .first()
    )
    if not item:
        raise HTTPException(404, "Item not found.")
    rows = conn.execute(
        text(
            """SELECT m.id, m.posting_id, m.quantity::text AS quantity,
        m.value_paise::text AS value_paise FROM inventory_stockmovement m
        WHERE m.item_id=:id ORDER BY m.posting_id, m.id"""
        ),
        {"id": item["id"]},
    ).mappings()
    return {"item": dict(item), "movements": [dict(row) for row in rows]}
