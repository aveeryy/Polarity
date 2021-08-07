from .base import PolarType
from .stream import Stream

class Episode(PolarType):
    def __init__(self) -> None:
        self.title = None
        self.id = None
        self.synopsis = None
        self.number = 0
        self.images = []
        self.streams = []
        self.movie = False
        self.year = 0  # Only used in movies
        self._parent = None

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