from polarity.types.base import PolarType
from polarity.utils import get_extension


class Segment(PolarType):
    def __init__(self, url: str, number: int, type: str, key=None, key_method=None, duration=float, group=str, init=False):
        self.url = url
        self.number = number if init is False else -1
        self.media_type = type
        self.key = key
        self.key_method = key_method
        self.duration = duration
        self.id = f'{group}_{number}'
        self.group = group
        self.ext = get_extension(url)
        self.output = f'{self.id}{self.ext}'
        self.is_init = init
        
class SegmentPool(PolarType):
    def __init__(self) -> None:
        self.segments = []
        self.format = None
        self.id = None
        self.type = None
        self._finished = False
        self._reserved = False
        self._reserved_by = None
    
    def get_ext_from_segment(self, segment=0) -> str:
        if not self.segments:
            return
        return self.segments[segment].ext
    
class M3U8Pool:
    ext = '.m3u8'