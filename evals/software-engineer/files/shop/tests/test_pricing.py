from decimal import Decimal as D

from shop.pricing import cart_total
from shop.checkout import checkout


def test_total_no_coupon():
    assert cart_total([(D("10.00"), 2)]) == D("22.00")


def test_total_with_coupon():
    assert cart_total([(D("10.00"), 2)], D("10")) == D("19.80")


def test_checkout_with_promo():
    assert checkout([(D("100.00"), 1)], "halfoff")["total"] == D("55.00")
