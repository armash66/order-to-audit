# Production validation

Scope: benchmark steps 1–3 and 8 through services; no screens or sales/dispatch changes.

## Results

`docker compose exec -T web python manage.py test production inventory config -v 1`

Final restored suite: **26 tests passed** (12 production tests plus the previous 14). Django system check passed; `makemigrations --check --dry-run` reported no changes. Rebuilding with Compose succeeded, both services became healthy, repeating the opening seed returned sequence 1, and reconciliation succeeded.

| Benchmark assertion | Result |
| --- | --- |
| Flour / oil / spice | 120,000 g / 19,500 ml / 3,800 g |
| Pouches / cartons / FG | 306 / 21 / 238 pieces |
| Yield | −6%, flagged |
| Oil consumption | +5%, flagged |
| Carton consumption | −10%, flagged |
| Pouch consumption | −3%, not flagged at 3%; flagged after changing tolerance to 2% |
| Materials / overhead / total | 405,500 / 180,000 / 585,500 paise |
| Exact unit cost | Fraction(585500, 188) paise = 5855/188 rupees |
| Display unit cost | 3,114 paise = ₹31.14 |

Raw issue leaves packaging and FG untouched. Completion does not repeat raw consumption. Late overhead leaves every stock movement unchanged. FG receipts and summaries label valuation **materials-only**; the benchmark's unknown opening FG cost keeps aggregate FG value unknown.

## Failure and boundary coverage

- Raw and packaging shortages reject without writes.
- Failure after the first raw movement rolls back source lines, event, state and posting sequence.
- Failure while inserting FG rolls back the preceding packaging issues and leaves the run issued.
- Identical retries return existing events; changed payloads and invalid transitions fail.
- Run standards, expected yield and version numbers survive subsequent master edits.
- Zero output does not divide by zero or receive FG; zero consumption records no zero movement.
- Unknown input cost blocks consumption; unauthorized callers cannot create runs/change tolerance.
- Whole-paise residual test uses three real 1 g issues from 3 g worth 10 paise: costs 3, 4 and 3 paise; final stock and value both zero.
- Reconciliation checks production source lines as well as opening/purchase sources.

## Mutation checks

Each mutation was temporary and run against a fresh test database. The source was restored in a finally block before continuing; the final suite ran against the rebuilt image with original behaviour.

| Mutation | Test | Observed failure |
| --- | --- | --- |
| Change variance `>` to `>=` | `test_tolerance_retroactive_and_strict_boundary` | `AssertionError: True is not false` — exact −3% pouch variance was incorrectly flagged at 3%. |
| Round paise/base-unit before multiplying issue quantity | `test_benchmark_production_and_late_overhead` | `AssertionError: 393000 != 405500` — wrong materials cost. |

Both commands exited 1 with assertion failures, not setup/import failures. No unexpected failures occurred in this production chunk.

## Shared-recipe change effort

The recipe split required changes to `inventory/models.py`, `inventory/seed.py`, `inventory/tests.py` and two new migrations (`0003`, `0004`): five files for the shared-master foundation. The data migration moved the existing raw BOM lines into a recipe and preserved stock history; no schema-reset/reseed fallback was needed.

After that foundation, the 500 g scenario needed **16 lines in `production/test_fixtures.py` and a 17-line test method in `production/tests.py`**. This is 33 lines across two files, including fixture imports/comments. It added no SKU-specific production-service branch. The fixture explicitly assumes 80 good packets per shared recipe, a distinct pouch and four cartons holding 20 larger packets; it never changes the benchmark seed.

## Limits

The single factory lock serializes posting, favouring simplicity over throughput. This chunk adds no further concurrency tests beyond the stock core's duplicate-request test; production rollback is directly tested. Source freezing remains service-level; privileged ORM/SQL edits can bypass it. Production reversals, draft edit workflows, substitute ingredients, fractional planned batches and screens remain unimplemented. This is a run-cost prototype, not complete inventory absorption accounting.
