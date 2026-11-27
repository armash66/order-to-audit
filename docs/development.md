# Development and testing

[Documentation](README.md)

## Runtime

Run `docker compose up --build -d --wait`. The three runtime services are frontend (nginx), API (FastAPI) and PostgreSQL. Only the frontend publishes a localhost port. Optional environment settings are in [the example file](../.env.example).

```sh
docker compose ps
docker compose logs --tail 100 api
docker compose exec api python -m alembic current
docker compose exec api python -m api.cli reconcile
docker compose exec api python -m api.cli pdf-smoke
```

## Tests

The regression suite creates a temporary test database:

```sh
docker compose --profile test run --build --rm tests
```

Use a separate Compose project for native tests. Choose an unused project name so its volume starts empty. Starting only db/api avoids occupying another browser port.

```sh
docker compose -p ota-validation up --build -d --wait db api
docker compose -p ota-validation exec api python -m pytest api/test_api.py api/test_native.py api/test_units.py -q -p no:cacheprovider
docker compose -p ota-validation exec api python -m api.cli benchmark
docker compose -p ota-validation down
```

The benchmark rolls back and checks 49 expectations. `--persist` intentionally retains its scenario and belongs only on a fresh demo instance. Native benchmark tests require opening-only data. Do not reset operational data to satisfy a test.

## Frontend checks

From `frontend/`, run `npm ci` and `npm run build`. From the repository root:

```sh
node scripts/check_i18n.cjs
python scripts/check_docs.py
python -m pip install playwright
python -m playwright install chromium
python scripts/react_language_check.py --width 360
python scripts/react_language_check.py --width 1280
```

Language checks use existing demo accounts. Other `scripts/react_*.py` workflows can create records and must run against an isolated demo instance; pass its URL with `--url`.

`python scripts/react_layout_check.py --url http://localhost:8000` checks sidebar profile controls, contextual staff actions, report selection, responsive widths, filtering, pagination and exact ID sorting. It mocks only the order-list read response to exercise 45 rows without creating orders; it does not submit staff access or password changes. Screenshots are written to the operating system's temporary directory.

`python scripts/react_guidance_check.py --url http://localhost:8000` checks focused task dialogs, keyboard focus and Escape, searchable customer choices, item-specific units and column-header unit switching with one exact value per cell (including fractional and negative quantities). It mocks catalogue, dashboard and ledger reads and does not post business transactions.

## Code map

| Path | Responsibility |
| --- | --- |
| `api/main.py`, `workflows.py` | Authentication and HTTP routes |
| `api/queries.py`, `reporting.py`, `pdf.py` | Reads, reports and exports |
| `api/native.py`, `database.py` | Exact arithmetic, factory lock and transactions |
| `api/inventory/`, `production/`, `sales/` | Posting services and document lifecycles |
| `api/units/services.py` | Exact item/SKU conversions before posting and retry comparison |
| `api/accounts/`, `masters/`, `security/` | Account setup, masters and login controls |
| `api/seed.py`, `benchmark.py`, `reconciliation.py` | Fixtures, acceptance scenario and ledger checks |
| `api/migrations/` | Alembic schema ownership |
| `frontend/src/` | React screens, forms and bundled language catalogue |
| `frontend/public/` | Public offline shell service worker |
| `scripts/react_*.py` | Browser acceptance checks |
| Root Django apps and templates | Development regression oracle, excluded from runtime imports |

Business writes belong in service functions. Keep money and quantities exact, enforce roles server-side and append corrections rather than rewriting posted movements. Add service tests for business changes.

## Alembic schema cleanup

Revision `0004_drop_unused_django_session` removes only the unused `django_session` table after checking that no table has an incoming foreign key to it. The current installation verified it had no rows. Downgrade recreates the empty table; it cannot restore deleted session data. The initial schema SQL and signature omit this table so fresh installs reach the same schema before applying later revisions.

Do not drop Django auth tables as “boilerplate” without a separate identity migration. Native account, role, seed and security services still use `auth_user`, `auth_group`, and `auth_user_groups`; business/audit actor columns point to `auth_user`. `django_content_type` is referenced by `auth_permission`. The actual database showed 23 foreign keys to `auth_user`. A migration to a native `users` table must preserve user IDs, passwords, roles and every referencing foreign key, update `api/accounts/`, `api/security/`, seed, auth and queries, then pass fresh-install, upgrade, benchmark and native/API tests before legacy auth tables are removed. Never use `CASCADE` for this cleanup.

## Design PDF

The Markdown design note remains the editable source. With `reportlab` and `pypdf` installed, run `python scripts/render_design.py` to regenerate `output/pdf/design-note.pdf`. The renderer embeds Arial or DejaVu Sans, converts Mermaid relationships to a compact data-model table and asserts exactly two pages plus readable rupee text. Visually review both pages after editing the source.

## Troubleshooting

- **Port occupied:** set `WEB_PORT` in your ignored `.env` and restart Compose.
- **Startup failure:** inspect API logs and database health before changing data.
- **Benchmark refuses to run:** the database has operational postings; use an isolated project.
- **Old screen after an update:** rebuild and reload while online. Offline mode may still show its cached application shell.
- **Login fails:** initial demo passwords are not reset on restart; use the account's current password.
- **Translation check fails:** add the missing key in all three non-English catalogues, then rerun the browser checks.
