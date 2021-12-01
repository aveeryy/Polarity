import json
import os
import re
import subprocess
import threading
from copy import deepcopy
from dataclasses import asdict
from random import choice
from shutil import move
from time import sleep
from urllib.parse import unquote

import cloudscraper
from polarity.config import lang, paths
from polarity.downloader.base import BaseDownloader
from polarity.downloader.protocols import *
from polarity.types.ffmpeg import *
from polarity.types.stream import *
from polarity.types.progressbar import ProgressBar
from polarity.types.thread import Thread
from polarity.utils import (browser, get_extension, retry_config,
                            strip_extension, thread_vprint, vprint)
from polarity.version import __version__
from requests.adapters import HTTPAdapter


class PenguinDownloader(BaseDownloader):

    __penguin_version__ = '2021.11.30'

    thread_lock = threading.Lock()

    ARGUMENTS = [{
        'args': ['--penguin-segment-downloaders'],
        'attrib': {
            'help': lang['penguin']['args']['segment_downloaders']
        },
        'variable': 'segment_downloaders'
    }]

    DEFAULTS = {
        'segment_downloaders': 10,
        'ffmpeg': {
            'codecs': {
                'v': 'copy',
                'a': 'copy',
                # Changing this is not recommended, specially with Crunchyroll
                # since it uses SSA subtitles with styles, converting those to
                # SRT will cause them to lose all formatting
                's': 'copy'
            },
            'codec_rules': {
                '.vtt': [['s', 'srt']],
            }
        },
        'tweaks': {
            # Fixes Atresplayer subtitles italic parts
            'atresplayer_subtitle_fix': True,
            # Converts ttml2 subtitles to srt with internal convertor
            'convert_ttml2_to_srt': True,
        }
    }

    def __init__(self,
                 stream: Stream,
                 short_name: str,
                 media_id: str,
                 output: str,
                 extra_audio=None,
                 extra_subs=None,
                 _options=None) -> None:
        super().__init__(stream,
                         short_name,
                         media_id,
                         output,
                         extra_audio=extra_audio,
                         extra_subs=extra_subs,
                         _options=_options)

        self.segment_downloaders = []

        self.output_data = {
            'inputs': [],
            'segment_pools': [],
            'pool_count': {
                'video': 0,
                'audio': 0,
                'subtitles': 0,
                'unified': 0,
            },
            'total_segments': 0,
            'binary_concat': False
        }

        self.resume_stats = {
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'segments_downloaded': [],
        }

        self.indexes = {'video': 0, 'audio': 0, 'subtitles': 0, 'files': 0}

    def save_output_data(self) -> None:
        # Clone the output data dictionary
        data = deepcopy(self.output_data)
        # Convert segment pools to dictionaries
        data['segment_pools'] = [asdict(p) for p in data['segment_pools']]
        data['inputs'] = [asdict(p) for p in data['inputs']]
        with open(f'{self.temp_path}_pools.json', 'w') as f:
            # Save to file
            json.dump(data, f, indent=4)

    def load_output_data(self) -> dict:
        with open(f'{self.temp_path}_pools.json', 'r') as f:
            # Load the output data from the file
            try:
                output = json.load(f)
            except json.decoder.JSONDecodeError:
                return
        pools = []
        inputs = []
        for pool in output['segment_pools']:
            segments = []
            for segment in pool['segments']:
                # Create the content key from the dictionary data
                key = {
                    'video':
                    ContentKey(**segment['key']['video'])
                    if segment['key']['video'] is not None else None,
                    'audio':
                    ContentKey(**segment['key']['audio'])
                    if segment['key']['audio'] is not None else None
                } if segment['key'] is not None else None
                # Delete the key from the loaded data
                # This avoids SyntaxError exceptions, due to duplicate args
                del segment['key']
                # Create the segment from the content key and dict data
                _segment = Segment(key=key, **segment)
                # Add segment to temporal list
                segments.append(_segment)
            # Delete the segment list from the loaded data
            del pool['segments']
            _pool = SegmentPool(segments=segments, **pool)
            # Add pool to temporal list
            pools.append(_pool)
        for _input in output['inputs']:
            inp = FFmpegInput(**_input)
            inputs.append(inp)
        output['segment_pools'] = pools
        output['inputs'] = inputs
        return output

    def save_resume_data(self) -> None:
        if os.path.exists(f'{self.temp_path}_stats.json'):
            os.rename(f'{self.temp_path}_stats.json',
                      f'{self.temp_path}_stats.json.old')
        with open(f'{self.temp_path}_stats.json', 'w') as f:
            json.dump(self.resume_stats, f, indent=4)

    def load_resume_data(self, use_backup=False) -> dict:
        path = f'{self.temp_path}_stats.json'
        if use_backup:
            path += '.old'
        with open(path, 'rb') as f:
            try:
                return json.load(f)
            except json.decoder.JSONDecodeError:
                if use_backup:
                    # Backup file also broke, return
                    vprint('~TEMP~ backup file broke, trying to regenerate')
                    return self.regenerate_resume_data()
                vprint('~TEMP~ file broke, attempting to use backup')
                return self.load_resume_data(True)

    def regenerate_resume_data(self) -> dict:
        vprint('~TEMP~ Regenerating resume data, please wait', 1, 'penguin')
        stats = {
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'segments_downloaded': [],
        }
        for file in os.scandir(self.temp_path):
            if get_extension(file.name) in ('.m3u8'):
                continue
            stats['segments_downloaded'].append(strip_extension(file.name))
            stats['downloaded_bytes'] += file.stat().st_size

        # Calculate total bytes
        stats['total_bytes'] = stats['downloaded_bytes'] / len(
            stats['segments_downloaded']) * self.output_data['total_segments']
        return stats

    def _start(self):
        super()._start()
        self.options['penguin']['segment_downloaders'] = int(
            self.options['penguin']['segment_downloaders'])
        vprint('Starting download of ' + self.content['extended'], 1,
               'penguin')
        if os.path.exists(f'{self.temp_path}_pools.json'):
            # Open resume file
            output_data = self.load_output_data()
            if output_data is None:
                vprint('~TEMP~ Failed to load output data file, recreating', 2,
                       'penguin', 'error')
                # Remove the file
                os.remove(f'{self.temp_path}_pools.json')
            elif type(output_data) is dict:
                vprint(lang['penguin']['resuming'] % self.content['name'])
                self.output_data = output_data
        if not os.path.exists(f'{self.temp_path}_pools.json'):
            for stream in self.streams:
                self.process_stream(stream)

            # Save pools to file
            self.save_output_data()
        # Make a copy of the segment pools
        # Legacy stuff
        self.segment_pools = deepcopy(self.output_data['segment_pools'])
        if os.path.exists(f'{self.temp_path}_stats.json'):
            self.resume_stats = self.load_resume_data()

        # Create segment downloaders
        vprint(lang['penguin']['threads_started'] %
               (self.options['penguin']['segment_downloaders']),
               level=3,
               module_name='penguin',
               error_level='debug')
        for i in range(self.options['penguin']['segment_downloaders']):
            sdl_name = f'{threading.current_thread().name}/sdl{i}'
            sdl = threading.Thread(target=self.segment_downloader,
                                   name=sdl_name,
                                   daemon=True)
            self.segment_downloaders.append(sdl)
            sdl.start()

        self.progress_bar = ProgressBar(
            head='download',
            desc=self.content['name'],
            total=0,
            initial=self.resume_stats['downloaded_bytes'],
            unit='iB',
            unit_scale=True,
            leave=False,
        )
        self._last_updated = self.resume_stats['downloaded_bytes']

        # Wait until threads stop
        while True:

            # Update the total byte estimate
            try:
                self.resume_stats['total_bytes'] = self.resume_stats[
                    'downloaded_bytes'] / len(
                        self.resume_stats['segments_downloaded']
                    ) * self.output_data['total_segments']
            except ZeroDivisionError:
                pass

            self.save_resume_data()

            # Update progress bar
            self.progress_bar.total = self.resume_stats['total_bytes']
            self.progress_bar.update(self.resume_stats['downloaded_bytes'] -
                                     self._last_updated)
            self._last_updated = self.resume_stats['downloaded_bytes']

            # Check if seg. downloaders have finished
            if not [sdl for sdl in self.segment_downloaders if sdl.is_alive()]:
                self.progress_bar.close()
                self.resume_stats['download_finished'] = True
                break

            sleep(1)

        # Binary concating
        if self.output_data['binary_concat']:
            binconcat_threads = []
            for pool in self.copy_of_segment_pools:
                if pool.format == 'subtitles':
                    continue
                vprint(
                    lang['penguin']['doing_binary_concat'] %
                    (pool.id, self.content['name']), 3, 'penguin', 'debug')
                init_segment = pool.get_init_segment()
                prog_bar = ProgressBar(
                    head='binconcat',
                    desc=f'{self.content["name"]}: {pool.id}',
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
                    with open(
                            f'{self.temp_path}/{init_segment.group}_{init_segment.number}{init_segment.ext}',
                            'ab') as output_data:
                        with open(segment_path, 'rb') as input_data:
                            output_data.write(input_data.read())
                        # Delete segment
                        os.remove(segment_path)
                        prog_bar.update(1)
                prog_bar.close()

        # Widevine L3 decryption
        if self.streams[0].key and self.streams[0].key[
                'video'].method == 'Widevine':
            for pool in self.copy_of_segment_pools:
                if pool.format == 'subtitles':
                    continue
                init_segment = pool.get_init_segment()
                if not init_segment:
                    continue
                init_segment = init_segment[0]
                input_path = f'{self.temp_path}/{init_segment.group}_{init_segment.number}{init_segment.ext}'
                if not os.path.exists(input_path):
                    vprint(f'{pool.id} already decrypted. Skipping', 3,
                           'penguin', 'debug')
                    continue
                output_path = f'{self.temp_path}/{pool.id}.mp4'
                if pool.format == 'video':
                    key = self.streams[0].key['video'].raw_key
                elif pool.format == 'audio':
                    key = self.streams[0].key['audio'].raw_key
                vprint(
                    f'Decrypting track {pool.id} of {self.content["name"]} using key "{key}"',
                    3, 'penguin', 'debug')
                subprocess.run(
                    ['mp4decrypt', '--key', key, input_path, output_path])
                os.remove(input_path)

        command = self.generate_ffmpeg_command()
        Thread('__FFmpeg_Watchdog', target=self.ffmpeg_watchdog).start()

        subprocess.run(command, check=True)
        move(f'{paths["tmp"]}{self.content["sanitized"]}.mkv',
             f'{self.output}.mkv')
        for file in os.scandir(f'{paths["tmp"]}{self.content["sanitized"]}'):
            os.remove(file.path)
        os.rmdir(f'{paths["tmp"]}{self.content["sanitized"]}')
        os.remove(f'{paths["tmp"]}{self.content["sanitized"]}_stats.json')
        os.remove(f'{paths["tmp"]}{self.content["sanitized"]}_pools.json')
        os.remove(f'{self.temp_path}_stats.json.old')

    # TODO: finish threaded binary concat
    def binary_concat(self, pool: SegmentPool):
        vprint(f'Doing binary concat: {pool.id}', 3, 'penguin', 'debug')
        init_segment = pool.get_init_segment()
        prog_bar = self.create_progress_bar(
            head='binconcat',
            desc=f'{self.content["name"]}: {pool.id}',
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
            with open(
                    f'{self.temp_path}/{init_segment.group}_{init_segment.number}{init_segment.ext}',
                    'ab') as output_data:
                with open(segment_path, 'rb') as input_data:
                    output_data.write(input_data.read())
                # Delete segment
                os.remove(segment_path)
                prog_bar.update(1)
        prog_bar.close()

    # def get_segment_deletion_timings(self, pools: list[SegmentPool]) -> list:
    #     return [s for s in p.segments p for p in pools]

    def ffmpeg_watchdog(self) -> bool:
        '''
        Show ffmpeg merge progress and remove segments as they are merged
        to the master file
        '''
        # TODO: automatic removal of segments
        stats = {
            'total_size': 0,
            'out_time': None,
            'progress': 'continue',
        }

        last_update = 0
        remux_bar = ProgressBar(head='remux',
                                desc=self.content['name'],
                                unit='iB',
                                unit_scale=True,
                                leave=False,
                                total=self.resume_stats['downloaded_bytes'])
        # Wait until file is created
        while not os.path.exists(f'{self.temp_path}_ffmpeg.txt'):
            sleep(0.5)
        while stats['progress'] == 'continue':
            with open(f'{self.temp_path}_ffmpeg.txt', 'r') as f:
                try:
                    data = f.readlines()[-15:]
                    for i in ('total_size', 'out_time', 'progress'):
                        pattern = re.compile(f'{i}=(.+)')
                        # Find all matches
                        matches = re.findall(pattern, '\n'.join(data))
                        stats[i] = matches[-1]
                except IndexError:
                    sleep(0.2)
                    continue
            remux_bar.update(int(stats['total_size']) - last_update)
            last_update = int(stats['total_size'])
            sleep(0.5)
        remux_bar.close()

    def generate_ffmpeg_command(self, ) -> list:
        # Merge segments
        command = [
            'ffmpeg', '-v', 'error', '-y', '-protocol_whitelist',
            'file,crypto,data,https,http,tls,tcp'
        ]
        commands = [
            cmd.generate_command() for cmd in self.output_data['inputs']
        ]
        # Extend the input part
        for _command in commands:
            command.extend(_command['input'])
        # Extend the metadata part
        for _command in commands:
            command.extend(_command['meta'])
        command.extend([
            '-metadata',
            'encoding_tool=Polarity %s | Penguin %s' %
            (__version__, self.__penguin_version__), '-progress',
            f'{self.temp_path}_ffmpeg.txt'
        ])
        # Append the output
        command.append(f'{paths["tmp"]}{self.content["sanitized"]}.mkv')
        return command

    def generate_pool_id(self, pool_format: str) -> str:
        pool_id = f'{pool_format}{self.output_data["pool_count"][pool_format]}'

        self.output_data['pool_count'][pool_format] += 1
        return pool_id

    def process_stream(self, stream: Stream) -> None:
        if not stream.preferred:
            return
        for prot in ALL_PROTOCOLS:
            if not get_extension(stream.url) in prot.SUPPORTED_EXTENSIONS:
                continue
            processed = prot(stream=stream, options=self.options).extract()
            for pool in processed['segment_pools']:
                self.output_data['total_segments'] += len(pool.segments)
                pool.id = self.generate_pool_id(pool.format)
                if prot == HTTPLiveStream:
                    # Create a playlist from the segments
                    self.create_m3u8_playlist(pool=pool)
                elif prot == MPEGDASHStream and stream == self.streams[0]:
                    # TODO: rework
                    self.resume_stats['do_binary_concat'] = True
                self.output_data['segment_pools'].append(pool)
                self.output_data['inputs'].append(
                    self.create_input(pool=pool, stream=stream))
            return
        if not stream.extra_sub:
            vprint('~TEMP~ Stream incompatible error', 1, 'penguin', 'error')
            return
        # Process extra subtitle streams
        subtitle_pool_id = self.generate_pool_id('subtitles')
        subtitle_pool = SegmentPool([], 'subtitles', subtitle_pool_id, None,
                                    None)
        subtitle_segment = Segment(url=stream.url,
                                   number=0,
                                   media_type='subtitles',
                                   group=subtitle_pool_id,
                                   key=None,
                                   duration=None,
                                   init=False,
                                   ext=get_extension(stream.url),
                                   byte_range=None)
        subtitle_pool.segments = [subtitle_segment]
        self.output_data['segment_pools'].append(subtitle_pool)
        ff_input = self.create_input(pool=subtitle_pool, stream=stream)
        ff_input.input_path = ff_input.input_path.replace(
            subtitle_pool_id, subtitle_pool_id + '_0')
        self.output_data['inputs'].append(ff_input)

    def create_input(self, pool: SegmentPool, stream: Stream) -> FFmpegInput:
        def set_metadata(parent: str, child: str, value: str):
            if parent not in ff_input.metadata:
                ff_input.metadata[parent] = {}
            if value is None or not value:
                return
            elif type(value) is dict:
                if parent in value:
                    value = value[parent]
                elif pool.track_id in value:
                    value = value[pool.track_id]
                else:
                    return
            ff_input.metadata[parent][child] = value

        pool_extension = pool.pool_type if pool.pool_type is not None else pool.get_ext_from_segment(
        )
        segment_extension = pool.get_ext_from_segment(0)
        ff_input = FFmpegInput(
            input_path=f'{self.temp_path}/{pool.id}{pool_extension}',
            indexes={
                'file': self.indexes['files'],
                VIDEO: self.indexes['video'],
                AUDIO: self.indexes['audio'],
                SUBTITLES: self.indexes['subtitles'],
            },
            codecs=dict(self.options['penguin']['ffmpeg']['codecs']),
            metadata={},
            hls_stream='.m3u' in stream.url)

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

        for ext, rules in self.options['penguin']['ffmpeg'][
                'codec_rules'].items():
            if ext == segment_extension:
                proc = {rule[0]: rule[1] for rule in rules}
                codec_rules = {**ff_input.codecs, **proc}
                ff_input.codecs = codec_rules
                break
        return ff_input

    def segment_downloader(self):
        def get_unfinished_pools() -> list[SegmentPool]:
            return [
                p for p in self.output_data['segment_pools'] if not p._finished
            ]

        def get_unreserved_pools() -> list[SegmentPool]:
            return [
                p for p in self.output_data['segment_pools'] if not p._reserved
            ]

        def get_pool() -> SegmentPool:
            unfinished = get_unfinished_pools()
            pools = get_unreserved_pools()

            if not unfinished:
                return

            if not pools:
                pool = choice(unfinished)
                vprint(f'Assisting {pool._reserved_by} with pool {pool.id}', 4,
                       thread_name)
                return pool
            pools[0]._reserved = True
            pools[0]._reserved_by = thread_name
            return pools[0]

        thread_name = threading.current_thread().name

        thread_vprint(message=f'Started segment downloader {thread_name}',
                      level=4,
                      module_name='penguin',
                      error_level='debug',
                      lock=self.thread_lock)

        while True:

            pool = get_pool()

            if pool is None:
                return

            thread_vprint('Current pool: ' + pool.id,
                          level=4,
                          module_name=thread_name,
                          lock=self.thread_lock)
            while True:
                if not pool.segments:
                    if not pool._finished:
                        pool._finished = True
                    break

                segment = pool.segments.pop(0)

                thread_vprint(
                    message=
                    f'~TEMP~ Took segment {segment.group}_{segment.number}',
                    level=5,
                    module_name=thread_name,
                    error_level='debug',
                    lock=self.thread_lock)

                segment_path = f'{self.temp_path}/{segment.group}_{segment.number}{segment.ext}'
                if f'{segment.group}_{segment.number}' in self.resume_stats[
                        'segments_downloaded']:
                    thread_vprint(
                        message=
                        f'~TEMP~ Skipping already downloaded segment {segment.group}_{segment.number}',
                        level=5,
                        module_name='penguin',
                        error_level='debug',
                        lock=self.thread_lock)
                    continue
                # Segment download
                while True:
                    # Create a cloudscraper session
                    with cloudscraper.create_scraper(
                            browser=browser) as session:

                        session.mount('https://',
                                      HTTPAdapter(max_retries=retry_config))
                        session.mount('http://',
                                      HTTPAdapter(max_retries=retry_config))
                        try:
                            segment_data = session.get(
                                segment.url,
                                timeout=15,
                                headers={
                                    'range': f'bytes={segment.byte_range}'
                                } if segment.byte_range is not None else {})
                        except OSError as e:
                            pass
                        except BaseException as e:
                            thread_vprint(f'Exception in download: {e}',
                                          level=5,
                                          module_name=thread_name,
                                          error_level='error',
                                          lock=self.thread_lock)
                            sleep(0.5)
                            continue
                        if 'Content-Length' in segment_data.headers:
                            self.resume_stats['downloaded_bytes'] += int(
                                segment_data.headers['Content-Length'])
                        segment_contents = segment_data.content

                        if segment.ext == '.vtt':
                            # Workarounds for Atresplayer subtitles
                            # Fix italic characters
                            # Replace facing (#) characters
                            segment_contents = re.sub(
                                r'^# ',
                                '<i>',
                                segment_contents.decode(),
                                flags=re.MULTILINE)
                            # Replace trailing (#) characters
                            segment_contents = re.sub(r' #$',
                                                      '</i>',
                                                      segment_contents,
                                                      flags=re.MULTILINE)
                            # Fix aposthrophes
                            segment_contents = segment_contents.replace(
                                '&apos;', '\'').encode()
                        elif segment.ext == '.ttml2':
                            # Convert ttml2 subtitles to Subrip
                            subrip_contents = ''
                            subtitle_entries = re.findall(
                                r'<p.+</p>', segment_contents.decode())
                            i = 1
                            for p in subtitle_entries:
                                begin = re.search(r'begin="([\d:.]+)"',
                                                  p).group(1).replace(
                                                      '.', ',')
                                end = re.search(r'end="([\d:.]+)"',
                                                p).group(1).replace('.', ',')
                                contents = re.search(r'>(.+)</p>',
                                                     p).group(1).replace(
                                                         '<br/>', '\n')
                                contents = re.sub(r'<(|/)span>', '', p)
                                contents = contents.replace('&gt;', '')
                                contents = contents.strip()
                                subrip_contents += f'{i}\n{begin} --> {end}\n{contents}\n\n'
                                i += 1
                            segment_contents = subrip_contents.encode()
                            segment_path = segment_path.replace(
                                '.ttml2', '.srt')

                        # Write fragment data to file
                        with open(segment_path, 'wb') as f:
                            f.write(segment_contents)

                        thread_vprint(lang['penguin']['segment_downloaded'] %
                                      (f'{segment.group}_{segment.number}'),
                                      level=5,
                                      module_name='penguin',
                                      error_level='debug',
                                      lock=self.thread_lock)

                        segment._finished = True

                        self.resume_stats['segments_downloaded'].append(
                            f'{segment.group}_{segment.number}')
                        break

    def create_m3u8_playlist(self, pool: SegmentPool) -> None:
        '''
        Creates a m3u8 playlist from a SegmentPool's segments.


        '''
        def download_key(segment: Segment) -> None:
            with cloudscraper.create_scraper(browser=browser) as session:
                session.mount('https://',
                              HTTPAdapter(max_retries=retry_config))
                key_contents = session.get(unquote(segment.key['video'].url))
                # Write key to file
                with open(f'{self.temp_path}/{pool.id}_{key_num}.key',
                          'wb') as key_file:
                    key_file.write(key_contents.content)

        last_key = None
        key_num = 0
        # Playlist header
        playlist = '#EXTM3U\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-MEDIA-SEQUENCE:0\n'

        # Handle initialization segments
        init_segment = [f for f in pool.segments if f.init]
        if init_segment:
            init_segment = init_segment[0]
            playlist += f'#EXT-X-MAP:URI="{init_segment.group}_{init_segment.number}{init_segment.ext}"\n'

        # Add segments to playlist
        for segment in pool.segments:
            if segment.key != last_key and segment.key is not None:
                if segment.key['video'] is not None:
                    last_key = segment.key
                    playlist += f'#EXT-X-KEY:METHOD={segment.key["video"].method},URI="{self.temp_path}/{pool.id}_{key_num}.key"\n'
                    # Download the key
                    download_key(segment)
                    key_num += 1
            playlist += f'#EXTINF:{segment.duration},\n{self.temp_path}/{segment.group}_{segment.number}{segment.ext}\n'
        # Write end of file
        playlist += '#EXT-X-ENDLIST\n'
        # Write playlist to file
        with open(f'{self.temp_path}/{pool.id}.m3u8', 'w') as playlist_file:
            playlist_file.write(playlist)