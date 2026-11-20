from django.db import migrations


def backfill(apps, schema_editor):
    Lot=apps.get_model("inventory","StockLot")
    Allocation=apps.get_model("inventory","LotAllocation")
    Movement=apps.get_model("inventory","StockMovement")
    lots={}
    for movement in Movement.objects.order_by("posting__sequence","pk").iterator():
        if movement.item_id not in lots:
            lots[movement.item_id]=Lot.objects.create(item_id=movement.item_id,code="LEGACY",expiry_date=None)
        Allocation.objects.create(movement=movement,lot=lots[movement.item_id],quantity=movement.quantity)


class Migration(migrations.Migration):
    dependencies=[("inventory","0010_openingstock_lot_details_purchasereceipt_lot_details_and_more")]
    operations=[migrations.RunPython(backfill,migrations.RunPython.noop)]
