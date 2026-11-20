# Compliance evidence

Implementation evidence is automated unless marked browser/manual. Commands: `python manage.py test`, `python manage.py benchmark`. The expanded suite has 63 passing tests; the benchmark prints 49 expected/actual checks and also reads the golden workbook directly. This is local verification, not an organizer acceptance result.

## Section 5

| Step / expected result | Status | Evidence |
| --- | --- | --- |
| Masters/opening: flour 100 kg, oil 30 L, spice 5 kg, pouches 500, cartons 30, FG 50 | Pass | `inventory.seed.seed_benchmark`; opening checkpoint and source reconciliation |
| 1: flour purchase 60 kg at ₹45, closing 160 kg; average ₹43.125/kg | Pass | `reporting.benchmark.run_benchmark` step 1; purchase screen/register |
| 2: issue flour 40 kg, oil 10.5 L, spice 1.2 kg | Pass | Step 2; `production.tests`; source-linked negative movements |
| 3: 188 good, 194 pouches including 6 damaged, 9 cartons; FG 238; raw 120 kg/19.5 L/3.8 kg | Pass | Step 3; production run screen; exact cost, yield −6%, oil +5%, carton −10% flagged, pouch −3% unflagged |
| 4: salesman A submits 150 | Pass | Step 4 uses salesman identity; mobile `/orders/`; browser 360 px check |
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
| Must: login, salesman/admin/production | Pass | Five demo groups; `RoleAuditTests`, `ScreenTests`, CSRF/read-only tests |
| Must: product/customer/raw/BOM masters | Pass | Seed command, conversion tests, snapshotted versioned recipe/BOM tests |
| Must: mobile order/admin approval | Pass; human timing trial pending | `/orders/`, `/orders/<id>/`; concurrent reservation test; 360 px browser check |
| Must: GST invoice PDF | Pass | `PDFTests`; `/invoices/<id>/pdf/`; ₹ text extraction, intra/interstate and FY tests |
| Must: production updates raw/FG automatically | Pass | `production.tests`, nine-step scenario; issue/complete screens |
| Must: planned/actual consumption/yield | Pass | Run screen and production report; strict tolerance boundary/2% tests |
| Must: stock summary/ledger | Pass | `/stock/`, `/stock/<code>/`, `/sources/<id>/`; reconciliation and immutability tests |
| Must: sales and stock CSV | Pass | `/reports/`; `ReportTests.test_all_exports_and_dashboard` |
| Should: purchases/suppliers | Pass | Receipt screen; seed supplier; weighted-average purchase test/register |
| Should: payments/outstanding/ageing | Pass | Order payment form; collections/ageing CSV/PDF; historical cutoff/boundary tests |
| Should: cost per packet with overheads | Pass | Run screen; exact material and late overhead tests; known FG valuation limitation disclosed |
| Should: GST summary | Pass for exercise mapping | GST report: GSTR-1 B2B/category, GSTR-3B 3.1(a); not a filing payload |
| Should: tolerance alerts | Pass | Configurable basis-point setting; exact 3% not flagged; mutation check detects `>=` |
| Should: owner dashboard | Pass | `/` as owner; `dashboard` totals and read-only checks |
| Selected stretch: planning from shortages | Pass | Order detail; `SuggestionTests`: 32 → 1 batch; 250 → 2 needed/1 feasible |
| Selected stretch: offline capture/sync | Pass | `/offline/`; server ownership/retry/CSRF tests; browser offline restart and sync |
| Stretch: batch/expiry/FEFO | Pass with optional expiry | Batch screen/ledger; `inventory/test_batches.py`; expired issue rollback and lot reconciliation |
| Stretch: reorder alerts | Pass | Batch thresholds and owner dashboard; available-stock threshold test |
| Stretch: routes/GPS | Pass | Visits screen; consent, ownership and retry tests |
| Stretch: Tally export | Implemented; real import unverified | Reports ZIP; XML structure/balance/date tests; documented accounting-only format |
| Stretch: mock e-invoice/e-way bill | Pass as local mock | Order mock screen; exact JSON, both formats, deterministic MOCK responses and role tests |
| Stretch: Tamil | Implemented; native-speaker review pending | Production/receipt/run/variance labels; session tests |
| Optional: customer pricing/schemes | Pass for fixed prices | Prices screen; override/snapshot/catalogue test |
| Optional: partial dispatch/returns | Pass for resalable goods | Order screen; exact reservations, retry, over-dispatch/return and cumulative tax/value tests |

## Additional contract and delivery

| Requirement | Evidence / boundary |
| --- | --- |
| Immutable ledger and exact arithmetic | PostgreSQL update/delete trigger; integer base units/paise, Fraction; rollback and duplicate-request concurrency tests; mutation checks in stock/production validation notes |
| Corrections and audit | Reasoned adjustments; bounded exact-inverse run reversal tests; full unpaid/undispatched credit; draft invoice/run edit audit tests |
| Shared recipe / 500 g change | `production/test_fixtures.py` plus test; 33 added lines across two files after recipe separation; benchmark seed unchanged |
| One-command local run | Clean source-copy Compose startup with fresh DB and automatic role seed; no local `.env` required |
| Design/README | `docs/design.md`, README and this matrix |
| Public repo/history/video | Applicant must commit/push their work, confirm repository visibility and record/upload the ≤8-minute walkthrough; agent does not commit/push or send messages |
| Real-user order timing | Screen requires customer/product/quantity and submit; automated 360 px check passes. Applicant must perform the under-one-minute usability trial. |

Known limitations and deliberate PS interpretations are listed in README; no Must/Should item was removed under the earlier cut line.
