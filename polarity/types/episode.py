from dataclasses import dataclass, field
from typing import List

from polarity.types.generic import Content
from polarity.types.stream import Stream
from polarity.utils import normalize_number


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
