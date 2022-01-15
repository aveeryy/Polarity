from typing import Union
from polarity.utils import get_extension, dict_merge, sanitize_path
from polarity.types.thread import Thread
from polarity.types import Stream, Episode, Movie

import os


class BaseDownloader(Thread):
    def __init__(self, item: Union[Episode, Movie], _options=None) -> None:
        super().__init__(thread_type="Downloader")
        from polarity.config import options, paths

        self.streams = item.streams
        self.options = options["download"]
        self.content = {
            "name": item.short_name,
            "id": item.id,
            "extended": f"{item.short_name} ({item.id})",
            "sanitized": sanitize_path(f"{item.short_name} ({item.id})").strip("?#"),
        }
        self.output = item.output
        self.temp_path = f'{paths["tmp"]}{self.content["sanitized"]}'
        self.success = False

    def _start(self) -> None:
        path, _ = os.path.split(self.output)
        os.makedirs(path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)

    def run(self) -> None:
        self._start()
