import cloudscraper
import os
import pickle
import re
import subprocess
import threading

from requests.adapters import HTTPAdapter
from shutil import move
from time import sleep
from urllib.parse import unquote
from urllib3.util.retry import Retry

from polarity.config import lang
from polarity.downloader.base import BaseDownloader
from polarity.downloader.penguin.protocols import *
from polarity.paths import TEMP
from polarity.types import Stream
from polarity.types.ffmpeg import *
from polarity.types.segment import *
from polarity.utils import get_extension, vprint, threaded_vprint
from polarity.version import __version__


class PenguinDownloader(BaseDownloader):
    
    __penguin_version__ = '2021.08.15-emperor'
    
    # Set retry config
    retry_config = Retry(total=10, backoff_factor=1, status_forcelist=[502, 503, 504, 403, 404])

    browser = {
        'browser': 'firefox',
        'platform': 'windows',
        'mobile': False
        }
    
    thread_lock = threading.Lock()
    
    ARGUMENTS = [
        {
            'args': ['--penguin-segment-downloaders'],
            'attrib': {
                'help': lang['penguin']['args']['segment_downloaders']
            },
            'variable': 'segment_downloaders'
        }
    ]
    
    DEFAULTS = {
        'segment_downloaders': 10,
        # 'tweaks': {
        #     'atresplayer_subtitle_fix': True,
        #     'convert_webvtt_to_srt': True,
        # }
    }
 
    @classmethod
    def return_class(self): return __class__.__name__ 
    
    def load_at_init(self):
    
        self.segment_downloaders = []
        
        self.segment_pools = []
        
        # Pool format: unified0
        
        self.stats = {
            'bytes_downloaded': 0,
            'estimated_total_bytes': 0,
            'segments_downloaded': 0,
            'total_segments': 0,
            'inputs': [],
            'pools': {
                'video': 0,
                'audio': 0,
                'subtitles': 0,
                'unified': 0,
            }
        }
        
        self.indexes = {
            'video': 0,
            'audio': 0,
            'subtitles': 0,
            'files': 0
        }
    
    def start(self):
        vprint('Item: ' + self.content, 4, threading.current_thread().name)
        if os.path.exists(f'{self.temp_path}.pools'):
            vprint('resuming download...')
            with open(f'{self.temp_path}.pools', 'rb') as f:
                self.segment_pools = pickle.load(f)
        else:
            self.process_stream(stream=self.stream)
            for stream in self.extra_audio:
                self.process_stream(stream=stream)
            for stream in self.extra_subs:
                self.process_stream(stream=stream)
            # Save pools to file
            with open(f'{self.temp_path}.pools', 'wb') as f:  
                pickle.dump(self.segment_pools, file=f)
        if os.path.exists(f'{self.temp_path}.stats'):
            with open(f'{self.temp_path}.stats', 'rb') as f:
                self.stats = pickle.load(f)
        # Create segment downloaders
        vprint(
            lang['penguin']['threads_started'] % (self.options['penguin']['segment_downloaders']),
            level=3,
            module_name='penguin'
            )
        for i in range(self.options['penguin']['segment_downloaders']):
            sdl_name = f'{threading.current_thread().name}/sdl{i}'
            sdl = threading.Thread(target=self.segment_downloader, name=sdl_name, daemon=True)
            self.segment_downloaders.append(sdl)
            sdl.start()
        progress_bar = {
            'desc': self.content_name,
            'total': 0,
            'initial': self.stats['bytes_downloaded'],
            'unit': 'iB',
            'unit_scale': True,
            'leave': False
        }
        self.create_progress_bar(**progress_bar)
        self.progress_bar_updated = self.stats['bytes_downloaded']
        # Wait until threads stop
        while True:
            try:
                self.stats['estimated_total_bytes'] = self.stats['bytes_downloaded'] / self.stats['segments_downloaded'] * self.stats['total_segments']
            except ZeroDivisionError:
                pass
            # Dump statistics to file
            with open(f'{self.temp_path}.stats', 'wb') as f:  
                pickle.dump(self.stats, file=f)
                
            # Update progress bar
            self.progress_bar.total = self.stats['estimated_total_bytes']
            self.progress_bar.update(self.stats['bytes_downloaded'] - self.progress_bar_updated)
            self.progress_bar_updated = self.stats['bytes_downloaded']
            
            # Check if seg. downloaders have finished
            if [sdl for sdl in self.segment_downloaders if sdl.is_alive()]:
                sleep(0.5)
                continue
            self.progress_bar.close()
            break
        # Merge segments
        command = [
            'ffmpeg',
            '-v',
            'error',
            '-y',
            '-protocol_whitelist',
            'file,crypto,data,https,http,tls,tcp'
            ]
        commands = [
            (
                cmd.generate_command()['input'],
                cmd.generate_command()['meta'],
                )
            for cmd in self.stats['inputs']
            ]
        for _command in commands:
            command.extend(_command[0])
        for _command in commands:
            command.extend(_command[1])
        command.extend([
            '-c',
            'copy',
            '-metadata',
            'encoding_tool=Polarity %s | Penguin %s' % (
                __version__, self.__penguin_version__
            )])
        command.append(f'{TEMP}{self.content_sanitized}.mkv')
        subprocess.run(command, check=True)
        move(f'{TEMP}{self.content_sanitized}.mkv', f'{self.output_path}.mkv')
        for file in os.scandir(f'{TEMP}{self.content_sanitized}'):
            os.remove(file.path)
        os.rmdir(f'{TEMP}{self.content_sanitized}')
        os.remove(f'{TEMP}{self.content_sanitized}.stats')
        os.remove(f'{TEMP}{self.content_sanitized}.pools')
        
    def generate_pool_id(self, pool_format: str) -> str:
        pool_id = f'{pool_format}{self.stats["pools"][pool_format]}'
        self.stats['pools'][pool_format] += 1
        return pool_id

    def process_stream(self, stream: Stream) -> None:
        if not stream.preferred:
            return      
        for prot in ALL_PROTOCOLS:
            if not get_extension(stream.url) in prot.SUPPORTED_EXTENSIONS:
                continue
            processed = prot(url=stream.url, options=self.options).extract()
            for pool in processed['segment_pools']:
                
                self.stats['total_segments'] += len(pool.segments)
                pool.id = self.generate_pool_id(pool.format)
                if prot == HTTPLiveStream:
                    self.create_m3u8_playlist(pool=pool)
                self.segment_pools.append(pool)
                self.stats['inputs'].append(self.create_input(pool=pool, stream=stream))
            return
        if not stream.extra_sub:
            vprint('stream incompatible error', 1, 'emperor', 'error')
            return
        subtitle_pool_id = self.generate_pool_id('subtitles')
        subtitle_pool = SegmentPool()
        subtitle_segment = Segment(
            url=stream.url,
            number=0,
            type='subtitles',
            group=subtitle_pool_id,
            )
        subtitle_pool.segments = [subtitle_segment]
        subtitle_pool.format = 'subtitles'
        subtitle_pool.id = subtitle_pool_id
        self.segment_pools.append(subtitle_pool)
        ff_input = self.create_input(pool=subtitle_pool, stream=stream)
        ff_input.file_path = ff_input.file_path.replace(subtitle_pool_id, subtitle_pool_id + '_0')
        self.stats['inputs'].append(ff_input)
                    
    def create_input(self, pool: SegmentPool, stream: Stream) -> FFmpegInput:
        pool_extension = pool.type.ext if pool.type is not None else pool.get_ext_from_segment()
        ff_input = FFmpegInput()
        ff_input.file_path = f'{self.temp_path}/{pool.id}{pool_extension}'
        ff_input.indexes = {
            'file': self.indexes['files'],
            'v': self.indexes['video'],
            'a': self.indexes['audio'],
            's': self.indexes['subtitles'],
        }
        
        self.indexes['files'] += 1
        if pool.format in ('video', 'unified'):
            ff_input.metadata[VIDEO] = {
                'title': stream.name,
                'language': stream.language
            }
            self.indexes['video'] += 1
        if pool.format in ('audio', 'unified'):
            self.indexes['audio'] += 1
            ff_input.metadata[AUDIO] = {
                'title': stream.audio_name,
                'language': stream.audio_language
            }
        if pool.format == 'subtitles':
            self.indexes['subtitles'] += 1
            ff_input.metadata[SUBTITLES] = {
                'title': stream.sub_name,
                'language': stream.sub_language
            }
        ff_input.hls_stream = '.m3u' in stream.url
        return ff_input
        
    def segment_downloader(self):
        
        def get_unfinished_pools() -> list[SegmentPool]:
            return [p for p in self.segment_pools if not p._finished]
        
        def get_unreserved_pools() -> list[SegmentPool]:
            return [p for p in self.segment_pools if not p._reserved]
        
        def get_pool() -> SegmentPool:
            unfinished = get_unfinished_pools()
            pools = get_unreserved_pools()
            if not unfinished:
                return
            if not pools:
                vprint(f'Assisting {unfinished[0]._reserved_by} with pool {unfinished[0].id}', 4, thread_name)
                return unfinished[0]
            pools[0]._reserved = True
            pools[0]._reserved_by = thread_name
            return pools[0]
        
        thread_name = threading.current_thread().name
        
        threaded_vprint(
            message=f'Started segment downloader {thread_name}',
            level=4,
            module_name='penguin',
            error_level='debug',
            lock=self.thread_lock
            )
        
        while True:
            
            pool = get_pool()
            
            if pool is None:
                return
            
            threaded_vprint(
                'Current pool: ' + pool.id,
                level=4,
                module_name=thread_name,
                lock=self.thread_lock
                )
            while True:
                if not pool.segments:
                    if not pool._finished:
                        pool._finished = True
                        # TODO: actual message
                        # vprint('painful ' + pool.id, 5)
                    break
                
                segment = pool.segments.pop(0)
                
                threaded_vprint(
                    message=f'Took segment {segment.id}',
                    level=5,
                    module_name=thread_name,
                    error_level='debug',
                    lock=self.thread_lock
                )
                
                segment_path = f'{self.temp_path}/{segment.id}{segment.ext}'
                if os.path.exists(segment_path):
                    threaded_vprint(
                        message=f'Skipping already downloaded segment {segment.id}',
                        level=5,
                        module_name='penguin',
                        error_level='debug',
                        lock=self.thread_lock
                    )
                    continue
                # Segment download
                while True:
                    # Create a cloudscraper session
                    with cloudscraper.create_scraper(browser=self.browser) as session:
            
                        session.mount('https://', HTTPAdapter(max_retries=self.retry_config))
                        session.mount('http://', HTTPAdapter(max_retries=self.retry_config))
                        try:
                            segment_data = session.get(segment.url, timeout=15)
                        except BaseException as e:
                            threaded_vprint(
                                f'Exception in download: {e}',
                                level=5,
                                module_name=thread_name,
                                error_level='error',
                                lock=self.thread_lock
                                )
                            sleep(0.5) 
                            continue
                        if 'Content-Length' in segment_data.headers:
                            self.stats['bytes_downloaded'] += int(segment_data.headers['Content-Length'])
                        segment_contents = segment_data.content
                        
                        if segment.ext == '.vtt':
                            # Workarounds for Atresplayer subtitles
                            # Fix italic characters
                            # Replace facing (#) characters
                            segment_contents = re.sub(r'^# ', '<i>', segment_contents.decode(), flags=re.MULTILINE)
                            # Replace trailing (#) characters
                            segment_contents = re.sub(r' #$', '</i>', segment_contents, flags=re.MULTILINE)
                            # Fix aposthrophes
                            segment_contents = segment_contents.replace('&apos;', '\'').encode()
                        
                        # Write fragment data to file
                        with open(segment_path, 'wb') as f:
                            f.write(segment_contents)

                        threaded_vprint(
                            lang['penguin']['segment_downloaded'] % (segment.id),
                            level=5,
                            module_name='penguin',
                            error_level='debug',
                            lock=self.thread_lock
                            )
                        self.stats['segments_downloaded'] += 1
                        break
            
    def create_m3u8_playlist(self, pool: SegmentPool):
        if os.path.exists(f'{self.temp_path}/{pool.id}.m3u8'):
            return
        # Set first segment from list
        first_segment = pool.segments[0]
        playlist = '#EXTM3U\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-MEDIA-SEQUENCE:0\n'
        # Handle initialization segments
        init_segment = [f for f in pool.segments if f.is_init]
        if init_segment:
            playlist += f'#EXT-X-MAP:URI="{init_segment[0].output}"'
        # Handle decryption keys
        if first_segment.key is not None:
            playlist += f'#EXT-X-KEY:METHOD={first_segment.key_method},URI={pool.id}.key\n'
            # Download the key
            with cloudscraper.create_scraper(browser=self.browser) as session:
                session.mount('https://', HTTPAdapter(max_retries=self.retry_config))
                key_contents = session.get(unquote(first_segment.key))
                # Write key to file
                with open(f'{self.temp_path}/{pool.id}.key', 'wb') as key_file:
                    key_file.write(key_contents.content)
        # Add segments to playlist
        for segment in pool.segments:
            playlist += f'#EXTINF:{segment.duration},\n{segment.id}{segment.ext}\n'
        # Write end of file 
        playlist += '#EXT-X-ENDLIST\n'
        # Write playlist to file
        with open(f'{self.temp_path}/{pool.id}.m3u8', 'w') as playlist_file:
            playlist_file.write(playlist)