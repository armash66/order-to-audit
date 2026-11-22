# Security and data handling

[Documentation](README.md)

## Current controls

- Role and record-ownership checks run on the server.
- Signed access tokens stay in browser memory and expire after one hour.
- Password changes, resets and account disabling invalidate existing tokens.
- New staff must replace temporary passwords before normal API access.
- Database-backed login throttling limits repeated failed sign-in attempts.
- Posting is atomic, idempotent and serialized under the factory lock.
- Stock movements reject database UPDATE and DELETE; corrections append records.
- Audit entries retain actor, time and before/after values.
- Browser headers restrict framing, resource loading and MIME sniffing.
- GPS capture requires explicit consent. API responses are never cached by the service worker.

## Local demo boundary

Compose binds the application to localhost. Default secrets and published demo credentials are for local evaluation. Public hosting requires HTTPS, private secrets, changed credentials, backups and deployment review. A hosted production security assessment has not been completed.

Posted source documents are frozen by services; a privileged database owner can bypass service rules. Ledger reconciliation checks for disagreement. Do not expose database credentials to ordinary operators.

## Device data

Offline capture stores customer catalogue data and unsynced orders in browser storage. Use a private device and clear it before handing it over. Sign-out does not erase the offline queue. Browser scripts with the same origin can access this storage.

## Secrets and backups

Keep local settings in the ignored `.env`; only `.env.example` belongs in version control. Docker volumes preserve the database across restarts, but a volume is not a backup. Before any deployment or data reset, take and verify a PostgreSQL backup using your deployment's credential handling procedure.

## Reporting a security issue

Do not post credentials or private records in a public issue. Contact the repository owner privately with reproduction steps, affected version and impact. This repository does not currently publish a dedicated security contact or response-time commitment.
