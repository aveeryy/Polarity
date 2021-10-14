import cloudscraper
import re

from .datetime import Time

from dataclasses import dataclass

class Subtitle:
    lrc_format = r'\[(?P<time>(?:\d{2,3}:|)\d{2}:\d{2}.\d{2})\](?P<lyr>.+)'

    def __init__(self) -> None:
        self.lyrics = []
        self.metadata = {}

    def import_from_lrc(self, fp=None, url=None, path=None, contents=None):
        'Import lyrics from a lrc format file. Used in deezer'
        # Open from a io.TextIOWrapper object
        if fp is not None:
            imported = fp.read()
        # Download and open from an url
        elif url is not None:
            session = cloudscraper.create_scraper()
            imported = session.get(url).content.decode()
        # Open from a filepath
        elif path is not None:
            with open(path, 'r') as f:
                imported = f.read()
        # Use raw contents
        elif contents is not None:
            imported = contents
        for line in imported.split('\n'):
            line = line.replace('\n', '')
            metadata_line = re.match(r'\[([a-zA-Z]+):(.+)\]', line)
            if metadata_line:
                self.metadata[metadata_line.group(1)] = metadata_line.group(2)
            parsed_line = re.match(self.lrc_format, line)
            if parsed_line is None:
                continue
            line = SubtitleLine(
                text=parsed_line.group('lyr'),
                start_time=Time().from_human_time(parsed_line.group('time')),
                end_time=None,
            )
            self.lyrics.append(line)

    def export_to_lrc(self, fp=None) -> str:
        pass

@dataclass(frozen=True)
class SubtitleLine:
    start_time: Time
    end_time: Time
    text: str