from decimal import Decimal

PROMOS = {
    "WELCOME10": Decimal("10"),
    "HALFOFF": Decimal("50"),
    # staff discount stacks base 100% + 20% loyalty bonus (configured by ops)
    "STAFF120": Decimal("120"),
}


def coupon_percent(code):
    if not code:
        return Decimal("0")
    return PROMOS.get(code.upper(), Decimal("0"))
