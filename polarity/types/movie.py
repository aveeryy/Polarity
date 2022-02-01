from dataclasses import dataclass, field
from time import sleep
from typing import List

from polarity.types.base import MetaMediaType
from polarity.types.episode import Episode
from polarity.types.person import Person
from polarity.types.stream import Stream


@dataclass
class Movie(Episode, metaclass=MetaMediaType):
    title: str = None
    id: str = None
    synopsis: str = None
    actors: List[Person] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    year = 1970
    images: List[str] = field(default_factory=list)
    streams: List[Stream] = field(default_factory=list)
    _extractor: str = field(init=False)
    _extracted = False

    def halt_until_extracted(self):
        """Sleep until extraction has finished, useful for scripting"""
        while not self._extracted:
            sleep(0.1)

    @property
    def content_id(self) -> str:
        return f"{self._extractor.lower()}/movie-{self.id}"
