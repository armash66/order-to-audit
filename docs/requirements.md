# Requirements baseline — 19 November 2026

Source: supplied **Problem Statement - Winter Internship Application - 2026 .pdf**, sections 4 and 6; benchmark in section 5. This is a planned acceptance list, not a claim of implementation. Section 6 sets tiers; section 4 supplies detail. `Should` features needed by the mandatory benchmark remain release gates. Additional design constraints are explicitly identified below. All Must rows are committed. Should rows and the single selected stretch STR-4 are planned subject to the explicit cut line below. Optional/deferred rows retain checks for future scope.

| ID | Requirement | Tier | Acceptance check | PS source |
| --- | --- | --- | --- | --- |
| AUTH-1 | Login and restricted salesman, admin and production roles | Must | Salesman cannot open production screen or invoke its API; unauthenticated requests fail | 3, 6 |
| AUTH-2 | Read-only auditor and owner access | Should | Auditor can export but cannot mutate; owner can view summary | 3, 6 |
| MAS-1 | Product/SKU, customer, raw-material, packaging and BOM masters | Must | Seed loads section 5 quantities, rates, pack size, customer states and recipe | 4.3, 6 |
| MAS-2 | BOM standard quantities, packaging and expected yield | Must | One batch expands to 40 kg flour, 10 L oil, 1.2 kg spice, 200 pouches, 10 cartons; 200 expected packets | 4.3 |
| MAS-3 | Unit conversions by item/SKU | Must | 40 kg = 40,000 g; 10.5 L = 10,500 ml; one carton of this SKU = 20 packets; incompatible dimensions rejected | 4.3 |
| SAL-1 | Admin incoming queue, edits, approve/reject and stock check | Must | Edits to draft price/quantity are logged; A can be approved; B stays submitted with a computed shortage flag of 32 and cannot be fully approved; explicit rejection records a reason and releases any reservation | 4.2, 6 |
| SAL-2 | GST invoice with PDF | Must | A shows taxable ₹7,500, CGST ₹187.50, SGST ₹187.50, total ₹7,875; PDF includes supplier/customer GSTIN where applicable, HSN, place of supply and unique financial-year number | 4.2, 6 |
| SAL-3 | Mobile order entry and direct factory submission | Must | At 360 px width salesman selects retailer/distributor, adds SKU/quantity and submits without re-entry; typical order under one minute | 4.1, 6, 9 |
| SAL-4 | Price-list pricing | Must | Selecting Murukku populates ₹50 before tax; submitted order snapshots the price | 4.1 |
| SAL-5 | Own orders, statuses and customer-wise sales | Must | Salesman A sees submitted/approved/invoiced/dispatched progress, rejected outcome with reason, and own sales, but cannot read B's orders by URL/API | 4.1 |
| SAL-6 | Invoice share action | Should | A PDF can be shared through a user-triggered email or WhatsApp share action | 4.2 |
| SAL-7 | Dispatch reduces FG, invoice does not | Must | Step 5a approval: on hand/reserved/available = 238/150/88; 5b invoice: 238/150/88 and receivable ₹7,875; 5c dispatch: 88/0/88; retry cannot deduct twice | 4.2 |
| SAL-8 | Interstate tax and financial-year sequence | Must | Separate fixture for Karnataka invoice uses 5% IGST and zero CGST/SGST; April 1 starts a new unique FY sequence | 4.2 |
| SAL-9 | Customer-specific prices or schemes | Optional/deferred | Customer price overrides default and applied scheme is visible | 4.1 |
| SAL-10 | Partial dispatch and physical returns | Optional/deferred | Partial quantities reconcile to order; accepted return posts a linked positive movement exactly once | 4.2 |
| PRD-1 | Run records issues and automatically updates raw and FG stock | Must | Steps 2–3 leave flour 120 kg, oil 19.5 L, spice 3.8 kg, pouches 306, cartons 21 and FG 238 | 4.3, 6 |
| PRD-2 | Planned/actual consumption and yield | Must | Run displays 188/200 yield (−6%), oil 10.5/10 L (+5%) and each packaging variance | 4.3, 6 |
| PRD-3 | Run identity, batch scale, expected/actual output and wastage | Must | Run stores product, BOM snapshot, one batch, issued quantities, 188 good packets, 12 unclassified packet-equivalents of yield shortfall and 6 damaged pouches separately; no extra stock deduction for shortfall | 4.3 |
| PRD-4 | Configurable variance tolerance and alerts | Should; benchmark gate | Default 3% flags yield −6% and oil +5%; exact 3% does not flag; changed setting affects alert evaluation | 4.3, 6 |
| INV-1 | Separate raw, packaging and SKU stock summary and source ledger | Must | Opening + receipts − issues ± adjustments = closing for every item; every movement opens its source | 4.4, 6 |
| INV-2 | Explicit opening and adjustment documents | Must | Seed opening is traceable; signed adjustment requires reason and actor; no direct balance overwrite | 4.4, 7 |
| INV-3 | Work-in-progress inventory valuation | Optional/deferred | If added, issued cost transfers through WIP and clears on completion without duplicate consumption | 4.4 |
| PUR-1 | Purchases, supplier records and purchase rates | Should; benchmark gate | Receipt of 60 kg flour at ₹45 links supplier and adds 60 kg once | 4.5, 6 |
| COST-1 | Raw/packaging valuation and cost per good packet | Should; benchmark gate | Weighted flour ₹43.125/kg; materials ₹4,055; total ₹5,855; cost ₹31.14 displayed with method | 4.5, 6 |
| COST-2 | Labour, power/gas and other overhead allocation | Should; benchmark gate | ₹1,200 labour + ₹600 gas/power allocated over 188 good packets; zero output cannot divide | 4.5 |
| COST-3 | Selling-price margin by product | Should | Benchmark ₹50 − unrounded run unit cost displays ₹18.86 before tax; all cost inputs trace to sources | 4.5 |
| PAY-1 | Invoice allocations, collections and customer outstanding | Should; benchmark gate | ₹4,000 payment against A's ₹7,875 invoice leaves ₹3,875; duplicate payment is prevented | 4.2, 4.6, 6 |
| PAY-2 | Receivables ageing | Should | As-of date groups unpaid amount into current, 1–30, 31–60, 61–90, 91+ days overdue; buckets sum to outstanding; ₹3,875 is current on 19 Nov 2026, 30 days overdue in 1–30 on 19 Dec, and 31 days overdue in 31–60 on 20 Dec (no further payments) | 4.6, 6 |
| RPT-1 | Sales register and stock report CSV | Must | UTF-8 CSV opens in Excel with headers, units and exact amounts matching the ledger | 4.6, 6 |
| RPT-2 | Monthly/date-range filtering and CSV/PDF exports | Should; CSV benchmark gate, PDF cuttable | Every section 4.6 report exports CSV for a chosen range; boundary dates included; PDF uses one generic table renderer and may be deferred under the cut line | 4.6 |
| RPT-3 | Customer-wise and product-wise sales | Should; benchmark gate | A and Murukku show 150 packets, ₹7,500 taxable; unapproved B is excluded | 4.6 |
| RPT-4 | Outward GST summary mapped to GSTR-1/GSTR-3B fields | Should; benchmark gate | ₹7,500 taxable and ₹375 tax reconcile to invoice register, with documented field mapping; no filing claim | 4.6, 6 |
| RPT-5 | Purchase register | Should; benchmark gate | Flour purchase appears as 60 kg and ₹2,700; no invented input GST | 4.6 |
| RPT-6 | Production consumption, yield and wastage report | Should; benchmark gate | Reports expected 200, good 188, −6% yield, +5% oil and unclassified output shortfall separately from packaging damage | 4.6 |
| RPT-7 | Payments, collections and aged outstanding report | Should; benchmark gate | A shows invoiced ₹7,875, collected ₹4,000 and due ₹3,875 | 4.6 |
| DASH-1 | Owner dashboard | Should | Today's orders, raw/FG stock, variance alerts, cost and dues reconcile to underlying reports | 6 |
| STR-1 | Offline capture and sync | Stretch/deferred | Offline order survives restart and sync retries produce one server order | 4.1, 6 |
| STR-2 | Batch/expiry tracking and FEFO | Stretch/deferred | Dispatch selects earliest non-expired batch with remaining stock | 4.4, 6 |
| STR-3 | Raw-material reorder thresholds and low-stock alerts | Stretch/deferred | Crossing configured threshold raises item-specific alert | 6 |
| STR-4 | Production suggestion from pending-order shortages | Stretch/committed | B shortage 32 suggests ceil(32/200) = 1 standard batch. Show BOM needs versus remaining raw/packaging stock and warn if inputs cannot cover required batches. Independent 250-uncovered-packet fixture needs 2 batches, only 1 feasible (oil supports 1.95, pouches 1.53); shortages are 0.5 L oil and 94 pouches. Suggestion never posts stock | 6 |
| STR-5 | Salesman route/visit log and GPS check-in | Stretch/deferred | Visit records customer, time and consented position | 6 |
| STR-6 | Tally-compatible export | Stretch/deferred | Sample export imports or validates against a documented format; daily work remains independent | 4.6, 6 |
| STR-7 | Mock e-Invoice/e-Way Bill data | Stretch/deferred | Dummy payload validates against stated format and mocked response is clearly identified | 6 |
| STR-8 | Tamil floor interface | Stretch/deferred | Production workflow has Tamil labels with the same quantities and permissions | 6 |

