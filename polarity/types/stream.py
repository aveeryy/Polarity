from dataclasses import dataclass, field
from typing import Dict, List

from polarity.types.base import MediaType, MetaMediaType
from polarity.utils import get_extension


@dataclass
class ContentKey(MediaType, metaclass=MetaMediaType):
    """
    Available key methods:

    - `AES-128`
    - `Widevine` (Only on Singularity)
    """

    url: str
    raw_key: str
    method: str


@dataclass
class Stream(MediaType, metaclass=MetaMediaType):
    """
    ### Stream guidelines:
    - Languages' names must be the actual name in that language

        >>> ...
        # Bad
        >>> self.name = 'Spanish'
        # Good
        >>> self.name = 'Español'
    - Languages' codes must be [ISO 639-1 or ISO 639-2 codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
    - On extra_* streams
    """

    url: str
    preferred: bool
    name: dict
    language: dict
    id: str = None
    key: Dict[str, ContentKey] = None
    content_type: str = None
    extra_audio: bool = field(default=False, init=False)
    extra_sub: bool = field(default=False, init=False)
    _parent = None


@dataclass
class Segment(MediaType, metaclass=MetaMediaType):
    url: str
    number: int
    media_type: type
    key: ContentKey
    group: str
    duration: float
    init: bool
    time: float = float("9" * 15)
    byte_range: str = None
    _finished = False
    _id: str = field(init=False)
    _ext: str = field(init=False)
    _filename: str = field(init=False)

    def __post_init__(self):
        self._id = f"{self.group}_{self.number}"
        self._ext = get_extension(self.url)
        self._filename = f"{self._id}{self._ext}"


@dataclass
class SegmentPool(MediaType, metaclass=MetaMediaType):
    segments: List[Segment]
    format: str
    id: str
    track_id: str
    pool_type: str = None
    _finished = False
    _reserved = False
    _reserved_by = None

    def get_ext_from_segment(self, segment=0) -> str:
        if not self.segments:
            return
        return self.segments[segment]._ext

    def get_init_segment(self) -> Segment:
        return [s for s in self.segments if s.init]


M3U8Pool = ".m3u8"

DASHPool = ".mp4"
