from polarity.types.base import MediaType, MetaMediaType
from dataclasses import dataclass


@dataclass
class SearchResult(MediaType, metaclass=MetaMediaType):
    name: str
    type: str
    id: str
    url: str
    extractor: str

    @property
    def content_id(self) -> str:
        return f"{self.extractor.lower()}/{self.type.__name__.lower()}-{self.id}"
