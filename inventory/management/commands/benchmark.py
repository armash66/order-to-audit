from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from reporting.benchmark import run_benchmark


class Command(BaseCommand):
    help = "Run all nine steps through real services; rolls back unless --persist is supplied. Requires opening-only data."

    def add_arguments(self, parser):
        parser.add_argument("--persist",action="store_true",help="Keep the completed scenario for screen demonstrations.")

    def handle(self, *args, **options):
        try:
            results=run_benchmark(options["persist"])
        except ValidationError as error:
            raise CommandError(str(error)) from error
        for label,expected,actual,passed in results:
            self.stdout.write(f"{'PASS' if passed else 'FAIL'} {label}: expected={expected}; actual={actual}")
        if not all(row[3] for row in results):
            raise CommandError("Benchmark failed; scenario writes rolled back.")
        self.stdout.write(self.style.SUCCESS(f"{len(results)} checks passed. {'Scenario retained.' if options['persist'] else 'Scenario rolled back.'}"))
