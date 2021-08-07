from polarity.utils import get_extension, request_webpage, vprint
from polarity.downloader.base import BaseDownloader, Segment
from polarity.downloader.penguin.protocols import *
from polarity.types import Stream

class PenguinDownloader(BaseDownloader):
    
    __penguin_version__ = '2021.08.07-emperor'
    
    DEFAULTS = {
        'segment_downloaders': 10,
        
    }
    
    segment_pools = {}
    
    # Pool format: unified0
    
    statistics = {
        'files': [],
        'indexes': {
            'total': 0,
            'subtitles': 0,
            'audio': 0,
            'video': 0,
        },
        'metadata': [],
        'playlists': {
            'video': 0,
            'audio': 0,
            'subtitles': 0,
            'unified': 0,
        }
    }
    
    video_streams = statistics['indexes']['video']
    audio_streams = statistics['indexes']['audio']
    subt_streams = statistics['indexes']['subtitles']
    total_streams = statistics['indexes']['total']
    
    @classmethod
    def return_class(self): return __class__.__name__
    
    def load_at_init(self):
        # suck my dick past me
        pass
    
    def start():
        pass

    def process_stream(self, stream: Stream):
        if not stream.preferred:
            return        
        if not get_extension(stream.url) in SUPPORTED:   
            return         
        for prot in ALL_PROTOCOLS:
            if not get_extension(stream.url) in prot.SUPPORTED_EXTENSIONS:
                continue
            unified_skip_video = False
            processed = prot(url=stream.url, options=self.options).extract_frags()
            for segment_list in processed['segment_lists']:
                pool = segment_list['format']
                meta = FFmpegMetadata()
                self.segment_pools[f'{pool}{self.statistics["playlists"][pool]}'] = segment_list['segments']
                self.statistics['playlists'][pool] += 1
                meta.index = self.total_streams
                if pool in ('video', 'unified') and not unified_skip_video:
                    index = self.statistics['indexes']['video']
                    title = stream.name
                    language = stream.language
                    if pool == 'unified':
                        unified_skip_video = True
                if pool in ('audio', 'unified'):
                    index = self.audio_streams
                    title = stream.sub_name
                    language = stream.sub_language
                elif pool == 'subtitles':
                    index = self.subt_streams
                    title = stream.sub_name
                    language = stream.sub_language
                
                meta.type_index = index
                meta.values = {
                    'title': title,
                    'language': language
                }
                self.statistics['indexes']['total'] += 1
                index += 1
                self.statistics['metadata'].append(meta)
                        
    def create_metadata(self, stream: Stream, pool: str, unified_is_video=False):
        meta = FFmpegMetadata()
        if pool == 'unified' and unified_is_video:
            pool = 'video'
        elif pool == 'unified' and not unified_is_video:
            pool = 'audio'
        meta.index = self.statistics['indexes']['total']
        meta.type_index = self.statistics['indexes'][pool]
        if pool == 'video':
            meta.values = {
                'title': stream.name,
                'language': stream.language
            }
        elif pool == 'audio':
            meta.values = {
                'title': stream.audio_name,
                'language': stream.audio_language
            }
    
    def segment_downloader(self):
        vprint('Launched thread')
        for name, pool in self.segment_pools.items():
            vprint('Current pool: ' + name)
            segment = pool.pop(0)
            vprint('Picked up segment:' + segment.id)
            
    def create_hls_playlist():
        pass          
    
    def get_key_from_segment(self, segment: Segment):
        key = request_webpage(url=segment.key)
        return {'key': key.content, 'method': segment.key_method}
    
class FFmpegMetadata:
    index = None
    type_index = None
    values = {}
    
    
    def return_command() -> str:
        pass