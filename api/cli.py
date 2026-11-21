"""Native setup, benchmark and reconciliation commands: python -m api.cli COMMAND."""

import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["seed", "benchmark", "reconcile", "pdf-smoke"]
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Keep a successful benchmark in an isolated demo database.",
    )
    args = parser.parse_args()
    if args.command == "seed":
        from api.seed import seed_benchmark

        print(
            "Seeded masters, opening document and demo accounts; posting",
            seed_benchmark(),
        )
    elif args.command == "benchmark":
        from api.benchmark import run_benchmark

        results = run_benchmark(args.persist)
        for label, expected, actual, passed in results:
            print(
                f"{'PASS' if passed else 'FAIL'} {label}: expected={expected}; actual={actual}"
            )
        if not all(row[3] for row in results):
            raise SystemExit("Benchmark failed; writes rolled back.")
        print(
            f"{len(results)} checks passed. {'Scenario retained.' if args.persist else 'Scenario rolled back.'}"
        )
    elif args.command == "reconcile":
        from api.reconciliation import reconcile

        for code, values in reconcile().items():
            print(code, values)
        print("Ledger, source documents and batch allocations reconcile.")
    else:
        from io import BytesIO
        from pypdf import PdfReader
        from api.pdf import render

        content = render("PDF smoke check", "<p>₹1.00</p>")
        if "₹1.00" not in "".join(
            page.extract_text() for page in PdfReader(BytesIO(content)).pages
        ):
            raise SystemExit("Rupee PDF glyph check failed.")
        print("PDF rendered and ₹ text extracted successfully.")


if __name__ == "__main__":
    main()
