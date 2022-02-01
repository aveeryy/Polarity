import logging
import os
from dataclasses import dataclass
from getpass import getpass
from http.cookiejar import CookieJar, LWPCookieJar
from time import sleep
from typing import List, Union

from polarity.config import lang, paths
from polarity.extractor import flags
from polarity.types import Episode, Movie, SearchResult, Season, Series, Thread
from polarity.types.filter import MatchFilter, NumberFilter
from polarity.utils import dict_merge, mkfile
from polarity.utils import vprint as true_vprint


class BaseExtractor:
    def __init__(
        self,
        url: str = "",
        filter_list: list = None,
        _options: dict = None,
        _stack_id: int = 0,
    ) -> None:

        from polarity.config import options

        self.url = url
        self.extractor_name = self.__class__.__name__.replace("Extractor", "")
        self.unparsed_filters = filter_list
        # Dictionary containing what seasons and episodes to extract
        self._seasons = {}
        # List containing subextractors
        self._workers = []
        self._stack_id = _stack_id

        # create logger for capturing extractor specific messages
        # TODO: implement this in a better way

        # logging.Logger(f"extractor-{_stack_id}")
        # logging.getLogger(f"extractor-{_stack_id}").setLevel(10)

        # add the handler
        # self.log_capture = io.StringIO()

        # create a temporal handler to capture config vprint statements
        # handler = logging.StreamHandler(self.log_capture)
        # handler.setLevel(10)
        # logging.getLogger(f"extractor-{_stack_id}").addHandler(handler)

        if _options is None:
            _options = {self.extractor_name: {}}

        self.hooks = options.pop("hooks", {})

        if self.extractor_name.lower() != "base":
            self.options = dict_merge(
                options["extractor"], options, overwrite=True, modify=False
            )
            self.__opts = options["extractor"][self.extractor_name.lower()]
            self.extractor_lang = lang[self.extractor_name.lower()]

            # Do extractor validation
            self._validate_extractor()
            if not self._valid_extractor:
                return

            if flags.AccountCapabilities in self.FLAGS:
                # Account Capabilities is enabled, use the extractor's cookiejar
                cjar_path = f"{paths['account']}{self.extractor_name.lower()}.cjar"

                if not os.path.exists(cjar_path):
                    # Create the cookiejar
                    mkfile(cjar_path, "#LWP-Cookies-2.0\n")

                self.cjar = LWPCookieJar(cjar_path)
                # Load the cookiejar
                self.cjar.load(ignore_discard=True, ignore_expires=True)

        if filter_list is None or not filter_list:
            # Set seasons and episodes to extract to ALL
            self._seasons = {"ALL": "ALL"}
            self.filters = []
            self._using_filters = False
        else:
            # Parse the filter list
            self._parse_filters()
            self._using_filters = True

        if hasattr(self, "__post_init__"):
            self.__post_init__()

    def _watchdog(self):
        """
        Sets the extraction flag in case of the extraction thread dying.

        Also, executes some extraction-related hooks
        """
        # predefine hook variables
        hook_main_content = False
        while self._extractor.is_alive():
            if hasattr(self, "info") and self.info.title and not hook_main_content:
                # Extracted main content* hook
                # *Series and Movie objects
                self.__execute_hooks(
                    "extracted_main_content",
                    {
                        "title": self.info.title,
                        "type": self.info.__class__.__name__,
                        "object": self.info,
                    },
                )
                hook_main_content = True
            sleep(0.5)
        # remove handler from the logger
        logging.getLogger(f"extractor-{self._stack_id}").handlers = []
        self.info._extracted = True

    def __execute_hooks(self, hook: str, contents: dict) -> None:
        if hook not in self.hooks:
            return
        for hook_function in self.hooks[hook]:
            hook_function(contents)

    def extract(self) -> Union[Series, Movie]:
        if flags.ExtractionLoginRequired in self.FLAGS and not self.is_logged_in():
            # Check if username and password has been passed in options
            username = self.__opts["username"] if "username" in self.__opts else None
            password = self.__opts["password"] if "password" in self.__opts else None
            self.login(username, password)

        self.extraction = True
        # Return if no URL is inputted
        if not self.url or self.url is None:
            raise ExtractorError(lang["extractor"]["except"]["no_url"])
        # Create a thread to execute the extraction function in the background
        self._extractor = Thread(
            "__Extraction_Executor", self._stack_id, target=self._extract, daemon=True
        )
        _watchdog_thread = Thread(
            "__Extraction_Watchdog", self._stack_id, target=self._watchdog, daemon=True
        )
        # start the threads
        self._extractor.start()
        _watchdog_thread.start()
        self.__execute_hooks(
            "started_extraction_thread",
            {
                "status": "started",
                "thread": self._extractor,
                "self": self,
                "url": self.url,
                "options": self.options,
            },
        )
        # Return a partial information object
        while not hasattr(self, "info"):
            # Check if extractor fucking died
            sleep(0.1)

        self.info._extractor = self.extractor_name
        return self.info

    def _print_filter_warning(self) -> None:
        if not self._using_filters:
            return
        true_vprint(
            lang["extractor"]["base"]["using_filters"],
            module_name=self.__class__.__name__.lower().replace("extractor", ""),
            level="warning",
        )

    def _validate_extractor(self) -> bool:
        """Check if extractor has all needed variables"""

        @dataclass(frozen=True)
        class Condition:
            name: str
            condition: bool

        @dataclass(frozen=True)
        class Feature:
            name: str
            conditions: List[Condition]
            function: object

            def __post_init__(self):
                self.function(self)

        def check_all_or_none(feature: Feature) -> bool:
            checked = [v.condition for v in feature.conditions]
            valid = all(checked) or not any(checked)
            if not valid:
                true_vprint(
                    lang["extractor"]["base"]["check_failed"]
                    % (
                        feature.name,
                        [v.name for v in feature.conditions if not v.condition],
                    ),
                    level="error",
                )
                if self._valid_extractor:
                    self._valid_extractor = False

        def check_all(feature: Feature) -> bool:
            checked = [v.condition for v in feature.conditions]
            valid = all(checked)
            if not valid:
                true_vprint(
                    lang["extractor"]["base"]["check_failed"]
                    % (
                        feature.name,
                        [v.name for v in feature.conditions if not v.condition],
                    ),
                    level="error",
                )
                if self._valid_extractor:
                    self._valid_extractor = False

        if self.extractor_name.lower() == "base":
            return

        self._valid_extractor = True
        features = lang["extractor"]["check"]["features"]

        # The base functionality for a polarity extractor
        Feature(
            features["base"],
            [
                Condition("variable.HOST", hasattr(self, "HOST")),
                Condition("variable.ARGUMENTS", hasattr(self, "ARGUMENTS")),
                Condition("variable.DEFAULTS", hasattr(self, "DEFAULTS")),
                Condition("variable.FLAGS", hasattr(self, "FLAGS")),
                Condition("function._extract", hasattr(self, "_extract")),
                Condition("function.identify_url", hasattr(self, "identify_url")),
                Condition("function._get_url_type", hasattr(self, "_get_url_type")),
            ],
            check_all,
        )

        # Check if extractor is already invalid, cannot continue testing
        if not self._valid_extractor:
            return False

        Feature(
            features["login"],
            [
                Condition(
                    "flag.AccountCapabilities", flags.AccountCapabilities in self.FLAGS
                ),
                Condition("function._login", hasattr(self, "_login")),
                Condition("function.is_logged_in", hasattr(self, "is_logged_in")),
            ],
            check_all_or_none,
        )

        Feature(
            features["search"],
            [
                Condition("flag.EnableSearch", flags.EnableSearch in self.FLAGS),
                Condition("function._search", hasattr(self, "_search")),
            ],
            check_all_or_none,
        )

        Feature(
            features["livetv"],
            [
                Condition("flag.EnableLiveTV", flags.EnableLiveTV in self.FLAGS),
                Condition(
                    "function.get_live_tv_stream", hasattr(self, "get_live_tv_stream")
                ),
            ],
            check_all_or_none,
        )

        # if VideoExtractor in self.FLAGS:
        #     # Identification methods
        #     check_all_or_none('', 'get_series_info', 'get_season_info',
        #                       'get_seasons', 'get_episodes_from_season',
        #                       'get_episode_info', '_get_streams')

        return self._valid_extractor

    def _has_cookiejar(func):
        """
        Check if current extractor has a cookiejar before running cookiejar
        functions
        """

        def wrapper(self, *args, **kwargs):
            if not hasattr(self, "cjar"):
                raise ExtractorError(lang["extractor"]["base"]["except"]["no_cookiejar"])
            return func(self, *args, **kwargs)

        return wrapper

    @_has_cookiejar
    def save_cookies(
        self, cookies: Union[CookieJar, list], filter_list: list = None
    ) -> bool:
        for cookie in cookies:
            if filter_list is not None and cookie.name in filter_list:
                self.cjar.set_cookie(cookie=cookie)
        self.cjar.save(ignore_discard=True, ignore_expires=True)

    @_has_cookiejar
    def cookie_exists(self, cookie_name: str) -> bool:
        return cookie_name in self.cjar.as_lwp_str()

    def _parse_filters(self) -> None:
        number_filters = [f for f in self.unparsed_filters if type(f) is NumberFilter]
        match_filters = [f for f in self.unparsed_filters if type(f) is MatchFilter]
        self._parse_number_filters(number_filters)
        self.filters = match_filters
        # Delete the unparsed filters variable to save a bit of memory
        del self.unparsed_filters

    def _parse_number_filters(self, filters: list, debug=False) -> dict:
        for _filter in filters:

            if _filter.seasons and _filter.episodes:
                # S01E01-like string
                _dict = {_filter.seasons[0]: [_filter.episodes[0]]}
            elif _filter.seasons:
                # S01-like string
                _dict = {k: "ALL" for k in _filter.seasons}
            elif _filter.episodes:
                # E01-like string
                _dict = {"ALL": [k for k in _filter.episodes]}
            # self._seasons = {**self._seasons, **_dict}
            for k, v in _dict.items():
                if k not in self._seasons:
                    # Season 1 not in self.__seasons:
                    # add values (v) to self._seasons[1]
                    self._seasons[k] = v
                elif k in self._seasons and self._seasons[k] == "ALL":
                    # Season 1 in self.__seasons, self._seasons[1] value is ALL
                    # skip, since all episodes from season 1 are already set to
                    # extraction
                    continue
                elif k in self._seasons and self._seasons[k] != "ALL" and v != "ALL":
                    self._seasons[k].extend(v)
                elif k in self._seasons and self._seasons[k] != "ALL" and v == "ALL":
                    self._seasons[k] = "ALL"
            if debug:
                return _dict

    def login(self, username: str = None, password: str = None) -> bool:
        if not hasattr(self, "_login") or flags.AccountCapabilities not in self.FLAGS:
            return True
        if username is None and "username" not in self.__opts:
            username = input(lang["extractor"]["base"]["email_prompt"])
        elif username is None and "username" in self.__opts:
            username = self.__opts["username"]
        if password is None and "password" not in self.__opts:
            password = getpass(lang["extractor"]["base"]["password_prompt"])
        elif password is None and "password" in self.__opts:
            password = self.__opts["password"]
        return self._login(username=username, password=password)

    def search(
        self, term: str, max: int = -1, max_per_category: int = -1
    ) -> List[SearchResult]:
        return self._search(term, max, max_per_category)

    def check_content(self, content: Episode) -> bool:
        """Returns True if episode passes filters check"""
        # TODO: type filter check
        # Using episode object, filters apply here
        if "ALL" in self._seasons and "ALL" in self._seasons["ALL"]:
            # All episodes are set to be downloaded
            pass
        elif "ALL" in self._seasons and content.number in self._seasons["ALL"]:
            # Episode number in ALL seasons list
            # Example: download the episode 5 of every season
            pass
        elif content._season is not None:
            # Since all possibilities to be included from the "ALL"
            # list have passed now, check if the episode is in it's
            # season's list
            if (
                content._season.number in self._seasons
                and self._seasons[content._season.number] == "ALL"
            ):
                pass
            elif (
                content._season.number in self._seasons
                and content.number in self._seasons[content._season.number]
            ):
                pass
            else:
                # All possible cases have been considered
                # Episode does not pass filter tests
                return False
        elif content._season is None:
            # Orphan Episode object, not applicable
            pass
        # Finally check if passes title check
        return self._check_content_by_title(content)

    def _check_content_by_title(self, episode: Episode) -> bool:
        """Check if episode passes the title match filters"""
        passes = True
        for _filter in [f for f in self.filters if type(f) is MatchFilter]:
            match = _filter.check(episode)
            if not match and _filter.absolute:
                # Since absolute filters must always pass, return False
                return False
            # Modify variable only if 'passes' is False
            passes = match if not match else passes
        return passes

    # *--- End of BaseExtraction methods ---*#


