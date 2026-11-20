# Order-to-Audit

A local factory workflow for the CDI NIT Trichy internship exercise: order → approval → invoice → dispatch → collection, and purchase → raw issue → production → finished goods → variance/cost.

## Run locally

Install Docker with Compose, then from this directory:

```sh
docker compose up --build -d --wait
```

Open **http://localhost:8000**. Startup migrates PostgreSQL, seeds the section 5 masters/opening stock and creates demo logins. No `.env` is required; `.env.example` documents optional overrides. `.env` is ignored and excluded from the image. Data persists in the project-specific Docker volume. Stop with `docker compose down`; do not delete the volume unless you intend to erase its data.

All initial demo passwords: **`DemoPass123!`**. Change `DEMO_PASSWORD` before first startup to choose another; restarts never reset existing passwords.

| Login | Access |
| --- | --- |
| `salesman_a`, `salesman_b` | Capture orders; see only own orders and own customer sales; PDF/share |
| `admin` | Approve/reject, invoice, dispatch, payments, corrections and production |
| `production` | Receipts, run issue/completion, variance and stock |
| `accountant` | Read-only orders, stock and report exports |
| `owner` | Read-only dashboard, orders, stock and reports |

These are fictional demo identities. This Compose configuration binds localhost and uses Django's development server; it is not a public hosting configuration.

## Verify

```sh
docker compose exec web python manage.py test -v 1
docker compose exec web python manage.py benchmark
docker compose exec web python manage.py reconcile_stock
docker compose exec web python manage.py makemigrations --check --dry-run
```

`benchmark` runs all nine steps through real services, prints 49 expected/actual checks and rolls its scenario back. It requires opening-only stock data. Use `benchmark --persist` once on a fresh instance to keep the full scenario for inspecting screens. A database with operational stock postings is rejected, never reset. For an independent rehearsal instance use a new Compose project name and `WEB_PORT=8001` in an external environment file. The 63-test suite uses its own temporary database, also checks the golden workbook's decimal XML directly, and never deletes application data.

## Stack and rationale

Django with server-rendered forms keeps validation, permissions and business rules in one understandable Python codebase; a React/API split would add state and build tooling without improving the benchmark. PostgreSQL supplies real transactions, row locks and immutable-movement triggers; SQLite would not exercise the same concurrency guarantees. Docker Compose packages PostgreSQL and WeasyPrint's native libraries and fonts into a reproducible local run.

## Scope status

| Section 6 tier | Delivered |
| --- | --- |
| Must | Five role groups; seeded masters/conversions/versioned BOMs; mobile ordering and admin approval; GST PDF; two-stage production; consumption/yield variance; ledger/summary; CSV sales and stock reports |
| Should | Suppliers/purchases; allocations/outstanding/ageing; exact cost with overheads; GST summary; configurable strict tolerance alerts; owner dashboard |
| Additional section 4 | Customer/product sales, purchase, production, collections and ageing reports; inclusive dates; CSV/PDF via one renderer; native PDF sharing with desktop attachment fallback |
| Optional sales | Customer-specific fixed prices/scheme labels, partial dispatch and resalable returns with exact credit allocation |
| All eight stretch categories | Shortage planning; offline capture/reconnect sync; batches/expiry/FEFO; reorder alerts; visits/consented GPS; Tally XML export; local e-invoice/e-way-bill mocks; Tamil production labels |

See [extended feature guide](docs/extended-features.md) for screens, tests and external-validation boundaries. Tally import and human Tamil review remain unverified; government integrations are explicitly local mocks.

See [compliance evidence](docs/compliance.md), [requirements](docs/requirements.md), [decisions](docs/assumptions.md), [design note](docs/design.md), [golden workbook](docs/benchmark.xlsx), [validation](docs/delivery-validation.md) and [demo walkthrough](docs/demo.md).

## Benchmark results

| Check | Result |
| --- | --- |
| Flour / oil / spice closing | 120 kg / 19.5 L / 3.8 kg |
| Pouches / cartons | 306 / 21 |
| FG after run / after dispatch | 238 / 88 packets |
| Approval and invoice: on-hand / reserved / available | 238 / 150 / 88 |
| Dispatch: on-hand / reserved / available | 88 / 0 / 88 |
| Yield / oil / cartons / pouches variance | −6% flagged / +5% flagged / −10% flagged / −3% not flagged |
| A invoice | ₹7,500 + ₹187.50 CGST + ₹187.50 SGST = ₹7,875 |
| A collected / outstanding | ₹4,000 / ₹3,875 |
| B | Submitted, shortage 32; no invoice or reservation |
| Weighted flour / materials / total cost | ₹43.125/kg / ₹4,055 / ₹5,855 |
| Cost and margin per good packet | Exact ₹5,855/188; displayed ₹31.14; margin ₹18.86 |

