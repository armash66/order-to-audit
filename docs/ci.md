# Continuous integration and delivery artifacts

[Workflow](../.github/workflows/ci.yml) runs on pushes, pull requests and manual dispatch. It grants only repository-content read permission and does not use production credentials. A failed check blocks the delivery-artifact step. Configure the **Application checks / verify** required status check in branch protection after its first successful GitHub run; adding YAML alone does not enforce branch protection.

The workflow builds the frontend, checks translation coverage and documentation links, starts a fresh Compose database, runs native tests and the 49-check benchmark, executes the complete regression suite, runs browser workflows, and rehearses backup/restore. Browser scenarios run after rollback-only benchmark tests because they intentionally create transactions. Cleanup runs even on failure. Logs are printed on failure; database dumps and tokens are never uploaded.

After passing, it uploads Docker image archives as `verified-local-images-COMMIT_SHA` with seven-day retention. These are build artifacts for the exact tested revision, not a hosted deployment. Load the archive with `docker image load`, use the matching source checkout and Compose configuration, and check the image tags/project name before running. PostgreSQL is an external base image and data is never packaged in the application image archive.

There is no production target or registry credential configured. Automatically deploying the private factory database to a guessed host would be inappropriate. The local-first delivery requirement is met by Compose; a future deployment job would require an explicit environment, HTTPS/secrets, backup policy and migration/recovery checks.

## Local equivalent

Follow [development](development.md) for native/regression tests, then run `scripts/react_benchmark_check.py`, `scripts/react_offline_check.py`, `scripts/react_language_check.py` and `scripts/react_ux_check.py` against an isolated instance. Run the [backup rehearsal](backup-restore.md) after the browser scenario so the restored database includes production and sales documents.

The pipeline is committed as configuration only by the applicant. Local equivalents have been exercised; the actual GitHub-hosted workflow must still run after the applicant pushes it. Do not claim a green Actions run before seeing one.

GitHub's [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) documents triggers and token permissions. CI/CD means continuous integration and continuous delivery/deployment; the supplied internship problem statement evaluates the application, benchmark and engineering quality, not an acronym-based DevOps specialization.
