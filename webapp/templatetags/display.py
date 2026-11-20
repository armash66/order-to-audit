from django import template
from inventory.services import round_paise
register = template.Library()


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
