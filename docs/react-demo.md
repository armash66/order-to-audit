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

Optional tools: Batches/reorder, Prices, Visits/GPS, Offline; returns/partial dispatch and mock documents are on order detail. Tally export is on Reports. The language chooser has partial navigation/production translations with English fallback.

Offline: open Offline online once, then capture without network. Active-page reconnection syncs automatically. After a browser restart use `/offline` for cached capture; sign in as the original account and open Offline to sync. Never promise closed-browser background sync.

Keep the narrated benchmark under eight minutes. Explain FastAPI services, SQLAlchemy Core transactions, the PostgreSQL factory lock and immutable ledger, and Alembic's schema-preserving adoption. Django remains only in the separate regression test image, not the running application.
