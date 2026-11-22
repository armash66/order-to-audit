# Order-to-Audit

Factory orders, production, inventory and accounts in one traceable workflow.

Built for the CDI NIT Trichy Software Developer Internship exercise. Sales documents and production runs meet at a shared stock ledger; every movement links to its source.

[Quick start](#quick-start) · [Documentation](docs/README.md) · [Benchmark](docs/reference.md) · [Design](docs/design.md)

## Quick start

Install Docker with Compose. From the repository root:

```sh
docker compose up --build -d --wait
```

Open [localhost:8000](http://localhost:8000). Startup applies migrations and loads fictional benchmark masters, opening stock and demo accounts.

No configuration file is required for the local demo. Optional settings are in [.env.example](.env.example). PostgreSQL data persists in a Docker volume. Use `docker compose down` to stop; keep the volume to retain your records.

## Demo accounts

Initial password for every account: **`DemoPass123!`**

| Username | Workspace |
| --- | --- |
| `salesman_a`, `salesman_b` | Mobile orders, own sales, visits and offline capture |
| `admin` | Approval, billing, dispatch, payments, production and setup |
| `production` | Receipts, material issues, output, variance and stock |
| `accountant` | Read-only records and report exports |
| `owner` | Read-only dashboard, costs, stock and outstanding |

Choose English, Tamil, Hindi or Marathi at sign-in or in the workspace. The preference is saved on the device.

Follow the [nine-step demo](docs/react-demo.md) for a first walkthrough. To add fictional staff, customers, suppliers or products, sign in as admin and open **Setup**. New staff must replace their temporary password at first sign-in.

## Features

| Scope | Implementation |
| --- | --- |
| Must | Role access; masters and versioned BOMs; mobile ordering and approval; GST invoice PDF; automatic production postings; consumption/yield variance; stock ledger; sales and stock CSV |
| Should | Suppliers and purchases; payments, outstanding and ageing; overhead costing; GST summary; variance alerts; owner dashboard |
| Optional sales | Customer prices, partial dispatch and sealed-goods returns |
| Stretch | Offline sync; batches/expiry/FEFO; reorder alerts; production suggestions; consented GPS visits; Tally XML; mocked fiscal documents; Tamil interface |
| Operator tools | Staff setup, first-use passwords, quality holds, recall tracing, loss notes, collection follow-ups and Hindi/Marathi interfaces |

See the [compliance matrix](docs/compliance.md) for evidence. Tally import has not been validated in Tally; fiscal adapters are local mocks. Invoice and exported report content remains in English.

## Verify

```sh
docker compose --profile test run --build --rm tests
```

On a database containing only opening stock:

```sh
docker compose exec api python -m api.cli benchmark
```

The benchmark checks all nine steps and rolls back its scenario. It rejects operational postings rather than resetting them. Follow the [isolated test instructions](docs/development.md) if your main database already has transactions.

Expected results include **120 kg flour**, **19.5 L oil**, **306 pouches**, **88 finished packets after dispatch**, **₹3,875 outstanding** and **₹31.14 per good packet**. [All figures and interpretations](docs/reference.md).

## Architecture

React/TypeScript provides the screens; FastAPI and SQLAlchemy Core implement explicit service transactions; PostgreSQL supplies persistence, constraints and locking. This stack matches the applicant's experience and supports a live code walkthrough. Docker Compose packages the frontend, API, database and PDF dependencies.

- Money uses integer paise; quantities use integer base units.
- Ratios use exact fractions and half-up rounding.
- Stock derives from immutable movements.
- Posting, reservations and numbering share a factory lock.
- Corrections append reasoned adjustments or reversals.

The [design note](docs/design.md) explains the model, lifecycle and costing. Earlier Django code remains a development regression oracle; it is absent from the runtime image.

## Documentation

| Guide | Contents |
| --- | --- |
| [Operations](docs/operations.md) | Daily workflows, roles, setup and offline use |
| [Development](docs/development.md) | Code map, commands, isolated tests and troubleshooting |
| [Localization](docs/localization.md) | Language behavior, catalogue maintenance and verification |
| [Benchmark and boundaries](docs/reference.md) | Expected numbers, assumptions and known limitations |
| [Security](docs/security.md) | Access controls, local deployment and data handling |
| [Requirements](docs/requirements.md) / [decisions](docs/assumptions.md) | Scope and business choices |
| [Demo](docs/react-demo.md) | Submission video sequence |

[Documentation index](docs/README.md) · [Current handoff](NEXT_STEPS.md)
