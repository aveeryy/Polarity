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
    - Other key types supported by ffmpeg
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
    name: dict
    language: dict
    wanted: bool
    id: str = None
    key: Dict[str, ContentKey] = None
    media_type: str = None
    extra_audio: bool = field(default=False)
    extra_sub: bool = field(default=False)
    _parent = None


@dataclass
class Segment(MediaType, metaclass=MetaMediaType):
    # The stream URL
    url: str
    # The stream number, if it's an initialization segment, it must be -1
    number: int
    # Decryption key of the segment
    key: ContentKey = None
    # Duration of the segment
    duration: float = None
    # Specify if the segment is
    init: bool = False
    byte_range: str = None
    _finished = False
    _pool: str = field(init=True, default=None)
    _id: str = field(init=True, default=None)
    _ext: str = field(init=False)
    _filename: str = field(init=False)

    def link(self, pool: str):
        self._pool = pool
        self._id = f"{self._pool}_{self.number}"
        self._ext = get_extension(self.url)
        self._filename = f"{self._id}{self._ext}"


@dataclass
class SegmentPool(MediaType, metaclass=MetaMediaType):
    # The segment list
    segments: List[Segment]
    # Type of media, if unknown leave as unified
    media_type: str
    # Specifies the type of the pool
    pool_type: str = None
    _id: str = field(init=True, default=None)
    _finished = False
    _reserved = False
    _reserved_by = None

    def set_id(self, id: str):
        self._id = id
        for segment in self.segments:
            segment.link(self._id)

    def get_ext_from_segment(self, segment=0) -> str:
        if not self.segments:
            return
        return self.segments[segment]._ext

    def get_init_segment(self) -> Segment:
        return [s for s in self.segments if s.init]


M3U8Pool = ".m3u8"

DASHPool = ".mp4"
