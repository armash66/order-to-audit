# React demo walkthrough

## Prepare a clean recording instance (PowerShell)

Run in the repository terminal. Keep this terminal open: the variables identify this recording instance. These commands use a new database volume and do not reset localhost:8000.

```powershell
$demoProject = 'ota-video-' + (Get-Date -Format 'yyyyMMddHHmmss')
$demoOverride = Join-Path $env:TEMP ($demoProject + '.yaml')
@'
services:
  db:
    ports: !reset []
'@ | Set-Content -LiteralPath $demoOverride -Encoding utf8
$env:WEB_PORT = '8020'
docker compose -p $demoProject -f compose.yaml -f $demoOverride up --build -d
docker compose -p $demoProject -f compose.yaml -f $demoOverride ps
docker compose -p $demoProject -f compose.yaml -f $demoOverride exec -T api python -m api.cli benchmark
```

Wait for healthy services. The last command must print **49 checks passed** and **Scenario rolled back**. Run it BEFORE manual transactions; it requires opening-only data. Save its terminal output for the end of the video. Open http://localhost:8020. If that port is occupied, choose another unused port before starting.

Demo logins: `production`, `salesman_a`, `salesman_b`, `admin`, `accountant`, `owner`. Password for each: `DemoPass123!`. Use these only for the local fictional demo.

## Record and narrate

Use your screen recorder with screen capture and microphone enabled. Capture the browser window at 1920×1080 or 1280×720, keep browser zoom at 100%, silence notifications and record a ten-second microphone test first. Avoid displaying your desktop, private tabs or environment files. Keep the final video under eight minutes; aim for 7:30.

For the salesman segment, use Chrome/Edge developer tools, toggle device emulation and set the viewport to 390×844. Return to desktop mode for admin work. This demonstrates the mobile layout; do not claim it is a physical-phone recording.

Use the nine numbered steps below for exact entries. Narrate in your own words using this script:

1. **Opening (0:00–0:25):** “Order-to-Audit connects field orders, production, stock and collections for a small snack factory. Each stock movement links to its source document.” Open Stock and show opening flour 100 kg and finished goods 50 packets.
2. **Purchase (0:25–0:55):** “I receive 60 kg of flour for ₹2,700. Flour is now 160 kg. Weighted-average valuation combines the opening and purchase costs.” Enter the receipt once.
3. **Issue (0:55–1:35):** “One batch expects 200 packets. Actual oil is 10.5 litres against a 10-litre standard.” Create and issue the run using the values below.
4. **Complete (1:35–2:35):** “The run produces 188 good packets. I issue 194 pouches, including six damaged, and nine cartons.” Show output, consumption and damage sections. “Yield is −6%, oil is +5%, and cartons are −10%. Pouches are exactly −3%, so they do not exceed the 3% tolerance. The 12-packet shortfall remains unclassified; packaging damage is separate.” Show FG 238 and raw balances.
5. **Mobile order (2:35–3:10):** Sign out, sign in as salesman_a in mobile mode. “The salesman submits 150 packets for Retailer A directly to the factory.” Submit once.
6. **Billing (3:10–4:20):** Sign in as admin on desktop, open A's order. “Approval reserves 150 packets but leaves 238 on hand; available stock is 88. Invoicing also leaves physical stock unchanged.” Show PDF: ₹7,500 + ₹187.50 CGST + ₹187.50 SGST = ₹7,875. Dispatch. “Dispatch now reduces on-hand stock to 88 and clears the reservation.”
7. **Shortage (4:20–4:55):** Sign in as salesman_b, submit 120 packets for Distributor B. Switch to admin and open it. “Only 88 are available, so the shortage is 32. The order stays submitted rather than overselling. Karnataka would use IGST if invoiced.”
8. **Payment (4:55–5:20):** Open Retailer A's order and record ₹4,000. “The outstanding balance is now ₹3,875.”
9. **Cost (5:20–6:05):** Open the production run, add Labour ₹1,200 and Gas/power ₹600. “Materials and packaging cost ₹4,055; overheads bring the total to ₹5,855. Dividing by 188 good packets gives ₹31.14 displayed, with the exact fraction retained. Money is stored in integer paise. Finished-goods valuation excludes overheads.”
10. **Reports (6:05–7:20):** Sign in as accountant, select November 2026, show sales, GST, purchase, stock/ledger, production and collections/ageing reports. Export a CSV and PDF, open at least one. “Reports reuse the posted transactions; the accountant has read-only access.” Briefly show the owner dashboard.
11. **Close (7:20–7:50):** Show the saved successful benchmark terminal output and README/design note. “These 49 automated checks exercise the scenario through the real services. The README documents assumptions and limitations, and Docker Compose runs the application locally.”

Rehearse once. A rehearsal creates transactions: start a NEW project name using the preparation commands for the actual recording. Do not rerun the manual scenario on the same database. The existing `scripts/record_demo.py` still targets old dropdowns/accordions and is not a supported recording route for this UI.

## Finish

Export the final narrated video as MP4, play it end to end and verify readable numbers, audible narration and duration under eight minutes. Upload as unlisted YouTube or a Drive video viewable without requesting access. Test the link signed out and add it to README. Do not commit the video binary to Git.

