from json.decoder import JSONDecodeError
from xml.parsers.expat import ExpatError
import os

from tqdm.std import tqdm
from ..utils import vprint, load_language
from ..config import config, save_config
from ..paths import cookies_dir
from http.cookiejar import LWPCookieJar
from getpass import getpass
import cloudscraper
import json
import xmltodict

class BaseExtractor(object):
    '''
    ## Base extractor
    ### __init__
    - Sets the url to extract the info from
    - Loads user inputted options
    - Calls `load_at_init`, usually to add arguments and default config
    '''
    def __init__(self, url=str, options=dict):
        self.url = url
        self.extractor_name = self.return_class()[:-9]
        if self.extractor_name not in config['extractor']:
            config['extractor'][self.extractor_name] = self.DEFAULTS
            save_config()
        if options != dict:
            self.options = {**config['extractor'][self.extractor_name], **options}
        else:
            self.options = config['extractor'][self.extractor_name]
        self.lang = load_language()
        self.extractor_lang = self.lang[self.extractor_name.lower()]
        # Create a cookiejar for the extractor
        if not os.path.exists(cookies_dir + f'{self.extractor_name}.cjar'):
            with open(cookies_dir + f'{self.extractor_name}.cjar', 'w', encoding='utf-8') as c:
                c.write('#LWP-Cookies-2.0\n')
        # Open that cookiejar
        self.cjar = LWPCookieJar(cookies_dir + f'{self.extractor_name}.cjar')
        self.cjar.load(ignore_discard=True, ignore_expires=True)
        if hasattr(self, 'load_at_init'):
            self.load_at_init()
        # Login if there's an user-inputted username and password in the options
        if 'username' in options and 'password' in options:
            self.login(options['username'], options['password'])

    def load_info_template(self, media_type=str):
        if media_type == 'series':
            self.info = {'title': '',
                         'id': '',
                         'type': 'series',
                         'synopsis': '',
                         'year': 0,
                         'genres': [],
                         'actors': [],
                         'images': {'tall': [], 'wide': []},
                         'seasons': []}

        elif media_type == 'movie':
            self.info = {'title': '',
                         'id': '',
                         'type': 'movie',
                         'synopsis': '',
                         'year': 0,
                         'genres': [],
                         'images': {'tall': [], 'wide': []},
                         'streams': [],
                         'extra_audio': [],
                         'extra_subs': []}

    def load_new_info_template(self, template=str):
        if template == 'series':
            return {
                'title': '',
                'id': '',
                'type': 'series',
                'synopsis': '',
                'year': 0,
                'genres': [],
                'actors': [],
                'images': {'tall': [], 'wide': []},
                'seasons': [],
                'episodes': [],
                'extras': [],
                'indexes': []
            }
        elif template == 'movie':
            return {
                'title': '',
                'id': '',
                'type': 'movie',
                'synopsis': '',
                'year': 0,
                'genres': [],
                'actors': [],
                'images': {'tall': [], 'wide': []},
                'streams': [],
                'extra_audio': [],
                'extra_subs': []
            }
        elif template == 'artist':
            # TODO: Finish artist template
            return {
                'name': '',
                'id': '',
                'type': '',
                'images': [],
                'albums': [],
                'songs': [],
            }


    def create_progress_bar(self, *args, **kwargs):
        self.progress_bar = tqdm(*args, **kwargs)
        self.progress_bar.desc = f'[ex] {self.progress_bar.desc}'
        self.progress_bar.update(0)

    'Login / cookiejar functions'

    def login_form(self, user=str, password=str):
        if user == str:
            self.user = input(self.lang['extractor']['base']['login_email_prompt'])
        else:
            self.user = user
        if password == str:
            self.password = getpass(self.lang['extractor']['base']['login_password_prompt'])
        else:
            self.password = password
        return (self.user, self.password)

    def save_cookies_in_jar(self, cookies, filter_list=list):
        for cookie in cookies:
            if cookie.name not in filter_list:
                continue
            self.cjar.set_cookie(cookie)
        self.cjar.save(ignore_discard=True, ignore_expires=True)

    def cookie_exists(self, cookie_name=str):
        return bool([c for c in self.cjar if c.name == cookie_name])

    'HTTP request functions'

    @classmethod
    def request_webpage(self, url=str, method='get', **kwargs):

        '''
        Make a HTTP request using cloudscraper

        `url` url to make the request to

        `method` http request method

        `cloudscraper_kwargs` extra cloudscraper arguments, for more info check the `requests wiki`
        '''
        # Create a cloudscraper session
        # Spoof an Android Firefox browser to bypass Captcha v2
        self.browser = {
            'browser': 'firefox',
            'platform': 'android',
            'desktop': False,
        } 
        self.r = cloudscraper.create_scraper(browser=self.browser)
        try:
             self.response = getattr(self.r, method.lower())(url, **kwargs)
        except AttributeError:
                raise ExtractorCodingError('Invalid cloudscraper method "%s"' % method)
        return self.response

    @classmethod
    def request_json(self, url=str, method='get', **kwargs):
        '''
        Same as request_webpage, except it returns a tuple with the json as a dict and the response object
        '''
        self.response = self.request_webpage(url,
                                             method,
                                             **kwargs)
        try:
            return (json.loads(self.response.content.decode()),
                    self.response)
        except JSONDecodeError:
            return ({},
                    self.response)

    @classmethod
    def request_xml(self, url=str, method='get', **kwargs):
        '''
        Same as request_webpage, except it returns a tuple with the xml as a dict and the response object
        '''
        self.response = self.request_webpage(url,
                                             method,
                                             **kwargs)
        try:
            return (xmltodict.parse(self.response.content.decode()),
                    self.response)
        except ExpatError:
            return ({},
                    self.response)

    '''
    Media functions
    '''

    def create_season(self, **metadata):
        # TODO: replace all wiki links with actual links
        '''
        Create a new season and append the last opened one

        See the [polarity wiki](monkey_ass) for more info
        '''
        #if not 'type' in self.info or self.info['type'] != 'series':
        #    raise ExtractorCodingError('You can only use create_season with a series')
        if hasattr(self, 'season'):
            self.info['seasons'].append(self.season)
        self.season_base = {'title': '', 'id': '', 'synopsis': '', 'images': {'tall': [], 'wide': []}, 'season_number': 0, 'total_episodes': 0, 'episodes': []}
        self.season = {**self.season_base, **metadata}

    def append_season(self):
        '''
        Appends a created season without creating a new one
        '''
        if hasattr(self, 'season'):
            self.info['seasons'].append(self.season)
        else:
            raise ExtractorCodingError('Can\'t append something that doesn\'t exist! (create a season first)')
        del self.season


    def create_episode(self, **metadata):
        # TODO: replace all wiki links with actual links
        '''
        Create a new episode and append the last opened one

        See the [polarity wiki](monkey_ass) for more info
        '''
        if not 'type' in self.info or self.info['type'] != 'series':
            raise ExtractorCodingError('You can only use create_episode with a series')
        if not hasattr(self, 'season'):
            raise ExtractorCodingError('You need to create a season before creating an episode!')
        if hasattr(self, 'episode'):
            self.season['episodes'].append(self.episode)
        self.episode_base = {'title': '', 'id': '', 'type': '', 'synopsis': '', 'year': 0000, 'episode_number': 0, 'images': {'tall': [], 'wide': []}, 'streams': {}, 'extra_audio': [], 'extra_subs': []}
        self.episode = {**self.episode_base, **metadata}        

    def append_episode(self):
        '''
        Appends a created episode without creating a new one
        '''
        if hasattr(self, 'season'):
            if hasattr(self, 'episode'):
                self.season['episodes'].append(self.episode)
                del self.episode
            else:
                raise ExtractorCodingError('Can\'t append something that doesn\'t exist! (create an episode first)')
        else:
            raise ExtractorCodingError('Can\'t append to something that doesn\'t exist! (create a season first)')

    def create_content(self, create=str, **metadata):
        '''
        Valid types: season, episode, album, song, actor
        '''
        def create_season():
            self.info['seasons'].append(metadata)
            self.info['index_map'][metadata['id']] = len(self.info['seasons']) - 1
        def create_episode():
            self.info['episodes'].append(metadata)
            self.info['index_map'][metadata['id']] = len(self.info['episodes']) - 1

    def search(self, term):
        self.r = self.search_function()
        
class ExtractorError(Exception):
    pass

class LoginError(Exception):
    pass

class ContentUnavailableError(Exception):
    def __init__(self, msg='Content is unavailable in your region or has been taken out of the platform', *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

class ExtractorCodingError(Exception):
    'This is only used on BaseExtractor, do not use!'
    pass