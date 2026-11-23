# Operations guide

[Documentation](README.md)

## Set up the factory

Sign in as admin. In **Setup**, create separate staff accounts, customers and suppliers, materials, sellable products and BOM versions. Temporary staff passwords must be replaced on first sign-in. For the internship submission use fictional records only.

Materials use integer grams, millilitres or pieces. Products define pack size, list price, HSN and packets per carton. A BOM combines a versioned ingredient recipe with SKU-specific packaging and expected packets. New versions affect future runs.

## Roles

Salespeople see their own orders, customer sales and visits. Production staff record receipts and production. Admins manage billing, payments and setup. Accountants and owners inspect records and export reports without posting business transactions. Owners also see the dashboard.

## Sales

1. **Orders → Submit order**: select customer, quantity and packets or cartons for each product. Carton size comes from that SKU; prices are per packet from the applicable price list.
2. Admin opens the order and reviews stock. Approval reserves available finished goods.
3. **Post invoice**: creates the numbered GST invoice; it does not move stock.
4. **Dispatch remaining order** or **Partial dispatch**: moves stock and releases the dispatched reservation.
5. **Record payment**: allocates the payment to that invoice and reduces outstanding.

Rejecting a pre-invoice order requires a reason and releases its reservation. Full cancellation credit requires an unpaid, undispatched invoice. Sealed-goods returns have their own quantity and tax checks. See [boundaries](reference.md) before using corrections.

## Production

1. **Receive materials**: select supplier/item, quantity and its unit (g/kg, ml/L or pieces), then the total amount in rupees. Add batch and expiry details when known. For the benchmark enter 60 kg flour and ₹2,700.
2. **Create production run**: select BOM version and batch count.
3. Open the draft and **Issue raw materials** using actual quantities and units: 40 kg flour, 10.5 L oil and 1.2 kg spice in the benchmark. Conversion must resolve to a whole gram, millilitre or piece.
4. **Complete production**: enter good packets and total packaging issued, including damaged packaging. Enter damage separately for reporting.
5. Review consumption and yield variance, then add labour, power or other overheads.

The service posts stock automatically at issue and completion. A variance flags only when its absolute value exceeds the configured tolerance. Changing tolerance also changes alerts shown on past reports.

## Stock and quality

**Stock** shows ledger-derived quantities. Open an item and then a movement to inspect its source document. **Batches** shows expiry and quality status, recall links and reorder alerts. Held or expired stock is unavailable for new fulfilment even though it remains physically on hand.

## Reports

Select the report and date range in **Reports**, then export CSV or PDF. Report families cover sales, customer/product sales, GST, purchases, stock, production, collections and ageing. Ageing uses the selected end date as its as-of date. Stock uses posting dates; commercial registers use document dates.

## Offline orders and visits

Open **Offline** once while connected to load the catalogue. Save orders on the private device. While that page is active and signed in as the original user, saved orders sync automatically on reconnect or page reopen. Failed requests remain queued; **Confirm and sync orders** retries them. The server confirms current prices and prevents duplicate submission. An offline browser restart still requires online sign-in before sync.

After a browser restart, open `/offline` for cached capture. **Clear this device** removes the cached catalogue and all unsynced orders after confirmation. Sign-out alone does not clear them.

**Visits** supports an optional location capture. GPS requires consent; denied permission does not prevent recording a visit.

## Language

Use the language selector at sign-in or in the workspace. It changes operator text and persists on that browser. Brand names, codes, newly entered business names and exported documents are not automatically translated.
