import cloudscraper
import os
import pickle
import re
import subprocess
import threading

from copy import deepcopy
from random import choice, randrange
from requests.adapters import HTTPAdapter
from shutil import move, copyfileobj
from time import sleep
from urllib.parse import unquote

from polarity.config import lang
from polarity.downloader.base import BaseDownloader
from polarity.downloader.penguin.protocols import *
from polarity.paths import TEMP
from polarity.types.ffmpeg import *
from polarity.types.stream import *
from polarity.utils import get_extension, vprint, threaded_vprint, browser, retry_config
from polarity.version import __version__


class PenguinDownloader(BaseDownloader):
    
    __penguin_version__ = '2021.09.15'
    
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
        'ffmpeg': {
            'codec': '-c copy'
        },
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
            'segments_downloaded': [],
            'total_segments': 0,
            'inputs': [],
            'pools': {
                'video': 0,
                'audio': 0,
                'subtitles': 0,
                'unified': 0,
            },
            'do_binary_concat': False,
            'finished': {
                'download': False,
                'post-processing': {
                    'concat': False,
                    'decryption': False,
                }
            }
        }
        
        self.indexes = {
            'video': 0,
            'audio': 0,
            'subtitles': 0,
            'files': 0
        }
    
    def start(self):
        self.options['penguin']['segment_downloaders'] = int(self.options['penguin']['segment_downloaders'])
        vprint('Item: ' + self.content, 4, threading.current_thread().name)
        if os.path.exists(f'{self.temp_path}.pools'):
            vprint(lang['penguin']['resuming'] % self.content_name)
            # Open resume file
            with open(f'{self.temp_path}.pools', 'rb') as f:
                self.segment_pools = pickle.load(f)
                self.copy_of_segment_pools = deepcopy(self.segment_pools)
        else:
            self.process_stream(stream=self.stream)
            for stream in self.extra_audio:
                self.process_stream(stream=stream)
            for stream in self.extra_subs:
                self.process_stream(stream=stream)
            # Make a copy of the segment pools 
            self.copy_of_segment_pools = deepcopy(self.segment_pools)
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
        self.progress_bar = self.create_progress_bar(**progress_bar)
        self.progress_bar_updated = self.stats['bytes_downloaded']
        # Wait until threads stop
        while True:
            try:
                self.stats['estimated_total_bytes'] = self.stats['bytes_downloaded'] / len(self.stats['segments_downloaded']) * self.stats['total_segments']
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
        # Binary concating
        if self.stats['do_binary_concat']:
            binconcat_threads = []
            for pool in self.copy_of_segment_pools:
                if pool.format == 'subtitles':
                    continue
                vprint(lang['penguin']['doing_binary_concat'] % (pool.id, self.content_name), 3, 'penguin', 'debug')
                init_segment = pool.get_init_segment()
                prog_bar = self.create_progress_bar(
                    head='binconcat',
                    desc=f'{self.content_name}: {pool.id}',
                    total=len(pool.segments),
                    leave=False,
                )
                if not init_segment:
                    return
                init_segment = init_segment[0]
                for segment in pool.segments:
                    if segment.number == -1:
                        break
                    segment_path = f'{self.temp_path}/{segment.group}_{segment.number}{segment.ext}'
                    if not os.path.exists(segment_path):
                        prog_bar.update(1)
                        continue
                    with open(f'{self.temp_path}/{init_segment.group}_{init_segment.number}{init_segment.ext}', 'ab') as output_data:
                        with open(segment_path, 'rb') as input_data:
                            output_data.write(input_data.read())
                        # Delete segment
                        os.remove(segment_path)
                        prog_bar.update(1)   
                prog_bar.close()
            '''
                t = threading.Thread(target=self.binary_concat, kwargs={'pool': pool}, daemon=True)
                binconcat_threads.append(t)
                t.start()
            while True:
                if [b for b in binconcat_threads if b.is_alive()]:
                    sleep(0.5)
                    continue
                break'''
                        
        # Widevine L3 decryption
        # TODO: update strings
        if self.stream.key and self.stream.key['video'].method == 'Widevine':
            for pool in self.copy_of_segment_pools:
                if pool.format == 'subtitles':
                    continue
                init_segment = pool.get_init_segment()
                if not init_segment:
                    continue
                init_segment = init_segment[0]        
                input_path = f'{self.temp_path}/{init_segment.group}_{init_segment.number}{init_segment.ext}'
                if not os.path.exists(input_path):
                    vprint(f'{pool.id} already decrypted. Skipping', 3, 'penguin', 'debug')
                    continue
                output_path = f'{self.temp_path}/{pool.id}.mp4'
                if pool.format == 'video':
                    key = self.stream.key['video'].raw_key
                elif pool.format == 'audio':
                    key = self.stream.key['audio'].raw_key
                vprint(f'Decrypting track {pool.id} of {self.content_name} using key "{key}"', 3, 'penguin', 'debug')
                subprocess.run(['mp4decrypt', '--key', key, input_path, output_path])
                os.remove(input_path)

        command = self.generate_ffmpeg_command()

        subprocess.run(command, check=True)
        move(f'{TEMP}{self.content_sanitized}.mkv', f'{self.output_path}.mkv')
        for file in os.scandir(f'{TEMP}{self.content_sanitized}'):
            os.remove(file.path)
        os.rmdir(f'{TEMP}{self.content_sanitized}')
        os.remove(f'{TEMP}{self.content_sanitized}.stats')
        os.remove(f'{TEMP}{self.content_sanitized}.pools')
        
    # TODO: finish threaded binary concat
    def binary_concat(self, pool: SegmentPool):
        vprint(f'Doing binary concat: {pool.id}', 3, 'penguin', 'debug')
        init_segment = pool.get_init_segment()
        prog_bar = self.create_progress_bar(
            head='binconcat',
            desc=f'{self.content_name}: {pool.id}',
            total=len(pool.segments),
            leave=False,
        )
        if not init_segment:
            return
        init_segment = init_segment[0]
        for segment in pool.segments:
            if segment.number == -1:
                break
            segment_path = f'{self.temp_path}/{segment.group}_{segment.number}{segment.ext}'
            if not os.path.exists(segment_path):
                prog_bar.update(1)
                continue
            with open(f'{self.temp_path}/{init_segment.group}_{init_segment.number}{init_segment.ext}', 'ab') as output_data:
                with open(segment_path, 'rb') as input_data:
                    output_data.write(input_data.read())
                # Delete segment
                os.remove(segment_path)
                prog_bar.update(1)   
        prog_bar.close()
        
    def generate_ffmpeg_command(self, ) -> list:
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
            '-c:v',
            'copy',
            '-c:a',
            'copy',
            '-metadata',
            'encoding_tool=Polarity %s | Penguin %s' % (
                __version__, self.__penguin_version__
            )])
        command.append(f'{TEMP}{self.content_sanitized}.mkv')
        return command
        
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
            processed = prot(stream=stream, options=self.options).extract()
            for pool in processed['segment_pools']:
                self.stats['total_segments'] += len(pool.segments)
                pool.id = self.generate_pool_id(pool.format)
                if prot == HTTPLiveStream:
                    self.create_m3u8_playlist(pool=pool)
                elif prot == MPEGDASHStream and stream == self.stream:
                    self.stats['do_binary_concat'] = True
                self.segment_pools.append(pool)
                self.stats['inputs'].append(self.create_input(pool=pool, stream=stream))
            return
        if not stream.extra_sub:
            vprint('Stream incompatible error', 1, 'emperor', 'error')
            return
        subtitle_pool_id = self.generate_pool_id('subtitles')
        subtitle_pool = SegmentPool([], 'subtitles', subtitle_pool_id, None, None)
        subtitle_segment = Segment(
            url=stream.url,
            number=0,
            media_type='subtitles',
            group=subtitle_pool_id,
            key=None,
            duration=None,
            init=False,
            ext=get_extension(stream.url),
            mpd_range=None
            )
        subtitle_pool.segments = [subtitle_segment]
        self.segment_pools.append(subtitle_pool)
        ff_input = self.create_input(pool=subtitle_pool, stream=stream)
        ff_input.file_path = ff_input.file_path.replace(subtitle_pool_id, subtitle_pool_id + '_0')
        self.stats['inputs'].append(ff_input)
                    
    def create_input(self, pool: SegmentPool, stream: Stream) -> FFmpegInput:
        
        def set_metadata(parent: str, child: str, value: str):
            if parent not in ff_input.metadata:
                ff_input.metadata[parent] = {}
            if value is None or not value:
                return
            elif type(value) == dict:
                if parent in value:
                    value = value[parent]
                elif pool.track_id in value:
                    value = value[pool.track_id]
                else:
                    return
            ff_input.metadata[parent][child] = value
        
        pool_extension = pool.pool_type.ext if pool.pool_type is not None else pool.get_ext_from_segment()
        ff_input = FFmpegInput()
        ff_input.file_path = f'{self.temp_path}/{pool.id}{pool_extension}'.replace('.ttml2', '.srt')
        ff_input.indexes = {
            'file': self.indexes['files'],
            VIDEO: self.indexes['video'],
            AUDIO: self.indexes['audio'],
            SUBTITLES: self.indexes['subtitles'],
        }
        
        if pool.get_ext_from_segment(0) == '.vtt':
            ff_input.convert_to_srt = True
        
        self.indexes['files'] += 1
        if pool.format in ('video', 'unified'):      
            self.indexes['video'] += 1      
            set_metadata(VIDEO, 'title', stream.name)
            set_metadata(VIDEO, 'language', stream.language)
        if pool.format in ('audio', 'unified'):
            self.indexes['audio'] += 1
            set_metadata(AUDIO, 'title', stream.name)
            set_metadata(AUDIO, 'language', stream.language)            
        if pool.format == 'subtitles':
            self.indexes['subtitles'] += 1
            set_metadata(SUBTITLES, 'title', stream.name)
            set_metadata(SUBTITLES, 'language', stream.language)
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
                pool = choice(unfinished)
                vprint(f'Assisting {pool._reserved_by} with pool {pool.id}', 4, thread_name)
                return pool
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
                    message=f'Took segment {segment.group}_{segment.number}',
                    level=5,
                    module_name=thread_name,
                    error_level='debug',
                    lock=self.thread_lock
                )

                segment_path = f'{self.temp_path}/{segment.group}_{segment.number}{segment.ext}'
                if f'{segment.group}_{segment.number}' in self.stats['segments_downloaded']:
                    threaded_vprint(
                        message=f'Skipping already downloaded segment {segment.group}_{segment.number}',
                        level=5,
                        module_name='penguin',
                        error_level='debug',
                        lock=self.thread_lock
                    )
                    continue
                # Segment download
                while True:
                    # Create a cloudscraper session
                    with cloudscraper.create_scraper(browser=browser) as session:
            
                        session.mount('https://', HTTPAdapter(max_retries=retry_config))
                        session.mount('http://', HTTPAdapter(max_retries=retry_config))
                        try:
                            segment_data = session.get(segment.url, timeout=15, headers={'range': f'bytes={segment.mpd_range}'} if segment.mpd_range is not None else {})
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
                        elif segment.ext == '.ttml2':
                            subrip_contents = ''
                            subtitle_entries = re.findall(r'<p.+</p>', segment_contents.decode())
                            i = 1
                            for p in subtitle_entries:
                                begin = re.search(r'begin="([\d:.]+)"', p).group(1).replace('.', ',')
                                end = re.search(r'end="([\d:.]+)"', p).group(1).replace('.', ',')
                                contents = re.search(r'>(.+)</p>', p).group(1).replace('<br />', '\n')
                                contents = re.sub(r'<(|/)span>', '', p)
                                contents = contents.replace('&gt;', '')
                                contents = contents.strip()
                                subrip_contents += f'{i}\n{begin} --> {end}\n{contents}\n\n'
                                i += 1
                            segment_contents = subrip_contents.encode()
                            segment_path = segment_path.replace('.ttml2', '.srt')
                            
                        # Write fragment data to file
                        with open(segment_path, 'wb') as f:
                            f.write(segment_contents)

                        threaded_vprint(
                            lang['penguin']['segment_downloaded'] % (f'{segment.group}_{segment.number}'),
                            level=5,
                            module_name='penguin',
                            error_level='debug',
                            lock=self.thread_lock
                            )
                        
                        segment._finished = True
                        
                        self.stats['segments_downloaded'].append(f'{segment.group}_{segment.number}')
                        break
            
    def create_m3u8_playlist(self, pool: SegmentPool):
        # TODO: support for multi-key
        keys = []
        # Set first segment from list
        first_segment = pool.segments[0]
        playlist = '#EXTM3U\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-MEDIA-SEQUENCE:0\n'
        # Handle initialization segments
        init_segment = [f for f in pool.segments if f.init]
        if init_segment:
            init_segment = init_segment[0]
            playlist += f'#EXT-X-MAP:URI="{init_segment.group}_{init_segment.number}{init_segment.ext}"\n'
        # Handle decryption keys
        if first_segment.key is not None and first_segment.key['video'].url is not None:
            playlist += f'#EXT-X-KEY:METHOD={first_segment.key["video"].method},URI="{self.temp_path}/{pool.id}.key"\n'
            # Download the key
            with cloudscraper.create_scraper(browser=browser) as session:
                session.mount('https://', HTTPAdapter(max_retries=retry_config))
                key_contents = session.get(unquote(first_segment.key['video'].url))
                # Write key to file
                with open(f'{self.temp_path}/{pool.id}.key', 'wb') as key_file:
                    key_file.write(key_contents.content)
        # Add segments to playlist
        for segment in pool.segments:
            playlist += f'#EXTINF:{segment.duration},\n{self.temp_path}/{segment.group}_{segment.number}{segment.ext}\n'
        # Write end of file 
        playlist += '#EXT-X-ENDLIST\n'
        # Write playlist to file
        with open(f'{self.temp_path}/{pool.id}.m3u8', 'w') as playlist_file:
            playlist_file.write(playlist)
