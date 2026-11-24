# HTTP API reference

Base URL for local Compose: `http://localhost:8000`. This documents the active FastAPI runtime. All business writes call service functions; the browser is not an authorization boundary. Routes live in `api/main.py` and `api/workflows.py`.

## Authentication and numbers

`POST /api/login` accepts `{"username":"admin","password":"DemoPass123!"}` and returns `{"access_token":"...","user":{"username":"admin","roles":["admin"],"is_staff":false,"must_change_password":false}}`. The exact role/staff values depend on the account. Send `Authorization: Bearer TOKEN` on protected requests. Tokens expire after one hour; password changes and disabling invalidate them. Do not put tokens in URLs or persistent browser storage.

`GET /api/me` returns the current public user. `POST /api/change-password` accepts `old_password` and `new_password`, returning a fresh session. A temporary-password account must use this route before accessing ordinary workspace endpoints. Passwords are 12–128 characters, unrelated to the username and different from the published demo password.

Workspace responses serialize business integers as decimal strings, including IDs, paise and base quantities. The separate `/api/stock` and `/api/stock/{code}/ledger` endpoints return IDs as JSON integers, with quantities and known values as decimal strings; unknown values are null. Workspace ratios are `{"numerator":"146375","denominator":"47"}`; booleans remain JSON booleans. Money inputs are integer paise, never rupee floats. Quantities are base-unit integers or measured objects such as `{"quantity":"10.5","unit":"L"}` where supported. Date inputs use `YYYY-MM-DD`.

## Reads

All paths below start with `/api`.

| Method/path | Access and response |
| --- | --- |
| `GET /health` | Public health response `{"status":"ok"}` |
| `GET /stock` | Admin, production, accountant, owner; ledger-derived item balances |
| `GET /stock/{code}/ledger` | Same roles; item and source-linked movements |
| `GET /workspace/catalog` | All five roles; permitted masters, user ID, factory date and report names |
| `GET /workspace/accounts` | Admin only; staff, role, active and must-change-password state |
| `GET /workspace/orders` and `/orders/{id}` | Admin, salesman, accountant, owner; salesman restricted to own orders |
| `GET /workspace/production` and `/production/{id}` | Admin/production; runs, standards, consumption, yield and cost |
| `GET /workspace/batches`, `/recall/{lot_id}`, `/sources/{posting_id}`, `/audit` | Factory/reviewer roles; lot balances/trace, posting source or latest audit entries |
| `GET /workspace/prices/{customer_id}` | Admin/salesman; effective SKU prices |
| `GET /workspace/visits` | Sales/reviewer roles; salesman sees own visits |
| `GET /workspace/dashboard` | Admin/accountant/owner; operational summary |
| `GET /workspace/translations` | Authenticated catalogue; business records are not translated by the API |
| `GET /workspace/invoices/{id}/pdf` | Invoice access checked, including salesman ownership; PDF attachment |
| `GET /workspace/reports/{kind}?start=2026-11-01&end=2026-11-30&format=csv` | Admin/accountant/owner; salesman limited to own customer sales. Format `json`, `csv` or `pdf`; `tally` returns ZIP |

Report kinds: `sales`, `customers`, `products`, `gst`, `purchases`, `stock`, `ledger`, `production`, `collections`, `ageing`, `customer_ageing`. JSON tables have `title`, `headers` and `rows`. Ageing uses `end` as its as-of date; stock uses posting dates; commercial registers use document dates. Export figures retain the documented exercise limitations.

## Command envelope and retry rules

`POST /api/workspace/commands` accepts:

```json
{
  "action": "receipt",
  "request_key": "client-generated-unique-key",
  "data": {
    "date": "2026-11-19",
    "supplier": "1",
    "lines": [{"item":"1","quantity":"60","unit":"kg","value_paise":"270000"}]
  }
}
```

Resolve IDs from the catalogue; examples do not promise ID 1 identifies a particular master. Most successful commands return `{"ok":true,"id":"123"}`. The ID belongs to the action's resulting document and is not always an order ID. Mock fiscal commands return their explicitly MOCK request/response instead.

The key is required, 1–100 characters. Keep it with the pending request and reuse the same key and data after a timeout. Stock posting, run events, order submission, payments and append-only notes compare existing request/document identity and content inside their transaction. Changed content on an existing key fails. Measured quantities normalize before comparison: 60 kg equals 60000 g.

Not every edit is request-key idempotent: master/account creation uses unique codes/usernames; draft edits, settings and access changes use current state and audit. After an uncertain response for these actions, read the current record before resubmitting. Never issue a new key merely to bypass a business rejection.

## Sales commands

| Action | Required data in addition to optional `date` | Access / effect |
| --- | --- | --- |
| `order.create` | `customer`, `quantities` keyed by SKU ID | Admin/salesman; submit, no reservation |
| `order.approve` | `id` (order) | Admin; recheck available stock and reserve |
| `order.reject` | `id`, `reason` | Admin; pre-invoice rejection releases reservation |
| `order.edit` | `id`, `lines` keyed by order-line ID, each `[quantity, price_paise]` | Admin; permitted draft/pre-invoice edits audited |
| `order.invoice` | `id`; optional boolean `draft` | Admin; default posts FY-numbered invoice, no stock movement; draft consumes no number |
| `order.edit_invoice` | `id` (order), `date` | Admin; change draft invoice date with audit |
| `order.dispatch` | `id`; optional `quantities` keyed by item ID | Admin; omitted map dispatches remaining; explicit map is partial dispatch |
| `order.payment` | `id`, `amount_paise` | Admin; allocate to that invoice, cannot exceed outstanding |
| `order.credit` | `id`, `reason` | Admin; full unpaid/undispatched cancellation only |
| `order.return` | `id`, `quantities` keyed by item ID, `reason` | Admin; bounded resalable returns and original-value/tax credit |

