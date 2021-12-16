import os
import re
from getpass import getpass
from http.cookiejar import CookieJar, LWPCookieJar
from time import sleep
from typing import Union

from polarity.config import config, lang, paths
from polarity.extractor.flags import *
from polarity.types import Episode, Season, Series, Movie
from polarity.types.filter import MatchFilter, NumberFilter
from polarity.types.thread import Thread
from polarity.utils import dict_merge, mkfile, vprint


class BaseExtractor:
    def __init__(self,
                 url: str,
                 filter_list: list = None,
                 options: dict = None) -> None:

        from polarity.config import options as user_options

        self.url = url
        self.extractor_name = self.__class__.__name__.replace('Extractor', '')
        if options is None:
            options = {self.extractor_name.lower(): {}}
        if self.extractor_name.lower() != 'base':
            # self.options = dict_merge(user_options['extractor'],
            #                           options,
            #                           overwrite=True,
            #                           modify=False)
            self.options = user_options['extractor']
            self.__opts = user_options['extractor'][
                self.extractor_name.lower()]
            self.extractor_lang = lang[self.extractor_name.lower()]
            self._validate_extractor()

            if AccountCapabilities in self.FLAGS:
                # Account Capabilities is enabled, use the extractor's cookiejar
                cjar_path = f"{paths['account']}{self.extractor_name.lower()}.cjar"

                if not os.path.exists(cjar_path):
                    # Create the cookiejar
                    mkfile(cjar_path, '#LWP-Cookies-2.0\n')

                self.cjar = LWPCookieJar(cjar_path)
                # Load the cookiejar
                self.cjar.load(ignore_discard=True, ignore_expires=True)

                if LoginRequired in self.FLAGS and not self.is_logged_in():
                    # Check if username and password has been passed in options
                    username = self.__opts[
                        'username'] if 'username' in self.__opts else None
                    password = self.__opts[
                        'password'] if 'password' in self.__opts else None
                    self.login(username, password)

        self.unparsed_filters = filter_list

        # Dictionary containing what seasons and episodes to extract
        self._seasons = {}
        # List containing subextractors
        self._workers = []

        if filter_list is None or not filter_list:
            # Set seasons and episodes to extract to ALL
            self._seasons = {'ALL': 'ALL'}
            self.filters = []
            self._using_filters = False
        else:
            # Parse the filter list
            self._parse_filters()
            self._using_filters = True

    def _watchdog(self):
        '''Set the extraction flag in case of the extraction thread dying'''
        while self._extractor.is_alive():
            sleep(0.5)
        self.info._extracted = True

    def extract(self) -> Union[Series, Movie]:
        self.extraction = True
        # Return if no URL is inputted
        if not self.url or self.url is None:
            raise ExtractorError('~TEMP~ No URL inputted')
        # Create a thread to execute the extraction function in the background
        self._extractor = Thread('__Extraction_Executor',
                                 target=self._extract,
                                 daemon=True)
        _watchdog_thread = Thread('__Extraction_Watchdog',
                                  target=self._watchdog,
                                  daemon=True)
        self._extractor.start()
        _watchdog_thread.start()
        # Return a partial information object
        while not hasattr(self, 'info'):
            # Check if extractor fucking died
            sleep(0.1)
        self.info._extractor = self.extractor_name
        return self.info

    def _print_filter_warning(self) -> None:
        if not self._using_filters:
            return
        vprint(
            '~TEMP~ Using filters, total count in progress bar will be inaccurate',
            module_name=self.__class__.__name__.lower().replace(
                'extractor', ''),
            error_level='warning')

    def _validate_extractor(self) -> bool:
        '''Check if extractor has all needed variables'''
        def check_variables(*_vars):
            '''
            Raise an ExtractorError if a variable does not exist in
            class scope
            '''
            missing = [v for v in _vars if not hasattr(self, v)]
            if missing:
                raise InvalidExtractorError(
                    f'Extractor {self.extractor_name.lower()} is invalid! Missing variables: {missing}'
                )

        if self.extractor_name.lower() == 'base':
            return

        # Check if extractor has all necessary variables
        check_variables(
            'HOST',
            'ARGUMENTS',
            'DEFAULTS',
            'FLAGS',
            '_extract',
            'identify_url',
            '_get_url_type',
        )

        if VideoExtractor in self.FLAGS:
            # Identification methods
            check_variables('get_series_info', 'get_season_info',
                            'get_seasons', 'get_episodes_from_season',
                            'get_episode_info', '_get_streams')

        if AccountCapabilities in self.FLAGS:
            # Check if extractor has necessary login variables
            check_variables('_login', 'is_logged_in')
        return True

    def _has_cookiejar(func):
        '''
        Check if current extractor has a cookiejar before running cookiejar
        functions
        '''
        def wrapper(self, *args, **kwargs):
            if not hasattr(self,
                           'cjar') or AccountCapabilities not in self.FLAGS:

                raise ExtractorError('no cookiejar')
            return func(self, *args, **kwargs)

        return wrapper

    @_has_cookiejar
    def save_cookies(self,
                     cookies: Union[CookieJar, list],
                     filter_list: list = None) -> bool:
        for cookie in cookies:
            if filter_list is not None and cookie.name in filter_list:
                self.cjar.set_cookie(cookie=cookie)

    @_has_cookiejar
    def cookie_exists(self, cookie_name: str) -> bool:
        return cookie_name in self.cjar.as_lwp_str()

    def _parse_filters(self) -> None:
        number_filters = [
            f for f in self.unparsed_filters if type(f) is NumberFilter
        ]
        match_filters = [
            f for f in self.unparsed_filters if type(f) is MatchFilter
        ]
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
                _dict = {k: 'ALL' for k in _filter.seasons}
            elif _filter.episodes:
                # E01-like string
                _dict = {'ALL': [k for k in _filter.episodes]}
            # self._seasons = {**self._seasons, **_dict}
            for k, v in _dict.items():
                if k not in self._seasons:
                    # Season 1 not in self.__seasons:
                    # add values (v) to self._seasons[1]
                    self._seasons[k] = v
                elif k in self._seasons and self._seasons[k] == 'ALL':
                    # Season 1 in self.__seasons, self._seasons[1] value is ALL
                    # skip, since all episodes from season 1 are already set to
                    # extraction
                    continue
                elif k in self._seasons and self._seasons[
                        k] != 'ALL' and v != 'ALL':
                    self._seasons[k].extend(v)
                elif k in self._seasons and self._seasons[
                        k] != 'ALL' and v == 'ALL':
                    self._seasons[k] = 'ALL'
            if debug:
                return _dict

    def login(self, username: str = None, password: str = None) -> bool:
        if not hasattr(self,
                       '_login') or AccountCapabilities not in self.FLAGS:
            return True
        if username is None:
            username = input(lang['extractor']['base']['email_prompt'])
        if password is None:
            password = getpass(lang['extractor']['base']['password_prompt'])
        return self._login(username=username, password=password)

    def check_episode(self, episode: Episode) -> bool:
        '''Returns True if episode passes filters check'''
        # Using episode object, filters apply here
        if 'ALL' in self._seasons and 'ALL' in self._seasons['ALL']:
            # All episodes are set to be downloaded
            pass
        elif 'ALL' in self._seasons and episode.number in self._seasons['ALL']:
            # Episode number in ALL seasons list
            pass
        elif episode._season is not None:
            # Since all possibilities to be included from the "ALL"
            # list have passed now, check if the episode is in it's
            # season's list
            if episode._season.number in self._seasons and self._seasons[
                    episode._season.number] == 'ALL':
                pass
            elif episode._season.number in self._seasons and \
                episode.number in self._seasons[episode._season.number]:
                pass
            else:
                # All possible cases have been considered
                # Episode does not pass filter tests
                return False
        elif episode._season is None:
            # Orphan Episode object, not applicable
            pass
        # Finally check if passes title check
        return self._check_episode_by_title(episode=episode.title)

    def _check_episode_by_title(self, episode: Episode) -> bool:
        '''Check if episode passes the title match filters'''
        passes = True
        for _filter in self.filters:
            match = _filter.check(title=episode.title)
            if not match and _filter.absolutes:
                # Since absolute filters must always pass, return False
                return False
            # Modify variable only if 'passes' is False
            passes = match if not match else passes
        return passes


def check_season_wrapper(func) -> Season:
    '''
    Wrapper for get_season_info, avoids getting information
    from seasons that are filtered out
    '''
    def wrapper(self,
                season: Season = None,
                season_id: str = None,
                *args,
                **kwargs):
        if season_id is not None:
            return func(self, season, season_id, *args, **kwargs)
        if 'ALL' in self._seasons or season.number in self._seasons:
            return func(self, season, season_id, *args, **kwargs)
        # Unwanted season, don't bother getting information
        return season

    return wrapper


def check_episode_wrapper(func) -> Episode:
    '''
    Wrapper for get_episode_info, avoids getting information
    from episodes that are filtered out.

    Does *not* work when inputting a bare identifier instead of a
    partial Episode object
    '''
    def wrapper(self,
                episode: Episode = None,
                episode_id: str = None,
                *args,
                **kwargs):
        # Number filter check
        if episode_id is not None:
            # Do not check if episode identifier inputted directly
            pass
        elif episode is not None:
            if not self._check_episode(episode):
                return episode

        return func(self,
                    episode=episode,
                    episode_id=episode_id,
                    *args,
                    **kwargs)

    return wrapper


def check_login_wrapper(func) -> bool:
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