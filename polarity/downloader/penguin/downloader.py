from polarity.config import lang
from polarity.downloader.base import BaseDownloader, InitSegment, Segment
from polarity.downloader.penguin.protocols import *
from polarity.paths import TEMP as temporary_dir
from polarity.utils import get_extension, humanbytes, vprint, threaded_vprint, calculate_time_left
from polarity.version import __version__

from datetime import timedelta
from requests.adapters import HTTPAdapter
from shutil import move
from urllib.parse import unquote
from urllib3.util.retry import Retry
from threading import Thread, Lock, current_thread
from time import sleep, time

import cloudscraper
import os
import re
import subprocess
import toml
import threading


class PenguinDownloader(BaseDownloader):
    '''
    # Penguin Downloader 🐧
    ## Polarity version
    Penguin is a multi-threaded downloader, designed for Polarity and released under the Creative Commons Zero license.
    A standalone version will soon be available [here](https://github.com/Aveeryy/penguin-standalone)

    ### Arguments
    `main_url` Main manifest URL
    
    `extra_audio` and `extra_subs` Dictionary containing extra media
    
    Dict. format:
    ``{'url': url, 'lang': 'ffmpeg language code', 'name': 'track name'}`
    '''

    __penguin_version__ = '2021.08.06'

    ARGUMENTS = [
        {
            'args': ['--penguin-video-threads'],
            'attrib': {
                'help': '',
            },
            'variable': 'video_threads'
        },
        {
            'args': ['--penguin-audio-threads'],
            'attrib': {
                'help': '',
            },
            'variable': 'audio_threads'
        },
        {
            'args': ['--penguin-recovery-threads'],
            'attrib': {
                'help': '',
            },
            'variable': 'recovery_threads'
        },
        {
            'args': ['--penguin-thread-timeout'],
            'attrib': {
                'help': '',
            },
            'variable': 'thread_timeout'
        },
    ]

        # Set retry config
    retry_config = Retry(total=10, backoff_factor=1, status_forcelist=[502, 503, 504, 403, 404])

    browser = {
        'browser': 'firefox',
        'platform': 'windows',
        'mobile': False
        }

    print_lock = Lock()

    lang = lang['penguin']

    DEFAULTS = {            
        'video_threads': 5,
        'audio_threads': 5,
        'recovery_threads': 3, 
        'thread_timeout': 10,
    }

    @classmethod
    def return_class(self): return __class__.__name__.lower()

    def load_at_init(self):
        self.stats = {
            'running': False,
            'finished': False,
            'bytes_downloaded': 0,
            'ffmpeg_command': [
                'ffmpeg',
                '-v', 'error',
                '-y',
                '-protocol_whitelist', 'file,crypto,data,https,http,tls,tcp'
            ],
            'ffmpeg_metadata': [
                '-c',
                'copy',
                '-metadata',
                'encoding_tool=Polarity %s | Penguin %s' % (
                    __version__, self.__penguin_version__
                    )
            ],
            'files': [],
            'input_count': {
                'total': 0,
                'audio': 0,
                'subt': 0,
            },
            'last_report': 0,
            'segments_downloaded': {
                'video': 0,
                'audio': 0,
                'multi': 0,
                'subtitles': 0,
                'total': 0,
                'actually_downloaded': 0,
            },
            'segments_skipped': 0,
            'time_elapsed_download': 0,
            'time_left_download': 0,
            'time_start': {
                'process': time(),
                'start': 0,
                'download': 0,
                'merge': 0,
                'cleanup': 0,
                'moving': 0,
            },
            'total_segments': {
                'video': 0,
                'audio': 0,
                'multi': 0,
                'subtitles': 0,
                'total': 0,
            },
            'FLAGS': {
                'loaded_from_file': False
            }
        }

        # Sanitize the filename so that ffmpeg (and Android ) won't fuck the whole thing up
        # This is not a problem on Windows systems as the '?' character and gets replaced
        # in the filename formatting
        self.content_sanitized = self.content.replace('?', '')
        # Remove temporary directory created by the base and create a sanitized directory
        if self.content_sanitized != self.output_name:
            os.removedirs(f'{temporary_dir}{self.output_name}')
        if not os.path.exists(f'{temporary_dir}{self.content_sanitized}'):
            os.makedirs(f'{temporary_dir}{self.content_sanitized}')

        # Create a status file if it does not exist, else load it
        if not os.path.exists(f'{temporary_dir}{self.content_sanitized}.status'):
            with open(f'{temporary_dir}{self.content_sanitized}.status', 'w', encoding='utf-8') as status:
                toml.dump(self.stats, status)
        elif os.path.exists(f'{temporary_dir}{self.content_sanitized}.status'):
            with open(f'{temporary_dir}{self.content_sanitized}.status', 'r', encoding='utf-8') as status:
                self.stats = toml.load(status)

        for protocol in ALL_PROTOCOLS:
            if get_extension(self.stream.url) in protocol.SUPPORTED_EXTENSIONS:
                self.protocol = protocol
                break
        if not hasattr(self, 'protocol'):
            raise IncompatibleProtocolError(f'Protocol with extension "{get_extension(self.stream.url)}" is not supported')
        self.segment_info = self.protocol(self.stream.url, options=self.options).extract_frags()
        self.segment_groups = self.segment_info['segment_lists']
        self.processed_tracks = self.segment_info['tracks']
        # Build M3U8 playlists for merging
        if self.protocol == HTTPLiveStream:
            self.m3u8_playlists = {}
            for f in self.segment_groups:
                self.build_m3u8_playlist(f)
        del self.protocol
        # Parse extra audio and subtitles
        if not self.stats['FLAGS']['loaded_from_file']:
            if self.extra_audio != dict:
                # Audio is untested due to no extractors actually using it!
                for item in self.extra_audio:
                    for protocol in ALL_PROTOCOLS:
                        if get_extension(item.url) in protocol.SUPPORTED_EXTENSIONS:
                            self.protocol = protocol
                            self.processed_audio = self.protocol(url=item.url, options=self.options)['segment_lists']
                            # Override protocol-set identifier
                            self.processed_audio['id'] = f'audio_{self.processed_tracks["audio"]}'
                            self.segment_groups.append(self.processed_audio)
                            # Process ffmpeg metadata
                            self.stats['ffmpeg_metadata'].extend(
                            [
                                '-map', f'{str(self.stats["input_count"]["total"])}:a?',
                                f'-metadata:s:s:{str(self.stats["input_count"]["audio"])}', f'language={item.language}',
                                f'-metadata:s:s:{str(self.stats["input_count"]["audio"])}', f'title={item.name}',
                            ])
                            self.stats['input_count']['total'] += 1
                            self.stats['input_count']['audio'] += 1
                            del self.protocol
                    if not hasattr(self, 'protocol'):
                        vprint(
                            message=f'Skipping extra audio {item["name"]}. Unsupported protocol',
                            module_name='penguin',
                            error_level='error'
                        )
                        continue
            if self.extra_subs != dict:
                for item in self.extra_subs:
                    self.processed_tracks['subtitles'] += 1
                    for protocol in ALL_PROTOCOLS:
                        if get_extension(item.url) in protocol.SUPPORTED_EXTENSIONS:
                            self.protocol = protocol
                            self.processed_subts = [s for s in self.protocol(url=item.url, options=self.options).extract_frags()['segment_lists'] if s['format'] == 'subtitles']
                            # Override protocol-set identifier
                            self.processed_subts[0]['id'] = f'subtitles_{self.processed_tracks["subtitles"]}'
                            self.processed_tracks['subtitles'] += 1
                            self.segment_groups.append(self.processed_subts[0])
                            del self.protocol
                    if not hasattr(self, 'protocol'):
                        # Add it as a normal file
                        self.subtitle_segment = Segment(
                            url=item.url,
                            number=0,
                            type='subtitles',
                            group=f'subtitles_{self.processed_tracks["subtitles"]}',
                            )
                        self.subtitle_set = {
                            'segments': [self.subtitle_segment],
                            'format': 'subtitles',
                            'id': f'subtitles_{self.processed_tracks["subtitles"]}'
                        }
                        self.segment_groups.append(self.subtitle_set)
                        self.stats['files'].append(f'{temporary_dir}{self.content_sanitized}/subtitles_{self.processed_tracks["subtitles"]}_0{get_extension(item.url)}')
                        self.stats['ffmpeg_metadata'].extend(
                            [
                                '-map', str(self.stats["input_count"]['total']) + '?',
                                f'-metadata:s:s:{str(self.stats["input_count"]["subt"])}', f'language={item.language}',
                                f'-metadata:s:s:{str(self.stats["input_count"]["subt"])}', f'title={item.name}',
                            ])
                        if get_extension(item.url) == '.vtt':
                            self.stats['ffmpeg_metadata'].extend([f'-c:{self.stats["input_count"]["total"]}, srt'])
                        self.stats['input_count']['total'] += 1
                        self.stats['input_count']['subt'] += 1

    def segment_downloader(self, mode='multi'):
        '''
        ## Segment Downloader (Thread)
        ### Takes and downloads segments from the list specified at `mode`
        '''

        thread_name = threading.current_thread().name

        self.conversion_map = {
            'video': 'audio',
            'audio': 'video',
            'subtitles': 'video'
        }

        # Sets Thread-wide link to the format's segment list
        segment_list = self.segments[mode]

        threaded_vprint(
            message=f'Started Thread "{thread_name}"',
            level=4,
            module_name='penguin',
            error_level='debug',
            lock=self.print_lock)   
        
        while True:
            if not segment_list:
                if mode == 'multi':
                    return
                mode = self.conversion_map[mode]
                if not self.segments[mode]:
                    return
                segment_list = self.segments[mode]
                threaded_vprint(
                    message=f'Converted Thread "{thread_name}" to {mode}',
                    level=5,
                    module_name='penguin',
                    error_level='debug',
                    lock=self.print_lock)

            # Take an item from the fragment list
            segment = segment_list.pop(0)

            self.segment_downloaders[thread_name]['current_segment'] = segment
            self.segment_downloaders[thread_name]['segment_time'] = time()

            # TODO: do not do ffmpeg metadata generation in segment downloaders
            # This is just a quick fix
            if mode == 'subtitles' and f'{temporary_dir}{segment.output}' not in self.stats['files'] and not [f for f in self.stats['files'] if re.search(segment.group, f)]:
                self.stats['files'].append(f'{temporary_dir}{self.content_sanitized}/{segment.output}')
                self.stats['ffmpeg_metadata'].extend(['-map', str(self.stats['input_count']['total']) + '?'])
                self.stats['input_count']['total'] += 1
            if mode == 'subtitles' and get_extension(segment.url) == '.vtt':
                group_index = int(re.search(r'\d+', segment.group).group(0))
                if f'-c:s:{group_index}' not in self.stats['ffmpeg_metadata']:
                    self.stats['ffmpeg_metadata'].extend([f'-c:s:{group_index}', 'srt'])

            # Example path: ~/.Polarity/Temp/Johnny's cookies S01E01 - The return of the cookie/video_0_727.ts
            fragment_path = f'{temporary_dir}{self.content_sanitized}/{segment.id}{segment.ext}'
            # Check if segment is already downloaded
            if os.path.exists(fragment_path):
                threaded_vprint(
                    message=f'Skipping already downloaded segment {segment.id}',
                    level=5,
                    module_name='penguin',
                    error_level='debug',
                    lock=self.print_lock
                )
                if segment.group not in self.stats['segments_downloaded']:
                    self.stats['segments_downloaded'][segment.group] = 1
                else:
                    self.stats['segments_downloaded'][segment.group] += 1
                self.stats['segments_downloaded'][segment.media_type] += 1
                self.stats['segments_downloaded']['total'] += 1
                self.stats['segments_skipped'] += 1
                continue
            while True:
                # Create a cloudscraper session
                with cloudscraper.create_scraper(browser=self.browser) as session:
                    session.mount('https://', HTTPAdapter(max_retries=self.retry_config))
                    session.mount('http://', HTTPAdapter(max_retries=self.retry_config))
                    try:
                        segment_data = session.get(segment.url, timeout=self.options['penguin']['thread_timeout'])
                    except BaseException as e:
                        sleep(0.5)
                        threaded_vprint(f'exception? {e} - {thread_name}', lock=self.print_lock)
                        continue
                    try:
                        self.stats['bytes_downloaded'] += int(segment_data.headers['Content-Length'])
                    except KeyError:
                        # Skip if content-length not in headers
                        pass
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
                    with open(fragment_path, 'wb') as frag_file:
                        frag_file.write(segment_contents)

                    if segment.group not in self.stats['segments_downloaded']:
                        self.stats['segments_downloaded'][segment.group] = 1
                    else:
                        self.stats['segments_downloaded'][segment.group] += 1
                    self.stats['segments_downloaded'][segment.media_type] += 1
                    self.stats['segments_downloaded']['total'] += 1
                    self.stats['segments_downloaded']['actually_downloaded'] += 1

                    threaded_vprint(
                        f'Successfully downloaded fragment {segment.id}',
                        level=5,
                        module_name='penguin',
                        error_level='debug',
                        lock=self.print_lock)
                    
                    del segment, segment_contents, segment_data
                    
                    break

    def start(self):
        self.stats['running'] = True
        self.thread_number = 0
        def create_segment_downloader(mode=str):
            self.segment_downloaders[f'Penguin-{self.thread_number}'] = {
                'thread': 
                    Thread(
                        target=self.segment_downloader,
                        kwargs={'mode': mode},
                        daemon=True,
                        name=f'Penguin-{self.thread_number}'),
                'status': 'not_started',
                'current_segment': None,
                'segment_time': 0,
                }
            self.thread_number += 1

        def get_all_segments(mode=str):
            return [
                i
                for s in self.segment_groups
                for i in s['segments']
                if s['format'] == mode
                # Don't add already downloaded segments
                if not os.path.exists(f'{temporary_dir}{self.content_sanitized}/{i.id}{i.ext}')
                ]
        
        self.segment_downloaders = {}

        self.segments = {
            'video': get_all_segments('video'),
            'audio': get_all_segments('audio'),
            'multi': get_all_segments('multi'),
            'subtitles': get_all_segments('subtitles'),
            'total': []
        }
  
        for segment_list in self.segments:
            if segment_list == 'total':
                continue
            self.segments['total'].extend(self.segments[segment_list])
            if not self.stats['FLAGS']['loaded_from_file']:
                self.stats['total_segments'][segment_list] += len(self.segments[segment_list])
        if not self.stats['FLAGS']['loaded_from_file']:
            self.stats['total_segments']['total'] = len(self.segments['total'])

        if self.segments['multi']:            
            self.total_threads = self.options['penguin']['video_threads'] + self.options['penguin']['audio_threads']
            for _ in range(self.total_threads):
                create_segment_downloader('multi')
        else:
            for _ in range(self.options['penguin']['video_threads']):
                create_segment_downloader('video')
            for _ in range(self.options['penguin']['audio_threads']):
                create_segment_downloader('audio')
        if self.segments['subtitles']:
            create_segment_downloader('subtitles')
        
        vprint(self.lang['threads_started'] % len(self.segment_downloaders), 3, 'penguin', 'debug')
        self.stats['time_start']['download'] = time()

        # Start threads
        for downloader in self.segment_downloaders.items():
            downloader[1]['thread'].start()

        while True:
            # Wait until all threads are dead
            self.check_active_threads()
            # Remove downloaders from list
            self.segment_downloaders = {}
            # Check if all segments have been downloaded
            self.missing_segments = [
                s
                for s in self.segments['total']
                if not os.path.exists(
                    os.path.join(temporary_dir, self.content_sanitized, f'{s.id}{s.ext}')
                )]
            if not self.missing_segments:
                break
            self.segments['recovery'] = self.missing_segments
            for i in range(self.options['penguin']['recovery_threads']):
                create_segment_downloader('recovery')
            for downloader in self.segment_downloaders.items():
                downloader[1]['thread'].start()

        # Close the progress bar
        try:
            self.progress_bar.close()
        except AttributeError:
            pass
        vprint('Download process finished', 2, module_name='penguin')

        self.stats['time_start']['merge'] = time()
        vprint('Merging segments together...', 2, 'penguin')
        subprocess.run(self.build_ffmpeg_command(), check=True)

        vprint('Moving file to download folder', 2, 'penguin')
        self.stats['time_start']['moving'] = time()
        # Move file to download folder
        move(f'{temporary_dir}{self.content_sanitized}.mkv', f'{self.output_path}.mkv')
        self.stats['running'] = False
        self.stats['finished'] = True

        self.stats['time_start']['cleanup'] = time()
        # Clean-up
        vprint('Cleaning up the temporary folder...', 2, module_name='penguin')
        for file in os.scandir(f'{temporary_dir}{self.content_sanitized}'):
            os.remove(file.path)
        os.rmdir(f'{temporary_dir}{self.content_sanitized}')
        os.remove(f'{temporary_dir}{self.content_sanitized}.status')

    def check_active_threads(self):
        'Checks active threads'
        def print_active_threads():
            while True:
                # Return if there aren't segment downloaders active
                if len(self.active_threads) == 0:
                    break
                threaded_vprint(
                    message=f'Active Threads: {len(self.active_threads)}',
                    level=5,
                    module_name='penguin',
                    error_level='debug',
                    lock=self.print_lock
                )
                sleep(5)
        # Set first time so print_active_threads works
        self.active_threads = [s for s in self.segment_downloaders.items() if s[1]["thread"].is_alive()]
        Thread(target=print_active_threads, daemon=True).start()
        Thread(target=self.report_status, daemon=True).start()
        while True:
            # Check if there are any downloaders alive
            self.active_threads = [s for s in self.segment_downloaders.items() if s[1]["thread"].is_alive()]
            # vprint(f'{current_thread().name} - {humanbytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)}', 3, error_level='debug')
            if self.active_threads:
                sleep(0.5)
                continue
            return

    def build_ffmpeg_command(self):
        self.hls_files = [
            i
            for f in self.stats['files']
            for i in ['-allowed_extensions', 'ALL', '-i', os.path.abspath(f)]
            if '.m3u' in f
            ]
        self.ffmpeg_files = [
            i
            for f in self.stats['files']
            for i in ['-i', os.path.abspath(f)]
            if '.m3u' not in f
        ]
        self.stats['ffmpeg_command'].extend(self.hls_files)
        self.stats['ffmpeg_command'].extend(self.ffmpeg_files)
        self.stats['ffmpeg_command'].extend(self.stats['ffmpeg_metadata'])
        self.stats['ffmpeg_command'].append(f'{temporary_dir}{self.content_sanitized}.mkv')
        return self.stats['ffmpeg_command']


    def build_m3u8_playlist(self, playlist=dict):
        if os.path.exists(f'{temporary_dir}{self.content_sanitized}/{playlist["id"]}.m3u8'):
            return
        if playlist['format'] == 'subtitles' and len(playlist['segments']) == 1:
            return
        if playlist['id'] not in self.m3u8_playlists:
            self.m3u8_playlists[playlist['id']] = ''
        # Link to variable
        self.playlist = self.m3u8_playlists[playlist['id']]
        # Set first segment from list
        self.first_segment = playlist['segments'][0]
        self.playlist = '#EXTM3U\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-MEDIA-SEQUENCE:0\n'
        # Handle initialization segments
        self.init_segment = [f for f in playlist['segments'] if type(f) == InitSegment]
        if self.init_segment:
            self.playlist += f'#EXT-X-MAP:URI="{self.init_segment[0].output}"'
        # Handle decryption keys
        if self.first_segment.key is not None:
            self.playlist += f'#EXT-X-KEY:METHOD={self.first_segment.key_method},URI={playlist["id"]}.key\n'
            # Download the key
            with cloudscraper.create_scraper(browser=self.browser) as session:
                session.mount('https://', HTTPAdapter(max_retries=self.retry_config))
                self.key_contents = session.get(unquote(self.first_segment.key))
                # Write key to file
                with open(f'{temporary_dir}{self.content_sanitized}/{playlist["id"]}.key', 'wb') as key_file:
                    key_file.write(self.key_contents.content)
        # Add segments to playlist
        for segment in playlist['segments']:
            self.playlist += f'#EXTINF:{segment.duration},\n{segment.id}{segment.ext}\n'
        # Write end of file 
        self.playlist += '#EXT-X-ENDLIST\n'
        # Write playlist to file
        with open(f'{temporary_dir}{self.content_sanitized}/{playlist["id"]}.m3u8', 'w') as playlist_file:
            playlist_file.write(self.playlist)
        # Add playlist to inputs
        self.stats['files'].append(f'{temporary_dir}{self.content_sanitized}/{playlist["id"]}.m3u8')
        self.stats['ffmpeg_metadata'].extend([
            '-map', f'{str(self.stats["input_count"]["total"])}:v?',
            '-map', f'{str(self.stats["input_count"]["total"])}:a?',
            '-map', f'{str(self.stats["input_count"]["total"])}:s?',
            ])
        self.stats['input_count']['total'] += 1

    def report_status(self):
        # Create a tqdm progress bar
        self.progress_bar_data = {
            'desc': self.content_name,
            'total': 0,
            'initial': self.stats['bytes_downloaded'],
            'unit': 'iB',
            'unit_scale': True,
            'leave': False
        }
        self.create_progress_bar(**self.progress_bar_data)
        self.progress_bar_updated = self.stats['bytes_downloaded']
        self.stats['FLAGS']['loaded_from_file'] = True
        # Thread(target=self.print_status_thread, daemon=True).start()
        while True:
            # Refresh stats
            try:
                self.stats['estimated_total_bytes'] = self.stats['bytes_downloaded'] / self.stats['segments_downloaded']['total'] * self.stats['total_segments']['total']
            except ZeroDivisionError:
                pass

            with open(f'{temporary_dir}{self.content_sanitized}.status', 'w', encoding='utf-8') as status:
                toml.dump(self.stats, status)
            
            # Update total file size since it's really volatile
            self.progress_bar.total = self.stats['estimated_total_bytes']
            # Update the progress bar
            self.progress_bar.update(self.stats['bytes_downloaded'] - self.progress_bar_updated)
            self.progress_bar_updated = self.stats['bytes_downloaded']
            if self.stats['segments_downloaded']['total'] == self.stats['total_segments']['total']:
                return
            sleep(0.25)

class IncompatibleProtocolError(Exception):
    pass