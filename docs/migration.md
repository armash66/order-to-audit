# FastAPI / React migration

The user requested FastAPI and React because these are the frameworks they can explain and change confidently. PostgreSQL, its volume, source documents, ledger constraints and posting history stay in place.

## Runtime

`docker compose up --build -d --wait` serves the React/TypeScript application on http://localhost:8000. Nginx serves compiled assets and proxies `/api/` to FastAPI. There is no Django HTTP server in the default stack. Existing demo accounts/passwords continue to work; PBKDF2 hashes are verified without rewriting accounts.

The API issues signed one-hour bearer tokens held in React memory. Refresh/restart requires login again. Account activity, roles and password version are checked on every request. API amounts and quantities are decimal strings; React uses BigInt for paise. Existing service validation rejects floats before posting.

## Persistence and schema ownership

The runtime is Django-free. SQLAlchemy Core services handle receipts, production, orders, GST invoices, dispatch, payments, credits, returns, corrections, pricing, reorder settings, visits and mocks. Workspace/report queries and startup seeding are native too. Offline sync uses the same order service. WeasyPrint renders escaped invoice/report HTML without Django templates. Stock/authentication GET dependencies use read-only connections.

Alembic owns schema startup. Its first revision creates the captured schema on an empty database, or verifies columns, constraints, indexes and enabled trigger definitions before adopting an existing database. Adoption adds only Alembic's revision tracking; table names, source IDs, credentials and movement history stay intact. The generated `schema.sql` and `schema-signature.json` are the baseline, not hand-maintained business logic. Future changes must be explicit Alembic revisions; do not run old Django migrations against the runtime database.

Earlier Django code remains as a development-only regression oracle. The `tests` image installs Django and creates its own temporary test database. The default runtime image does not install or import Django, and Compose no longer exposes a legacy web service.

## Files

- `api/main.py`: FastAPI authentication and read-only stock endpoints.
- `api/database.py`, `api/services.py`: SQLAlchemy connections and exact ledger/password reads.
- `api/workflows.py`: role-checked transport adapter to atomic posting/report services, including offline sync.
- `api/native.py`: exact integer valuation, factory locking, source sequencing, reflected tables, audit and FEFO allocation primitives.
- `api/inventory/services.py`, `api/inventory/corrections.py`: receipt posting, reasoned adjustments and exact production reversal.
- `api/production/services.py`: versioned run snapshots, issue/completion, overheads, tolerance and exact cost/variance reporting.
- `api/sales/services.py`: reservation lifecycle, invoice tax/numbering, partial dispatch, payment, credit and cumulative return allocation.
- `api/extensions.py`: customer prices, reorder settings, optional consented GPS visits and local mock document exports.
- `api/pdf.py`: escaped invoice/report HTML and WeasyPrint rendering from frozen snapshots.
- `api/queries.py`, `api/reporting.py`: scoped workspace queries, planning feasibility, eleven reports, dashboard and balanced Tally XML.
- `api/seed.py`, `api/cli.py`, `api/benchmark.py`, `api/reconciliation.py`: native seed, operational checks and rollback-safe nine-step benchmark.
- `api/migrations/`, `alembic.ini`: schema-preserving adoption and future migration ownership.
- `api/translations.json`: UTF-8 English/Tamil/Hindi/Marathi catalog independent of template tags.
- `api/tests.py`: nine-step scenario through HTTP endpoints against an isolated test database.
- `api/test_api.py`: read-only checks against a running seeded instance.
- `frontend/src/Workspace.tsx`: React workflows/forms and exports. `main.tsx` owns login and in-memory authentication.
- `Offline.tsx`, `VisitForm.tsx`, `language.tsx`: persistent offline capture, consented GPS and the existing translation catalogue.
- `frontend/public/service-worker.js`: caches public app shell/assets only, never authenticated API responses.
- `frontend/Dockerfile`, `nginx.conf`: compiled React delivery and same-origin API proxy.

## Checks and known gaps

Validation: 77 regression/API tests and ten separate Django-free runtime tests. All eleven report outputs match the legacy implementation for the benchmark (source links now use API paths). The native benchmark passes 49 checks and proves rollback; tests cover concurrent receipt retry/approval, exact tax, partial dispatch/returns, permissions, corrections, 500 g shared recipe, tolerance and PDF text extraction. Variance `>=` and incorrect issue-value mutations both cause benchmark failures and leave no scenario writes. Adoption rejects a disabled movement guard and restores it through rollback.

React builds with TypeScript checking. The nine-step browser walkthrough and offline capture/reconnect/restart checks pass on an isolated native stack. Fixed migration defects include PostgreSQL numeric aggregates being converted exactly to integers, a seed helper argument colliding with the item name column, explicit zero production usage, accessible select labels and stale detail rendering.

Commands: `docker compose --profile test run --build --rm tests`; `docker compose exec api python -m api.cli benchmark`; `docker compose exec api python -m api.cli reconcile`. Native runtime tests need a fresh opening-only instance: `docker compose exec api python -m pytest api/test_api.py api/test_native.py -q -p no:cacheprovider`.

Clean-install proof: copied the 189 tracked/unignored source files to a temporary directory without `.env`, Git metadata, node_modules or build output; one Compose command created a fresh PostgreSQL volume and healthy native app. The native CLI passed all 49 benchmark checks and rolled back. This is a clean source-copy check because the user commits manually; it is not falsely described as a check of an already-committed clone.

In-place proof: main port 8000 now runs the native image. Before/after hashes and row counts match for all 51 pre-existing tables; only the Alembic revision record was added. Existing passwords and opening stock were retained, and source/ledger/lot reconciliation passes. The old stopped Django web container was removed without deleting its PostgreSQL volume.

Partial translations and the prior accounting limitations still apply. The new frontend uses base-unit production inputs explicitly labelled g/ml/piece. The generic workflow forms need further UX refinement; existing Django-screen usability claims must not be assumed to apply to React. Tokens are not persisted to disk; offline capture survives restart, but syncing requires the original account to sign in online.
