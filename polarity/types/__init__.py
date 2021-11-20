from .person import Person, Actor, Director
from .episode import Episode
from .movie import Movie
from .search import SearchResult
from .season import Season
from .series import Series
from .stream import Stream
from .datetime import Time

from polarity.types.base import MediaType, MetaMediaType

__all_types = [
    v
    for v in globals().values()
    if v.__class__.__name__ == 'MetaMediaType'
    ]

def str_to_type(text: str) -> MediaType:
    '''Get a media type by it's name'''
    _type = [t for t in __all_types if t.__name__.lower() == text]
    if not _type:
        return None
    return _type[0]