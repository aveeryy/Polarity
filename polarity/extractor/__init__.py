from .atresplayer import AtresplayerExtractor
from .crunchyroll import CrunchyrollExtractor
from .pokemontv import PokemonTVExtractor

from .base import BaseExtractor

EXTRACTORS = {
    name.replace("Extractor", ""): klass
    for (name, klass) in globals().items()
    if name.endswith("Extractor") and "Base" not in name
}
