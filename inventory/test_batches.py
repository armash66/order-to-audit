from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from inventory.seed import seed_benchmark
from django.contrib.auth.models import User
from inventory.models import Item, Supplier, LotAllocation
from inventory.services import post_receipt, reconcile_stock, set_reorder_level, reorder_alerts
from production.services import create_run, issue_run
from inventory.models import BOM


class BatchTests(TestCase):
    def setUp(self):
        seed_benchmark()
        self.actor=User.objects.get(username='benchmark-seed')
        self.item=Item.objects.get(code='FLOUR')
        self.day=timezone.localdate()

    def receipt(self,code,days,quantity=10000):
        return post_receipt(kind='purchase',request_key=code,document_date=self.day,actor=self.actor,supplier=Supplier.objects.first(),
            lines=[(self.item,quantity,45000)],lot_details={'FLOUR':{'code':code,'expiry':str(self.day+timedelta(days=days))}})

    def test_fefo_skips_expired_and_prefers_earliest(self):
        self.receipt('late',10)
        self.receipt('early',2)
        self.receipt('expired',-1)
        run=create_run(bom=BOM.objects.first(),batches=1,request_key='batch-run',document_date=self.day,actor=self.actor)
        issue_run(run=run,actual={'FLOUR':15000,'OIL':0,'SPICE':0},request_key='batch-issue',actor=self.actor)
        used=dict(LotAllocation.objects.filter(movement__production_line__event__run=run).values_list('lot__code','quantity'))
        self.assertEqual(used,{'early':-10000,'late':-5000})
        reconcile_stock()
        set_reorder_level(item=self.item,minimum_quantity=200000,actor=self.actor)
        self.assertEqual(reorder_alerts()[0]['available'],105000)

    def test_changed_expiry_and_expired_only_stock_rejected(self):
        self.receipt('old',-1)
        with self.assertRaises(ValidationError): self.receipt('old',5)
        # A new item isolates expiry handling from the benchmark's unknown-expiry opening stock.
        item=Item.objects.create(code='EXPIRED',name='Expired input',category='raw',base_unit='g')
        post_receipt(kind='purchase',request_key='expired-only',document_date=self.day,actor=self.actor,supplier=Supplier.objects.first(),lines=[(item,100,100)],lot_details={item.code:{'code':'expired','expiry':str(self.day-timedelta(days=1))}})
        from sales.services import available_stock
        self.assertEqual(available_stock()[item.code]['available'],0)
        from inventory.models import RecipeLine, StockMovement
        bom=BOM.objects.first()
        RecipeLine.objects.create(recipe=bom.recipe,item=item,quantity=1)
        run=create_run(bom=bom,batches=1,request_key='expired-run',document_date=self.day,actor=self.actor)
        count=StockMovement.objects.count()
        with self.assertRaises(ValidationError):
            issue_run(run=run,actual={'FLOUR':0,'OIL':0,'SPICE':0,'EXPIRED':1},request_key='expired-issue',actor=self.actor)
        self.assertEqual(StockMovement.objects.count(),count)
        reconcile_stock()
