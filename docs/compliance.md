# Compliance evidence

Verified 24 November 2026 against the original seven-page problem statement. The active runtime is React / FastAPI / SQLAlchemy / PostgreSQL with Alembic. Screen names below refer to the current React workspace. Legacy service tests are an independent regression oracle; `api/tests.py`, `api/test_native.py` and `api/test_units.py` exercise the native implementation.

Validation: 86 full regression tests, 13 Django-free tests and 49 native benchmark expectations passed. Browser evidence covers the nine-step workflow, invoice PDF and share drafts, automatic offline reconnect/reopen sync, and multilingual role screens. Commands are in [development](development.md). These are local checks, not organizer acceptance or a human usability certification.

## Section 5

| Step / expected result | Status | Evidence |
| --- | --- | --- |
| Masters/opening: flour 100 kg, oil 30 L, spice 5 kg, pouches 500, cartons 30, FG 50 | Pass | `api.seed.seed_benchmark`; opening checkpoint and source reconciliation |
| 1: flour purchase 60 kg at ₹45, closing 160 kg; average ₹43.125/kg | Pass | `api.benchmark.run_benchmark` step 1; purchase screen/register |
| 2: issue flour 40 kg, oil 10.5 L, spice 1.2 kg | Pass | Step 2; `production.tests`; source-linked negative movements |
| 3: 188 good, 194 pouches including 6 damaged, 9 cartons; FG 238; raw 120 kg/19.5 L/3.8 kg | Pass | Step 3; production run screen; exact cost, yield −6%, oil +5%, carton −10% flagged, pouch −3% unflagged |
| 4: salesman A submits 150 | Pass | Step 4 uses salesman identity; mobile Orders; browser 360 px check |
| 5a: approval 238/150/88 on-hand/reserved/available | Pass | `SalesTests.test_benchmark_reservations_dispatch_payment`; concurrent approval test |
| 5b: invoice leaves stock unchanged; ₹7,500 + ₹187.50 + ₹187.50 = ₹7,875 | Pass | Step 5b; PDF extraction checks currency/totals; invoice screen |
| 5c: dispatch 88/0/88; retry does not double-deduct | Pass | Step 5c; duplicate dispatch test and reconciliation |
| 6: B asks 120, shortage 32, remains submitted | Pass | Step 6 rejects approval; order screen; independent interstate/FY test confirms IGST |
| 7: collection ₹4,000; due ₹3,875 | Pass | Step 7; payment allocation/idempotency; collections/ageing reports |
| 8: labour ₹1,200, power ₹600; run ₹5,855; exact unit cost ₹5,855/188, display ₹31.14 | Pass | Step 8; append-only overhead test; run cost/margin screen |
| 9: month's section 4.6 reports | Pass | Step 9 renders eleven report tables to CSV and PDF, including customer ageing; date/credit tests; ageing 30/31-day boundaries |

## Section 6

| Item | Status | Test or screen |
| --- | --- | --- |
| Must: login, salesman/admin/production | Pass | Five demo groups; `RoleAuditTests`, `ScreenTests`, native role/ownership and read-only tests |
| Must: product/customer/raw/BOM masters | Pass | Seed command, conversion tests, snapshotted versioned recipe/BOM tests |
| Must: mobile order/admin approval | Pass; human timing trial pending | Orders list and order detail; concurrent reservation test; 360 px browser check |
| Must: GST invoice PDF | Pass | `PDFTests`; Order detail: Download invoice PDF; ₹ text extraction, intra/interstate and FY tests |
| Must: production updates raw/FG automatically | Pass | `production.tests`, nine-step scenario; issue/complete screens |
| Must: planned/actual consumption/yield | Pass | Run screen and production report; strict tolerance boundary/2% tests |
| Must: stock summary/ledger | Pass | Stock, item ledger and source detail; reconciliation and immutability tests |
| Must: sales and stock CSV | Pass | Reports; `ReportTests.test_all_exports_and_dashboard` |
| Should: purchases/suppliers | Pass | Receipt screen; seed supplier; weighted-average purchase test/register |
| Should: payments/outstanding/ageing | Pass | Order payment form; collections/ageing CSV/PDF; historical cutoff/boundary tests |
| Should: cost per packet with overheads | Pass | Run screen; exact material and late overhead tests; known FG valuation limitation disclosed |
| Should: GST summary | Pass for exercise mapping | GST report: GSTR-1 B2B/category, GSTR-3B 3.1(a); not a filing payload |
| Should: tolerance alerts | Pass | Configurable basis-point setting; exact 3% not flagged; mutation check detects `>=` |
| Should: owner dashboard | Pass | Dashboard as owner; `dashboard` totals and read-only checks |
| Selected stretch: planning from shortages | Pass | Order detail; `SuggestionTests`: 32 → 1 batch; 250 → 2 needed/1 feasible |
| Selected stretch: offline capture/sync | Pass | Offline; native ownership/retry tests; browser automatic reconnect/reopen sync |
| Stretch: batch/expiry/FEFO | Pass with optional expiry | Batch screen/ledger; `inventory/test_batches.py`; expired issue rollback and lot reconciliation |
| Stretch: reorder alerts | Pass | Batch thresholds and owner dashboard; available-stock threshold test |
| Stretch: routes/GPS | Pass | Visits screen; consent, ownership and retry tests |
| Stretch: Tally export | Implemented; real import unverified | Reports ZIP; XML structure/balance/date tests; documented accounting-only format |
| Stretch: mock e-invoice/e-way bill | Pass as local mock | Order mock screen; exact JSON, both formats, deterministic MOCK responses and role tests |
| Stretch: Tamil | Implemented; native-speaker review pending | Four-language catalogue; three translated languages across four roles, sign-in, all menus and offline |
| Optional: customer pricing/schemes | Pass for fixed prices | Prices screen; override/snapshot/catalogue test |
| Optional: partial dispatch/returns | Pass for resalable goods | Order screen; exact reservations, retry, over-dispatch/return and cumulative tax/value tests |

