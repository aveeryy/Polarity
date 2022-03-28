from polarity.extractor import PokemonTVExtractor
from polarity.types import Series, Episode
import pytest


@pytest.mark.parametrize(
    "url,expected",
    [
        # Valid URLs
        ("https://watch.pokemon.com/en-us/#/season?id=pokemon-indigo-league", Series),
        (
            "https://watch.pokemon.com/en-us/#/season?id=2019-pokemon-world-championships",
            Series,
        ),
        (
            "https://watch.pokemon.com/en-us/#/player?id=dd4e176a17774e309778c5184d4549c6&channelId=pokemon-generations&cameFromHome=false",
            Episode,
        ),
        (
            "https://watch.pokemon.com/sv-se/#/player?id=2ef1ab67c95c42bb8c419da93e4a321c&channelId=pokemon-serien-sol-mane-ultraaeventyren&cameFromHome=false",
            Episode,
        ),
    ],
)
def test_urls(url: str, expected: str):
    assert PokemonTVExtractor._get_url_type(url=url)[0] is expected
