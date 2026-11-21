import hashlib
import os
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from .database import connection
from . import database
from .services import user_by_name, verify_password, stock_summary, item_ledger

app = FastAPI(title="Order-to-Audit API", version="0.1.0")
signer = URLSafeTimedSerializer(os.environ["API_SECRET_KEY"], salt="ota-access-v1")
bearer = HTTPBearer(auto_error=False)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=1024)


def public_user(user):
    return {key: user[key] for key in ("username", "roles", "is_staff", "must_change_password")}


def session(user):
    token = signer.dumps({"username": user["username"],
                          "version": hashlib.sha256(user["password"].encode()).hexdigest()})
    return {"access_token": token, "user": public_user(user)}


# Reload account state on every request; password changes invalidate existing tokens.
def authenticated_user(
    auth: HTTPAuthorizationCredentials = Depends(bearer), conn=Depends(connection)
):
    try:
        if not auth:
            raise ValueError()
        payload = signer.loads(auth.credentials, max_age=3600)
        user = user_by_name(conn, payload["username"])
        if (
            not user
            or payload["version"]
            != hashlib.sha256(user["password"].encode()).hexdigest()
        ):
            raise ValueError()
        return user
    except (BadSignature, ValueError, KeyError, TypeError):
        raise HTTPException(
            401, "Sign in again.", headers={"WWW-Authenticate": "Bearer"}
        )


def current_user(user=Depends(authenticated_user)):
    if user["must_change_password"]:
        raise HTTPException(403, "Change your temporary password before continuing.")
    return user


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def login(body: Login, request: Request):
    from api.security.services import attempt_key, blocked, failed, clear

    address = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    key = attempt_key(body.username, address)
    with database.transaction() as conn:
        if blocked(conn, key):
            user = None
        else:
            user = user_by_name(conn, body.username)
            if user and verify_password(body.password, user["password"]):
                clear(conn, key)
            else:
                user = None
                failed(conn, key)
    if not user:
        raise HTTPException(401, "Incorrect username or password.")
    return session(user)


class PasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=128)


@app.post("/api/change-password")
def change_password(body: PasswordChange, user=Depends(authenticated_user)):
    from api.accounts.services import change_password as change

    try:
        return session(change(body.model_dump(), user))
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(400, str(error))


@app.get("/api/me")
def me(user=Depends(authenticated_user)):
    return public_user(user)


@app.get("/api/stock")
def stock(user=Depends(current_user), conn=Depends(connection)):
    return stock_summary(conn, user)


@app.get("/api/stock/{code}/ledger")
def ledger(code: str, user=Depends(current_user), conn=Depends(connection)):
    return item_ledger(conn, user, code)


# Mount workflow routes after authentication dependencies are defined.
from .workflows import router

app.include_router(router)
