from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Item, UnitConversion, SKU, Supplier, Customer, BOM, BOMLine, FactoryControl, Recipe, RecipeLine
from .services import post_receipt


# Existing fixture edits are conflicts, never silently overwritten on reseeding.
def ensure(model, lookup, values):
    obj, created = model.objects.get_or_create(**lookup, defaults=values)
    if not created and any(getattr(obj, field) != value for field, value in values.items()):
        raise ValidationError(f"Changed benchmark fixture: {model.__name__} {lookup}")
    return obj


# Seed under the same lock as posting, so all masters and opening commit together.
@transaction.atomic
def seed_benchmark():
    FactoryControl.objects.select_for_update().get(pk=1)
    actor = ensure(get_user_model(), {"username": "benchmark-seed"}, {"is_staff": True, "is_active": True, "password": "!"})
    data = [("FLOUR", "Flour", "raw", "g", 100000, 420000),
            ("OIL", "Cooking oil", "raw", "ml", 30000, 420000),
            ("SPICE", "Spice mix", "raw", "g", 5000, 100000),
            ("POUCH", "200 g pouch", "packaging", "piece", 500, 125000),
            ("CARTON", "Carton", "packaging", "piece", 30, 45000),
            ("MURUKKU200", "Murukku 200 g", "finished", "piece", 50, None)]
    items, opening = {}, []
    for code, name, category, unit, quantity, value in data:
        item = ensure(Item, {"code": code}, {"name": name, "category": category, "base_unit": unit})
        items[code] = item
        opening.append((item, quantity, value))
        for display, factor in ([("kg", 1000)] if unit == "g" else [("L", 1000)] if unit == "ml" else []):
            ensure(UnitConversion, {"item": item, "unit": display}, {"numerator": factor, "denominator": 1})
    for unit, factor in [("packet", 1), ("carton", 20)]:
        ensure(UnitConversion, {"item": items["MURUKKU200"], "unit": unit}, {"numerator": factor, "denominator": 1})
    sku = ensure(SKU, {"item": items["MURUKKU200"]}, {"pack_size_g": 200, "price_paise": 5000, "hsn": "99999999"})
    recipe = ensure(Recipe, {"code": "MURUKKU200-RECIPE", "version": 1}, {})
    bom = ensure(BOM, {"sku": sku, "version": 1}, {"expected_packets": 200, "recipe": recipe})
    for code, quantity in [("FLOUR", 40000), ("OIL", 10000), ("SPICE", 1200), ("POUCH", 200), ("CARTON", 10)]:
        if items[code].category == "raw":
            ensure(RecipeLine, {"recipe": recipe, "item": items[code]}, {"quantity": quantity})
        else:
            ensure(BOMLine, {"bom": bom, "item": items[code]}, {"quantity": quantity})
    ensure(Supplier, {"code": "FLOUR-SUPPLIER"}, {"name": "Demo Flour Supplier"})
    for code, name, state, gstin in [("A", "Demo Retailer A", "33", "33BBBBB0000B1Z0"), ("B", "Demo Distributor B", "29", "29CCCCC0000C1Z0")]:
        ensure(Customer, {"code": code}, {"name": name, "state_code": state, "gstin": gstin})
    return post_receipt(kind="opening", request_key="benchmark-opening-v1", document_date=date(2026, 11, 19), lines=opening, actor=actor)
