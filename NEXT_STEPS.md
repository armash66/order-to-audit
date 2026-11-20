# Execution status

Done: foundation, stock core, production services (26 passing tests).
Done: phase 1 sales core (31-test suite).
Done: phase 2 roles/audit (33 tests).
Done: phase 3 screens (36 tests).
Done: phase 4 PDF/share (37 tests).
Done: phase 5 reports/dashboard (41 tests).
Done: phase 6 benchmark/logins and adjustments/reversals (46 tests).
Done: phase 7 suggestions/offline (48 tests; browser offline restart/sync verified).
Done: phase 8 delivery and clean source-copy validation (53 tests; 48 benchmark checks; full browser walkthrough).
In progress: none.
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
