from dataclasses import dataclass, field

from polarity.types.base import MediaType
from polarity.types.stream import Stream

@dataclass
class Content(MediaType):
    title: str
    id: str
    number: int = 0
    streams: list[Stream] = field(default_factory=list)
