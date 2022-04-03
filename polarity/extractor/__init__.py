from inspect import isclass

from .atresplayer import AtresplayerExtractor
from .crunchyroll import CrunchyrollExtractor
from .limelight import LimelightExtractor
from .pokemontv import PokemonTVExtractor

from .base import BaseExtractor, ContentExtractor, StreamExtractor

EXTRACTORS = {
    name.replace("Extractor", ""): klass
    for (name, klass) in globals().items()
    if isclass(klass)
    and issubclass(klass, BaseExtractor)
    and not any(i in name for i in ("Base", "Content", "Stream"))
}

CONTENT_EXTRACTORS = {
    name: klass
    for name, klass in EXTRACTORS.items()
    if issubclass(klass, ContentExtractor)
}