For example, submit `{"customer":"1","quantities":{"1":{"quantity":"2","unit":"carton"}},"date":"2026-11-19"}`. Carton factors belong to the SKU. This does not issue packaging material again. Sales tax is the exercise's 5%; state 33 gives CGST/SGST and other states IGST. Invalid state transitions leave no writes.

## Production and stock commands

| Action | Data | Access |
| --- | --- | --- |
| `receipt` | `supplier`, `date`, `lines:[{item,quantity,unit?,value_paise}]`; optional `lots` keyed by item code with `code`/`expiry` | Admin/production |
| `production.create` | `bom`, integer `batches`, `date`, optional `expiry` | Admin/production |
| `production.issue` | `id` (run), `actual` keyed by raw item code | Admin/production |
| `production.complete` | `id`, `actual` packaging totals, `damaged` subset, `good_packets` | Admin/production |
| `production.overhead` | `id`, `label`, `amount_paise`, `date` | Admin/production |
| `production.edit` | `id`, integer `batches` | Admin/production; draft only, scales snapshotted standards and expected output, audited |
| `tolerance` | `basis_points` | Admin; 300 is 3%; strict greater-than, retroactive alerts |

Raw issue example:

```json
{
  "action":"production.issue", "request_key":"run-17-issue",
  "data":{"id":"17","actual":{
    "FLOUR":{"quantity":"40","unit":"kg"},
    "OIL":{"quantity":"10.5","unit":"L"},
    "SPICE":{"quantity":"1.2","unit":"kg"}
  }}
}
```

Completion uses `{"id":"17","actual":{"POUCH":"194","CARTON":"9"},"damaged":{"POUCH":"6"},"good_packets":"188"}`. Packaging totals already include damage. All snapshot inputs must be represented, including zero usage. Fractional base units, incompatible units and negative stock fail. Admin corrections in `api/inventory/corrections.py` use `adjustment` with `item`, signed nonzero base `quantity`, `reason`, `date`, and optional `value_paise` for positive receipts; or `production.reverse` with run `id`, `reason`, `date`. Never edit movements directly. Reversal dependency restrictions are in [assumptions](assumptions.md).

## Staff and masters

All require admin access. `account.create` accepts `name`, lowercase `username`, `role`, `temporary_password`. Roles are `salesman`, `admin`, `production`, `accountant`, `owner`. `account.active` accepts `id` and a JSON boolean `active`; `account.reset` accepts `id`, `temporary_password`. Self-disabling is rejected. Credentials are not included in audit payloads.

| Action | Data |
| --- | --- |
| `master.customer` | `code`, `name`, `state_code`, `gstin` (15 characters matching state prefix) |
| `master.supplier` | `code`, `name` |
| `master.item` | `code`, `name`, `category` (`raw`/`packaging`), `base_unit` (`g`/`ml`/`piece`) |
| `master.product` | `code`, `name`, `pack_size_g`, `price_paise`, `hsn`, `carton_size` |
| `master.bom` | `sku`, `expected_packets`, `packaging` item-ID quantity map; either shared `recipe` ID or a `raw` item-ID quantity map |

These create records, not stock. New BOMs create versions; existing run standards stay frozen. Master codes/usernames are unique. Public self-registration and self-assigned privileged roles are not offered.

## Optional workflows

`POST /api/workspace/offline/sync` accepts `request_key`, `user_id`, `customer`, `quantities` (SKU IDs to packet quantities), `date`. The signed-in identity must match `user_id`; server pricing is authoritative. Success returns `{"id":"123"}`. Keep queued data until success.

Other command actions: `price` (`customer`, `sku`, `price_paise`, `label`, admin), `reorder` (`item`, `minimum`, admin), `quality` (`lot`, `status`: held/released, `reason`, admin/production), `run.loss_note` (`run`, `reason`, optional `note`, admin/production), `collection.followup` (`invoice`, `note`, `next_contact`, admin).

`visit` is admin/salesman: `customer`, `route`, optional `note`, optional paired decimal-string `latitude`/`longitude` and explicit boolean `consent`. Coordinates require consent; a non-GPS visit does not. `mock` is admin: `invoice`, `kind` (`e_invoice`/`e_waybill`), optional integer `distance` (1–10000) and `vehicle`. Fiscal responses are local MOCK data. See [extended features](extended-features.md) for limits.

## Errors and examples

| HTTP status | Meaning / client action |
| --- | --- |
| 400 | Domain/input failure, such as incompatible unit, insufficient stock or changed retry content; show `detail`, correct/review input |
| 401 | Missing/invalid/expired session or invalid login; sign in again |
| 403 | Role/ownership denial, or temporary password change required |
| 404 | Missing resource on routes that explicitly return 404; some service lookups use 400 |
| 409 | Database uniqueness/conflict translated by workspace transport; read current record |
| 422 | FastAPI validation of typed request fields and query parameters; `detail` is a list of validation errors. Action-specific command data, including its date, is validated inside the command handler and generally returns 400 instead. |

Example error: `{"detail":"Unit is not valid for this item."}`. Do not assume all failures use 409 or that a network timeout means rollback. Retry only with the original immutable posting payload/key. The service tests in `api/tests.py` contain executable examples for all nine benchmark steps, permissions, tax rounding, edits, retries and optional workflows.

FastAPI's generated OpenAPI document is internal at `/openapi.json`; the nginx frontend only forwards `/api/`. To inspect the exact route schema locally, run `docker compose exec -T api python -c "import json; from api.main import app; print(json.dumps(app.openapi(), indent=2))"`. The generic command envelope needs the action-specific tables above; generated OpenAPI alone cannot describe its `data` payloads.
