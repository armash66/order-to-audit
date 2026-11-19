from django.core.management.base import BaseCommand
from inventory.seed import seed_benchmark


class Command(BaseCommand):
    help = "Load section 5 masters and opening stock only; safely repeatable."

    def handle(self, *args, **options):
        posting = seed_benchmark()
        self.stdout.write(self.style.SUCCESS(f"Opening stock posting sequence: {posting.sequence}"))
