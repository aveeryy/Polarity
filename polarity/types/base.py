import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from time import sleep
from typing import List


class MetaMediaType(type):
    """Class used to give MediaType classes readibility when printed"""

    def __repr__(self) -> str:
        return self.__name__


class MediaType(metaclass=MetaMediaType):
    def set_values(self, **values) -> None:
        for key, val in values.items():
            setattr(self, key, val)

    def as_dict(self) -> dict:
        return asdict(self)

    def as_json(self, indentation: int = 4) -> str:
        """
        Returns the Series object and children (Season, Episode) objects
        as a JSON string
        :param identation: JSON identation, default: 4
        :return: JSON string
        """
        return json.dumps(asdict(self), indent=indentation)


@dataclass
class Content(MediaType, metaclass=MetaMediaType):
    title: str
    id: str
    synopsis: str = ""
    # TODO: better default for date
    date: datetime = field(default=None)
    images: list = field(default_factory=list)
    streams: list = field(default_factory=list)
    skip_download = None


@dataclass
class ContentContainer(MediaType, metaclass=MetaMediaType):
    title: str
    id: str
    images: list = field(default_factory=list)
    content: list[Content] = field(init=False, default_factory=list)
    _extractor: str = field(init=False, default=None)
    # True if all requested contents have been extracted, False if not
    _extracted = False

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
