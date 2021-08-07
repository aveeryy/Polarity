from polarity.utils import run_ffprobe
from polarity.version import __version__
from random import randint

from .base import BaseDownloader
from ..paths import TEMP
class FFMPEGDownloader(BaseDownloader):

    @classmethod
    def return_class(self): return __class__.__name__.lower()

    DEFAULTS = {
                'video_codec': 'copy',
                'audio_codec': 'copy',
                'subtitle_codec': 'copy',
                'extra_params': '-v error -y',
            }

    def load_at_init(self):
        self.downloader_config(
            executable_filename='ffmpeg',
            defaults=self.DEFAULTS,
            config_file_ignore=['resolution', 'concat'])
        # This file is used to report progress
        self.progress_file = f'{TEMP}ffmpeg_progress_{randint(0, 727727)}'
        self.add_arguments(f'-hide_banner -stats -progress {self.progress_file}')
        self.config_to_args()
        #self.parse_extra_urls()
        if self.options['resolution'] is not None:
            self.get_preferred_resolution()
        self.add_arguments('-metadata encoding_tool="Polarity %s | ffmpeg"' % __version__)
        self.add_raw_arguments(self.output.replace('"', ''))
    
    def config_to_args(self):
        # Add main arguments
        if 'concat' in self.options and self.options['concat']:
            self.add_arguments(['-f', 'concat', '-safe', '0'])
        self.add_raw_arguments('-i', self.url)
        self.add_arguments(f'-c:v {self.options["video_codec"]}')
        self.add_arguments(f'-c:a {self.options["audio_codec"]}')
        self.add_arguments(f'-c:s {self.options["subtitle_codec"]}')
        self.add_arguments(self.options['extra_params'])
    
    def parse_extra_urls(self):
        '''
        TODO: finish
        '''
        self.extra_id = 1
        self.extra_audio_id = 1
        self.extra_subs_id = 0
        if self.extra_audio != dict:
            for item in self.extra_audio:
                self.add_arguments('-map %d:a:0? -metadata:s:a:%d language=%s -metadata:s:a:%d title="%s"' %
                    self.extra_id, self.extra_audio_id, item['lang'], self.extra_audio_id, item['name'])
                self.extra_id += 1
                self.extra_audio_id += 1
        if self.extra_subs != dict:
            for item in self.extra_subs:
                self.add_arguments('-map %d:s:0? -metadata:s:s:%d language=%s -metadata:s:s:%d title="%s"' %
                    self.extra_id, self.extra_subs_id, item['lang'], self.extra_subs_id, item['name'])
                self.extra_id += 1
                self.extra_subs_id += 1

    def get_preferred_resolution(self):
        self.ffprobe_json = run_ffprobe(self.url)

        self.resolution_list = []
        for program in self.ffprobe_json['programs']:
            for stream in program['streams']:
                if stream['codec_type'] == 'video':
                    self.resolution_list.append((stream['index'], stream['height']))

        # Returns a tuple with resolution and duration
        try:
            return min(self.resolution_list, key=lambda x:abs(x[1]-self.options['resolution']))
        except ValueError:
            return (0, 0)