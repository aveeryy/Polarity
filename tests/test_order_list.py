from polarity.utils import order_list
import pytest

# Set predefined range lists
range_list = list(range(0, 9))
reversed_range_list = list(range(0, 9))
reversed_range_list.reverse()

@pytest.mark.parametrize('to_order,definer,expected', [
    # Definer iterable can have more items than needed
    ([1, 4, 5, 6, 7, 2], reversed_range_list, [7, 6, 5, 4, 2, 1]),
    ([4, 5, 'tomatos', 'bananas'], ['tomatos', 4, 'bananas', 5, 'apples', 1], ['tomatos', 4, 'bananas', 5]),
    # Items in to_order iterable and not in definer list will be removed
    ([9, 8, 4, 32], [4, 8, 32], [4, 8, 32])
])
def test_order_list(to_order: list, definer: list, expected: list):
    assert order_list(to_order=to_order, order_definer=definer) == expected