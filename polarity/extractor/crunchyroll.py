import re
from typing import Union, Tuple, List, Dict
from urllib.parse import urlparse

from polarity.config import lang
from polarity.extractor import flags
from polarity.extractor.base import (
    BaseExtractor,
    ExtractorError,
    InvalidURLError,
    check_episode_wrapper,
    check_season_wrapper,
)
from polarity.types import (
    Episode,
    MediaType,
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
    order_dict,
    parse_content_id,
    request_json,
    request_webpage,
    vprint,
)


class CrunchyrollExtractor(BaseExtractor):

    HOST = r"(?:http(?:s://|://|)|)(?:www\.|beta\.|)crunchyroll\.com"

    DEFAULTS = {
        "sub_language": ["all"],
        "dub_language": ["all"],
        "meta_language": "en-US",
        "hardsub_language": "none",
    }

    ARGUMENTS = [
        {
            "args": ["--crunchyroll-subs"],
            "attrib": {
                "choices": [
                    "all",
                    "none",
                    "en-US",
                    "es-ES",
                    "es-LA",
                    "fr-FR",
                    "pt-BR",
                    "ar-ME",
                    "it-IT",
                    "de-DE",
                    "ru-RU",
                    "tr-TR",
                ],
                "help": lang["crunchyroll"]["args"]["subs"],
                "nargs": "+",
            },
            "variable": "sub_language",
        },
        {
            "args": ["--crunchyroll-dubs"],
            "attrib": {
                "choices": [
                    "all",
                    "ja-JP",
                    "en-US",
                    "es-LA",
                    "fr-FR",
                    "pt-BR",
                    "it-IT",
                    "de-DE",
                    "ru-RU",
                ],
                "help": lang["crunchyroll"]["args"]["dubs"],
                "nargs": "+",
            },
            "variable": "dub_language",
        },
        {
            "args": ["--crunchyroll-meta"],
            "attrib": {
                "choices": [
                    "en-US",
                    "es-LA",
                    "es-ES",
                    "fr-FR",
                    "pt-BR",
                    "ar-ME",
                    "it-IT",
                    "de-DE",
                    "ru-RU",
                ],
                "help": lang["crunchyroll"]["args"]["meta"],
            },
            "variable": "meta_language",
        },
        {
            "args": ["--crunchyroll-hardsub"],
            "attrib": {
                "choices": [
                    "none",
                    "en-US",
                    "es-LA",
                    "es-ES",
                    "fr-FR",
                    "pt-BR",
                    "ar-ME",
                    "it-IT",
                    "de-DE",
                    "ru-RU",
                ],
                "help": lang["crunchyroll"]["args"]["hard"],
            },
            "variable": "hardsub_language",
        },
        {
            "args": ["--crunchyroll-email"],
            "attrib": {
                "help": lang["args"]["help"]["email"] % "Crunchyroll",
            },
            "variable": "username",
        },
        {
            "args": ["--crunchyroll-password"],
            "attrib": {
                "help": lang["args"]["help"]["pass"] % "Crunchyroll",
            },
            "variable": "password",
        },
    ]

    account_info = {
        "basic": "Basic bm9haWhkZXZtXzZpeWcwYThsMHE6",
        "bearer": None,
        "session_id": None,
        "policy": None,
        "signature": None,
        "key_pair_id": None,
        "bucket": None,
        "country": None,
        "madurity": None,
        "email": None,
    }

    API_URL = "https://beta-api.crunchyroll.com/"

    FLAGS = {flags.AccountCapabilities, flags.EnableSearch}

    LANG_CODES = {
        "en-US": {
            "meta": "",
            "lang": "eng",
            "name": "English (USA)",
            "dub": r"\(English Dub\)",
        },
        "es-ES": {"meta": "es-es", "lang": "spa", "name": "Español (España)"},
        "es-LA": {
            "meta": "es",
            "lang": "spa",
            "name": "Español (América Latina)",
            "dub": r"\(Spanish Dub\)",
        },
        "fr-FR": {
            "meta": "fr",
            "lang": "fre",
            "name": "Français (France)",
            "dub": r"\(French Dub\)",
        },
        "pt-BR": {
            "meta": "pt-br",
            "lang": "por",
            "name": "Português (Brasil)",
            "dub": r"\(Portuguese Dub\)",
        },
        "de-DE": {
            "meta": "de",
            "lang": "ger",
            "name": "Deutsch",
            "dub": r"\(German Dub\)",
        },
        "it-IT": {
            "meta": "it",
            "lang": "ita",
            "name": "Italiano",
            "dub": r"\(Italian Dub\)",
        },
        "ar-ME": {"meta": "ar", "lang": "ara", "name": "العربية"},
        "ru-RU": {
            "meta": "ru",
            "lang": "rus",
            "name": "Русский",
            "dub": r"\(Russian\)",
        },
        "tr-TR": {"meta": "", "lang": "tur", "name": "Türkçe"},
        "ja-JP": {"meta": "", "lang": "jpn", "name": "日本語", "dub": r"[^()]"},
    }

    def __post_init__(self) -> None:
        self.proxy = {}
        self.get_bearer_token()
        self.get_cms_tokens()
        # Since there are no individual movies in Crunchyroll, set
        # information variable to a Series object
        self.info = Series()

    @staticmethod
    def check_for_error(contents: dict, error_msg: str = None) -> bool:
        if "error" in contents and contents["error"]:
            vprint(message=error_msg, module_name="crunchyroll", level="error")
            return True
        return False

    def identify_url(self, url: str) -> Tuple[MediaType, Dict[MediaType, str]]:
        """
        Returns a tuple with the url type and a dict with raw content
        identifiers related to that url
        """
        # TODO: support for season content identifiers
        series_id = season_id = episode_id = None
        if not is_content_id(url):
            url_type, url_id = self._get_url_type(url=url)
        else:
            parsed = parse_content_id(url)
            url_type = parsed.content_type
            url_id = parsed.id

        if url_id is not None and url_id.isdigit():
            # URL is a legacy one, get the new identifier
            return (
                url_type,
                self._get_etp_guid(**{f"{url_type.__name__.lower()}_id": url_id}),
            )

        if url_type == Series:
            if url_id is None:
                # Request the series' webpage and get id from page's source
                series_page = request_webpage(self.url, cookies=self.cjar)

                # Raise an Invalid URL error if page doesn't exist
                if series_page.status_code == 404:
                    raise InvalidURLError

                series_content = series_page.content.decode()
                _series_id = re.search(
                    pattern=r'ass="show-actions" group_id="(?P<id>\d{5,})"',
                    string=series_content,
                ).group(1)

                # Get series GUID from the ID
                series_id = self._get_etp_guid(series_id=_series_id)[Series]
            else:
                series_id = url_id
        elif url_type == Episode:
            # Get raw episode info
            self.__episode_info = self.get_episode_info(
                episode_id=url_id, return_raw_info=True
            )
            # Get series and season's guid using regex
            series_id = re.search(
                r"/(\w+)$", self.__episode_info["__links__"]["episode/series"]["href"]
            ).group(1)
            season_id = re.search(
                r"/(\w+)$", self.__episode_info["__links__"]["episode/season"]["href"]
            ).group(1)
            episode_id = url_id

        return (url_type, {Series: series_id, Season: season_id, Episode: episode_id})

    @staticmethod
    def _get_url_type(url: str) -> Tuple[MediaType, str]:
        is_legacy = False
        parsed_url = urlparse(url=url)
        url_host = parsed_url.netloc
        url_path = parsed_url.path
        # Identify if the url is a legacy one
        is_legacy = (
            url_host in ("www.crunchyroll.com", "crunchyroll.com")
            and "/watch/" not in url
        )
        if is_legacy:
            regexes = {
                # Regex breakdown
                # 1. (/[a-z-]{2,5}/|/) -> matches a language i.e: /es-es/ or /ru/
                # 2. (?:\w+-(?P<id>\d+) -> matches a series short url, i.e series-272199
                # 3. [^/]+) -> matches the series part of the url, i.e new-game
                # 4. (?:/$|$) -> matches the end of the url
                # 5. [\w-] -> matches the episode part of the url i.e episode-3...
                # 6. media)- -> matches an episode short url
                # 7. (?P<id>[\d]{6,}) -> matches the id on both a long and a short url, 811160  # noqa: E501
                Series: r"(?:/[a-z-]{2,5}/|/)(?:series-(?P<id>\d+)|(?!media-)[^/]+)(?:/$|$)",  # noqa: E501
                Episode: r"(?:/[a-z-]{2,5}/|/)(?:(?:[^/]+)/[\w-]+|media)-(?P<id>[\d]{6,})(?:/$|$)",  # noqa: E501
            }
        else:
            regexes = {
                # Regex breakdown
                # 1. (/[a-z-]{2,5}/|/) -> matches a language i.e: /es-es/ or /ru/
                # 2. (?P<id>[\w\d]+) -> matches the media id i.e: GVWU0P0K5
                # 3. (?:$|/[\w-]+) -> matches the end or the episode title i.e Se-cumpl...
                Series: r"(?:/[a-z-]{2,5}/|/)series/(?P<id>[\w\d]+)(?:$|/[\w-]+)(?:/$|$)",
                Episode: r"(?:/[a-z-]{2,5}/|/)watch/(?P<id>[\w\d]+)(?:$|/[\w-]+)(?:/$|$)",
            }
        for media_type, regex in regexes.items():
            match = re.match(regex, url_path)
            if match:
                return (media_type, match.group("id"))
        raise InvalidURLError

    def _get_etp_guid(
        self, series_id: int = None, season_id: int = None, episode_id: int = None
    ) -> Dict[MediaType, str]:
        """
        Support for legacy Crunchyroll identifiers

        :param (series/season/episode)_id:
        """
        info_api = "https://api.crunchyroll.com/info.0.json"
        # Define variables
        series_guid = season_guid = episode_guid = None
        if series_id is not None:
            req = request_json(
                url=info_api,
                params={"session_id": self.get_session_id(), "series_id": series_id},
                proxies=self.proxy,
            )
            if not self.check_for_error(req[0], "Failed to fetch. Content unavailable"):
                series_guid = req[0]["data"]["etp_guid"]
        elif season_id is not None:
            req = request_json(
                url=info_api,
                params={
                    "session_id": self.get_session_id(),
                    "collection_id": season_id,
                },
                proxies=self.proxy,
            )
            if not self.check_for_error(req[0], "Failed to fetch. Content unavailable"):
                series_guid = req[0]["data"]["series_etp_guid"]
                season_guid = req[0]["data"]["etp_guid"]
        elif episode_id is not None:
            req = request_json(
                url=info_api,
                params={
                    "session_id": self.get_session_id(),
                    "fields": "media.etp_guid,media.collection_etp_guid,media.series_etp_guid",
                    "media_id": episode_id,
                },
                proxies=self.proxy,
            )
            if not self.check_for_error(req[0], "Failed to fetch. Content unavailable"):
                series_guid = req[0]["data"]["series_etp_guid"]
                season_guid = req[0]["data"]["collection_etp_guid"]
                episode_guid = req[0]["data"]["etp_guid"]
        return {Series: series_guid, Season: season_guid, Episode: episode_guid}

    # Session stuff
    def get_session_id(self, save_to_cjar=False) -> str:
        """
        Returns a session identifier

        :param save_to_cjar: Save session identifier in cookie jar
        :return: Crunchyroll Session ID (string)
        """
        req = request_json(
            url="https://api.crunchyroll.com/start_session.0.json",
            headers={"content-type": "application/x-www-form-urlencoded"},
            params={
                "sess_id": "1",
                "device_type": "com.crunchyroll.static",
                "device_id": "46n8i3b963vch0.95917811",
                "access_token": "giKq5eY27ny3cqz",
            },
            proxies=self.proxy,
        )
        self.account_info["session_id"] = req[0]["data"]["session_id"]
        if save_to_cjar:
            cookie = [c for c in req[1].cookies if c.name == "session_id"][0].value
            self.save_cookies_in_jar(cookie)
        return req[0]["data"]["session_id"]

    def _login(self, username: str = None, password: str = None) -> dict:
        """
        Login into the extractor's website

        :param user: Your Crunchyroll account's email
        :param password: Your Crunchyroll account's password
        """
        session_id = self.get_session_id()
        login_req = request_json(
            url="https://api.crunchyroll.com/login.0.json",
            method="post",
            params={
                "session_id": session_id,
                "account": username,
                "password": password,
            },
            cookies=self.cjar,
        )
        if not login_req[0]["error"]:
            vprint(lang["extractor"]["login_success"], module_name="crunchyroll")
            self.save_cookies(login_req[1].cookies, ["session_id", "etp_rt"])
        else:
            vprint(
                lang["extractor"]["login_failure"] % (login_req[0]["message"]),
                module_name="crunchyroll",
                level="error",
            )
        return login_req[0]

    def is_logged_in(self) -> bool:
        """
        Returns True if user is logged in

        This does not check if session is still valid

        :return: True if user is logged into Crunchyroll, else False
        """
        return self.cookie_exists("etp_rt")

    def get_bearer_token(self, force_client_id=False) -> str:
        """Grabs Bearer Authorization token"""
        # Set token method
        # etp_rt -> logged in
        # client_id -> not logged in

        vprint(
            self.extractor_lang["bearer_fetch"],
            module_name="crunchyroll",
            level="debug",
        )
        method = (
            "etp_rt_cookie"
            if self.cookie_exists("etp_rt") and not force_client_id
            else "client_id"
        )
        vprint(self.extractor_lang["using_method"] % method, "debug", "crunchyroll")
        # Request the bearer token using the basic token,
        # to get the basic token
        token_req = request_json(
            url=self.API_URL + "auth/v1/token",
            method="post",
            headers={
                "Authorization": self.account_info["basic"],
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": method},
            cookies=self.cjar,
            proxies=self.proxy,
        )
        if "access_token" not in token_req[0]:
            vprint(lang["crunchyroll"]["bearer_fetch_fail"], "error", "crunchyroll")
            if method == "etp_rt_cookie":
                vprint(lang["extractor"]["login_extractor"], "warning" "crunchyroll")
                # TODO: BaseExtractor method
                self.cjar.clear()
                # Save the cookie jar
                self.cjar.save()
                return self.get_bearer_token(True)

        self.account_info["bearer"] = f'Bearer {token_req[0]["access_token"]}'
        return self.account_info["bearer"]

    def get_cms_tokens(self) -> Dict[str, str]:
        """Get necessary elements to build a valid API URL"""
        bucket_re = r"/(?P<country>\w{2})/(?P<madurity>M[1-3])"
        if self.account_info["bearer"] is None:
            self.get_bearer_token()
        vprint(self.extractor_lang["cms_fetch"], "debug", "crunchyroll")
        token_req = request_json(
            url=self.API_URL + "index/v2",
            headers={"Authorization": self.account_info["bearer"]},
            proxies=self.proxy,
        )[0]
        if self.check_for_error(token_req):
            raise ExtractorError(self.extractor_lang["cms_fetch_fail"])
        bucket_match = re.match(bucket_re, token_req["cms"]["bucket"])
        # These variables are used in every request as request data
        self.account_info["policy"] = token_req["cms"]["policy"]
        self.account_info["signature"] = token_req["cms"]["signature"]
        self.account_info["key_pair_id"] = token_req["cms"]["key_pair_id"]
        # Content-availability variables
        # Country and madurity are unused in actual extraction
        self.account_info["country"] = bucket_match.group("country")
        self.account_info["madurity"] = bucket_match.group("madurity")
        # This determines the
        self.account_info["bucket"] = token_req["cms"]["bucket"]
        # Build the final api url for the session
        self.CMS_API_URL = f'{self.API_URL}cms/v2{self.account_info["bucket"]}'

        return {
            "policy": self.account_info["policy"],
            "signature": self.account_info["signature"],
            "key_pair_id": self.account_info["key_pair_id"],
            "api_url": self.CMS_API_URL,
        }

    def get_series_info(
        self, series_id: str, return_raw_info=False
    ) -> Union[Series, dict]:
        if self.account_info["bearer"] is None:
            self.get_cms_tokens()
        series_json = request_json(
            url=self.CMS_API_URL + "/series/" + series_id,
            headers={"Authorization": self.account_info["bearer"]},
            params={
                "locale": self.options["crunchyroll"]["meta_language"],
                "Signature": self.account_info["signature"],
                "Policy": self.account_info["policy"],
                "Key-Pair-Id": self.account_info["key_pair_id"],
            },
        )[0]

        if return_raw_info:
            return series_json

        vprint(
            lang["extractor"]["get_media_info"]
            % (lang["types"]["alt"]["series"], series_json["title"], series_id),
            module_name="crunchyroll",
        )

        self.info.set_metadata(
            title=series_json["title"],
            id=series_id,
            synopsis=series_json["description"],
            genres=series_json["keywords"],
            images=[
                series_json["images"]["poster_tall"][0][-1:][0]["source"],
                series_json["images"]["poster_wide"][0][-1:][0]["source"],
            ],
            episode_count=series_json["episode_count"],
            season_count=series_json["season_count"],
            year=re.search(r"(\d+)", series_json["season_tags"][0]).group(0)
            if series_json["season_tags"]
            else 1970,
        )

        return self.info

    def get_seasons(self, series_id: str, return_raw_info=False) -> List[Season]:

        season_list = []
        vprint(lang["extractor"]["get_all_seasons"], module_name="crunchyroll")

        api_season_list = request_json(
            self.CMS_API_URL + "/seasons",
            params={
                "series_id": series_id,
                "locale": self.options["crunchyroll"]["meta_language"],
                "Signature": self.account_info["signature"],
                "Policy": self.account_info["policy"],
                "Key-Pair-Id": self.account_info["key_pair_id"],
            },
        )[0]
        if return_raw_info:
            return api_season_list

        for season in api_season_list["items"]:
            # Get dub language from the title using regex
            for _lang, values in self.LANG_CODES.items():
                if "dub" not in values:
                    # Skip languages without dubs
                    continue
                elif re.search(values["dub"], season["title"]):
                    language = _lang
                    break

            _season = Season(
                title=season["title"], id=season["id"], number=season["season_number"]
            )

            # Add dub language attribute
            _season._crunchyroll_dub = language

            season_list.append(_season)
        return season_list

    @check_season_wrapper
    def get_season_info(
        self, season: Season = None, season_id: str = None, return_raw_info=False
    ) -> Union[Season, dict]:
        """
        Returns a full Season object from specified season identifier or from
        a partial Season object

        Only one season parameter is required
        :param season: Partial Season object
        :param season_id: Season identifier
        :param return_raw_info: Returns the JSON directly, without parsing
        :return: Full Season object, or dict if return_raw_info
        """
        _season = season if season is not None else Season()
        _season_id = season.id if season is not None else season_id

        season_json = request_json(
            self.CMS_API_URL + "/seasons/" + _season_id,
            headers={"Authorization": self.account_info["bearer"]},
            params={
                "locale": self.options["crunchyroll"]["meta_language"],
                "Signature": self.account_info["signature"],
                "Policy": self.account_info["policy"],
                "Key-Pair-Id": self.account_info["key_pair_id"],
            },
        )[0]
        if return_raw_info:
            return season_json

        vprint(
            lang["extractor"]["get_media_info"]
            % (lang["types"]["alt"]["season"], season_json["title"], _season_id),
            module_name="crunchyroll",
        )

        metadata = {
            "title": season_json["title"],
            "id": _season_id,
            "number": season_json["season_number"],
        }

        _season.set_metadata(**metadata)

        return _season

    def get_episodes_from_season(
        self,
        season_id: str = None,
        season: Season = None,
        return_raw_info=False,
        get_partial_episodes=False,
    ) -> Union[List[Episode], dict]:
        """
        Return a list with full Episode objects from the episodes of the
        season

        Only one season parameter is required
        :param season_id: Season's identifier
        :param season: Season object
        :param return_raw_info: Returns the JSON directly without parsing
        :param threaded: Run with multiple threads
        :return: Returns a Full Episode object (with streams) if
        return_raw_info is False, else returns unparsed JSON dict
        """
        identifier = season_id if season_id is not None else season.id
        if identifier is None:
            raise ExtractorError(lang["extractor"]["except"]["no_id"])

        unparsed_list = request_json(
            self.CMS_API_URL + "/episodes",
            params={
                "season_id": identifier,
                "locale": self.options["crunchyroll"]["meta_language"],
                "Signature": self.account_info["signature"],
                "Policy": self.account_info["policy"],
                "Key-Pair-Id": self.account_info["key_pair_id"],
            },
        )[0]
        if return_raw_info:
            return unparsed_list

        if hasattr(self, "season") or season is not None:
            # Add episode count attribute to season
            _season = season if season is not None else self.season
            _season.episode_count = len(unparsed_list["items"])

        for episode in unparsed_list["items"]:
            # Create a partial episode object to check if passes filter check
            e = Episode(
                title=episode["title"],
                id=episode["id"],
                number=episode["episode_number"],
            )
            e._season = season if season is not None else None
            if self.check_content(e) and not get_partial_episodes:
                yield self._parse_episode_info(episode)
            elif self.check_content(e) and get_partial_episodes:
                yield e
            if hasattr(self, "progress_bar"):
                self.progress_bar.update()

    @check_episode_wrapper
    def get_episode_info(
        self, episode: Episode, episode_id: str, return_raw_info=False, get_streams=True
    ) -> Union[Episode, dict]:
        """
        Get information from an episode using it's identifier or a partial
        Episode object

        Either an Episode object with an id or the raw id is required
        :param episode: Partial Episode object
        :param episode_id: Episode identifier
        :param return_raw_info: Returns the JSON directly, without parsing
        :param get_streams: Run the _get_streams function automatically
        :return: Full Episode object if not return_raw_info, else a dict
        """

        _episode_id = episode.id if episode is not None else episode_id

        episode_info = request_json(
            self.CMS_API_URL + "/episodes/" + _episode_id,
            headers={"Authorization": self.account_info["bearer"]},
            params={
                "locale": self.options["crunchyroll"]["meta_language"],
                "Signature": self.account_info["signature"],
                "Policy": self.account_info["policy"],
                "Key-Pair-Id": self.account_info["key_pair_id"],
            },
        )[0]
        if return_raw_info:
            return episode_info

        episode = self._parse_episode_info(episode_info, get_streams=get_streams)
        if not self.check_content(episode):
            if not hasattr(episode, "skip_download"):
                # If episode has not a skip reason already, add one
                episode.skip_download = lang["extractor"]["filter_check_fail"]
        return episode

    def _parse_episode_info(self, episode_info: dict, get_streams=True) -> Episode:
        """Parses info from an episode's JSON"""
        vprint(
            lang["extractor"]["get_media_info"]
            % (
                lang["types"]["alt"]["episode"],
                episode_info["title"],
                episode_info["id"],
            ),
            module_name="crunchyroll",
        )
        episode = Episode(
            title=episode_info["title"],
            id=episode_info["id"],
            synopsis=episode_info["description"],
            number=episode_info["episode_number"],
        )
        # If content does not have an episode number, assume it's a movie
        if episode.number is None:
            episode = episode.convert_to_movie()
            if episode_info["season_tags"]:
                episode.year = re.search(r"(\d+)", episode_info["season_tags"][0]).group(
                    0
                )

        episode._partial = False

        if get_streams and "playback" in episode_info:
            episode.streams = self._get_streams(episode_info["playback"])
        elif get_streams and "playback" not in episode_info:
            episode.skip_download = lang["extractor"]["skip_dl_premium"]

        return episode

    def _get_streams(
        self,
        playback_url: str = None,
        episode: Episode = None,
        episode_id: str = None,
    ) -> List[Stream]:
        """
        Get streams from an inputted episode identifier

        Also allows getting streams directly using the playback url

        Only one parameter is required
        :param playback_url: Direct playback url
        :param episode: Episode object, requires having an identifier set
        :param episode_id: Episode identifier
        :return: list with Stream objects if successful, else empty list
        """

        streams = []

        # Set the streams page URL
        if playback_url is not None:
            playback = playback_url
        elif episode is not None or episode_id is not None:
            _id = episode.id if episode is not None else episode_id
            # Get raw episode info JSON
            inf = self.get_episode_info(episode_id=_id, return_raw_info=True)
            if "playback" not in inf:
                return streams
            playback = inf["playback"]

        streams_json = request_json(url=playback)[0]
        # Case 1: Disabled hardsubs or desired hardsub language does not exist
        if (
            self.options["crunchyroll"]["hardsub_language"] == "none"
            or self.options["crunchyroll"]["hardsub_language"]
            not in streams_json["streams"]["adaptive_hls"]
        ):
            is_preferred = "ja-JP"
        # Case 2: Desired hardsub language exists
        elif (
            self.options["crunchyroll"]["hardsub_language"]
            in streams_json["streams"]["adaptive_hls"]
        ):
            is_preferred = streams_json["streams"]["adaptive_hls"][
                self.options["crunchyroll"]["hardsub_language"]
            ]["hardsub_locale"]

        for stream in streams_json["streams"]["adaptive_hls"].values():
            if stream["hardsub_locale"] == "":
                stream["hardsub_locale"] = "ja-JP"
            _stream = Stream(
                url=stream["url"],
                id="video",
                preferred=stream["hardsub_locale"] == is_preferred,
                name={
                    VIDEO: self.LANG_CODES[stream["hardsub_locale"]]["name"],
                    AUDIO: self.LANG_CODES[streams_json["audio_locale"]]["name"],
                },
                language={
                    VIDEO: self.LANG_CODES[stream["hardsub_locale"]]["lang"],
                    AUDIO: self.LANG_CODES[streams_json["audio_locale"]]["lang"],
                },
            )
            streams.append(_stream)

        # Create subtitle stream list
        subtitles = [
            Stream(
                url=s["url"],
                name=self.LANG_CODES[s["locale"]]["name"],
                language=self.LANG_CODES[s["locale"]]["lang"],
                preferred="all" in self.options["crunchyroll"]["sub_language"]
                or s in self.options["crunchyroll"]["sub_language"],
            )
            for s in order_dict(
                to_order=streams_json["subtitles"], order_definer=self.LANG_CODES
            ).values()
        ]
        for subtitle in subtitles:
            subtitle.extra_sub = True
            streams.append(subtitle)

        return streams

    def _search(self, term: str, maximum: int, max_per_type: int) -> List[SearchResult]:
        def parse_group(data: dict, media_type: MediaType):
            parsed_items = 0
            for result in data["items"]:
                # Halt if surpassed the per type limit
                if parsed_items >= max_per_type and max_per_type > 0:
                    break
                # Create a SearchResult object
                parsed_result = SearchResult(
                    result["title"],
                    media_type,
                    result["id"],
                    url=build_url(result["id"], media_type),
                    extractor=self.extractor_name,
                )
                if media_type == Episode:
                    parsed_result.name = f"{result['episode_metadata']['series_title']} - {parsed_result.name}"
                # Add parsed result to respective list
                results[media_type].append(parsed_result)
                parsed_items += 1

        def build_url(id: str, media_type: MediaType) -> str:
            """Builds a valid Crunchyroll URL from the inputted id and type"""
            component = {Series: "series", Episode: "watch", Movie: "watch"}

            return f"https://crunchyroll.com/{component[media_type]}/{id}"

        results = {Series: [], Season: [], Episode: [], Movie: []}
        search_results = request_json(
            url=self.API_URL + "content/v1/search",
            headers={
                "Authorization": self.account_info["bearer"],
            },
            params={
                "q": term,
                "n": maximum if maximum > 0 else 1000,
                "locale": self.options["crunchyroll"]["meta_language"],
            },
        )[0]

        for n, group in enumerate((Series, Movie, Episode)):
            # Get the results
            parse_group(search_results["items"][n + 1], group)

        return results

    def _extract(self):
        url_type, url_ids = self.identify_url(url=self.url)

        if url_type == Series:
            series_guid = url_ids[Series]
            self.get_series_info(series_id=series_guid)

            self.progress_bar = ProgressBar(
                desc=self.info.title,
                total=self.info.episode_count,
                leave=False,
                head="extraction",
            )

            # This is required when extracting a series
            # Prints a warning when using filters to tell the user that
            # the progress bar will be inaccurate
            self._print_filter_warning()

            for season in self.get_seasons(series_id=series_guid):
                if (
                    "all" not in self.options["crunchyroll"]["dub_language"]
                    and season._crunchyroll_dub
                    not in self.options["crunchyroll"]["dub_language"]
                ):
                    vprint(
                        lang["crunchyroll"]["unwanted_season"] % season.title,
                        "warning",
                        "crunchyroll",
                    )
                    continue

                self.get_season_info(season=season)
                self.info.link_season(season=season)
                for episode in self.get_episodes_from_season(season=season):
                    season.link_episode(episode=episode)

        elif url_type == Episode:
            # Get series and season info
            self.get_series_info(series_id=url_ids[Series])
            self.season = self.get_season_info(season_id=url_ids[Season])
            self.info.link_season(season=self.season)
            # Parse the raw episode info
            # Reusing the info fetched from the get_identifier function
            # since there's no point in doing it again
            if hasattr(self, "__episode_info"):
                episode = self._parse_episode_info(episode_info=self.__episode_info)
            else:
                episode = self.get_episode_info(episode_id=url_ids[Episode])
            # Link the episode with the season
            self.season.link_episode(episode=episode)
        # Since extraction has finished, remove the partial flag
        self.info._partial = False