Additional release constraints from sections 5, 7 and 8 and the requested design:

| ID | Requirement | Tier | Acceptance check |
| --- | --- | --- | --- |
| BEN-1 | Repeatable nine-step benchmark | Must | Automated scenario compares all nine steps, including 5a/5b/5c, and totals with benchmark.xlsx; demo follows the same order |
| DATA-1 | Real database, atomic posting and immutable movement ledger | Must | Failed posting changes nothing; repeated posting is idempotent; concurrent approvals cannot over-reserve; stock postings append in server-assigned sequence and older document dates cannot change prior valuation |
| DATA-2 | Exact money and quantity arithmetic | Must | Integer paise/base units plus precise valuation ratios reproduce benchmark without cumulative rounding drift |
| AUD-1 | User/time audit trail and corrective documents | Must | Draft invoice/run edits are logged; posted invoice corrected by credit note; run corrected by linked reversal, never deletion; permitted transitions and bounded correction restrictions are defined in assumptions.md |
| DEL-1 | Seed data and deployability | Must | Fresh instance loads dummy benchmark with one documented command; hosted demo or one-command local run has role logins |
| DEL-2 | README, design note and demonstrable delivery | Must | README covers setup, stack rationale, tier status, assumptions, gaps and benchmark; design note ≤2 pages; video ≤8 minutes shows mobile/admin; public repo has meaningful history |

Build order: masters/access/ledger → production → sales/invoice/dispatch → benchmark purchases/payments/cost/reports → remaining Should features → STR-4. Django, PostgreSQL and server-rendered pages are accepted; the local foundation is the first implementation chunk. These domain acceptance checks remain the future test list; none is marked passed yet.

## Cut line if time runs short

Defer in this order: **DASH-1 → AUTH-2 → RPT-2 report PDFs → STR-4**. Record any actual cuts in the README; none are cut yet. Invoice PDF (SAL-2), all Must requirements, all section 4.6 CSV reports and benchmark calculations remain in scope. Report PDFs use one generic table-to-PDF renderer, not seven bespoke layouts. Deferring them is an explicit gap against section 4.6, even though section 6 minimum exports are covered by CSV. SAL-6 is Should because section 6 does not list invoice sharing among the Must features.

Allowed state transitions and correction limits are defined in [assumptions.md](assumptions.md#allowed-transitions-implementation-contract). Paid/dispatched invoice correction and reversal of runs with subsequent affected-item stock postings are explicitly unsupported; failures must leave no writes. These limits keep AUD-1 implementable without refunds, returns or retroactive valuation.
