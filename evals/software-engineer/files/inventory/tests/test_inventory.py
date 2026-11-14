import pytest

from inventory import Inventory, OutOfStock


def test_add_and_available():
    inv = Inventory()
    inv.add_stock("A", 5)
    assert inv.available("A") == 5


def test_remove():
    inv = Inventory()
    inv.add_stock("A", 5)
    inv.remove_stock("A", 2)
    assert inv.available("A") == 3


def test_remove_too_many():
    inv = Inventory()
    inv.add_stock("A", 1)
    with pytest.raises(OutOfStock):
        inv.remove_stock("A", 2)


def test_rejects_non_positive():
    with pytest.raises(ValueError):
        Inventory().add_stock("A", 0)
