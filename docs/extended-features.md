# Extended features and prototype boundaries

All optional sales features and eight section 6 stretch categories were authorized after the core benchmark passed. DEC-39–47 explain the choices. The benchmark seed remains unchanged; optional fixtures do not alter its numbers.

| Feature | How to use | Automated evidence |
| --- | --- | --- |
| Customer prices/schemes | Admin → Prices; set a customer/SKU price and scheme label. New orders snapshot it; existing orders retain their price. | `sales/test_extended.py`: override, snapshot and catalogue |
| Partial dispatch | On an invoiced order enter quantities in the partial-dispatch form. Unshipped quantities remain reserved. | Partial/retry/over-dispatch and reservation tests |
| Returns | Admin records resalable sealed goods against dispatched quantities, with reason. Original tax/value is credited cumulatively. | Paid return, over-return, exact rounding residual tests |
| Offline orders | Salesman opens Offline online once, captures without network; page reconnect/reopen automatically syncs with the original account. | Server retry/ownership tests; `scripts/extended_browser_check.py` browser restart/reconnect |
| Batch/expiry/FEFO | Enter receipt batch/expiry and run output expiry; Batch alerts and ledger show allocations. Expired stock cannot be issued or dispatched. | `inventory/test_batches.py`: FEFO, expired-stock rollback, reconciliation |
| Reorder alerts | Admin sets raw-material minimum in Batch alerts; owner dashboard shows quantities at/below threshold. | Reorder/available-stock tests |
| Production planning | Order detail shows aggregate shortage, batches needed and BOM input feasibility. | `SuggestionTests`: 250 uncovered, two needed, one feasible |
| Routes/GPS | Salesman → Visits; route/customer/note, optional consent then Capture location. Browser permission denial still permits a visit without location. | `extensions/tests.py`: consent, exact coordinates, retry, own visits; browser uses fictional coordinates |
| Tally export | Reports → Tally ZIP for selected dates. Import masters before vouchers into a separate demo company. | XML parsing, balanced paise amounts, date filters |
| Mock e-invoice/e-way bill | Invoiced order → Mock government documents; admin generates and downloads explicitly MOCK JSON. | Exact amounts, both formats, retry mismatch, role restrictions |
| Tamil floor UI | Production → Tamil; session preference applies to receipt/run/variance labels; English toggle restores English. | Session/template checks and browser rendering |

## What each new file does

- `sales/test_extended.py` tests prices, partial dispatch and return accounting; sales migrations add those source documents and links.
- `inventory/test_batches.py` checks lot allocation, expiry and reorder behavior; migration 0011 derives LEGACY allocations from existing movements without rewriting stock.
- `extensions/models.py`, `services.py`, `tests.py` hold visit/mock documents, authorized operations and their tests; its migration creates their tables.
- `webapp/extra_views.py` adapts pricing, batches, visits, mock downloads and Tally exports to HTTP. `webapp/templatetags/floor_language.py` contains the small production translation catalogue.
- `templates/batches.html`, `pricing.html`, `visits.html`, `mock_documents.html` are their server-rendered screens. `static/prices.js` refreshes visible customer prices; `static/visits.js` requests consented browser location.
- `scripts/extended_browser_check.py` exercises the new screens and offline restart/reconnect on an isolated instance after the original browser walkthrough.

## Explicit limitations

Tally XML follows the [published import envelope/examples](https://help.tallysolutions.com/sample-xml/). Automated checks establish XML structure and balanced vouchers, not successful import into a real Tally installation. No input GST is invented. Export is accounting-only and includes a README; avoid overlapping repeated imports.

The local fiscal mock uses selected fields from the [published e-invoice schema](https://einvoice6.gst.gov.in/content/notified-e-invoice-schema/). It is not a complete government-schema validator or network integration. All identities/addresses are fictional, every reference begins MOCK, and an e-way-bill mock grants no transport authorization.

Existing stock has unknown expiry unless supplied at entry. FEFO uses known non-expired dates first, then unknown dates; cost remains item-level weighted average. Returned lots conservatively inherit the earliest known expiry among original dispatched lots. There is no separate WIP stock account; issued runs retain their source costs until completion.

Schemes mean fixed customer prices with labels, not arbitrary discount rules. Returns may create negative outstanding/customer credit, but cash refunds are not implemented. GPS is a single consented visit position, not tracking or route optimization. Offline synchronization needs the page active/reopened, not a background service.

Tamil covers the floor workflow labels and known demo item names. Validation errors and unknown names fall back to English; native-speaker review remains pending. No external import acceptance, government validity or human language review is claimed.