**Deliberate interpretations:** the uniform tolerance rule also flags cartons (−10%), beyond the PS's named yield/oil alerts. Nine cartons are recorded as given, with eight packets loose. The 12 packet-equivalents of output shortfall are **unclassified**; six damaged pouches are separate packaging damage already included in the 194 issued. No assumed 6 + 6 food-loss split and no additional stock deduction. No benchmark quantity or money result differs from the golden file.

## Boundaries and known gaps

- FG valuation is materials-only. Opening FG value is unknown, so aggregate FG value and COGS remain unknown. Late overhead changes run cost, not past FG movements.
- Tolerance changes apply retroactively to displayed alerts. Production reports select runs by document date and show their currently recorded costs. Stock reports use posting date/sequence; commercial registers use document dates. Ageing is due-date based, due on invoice date, and ignores its range start.
- Payments are allocated in full to one invoice; several payments per invoice are supported. Full cancellation credit is unpaid/undispatched only. Partial dispatch and resalable returns are supported; returns credit original tax and restore original dispatch value. Paid returns may leave customer credit; no cash-refund settlement workflow.
- Run reversals correct recording errors, not physical production. Later or intervening affected-item stock events and reserved FG block reversal. No cascading revaluation, fractional planned batches or ingredient substitution.
- Posted sources are frozen by services; privileged ORM/SQL can bypass this. The database trigger protects movement update/delete only. Reconciliation detects source/ledger disagreement. Direct database owners are trusted.
- Native file sharing depends on the device. Desktop fallback requires downloading and attaching the PDF manually. The app does not send email or WhatsApp messages. Localhost links are not public customer links.
- Offline capture is one SKU per queued order, supports a private demo device, and confirms server pricing at sync. Cached dummy catalog/queued data remains on that device across sign-out; sync requires the original account. No background sync or multi-device conflict resolution.
- GST is the exercise's fixed 5%, with per-line component rounding. GSTR labels are explanatory mappings, not filing-ready payloads. GSTINs and HSN are fictional. Master data is seeded; no generic master-maintenance UI.
- Expiry is optional: migrated stock has labelled LEGACY lots with unknown expiry. FEFO excludes expired stock and uses unknown-expiry lots last; valuation stays item-level weighted average. Returned batches use the earliest known original expiry conservatively. Lot allocations are service-frozen and reconciled, not protected by additional database triggers.
- Customer schemes are fixed price overrides, not a promotion engine. Tally XML has structure/balance tests but has not been imported into Tally. Mock government documents are not valid fiscal documents. Tamil covers production labels, with English validation messages and fallback product names; native-speaker review is pending.
- Images/transitive dependencies are not fully digest-locked. No hosted demo, production webserver or public deployment hardening. The video/public repository submission and organizer deadline/contact verification remain human delivery tasks.

## Where the code lives

| Files | Purpose |
| --- | --- |
| `inventory/models.py`, `services.py`, migrations | Masters, typed sources, ledger, receipt/adjustment/reversal posting and reconciliation |
| `production/models.py`, `services.py` | Snapshotted runs, exact issues, completion, late overhead, variance and suggestions |
| `sales/models.py`, `services.py` | Orders/reservations, immutable invoice snapshots, FY sequence, dispatch, payments, credits |
| `extensions/models.py`, `services.py` | Consented visits/GPS and deterministic local government-document mocks |
| `access/models.py`, `services.py`, `seed.py` | Audit events, role gates and demo identities |
| `reporting/services.py`, `benchmark.py` | Shared report tables/exports/dashboard and the nine-step service orchestrator |
| `webapp/views.py`, `forms.py`, `services.py` | HTTP adaptation, exact entry parsing, PDF and offline sync boundaries |
| `templates/`, `static/` | Server-rendered screens, shared styling, native file share and offline shell/queue |
| `config/`, `Dockerfile`, `compose.yaml`, `docker/` | Django runtime, container libraries, startup/migrations/seed |
| App `tests.py` and `test_*.py` | Arithmetic, posting/retry/concurrency, rollback, permissions, reports, golden benchmark and corrections |

No Git commits or pushes are made by the coding agent. See [NEXT_STEPS](NEXT_STEPS.md) for the handoff and suggested commit batches.
