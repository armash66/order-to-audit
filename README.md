# Order-to-Audit

A planned document-led system connecting sales, production, inventory and receivables for a small food manufacturer. Planning only: no application code, stack choice, setup command or automated application tests yet.

## Planning documents

- [Vision](docs/vision.md)
- [Requirements and acceptance checks](docs/requirements.md)
- [Decisions and domain sketch](docs/assumptions.md)
- [Benchmark golden workbook](docs/benchmark.xlsx)

## Benchmark expectations and deliberate interpretations

Materials cost ?4,055; run cost with overhead ?5,855; cost per good packet ?31.14; margin before tax ?18.86. Retailer A invoice is ?7,875 and outstanding is ?3,875. These are verified planning values, not application test results.

- **Carton alert:** actual 9 versus standard 10 gives ?10%, so the uniform absolute-variance rule flags cartons as well as yield (?6%) and oil (+5%). The PS's named expected alerts list only yield and oil; this additional alert preserves the given nine-carton consumption. Eight packets remain loose under DEC-05.
- **Provisional loss split (DEC-06):** 12 packet-equivalent output shortfall: provisional 6 damaged-output equivalents + 6 process loss. Damaged food is not confirmed by PS. The PS only confirms six damaged pouches. The split does not cause an additional stock deduction and awaits organizer clarification.

## Scope and cut line

SAL-6 invoice sharing is Should. The selected stretch is STR-4, production suggestions with input-feasibility warnings. If time runs short, defer in this order: DASH-1 owner dashboard, AUTH-2 auditor/owner access, RPT-2 report PDFs, then STR-4. No cuts have been activated. Invoice PDF, all Must features and benchmark CSV reports/calculations remain required. Report PDFs will share one generic table renderer; deferral must be disclosed as a section 4.6 gap.

## Next implementation session

Choose and justify the stack, then design the ledger transaction boundaries. Add setup/run instructions, seed command, role logins, implemented requirement status, benchmark execution instructions and demo link as those exist. Organizer contact and questions-window dates remain unconfirmed because the supplied PDF contains placeholders; the questions email remains unsent.
