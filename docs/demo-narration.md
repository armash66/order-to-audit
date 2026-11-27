# Order-to-Audit: phone cue sheet for your demo

Keep this document open on your phone while you operate the laptop. Read only the quoted paragraphs aloud. The **Do** lines tell you what to click; they are not narration. Speak in your normal voice and pause while results appear. Timings include clicks and sign-ins: rehearse once and keep the final video under eight minutes.

## Before pressing Record

1. Use the fresh instance at **http://localhost:8020**, prepared with the [exact setup commands](react-demo.md).
2. Run the benchmark before any manual entries. Confirm **49 checks passed. Scenario rolled back.** Keep that terminal output available for the closing segment. Do not rerun it after the manual scenario.
3. Sign in as **production**, password **DemoPass123!**, and open **Stock**. Set the Quantity column switches to **kg** and **L**.
4. Confirm opening stock: flour 100 kg, oil 30 L, spice 5 kg, pouches 500, cartons 30, finished goods 50 packets. If these differ, stop and check the instance before recording.
5. All accounts below use **DemoPass123!**. Use sidebar **Sign out** before changing accounts.
6. Leave document dates on today's default. For this November recording, reports must include **1–30 November 2026**, including the actual posting date.
7. Current amount inputs accept **rupees**. Enter 2700, 4000, 1200 and 600 as specified. Do not multiply them by 100.
8. Record a ten-second microphone test and play it back. Silence notifications and close private windows. If capturing only Chrome, deliberately switch the recording source when showing VS Code at the end; changing windows alone does not change a window-only capture.

## Introduction — 0:00–0:20

**Account: production. Screen: Stock.**

**Do:** Start recording with the application name and Stock page visible. Keep the cursor still during the introduction. You can speak off camera; a separate title slide is optional.

“Hi, I’m Armash. I built Order-to-Audit for the CDI internship task. The idea is to help a small food factory keep orders, production and stock connected, without entering the same information again. I’ll show you how it works using the murukku scenario from the problem statement.”

## Opening stock — 0:20–0:30

**Do:** Point to Flour and Murukku in the stock table.

“I’m starting with a fresh demo database. Here we have 100 kilos of flour and 50 finished packets. Let’s record the flour purchase first.”

## Receive the flour — 0:30–1:00

**Account: production. Screen: Production → Receive materials.**

**Do:** Select Demo Flour Supplier and Flour. Enter quantity **60**, unit **kg**, then **Rate (₹ per selected unit): 45**. Confirm the calculated total is **2700.00**. Leave batch/expiry blank and date unchanged. Speak while filling; submit once after the first paragraph. Open Stock and show flour **160 kg**, then open the Flour row. Show **Stock valuation: ₹6,900 ÷ 160 kg = ₹43.125/kg** and the movement rates **₹42/kg** and **₹45/kg** before the next paragraph.

“The supplier delivers 60 kilos of flour at ₹45 a kilo. I enter the quantity and rate, and the form calculates ₹2,700 for me.

After saving, I can open Flour and see where the valuation comes from. The opening stock was ₹42 a kilo, and this purchase was ₹45.

Together, that’s ₹6,900 worth of flour across 160 kilos. Dividing gives ₹43.125 per kilo. That’s the weighted average used for production issues.”

**Your cue, not narration:** Stay in **Unit rate** mode for this demo. **Invoice total** is available when a supplier gives only a total amount. Changing the item or unit clears the rate, so choose **kg before entering 45**. Rate calculation uses integer arithmetic and rounds the final total half-up to paise. The ledger shows rates derived from posted values; it does not store the typed rate as a separate quote.

## Start production — 1:00–1:40

**Account: production. Screen: Production → Create production run.**

**Do:** Select the Murukku 200 g BOM and **1 batch**. Save, open the run, then click **Issue raw materials**. Enter Flour **40 kg**, Cooking oil **10.5 L**, Spice mix **1.2 kg**. Submit once as you reach “I’m saving the actual issue.”

“Now I’ll start one batch. The recipe tells us what we expect to consume and that we expect 200 packets from it.

