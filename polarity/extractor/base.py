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
from polarity.types.progressbar import ProgressBar
from polarity.utils import dict_merge, mkfile, vprint


class BaseExtractor(Thread):
    def __init__(self,
                 url: str,
                 filter_list: list = None,
                 options: dict = None) -> None:
        super().__init__(thread_type='Extractor', daemon=True)

        from polarity.config import options as user_options

        self.url = url
        self.extractor_name = self.__class__.__name__.replace('Extractor',
                                                              '').lower()
        if options is None:
            options = {self.extractor_name: {}}
        if self.extractor_name != 'base':
            self.options = dict_merge(user_options['extractor'],
                                      options,
                                      overwrite=True,
                                      modify=False)
            self.extractor_lang = lang[self.extractor_name]

        self.unparsed_filters = filter_list

        # Dictionary containing what seasons and episodes to extract
        self._seasons = {}
        # List containing subextractors
        self._workers = []

        if AccountCapabilities in self.FLAGS:
            # Account Capabilities is enabled, use the extractor's cookiejar
            cjar_path = f"{paths['account']}{self.extractor_name}.cjar"
            if not os.path.exists(cjar_path):
                # Create the cookiejar
                mkfile(cjar_path, '#LWP-Cookies-2.0\n')
            self.cjar = LWPCookieJar(cjar_path)
            # Load the cookiejar
            self.cjar.load(ignore_discard=True, ignore_expires=True)

        if filter_list is None:
            # Set seasons and episodes to extract to ALL
            self._seasons = {'ALL': 'ALL'}
            self._using_filters = False
        else:
            # Parse the filter list
            self._parse_filters()
            self._using_filters = True

    def extract(self) -> Union[Series, Movie]:
        self.extraction = True
        # Return if no URL is inputted
        if not self.url or self.url is None:
            raise ExtractorError('~TEMP~ No URL inputted')
        # Create a thread to execute the extraction function in the background
        extractor = Thread('__Extraction_Executor', target=self._extract)
        # Make the thread a child of current one
        self.set_child(child=extractor)
        extractor.start()
        # Return a partial information object
        while not hasattr(self, 'info'):
            sleep(0.1)
        return self.info

    def _print_filter_warning(self) -> None:
        if not self._using_filters:
            return
        vprint(
            '~TEMP~ Using filters, total count in progress bar will be inaccurate',
            module_name=self.__class__.__name__.lower(),
            error_level='warning')

    def _validate_extractor(self) -> bool:
        '''Check if extractor has all needed variables'''
        def check_variables(_vars: list):
            '''
            Raise an ExtractorError if a variable does not exist in
            class scope
            '''
            missing = (v for v in _vars if not hasattr(self, v))
            if missing:
                raise ExtractorError(
                    f'Invalid extractor! Missing variables: {missing}')

        if self.extractor_name == 'base':
            return
        # Check if extractor has all necessary variables
        check_variables('HOST', 'ARGUMENTS', 'DEFAULTS', 'FLAGS', '_extract')

        if AccountCapabilities in self.FLAGS:
            # Check if extractor has necessary login variables
            check_variables(('_login', 'is_logged_in'))
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
        return cookie_name in self.cjar

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
            username = input(lang['extractor']['base']['login_email_prompt'])
        if password is None:
            password = getpass(
                lang['extractor']['base']['login_password_prompt'])
        return self._login(username=username, password=password)

    def _subworkers_wait(self) -> None:
        'Do not call this function directly, use `self.wait_for_subworkers` instead'
        while [proc for proc in self._workers if proc.is_alive]:
            sleep(0.5)
        if type(self.info) is Series:
            self.info.extracted = True

    def wait_for_subworkers(self) -> None:
        '''
        Waits until all subworkers have finished,
        then if self.info obj type is Series, change it's finished attribute
        to True
        '''

        wait_proc = Thread('__Bus_Waiter',
                           daemon=True,
                           target=self._subworkers_wait)
        wait_proc.start()

    def check_episode_by_title(self, episode: Episode) -> bool:
        '''Check if episode passes the title match filters'''
        passes = False
        for _filter in self.filters:
            match = _filter.check(title=episode.title)
            if not match and _filter.absolutes:
                # Since absolute filters must always pass, return False
                return False
            # Modify variable only if 'passes' is False
            passes = match if not passes else passes
        return passes


def check_season(func) -> Season:
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


def check_episode(func) -> Episode:
    '''
    Input an Episode, if the Episode object passes number filter
    checks, returns the Episode run throught the decorated function,
    else returns the Episode back as-is
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
            # Using episode object, filters apply here
            if 'ALL' in self._seasons and 'ALL' in self._seasons['ALL']:
                # All episodes are set to be downloaded
                pass
            elif 'ALL' in self._seasons and episode.number in self._seasons[
                    'ALL']:
                # Episode number in ALL seasons list
                pass
            elif episode._parent is not None:
                # Since all possibilities to be included from the "ALL"
                # list have passed now, check if the episode is in it's
                # season's list
                if not episode._parent.number in self._seasons and \
                    episode.number in self._seasons[episode._parent.number]:
                    pass
                else:
                    # All possible cases have been considered
                    # Episode does not pass filter tests
                    return episode
            elif episode._parent is None:
                # Orphan Episode object, not applicable
                pass
        return func(self,
                    episode=episode,
                    episode_id=episode_id,
                    *args,
                    **kwargs)

    return wrapper


class ExtractorError(Exception):
    pass


class InvalidURLError(Exception):
    pass