Stop only the recording instance afterwards; retain its volume for recovery:

```powershell
docker compose -p $demoProject -f compose.yaml -f $demoOverride down
Remove-Item Env:WEB_PORT
```

Use a fresh isolated Compose project, never reset the working database. All accounts retain `DemoPass123!`. The public application is React on port 8000; FastAPI is available through `/api/`, including `/api/docs` only if explicitly routed (the default API documentation itself lives at `/docs` inside the API container).

1. Production → Receive materials: supplier, Flour, quantity **60**, unit **kg**, total **2700** rupees. Optional batch/expiry fields are available.
2. Create production run: Murukku BOM, one batch. Open it; Issue raw materials: flour **40 kg**, oil **10.5 L**, spice **1.2 kg**.
3. Complete production: **188** good, pouch total **194**, pouch damage **6**, carton total **9**, carton damage **0**. Review variance/cost.
4. Salesman A → Orders → Submit order: Retailer A, **150** packets. Customer prices appear before GST.
5. Admin → Orders → Open → Approve and reserve → Post invoice → download PDF → Dispatch remaining order.
6. Salesman B → Distributor B, **120**. Open stock check: **32** short. Admin approval fails without a posting.
7. Admin → A order → Record payment: **4000** rupees. Outstanding **3875**.
8. Admin → Production → run → Add overhead: Labour **1200**, Gas/power **600**. Display cost **31.14**, exact ratio retained.
9. Accountant → Reports: select the month's dates, review each register and export CSV/PDF. Owner → Dashboard.

Optional tools: Batches/reorder, Prices, Visits/GPS, Offline; returns/partial dispatch and mock documents are on order detail. Tally export is on Reports. The language chooser covers the operator interface in Tamil, Hindi and Marathi; see [localization](localization.md) for scope and validation.

Offline: open Offline online once, then capture without network. Saved orders automatically sync when this page reconnects or reopens with the original account signed in. Failed requests stay queued; **Confirm and sync orders** retries them. After a browser restart use `/offline` for cached capture, then sign in online and reopen Offline to sync. Never promise closed-browser background sync.

Operational add-ons for a separate walkthrough: open B's order to see the batch count, BOM input gaps and receipt/run action; open Batches to hold/release a finished lot with a reason and trace an input lot to affected dispatches; add a loss explanation on a completed run; add a collection follow-up on an unpaid invoice and check the Dashboard when its contact date is due. These actions leave the nine-step benchmark figures unchanged unless a quality hold intentionally blocks dispatch.

Setup demonstration (outside the eight-minute benchmark video if time is tight): admin opens **Setup**, creates a fictional staff account and customer, then signs in as that staff member to replace the temporary password. Materials and products can also be created there; a new BOM version affects future runs only. Never use a real company or customer record for this internship submission.

Keep the narrated benchmark under eight minutes. Explain FastAPI services, SQLAlchemy Core transactions, the PostgreSQL factory lock and immutable ledger, and Alembic's schema-preserving adoption. Django remains only in the separate regression test image, not the running application.

## Recording schedule

Prepare desktop (1280 px) and mobile (360 px) windows. Use a fresh isolated instance for each complete rehearsal; the browser benchmark creates real transactions. The automated benchmark command instead rolls back and must run on opening-only data.

| Time | Show |
| --- | --- |
| 0:00–0:25 | Opening stock and one source-document drill-down |
| 0:25–0:55 | Step 1 purchase; flour 160 kg and weighted rate ₹43.125/kg |
| 0:55–1:35 | Step 2 actual raw issue and the snapshotted BOM |
| 1:35–2:35 | Step 3 output, packaging, yield/oil/carton alerts and FG 238 |
| 2:35–3:10 | Step 4 salesman A on mobile, 150 packets |
| 3:10–4:20 | Step 5 approval 238/150/88; invoice unchanged; PDF taxes; dispatch 88/0/88 |
| 4:20–4:55 | Step 6 salesman B, shortage 32, still submitted |
| 4:55–5:20 | Step 7 ₹4,000 collection, ₹3,875 outstanding |
| 5:20–6:05 | Step 8 ₹1,800 overhead, total ₹5,855/188, display ₹31.14 |
| 6:05–7:20 | Step 9 accountant report families, CSV/PDF and owner dashboard |
| 7:20–7:50 | Completed 49-check benchmark output, two-page design and README limitations |

Explain that the 12 missing packet-equivalents remain unclassified and six damaged pouches are separate packaging damage. At exactly −3% pouches do not flag; the uniform rule also flags cartons at −10%. Nine cartons leave eight packets loose.

Download the invoice, then show the WhatsApp/email draft links without sending a message. Desktop users attach the PDF manually; links never carry a bearer token or localhost PDF URL.

Stock report filters must include the actual posting dates; commercial registers use document dates. A human must rehearse placing an order within one minute: automated browser timing cannot prove that usability target.

Record your own narration, upload the finished video to unlisted YouTube or viewable Drive, verify it while signed out, and add its link to README. This upload remains pending; see the [submission checklist](submission.md).
