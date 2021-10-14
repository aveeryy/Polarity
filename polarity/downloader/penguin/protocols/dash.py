import cloudscraper

from requests.adapters import HTTPAdapter
from urllib.parse import urljoin
from urllib3.util.retry import Retry

from polarity.config import lang
from polarity.downloader.penguin.protocols.base import StreamProtocol
from polarity.types.stream import *
from polarity.utils import vprint, request_xml


class MPEGDASHStream(StreamProtocol):
    SUPPORTED_EXTENSIONS = ('.mpd')
    def open_playlist(self):
        
        def process_audio_repr(repr: dict):
            if '@audioTrackId' in adap_set:
                id_entry = adap_set['@audioTrackId']
            elif '@lang' in adap_set:
                id_entry = adap_set['@lang']
            if id_entry not in audio_bitrate:
                audio_bitrate[id_entry] = (None, 0)
            if id_entry not in self.stream.language:
                self.stream.language[id_entry] = adap_set['@lang']
            if int(repr['@bandwidth']) > int(audio_bitrate[id_entry][1]):
                audio_bitrate[id_entry] = (repr, int(repr['@bandwidth']))            
        
        self.manifest_data = request_xml(self.url)[0]
        self.processed_tracks = {
            'video': -1,
            'audio': -1,
            'unified': -1,
            'subtitles': -1
        }
        resolution_list = []
        audio_bitrate = {}
        
        for adap_set in self.manifest_data['MPD']['Period']['AdaptationSet']:
            if adap_set['@contentType'] == 'video':
                vprint(lang['penguin']['protocols']['picking_best_stream_0'], 3, 'penguin/dash', 'debug')
                for repr in adap_set['Representation']:
                    resolution_list.append((repr, int(repr['@height'])))
                resolution = min(resolution_list, key=lambda x:abs(x[1]-self.options['resolution']))
                streams = [s for s in resolution_list if s[1] == resolution[1]]
                # Pick stream with higher bandwidth
                if len(streams) > 1:
                    vprint(lang['penguin']['protocols']['picking_best_stream_1'], 3, 'penguin/dash', 'debug')
                    bandwidth_values = [int(s[0]['@bandwidth']) for s in streams]
                    stream = streams[bandwidth_values.index(max(bandwidth_values))][0]
                else:
                    stream = streams[0][0]
                vprint(lang['penguin']['protocols']['selected_stream'] % stream['BaseURL'], 3, 'penguin/dash', 'debug')
                self.get_stream_fragments(stream, 'video', 'video')
            elif adap_set['@contentType'] == 'audio':
                vprint(lang['penguin']['protocols']['picking_best_stream_2'], 3, 'penguin/dash', 'debug')
                if type(adap_set['Representation']) == list:
                    for repr in adap_set['Representation']:
                        process_audio_repr(repr)
                else:
                    process_audio_repr(adap_set['Representation'])
        
        for ident, repr in audio_bitrate.items():
            self.get_stream_fragments(repr[0], ident, 'audio')

    def get_stream_fragments(self, representation: dict, track_id: str, force_type=None):
        def build_segment_pool(media_type=str):
            self.processed_tracks[media_type] += 1
            segments = [
                # Create a Segment object
                Segment(
                    url=self.stream_url,
                    number=list(representation['SegmentList']['SegmentURL']).index(s),
                    media_type=media_type,
                    key=None,
                    group=f'{media_type}{self.processed_tracks[media_type]}',
                    init=False,
                    duration=None,
                    ext=get_extension(self.stream_url),
                    mpd_range=s['@mediaRange']
                    )
                for s in representation['SegmentList']['SegmentURL']
                ]
            seg_pool = SegmentPool(segments, media_type, f'{media_type}{self.processed_tracks[media_type]}', track_id, DASHPool)
            
            return seg_pool
        def create_init_segment(pool: str) -> None:
            self.segment_pool.segments.append(
                Segment(
                    url=self.stream_url,
                    number=-1,
                    init=True,
                    media_type=pool,
                    key=None,
                    group=f'{pool}{self.processed_tracks[pool]}',
                    ext=get_extension(self.stream_url),
                    duration=None,
                    mpd_range=representation['SegmentList']['Initialization']['@range']
                )                
            )
        self.stream_url = urljoin(self.url, representation['BaseURL'])
        vprint(lang['penguin']['protocols']['getting_stream'], 3, 'penguin/dash', 'debug')

        if force_type is not None:
            self.segment_pool = build_segment_pool(force_type)
            if 'Initialization' in representation['SegmentList']:
                create_init_segment(pool=force_type)
            self.segment_pools.append(self.segment_pool)
            return

    def extract(self):
        self.retries = Retry(total=30, backoff_factor=1, status_forcelist=[502, 503, 504, 403, 404])
        # Spoof a Firefox Android browser to (usually) bypass CaptchaV2
        self.browser = {
            'browser': 'firefox',
            'platform': 'android',
            'desktop': False,
        }
        vprint(lang['penguin']['protocols']['getting_playlist'], 3, module_name='penguin/dash', error_level='debug')
        self.open_playlist()
        return {'segment_pools': self.segment_pools, 'tracks': self.processed_tracks}
