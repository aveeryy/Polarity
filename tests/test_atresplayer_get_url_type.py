from polarity.extractor.atresplayer import AtresplayerExtractor
from polarity.types import Series, Season, Episode, Movie
import pytest


@pytest.mark.parametrize(
    'url,expected',
    [
        # Valid URLs
        ('https://www.atresplayer.com/series/byanamilan/', Series),
        ('https://www.atresplayer.com/series/byanamilan/temporada-1/capitulo-7-cuando-me-case-por-papeles_5fe1bdff7ed1a827b2a9ff65/',
         Episode),
        ('https://www.atresplayer.com/lasexta/programas/pesadilla-en-la-cocina/temporada-5/',
         Season),
        # Movie URL
        ('https://www.atresplayer.com/cine/tv-movies/peliculas/el-caso-amish_60d87fdb6584a878459b5842/',
         Movie),
        # Invalid URLs, returns None
        ('https://www.atresplayer.com/lasexta/', None),
    ])
def test_urls(url: str, expected: str):
    assert AtresplayerExtractor._get_url_type(url=url) is expected
