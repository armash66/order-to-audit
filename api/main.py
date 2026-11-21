import hashlib
import os
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from .database import connection
from .services import user_by_name, verify_password, stock_summary, item_ledger

app = FastAPI(title="Order-to-Audit API", version="0.1.0")
signer = URLSafeTimedSerializer(os.environ["API_SECRET_KEY"], salt="ota-access-v1")
bearer = HTTPBearer(auto_error=False)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=1024)


def public_user(user):
    return {key: user[key] for key in ("username", "roles", "is_staff")}


# Reload account state on every request; password changes invalidate existing tokens.
def current_user(
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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def login(body: Login, conn=Depends(connection)):
    user = user_by_name(conn, body.username)
    if not user or not verify_password(body.password, user["password"]):
        raise HTTPException(401, "Incorrect username or password.")
    token = signer.dumps(
        {
            "username": user["username"],
            "version": hashlib.sha256(user["password"].encode()).hexdigest(),
        }
    )
    return {"access_token": token, "user": public_user(user)}


@app.get("/api/me")
def me(user=Depends(current_user)):
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
