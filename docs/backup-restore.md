# Backup and restore rehearsal

Run these commands from the repository root with the correct Compose project selected. Python and Docker are required; no additional Python packages are needed. This procedure was exercised locally against the application's PostgreSQL 17 database and the actual reconciliation command.

## Create a backup

```sh
python scripts/backup.py backup factory-2026-11-24.dump
python scripts/backup.py verify factory-2026-11-24.dump
```

Choose a new filename each time: existing files are never overwritten. `pg_dump` makes a consistent database snapshot while the app is running. The Python wrapper streams binary bytes directly; do not replace it with Windows PowerShell text redirection. If backup fails, treat any partial archive as unusable and choose a new path after resolving the failure.

The archive includes business documents, immutable movements, lot allocations, users/password hashes, audit history, schema, triggers and migration state. It does not contain `.env`, Docker images, repository source or browser-local unsynced orders. Keep the matching source revision and deployment secrets separately. Protect backups as private data, retain more than one dated copy, and keep a protected copy outside the application machine. `.dump` files are ignored by Git; they must never become CI artifacts or public repository files.

## What verification proves

The verifier starts a uniquely named PostgreSQL container with a temporary password and no published port, restores with `pg_restore --exit-on-error`, then runs the current application image against that restored database. It checks ledger/source/lot reconciliation and reads user count and Alembic version. The disposable container and its anonymous volume are removed in `finally`; the source database is never a restore target. An interruption that kills Python can leave a container named `ota-restore-*`; inspect it before manually removing that exact test container.

For a different Compose project, set `COMPOSE_PROJECT_NAME` before both commands. On PowerShell: `$env:COMPOSE_PROJECT_NAME='ota-validation'`. The application image must already be built. A successful rehearsal proves restore and ledger integrity for that snapshot; it is not a full login/browser acceptance test or proof every external asset was backed up.

## Recovery into an operational environment

Restore into a **new** environment with PostgreSQL 17 and the matching application revision. Preserve the old environment until verification passes. Disable automatic seed/startup while preparing recovery, restore the dump with `pg_restore --exit-on-error --no-owner --no-acl`, set the intended database owner/permissions, and verify migration state before starting the app. Reconcile stock, sign in, inspect representative invoices/runs and confirm exports. Rotate the API signing secret to invalidate old sessions. Switch access only after those checks; keep the old database available for rollback.

The repository deliberately provides an automated isolated rehearsal, not a one-command overwrite of live data. Recovery time, retention policy and off-machine storage depend on the eventual deployment. The local demonstration has no hosted disaster-recovery service.
