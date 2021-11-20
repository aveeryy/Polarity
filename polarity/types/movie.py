from dataclasses import dataclass, field
from polarity.types.base import MetaMediaType
from polarity.types.episode import Episode
from polarity.types.person import Person
from polarity.types.stream import Stream

@dataclass
class Movie(Episode, metaclass=MetaMediaType):
    title: str = None
    id: str = None
    synopsis: str = None
    actors: list[Person] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    year = 1970
    images: list[str] = field(default_factory=list)
    streams: list[Stream] = field(default_factory=list)
    _extracted = False