# Delivery validation — 20 November 2026

## Automated checks

- Full PostgreSQL suite: **53 tests passed** on a clean source copy with a fresh application database and automatic startup seeding. The test runner created and destroyed its separate test database.
- Nine-step management command: **48 expected/actual checks passed**, including approval/invoice/dispatch intermediate reservations, all ten CSV/PDF reports and ageing boundaries.
- The automated benchmark additionally reads every stock checkpoint from `benchmark.xlsx` XML using Decimal text, avoiding spreadsheet floats in application arithmetic.
- `makemigrations --check --dry-run`: no changes detected. Reconciliation: six seeded items reconciled after the full browser scenario. `.env` is ignored; UTF-8 text files decode successfully; `git diff --check` passes.
- Existing tests cover concurrent duplicate receipts and competing approvals, mid-posting rollback, negative stock, exact rounding/depletion, production snapshots, 500 g shared recipe, permissions/ownership, audit edits, credits and guarded reversals.

## Clean-copy run

All source files, including currently untracked new files and the golden workbook, were copied to a new temporary directory without `.git`, `.env`, a virtual environment or Python caches. Compose project `ota-cleancheck` built and became healthy on port8001 with a new PostgreSQL volume. Startup applied migrations and created role logins without manual database work. The full suite and benchmark passed inside that image.

This is a **clean source-copy test**, not a clone of already committed changes: the applicant commits manually. After committing/pushing, repeat the README commands from a Git clone for the exact submission revision. The temporary test database was recreated once for an independent browser rerun; the working `nit` database was retained.

## Browser evidence

`scripts/browser_check.py` drives a fresh seeded instance through purchase, raw issue, packaging/FG receipt, salesman A order, approval, invoice PDF, dispatch, B shortage, payment, overhead, all ten report CSV downloads and the owner dashboard. The completed run passed. Its captured invoice shows the ₹ glyph and benchmark totals. The mobile order page was checked at360px without document overflow.

Run this optional check with locally installed Playwright (`python -m pip install playwright`, then `python -m playwright install chromium`), against a **fresh rehearsal instance only**:

```sh
python scripts/browser_check.py --url http://localhost:8001
```

It intentionally leaves the completed scenario in that instance and prints its temporary screenshot/download directory. It is not safe to repeat on already-used business data without choosing another fresh project.

A separate browser check loaded the offline catalog online, disabled networking, reloaded the cached shell, captured an order, closed Chromium, reopened the same profile offline, confirmed the retained queue, reconnected and synced successfully. Server tests separately verify same-key retry, changed payload rejection, original-user enforcement, server pricing and CSRF.

Human under-one-minute timing, device-specific WhatsApp/email attachment UX, the final narrated video and public repository submission still require applicant verification.

## Failures found and resolved

| Failure | Fix / subsequent evidence |
| --- | --- |
| Source screen test assumed primary key1 | Use the actual opening posting ID; full suite passes |
| PDF ownership check passed an integer instead of Order | Pass the related Order object; other-salesman PDF denial test passes |
| Benchmark's printed earlier expected list mutated to final FG88 | Deep-copy result snapshots; assert retained expected/actual equality and compare workbook rows |
| Browser selector could not locate wrapped Item label | Use stable select names; nine-step browser rerun passes |
| Chromium's reused download tab failed final owner navigation | New tab per login; owner independently checked, then full fresh-database browser rerun passes |
| Draft invoice showed an outstanding amount; unknown SKU raised lookup error | Draft/future-invoice outstanding is zero; unknown products raise validation and roll back; regression tests pass |

The workspace's `config/` directory disappeared unexpectedly during review. Its missing files were recovered from the already-tested running image; subsequent clean-copy tests verified them. No Git history was changed.

## Mutation checks repeated at delivery

Both changes were temporary, with restoration in `finally` before final validation:

| Deliberate mutation | Observed failing assertion |
| --- | --- |
| Variance flag `>` → `>=` | `True is not false` for exact −3% pouch variance |
| Round weighted unit rate before multiplying quantity | Materials `393000 != 405500` paise |

Each targeted test exited1 with an assertion failure. The tests detect the intended numerical defects rather than merely import/setup errors. Earlier duplicate-post guard and immutable-trigger mutation results remain in `stock-core-validation.md`.

Final restoration check: rebuilt the working image, both Compose services became healthy, all 53 tests passed again, and migration drift/diff whitespace checks passed. No production mutation remains.

## Expanded-scope validation — 20 November 2026

The earlier 53-test/48-check results describe the original delivery. Current expanded scope passes **63 tests** and **49 benchmark checks**, including customer-level ageing. The original nine-step balances, taxes and costs are unchanged. `makemigrations --check --dry-run` reports no changes; main-instance reconciliation reports six reconciled items. Existing data migrated successfully and the main app is healthy on port 8000.

A separate `ota-expanded-check` Compose project started from a fresh volume on port 8002 using the current source. The dry-run benchmark passed before browser transactions. `scripts/browser_check.py` then passed all nine screen steps, 360 px ordering, invoice PDF, report CSV downloads and owner totals. Artifacts: `C:/Users/ARMASH~1/AppData/Local/Temp/ota-ui-hf73nc9n`.

`scripts/extended_browser_check.py` passed pricing/batch/visit page access, Tamil rendering, mock JSON download, consented fictional GPS, automatic reconnect while the offline page remains active, and queue persistence across browser restart followed by online page reopen. Artifacts: `C:/Users/ARMASH~1/AppData/Local/Temp/ota-extensions-rxawjmn1`. The full restart test explicitly reloads online; it does not claim closed-browser background sync.

Failures were surfaced and corrected: the first browser selector missed whitespace-wrapped order URLs, so it now checks resolved URLs. Mock download originally omitted the clearly labelled response; it now wraps exact request JSON and MOCK response together, with regression assertions. A combined restart/reconnect check failed to fetch; separate checks now verify active-page reconnect and restarted-page reopen without clicking Sync. The complete 63-test suite passed after the download fix.

Real Tally import, native-speaker Tamil review, human under-one-minute usability timing and narrated submission video remain external/manual checks. No commits, pushes or messages were sent. Optional-feature evidence and limitations are in `extended-features.md`; the full section 5/6 matrix is in `compliance.md`.
