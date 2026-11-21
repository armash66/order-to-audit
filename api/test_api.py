import os
from fastapi.testclient import TestClient
from sqlalchemy import text
from api.main import app, signer
from api.database import engine
from api.services import verify_password

client = TestClient(app)


def token(username):
    response = client.post(
        "/api/login",
        json={
            "username": username,
            "password": os.environ.get("DEMO_PASSWORD", "DemoPass123!"),
        },
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_login_and_permissions():
    assert client.get("/api/stock").status_code == 401
    assert (
        client.get(
            "/api/stock", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/login", json={"username": "admin", "password": "wrong"}
        ).status_code
        == 401
    )
    assert client.get("/api/stock", headers=token("salesman_a")).status_code == 403
    for role in ("admin", "production", "accountant", "owner"):
        assert client.get("/api/stock", headers=token(role)).status_code == 200


def test_summary_and_ledger_reconcile_to_database():
    headers = token("accountant")
    rows = client.get("/api/stock", headers=headers).json()
    assert rows
    with engine.connect() as conn:
        expected = dict(
            conn.execute(
                text(
                    "SELECT i.code, COALESCE(SUM(m.quantity),0) FROM inventory_item i LEFT JOIN inventory_stockmovement m ON m.item_id=i.id GROUP BY i.code"
                )
            ).all()
        )
    for row in rows:
        assert isinstance(row["quantity"], str)
        assert int(row["quantity"]) == expected[row["code"]]
        ledger = client.get(
            "/api/stock/" + row["code"] + "/ledger", headers=headers
        ).json()
        assert sum(int(m["quantity"]) for m in ledger["movements"]) == int(
            row["quantity"]
        )
    assert (
        client.get("/api/stock/DOES-NOT-EXIST/ledger", headers=headers).status_code
        == 404
    )


def test_token_version_and_no_mutations():
    bad = signer.dumps({"username": "admin", "version": "old-password"})
    assert (
        client.get("/api/me", headers={"Authorization": "Bearer " + bad}).status_code
        == 401
    )
    assert client.post("/api/stock", headers=token("admin"), json={}).status_code == 405
    assert not verify_password("anything", "!disabled")
