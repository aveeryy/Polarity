from polarity.extractor import CrunchyrollExtractor
from polarity.types import Series, Episode
import pytest


@pytest.mark.parametrize(
    "url,expected",
    [
        # Legacy URLs
        ("https://www.crunchyroll.com/es-es/new-game", Series),
        ("https://www.crunchyroll.com/series-270699", Series),
        (
            "https://www.crunchyroll.com/es-es/new-game/episode-8-im-telling-you-i-want-a-maid-caf-742165",
            Episode,
        ),
        ("https://www.crunchyroll.com/media-715393", Episode),
        # Beta URLs
        ("https://beta.crunchyroll.com/es-es/series/GRWE2PQQR", Series),
        (
            "https://beta.crunchyroll.com/es-es/watch/G609G82E6/it-actually-feels-like-i-started-my-job",
            Episode,
        ),
        ("https://www.crunchyroll.com/es-es/watch/G609G82E6", Episode),
    ],
)
def test_urls(url: str, expected: str):
    assert CrunchyrollExtractor._get_url_type(url=url)[0] is expected
