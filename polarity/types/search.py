from polarity.types.base import MediaType
from dataclasses import dataclass

@dataclass
class SearchResult(MediaType):
    name: str
    type: str
    id: str
    url: str