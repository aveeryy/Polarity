import logging
import os
from dataclasses import dataclass
from getpass import getpass
from http.cookiejar import CookieJar, LWPCookieJar
from time import sleep
from typing import List, Union

from polarity.config import paths
from polarity.lang import lang
from polarity.extractor import flags
from polarity.types import Episode, Movie, SearchResult, Season, Series, Thread
from polarity.types.content import Content, ContentContainer
from polarity.types.filter import MatchFilter, NumberFilter, TypeFilter
from polarity.utils import dict_merge, mkfile, vprint


class BaseExtractor:
    """
    The base class for other *Extractor classes

    Do NOT use this as a parent class for an extractor, instead use
    ContentExtractor or StreamExtractor
    """

    def __init__(self, url: str, _options: dict = None, _thread_id: int = 0) -> None:
        from polarity.config import options

        self.url = url
        self.options = _options
        self._thread_id = _thread_id
        self.extractor_name = self.__class__.__name__.replace("Extractor", "")
        self.hooks = options.pop("hooks", {})
        if _options is not None:
            dict_merge(self.hooks, _options.pop("hooks", {}), False, True, True)

        if _options is None:
            _options = {self.extractor_name: {}}

        if self.extractor_name.lower() not in ("base", "content", "stream"):
            self.options = dict_merge(
                options["extractor"], _options, overwrite=True, modify=False
            )
            self._opts = options["extractor"][self.extractor_name.lower()]


