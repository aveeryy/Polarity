import logging
import os
from io import StringIO
from typing import Union

from polarity.types import Episode, Movie
from polarity.types.thread import Thread
from polarity.utils import dict_merge, mkfile, sanitize_path


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
            "extended": item.content_id.replace("/", "-"),
        }
        self.output = item.output
        self.temp_path = f'{paths["tmp"]}{self.content["extended"]}'
        self.success = False
        self._thread_id = _stack_id
        self.hooks = self.options["hooks"] if "hooks" in self.options else {}

    def _start(self) -> None:
        os.makedirs(self.temp_path, exist_ok=True)
        self._logger = logging.Logger(self.content["extended"], logging.DEBUG)
        self._handler = logging.FileHandler(f"{self.temp_path}/download.log")
        self._log_format = logging.Formatter("%(asctime)s -> %(message)s")
        self._handler.setFormatter(self._log_format)
        self._logger.addHandler(self._handler)
        self.logger = (self._logger, "verbose")

    def run(self) -> None:
        try:
            self._start()
        except (KeyboardInterrupt, Exception):
            # unlock the download to avoid rogue lock files
            self._unlock()
            raise

    def _execute_hooks(self, hook_name, content: dict) -> None:
        """Executes specified hook's functions by the hook name"""
        if hook_name not in self.hooks:
            return
        for hook in self.hooks[hook_name]:
            hook(content)

    def _lock(self):
        """
        Locks the current download to avoid multiple Polarity
        instances colliding with each other
        """
        mkfile(f"{self.temp_path}/lock", "")

    def _unlock(self):
        """
        Unlocks the current download to permit other instances
        to download it
        """
        os.remove(f"{self.temp_path}/lock")

    def _is_locked(self):
        """Checks if current download is locked"""
        return os.path.exists(f"{self.temp_path}/lock")
