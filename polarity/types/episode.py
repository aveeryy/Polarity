from .base import PolarType
from .stream import Stream

from dataclasses import dataclass, field

@dataclass
class Episode(PolarType):
    # TODO: finish this
    title: str
    id: str
    synopsis: str = ''
    number: int = 0
    images: list = field(default_factory=list)
    streams = []
    movie: bool = False
    year: int = 1970  # Only used in movies
    _parent = None

    def link_stream(self, stream=Stream) -> None:
        if not stream in self.streams:
            stream._parent = self
            self.streams.append(stream)
            
    def get_stream_by_id(self, stream_id: str) -> Stream:
        stream = [s for s in self.streams if s.id == stream_id]
        if not stream:
            return
        return stream[0]
            
    def get_preferred_stream(self) -> Stream:
        preferred = [s for s in self.streams if s.preferred]
        if not preferred:
            return
        return preferred[0]
    
    def get_extra_audio(self) -> list:
        return [s for s in self.streams if s.extra_audio]
    
    def get_extra_subs(self) -> list:
        return [s for s in self.streams if s.extra_sub]