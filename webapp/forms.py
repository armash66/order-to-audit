from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError


def money_input(value):
    try:
        amount = Decimal(value.replace(",", "")) * 100
        if not amount.is_finite() or amount != amount.to_integral_value() or amount < 0:
            raise ValueError()
        return int(amount)
    except (InvalidOperation, ValueError):
        raise ValidationError("Enter a nonnegative amount with at most two decimal places.")
