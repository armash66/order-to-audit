from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from sales.tests import prepare, DAY
from inventory.models import Item, Posting, StockMovement, Adjustment
from production.models import ProductionRun
from production.services import run_report
from .services import adjust_stock, reverse_run, reconcile_stock


class CorrectionTests(TestCase):
    def setUp(self):
        self.actor=prepare()

    def test_adjustment_and_retry(self):
        item=Item.objects.get(code='FLOUR')
        args=dict(item=item,quantity=-1000,value_paise=None,reason='Measured spillage',request_key='adjust',document_date=DAY,actor=self.actor)
        posting=adjust_stock(**args)
        self.assertEqual(adjust_stock(**args).pk,posting.pk)
        self.assertEqual(posting.movements.get().value_paise,-4313)
        self.assertEqual(reconcile_stock()['FLOUR']['quantity'],119000)
        with self.assertRaises(ValidationError): adjust_stock(**{**args,'quantity':-120000,'request_key':'too-much'})

    def test_reversal_restores_inputs_and_freezes_cost(self):
        run=ProductionRun.objects.first()
        args=dict(run=run,reason='Duplicate recorded run',request_key='reverse',document_date=DAY,actor=self.actor)
        posting=reverse_run(**args)
        self.assertEqual(reverse_run(**args).pk,posting.pk)
        balances=reconcile_stock()
        self.assertEqual([balances[c]['quantity'] for c in ['FLOUR','OIL','POUCH','MURUKKU200']],[160000,30000,500,50])
        self.assertEqual(run_report(run)['total_paise'],0)

    def test_reversal_dependency_and_atomic_failure(self):
        run=ProductionRun.objects.first()
        args=dict(run=run,reason='Error',request_key='reverse',document_date=DAY,actor=self.actor)
        count=Posting.objects.count()
        with patch('inventory.services.StockMovement.objects.create',side_effect=RuntimeError('disk')):
            with self.assertRaises(RuntimeError): reverse_run(**args)
        self.assertEqual(Posting.objects.count(),count)
        self.assertFalse(Adjustment.objects.exists())
        adjust_stock(item=Item.objects.get(code='OIL'),quantity=-1,value_paise=None,reason='spill',request_key='later',document_date=DAY,actor=self.actor)
        with self.assertRaises(ValidationError): reverse_run(**args)
        run.refresh_from_db()
        self.assertEqual(run.state,'completed')
