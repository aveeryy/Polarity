from polarity.types.stream import Stream
import threading

import re
import os
import subprocess
import sys
import time

from colorama import Fore
from tqdm import tqdm

from polarity.config import config, save_config
from polarity.paths import TEMP
from polarity.utils import get_extension, sanitize_filename, vprint, send_android_notification, recurse_merge_dict

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
    def __init__(self, stream: Stream, extra_audio=None, extra_subs=None, options=dict, status_list=list, media_metadata=dict, name=str, id=str, output=str):
        self.stream = stream
        self.extra_audio = extra_audio if extra_audio is not None else []
        self.extra_subs = extra_subs if extra_subs is not None else []
        self.user_options = options
        self.downloader_name = self.return_class()[:-10].lower()
        self.options = recurse_merge_dict({self.downloader_name: self.DEFAULTS}, config['download'])
        if options != dict:
            self.options = recurse_merge_dict(self.options, self.user_options)

        self.content = f'{name} ({id})'
        self.content_name = name
        self.content_sanitized = sanitize_filename(self.content).strip('?#')
        self.output = output
        self.output_path = output.replace(get_extension(output), '')
        self.output_name = os.path.basename(output).replace(get_extension(output), '')
        self.temp_path = f'{TEMP}{self.content_sanitized}'

        # Create output and temporal paths
        os.makedirs(self.output_path.replace(self.output_name, ''), exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)
        if hasattr(self, 'load_at_init'):
            self.load_at_init()

    def write_status_dict(self, status=dict):
        '#### Write to status dict, use this instead of writing directly to `self.status`'
        self.status.clear()
        for j in status:
            self.status.append(j)

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

    def create_progress_bar(self, head='download', *args, **kwargs) -> tqdm:
        color = Fore.MAGENTA if sys.platform != 'win32' else ''
        progress_bar = tqdm(*args, **kwargs)
        progress_bar.desc = f'{color}[{head}]{Fore.RESET} {progress_bar.desc}'
        progress_bar.update(0)
        return progress_bar

    def start(self):
 
        self.subprocess = subprocess.Popen(self.launch_args)
        try:
            while self.subprocess.poll() is None:
                time.sleep(0.2)
        except KeyboardInterrupt:
            self.subprocess.kill()
            time.sleep(0.5)
            raise