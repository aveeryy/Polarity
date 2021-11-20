from polarity.types.base import MediaType, MetaMediaType
from dataclasses import dataclass

@dataclass
class SearchResult(MediaType, metaclass=MetaMediaType):
    name: str
    type: str
    id: str
    url: str