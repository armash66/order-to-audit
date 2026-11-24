# Current handoff

Updated 24 November 2026. Target submission: 27 November, 14:00 IST.

## Done

- Hosted CI repair: pinned the runner to Ubuntu 24.04. Uploaded logs show Ubuntu 26.04 was incompatible with Playwright 1.57 at browser installation; application regression checks had passed. Workflow/docs checked locally; the repaired hosted run awaits applicant push.

- Latest chunk: admin setup checklist, searchable order/customer/staff lists, status/access filters and action-specific posting confirmations. Browser check creates a real fictional staff account in an isolated project.
- Added API reference, verified binary-safe backup/restore guide and updated historical optional-feature descriptions.
- Added GitHub Actions CI: frontend/docs checks, fresh Compose, native/regression tests, benchmark, browser checks, restore rehearsal and downloadable tested images. No deployment host configured; hosted Actions status awaits applicant push.

Latest validation: 86 regression tests, 13 native tests, 49 benchmark checks; browser benchmark, UX/account creation, offline reconnect and multilingual mobile checks; 249 translated static phrases and 14 document-link checks. Backup of completed benchmark + created staff restored to a separate PostgreSQL container and passed ledger/source/lot reconciliation; 8 users and Alembic 0003_operator_setup recovered. YAML/permission/cleanup checks passed. Playwright pinned to locally exercised 1.57.0 in CI.

Latest commit points (supersede the earlier file list below):

1. `feat: improve setup discovery and everyday navigation`: `frontend/src/Workspace.tsx`, `frontend/src/translations.json`, `scripts/check_i18n.cjs`, `scripts/react_ux_check.py`, `docs/operations.md`.
2. `ci: verify application builds and database recovery`: `.github/workflows/ci.yml`, `scripts/backup.py`, `.gitignore`, `.dockerignore`, `scripts/check_docs.py`, `README.md`, `docs/README.md`, `docs/api.md`, `docs/backup-restore.md`, `docs/ci.md`, `docs/security.md`, `docs/extended-features.md`, requirements/assumptions and this handoff.

- FastAPI/React runtime with PostgreSQL, native services and Alembic.
- Sales, production, immutable stock, reports, setup and optional workflows.
- Shared English/Tamil/Hindi/Marathi interface catalogue.
- Language preference at sign-in and offline; translated controls, messages, confirmations and accessibility labels.
- README reorganized into setup, features, verification and documentation links.
- Dedicated operations, development, localization, security and benchmark guides.
- Removed obsolete root Django Dockerfile, startup script and dependency file. Regression source and historical evidence retained.
- PS gap closure: exact native kg/L/SKU-carton conversion, canonical retries, invalid-unit rejection and tests.
- Automatic same-user offline reconnect/reopen sync; explicit WhatsApp/email draft links alongside PDF download/native sharing.
- Inline README benchmark/assumptions, current compliance matrix, timed video guide, submission checklist and two-page design PDF.

## Validation

Current pass: 86 full regression tests, 13 native tests including exact units, 49 benchmark expectations, frontend build, 230 static phrases across three translated languages, and documentation links. Browser checks cover the nine-step workflow using kg/L, invoice sharing drafts, automatic offline sync/restart and three languages at 360/1280 px across four roles. UTF-8 verification caught and corrected damaged new entries; the source checker now rejects repeated question marks/replacement glyphs.

Final clean-source validation: a source copy excluding `.git`, `.env`, caches and installed dependencies started with a new PostgreSQL volume using one Compose command. All 13 native tests and 49 benchmark checks passed again; the browser walkthrough also verified rupee price editing. The two-page PDF was rendered and visually checked. The main localhost:8000 application has been rebuilt; temporary validation projects are stopped without deleting volumes.

Final main-instance checks: ledger/source/lot reconciliation, rupee PDF smoke check and mobile language checks passed. Only `nit-api-1`, `nit-frontend-1` and `nit-db-1` remain running. Automatic approval review blocked recursive cleanup of the task's `ota-clean-submission-492ahaly` and `ota-design-preview` folders in Windows Temp; those temporary files remain. No application data was removed.

## Remaining submission work

- Native-speaker wording review; automated coverage does not certify idiomatic translation.
- Review documented integration limits, especially Tally import and mocked government formats.
- Record the nine-step demo in under eight minutes.
- Confirm organizer task deadline/contact and submit the repository/video links.
- Public visibility confirmed: https://github.com/armash66/order-to-audit . Applicant must push the latest local work; published history/video remains a final delivery check.

## Commit point

Suggested message: `feat: close problem statement workflow and submission gaps`.

Files:

- `api/units/__init__.py`, `api/units/services.py`: exact conversion boundary; `api/inventory/services.py`, `api/production/services.py`, `api/sales/services.py`: normalize under the factory lock; `api/benchmark.py`, `api/tests.py`, `api/test_units.py`: measured-unit benchmark, retries and rollback evidence.
- `frontend/src/Workspace.tsx`, `frontend/src/Offline.tsx`, `frontend/src/translations.json`: unit controls, rupee price editing, draft share links, reconnect sync and translated copy.
- `scripts/react_benchmark_check.py`, `scripts/react_offline_check.py`, `scripts/react_factory_gaps_check.py`, `scripts/check_i18n.cjs`, `scripts/check_docs.py`: browser, localization/encoding and link verification.
- `README.md`, `docs/README.md`, `docs/assumptions.md`, `docs/compliance.md`, `docs/design.md`, `docs/development.md`, `docs/extended-features.md`, `docs/operations.md`, `docs/react-demo.md`, `docs/reference.md`, `docs/submission.md`, `NEXT_STEPS.md`: contract evidence, current behavior, decisions, remaining delivery work and interview questions.
- `scripts/render_design.py`, `output/pdf/design-note.pdf`: reproducible, visually verified two-page submission note.

No staging, commits or pushes performed.
