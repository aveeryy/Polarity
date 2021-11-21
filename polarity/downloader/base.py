from polarity.utils import get_extension, dict_merge, sanitize_path
from polarity.types.thread import Thread
from polarity.types import Stream

import os


class BaseDownloader(Thread):
    def __init__(self,
                 stream: Stream,
                 short_name: str,
                 media_id: str,
                 output: str,
                 extra_audio=None,
                 extra_subs=None,
                 _options=None) -> None:
        super().__init__(thread_type='Downloader')
        from polarity.config import options, paths
        extra_audio = extra_audio if extra_audio is not None else []
        extra_subs = extra_subs if extra_subs is not None else []
        self.streams = [stream, *extra_audio, *extra_subs]
        self.options = options['download']
        self.content = {
            'name': short_name,
            'id': media_id,
            'extended': f'{short_name} ({media_id})',
            'sanitized':
            sanitize_path(f'{short_name} ({media_id})').strip('?#')
        }
        self.output = output
        self.temp_path = f'{paths["tmp"]}{self.content["sanitized"]}'

    def _start(self) -> None:
        path, _ = os.path.split(self.output)
        os.makedirs(path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)

    def run(self) -> None:
        self._start()