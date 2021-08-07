from polarity.utils import vprint
import cloudscraper
from urllib.parse import urljoin
from m3u8 import parse
from .base import StreamProtocol
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from polarity.downloader.base import Segment, InitSegment

class HTTPLiveStream(StreamProtocol):
    SUPPORTED_EXTENSIONS = ('.m3u', '.m3u8')
    def open_playlist(self):
        self.manifest_data = self.scraper.get(self.url).content
        self.parsed_data = parse(self.manifest_data.decode())
        self.processed_tracks = {
            'video': -1,
            'audio': -1,
            'unified': -1,
            'subtitles': -1
        }
        if self.parsed_data['is_variant']:
            # get preferred resolution stream
            self.resolutions = [
                (s, int(s['stream_info']['resolution'].split('x')[1] if 'resolution' in s['stream_info'] else 0))
                for s in self.parsed_data['playlists']
                ]
            self.resolution = min(self.resolutions, key=lambda x:abs(x[1]-self.options['resolution']))
            self.streams = [s for s in self.resolutions if s[1] == self.resolution[1]]
            if len(self.streams) > 1:
                self.bandwidth_values = [s[0]['stream_info']['bandwidth'] for s in self.streams]
                self.stream = self.streams[self.bandwidth_values.index(max(self.bandwidth_values))][0]
            else:
                self.stream = self.streams[0][0]
        else:
            self.stream = self.parsed
            

    def get_stream_fragments(self, stream=dict, force_type=None):
        def build_segment_list(media_type=str):
            self.processed_tracks[media_type] += 1
            return {
                'segments': [
                    # Create a Segment object
                    Segment(
                        url=urljoin(self.stream_url, s['uri']),
                        number=self.parsed_stream['segments'].index(s),
                        type=media_type,
                        key=s['key']['uri'] if 'key' in s else None,
                        key_method=s['key']['method'] if 'key' in s else None,
                        duration=s['duration'],
                        group=f'{media_type}{self.processed_tracks[media_type]}',
                        )
                    for s in self.parsed_stream['segments']],
                'format': media_type,
                'id': f'{media_type}{self.processed_tracks[media_type]}'
            }
        self.stream_url = urljoin(self.url, stream['uri'])
        vprint('Getting stream data', 1, 'penguin/hls', 'debug')
        self.stream_data = self.scraper.get(self.stream_url).content
        self.parsed_stream = parse(self.stream_data.decode())
        # Support for legacy m3u8 playlists
        # (Not having video and audio in different streams)
        if force_type is not None:
            self.segment_set = build_segment_list(force_type)
            if 'segment_map' in self.parsed_stream:
                self.segment_set['segments'].append(
                    InitSegment(
                        url=urljoin(self.stream_url, self.parsed_stream['segment_map']['uri']),
                        number=99999,
                        type=force_type,
                        group=f'{force_type}{self.processed_tracks[force_type]}'
                    )
                )
            self.segment_list.append(self.segment_set)
            return

        if 'audio' not in stream['stream_info']:
            self.segment_set = build_segment_list('unified')
            if 'segment_map' in self.parsed_stream:
                self.segment_set['segments'].append(
                    InitSegment(
                        url=urljoin(self.stream_url, self.parsed_stream['segment_map']['uri']),
                        number=99999,
                        type='unified',
                        group=f'{"unified"}{self.processed_tracks["unified"]}'
                    )
                )
        else:
            self.segment_set = build_segment_list('video')
        self.segment_list.append(self.segment_set)
        if 'segment_map' in self.parsed_stream:
            self.segment_set['segments'].append(
                InitSegment(
                    url=urljoin(self.stream_url, self.parsed_stream['segment_map']['uri']),
                    number=99999,
                    type='video',
                    group=f'{"video"}{self.processed_tracks["video"]}'
                )
            )       
        # Open extra media
        if 'audio' in stream['stream_info']:
            self.audio_group = stream['stream_info']['audio']
        if 'subtitles' in stream['stream_info']:
            self.subt_group = stream['stream_info']['subtitles']
        for media in self.parsed_data['media']:
            if media['type'] == 'AUDIO':
                self.get_stream_fragments(media, 'audio')
            elif media['type'] == 'SUBTITLES':
                if '.m3u' in media['uri']:
                    self.get_stream_fragments(media, 'subtitles')
                else:
                    self.subt_contents = self.scraper.get(urljoin(self.url, media['uri'])).content
                    # Fuck whoever thought it was a good idea to disguise m3u8 playlists as .vtt subtitles
                    if b'#EXTM3U' in self.subt_contents:
                        self.get_stream_fragments(media, 'subtitles')
                        continue
                    self.processed_tracks['subtitles'] += 1
                    self.subtitle_object = Segment(
                        url=urljoin(self.url, media['uri']),
                        number=0,
                        type='subtitles',
                        group=f'subtitles{self.processed_tracks["subtitles"]}',
                    )
                    self.subtitle_set = {
                        'segments': [self.subtitle_object],
                        'format': 'subtitles',
                        'id': f'subtitles{self.processed_tracks["subtitles"]}'
                    }
                    self.segment_list.append(self.subtitle_set)    

    def extract_frags(self):
        self.retries = Retry(total=30, backoff_factor=1, status_forcelist=[502, 503, 504, 403, 404])
        # Spoof a Firefox Android browser to (usually) bypass CaptchaV2
        self.browser = {
            'browser': 'firefox',
            'platform': 'android',
            'desktop': False,
        }
        vprint('Getting playlist data', module_name='penguin/hls', error_level='debug')
        self.scraper = cloudscraper.create_scraper(browser=self.browser)
        self.scraper.mount('https://', HTTPAdapter(max_retries=self.retries))
        self.open_playlist()
        self.get_stream_fragments(self.stream)
        return {'segment_lists': self.segment_list, 'tracks': self.processed_tracks}
