# Documentation

Start with the [project README](../README.md) to run the application.

## Use the application

- [Operations](operations.md): setup, roles, sales, production and reports.
- [Nine-step demo](react-demo.md): mandatory benchmark walkthrough.
- [Benchmark and boundaries](reference.md): numbers, interpretations and limitations.
- [Localization](localization.md): English, Tamil, Hindi and Marathi.
- [Security](security.md): credentials, permissions and deployment boundaries.

## Understand and develop

- [Design note](design.md): entities, ledger, BOM, valuation and transaction rules.
- [Development](development.md): repository map, tests and troubleshooting.
- [API reference](api.md): authentication, roles, payloads, exact numbers, errors and retries.
- [Backup and restore](backup-restore.md): binary-safe snapshots and isolated recovery verification.
- [CI and delivery artifacts](ci.md): automatic gates, local equivalents and hosting boundaries.
- [Vision](vision.md), [requirements](requirements.md) and [decisions](assumptions.md): planning contract.
- [Golden workbook](benchmark.xlsx): independent benchmark expectations.
- [Compliance matrix](compliance.md): requirement evidence.
- [Submission checklist](submission.md): delivery gates and interview preparation.
- [Two-page design PDF](../output/pdf/design-note.pdf): paginated version of the design note.
- [Extended features](extended-features.md): optional workflows and integration limits.

## Historical evidence

These documents describe earlier implementation milestones; use the guides above for current commands.

- [Migration](migration.md)
- [Stock-core validation](stock-core-validation.md)
- [Production validation](production-validation.md)
- [Delivery validation](delivery-validation.md)
- [Earlier demo and interview notes](demo.md)
- [UX review](ux-review.md)

[Current handoff](../NEXT_STEPS.md) records the remaining submission work.

## Keeping documentation current

Update affected documentation in the same change as behavior, routes, configuration or commands. Keep requirement tiers separate from implementation evidence: requirements.md defines acceptance, compliance.md records verification, and reference.md describes supported boundaries. Mark superseded decisions explicitly rather than leaving conflicting instructions active.

For each change, check the README and relevant operations/API/development guide against the code. Record only checks actually run; distinguish earlier local results from verified hosted CI results for a specific commit. Keep transient status in NEXT_STEPS.md and avoid duplicating counts across guides. Regenerate and visually review the design PDF if its Markdown source changes.

Run `python scripts/check_docs.py` and `git diff --check` for documentation changes, plus relevant application checks for behavior changes. The link checker validates local file targets in selected current guides; it does not validate headings, external links, feature claims or all Markdown files. Manual code-to-document review remains necessary.
