import cloudscraper
import re

from .datetime import Time

class Lyrics:
    lrc_format = r'\[(?P<time>(?:\d{2,3}:|)\d{2}:\d{2}.\d{2})\](?P<lyr>.+)'

    def __init__(self) -> None:
        self.lyrics = []

    def import_from_lrc(self, fp=None, url=None, path=None, contents=None):
        'Import lyrics from a lrc format file. Used in deezer'
        # Open from a io.TextIOWrapper object
        if fp is not None:
            self.__imported = fp.read()
        # Download and open from an url
        elif url is not None:
            session = cloudscraper.create_scraper()
            self.__imported = session.get(url).content.decode()
        # Open from a filepath
        elif path is not None:
            with open(path, 'r') as f:
                self.__imported = f.read()
        # Use raw contents
        elif contents is not None:
            self.__imported = contents
        for line in self.__imported.split('\n'):
            line = line.replace('\n', '')
            print(line)
            if re.match(r'\[(?:ar|al|ti):.+\]', line):
                continue
            self.__parsed_line = re.match(self.lrc_format, line)
            if self.__parsed_line is None:
                continue
            self.__line = LyricLine()
            self.__line.lyrics = self.__parsed_line.group('lyr')
            self.__line.time = Time().time_to_unix(self.__parsed_line.group('time'))
            self.lyrics.append(self.__line)

    def export_to_lrc(self, fp=None) -> str:
        pass

class LyricLine:
    def __init__(self) -> None:
        self.time = None
        self.lyrics = None