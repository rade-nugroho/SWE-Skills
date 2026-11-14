"""Cart pricing."""
from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")


def apply_discount(subtotal: Decimal, percent: Decimal) -> Decimal:
    """Apply a percentage coupon to a subtotal."""
    return subtotal * (1 - percent / 100)


def cart_total(items, coupon_percent=Decimal("0"), tax_rate=Decimal("0.10")) -> Decimal:
    """items: iterable of (unit_price: Decimal, qty: int)."""
    subtotal = sum((price * qty for price, qty in items), Decimal("0"))
    discounted = apply_discount(subtotal, coupon_percent)
    total = discounted * (1 + tax_rate)
    return total.quantize(CENTS, rounding=ROUND_HALF_UP)
