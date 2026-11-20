from django.test import TestCase
from sales.tests import prepare, DAY
from sales.services import submit_order, approve_order, invoice_order, dispatch_invoice
from inventory.models import Customer, SKU, StockMovement
from .services import suggest_production


class SuggestionTests(TestCase):
    def test_pending_shortage_and_two_batch_feasibility(self):
        actor=prepare()
        sku=SKU.objects.first()
        order=submit_order(customer=Customer.objects.get(code='A'),quantities={sku.pk:150},request_key='suggest-a',document_date=DAY,actor=actor)
        approve_order(order,actor)
        dispatch_invoice(invoice_order(order,actor,DAY),actor,DAY)
        submit_order(customer=Customer.objects.get(code='B'),quantities={sku.pk:120},request_key='suggest-b',document_date=DAY,actor=actor)
        count=StockMovement.objects.count()
        result=suggest_production(sku=sku,actor=actor)
        self.assertEqual((result['uncovered'],result['required_batches'],result['feasible_batches']),(32,1,1))
        result=suggest_production(sku=sku,actor=actor,uncovered=250)
        self.assertEqual((result['required_batches'],result['feasible_batches'],result['blocked']),(2,1,True))
        shortages={row['item']:row['shortage'] for row in result['inputs']}
        self.assertEqual((shortages['OIL'],shortages['POUCH']),(500,94))
        self.assertEqual(StockMovement.objects.count(),count)