The important bit is that the operator records what was actually issued. Here, flour and spice match the recipe, but oil is 10.5 litres instead of 10. If I just deducted the recipe quantities automatically, that extra half-litre would disappear from the records.

I’m saving the actual issue. Raw stock goes down at this point, but finished stock doesn’t go up yet. We haven’t recorded any finished packets.”

## Complete the batch — 1:40–2:45

**Account: production. Screen: The same run → Complete production.**

**Do:** Enter good packets **188**, pouches total issued **194**, pouches damaged **6**, cartons total issued **9**, cartons damaged **0**. Submit after the first paragraph. Show **Production output**, then **Material consumption**, pointing to oil, pouches and cartons as you explain them. Finish by opening Stock.

**Check:** Flour **120 kg**, oil **19.5 L**, spice **3.8 kg**, pouches **306**, cartons **21**, finished goods **238**.

“The batch is finished, and we have 188 good packets. For packaging, I enter 194 pouches in total: 188 used for the good packets and six damaged. Nine cartons were used.

Here’s the comparison. We expected 200 packets and got 188, so yield is down six percent. Oil is five percent above standard. Both are flagged because the tolerance is three percent.

Notice the pouches: consumption is three percent below standard, exactly at the tolerance, so there’s no flag. Cartons are ten percent below standard, and the same rule flags that too.

There’s an ambiguity in the problem statement here. Six damaged pouches don’t explain why production is twelve packets short. I’ve kept the twelve-packet shortfall unclassified rather than assuming they’re the same loss. They’re shown separately.

Finished stock is now 238 packets: the original 50 plus these 188.”

## Take the first order — 2:45–3:15

**Account: Sign out → salesman_a. Screen: Orders.**

**Do:** Press **F12**, then **Ctrl+Shift+M** for Chrome device emulation. Set approximately **390 × 844**. Open **New order / Submit order**, choose **Demo Retailer A**, enter **150 packets** for Murukku 200 g, and submit once. Keep the submitted order visible while finishing this paragraph.

“Next, I’m switching to the salesman’s account and the phone-sized view. He selects Retailer A and enters 150 packets. The price comes from the price list, so he doesn’t need to look it up separately.

After submission, this order is available to the factory. Nobody at the billing desk has to copy it out of a phone call or a message. The salesman can also come back here to check its status.”

## Approve, invoice and dispatch — 3:15–4:25

**Account: Sign out → admin. Return to desktop view and close developer tools.**

**Do:** Orders → Open Retailer A → review Stock check → **Approve and reserve**. Pause: **238 on hand / 150 reserved / 88 available**. Click **Post invoice**, submit, then **Download invoice PDF** and open it in Chrome. Show **7500 taxable + 187.50 CGST + 187.50 SGST = 7875**. Return to the order and **Dispatch remaining order** as you reach the final paragraph.

**Check:** After dispatch: **88 on hand / 0 reserved / 88 available**.

“At the factory, I open that same order and check stock before approving it. There are 238 packets on hand, which covers the requested 150.

Approval reserves those packets. We still physically have 238, but only 88 are available for another order. That distinction matters if two salesmen submit orders at about the same time.

Now I raise the invoice. Retailer A is in Tamil Nadu, the same state as the factory, so the tax is split into CGST and SGST. The taxable amount is 7,500 rupees, with 187 rupees and 50 paise under each tax, giving a total of 7,875.

This is the downloadable invoice. Making it hasn’t reduced physical stock. I record dispatch separately, when the goods leave. Now on-hand stock is 88 and the reservation has been released.”

## Handle the second order — 4:25–5:00

**Account: Sign out → salesman_b, then return to admin after submission.**

**Do:** Submit **120 packets** for **Demo Distributor B**. As admin, open B’s order and show **Stock check / Shortage resolution**. Point to **32 short**. Leave the order submitted. Do not invoice it, make another batch or adjust stock during the recording.

“The second salesman asks for 120 packets for Distributor B. This is where the earlier reservation and dispatch need to carry through correctly.

We have 88 available, so the system shows a shortage of 32. This order stays submitted; we can’t approve stock that isn’t available. The admin can use that shortage to decide what needs producing next.

