# Submission checklist

Target: **27 November 2026, 14:00 IST**. The reported application close is 17:00; the PDF contains placeholder dates/contact details. Confirm the task deadline in the actual organizer notice.

## Deliverables

| PS section 8 item | Current state | Final action |
| --- | --- | --- |
| Public source repository and clear history | GitHub's unauthenticated API confirms [armash66/order-to-audit](https://github.com/armash66/order-to-audit) is public; the old leading-hyphen URL redirects there. | Applicant commits/pushes these changes and checks the final branch/history. No agent commit or push. |
| README | Setup, logins, rationale, tiers, benchmark numbers, assumptions and gaps are inline. | Check the published README after pushing. |
| Design note, maximum two pages | [Markdown](design.md) and [two-page PDF](../output/pdf/design-note.pdf). | Include the PDF in the submitted repository. |
| Video, maximum eight minutes | [Timed guide](react-demo.md) is ready. **No uploaded video link verified.** | Record the nine steps in order with mobile and admin views, upload and add the link to README. |
| Live link or one-command run | `docker compose up --build -d --wait`; five role groups and six demo accounts. Hosted demo is not required. | Recheck the final submitted checkout after any further changes. |

The public-repository check on 24 November returned last push `2026-11-22T18:46:41Z`; it does not prove the current local changes are published. No credentials were used.

## Acceptance gates

- [x] Original seven-page PDF reviewed; section 5/6 evidence mapped in [compliance](compliance.md).
- [x] Full regression suite: 86 tests; native tests: 13; benchmark: 49 checks.
- [x] Browser walkthrough: kg receipt, kg/L issue, mobile order, approval, invoice PDF, dispatch, shortage, payment, costing and export.
- [x] Offline capture survives restart; reconnect/reopen automatically syncs under the original account.
- [x] Three translated languages checked at mobile width; user-entered names and English statutory documents are documented exceptions.
- [ ] Applicant completes a real under-one-minute mobile-order trial.
- [ ] Native-speaker wording review, or retain the explicit limitation.
- [ ] Real Tally import acceptance, or retain the explicit limitation. Fiscal responses remain labelled MOCK.
- [ ] Final video viewable without requesting access and no longer than eight minutes.
- [ ] Latest code/docs/video link pushed; verify repository while signed out.
- [ ] Organizer deadline/contact verified; submit before 14:00 IST target and retain confirmation.

## Six interview rehearsals

1. **Why a single factory lock?** Explain reservation/stock serialization and the throughput trade-off. Weak spot: confusing retry safety with concurrency safety.
2. **How does 10.5 L become ledger stock?** Explain decimal strings, item-specific Fraction conversion, whole-base-unit rejection and canonical retries. Weak spot: allowing JSON floats or frontend `Number` into arithmetic.
3. **Why does invoice posting leave 238 packets?** Explain on-hand/reserved/available at 5a/5b/5c and partial dispatch. Weak spot: deducting stock twice or forgetting remaining reservations.
4. **How do rounding and late overhead work?** Explain 1 g from 3 g valued at 10 paise, depletion, ₹5,855/188 and materials-only FG. Weak spot: presenting run cost as complete financial inventory valuation.
5. **How would you add 500 g?** Share the recipe, set SKU-specific output/packaging and snapshot a new BOM. Weak spot: forgetting packaging, carton conversion or version history.
6. **What if sync loses its connection?** Persisted request keys and atomic server retries decide whether the order already exists; another user's queue cannot submit. Weak spot: assuming an HTTP timeout means the database rolled back.
