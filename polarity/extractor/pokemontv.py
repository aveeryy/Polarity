# URL validation
from datetime import datetime
import re
from typing import Dict, Tuple, Union, List
from urllib.parse import urlparse

# Base functionality
from polarity.lang import lang
from polarity.extractor import flags
from polarity.extractor.base import (
    ContentExtractor,
    InvalidURLError,
)
from polarity.extractor.limelight import LimelightExtractor
from polarity.types import Episode, Movie, ProgressBar, Season, Series, Stream
from polarity.types.base import MediaType
from polarity.types.ffmpeg import AUDIO, SUBTITLES, VIDEO
from polarity.types.search import SearchResult

# Base utilities
from polarity.utils import (
    is_content_id,
    parse_content_id,
    request_json,
    request_webpage,
    vprint,
)


class PokemonTVExtractor(ContentExtractor, LimelightExtractor):
    """ """

    # Hostname(s) of extractor's webpage
    HOST = r"(?:http(?:s://|://|)|)watch\.pokemon\.com"

    API_URL = "https://www.pokemon.com/api/pokemontv/v2"

    # Default configuration for the extractor
    # Will get written to configuration file on start-up
    DEFAULTS = {}

    # Command line arguments
    ARGUMENTS = []

    # Extractor functionality flags
    # Check the polarity.extractor.flags module to see all the flags
    FLAGS = {}

    LANG_CODES = {
        "da-dk": {"name": "Dansk", "lang": "dan"},
        "de-de": {"name": "Deutsch", "lang": "ger"},
        "en-us": {"name": "English (United States)", "lang": "eng"},
        "en-gb": {"name": "English (Great Britain)", "lang": "eng"},
        "es-es": {"name": "Español (España)", "lang": "spa"},
        "es-xl": {"name": "Español (América Latina)", "lang": "spa"},
        "fi-fi": {"name": "Suomi", "lang": "fin"},
        "fr-fr": {"name": "Français (France)", "lang": "fre"},
        "it-it": {"name": "Italiano", "lang": "ita"},
        "nb-no": {"name": "Norsk", "lang": "nor"},
        "nl-nl": {"name": "Dutch", "lang": "dut"},
        "pt-br": {"name": "Português (Brasil)", "lang": "por"},
        "ru-ru": {"name": "Русский", "lang": "rus"},
        "sv-se": {"name": "Svenska", "lang": "swe"},
    }

    def __post_init__(self) -> None:
        # get the region from the webpage
        vprint(lang["pokemontv"]["get_region_info"], "debug", "pokemontv")
        page = request_webpage(self.url).content.decode()
        self.region = re.search(r"region: \"(\w{2})\"", page).group(1)
        self.language = re.search(r"language: \"([\w-]{5})\"", page).group(1)
        vprint(lang["pokemontv"]["get_channel_info"], "debug", "pokemontv")
        # get the channels information
        self.channels = request_json(f"{self.API_URL}/channels/{self.region}")[0]

    # *-- URL identification methods --* #

    def identify_url(self, url: str) -> Tuple[MediaType, Dict[MediaType, str]]:
        identifiers = {Series: None, Episode: None}
        # check if url argument is a content id
        if is_content_id(url):
            parsed = parse_content_id(url)
            url_type = parsed.content_type
            identifiers[url_type] = parsed.id
        else:
            url_type, url_ids = self._get_url_type(url)
            if url_type is Episode:
                identifiers[Episode] = url_ids[0]
                identifiers[Series] = url_ids[1]
            else:
                identifiers[Series] = url_ids[0]

        return url_type, identifiers

    @staticmethod
    def _get_url_type(url: str) -> Tuple[MediaType, str]:
        parsed = urlparse(url)
        frag = parsed.fragment

        regexes = {
            Series: r"/season\?id=(?P<id>[\w-]+)",
            Episode: r"/player\?id=(?P<id>\w+)&channelId=(?P<channel_id>[\w-]+)",
        }

        for media_type, regex in regexes.items():
            match = re.match(regex, frag)
            if match:
                # returns the media type and the id group
                # of the regex
                return media_type, match.groups()
        raise InvalidURLError(lang["extractor"]["except"]["cannot_identify_url"])

    def get_series_info(
        self, series_id: str = None, return_raw_info=False
    ) -> Union[Series, dict]:
        """
        Get the information from a Pokemon TV series (called channels on the
        website)

        :param series_id: Series/Channel identifier
        :param return_raw_info: Returns the unparsed information:
        :return: A Series object, if return_raw_info is True, dict object with
        unparsed information
        """
        info = self._get_channel(series_id)

        vprint(
            lang["extractor"]["get_media_info"]
            % (lang["types"]["alt"]["series"], info["channel_name"], series_id),
            "info",
            "pokemontv",
        )

        if return_raw_info:
            return info

        series = Series(
            title=info["channel_name"],
            id=series_id,
            extractor=self.extractor_name,
            date=datetime.fromtimestamp(info["channel_creation_date"]),
            synopsis=info["channel_description"],
            season_count=1,
            episode_count=len(info["media"]),
        )

        series._pokemontv_type = info["media_type"]

        return series

    def get_episodes_from_series(
        self, series_id: str, return_raw_info=False
    ) -> List[Union[Episode, Movie]]:
        channel_info = self._get_channel(series_id)

        if return_raw_info:
            # return the media part only
            return channel_info["media"]

        for episode in channel_info["media"]:
            yield self._parse_episode_info(episode, channel_info)

    def get_episode_info(
        self, episode_id: str, channel_id: str = None, return_raw_info=False
    ) -> Union[Episode, Movie]:

        info, channel_info = self._get_content(episode_id, channel_id, True)

        if return_raw_info:
            return info

        content = self._parse_episode_info(info, channel_info)

        return content

    def _parse_episode_info(self, episode_info: dict, channel_info: dict) -> Episode:
        episode = Episode(
            title=episode_info["title"],
            id=episode_info["id"],
            extractor=self.extractor_name,
            synopsis=episode_info["description"],
            date=datetime.fromtimestamp(episode_info["last_modified"]),
            # TODO: add images
        )

        if channel_info["media_type"] == "movie":
            episode = episode.as_movie()

        vprint(
            lang["extractor"]["get_media_info"]
            % (
                lang["types"]["alt"][type(episode).__name__.lower()],
                episode.title,
                episode.id,
            ),
            "info",
            "pokemontv",
        )

        if episode_info["episode"]:
            episode.number = int(episode_info["episode"])
        elif not episode_info["episode"]:
            # since all episodes are ordered, get the episode number
            # adding 1 to the list index
            episode.number = channel_info["media"].index(episode_info) + 1

        episode.streams = self.get_streams(episode.id)
        for stream in episode.streams:
            if stream.extra_sub:
                continue
            stream.name = {AUDIO: self.LANG_CODES[self.language]["name"]}
            stream.language = {AUDIO: self.LANG_CODES[self.language]["lang"]}

        return episode

    def _get_channel(self, id: str) -> dict:
        channels = [g for g in self.channels if g["channel_id"] == id]
        if channels:
            return channels[0]

    def _get_content(self, id: str, channel_id: str = None, get_channel=False) -> dict:
        """
        Get raw content information

        :param id: Identifier string of the content
        :param channel_id: Optional: Identifier of the channel, slightly improves
        speed if specified
        :param get_channel: Return the channel dict along the content dict
        :return: A dict object with the content information, if get_channel is True
        also returns the channel dict
        """
        if channel_id is not None:
            channel = self._get_channel(channel_id)
            contents = [c for c in channel["media"] if c["id"] == id]
        else:
            contents = [
                (c, g) for g in self.channels for c in g["media"] if c["id"] == id
            ]
            # small workaround
            *contents, channel = contents[0]
        if contents and not get_channel:
            return contents[0]
        if contents and get_channel:
            return contents[0], channel

    def _extract(self) -> Series:
        url_type, identifiers = self.identify_url(self.url)
        link_to_season = False

        series = self.get_series_info(identifiers[Series])
        self.info.link_content(series)
        if series._pokemontv_type == "episode":
            link_to_season = True
            season = Season(
                series.title,
                series.id,
                self.extractor_name,
                series.date,
                images=series.images,
                number=0,
                episode_count=series.episode_count,
                synopsis=series.synopsis,
            )
            series.link_content(season)

        if url_type is Series:
            progress_bar = ProgressBar(
                desc=series.title,
                total=series.episode_count,
                leave=False,
                head="extraction",
            )
            self._print_filter_warning()

            for episode in self.get_episodes_from_series(identifiers[Series]):
                progress_bar.update()
                if link_to_season:
                    season.link_content(episode)
                    # add number to season
                    if season.number == 0:
                        number = self._get_content(episode.id, series.id)["season"]
                        if number:
                            season.number = number
                else:
                    series.link_content(episode)

                self.check_content(episode)

            progress_bar.close()
        elif url_type is Episode:
            episode = self.get_episode_info(identifiers[Episode], identifiers[Series])

            if link_to_season:
                season.link_content(episode)
                # add number to season
                if season.number == 0:
                    number = self._get_content(episode.id, series.id)["season"]
                    if number:
                        season.number = number
            else:
                series.link_content(episode)

            self.check_content(episode)
