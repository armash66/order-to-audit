"""Durable sign-in attempt limits with the same response for every failed account."""
import hashlib
from datetime import timedelta
from sqlalchemy import text
from api.native import now


# Hash the account/address pair so the throttle table does not store usernames or IPs.
def attempt_key(username, address):
    value = f"{username.casefold()}|{address}"
    return hashlib.sha256(value.encode()).hexdigest()


def blocked(conn, key):
    until = conn.execute(
        text("SELECT blocked_until FROM factory_loginattempt WHERE key=:key"),
        {"key": key},
    ).scalar_one_or_none()
    return until is not None and until > now()


# Five failures in ten minutes block this account/address pair for ten minutes.
def failed(conn, key):
    instant = now()
    conn.execute(text("""INSERT INTO factory_loginattempt(key,failures,last_attempt,blocked_until)
        VALUES (:key,1,:instant,NULL)
        ON CONFLICT(key) DO UPDATE SET
        failures=CASE WHEN factory_loginattempt.last_attempt<:cutoff THEN 1
                      ELSE factory_loginattempt.failures+1 END,
        last_attempt=:instant,
        blocked_until=CASE WHEN factory_loginattempt.last_attempt<:cutoff THEN NULL
                           WHEN factory_loginattempt.failures+1>=5 THEN :until
                           ELSE factory_loginattempt.blocked_until END"""),
        {"key": key, "instant": instant, "cutoff": instant - timedelta(minutes=10),
         "until": instant + timedelta(minutes=10)})


def clear(conn, key):
    conn.execute(text("DELETE FROM factory_loginattempt WHERE key=:key"), {"key": key})
