# Benchmark and operating boundaries


| Check | Result |
| --- | --- |
| Flour / oil / spice closing | 120 kg / 19.5 L / 3.8 kg |
| Pouches / cartons | 306 / 21 |
| FG after run / after dispatch | 238 / 88 packets |
| Approval and invoice: on-hand / reserved / available | 238 / 150 / 88 |
| Dispatch: on-hand / reserved / available | 88 / 0 / 88 |
| Yield / oil / cartons / pouches variance | −6% flagged / +5% flagged / −10% flagged / −3% not flagged |
| A invoice | ₹7,500 + ₹187.50 CGST + ₹187.50 SGST = ₹7,875 |
| A collected / outstanding | ₹4,000 / ₹3,875 |
| B | Submitted, shortage 32; no invoice or reservation |
| Weighted flour / materials / total cost | ₹43.125/kg / ₹4,055 / ₹5,855 |
| Cost and margin per good packet | Exact ₹5,855/188; displayed ₹31.14; margin ₹18.86 |

**Deliberate interpretations:** the uniform tolerance rule also flags cartons (−10%), beyond the PS's named yield/oil alerts. Nine cartons are recorded as given, with eight packets loose. The 12 packet-equivalents of output shortfall are **unclassified**; six damaged pouches are separate packaging damage already included in the 194 issued. No assumed 6 + 6 food-loss split and no additional stock deduction. No benchmark quantity or money result differs from the golden file.

## Boundaries and known gaps

- FG valuation is materials-only. Opening FG value is unknown, so aggregate FG value and COGS remain unknown. Late overhead changes run cost, not past FG movements.
- Tolerance changes apply retroactively to displayed alerts. Production reports select runs by document date and show their currently recorded costs. Stock reports use posting date/sequence; commercial registers use document dates. Ageing is due-date based, due on invoice date, and ignores its range start.
- Payments are allocated in full to one invoice; several payments per invoice are supported. Full cancellation credit is unpaid/undispatched only. Partial dispatch and resalable returns are supported; returns credit original tax and restore original dispatch value. Paid returns may leave customer credit; no cash-refund settlement workflow.
- Run reversals correct recording errors, not physical production. Later or intervening affected-item stock events and reserved FG block reversal. No cascading revaluation, fractional planned batches or ingredient substitution.
- Posted sources are frozen by services; privileged ORM/SQL can bypass this. The database trigger protects movement update/delete only. Reconciliation detects source/ledger disagreement. Direct database owners are trusted.
- Native file sharing depends on the device. Desktop fallback offers WhatsApp/email drafts with invoice number/total; users download and attach the PDF manually. The app does not send messages, expose bearer tokens or pretend localhost links are public customer links.
- Offline capture accepts multiple SKU lines and automatically attempts sync on reconnect or page reopen while the Offline page is active, authenticated and online. The server confirms pricing at sync. Cached catalogue/queued data remains across sign-out; **Clear this device** removes both after confirmation. Sync requires the original account. No closed-browser background sync or multi-device conflict resolution.
- GST is the exercise's fixed 5%, with per-line component rounding. GSTR labels are explanatory mappings, not filing-ready payloads. GSTINs and HSN are fictional. Setup creates new masters but does not edit historical master records or import large customer lists.
- Expiry is optional: migrated stock has labelled LEGACY lots with unknown expiry. FEFO excludes expired stock and uses unknown-expiry lots last; valuation stays item-level weighted average. Returned batches use the earliest known original expiry conservatively. Lot allocations are service-frozen and reconciled, not protected by additional database triggers.
- Quality holds cover finished lots only. A recall trace uses recorded allocations and can identify dispatched customers, but does not send notifications or infer pre-opening provenance. Holds and loss/follow-up notes are audited service decisions, without extra stock movements.
- Customer schemes are fixed price overrides, not a promotion engine. Tally XML has structure/balance tests but has not been imported into Tally. Mock government documents are not valid fiscal documents. The four-language operator catalogue covers sign-in, setup, daily work, reports and offline capture. Seed names with catalogue entries are translated; new user-entered names and legal invoice/export content remain as recorded. Unfamiliar API errors use a localized retry message. Native-speaker review is pending.
- Demo credentials and default secrets are suitable only for localhost. The database-backed login limit, role checks and browser headers improve this local build; public hosting still needs HTTPS, unique secrets, changed demo passwords and a deployment security review. Images/transitive dependencies are not fully digest-locked. The video/public repository submission and organizer deadline/contact verification remain human delivery tasks.
