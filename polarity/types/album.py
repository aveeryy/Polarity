from dataclasses import dataclass, field
from typing import List

from polarity.types.base import MediaType, MetaMediaType
from polarity.types.person import Artist


@dataclass
class Album(MediaType, metaclass=MetaMediaType):
    title: str = None
    artists: List[Artist] = field(default_factory=list)
    year: int = 1970

    def get_album_artist(self) -> Artist:
        artist = [a for a in self.artists if a.album_artist]
        if artist:
            return artist[0]
