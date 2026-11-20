from datetime import date
from django.test import TestCase
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from inventory.seed import seed_benchmark
from inventory.models import SKU, Customer, BOM
from sales.services import submit_order, approve_order, order_for_actor, edit_order, invoice_order, edit_invoice_draft
from production.services import create_run, edit_run_draft
from .models import AuditLog
from .services import require_role


class RoleAuditTests(TestCase):
    def setUp(self):
        seed_benchmark()
        self.admin=User.objects.get(username="benchmark-seed")
        self.salesman=User.objects.create_user("salesman")
        self.salesman.groups.add(Group.objects.get_or_create(name="salesman")[0])
        self.order=submit_order(customer=Customer.objects.first(),quantities={SKU.objects.first().pk:1},request_key="one",document_date=date(2026,11,19),actor=self.salesman)

    def test_permissions_and_ownership(self):
        with self.assertRaises(PermissionDenied): approve_order(self.order,self.salesman)
        other=User.objects.create_user("other")
        other.groups.add(Group.objects.get(name="salesman"))
        with self.assertRaises(PermissionDenied): order_for_actor(self.order,other)
        for role in ["accountant","owner"]:
            other.groups.clear()
            other.groups.add(Group.objects.get_or_create(name=role)[0])
            require_role(other,[role])
            with self.assertRaises(PermissionDenied): approve_order(self.order,other)

    def test_draft_edits_audited_and_frozen_after_post(self):
        line=self.order.lines.get()
        edit_order(self.order,{str(line.pk):[2,5000]},self.admin)
        approve_order(self.order,self.admin)
        draft=invoice_order(self.order,self.admin,date(2026,11,19),draft=True)
        edit_invoice_draft(draft,date(2026,11,20),self.admin)
        posted=invoice_order(self.order,self.admin,date(2026,11,20))
        self.assertEqual(posted.number,"2026-27/00001")
        with self.assertRaises(ValidationError): edit_invoice_draft(posted,date(2026,11,21),self.admin)
        run=create_run(bom=BOM.objects.first(),batches=1,request_key="r",document_date=date(2026,11,19),actor=self.admin)
        edit_run_draft(run,2,self.admin)
        self.assertEqual(AuditLog.objects.filter(action__endswith=".edit").count(),3)
        record=AuditLog.objects.get(action="run.edit")
        self.assertEqual((record.before["batches"],record.after["batches"]),(1,2))
