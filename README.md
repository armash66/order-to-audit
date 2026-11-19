# Order-to-Audit

A document-led system connecting sales, production, inventory and receivables for a small food manufacturer. The local Django/PostgreSQL foundation is implemented; the stock core now supports masters, opening stock and purchase receipts. Production and sales workflows are not implemented yet.

## Local setup

Prerequisite: Docker Desktop running Linux containers with Docker Compose. From the repository root:

```sh
docker compose up --build -d --wait
```

Open http://localhost:8000. Startup waits for PostgreSQL, applies Django's built-in migrations and starts the local development server. No host Python installation or `.env` file is required. The first run needs internet access to download images, packages and fonts. PostgreSQL data persists in a named volume; ordinary restart does not reset it.

Optional: copy `.env.example` to `.env` to override the local demo settings. `.env` is ignored by Git and excluded from the Docker build context. Only `.env.example` belongs in version control. Defaults are deliberately local demo credentials, not deployment secrets. Changing PostgreSQL initialization credentials after a volume exists does not change that database's existing credentials.

```sh
docker compose exec web python manage.py check
docker compose exec web python manage.py test -v 2
docker compose logs web
docker compose down
```

The tests check the startup page, a real PostgreSQL test database, and an in-memory one-line PDF containing ₹. No invoice PDF feature exists yet. `down` stops the containers while preserving the database volume. The app listens only on the host loopback interface; PostgreSQL has no published host port. This is a local development setup, not a hosted deployment.

## Stack and files

Django 5.2 supplies forms, templates, authentication foundations and migrations in one application; PostgreSQL will support transactional ledger posting. Server-rendered pages keep validation and workflow logic on the server. Docker Compose provides the same local runtime for development and evaluation; WeasyPrint's Linux libraries and a rupee-capable font are installed early to expose PDF dependency problems before invoicing work.

| File | Purpose |
| --- | --- |
| `.gitignore` | Excludes real environment files, virtual environments and Python/test artifacts; permits `.env.example`. |
| `.dockerignore` | Excludes environment files, Git metadata, planning documents and local artifacts from the image. |
| `.env.example` | Documents optional local configuration using dummy values. |
| `requirements.txt` | Pins direct Python dependencies, including the PDF text reader used by the smoke test; transitive dependencies and image tags are not fully locked yet. |
| `Dockerfile` | Builds Python with WeasyPrint libraries and DejaVu fonts, then runs as a non-root user. |
| `compose.yaml` | Defines web/database services, health checks, local environment defaults and persistent database storage. |
| `docker/entrypoint.sh` | Applies migrations, stops on failure and starts the requested process. |
| `manage.py` | Runs Django management commands. |
| `config/__init__.py` | Marks the configuration directory as a Python package. |
| `config/settings.py` | Configures environment-based PostgreSQL access, templates, middleware and IST display timezone. |
| `config/urls.py` | Routes the root URL to the startup template. |
| `config/wsgi.py` | Exposes Django's WSGI application entry point. |
| `config/tests.py` | Tests startup rendering, PostgreSQL connectivity and one-line ₹ PDF rendering/text extraction. |
| `templates/startup.html` | Shows a minimal, mobile-width startup page without business workflows. |

## Planning documents

- [Vision](docs/vision.md)
- [Requirements and acceptance checks](docs/requirements.md)
- [Decisions and domain sketch](docs/assumptions.md)
- [Benchmark golden workbook](docs/benchmark.xlsx)

## Benchmark expectations and deliberate interpretations

Materials cost ₹4,055; run cost with overhead ₹5,855; cost per good packet ₹31.14; margin before tax ₹18.86. Retailer A invoice is ₹7,875 and outstanding is ₹3,875. These are verified planning values, not application test results.

- **Carton alert:** actual 9 versus standard 10 gives −10%, so the uniform absolute-variance rule flags cartons as well as yield (−6%) and oil (+5%). The PS's named expected alerts list only yield and oil; this additional alert preserves the given nine-carton consumption. Eight packets remain loose under DEC-05.
- **Unclassified output shortfall (DEC-06):** 200 expected minus 188 good gives 12 unclassified packet-equivalents. Six damaged pouches are recorded separately; the PS does not establish damaged food quantities or a cause. No assumed 6 + 6 split or additional stock deduction.

