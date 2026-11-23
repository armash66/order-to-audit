"""Exact item-specific display units at the boundary; the ledger stores base integers."""

import re
from fractions import Fraction
from sqlalchemy import select
from api.native import table, required_integer


# Reject fractional base units instead of silently rounding physical stock.
def to_base_units(conn, item_id, value, unit=None):
    if isinstance(value, dict):
        if set(value) != {"quantity", "unit"} or unit is not None:
            raise ValueError("Use quantity and unit for a measured amount.")
        value, unit = value["quantity"], value["unit"]
    if unit is not None and not isinstance(unit, str):
        raise ValueError("Unit is not valid for this item.")
    if type(value) not in (int, str) or not re.fullmatch(
        r"-?\d+(?:\.\d+)?", str(value)
    ) or len(str(value)) > 40:
        raise ValueError("Enter an exact decimal quantity, not a floating-point number.")
    items = table(conn, "inventory_item")
    base = conn.execute(select(items.c.base_unit).where(
        items.c.id == required_integer(item_id, 1)
    )).scalar_one_or_none()
    if base is None:
        raise ValueError("Item not found.")
    factor = Fraction(1)
    if unit and unit != base:
        conversions = table(conn, "inventory_unitconversion")
        row = conn.execute(select(conversions).where(
            conversions.c.item_id == int(item_id), conversions.c.unit == unit
        )).mappings().first()
        if row is None:
            raise ValueError("Unit is not valid for this item.")
        factor = Fraction(row["numerator"], row["denominator"])
    result = Fraction(str(value)) * factor
    if result.denominator != 1:
        raise ValueError("Quantity must resolve to a whole base unit.")
    if abs(result.numerator) > 9223372036854775807:
        raise ValueError("Quantity is too large.")
    return result.numerator
