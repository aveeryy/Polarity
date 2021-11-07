import pytest

from polarity import Polarity
from polarity.extractor import BaseExtractor

@pytest.mark.parametrize('filters,expected', [
    ('number S01E01 number S01', {1: 'ALL'}),
    ('number S02E01 number E01', {2: [1], 'ALL': [1]}),
    ('number S05 number S01 number E04', {5: 'ALL', 1: 'ALL', 'ALL': [4]}),
    ('number S06E57 number S01-04', {6: [57], 1: 'ALL', 2: 'ALL', 3: 'ALL', 4: 'ALL',}),
])
def test_number_filter_num_assignation(filters: str, expected: dict):
    filters = Polarity(None, {}).process_filters(filters=filters, link=False)
    print(filters)
    assert BaseExtractor(None, filters)._seasons == expected