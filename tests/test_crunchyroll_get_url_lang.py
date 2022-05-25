from polarity.extractor import CrunchyrollExtractor
import pytest


@pytest.mark.parametrize(
    "url,expected",
    [
        # Legacy URLs
        ("https://www.crunchyroll.com/fr/new-game", "fr-FR"),
        ("https://www.crunchyroll.com/series-270699", "en-US"),
        (
            "https://www.crunchyroll.com/es-es/new-game/episode-8-im-telling-you-i-want-a-maid-caf-742165",
            "es-ES",
        ),
        ("https://www.crunchyroll.com/media-715393", "en-US"),
        # Beta URLs
        ("https://beta.crunchyroll.com/es-es/series/GRWE2PQQR", "es-ES"),
        (
            "https://beta.crunchyroll.com/es/watch/G609G82E6/it-actually-feels-like-i-started-my-job",
            "es-LA",
        ),
        ("https://www.crunchyroll.com/de/watch/G609G82E6", "de-DE"),
    ],
)
def test_urls(url: str, expected: str):
    assert CrunchyrollExtractor._get_url_language(url=url) == expected