class ContentExtractor(BaseExtractor):
    def __init__(
        self,
        url: str = "",
        filter_list: list = None,
        _options: dict = None,
        _thread_id: int = 0,
    ) -> None:

        super().__init__(url, _options, _thread_id)

        self.unparsed_filters = filter_list
        # Dictionary containing what seasons and episodes to extract
        self._seasons = {}
        self.info = ContentContainer("initial", "__polarity_initial")

        if hasattr(self, "FLAGS") and flags.AccountCapabilities in self.FLAGS:
            if self.options.get("save_login_info", True):
                # Account Capabilities is enabled, use the extractor's cookiejar
                cjar_path = f"{paths['account']}{self.extractor_name.lower()}.cjar"

                if not os.path.exists(cjar_path):
                    # Create the cookiejar
                    mkfile(cjar_path, "#LWP-Cookies-2.0\n")

                self.cjar = LWPCookieJar(cjar_path)
            else:
                # create an empty cookiejar cookiejar
                self.cjar = LWPCookieJar()
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
        while self._extractor.is_alive():
            sleep(0.5)
        # remove handler from the logger
        logging.getLogger(f"extractor-{self._thread_id}").handlers = []
        self.info._extracted = True

    def __execute_hooks(self, hook: str, contents: dict) -> None:
        if hook not in self.hooks:
            return
        for hook_function in self.hooks[hook]:
            hook_function(contents)

    def extract(self) -> Union[Series, Movie]:
        if (
            "username" in self._opts
            and self._opts["username"] is not None
            and "password" in self._opts
            and self._opts["password"] is not None
            and flags.AccountCapabilities in self.FLAGS
        ):
            self.login(self._opts["username"], self._opts["password"])

        self.extraction = True
        # Return if no URL is inputted
        if not self.url or self.url is None:
            raise ExtractorError(lang["extractor"]["except"]["no_url"])
        # Create a thread to execute the extraction function in the background
        self._extractor = Thread(
            "__Extraction_Executor", self._thread_id, target=self._extract, daemon=True
        )
        _watchdog_thread = Thread(
            "__Extraction_Watchdog", self._thread_id, target=self._watchdog, daemon=True
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

    ###################
    # Cookiejar stuff #
    ###################

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
    def save_cookies(self, cookies: Union[CookieJar, list], filter_list: list = None):
        """
        Import cookies from another cookiejar / a list of Cookie objects

        :param cookies: Cookiejar / list of cookies
        :param filter_list: Cookies to import (list of cookies' names)
        """
        for cookie in cookies:
            if (
                filter_list is None
                or filter_list is not None
                and cookie.name in filter_list
            ):
                self.cjar.set_cookie(cookie=cookie)
        self.cjar.save(ignore_discard=True, ignore_expires=True)

    @_has_cookiejar
    def cookie_exists(self, cookie_name: str) -> bool:
        """Checks if the cookie exists in the jar"""
        return cookie_name in self.cjar.as_lwp_str()

    def login(self, username: str = None, password: str = None) -> bool:
        """
        Login into the extractor's website

        :param username: Account's email/username
        :param password: Account's password
        """
        if not hasattr(self, "_login"):
            return True
        if username is None and "username" not in self._opts:
            username = input(lang["extractor"]["base"]["email_prompt"])
        elif username is None and "username" in self._opts:
            username = self._opts["username"]
        if password is None and "password" not in self._opts:
            password = getpass(lang["extractor"]["base"]["password_prompt"])
        elif password is None and "password" in self._opts:
            password = self._opts["password"]
        return self._login(username=username, password=password)

    def search(
        self, term: str, max: int = -1, max_per_category: int = -1
    ) -> List[SearchResult]:
        return self._search(term, max, max_per_category)

    ##################################
    # Content filtering and checking #
    ##################################

    def notify_extraction(self, content: Union[Content, ContentContainer]):
        content.extractor = self.extractor_name
        self.__execute_hooks("extracted_content", {"content": content})

    def check_content(self, content: Union[Content, ContentContainer]) -> bool:
        def check() -> bool:
            if isinstance(content, Content):
                # check if content passes type checks
                if not self._check_content_by_type(content):
                    return False
                # check if content passes name checks
                if not self._check_content_by_title(content):
                    return False
                # if content is an episode, check for
                if type(content) is Episode:
                    # final check, return
                    return self._check_episode(content)
            elif type(content) is Season:
                return self._check_season(content)
            return True

        if not check():
            # set the unwanted tag on the content
            content.set_unwanted()
            return False
        return True

    def _check_season(self, season: Season) -> bool:
        return "ALL" in self._seasons or season.number in self._seasons

    def _check_episode(self, episode: Episode) -> bool:
        """Check an episode against parsed NumberFilter objects"""
        # FIXME: this probably could be improved to have less "pass"
        # keywords

        # Using episode object, filters apply here
        if "ALL" in self._seasons and "ALL" in self._seasons["ALL"]:
            # All episodes are set to be downloaded
            pass
        elif "ALL" in self._seasons and episode.number in self._seasons["ALL"]:
            # Episode number in ALL seasons list
            # Example: download the episode 5 of every season
            pass
        elif episode._season is not None:
            # Since all possibilities to be included from the "ALL"
            # list have passed now, check if the episode is in it's
            # season's list
            if (
                episode._season.number in self._seasons
                and self._seasons[episode._season.number] == "ALL"
            ):
                pass
            elif (
                episode._season.number in self._seasons
                and episode.number in self._seasons[episode._season.number]
            ):
                pass
            else:
                # All possible cases have been considered
                # Episode does not pass filter tests
                return False
        elif episode._season is None:
            # Orphan Episode object, not applicable
            pass
        return True

    def _check_content_by_type(self, content: Content) -> bool:
        """Check content against TypeFilter objects"""
        filters = [f for f in self.filters if type(f) is TypeFilter]
        if not filters:
            return True
        for _filter in filters:
            if _filter.check(content):
                return True
        return False

    def _check_content_by_title(self, content: Content) -> bool:
        """Check content against MatchFilter objects"""
        passes = True
        filters = [f for f in self.filters if type(f) is MatchFilter]
        if not filters:
            return True
        for _filter in filters:
            match = _filter.check(content)
            if not match and _filter.absolute:
                # Since absolute filters must always pass, return False
                return False
            # Modify variable only if 'passes' is False
            passes = match if not match else passes
        return passes

    def _parse_filters(self) -> None:
        """Parses non-NumberFilter episodes and adds them to self.filters"""
        number_filters = [f for f in self.unparsed_filters if type(f) is NumberFilter]
        self._seasons = self._parse_number_filters(number_filters)
        self.filters = [f for f in self.unparsed_filters if type(f) != NumberFilter]

    def _parse_number_filters(self, filters: list) -> dict:
        """Parse NumberFilter filters into a dict with seasons and episodes to extract"""
        _final = {}  # The final result
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
            for k, v in _dict.items():
                # k is the season, e the episodes / content
                if k not in _final:
                    # Season 1 not in _final:
                    # add values (v) to _final[k]
                    _final[k] = v
                elif k in _final and _final[k] == "ALL":
                    # Season (k) is in _final and _final[k] value is ALL (episodes)
                    # skip, since all episodes from that season are already set to
                    # extraction
                    pass
                elif k in _final and _final[k] != "ALL" and v != "ALL":
                    # Season is in _final and _final[k] value is not ALL, therefore
                    # is a list of episodes, extend that list
                    _final[k].extend(v)
                elif k in _final and _final[k] != "ALL" and v == "ALL":
                    # Season is in final and _final[k] value is not ALL, but new
                    # value is ALL, therefore, replace the list will ALL
                    _final[k] = "ALL"
        return _final

    def _print_filter_warning(self) -> None:
        if not self._using_filters:
            return
        vprint(
            lang["extractor"]["base"]["using_filters"],
            module_name=self.__class__.__name__.lower().replace("extractor", ""),
            level="warning",
        )


class StreamExtractor(BaseExtractor):
    """
    StreamExtractor class

    A complimentary class for ContentExtractor instances,

    Subclasses of StreamExtractor need to be inherited along
    the ContentExtractor class

    Example:

    >>> from polarity.extractor.base import ContentExtractor
    >>> from polarity.extractor.limelight import LimelightExtractor
    >>> class MyExtractor(ContentExtractor, LimelightExtractor):
    >>>     ...
    """

    pass


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
