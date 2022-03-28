from polarity.utils import dict_diff
import pytest

args = (
    ({"key_1": None, "key_2": None}, {"key_1": 2, "key_2": 4}, False),
    ({1: 2, 3: 4, 5: 6}, {1: 1, 3: 3, 5: 5}, False),
    ({None: None}, {None: None}, False),
    ({"key_1": 1}, {"key_2": 4}, True),
    ({"key_1": {"subkey": "value"}}, {"key_1": {"subkey": 2}}, False),
    ({"k": {"s": "v"}}, {"k": {"s": 1, "a": 42}}, True),
)


@pytest.mark.parametrize("dct,compare_to,expected", args)
def test_dict_key_difference(dct, compare_to, expected: bool):
    assert dict_diff(dct, compare_to) == expected
