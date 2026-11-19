from django.core.management.base import BaseCommand
from inventory.services import reconcile_stock


class Command(BaseCommand):
    help = "Check source documents against ledger movements and stock summaries."

    def handle(self, *args, **options):
        balances = reconcile_stock()
        self.stdout.write(self.style.SUCCESS(f"Reconciled {len(balances)} items."))