Distributor B is in Karnataka. If this order is eventually invoiced, it will use IGST rather than the two local tax components.”

## Record the payment — 5:00–5:25

**Account: admin. Screen: Orders → Retailer A → Record payment.**

**Do:** Enter amount **4000**, leave the date unchanged and submit once. Pause on **Outstanding ₹3,875**. Make sure this is A’s order, not B’s.

“Retailer A pays 4,000 rupees. I record that against the invoice, rather than just adding a note against the customer.

The invoice was 7,875, so 3,875 is still outstanding. That balance is now available to the collections reports as well; it doesn’t need to be entered again at month end.”

## Explain the cost — 5:25–6:15

**Account: admin. Screen: Production → completed run → Add overhead.**

**Do:** Save **Labour / 1200**, then save **Gas/power / 600** as a second entry. Scroll to **Run costing**. Point to each figure as you speak.

**Check:** Materials **₹4,055**, overheads **₹1,800**, total **₹5,855**, cost per good packet **₹31.14**, margin **₹18.86**.

“Back at the production run, I can add costs that weren’t known when the batch finished. Here that’s 1,200 rupees for labour and 600 for gas and power.

Materials and packaging cost 4,055 rupees. With those overheads, the run costs 5,855. I divide by the 188 good packets, because those are the packets we can sell. That gives about 31 rupees and 14 paise per packet, against a selling price of 50 rupees before tax.

The screen rounds the amount for reading, but the calculation keeps the exact fraction. Stored money uses integer paise, so binary floating-point rounding doesn’t accumulate in the accounts.

One limitation is documented: finished-goods stock valuation is materials-only. Overheads are included here in run costing, but aren’t retroactively added to stock value.”

## Reports and close — 6:15–7:45

**Account: Sign out → accountant. Screen: Reports.**

**Do:** Set **1 November 2026–30 November 2026**. Open Sales register and GST summary during the first two paragraphs. Then show Purchase register, Stock summary/ledger, Production and Collections/outstanding. Briefly select customer-wise and product-wise sales. Download a CSV and PDF; open one export.

**At “Finally”:** Switch the recording to the terminal output saved BEFORE the walkthrough. Show **49 checks passed** and **Scenario rolled back**. Then show README/design note. Do not run the benchmark over the manual transactions. Return to Chrome if your recorder captures the whole display and you want to finish on the application.

“For month end, I’m signed in as the accountant. This account can inspect and export records, but can’t post factory transactions.

The sales register contains the invoice we just made, and the GST summary contains its tax split. The purchase register shows the flour receipt. Stock and production reports show the quantities we’ve been following, including the actual consumption and variance. Collections show the payment and remaining balance.

These are different views of the work we’ve already recorded. I can select the reporting period and export CSV or PDF. For stock reports I include the actual posting dates, so today’s movements aren’t accidentally left out.

Finally, this is the automated benchmark result from the clean instance before the walkthrough. It checks the scenario through the real services, and all 49 checks passed. That run rolled back its transactions so the manual demo could start from opening stock.

The repository includes setup instructions, the design note and the assumptions I’ve mentioned. The main thing I wanted to demonstrate is that we can follow an order, a batch, a stock movement and a payment all the way through, and explain where each number came from.”

## Rehearsal notes

- Do not read every table cell. Point to the relevant row, explain the result, then move on.
- Leave a short pause after showing the invoice total, shortage, cost and final balances.
- If running long, shorten the opening and report commentary. Keep all nine benchmark steps in order.
- If an action fails, fix it before the final take. Do not narrate a result that the screen does not show.
- Show the owner dashboard only if time remains. Leave optional feature tours for another video.
- Replace phrases that sound unlike you. Do not add claims about real customers, production deployment or personal development history that you cannot support.

## After recording

Watch the whole video, confirm readable figures and audible narration, and check it is under eight minutes. Upload as unlisted YouTube or a viewable Drive link, test access signed out, and add the link to README. Keep the video binary out of Git. A rehearsal creates transactions: use a new demo instance for another take rather than repeating transactions in the same database.
