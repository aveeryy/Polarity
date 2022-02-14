import re
from typing import Union, List, Dict
from urllib.parse import urlparse

from polarity.config import ConfigError, lang
from polarity.extractor.base import (
    BaseExtractor,
    ExtractorError,
    check_episode_wrapper,
    requires_login,
    check_season_wrapper,
)
from polarity.extractor import flags
from polarity.types import (
    Episode,
    Movie,
    ProgressBar,
    SearchResult,
    Season,
    Series,
    Stream,
)
from polarity.types.ffmpeg import AUDIO, SUBTITLES, VIDEO
from polarity.utils import (
    is_content_id,
    parse_content_id,
    request_json,
    request_webpage,
    vprint,
)


class AtresplayerExtractor(BaseExtractor):
    """
    ## Atresplayer Extractor
    `www.atresplayer.com`
    ### Region lock
    Stuff is region locked to Spain, some content is available worldwide with a premium account
    """

    HOST = r"(?:http(?:s://|://|)|)(?:www.|)atresplayer.com"

    DEFAULTS = {
        "codec": "hevc",
    }

    API_URL = "https://api.atresplayer.com/"

    ACCOUNT_URL = "https://account.atresplayer.com/"

    LIVE_CHANNELS = {"antena3", "lasexta", "neox", "nova", "mega", "atreseries"}

    ARGUMENTS = [
        {
            "args": ["--atresplayer-codec"],
            "attrib": {
                "choices": ["avc", "hevc"],
                "default": "hevc",
                "help": lang["atresplayer"]["args"]["codec"],
            },
            "variable": "codec",
        },
        {
            "args": ["--atresplayer-email"],
            "attrib": {
                "help": lang["args"]["help"]["email"] % "Atresplayer",
            },
            "variable": "username",
        },
        {
            "args": ["--atresplayer-password"],
            "attrib": {
                "help": lang["args"]["help"]["pass"] % "Atresplayer",
            },
            "variable": "password",
        },
    ]

    FLAGS = {
        flags.VideoExtractor,
        flags.AccountCapabilities,
        flags.ExtractionLoginRequired,
        flags.EnableLiveTV,
        flags.EnableSearch,
    }

    def _login(self, username: str, password: str):

        res = request_json(
            url=f"{self.ACCOUNT_URL}auth/v1/login",
            method="POST",
            data={"username": username, "password": password},
            cookies=self.cjar,
        )
        if res[1].status_code == 200:
            vprint(lang["extractor"]["login_success"], "info", "atresplayer")
            vprint(lang["extractor"]["login_loggedas"] % username, "info", "atresplayer")
            self.save_cookies(res[1].cookies, ["A3PSID"])
            return True
        vprint(
            lang["extractor"]["login_failure"] % res[0]["error"],
            "error",
            "atresplayer",
        )
        return False

    def is_logged_in(self):
        return self.cookie_exists("A3PSID")

    @classmethod
    def identify_url(self, url: str):
        "Gets content identifier from an URL"
        # Preassign variables to None
        series_id = season_id = episode_id = None
        content_id = is_content_id(url)
        if content_id:
            parsed_content_id = parse_content_id(url)
            content_type = parsed_content_id.content_type
        elif not content_id:
            content_type = self._get_url_type(url=url)
        if content_type is None:
            return (None, {})

        # Get the series id from the page, this does not work with episodes
        # due how the player page is built
        if content_type not in (Episode, Movie):
            if not content_id:
                web = request_webpage(url).content.decode()
                series_id = re.search(
                    r"u002Fpage\\u002Fformat\\u002F(?P<id>[0-9a-f]{24})", web
                ).group(
                    1
                )  # Series ID
            else:
                series_id = parse_content_id(id=url).id
            if content_type == Season:
                if not content_id:
                    # Get season id from the seasons page's html
                    season_id = re.search(
                        r"seasonId=(?P<season_id>[0-9a-f]{24})", web
                    ).group(
                        1
                    )  # Season ID
                else:
                    season_id = parsed_content_id.id
        elif content_type in (Episode, Movie):
            if not content_id:
                # Get episode id from the inputted url
                episode_id = re.search(r"(?P<id>[0-9a-f]{24})", url).group(1)
            else:
                episode_id = parsed_content_id.id
            # Get season page from jsonld API
            json = request_json(self.API_URL + "client/v1/jsonld/episode/" + episode_id)[
                0
            ]
            season_page = request_webpage(json["partOfSeason"]["@id"]).content.decode()
            # Get the series identifier
            series_id = re.search(
                r"u002Fpage\\u002Fformat\\u002F(?P<id>[0-9a-f]{24})", season_page
            ).group(1)
            # Get the season identifier
            season_id = re.search(
                r"seasonId=(?P<season_id>[0-9a-f]{24})", season_page
            ).group(1)
        return (content_type, {Series: series_id, Season: season_id, Episode: episode_id})

    @classmethod
    def _get_url_type(self, url: str):
        url_path = urlparse(url).path
        subtypes = [
            "antena3",
            "lasexta",
            "neox",
            "nova",
            "mega",
            "atreseries",
            "flooxer",
            "kidz",
            "novelas-nova",
        ]
        regex = {
            Series: r"/[^/]+/[^/]+/\Z",
            Season: r"/[^/]+/[^/]+/[^/]+/\Z",
            Episode: r"/[^/]+/[^/]+/[^/]+/.+?_[0-9a-f]{24}/\Z",
        }
        # Check if URL has a subtype
        has_subtype = any(s in url_path for s in subtypes)
        if "/cine/" in url:
            return Movie
        for utype, regular in regex.items():
            if has_subtype:
                regular = r"/[^/]+" + regular
            if re.match(regular, url_path) is not None:
                return utype

    def get_series_info(
        self, series: Series = None, series_id: str = None, return_raw_info=False
    ) -> Union[Series, dict]:

        series_id = series.id if series is not None else series_id

        self.__series_json = request_json(
            self.API_URL + "client/v1/page/format/" + series_id
        )[0]

        if return_raw_info:
            return self.__series_json

        _episodes = request_json(
            f"{self.API_URL}client/v1/row/search",
            params={"entityType": "ATPEpisode", "formatId": series_id, "size": 1},
        )

        vprint(
            lang["extractor"]["get_media_info"]
            % (
                lang["types"]["alt"]["series"],
                self.__series_json["title"].strip(),
                series_id,
            ),
            module_name="atresplayer",
        )

        self.info = Series(
            title=self.__series_json["title"].strip(),
            id=series_id,
            synopsis=self.__series_json["description"]
            if "description" in self.__series_json
            else "",
            genres=[g["title"] for g in self.__series_json["tags"]],
            images=[
                self.__series_json["image"]["pathHorizontal"] + "1920x1080.jpg",
                self.__series_json["image"]["pathVertical"] + "720x1280.jpg",
            ],
            season_count=None,
            episode_count=_episodes[0]["pageInfo"]["totalElements"],
            year=1970,
        )

        return self.info

    def get_seasons(self, series_id: str = None, return_raw_info=False) -> List[Season]:
        vprint(lang["extractor"]["get_all_seasons"], "info", "atresplayer")

        if not hasattr(self, "__series_json"):
            if series_id is None:
                vprint(
                    lang["extractor"]["except"]["argument_missing"] % "series_id",
                    "error",
                    "atresplayer",
                )
                return
            self.get_series_info(series_id=series_id)

        is_single_season = "episode" in self.__series_json

        if return_raw_info:
            if is_single_season:
                vprint("~TEMP~ content does not have seasons", "warning")
                return
            return self.__series_json["seasons"]

        if not is_single_season:
            seasons = [
                Season(
                    title=season["title"],
                    id=season["link"]["href"][-24:],
                    **self.get_season_jsonld_info(season["link"]["href"][-24:]),
                )
                for season in self.__series_json["seasons"]
            ]
            return seasons

    def get_season_jsonld_info(self, season_id: str) -> Dict[str, int]:
        # This endpoint is only needed to get the season number and ep. count
        # For some stupid-ass reason it isn't in the season API
        season_jsonld = request_json(
            url=f"{self.API_URL}client/v1/jsonld/format/{self.info.id}",
            params={"seasonId": season_id},
        )
        return {
            "number": season_jsonld[0]["seasonNumber"],
            "episode_count": len(season_jsonld[0]["episode"]),
        }

    @check_season_wrapper
    def get_season_info(
        self, season: Season = None, season_id: str = None, return_raw_info=False
    ) -> Union[Season, dict]:

        season_id = season.id if season is not None else season_id

        # Download season info json
        season_json = request_json(
            f"{self.API_URL}client/v1/page/format/{self.info.id}",
            params={"seasonId": season_id},
        )[0]

        if return_raw_info:
            return season_json

        jsonld_info = self.get_season_jsonld_info(season_id)

        vprint(
            message=lang["extractor"]["get_media_info"]
            % (lang["types"]["alt"]["season"], season_json["title"], season_id),
            module_name="atresplayer",
        )

        season = Season(
            title=season_json["title"],
            id=season_id,
            number=jsonld_info["number"],
            images=[season_json["image"]["pathHorizontal"] + "1920x1080.jpg"],
            episode_count=jsonld_info["episode_count"],
        )
        season.synopsis = (
            season_json["description"] if "description" in season_json else ""
        )
        return season

    def get_episodes_from_season(
        self, season: Season = None, season_id: str = None, get_partial_episodes=False
    ) -> List[Episode]:

        season_id = season.id if season is not None else season_id
        page = 0
        # Placeholder until the total number of pages is known
        total_pages = 727
        while page < total_pages:
            page_json = request_json(
                url=self.API_URL + "client/v1/row/search",
                params={
                    "entityType": "ATPEpisode",
                    "formatId": self.info.id,
                    "seasonId": season_id,
                    "size": "100",
                    "page": page,
                },
            )[0]

            if "pageInfo" not in page_json:
                # If pageInfo is not in the json file, the season has no
                # content, therefore skip it
                vprint(
                    self.extractor_lang["no_content_in_season"]
                    % (page_json["title"], season_id),
                    "warning",
                    "atresplayer",
                )
                break

            # Update the number of total pages
            total_pages = page_json["pageInfo"]["totalPages"]
            for episode in page_json["itemRows"]:
                e = Episode(title=episode["title"], id=episode["contentId"])
                passes = self.check_content(e)
                if passes and not get_partial_episodes:
                    yield self.get_episode_info(episode_id=episode["contentId"])
                elif passes and get_partial_episodes:
                    yield e

            page += 1

    @check_episode_wrapper
    def get_episode_info(
        self, episode: Episode = None, episode_id: str = None, return_raw_info=False
    ) -> Union[Episode, dict]:

        episode_id = episode.id if episode is not None else episode_id

        # Download episode info json
        episode_info = request_json(
            url=f"{self.API_URL}client/v1/page/episode/" + episode_id
        )[0]

        if return_raw_info:
            return episode_info

        vprint(
            message=lang["extractor"]["get_media_info"]
            % (lang["types"]["alt"]["episode"], episode_info["title"], episode_id),
            module_name="atresplayer",
        )

        episode = Episode(
            title=episode_info["title"],
            id=episode_id,
            synopsis=episode_info["description"] if "description" in episode_info else "",
            number=episode_info["numberOfEpisode"],
            images=[episode_info["image"]["pathHorizontal"] + "1920x1080.jpg"],
        )

        self._get_streams(episode)

        # Check if the episode needs to be downloaded
        if not self.check_content(episode):
            episode.skip_download = lang["extractor"]["filter_check_fail"]

        return episode

    def _get_streams(
        self, episode: Episode = None, episode_id: str = None
    ) -> List[Stream]:

        # Create a burner Episode object to set streams to
        _episode = Episode("t", "t")
        episode_id = episode.id if episode is not None else episode_id

        # Download episode player json
        episode_player = request_json(
            f"{self.API_URL}player/v1/episode/{episode_id}",
            params={"NODRM": "true"},
            cookies=self.cjar,
        )[0]

        if "error" in episode_player:
            if episode is not None:
                episode.skip_download = episode_player["error_description"]
            return []
        else:
            # Get streams from player json
            stream_map = (
                ("application/vnd.apple.mpegurl", "hls"),
                ("application/hls+hevc", "hls_hevc"),
                ("application/hls+legacy", "hls_drmless"),
                ("application/dash+xml", "dash"),
                ("application/dash+hevc", "dash_hevc"),
            )

            streams = []

            for stream in episode_player["sources"]:
                for stream_type in stream_map:
                    if stream["type"] == stream_type[0]:
                        _stream = Stream(
                            url=stream["src"],
                            name={AUDIO: ["Español", "English"], SUBTITLES: "Español"},
                            language={AUDIO: ["es", "en"], SUBTITLES: "spa"},
                            id=stream_type[1],
                            content_type=VIDEO,
                            preferred=False,
                            key=None,
                        )
                        if episode is not None:
                            episode.link_stream(_stream)
                        _episode.link_stream(_stream)
                        streams.append(stream_type[1])

            if (
                "hls_hevc" in streams
                and self.options["atresplayer"]["codec"].lower() == "hevc"
            ):
                # Case 1: HEVC stream and preferred codec is HEVC
                preferred = "hls_hevc"
            elif (
                self.options["atresplayer"]["codec"].lower() == "avc"
                or "hls_hevc" not in streams
            ):
                # Case 2.1: Not DRM and codec preferance is AVC
                # Case 2.2: Not DRM and not HEVC stream
                preferred = "hls"
            else:
                raise ConfigError(self.extractor_lang["except"]["invalid_codec"])

            # Set preferred stream
            if episode is not None:
                episode.get_stream_by_id(preferred).preferred = True
            # This is the only reason to create a burner object lol
            _episode.get_stream_by_id(preferred).preferred = True

        return _episode.streams

    # Extra stuff

    @classmethod
    def get_all_genres(self) -> Dict[str, str]:
        """Returns a list of dicts containing name,
        id and API url of every Atresplayer genre"""
        genres = {}
        list_index = 0
        while True:
            genre_list = request_json(
                url=f"{self.API_URL}client/v1/row/search",
                params={"entityType": "ATPGenre", "size": "100", "page": list_index},
            )[0]
            for genre in genre_list["itemRows"]:
                genres[genre["title"]] = {
                    "id": genre["contentId"],
                    "api_url": genre["link"]["href"],
                }
            if genre_list["pageInfo"]["last"]:
                break
            list_index += 1
        return genres

    @requires_login
    def get_account_info(self):
        "Requires to be logged in, returns an untouched dict containing account information like name, email or gender"
        return request_json(
            "https://account.atresplayer.com/user/v1/me", cookies=self.cjar
        )[0]

    @classmethod
    def get_live_tv_stream(self, channel: str):
        "Gets the m3u8 stream of a live tv channel"

        _CHANNEL_IDS = {
            "antena3": "5a6a165a7ed1a834493ebf6a",
            "lasexta": "5a6a172c7ed1a834493ebf6b",
            "neox": "5a6a17da7ed1a834493ebf6d",
            "nova": "5a6a180b7ed1a834493ebf6e",
            "mega": "5a6a18357ed1a834493ebf6f",
            "atreseries": "5a6a189a7ed1a834493ebf70",
        }

        if channel not in _CHANNEL_IDS:
            return

        self.livetv_id = _CHANNEL_IDS[channel]
        self.channel_info = request_json(
            url=f"{self.API_URL}player/v1/live/{self.livetv_id}"
        )[0]
        return self.channel_info["sources"][0]["src"]

    def _search(self, term: str, maximum: int, max_per_type: int):
        results = {Series: [], Season: [], Episode: [], Movie: []}
        for media_type, entity in ((Series, "ATPFormat"), (Episode, "ATPEpisode")):
            search_results = request_json(
                url=self.API_URL + "client/v1/row/search",
                params={"entityType": entity, "text": term, "size": max_per_type},
            )[0]

            if "itemRows" in search_results and search_results["itemRows"]:
                for item in search_results["itemRows"]:
                    result = SearchResult(
                        item["title"],
                        media_type,
                        item["contentId"],
                        f"https://atresplayer.com{item['link']['url']}",
                        self.extractor_name,
                    )
                    results[media_type].append(result)
                    if media_type == Episode:
                        result.name = f"{item['subTitle']} - {result.name}"
                    if sum([len(t) for t in results.values()]) >= maximum and maximum > 0:
                        break

            else:
                vprint(
                    lang["extractor"]["search_no_results"] % (media_type, term),
                    "warning",
                    "atresplayer",
                )
        return results

    def _extract(self):
        url_type, identifiers = self.identify_url(url=self.url)

        if url_type in (Series, Season) and self._using_filters:
            self._print_filter_warning()

        # Get the series information
        self.get_series_info(series_id=identifiers[Series])

        if url_type == Series:
            # Gets information from all seasons
            self.progress_bar = ProgressBar(
                head="extraction",
                desc=self.info.title,
                total=self.info.episode_count,
                leave=False,
            )
            # Get all seasons' information
            for season in self.get_seasons():
                _season = self.get_season_info(season=season)
                # Link the season
                self.info.link_season(_season)
                for episode in self.get_episodes_from_season(season=_season):
                    _season.link_episode(episode)
                    self.progress_bar.update(1)
            self.progress_bar.close()

        elif url_type == Season:
            # Gets single season information
            season = self.get_season_info(season_id=identifiers[Season])
            self.info.link_season(season=season)
            self.progress_bar = ProgressBar(
                head="extraction",
                desc=self.info.title,
                total=season.episode_count,
                leave=False,
            )
            for episode in self.get_episodes_from_season(season):
                season.link_episode(episode=episode)
                self.progress_bar.update(1)
            self.progress_bar.close()

        elif url_type in (Episode, Movie):
            # Get the season information
            season = self.get_season_info(season_id=identifiers[Season])
            # Get the episode / movie information
            episode = self.get_episode_info(episode_id=identifiers[Episode])
            # Do links
            self.info.link_season(season)
            season.link_episode(episode=episode)
        elif url_type is None:
            raise ExtractorError(lang["extractor"]["except"]["cannot_identify_url"])

        return self.info