## Additional contract and delivery

| Requirement | Evidence / boundary |
| --- | --- |
| Immutable ledger and exact arithmetic | PostgreSQL update/delete trigger; integer base units/paise, Fraction; rollback and duplicate-request concurrency tests; mutation checks in stock/production validation notes |
| Corrections and audit | Reasoned adjustments; bounded exact-inverse run reversal tests; full unpaid/undispatched credit; draft invoice/run edit audit tests; role-gated React Audit page shows actor/time and before/after values |
| Shared recipe / 500 g change | `production/test_fixtures.py` plus test; 33 added lines across two files after recipe separation; benchmark seed unchanged |
| One-command local run | Clean source-copy Compose startup with fresh DB and automatic role seed; no local `.env` required |
| Design/README | `docs/design.md`, README and this matrix |
| Public repo/history/video | Public visibility verified through unauthenticated GitHub API; applicant must commit/push the latest work and record/upload the ≤8-minute walkthrough; agent does not commit/push or send messages |
| Real-user order timing | Screen requires customer/product/quantity and submit; automated 360 px check passes. Applicant must perform the under-one-minute usability trial. |

## Additional operational gap solutions

| ID | Evidence / boundary |
| --- | --- |
| OPS-1 | Order detail shows uncovered packets, batches, BOM input shortages and next action; read-only computation, including 250-uncovered test and 360 px browser check |
| OPS-2 | Batch screen hold/release with reason; held FG stays in ledger but leaves available and FEFO stock; API and 360 px browser checks |
| OPS-3 | Batch screen opens lot-to-production-to-dispatch/customer trace; API test checks input lot and salesman denial, browser opens trace |
| OPS-4 | Completed-run loss note shown with actor/time; retry and unchanged-movement test; no invented shortfall classification |
| OPS-5 | Offline queues multiple product lines; automatic same-user reconnect/reopen sync, retry button, browser restart and API two-SKU tests |
| OPS-6 | Invoice follow-up note and next-contact date; API test checks retry, permissions and no payment posting |

## Operator setup and local access

| ID | Evidence / boundary |
| --- | --- |
| SET-1 | Admin Setup lists named accounts and role; API lifecycle test covers create, disable, enable and reset; salesman denied |
| SET-2 | First-use password screen and self-service change; tests prove work endpoints denied until change and old tokens invalidated |
| SET-3 | Setup creates fictional customer, supplier, material, product and versioned shared-recipe BOM; API checks duplicate/invalid inputs and unchanged ledger; 360 px browser creates a second pack size and shared BOM; no bulk import |
| SET-4 | Business-only visible chrome; grouped daily/setup navigation; 360 px Playwright setup flow |
| SEC-1 | Durable username/address login attempt limit and generic failure test; served CSP, framing, MIME and API no-store headers verified locally |
| SEC-2 | Offline queue survives failed sync and restart; explicit device clear removes both queue and cached catalogue in browser test |

Known limitations and deliberate PS interpretations are listed in README; no Must/Should item was removed under the earlier cut line.

## Final contract-gap checks

Additional user-requested delivery improvements: UX-1 is covered by `scripts/react_ux_check.py` (mobile setup discovery, real staff creation, staff/customer search and access filter); OPS-7 by `scripts/backup.py` restoring a completed benchmark and reconciling it; DEV-1 by `.github/workflows/ci.yml`. Local equivalents previously passed. The first hosted run failed during Playwright installation; the runner fix is in source, but a successful hosted rerun and branch-protection configuration have not been verified in this documentation review. Details are in [CI](ci.md), [backup/restore](backup-restore.md) and [API](api.md).

| Item | Evidence |
| --- | --- |
| Native display-unit conversion (MAS-3 / PS 4.3) | `api/test_units.py`: 40 kg = 40000 g; 10.5 L = 10500 ml; SKU-specific cartons; invalid dimensions/fractional base units rejected; equivalent-unit retries and rollback. API and browser benchmark use kg/L inputs. |
| Invoice sharing (SAL-6 / PS 4.2) | Native PDF file sharing where supported; explicit WhatsApp/email draft links and manual attachment fallback. Browser checks verify invoice total, no token/local URL, and PDF download without sending a message. |
| Reconnect sync (STR-1 / PS 4.1) | `scripts/react_offline_check.py`: same-session reconnect and authenticated reopen drain the queue automatically; server request keys prevent duplicates. |
| Two-page design (PS 8) | `output/pdf/design-note.pdf`, generated from `docs/design.md`; page count and visual layout checked. |
| Final delivery | [Submission checklist](submission.md): video upload, latest pushed history, real-user timing and organizer deadline remain explicit applicant tasks. |
