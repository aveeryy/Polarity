from .person import Person, Actor, Director, Artist
from .episode import Episode
from .movie import Movie
from .progressbar import ProgressBar
from .search import SearchResult
from .season import Season
from .series import Series
from .stream import Stream
from .task import Task
from .thread import Thread

from polarity.types.base import MediaType, MetaMediaType

all_types = [
    v for v in globals().values() if v.__class__.__name__ == 'MetaMediaType'
]


def str_to_type(text: str) -> MediaType:
    '''Get a media type by it's name'''
    _type = [t for t in all_types if t.__name__.lower() == text]
    if not _type:
        return None
    return _type[0]