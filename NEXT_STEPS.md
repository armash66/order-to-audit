# Execution status

## FastAPI / React migration — complete

Done: native SQLAlchemy services, all workspace reads/reports/dashboard, PDFs, seed, benchmark/reconciliation CLI and Alembic schema adoption. Runtime image has no Django installed or imported. PostgreSQL schema/data remain intact; earlier Django source is retained only in the separate regression test image.

Validation complete: 77 regression/API tests and ten Django-free tests pass, including 49 benchmark checks, rollback, seeding, schema adoption, immutability and both mutation checks. React build, nine-step browser scenario and offline restart/reconnect pass. A clean source copy starts with one Compose command and passes all 49 native benchmark checks. Main instance adoption preserved counts/content hashes for all 51 existing tables; reconciliation and read-only smoke checks pass.

Next: user reviews/commits migration, rehearses the React demo, records the eight-minute video and submits. Main app is live on port 8000 with original data. No Git staging, commits or pushes were performed.

Commands: `docker compose up --build -d --wait`; `docker compose --profile test run --build --rm tests`; `docker compose exec api python -m api.cli benchmark` (opening-only DB); `docker compose exec api python -m api.cli reconcile`. Native test project `ota-native-final` is on port 8008; browser scenario project `ota-native-check` on port 8007 contains the completed demo.

Migration commit: `feat: complete FastAPI React migration with native ledger services`. Files: `api/`, `frontend/`, `alembic.ini`, `compose.yaml`, `.dockerignore`, `.gitignore`, `.env.example`, `README.md`, `NEXT_STEPS.md`, `docs/migration.md`, `docs/react-demo.md`, `docs/assumptions.md`, `docs/design.md`, `docs/compliance.md`, `scripts/react_benchmark_check.py`, `scripts/react_offline_check.py`, `scripts/migration_snapshot.py`. Earlier template/static/webapp UX edits are separate pre-existing work.

Workspace redesign: role-aware desktop sidebar/mobile navigation; searchable status-filtered order queue; task shortcuts; production register prioritized; secondary correction controls; unsaved-form warning; exact kg/L stock display. Browser checks cover all roles at desktop/360 px, filtering, warnings and full nine-step scenario. Suggested commit: `feat: redesign factory workspace around daily operations`.

UX follow-up: added role-aware home workflow shortcuts, order next-action guidance, run breadcrumb, and Hindi/Marathi navigation and common production labels. Translation coverage is partial with English fallback; native-speaker review is pending. Suggested commit: `feat: guide factory workflows and add Hindi Marathi labels`.

Done: foundation, stock core, production services (26 passing tests).
Done: phase 1 sales core (31-test suite).
Done: phase 2 roles/audit (33 tests).
Done: phase 3 screens (36 tests).
Done: phase 4 PDF/share (37 tests).
Done: phase 5 reports/dashboard (41 tests).
Done: phase 6 benchmark/logins and adjustments/reversals (46 tests).
Done: phase 7 suggestions/offline (48 tests; browser offline restart/sync verified).
Done: phase 8 delivery and clean source-copy validation (53 tests; 48 benchmark checks; full browser walkthrough).
Done: expanded reporting/offline gaps (54 tests), customer pricing/partial dispatch/returns (57 tests), batch/expiry/FEFO/reorder (59 tests).
Done: all eight stretch categories implemented; 63 tests pass, original benchmark passes 49 checks, migrations/reconciliation pass and the nine-step browser walkthrough passes on an isolated fresh Compose database.
Done: extension browser validation (Tamil, mock download, consented GPS, active-page automatic reconnect, offline restart followed by online reopen) and expanded delivery documentation.
Next (applicant): review/commit changes, repeat from the committed clone, timed rehearsal, narrated video/upload, confirm task deadline/contact and submit by 27 Nov 14:00 IST.
No git staging, commits or pushes authorized. Run full suite after each phase. Target feature complete 25 Nov; submission 27 Nov 14:00 IST.

## Review / commit groups

Shared files span phases; keep dependent migrations, app registrations and services together when batching. No changes were staged, committed or pushed.

| Phase | Files / directories | Suggested message |
| --- | --- | --- |
| 1 sales | sales/, inventory dispatch links/migrations, config/settings.py | feat: add atomic sales reservations invoicing dispatch and payments |
| 2 roles/audit | access/, sales/services.py, production/services.py, config/settings.py | feat: enforce role permissions and audit document edits |
| 3 screens | webapp/, templates/, static/app.css, config/, compose.yaml | feat: add role-aware order production and ledger screens |
| 4 invoice PDF/share | webapp/services.py and PDF view/tests, templates/invoice_pdf.html, templates/order.html, static/share.js | feat: render snapshot invoice PDFs and support file sharing |
| 5 reports | reporting/services.py and tests, report/dashboard templates, webapp/views.py and urls.py | feat: add filtered CSV PDF reports ageing and owner dashboard |
| 6 benchmark/corrections | reporting/benchmark.py, management commands, access/seed.py, inventory corrections/migrations/tests, production state/report, docker/entrypoint.sh | feat: verify nine-step benchmark and add guarded stock corrections |
| 7 stretch | production suggestion service/tests, webapp offline service/views/tests, static/offline.js and service-worker.js, offline/order templates | feat: suggest feasible production and sync persistent offline orders |
| 8 delivery | README.md, docs/, NEXT_STEPS.md, scripts/browser_check.py, .dockerignore, .env.example, compose.yaml, final sales/web regression fixes | chore: validate local delivery and document compliance |

Validation detail: docs/delivery-validation.md. Compliance matrix: docs/compliance.md. Six interview questions and weak spots: docs/demo.md. Full runtime suite passed after restoring both production mutations and rebuilding the final image.

## Expanded-scope commit batches

Shared files now span all optional features. Prefer these two dependency-complete commits rather than staging an incomplete intermediate migration graph:

| Files | Suggested message |
| --- | --- |
| config/settings.py; inventory/, production/, sales/, reporting/, extensions/; webapp/; templates/; static/ | feat: complete optional sales and all eight stretch workflows |
| README.md; NEXT_STEPS.md; docs/vision.md, requirements.md, assumptions.md, compliance.md, design.md, demo.md, delivery-validation.md, extended-features.md; scripts/extended_browser_check.py | docs: record expanded scope evidence and demo boundaries |

All initial demo accounts retain password `DemoPass123!`: admin, production, salesman_a, salesman_b, accountant, owner. Main instance is http://localhost:8000; isolated expanded rehearsal is http://localhost:8002. The rehearsal contains demo workflow transactions and must not be treated as a fresh benchmark seed.
