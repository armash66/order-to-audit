# Operations guide

[Documentation](README.md)

## Set up the factory

Sign in as admin. Use the sidebar for daily work and setup; on a phone, scroll the navigation horizontally. The always-visible profile section beneath the language buttons contains **Change password** and **Sign out**. In **Setup**, create separate staff accounts, customers and suppliers, materials, sellable products and BOM versions. Open a staff row to enable/disable that account or reset its temporary password. Temporary staff passwords must be replaced on first sign-in. For the internship submission use fictional records only.

The compact **Factory setup checklist** shortcuts on the admin Orders page links directly to Staff, Customers & suppliers, Materials & products and Recipes. Counts include demo records and are review prompts, not proof that your factory is configured. Staff, customer, order, production and stock lists support **Search records**. Visible status/access/category tabs filter applicable lists. Click a column heading to sort; lists show 20 rows per page. **Clear filters** restores the list. Search and sorting cover records already loaded on that screen, not a server-wide index. Orders and production show their record lists before creation tools. The Next step panel suggests an action for the selected record. Click an action button to open its focused form; choose visible options or search a longer list, review the values, then submit. Close or Escape dismisses the form without posting. Successful posting actions state what changed in stock, reservation or receivables.

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

1. **Receive materials**: select supplier/item, quantity and its unit (g/kg, ml/L or pieces), then the rate in rupees per selected unit. The total is calculated with exact decimal arithmetic and half-up rounding to paise. **Invoice total** allows a supplier total to be entered directly. Changing the item or unit clears the rate. Add batch and expiry details when known. For the benchmark enter 60 kg flour at ₹45/kg; the calculated total is ₹2,700.
2. **Create production run**: select BOM version and batch count.
3. Open the draft and **Issue raw materials** using actual quantities and units: 40 kg flour, 10.5 L oil and 1.2 kg spice in the benchmark. Conversion must resolve to a whole gram, millilitre or piece.
4. **Complete production**: enter good packets and total packaging issued, including damaged packaging. Enter damage separately for reporting.
5. Review consumption and yield variance, then add labour, power or other overheads.

The service posts stock automatically at issue and completion. A variance flags only when its absolute value exceeds the configured tolerance. Changing tolerance also changes alerts shown on past reports.

Open a production run to review four sections: **Production output**, **Material consumption**, **Run costing** and **Packaging damage**. Planned and issued quantities appear side by side with their units, percentage variance and a text flag. Missing actual output is shown as not recorded, rather than zero. Costing separates materials, overheads, total cost, cost per good packet and margin. Packaging damage remains separate from the unclassified output shortfall. Actions appear after this summary.

## Stock and quality

**Stock** shows ledger-derived quantities. Dashboard stock, stock summary and item ledger quantities show one value per cell. Use the g/kg and ml/L buttons in the Quantity column header to select the display units independently; pieces and packets retain their units. Each table starts in kg/L. Numeric headers and cells align right. Unknown valuation means a source cost is missing, not zero; the benchmark opening finished goods have no supplied cost. Conversion is display-only; exports retain their existing base-unit columns. Open an item to see its stock value divided by quantity on hand, the weighted-average rate, and the rate of each movement. Rates use up to six decimal places; repeating results carry an approximation mark. Open a movement to inspect its source document. **Batches** shows expiry and quality status, recall links and reorder alerts. Held or expired stock is unavailable for new fulfilment even though it remains physically on hand.

## Reports

Choose a visible report button and date range in **Reports**, then export CSV or PDF. Report families cover sales, customer/product sales, GST, purchases, stock, production, collections and ageing. Ageing uses the selected end date as its as-of date. Stock uses posting dates; commercial registers use document dates. Table pagination affects the screen only; exports include the full selected report.

## Offline orders and visits

Open **Offline** once while connected to load the catalogue. Save orders on the private device. While that page is active and signed in as the original user, saved orders sync automatically on reconnect or page reopen. Failed requests remain queued; **Confirm and sync orders** retries them. The server confirms current prices and prevents duplicate submission. An offline browser restart still requires online sign-in before sync.

After a browser restart, open `/offline` for cached capture. **Clear this device** removes the cached catalogue and all unsynced orders after confirmation. Sign-out alone does not clear them.

**Visits** supports an optional location capture. GPS requires consent; denied permission does not prevent recording a visit.

## Language

Use the visible language buttons at sign-in or in the workspace. It changes operator text and persists on that browser. Brand names, codes, newly entered business names and exported documents are not automatically translated.
