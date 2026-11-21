"""Atomic setup of parties, items, products and versioned recipes/BOMs."""
import re
from sqlalchemy import text
from api import database
from api.native import authorize, audit, factory_lock, insert_row, required_integer
from api.sales.services import get_row


def label(value, limit=120):
    if not isinstance(value, str):
        raise ValueError("Name must be text.")
    value = value.strip()
    if not value or len(value) > limit or any(ord(ch) < 32 for ch in value):
        raise ValueError("Name is required and must be plain text.")
    return value


def code(value):
    if not isinstance(value, str):
        raise ValueError("Code must be text.")
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_-]{0,39}", value):
        raise ValueError("Code must use 1-40 uppercase letters, digits, _ or -.")
    return value


def unique(conn, name, field, value):
    # Table names come only from fixed service branches, never from user input.
    if conn.execute(text(f"SELECT 1 FROM {name} WHERE {field}=:value"), {"value": value}).first():
        raise ValueError("Code is already in use.")


def item(data, user):
    authorize(user, ["admin"])
    item_code, name = code(data["code"]), label(data["name"])
    category, unit = data["category"], data["base_unit"]
    if category not in ("raw", "packaging") or unit not in ("g", "ml", "piece"):
        raise ValueError("Choose a raw or packaging item and a valid base unit.")
    if category == "packaging" and unit != "piece":
        raise ValueError("Packaging items are counted in pieces.")
    with database.transaction() as conn:
        factory_lock(conn)
        unique(conn, "inventory_item", "code", item_code)
        identifier = insert_row(conn, "inventory_item", code=item_code, name=name,
                                category=category, base_unit=unit)
        if unit in ("g", "ml"):
            insert_row(conn, "inventory_unitconversion", item_id=identifier,
                       unit="kg" if unit == "g" else "L", numerator=1000, denominator=1)
        audit(conn, user, "master.item", "inventory.Item", identifier, {},
              {"code": item_code, "name": name, "category": category, "base_unit": unit})
        return identifier


def customer(data, user):
    authorize(user, ["admin"])
    customer_code, name = code(data["code"]), label(data["name"])
    state, gstin = str(data["state_code"]).strip(), str(data["gstin"]).strip().upper()
    if not re.fullmatch(r"[0-9]{2}", state) or not re.fullmatch(r"[0-9]{2}[A-Z0-9]{13}", gstin) or not gstin.startswith(state):
        raise ValueError("GSTIN must have 15 characters and match the two-digit state code.")
    with database.transaction() as conn:
        factory_lock(conn)
        unique(conn, "inventory_customer", "code", customer_code)
        identifier = insert_row(conn, "inventory_customer", code=customer_code,
                                name=name, state_code=state, gstin=gstin)
        audit(conn, user, "master.customer", "inventory.Customer", identifier, {},
              {"code": customer_code, "name": name, "state_code": state, "gstin": gstin})
        return identifier


def supplier(data, user):
    authorize(user, ["admin"])
    supplier_code, name = code(data["code"]), label(data["name"])
    with database.transaction() as conn:
        factory_lock(conn)
        unique(conn, "inventory_supplier", "code", supplier_code)
        identifier = insert_row(conn, "inventory_supplier", code=supplier_code, name=name)
        audit(conn, user, "master.supplier", "inventory.Supplier", identifier, {},
              {"code": supplier_code, "name": name})
        return identifier


# A product creates its finished item and sellable SKU together; it starts with zero stock.
def product(data, user):
    authorize(user, ["admin"])
    product_code, name = code(data["code"]), label(data["name"])
    pack = required_integer(data["pack_size_g"], 1)
    price = required_integer(data["price_paise"], 0)
    carton = required_integer(data["carton_size"], 1)
    hsn = str(data["hsn"]).strip()
    if not re.fullmatch(r"[0-9]{4}([0-9]{2}){0,2}", hsn):
        raise ValueError("Use a 4, 6 or 8 digit HSN.")
    with database.transaction() as conn:
        factory_lock(conn)
        unique(conn, "inventory_item", "code", product_code)
        item_id = insert_row(conn, "inventory_item", code=product_code, name=name,
                             category="finished", base_unit="piece")
        sku_id = insert_row(conn, "inventory_sku", item_id=item_id,
                            pack_size_g=pack, price_paise=price, hsn=hsn)
        for unit, factor in (("packet", 1), ("carton", carton)):
            insert_row(conn, "inventory_unitconversion", item_id=item_id,
                       unit=unit, numerator=factor, denominator=1)
        audit(conn, user, "master.product", "inventory.SKU", sku_id, {},
              {"code": product_code, "name": name, "pack_size_g": pack,
               "price_paise": price, "hsn": hsn, "carton_size": carton})
        return sku_id


def quantities(values):
    if not isinstance(values, dict) or not values:
        raise ValueError("At least one BOM input is required.")
    return {required_integer(key, 1): required_integer(value, 1)
            for key, value in values.items()}


# New BOM versions snapshot a recipe; an existing recipe may be shared by another pack size.
def bom(data, user):
    authorize(user, ["admin"])
    sku_id = required_integer(data["sku"], 1)
    expected = required_integer(data["expected_packets"], 1)
    packaging = quantities(data["packaging"])
    shared = data.get("recipe")
    raw = None if shared else quantities(data["raw"])
    with database.transaction() as conn:
        factory_lock(conn)
        get_row(conn, "inventory_sku", sku_id)
        for item_id in packaging:
            if get_row(conn, "inventory_item", item_id)["category"] != "packaging":
                raise ValueError("Packaging lines must use packaging items.")
        if shared:
            recipe_id = required_integer(shared, 1)
            get_row(conn, "inventory_recipe", recipe_id)
        else:
            for item_id in raw:
                if get_row(conn, "inventory_item", item_id)["category"] != "raw":
                    raise ValueError("Recipe lines must use raw items.")
            recipe_id = None
        version = conn.execute(text("SELECT COALESCE(MAX(version),0)+1 FROM inventory_bom WHERE sku_id=:id"),
                               {"id": sku_id}).scalar_one()
        if recipe_id is None:
            recipe_id = insert_row(conn, "inventory_recipe",
                                   code=f"SKU{sku_id}-RECIPE", version=version)
            for item_id, quantity in raw.items():
                insert_row(conn, "inventory_recipeline", recipe_id=recipe_id,
                           item_id=item_id, quantity=quantity)
        bom_id = insert_row(conn, "inventory_bom", sku_id=sku_id, recipe_id=recipe_id,
                            version=version, expected_packets=expected)
        for item_id, quantity in packaging.items():
            insert_row(conn, "inventory_bomline", bom_id=bom_id,
                       item_id=item_id, quantity=quantity)
        audit(conn, user, "master.bom", "inventory.BOM", bom_id, {},
              {"sku": sku_id, "version": version, "recipe": recipe_id,
               "expected_packets": expected, "packaging": packaging,
               "raw": raw})
        return bom_id
