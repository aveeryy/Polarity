from dataclasses import dataclass, field
from datetime import datetime
from time import sleep
from typing import List

from polarity.types.base import MediaType, MetaMediaType
from polarity.types.people import Person
from polarity.types.stream import Stream
from polarity.utils import normalize_number


@dataclass
class Content(MediaType, metaclass=MetaMediaType):
    title: str
    id: str
    synopsis: str = ""
    date: datetime = field(default=datetime.fromisoformat("1970-01-01"))
    people: list[Person] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)
    streams: list = field(default_factory=list)
    # if this value is other than None, don't download the item
    skip_download = None
    output: str = field(init=False, default="")
    _parent: object = field(init=False)

    def __post_init__(self):
        # temporarily assign a parent container so unit tests don't fail
        self._parent = ContentContainer(None, None)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(title={self.title}, id={self.id})"

    def link_stream(self, stream=Stream) -> None:
        if stream not in self.streams:
            stream._parent = self
            self.streams.append(stream)

    def get_stream_by_id(self, stream_id: str) -> Stream:
        stream = [s for s in self.streams if s.id == stream_id]
        if stream:
            return stream[0]

    def get_preferred_stream(self) -> Stream:
        preferred = [s for s in self.streams if s.preferred]
        if preferred:
            return preferred[0]

    def get_extra_audio(self) -> List[Stream]:
        return [s for s in self.streams if s.extra_audio]

    def get_extra_subs(self) -> List[Stream]:
        return [s for s in self.streams if s.extra_sub]


@dataclass
class ContentContainer(MediaType, metaclass=MetaMediaType):
    title: str
    id: str
    images: list = field(default_factory=list)
    content: list[Content] = field(init=False, default_factory=list)
    _extractor: str = field(init=False, default=None)
    # True if all requested contents have been extracted, False if not
    _extracted = False

    def link_person(self, person) -> None:
        if person not in self.actors:
            self.actors.append(person)

    def link_content(self, content: Content) -> None:
        if self.id == "__polarity_initial":
            # ContentContainer is the initial created by BaseExtractor (self.info),
            # link to content as _parent
            content._parent = self
        if content not in self.content:
            self.content.append(content)

    def get_all_content(self, pop=False) -> List[Content]:
        """
        :param pop: (fakely) removes content from the list
        :returns: List with extracted content
        """

        everything = []

        for content in self.content:
            if isinstance(content, ContentContainer):
                # iterate though subcontainer contents
                everything.extend(content.get_all_content())
            if pop:
                if hasattr(content, "_popped"):
                    # if content has been popped skip to next
                    continue
                content._popped = None
            everything.append(content)

        return everything

    def get_content_by_id(self, content_id: str) -> Content:
        """
        Get a Content or ContentContainer object by it's identifier

        :param content_id: Content identifier to look for
        :return: If exists returns a Content or ContentContainer object, else None
        """
        for content in self.content:
            if content.id == content_id:
                return content
            if isinstance(content, ContentContainer):
                _content = content.get_content_by_id(content_id)
                if _content:
                    return _content

    def halt_until_extracted(self):
        """Sleep until extraction has finished, useful for scripting"""
        while not self._extracted:
            sleep(0.1)


@dataclass
class Series(ContentContainer):
    synopsis: str = ""
    year: int = 1970
    season_count: int = 0
    episode_count: int = 0

    def __repr__(self) -> str:
        return f"Series({self.title}, {self.id})"

    def link_content(self, content: Content) -> None:
        content._series = self
        return super().link_content(content)


@dataclass
class Season(ContentContainer):
    number: int = None
    year: int = 1970
    images: List[str] = field(default_factory=list)
    episode_count: int = 0
    finished: bool = True
    synopsis: str = ""
    _series = None
    _partial = True

    def link_content(self, content: Content):
        if content not in self.content:
            content._season = self
            content._series = self._series
            self.content.append(content)


@dataclass
class Episode(Content):
    number: int = 0
    _series = None
    _season = None

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


@dataclass
class Movie(Content):
    pass
