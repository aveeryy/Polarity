from polarity.extractor import AtresplayerExtractor
import pytest

@pytest.mark.parametrize('url,expected', [
    # Valid URLs
    ('https://www.atresplayer.com/series/byanamilan/', 'series'),
    ('https://www.atresplayer.com/series/byanamilan/temporada-1/capitulo-7-cuando-me-case-por-papeles_5fe1bdff7ed1a827b2a9ff65/', 'episode'),
    ('https://www.atresplayer.com/lasexta/programas/pesadilla-en-la-cocina/temporada-5/', 'season'),
    # Movie URL, should return episode
    ('https://www.atresplayer.com/cine/tv-movies/peliculas/el-caso-amish_60d87fdb6584a878459b5842/', 'episode'),
    # Invalid URLs, returns None
    ('https://www.atresplayer.com/lasexta/', None),
])
def test_urls(url: str, expected: str):
    assert AtresplayerExtractor.identify_url(url=url) is expected