import threading

import re
import os
import subprocess
import sys
import time

from colorama import Fore
from tqdm import tqdm

from polarity.config import config, save_config
from polarity.paths import TEMP as temporary_dir
from polarity.utils import get_extension, vprint, send_android_notification, recurse_merge_dict

class BaseDownloader:
    '''
    ## Base downloader
    ### Defines the base of a downloader with support for external downloaders
        >>> from polarity.downloader import BaseDownloader
        >>> class MyExternalDownloader(BaseDownloader):
        >>>     def load_at_init(self):
                self.downloader_config(...)
                # Stuff to load at init here
    '''
    def __init__(self, stream=None, extra_audio=None, extra_subs=dict, options=dict, status_list=list, media_metadata=dict, name=str, id=str, output=str):
        self.stream = stream
        self.extra_audio = extra_audio
        self.extra_subs = extra_subs
        self.user_options = options
        self.downloader_name = self.return_class()[:-10]
        if self.downloader_name not in config['download'] and hasattr(self, 'DEFAULTS'):
            config['download'][self.downloader_name] = self.DEFAULTS
            save_config()
        self.options = recurse_merge_dict({self.downloader_name: self.DEFAULTS}, config['download'])
        if options != dict:
            self.options = recurse_merge_dict(self.options, self.user_options)
        self.status = status_list
        self.media_metadata = media_metadata
        self.content_name = name
        self.content_id = id
        self.content = f'{name} ({id})'
        self.output = output
        self.output_path = output.replace(get_extension(output), '')
        self.output_name = os.path.basename(output).replace(get_extension(output), '')

        if not os.path.exists(self.output_path.replace(self.output_name, '')):
            try:
                os.makedirs(self.output_path.replace(self.output_name, ''))
            except FileExistsError:
                pass
        if not os.path.exists(f'{temporary_dir}{self.output_name}'):
            os.makedirs(f'{temporary_dir}{self.output_name}')
        self.segment_list = []
        self.status = []
        self.load_at_init()

    def write_status_dict(self, status=dict):
        '#### Write to status dict, use this instead of writing directly to `self.status`'
        self.status.clear()
        for j in status:
            self.status.append(j)

    def print_status_thread(self):
        while True:
            self.android_notification = ''
            if 'finished' in self.status:
                return
            for item in self.status:
                vprint(item['str'], item['verbose'], 'polarity/status')
                self.android_notification += item['str'] + '\n'
            vprint('=' * 30)
            send_android_notification(f'Polarity ({threading.current_thread().name})', self.android_notification, 'download_status', threading.current_thread().name)
            time.sleep(5)

    def downloader_config(
        self,
        executable_filename=str,
        defaults=dict,
        config_file_ignore=list):
        self.launch_args = [executable_filename]
        if not executable_filename in config['download']:
            config['download'][executable_filename] = {k: v for k, v in defaults if k not in config_file_ignore}
        self.options = recurse_merge_dict(defaults, config['download'][executable_filename])
        if self.user_options != dict:
            self.options = recurse_merge_dict(self.options, self.user_options)

    def add_raw_arguments(self, *args):
        self.launch_args.extend(args)

    def add_arguments(self, args=str):
        '''
        Converts a string containing launch arguments to a list
        
        ### Example:

        `--monkey "likes bananas" -a --nd --thats cool`
        becomes:

        `['--monkey', 'likes bananas', '-a', '--nd', '--thats', 'cool']`
        '''
        for self.a in re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', args):
            self.a = self.a.replace('"', '')
            self.launch_args.append(self.a)

    def create_progress_bar(self, *args, **kwargs):
        color = Fore.MAGENTA if sys.platform != 'win32' else ''
        self.progress_bar = tqdm(*args, **kwargs)
        self.progress_bar.desc = f'{color}[download]{Fore.RESET} {self.progress_bar.desc}'
        self.progress_bar.update(0)

    def start(self):
 
        self.subprocess = subprocess.Popen(self.launch_args)
        try:
            while self.subprocess.poll() is None:
                time.sleep(0.2)
        except KeyboardInterrupt:
            self.subprocess.kill()
            time.sleep(0.5)
            raise

# TODO: create a type for this
class Segment:
    '''
    Defines a segment
    '''
    def __init__(self, url=str, number=int, type=str, key=None, key_method=None, duration=float, group=str):
        self.url = url
        self.number = number
        self.media_type = type
        self.key = key
        self.key_method = key_method
        self.duration = duration
        self.id = f'{group}_{number}'
        self.group = group
        self.ext = get_extension(self.url)
        self.output = f'{self.id}{self.ext}'

class InitSegment(Segment):
    pass