def check_season_wrapper(func) -> Season:
    """
    Wrapper for get_season_info, avoids getting information
    from seasons that are filtered out
    """

    def wrapper(self, season: Season = None, season_id: str = None, *args, **kwargs):
        if season_id is not None:
            return func(self, season, season_id, *args, **kwargs)
        if "ALL" in self._seasons or season.number in self._seasons:
            return func(self, season, season_id, *args, **kwargs)
        # Unwanted season, don't bother getting information
        return season

    return wrapper


def check_episode_wrapper(func) -> Episode:
    """
    Wrapper for get_episode_info, avoids getting information
    from episodes that are filtered out.

    Does *not* work when inputting a bare identifier instead of a
    partial Episode object
    """

    def wrapper(self, episode: Episode = None, episode_id: str = None, *args, **kwargs):
        # Number filter check
        if episode_id is not None:
            # Do not check if episode identifier inputted directly
            pass
        elif episode is not None:
            if not self._check_episode(episode):
                return episode

        return func(self, episode=episode, episode_id=episode_id, *args, **kwargs)

    return wrapper


def requires_login(func) -> bool:
    def wrapper(self, *args, **kwargs):
        while True:
            if self.is_logged_in():
                return func(self, *args, **kwargs)
            self.login()

    return wrapper


class ExtractorError(Exception):
    pass


class InvalidURLError(Exception):
    pass


class InvalidExtractorError(Exception):
    pass
