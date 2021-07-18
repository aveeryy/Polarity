from .atresplayer import AtresplayerExtractor
from .crunchyroll import CrunchyrollExtractor

from .base import BaseExtractor

def get_extractors():
    _extractors = []
    for extractor in [
        (name.replace('Extractor', ''), klass)
        for (name, klass) in globals().items()
        if name.endswith('Extractor') and 'Base' not in name
    ]:
        _extractors.append((extractor[0], extractor[1], getattr(extractor[1], 'HOST')))
    return _extractors