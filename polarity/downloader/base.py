import os
from typing import Union

from polarity.types import Episode, Movie
from polarity.types.thread import Thread
from polarity.utils import dict_merge, sanitize_path


class BaseDownloader(Thread):
    def __init__(
        self,
        item: Union[Episode, Movie],
        _options: dict = None,
        _stack_id: int = 0,
    ) -> None:
        super().__init__(thread_type="Downloader", stack_id=_stack_id)

        from polarity.config import options, paths

        self.streams = item.streams
        if _options is None:
            _options = {}
        # merge options
        self.options = dict_merge(options["download"], _options, True, False)
        # dictionary with content name and identifier
        self.content = {
            "name": item.short_name,
            "id": item.id,
            "extended": f"{item.short_name} ({item.id})",
            "sanitized": sanitize_path(f"{item.short_name} ({item.id})").strip("?#"),
        }
        self.output = item.output
        self.temp_path = f'{paths["tmp"]}{self.content["sanitized"]}'
        self.success = False
        self._thread_id = _stack_id

    def _start(self) -> None:
        path, _ = os.path.split(self.output)
        os.makedirs(path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)

    def run(self) -> None:
        self._start()
