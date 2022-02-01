from polarity.config import paths
from polarity.utils import ContentIdentifier

from typing import List


class DownloadLog:
    def __init__(self, path: str = paths["dl_log"], update_path: bool = True) -> None:
        self.__path = path
        self.__update = update_path
        self.__entries = self._load_log()

    def add(self, id: str):
        identifier = id.string if type(id) is ContentIdentifier else id
        self.__entries = self._load_log()
        # add the entry
        self.__entries.append(identifier)
        # save log to file
        self._save_log()

    def in_log(self, id: str) -> bool:
        """Returns True if content identifier is in download log"""
        # update the log entries
        self.__entries = self._load_log()
        # if id is a contentidentifier object, get the raw_string
        identifier = id.string if type(id) is ContentIdentifier else id
        return identifier in self.__entries

    def _load_log(self) -> List[str]:
        if self.__update:
            self.__path = paths["dl_log"]
        self.__log = open(self.__path).read()
        return self.__log.split("\n")

    def _save_log(self):
        with open(self.__path, "w") as f:
            f.write("\n".join(self.__entries))

    @property
    def entries(self) -> List[str]:
        return self.__entries

    @property
    def path(self):
        return self.__path
