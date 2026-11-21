from django import template
from inventory.services import round_paise
register = template.Library()


# Format integer base units without converting quantities to floating point.
@register.filter
def quantity(value, unit):
    if unit not in ('g','ml'):
        return f'{value:,} pieces'
    whole, remainder=divmod(abs(value),1000)
    fraction=f'.{remainder:03d}'.rstrip('0') if remainder else ''
    return f'{"-" if value < 0 else ""}{whole:,}{fraction} {"kg" if unit == "g" else "L"}'


@register.filter
def money(value):
    if value is None:
        return "Unknown"
    amount = round_paise(value)
    return ("-" if amount < 0 else "") + f"{abs(amount)//100:,}.{abs(amount)%100:02d}"


@register.filter
def percent(value):
    if value is None:
        return "N/A"
    amount = round_paise(value * 10000)
    return ("-" if amount < 0 else "+") + f"{abs(amount)//100}.{abs(amount)%100:02d}%"
