# Demo rehearsal — target under eight minutes

Use a fresh Compose project with opening stock only. Do not run `benchmark --persist` before recording the manual workflow; that would already have performed the steps. Default demo password is `DemoPass123!`. Open separate browser profiles for admin, production and salesmen so sessions do not replace one another. Set the sales viewport to 360 px. Use November 2026 dates; document dates are independent of posting sequence.

| Time | Action and evidence |
| --- | --- |
| 0:00–0:40 | Show opening stock and its source. Production → receive 60 kg flour, total ₹2,700 from Demo Flour Supplier. Show flour 160 kg. |
| 0:40–1:35 | Create one Murukku run. Issue flour **40000 g**, oil **10500 ml**, spice **1200 g**. Complete with pouch **194**, damage **6**; carton **9**, damage **0**; good **188**. Show FG 238 and variance flags. |
| 1:35–2:10 | Salesman A mobile screen → Retailer A, Murukku, quantity150 → submit. Explain price snapshot and own-order scope. Time this interaction; it should take less than one minute. |
| 2:10–3:10 | Admin opens queue/order → approve; explain reservation. Post invoice; show ₹7,875 PDF, ₹187.50 tax components and ₹ glyph. Dispatch; show FG88 and source ledger. |
| 3:10–3:50 | Salesman B submits Distributor B,120. Admin sees shortage32; approval is rejected without a posting. Show suggested one batch and inputs available. |
| 3:50–4:20 | Admin records A payment4000, shows due3875. |
| 4:20–5:10 | Admin opens run → labour1200, gas/power600. Show cost5855/188, ₹31.14 display, margin₹18.86; explain materials-only FG valuation. |
| 5:10–6:20 | Reports: November sales/GST/purchases/production/stock/collections; download CSV and generic PDF. Ageing as of19Dec and20Dec shows 1–30 then31–60. Stock uses actual posting date; select a range including today. |
| 6:20–7:15 | Owner dashboard; briefly show offline capture, restart/reload and automatic reconnect sync. Show Batch alerts, Visits, Tamil toggle and mock/export links briefly; explain Tally import and native-speaker review remain unverified. Keep core evidence within the eight-minute cap. |
| 7:15–7:50 | Explain immutable ledger, factory lock, atomic services, audit/reversal restrictions and passing tests. Show design note and disclosed assumptions. |

If recording at another date, the fixed benchmark command still uses 19 November 2026; manual screen transactions default to today. Choose the report dates accordingly. The fixed ageing boundary assertions are automated independently.

## Interview rehearsal

1. **Two admins approve orders at once: why can neither oversell?** Trace the shared row lock, committed reservation-source query and transaction boundary. Likely weak spot: distinguishing a database lock from a Python process lock, and explaining why all stock/reservation writers must obey it.
2. **How does a lost HTTP response avoid posting twice?** Explain stored request keys, payload comparison, uniqueness constraints and lock/transaction order. Likely weak spot: confusing button disabling with server idempotency, or allowing a changed retry to succeed.
3. **Why does issuing 1 g from 3 g/10 paise cost 3, then 4, then 3?** Derive remaining weighted average with Fraction and depletion. Likely weak spot: rounding the unit rate early or describing `Decimal` alone as a rounding policy.
4. **What changes for a 500 g SKU sharing the recipe?** Raw recipe stays shared; expected packets and packaging change in a SKU-specific BOM and are snapshotted. Likely weak spot: assuming a recipe fixes packet count or claiming food mass/yield physics that the exercise does not establish.
5. **Why can a run not be reversed after dispatch?** Explain inverse source values, dependent stock events, reservations and avoiding cascading revaluation. Likely weak spot: confusing bookkeeping reversal with physically recovering ingredients, or forgetting overhead exclusion.
6. **How do historical ageing and GST reports remain correct after later payments/credits?** Explain invoice snapshots, event dates, as-of filters and per-line tax rounding. Likely weak spot: filtering on current invoice status alone, subtracting future payments, or presenting the exercise mapping as filing-ready GST compliance.
