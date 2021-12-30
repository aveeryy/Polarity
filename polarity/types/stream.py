from polarity.types.base import MediaType, MetaMediaType
from dataclasses import dataclass, field


@dataclass
class ContentKey(MediaType, metaclass=MetaMediaType):
    '''
    Available key methods:
    
    - `AES-128`
    - `Widevine` (Only on Singularity)
    '''
    url: str
    raw_key: str
    method: str


@dataclass
class Stream(MediaType, metaclass=MetaMediaType):
    '''
    ### Stream guidelines:
    - Languages' names must be the actual name in that language
    
        >>> ...
        # Bad
        >>> self.name = 'Spanish'
        # Good
        >>> self.name = 'Español'
    - Languages' codes must be [ISO 639-1 or ISO 639-2 codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
    - On extra_* streams 
    '''
    url: str
    preferred: bool
    name: dict
    language: dict
    id: str = None
    key: dict[str, ContentKey] = None
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
    ext: str
    time: float = float('9' * 15)
    byte_range: str = None
    _finished = False


@dataclass
class SegmentPool(MediaType, metaclass=MetaMediaType):
    segments: list[Segment]
    format: str
    id: str
    track_id: str
    pool_type: str
    _finished = False
    _reserved = False
    _reserved_by = None

    def get_ext_from_segment(self, segment=0) -> str:
        if not self.segments:
            return
        return self.segments[segment].ext

    def get_init_segment(self) -> Segment:
        return [s for s in self.segments if s.init]


M3U8Pool = '.m3u8'

DASHPool = '.mp4'