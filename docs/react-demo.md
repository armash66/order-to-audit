# React demo walkthrough

Use a fresh isolated Compose project, never reset the working database. All accounts retain `DemoPass123!`. The public application is React on port 8000; FastAPI is available through `/api/`, including `/api/docs` only if explicitly routed (the default API documentation itself lives at `/docs` inside the API container).

1. Production → Receive materials: supplier, Flour, **60000** base units, total **2700** rupees. Optional batch/expiry fields are available.
2. Create production run: Murukku BOM, one batch. Open it; Issue raw materials: flour **40000**, oil **10500**, spice **1200**.
3. Complete production: **188** good, pouch total **194**, pouch damage **6**, carton total **9**, carton damage **0**. Review variance/cost.
4. Salesman A → Orders → Submit order: Retailer A, **150** packets. Customer prices appear before GST.
5. Admin → Orders → Open → Approve and reserve → Post invoice → download PDF → Dispatch remaining order.
6. Salesman B → Distributor B, **120**. Open stock check: **32** short. Admin approval fails without a posting.
7. Admin → A order → Record payment: **4000** rupees. Outstanding **3875**.
8. Admin → Production → run → Add overhead: Labour **1200**, Gas/power **600**. Display cost **31.14**, exact ratio retained.
9. Accountant → Reports: select the month's dates, review each register and export CSV/PDF. Owner → Dashboard.

Optional tools: Batches/reorder, Prices, Visits/GPS, Offline; returns/partial dispatch and mock documents are on order detail. Tally export is on Reports. The language chooser covers the operator interface in Tamil, Hindi and Marathi; see [localization](localization.md) for scope and validation.

Offline: open Offline online once, then capture without network. Add product lines, review the saved queue, and press **Confirm and sync orders** when connected. After a browser restart use `/offline` for cached capture; sign in as the original account to sync. Never promise closed-browser background sync.

Operational add-ons for a separate walkthrough: open B's order to see the batch count, BOM input gaps and receipt/run action; open Batches to hold/release a finished lot with a reason and trace an input lot to affected dispatches; add a loss explanation on a completed run; add a collection follow-up on an unpaid invoice and check the Dashboard when its contact date is due. These actions leave the nine-step benchmark figures unchanged unless a quality hold intentionally blocks dispatch.

Setup demonstration (outside the eight-minute benchmark video if time is tight): admin opens **Setup**, creates a fictional staff account and customer, then signs in as that staff member to replace the temporary password. Materials and products can also be created there; a new BOM version affects future runs only. Never use a real company or customer record for this internship submission.

Keep the narrated benchmark under eight minutes. Explain FastAPI services, SQLAlchemy Core transactions, the PostgreSQL factory lock and immutable ledger, and Alembic's schema-preserving adoption. Django remains only in the separate regression test image, not the running application.
