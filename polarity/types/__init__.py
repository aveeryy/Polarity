# flake8: noqa
from polarity.types.base import MediaType, MetaMediaType
from polarity.types.content import (
    Content,
    ContentContainer,
    Episode,
    Movie,
    Season,
    Series,
)

from polarity.types.people import Person
from polarity.types.progressbar import ProgressBar
from polarity.types.search import SearchResult
from polarity.types.stream import Stream
from polarity.types.thread import Thread

all_types = [v for v in globals().values() if v.__class__.__name__ == "MetaMediaType"]

stringified_types = [t.__name__.lower() for t in all_types]


def str_to_type(text: str) -> MediaType:
    """Get a media type by it's name"""
    _type = [t for t in all_types if t.__name__.lower() == text]
    if not _type:
        return None
    return _type[0]
