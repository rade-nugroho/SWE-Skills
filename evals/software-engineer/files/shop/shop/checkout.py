from .pricing import cart_total
from .promos import coupon_percent


def checkout(cart, code=None):
    total = cart_total(cart, coupon_percent(code))
    return {"total": total, "charge_customer": total > 0}