## Scope and cut line

SAL-6 invoice sharing is Should. The selected stretch is STR-4, production suggestions with input-feasibility warnings. If time runs short, defer in this order: DASH-1 owner dashboard, AUTH-2 auditor/owner access, RPT-2 report PDFs, then STR-4. No cuts have been activated. Invoice PDF, all Must features and benchmark CSV reports/calculations remain required. Report PDFs will share one generic table renderer; deferral must be disclosed as a section 4.6 gap.

## Next implementation session

Design the ledger transaction boundaries, then add the first tested inventory service in a separately approved chunk. The opening seed and stock-core tests exist; role logins, full benchmark execution and production/sales screens are not implemented. Business logic will live in tested `services.py` functions. Organizer contact and questions-window dates remain unconfirmed because the supplied PDF contains placeholders; the questions email remains unsent.

## Posting and correction boundaries

Stock events append in server-assigned posting sequence; document dates cannot reorder valuation or insert earlier movements. Explicit rejection is a terminal order outcome with a reason; shortage alone leaves an order submitted. See the [allowed-transition tables](docs/assumptions.md#allowed-transitions-implementation-contract). Full invoice credit is supported only before payment or dispatch; full run reversal is blocked by later stock postings on affected items or insufficient unreserved FG. These are deliberate prototype limits.

Delivery is local-only with one-command reproducibility first. Target submission: 27 November 2026, 14:00 IST; user-reported application close: 17:00 IST. Task-specific deadline/contact confirmation is pending. Hosted delivery is reconsidered on 26 November only if core work is complete.

## Stock core

After startup, load the section 5 masters and opening stock with:

```sh
docker compose exec web python manage.py seed_benchmark
docker compose exec web python manage.py reconcile_stock
docker compose exec web python manage.py test inventory config -v 2
```

The seed is repeatable: it does not reset stock, execute the purchase, overwrite changed fixtures or create usable user passwords. The step-1 purchase is exercised through `post_receipt` in tests; there is no purchase screen yet. Expected flour after that receipt: 160,000 g, value 690,000 paise, weighted average 69/16 paise per gram (43.125 INR/kg). Opening finished-goods cost remains unknown.

| File | Purpose |
| --- | --- |
| `inventory/models.py` | Masters, explicit opening/purchase documents, posting sequence and movement relationships/constraints. |
| `inventory/migrations/0001_initial.py` | Creates the stock-core schema. |
| `inventory/migrations/0002_posting_guards.py` | Creates the factory lock row and movement update/delete rejection trigger. |
| `inventory/services.py` | Exact conversion/rounding, atomic authorized posting, weighted average, ledger summary and independent source reconciliation. |
| `inventory/seed.py` | Loads and verifies benchmark fixtures in one transaction, then posts opening through the service. |
| `inventory/management/commands/seed_benchmark.py` | Thin command wrapper for the seed. |
| `inventory/management/commands/reconcile_stock.py` | Thin command wrapper for reconciliation. |
| `inventory/tests.py` | Benchmark, exact arithmetic, retries, source/report mismatch, permissions, immutability and transaction tests. |
| `inventory/**/__init__.py` | Python package markers only. |

There is no editable balance or cached stock table. One factory row serializes all posting; this favors explainable correctness over throughput. Direct SQL/ORM editing of source documents bypasses service-level freezing, so production use would need tighter database privileges or source triggers. Movement immutability is enforced by PostgreSQL. Reconciliation checks internal consistency, not physical stock truth. Receipt valuation is implemented; issue costing and rounding-residual allocation remain for the production chunk.

Mutation verification: disabling the duplicate-return guard caused the retry test to error on the database unique constraint; disabling the immutable-movement trigger caused `DatabaseError not raised`. Both changes were container-only, independently tested, and restored. See `docs/stock-core-validation.md` for the validation record.
