# Stock core validation

Scope: section 5 opening stock and purchase step 1; no production/sales UI.

- PostgreSQL suite: 14 tests passed, including the existing three startup/PDF tests.
- Benchmark after receipt: flour 160000 g; oil 30000 ml; spice 5000 g; pouches 500; cartons 30; FG 50 pieces. Flour value 690000 paise; exact weighted rate 69/16 paise/g.
- Seed invoked twice without duplicate openings; reconciliation command succeeds.
- Mid-post failure injected on the second movement after the first insert: header, lines, movements and sequence all rolled back; retry succeeds at sequence 2.
- Two worker threads with independent PostgreSQL connections submit the same request: one receipt and posting, both callers receive the same posting ID.
- Source-tampering and faulty-report tests prove reconciliation detects mismatches.
- Initial verification failed due to a nested directory introduced by temporary Docker copying. Rebuilding from the workspace removed that container-only mistake; all tests then passed.

## Mutation checks

Each mutation was performed only in the disposable application container; each test used a newly created test database. The normal application database trigger was never disabled. Files were restored in a finally block.

| Temporary mutation | Target test | Observed failure |
| --- | --- | --- |
| Bypass `if existing is not None` in post_receipt | test_duplicate_and_changed_retry | IntegrityError: duplicate request_key; database uniqueness remains a second defense, but idempotent retry behaviour is broken. |
| Disable stock_movement_immutable in the test migration | test_movement_immutability | AssertionError: DatabaseError not raised. |

Both test commands exited 1, as required. Original service and migration were restored; the full 14-test suite was rerun successfully afterward. These checks do not prove all concurrency scenarios: only duplicate concurrent requests and mid-post rollback were included in the agreed transaction-test scope.
