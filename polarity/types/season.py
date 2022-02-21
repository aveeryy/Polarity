from typing import Union
from dataclasses import dataclass, field
from typing import List

from polarity.types.generic import Content, ContentContainer

from polarity.types.episode import Episode


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
