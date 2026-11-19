from inventory.models import Item, SKU, BOM, BOMLine
from inventory.services import post_receipt


# Test-only assumption: the shared recipe yields 80 x 500 g packs, not 200 packs.
def add_500g_bom(shared_recipe, actor, supplier, document_date):
    output = Item.objects.create(code="MURUKKU500", name="Murukku 500 g", category="finished", base_unit="piece")
    sku = SKU.objects.create(item=output, pack_size_g=500, price_paise=12500, hsn="99999999")
    pouch = Item.objects.create(code="POUCH500", name="500 g pouch", category="packaging", base_unit="piece")
    post_receipt(kind="purchase", request_key="test-500-pouches", document_date=document_date,
                 lines=[(pouch, 100, 30000)], actor=actor, supplier=supplier)
    bom = BOM.objects.create(sku=sku, recipe=shared_recipe, version=1, expected_packets=80)
    BOMLine.objects.create(bom=bom, item=pouch, quantity=80)
    # The test assumes the same carton can hold 20 larger packets; this is not benchmark data.
    BOMLine.objects.create(bom=bom, item=Item.objects.get(code="CARTON"), quantity=4)
    return bom
