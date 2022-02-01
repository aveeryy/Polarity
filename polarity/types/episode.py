from dataclasses import dataclass, field
from typing import List

from polarity.types.base import MediaType, MetaMediaType
from polarity.types.stream import Stream
from polarity.utils import normalize_number


@dataclass
class Episode(MediaType, metaclass=MetaMediaType):
    title: str
    id: str
    synopsis: str = ""
    number: int = 0
    images: list = field(default_factory=list)
    streams: List[Stream] = field(default_factory=list)
    _series = None
    _season = None
    _partial = True
    skip_download = None

    def link_stream(self, stream=Stream) -> None:
        if stream not in self.streams:
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

    def get_extra_audio(self) -> List[Stream]:
        return [s for s in self.streams if s.extra_audio]

    def get_extra_subs(self) -> List[Stream]:
        return [s for s in self.streams if s.extra_sub]

    def convert_to_movie(self):
        from polarity.types.movie import Movie

        return Movie(
            title=self.title,
            id=self.id,
            synopsis=self.synopsis,
            images=self.images,
            streams=self.streams,
        )

    @property
    def short_name(self) -> str:
        return "%s S%sE%s" % (
            self._series.title,
            normalize_number(self._season.number),
            normalize_number(self.number),
        )

    @property
    def content_id(self) -> str:
        return f"{self._series._extractor.lower()}/episode-{self.id}"
