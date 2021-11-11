import time
import re
from polarity.types.thread import Thread
from typing import Union
from urllib.parse import urlparse
from uuid import uuid4

from polarity.config import lang
from polarity.extractor.flags import *
from polarity.types import Episode, Season, Series, Stream
from polarity.types.progressbar import ProgressBar
from polarity.utils import (get_country_from_ip, is_content_id, order_dict,
                            parse_content_id, request_json, request_webpage,
                            vprint)

from .base import (BaseExtractor, ExtractorError, InvalidURLError,
                   Subextractor, check_episode, check_season)


class CrunchyrollExtractor(BaseExtractor):

    HOST = r'(?:http(?:s://|://|)|)(?:www\.|beta\.|)crunchyroll\.com'

    DEFAULTS = {
        'sub_language': ['all'],
        'dub_language': ['all'],
        'meta_language': 'en-US',
        'hardsub_language': 'none',
        'region_spoof': 'none',
        'use_alt_bearer': False,
        'alt_bearer_server': ''
    }

    ARGUMENTS = [
        {
            'args': ['--crunchyroll-subs'],
            'attrib': {
                'choices': [
                    'all', 'none', 'en-US', 'es-ES', 'es-LA', 'fr-FR', 'pt-BR',
                    'ar-ME', 'it-IT', 'de-DE', 'ru-RU', 'tr-TR'
                ],
                'help':
                lang['crunchyroll']['args']['subs'],
                'nargs':
                '+',
            },
            'variable': 'sub_language'
        },
        {
            'args': ['--crunchyroll-dubs'],
            'attrib': {
                'choices': [
                    'all', 'ja-JP', 'en-US', 'es-LA', 'fr-FR', 'pt-BR',
                    'it-IT', 'de-DE', 'ru-RU'
                ],
                'help':
                lang['crunchyroll']['args']['dubs'],
                'nargs':
                '+',
            },
            'variable': 'dub_language'
        },
        {
            'args': ['--crunchyroll-meta'],
            'attrib': {
                'choices': [
                    'en-US', 'es-LA', 'es-ES', 'fr-FR', 'pt-BR', 'ar-ME',
                    'it-IT', 'de-DE', 'ru-RU'
                ],
                'help':
                lang['crunchyroll']['args']['meta'],
            },
            'variable': 'meta_language'
        },
        {
            'args': ['--crunchyroll-hardsub'],
            'attrib': {
                'choices': [
                    'none', 'en-US', 'es-LA', 'es-ES', 'fr-FR', 'pt-BR',
                    'ar-ME', 'it-IT', 'de-DE', 'ru-RU'
                ],
                'help':
                lang['crunchyroll']['args']['hard'],
            },
            'variable': 'hardsub_language'
        },
        {
            'args': ['--crunchyroll-spoof-region'],
            'attrib': {
                'help': lang['crunchyroll']['args']['region']
            },
            'variable': 'region_spoof'
        },
        {
            'args': ['--crunchyroll-use-alt-bearer-server'],
            'attrib': {
                'action': 'store_true',
                'help': lang['crunchyroll']['args']['use_alt_bearer']
            },
            'variable': 'use_alt_bearer'
        },
        {
            'args': ['--crunchyroll-alt-bearer-server'],
            'attrib': {
                'help': lang['crunchyroll']['args']['alt_bearer_server']
            },
            'variable': 'alt_bearer_server'
        },
        {
            'args': ['--crunchyroll-email'],
            'attrib': {
                'help': lang['crunchyroll']['args']['email']
            },
            'variable': 'username'
        },
        {
            'args': ['--crunchyroll-password'],
            'attrib': {
                'help': lang['crunchyroll']['args']['pass'],
            },
            'variable': 'password'
        },
    ]

    account_info = {
        'basic': 'Basic bm9haWhkZXZtXzZpeWcwYThsMHE6',
        'bearer': None,
        'session_id': None,
        'policy': None,
        'signature': None,
        'key_pair_id': None,
        'bucket': None,
        'country': None,
        'madurity': None,
        'email': None,
    }

    API_URL = 'https://beta-api.crunchyroll.com/'

    FLAGS = {AccountCapabilities}

    LANG_CODES = {
        'en-US': {
            'meta': '',
            'lang': 'eng',
            'name': 'English (USA)',
            'dub': r'\(English Dub\)'
        },
        'es-ES': {
            'meta': 'es-es',
            'lang': 'spa',
            'name': 'Español (España)',
        },
        'es-LA': {
            'meta': 'es',
            'lang': 'spa',
            'name': 'Español (América Latina)',
            'dub': r'\(Spanish Dub\)'
        },
        'fr-FR': {
            'meta': 'fr',
            'lang': 'fre',
            'name': 'Français (France)',
            'dub': r'\(French Dub\)'
        },
        'pt-BR': {
            'meta': 'pt-br',
            'lang': 'por',
            'name': 'Português (Brasil)',
            'dub': r'\(Portuguese Dub\)'
        },
        'de-DE': {
            'meta': 'de',
            'lang': 'ger',
            'name': 'Deutsch',
            'dub': r'\(German Dub\)'
        },
        'it-IT': {
            'meta': 'it',
            'lang': 'ita',
            'name': 'Italiano',
            'dub': r'\(Italian Dub\)'
        },
        'ar-ME': {
            'meta': 'ar',
            'lang': 'ara',
            'name': 'العربية'
        },
        'ru-RU': {
            'meta': 'ru',
            'lang': 'rus',
            'name': 'Русский',
            'dub': r'\(Russian\)'
        },
        'tr-TR': {
            'meta': '',
            'lang': 'tur',
            'name': 'Türkçe'
        },
        'ja-JP': {
            'meta': '',
            'lang': 'jpn',
            'name': '日本語',
            'dub': r'[^()]'
        },
    }

    @classmethod
    def return_class(self):
        return __class__.__name__

    def __init__(self,
                 url: str,
                 filter_list: list = None,
                 options: dict = None) -> None:
        super().__init__(url, filter_list=filter_list, options=options)
        self.spoofed_region = False
        self.proxy = {}
        if self.options['region_spoof'] not in ('none', None):
            self.region_spoof(region_code=self.options['region_spoof'])
        self.get_bearer_token()
        self.get_cms_tokens()

    @staticmethod
    def check_for_error(contents=dict, error_msg=None) -> bool:
        if 'error' in contents and contents['error']:
            vprint(message=error_msg,
                   module_name='crunchyroll',
                   error_level='error')
            return True
        return False

    @staticmethod
    def identify_url(url: str) -> tuple:
        'Identifies an url type'
        is_legacy = False
        parsed_url = urlparse(url=url)
        url_host = parsed_url.netloc
        url_path = parsed_url.path
        # Check if URL host is valid
        if not re.match(r'(?:www\.|beta\.|)crunchyroll\.com', url_host):
            raise ExtractorError
        # Identify if the url is a legacy one
        is_legacy = url_host in ('www.crunchyroll.com',
                                 'crunchyroll.com') and not '/watch/' in url
        if is_legacy:
            regexes = {
                # Regex breakdown
                # 1. (/[a-z-]{2,5}/|/) -> matches a language i.e: /es-es/ or /ru/
                # 2. (?:\w+-(?P<id>\d+) -> matches a series short url, i.e series-272199
                # 3. [^/]+) -> matches the series part of the url, i.e new-game
                # 4. (?:/$|$) -> matches the end of the url
                # 5. [\w-] -> matches the episode part of the url i.e episode-3...
                # 6. media)- -> matches an episode short url
                # 7. (?P<id>[\d]{6,}) -> matches the id on both a long and a short url, i.e 811160
                Series:
                r'(?:/[a-z-]{2,5}/|/)(?:\w+-(?P<id>\d+)|[^/]+)(?:/$|$)',
                Episode:
                r'(?:/[a-z-]{2,5}/|/)(?:(?:[^/]+)/[\w-]+|media)-(?P<id>[\d]{6,})(?:/$|$)'
            }
        else:
            regexes = {
                # Regex breakdown
                # 1. (/[a-z-]{2,5}/|/) -> matches a language i.e: /es-es/ or /ru/
                # 2. (?P<id>[\w\d]+) -> matches the media id i.e: GVWU0P0K5
                # 3. (?:$|/[\w-]+) -> matches the end or the episode title i.e Se-cumpl...
                Series:
                r'(?:/[a-z-]{2,5}/|/)series/(?P<id>[\w\d]+)(?:$|/[\w-]+)(?:/$|$)',
                Episode:
                r'(?:/[a-z-]{2,5}/|/)watch/(?P<id>[\w\d]+)(?:$|/[\w-]+)(?:/$|$)',
            }
        for media_type, regex in regexes.items():
            match = re.match(regex, url_path)
            if match:
                return (media_type, match.group('id'))
        raise InvalidURLError

    # Session stuff
    def get_session_id(self, save_to_cjar=False) -> str:
        '''
        Returns a session identifier
        
        :param save_to_cjar: Save session identifier in cookie jar
        :return: Crunchyroll Session ID (string)
        '''
        req = request_json(
            url='https://api.crunchyroll.com/start_session.0.json',
            headers={'content-type': 'application/x-www-form-urlencoded'},
            params={
                'sess_id': '1',
                'device_type': 'com.crunchyroll.static',
                'device_id': '46n8i3b963vch0.95917811',
                'access_token': 'giKq5eY27ny3cqz'
            },
            proxies=self.proxy)
        self.account_info['session_id'] = req[0]['data']['session_id']
        if save_to_cjar:
            cookie = [c for c in req[1].cookies
                      if c.name == 'session_id'][0].value
            self.save_cookies_in_jar(cookie)
        return req[0]['data']['session_id']

    def login(self, user: None, password: None) -> dict:
        '''
        Login into the extractor's website
        
        :param user: Your Crunchyroll account's email
        :param password: Your Crunchyroll account's password
        '''
        session_id = self.get_session_id()
        login_req = request_json(
            url='https://api.crunchyroll.com/login.0.json',
            method='post',
            params={
                'session_id': session_id,
                'account': user,
                'password': password,
            },
            cookies=self.cjar)
        if not login_req[0]['error']:
            vprint(
                lang['extractor']['login_success'],
                module_name='crunchyroll',
            )
            self.save_cookies_in_jar(login_req[1].cookies,
                                     ['session_id', 'etp_rt'])
        else:
            vprint(lang['extractor']['login_failure'] %
                   (login_req[0]['message']),
                   module_name='crunchyroll',
                   error_level='error')
            return login_req[0]

    def is_logged_in(self) -> bool:
        '''
        Returns True if user is logged in
        
        This does not check if session is still valid
        
        :return: True if user is logged into Crunchyroll, else False
        '''
        return self.cookie_exists('etp_rt')

    def region_spoof(self, region_code=str):
        # TODO: remove
        key = 0
        while key == 0:
            uuid = uuid4().hex
            key_request = request_json(
                url='https://client.hola.org/client_cgi/background_init',
                method='post',
                params={'uuid': uuid},
                data={
                    'login': '1',
                    'ver': '1.164.641'
                })[0]

            key = key_request['key']

            proxy_request = request_json(
                url='https://client.hola.org/client_cgi/zgettunnels',
                params={
                    'country': region_code,
                    'limit': 3,
                    'ext_ver': '1.164.641',
                    'uuid': uuid,
                    'session_key': key,
                    'is_premium': 0
                })[0]
        self.spoofed_region = True
        self.spoofed_country = region_code.upper()
        self.proxy = {
            'http':
            f'http://user-uuid-{uuid}:{proxy_request["agent_key"]}@{list(proxy_request["ip_list"].values())[0]}:{proxy_request["port"]["direct"]}',
            'https':
            f'http://user-uuid-{uuid}:{proxy_request["agent_key"]}@{list(proxy_request["ip_list"].values())[0]}:{proxy_request["port"]["direct"]}'
        }
        return proxy_request

    def get_bearer_token(self, force_client_id=False) -> str:
        'Grabs Bearer Authorization token'
        # Set token method
        # etp_rt -> logged in
        # client_id -> not logged in

        vprint(
            self.extractor_lang['getting_bearer'],
            3,
            'crunchyroll',
        )
        method = 'etp_rt_cookie' if self.cookie_exists(
            'etp_rt') and not force_client_id else 'client_id'
        vprint(self.extractor_lang['using_method'] % method, 3, 'crunchyroll',
               'debug')
        token_req = request_json(url=self.API_URL + 'auth/v1/token',
                                 method='post',
                                 headers={
                                     'Authorization':
                                     self.account_info['basic'],
                                     'Content-Type':
                                     'application/x-www-form-urlencoded'
                                 },
                                 data={'grant_type': method},
                                 cookies=self.cjar,
                                 proxies=self.proxy)
        if not 'access_token' in token_req[0]:
            # TODO: better error message
            vprint('Failed to get Bearer', 1, 'crunchyroll', 'error')
            if method == 'etp_rt_cookie':
                vprint('Login expired, cleaning cookie jar', 1, 'crunchyroll',
                       'warning')
                self.cjar.clear()
                # Save the cookie jar
                self.cjar.save()
                return self.get_bearer_token(True)

        self.account_info['bearer'] = f'Bearer {token_req[0]["access_token"]}'
        return self.account_info['bearer']

    def get_cms_tokens(self) -> dict[str, str]:
        bucket_re = r'/(?P<country>\w{2})/(?P<madurity>M[1-3])'
        if self.account_info['bearer'] is None:
            self.get_bearer_token()
        vprint(self.extractor_lang['getting_cms'], 3, 'crunchyroll', 'debug')
        token_req = request_json(
            url=self.API_URL + 'index/v2',
            headers={'Authorization': self.account_info['bearer']},
            proxies=self.proxy)[0]
        if self.check_for_error(token_req):
            raise ExtractorError(self.extractor_lang['getting_cms_fail'])
        bucket_match = re.match(bucket_re, token_req['cms']['bucket'])
        self.account_info['policy'] = token_req['cms']['policy']
        self.account_info['signature'] = token_req['cms']['signature']
        self.account_info['key_pair_id'] = token_req['cms']['key_pair_id']
        # Content-availability variables
        self.account_info['country'] = bucket_match.group('country')
        self.account_info['madurity'] = bucket_match.group('madurity')
        self.account_info['bucket'] = token_req['cms']['bucket']
        self.CMS_API_URL = f'{self.API_URL}cms/v2{self.account_info["bucket"]}'
        if self.spoofed_region:
            if self.spoofed_country == bucket_match.group('country'):
                vprint(
                    self.extractor_lang['spoof_region_success'] %
                    self.spoofed_country, 2, 'crunchyroll')
            else:
                vprint(self.extractor_lang['spoof_region_fail'], 2,
                       'crunchyroll', 'error')
        return {
            'policy': self.account_info['policy'],
            'signature': self.account_info['signature'],
            'key_pair_id': self.account_info['key_pair_id']
        }

    def get_identifier(self, url: str) -> dict:
        series_id = season_id = episode_id = None
        url_type, url_id = self.identify_url(url=url)

    # Legacy Crunchyroll site support
    def get_etp_guid(self,
                     series_id=None,
                     collection_id=None,
                     episode_id=None):
        'Grab the etp_guid from a legacy id'
        info_api = 'https://api.crunchyroll.com/info.0.json'
        if series_id is not None:
            req = request_json(url=info_api,
                               params={
                                   'session_id': self.get_session_id(),
                                   'series_id': series_id
                               },
                               proxies=self.proxy)
            if not self.check_for_error(
                    req[0], 'Failed to fetch. Content unavailable'):
                return {'series': req[0]['data']['etp_guid']}
        if collection_id is not None:
            req = request_json(url=info_api,
                               params={
                                   'session_id': self.get_session_id(),
                                   'collection_id': collection_id
                               },
                               proxies=self.proxy)
            if not self.check_for_error(
                    req[0], 'Failed to fetch. Content unavailable'):
                return {
                    'series': req[0]['data']['series_etp_guid'],
                    'season': req[0]['data']['etp_guid'],
                }
        if episode_id is not None:
            req = request_json(
                url=info_api,
                params={
                    'session_id': self.get_session_id(),
                    'fields':
                    'media.etp_guid,media.collection_etp_guid,media.series_etp_guid',
                    'media_id': episode_id
                },
                proxies=self.proxy)
            if not self.check_for_error(
                    req[0], 'Failed to fetch. Content unavailable'):
                return {
                    'series': req[0]['data']['series_etp_guid'],
                    'season': req[0]['data']['collection_etp_guid'],
                    'episode': req[0]['data']['etp_guid'],
                }

    def get_series_info(self,
                        series_id: str,
                        return_raw_info=False) -> Union[Series, dict]:
        if self.account_info['bearer'] is None:
            self.get_cms_tokens()
        series_json = request_json(
            url=self.CMS_API_URL + '/series/' + series_id,
            headers={'Authorization': self.account_info['bearer']},
            params={
                'locale': self.options['meta_language'],
                'Signature': self.account_info['signature'],
                'Policy': self.account_info['policy'],
                'Key-Pair-Id': self.account_info['key_pair_id']
            })[0]

        if return_raw_info:
            return series_json

        vprint(
            lang['extractor']['get_media_info'] %
            (lang['types']['alt']['series'], series_json['title'], series_id),
            1, 'crunchyroll')

        self.info.set_metadata(
            title=series_json['title'],
            id=series_id,
            synopsis=series_json['description'],
            genres=series_json['keywords'],
            images=[
                series_json['images']['poster_tall'][0][-1:][0]['source'],
                series_json['images']['poster_wide'][0][-1:][0]['source']
            ],
            episode_count=series_json['episode_count'],
            season_count=series_json['season_count'],
            year=re.search(r'(\d+)', series_json['season_tags'][0]).group(0)
            if series_json['season_tags'] else 1970)

        return self.info

    def get_seasons(self, series_id: str) -> list[Season]:

        season_list = []
        vprint(lang['extractor']['get_all_seasons'], 2, 'crunchyroll')
        api_season_list = request_json(self.CMS_API_URL + '/seasons',
                                       params={
                                           'series_id':
                                           series_id,
                                           'locale':
                                           self.options['meta_language'],
                                           'Signature':
                                           self.account_info['signature'],
                                           'Policy':
                                           self.account_info['policy'],
                                           'Key-Pair-Id':
                                           self.account_info['key_pair_id']
                                       })[0]

        for season in api_season_list['items']:
            # Get dub language from the title using regex
            for _lang, values in self.LANG_CODES.items():
                if 'dub' not in values:
                    # Skip languages without dubs
                    continue
                elif re.search(values['dub'], season['title']):
                    language = _lang
                    break

            _season = Season(title=season['title'],
                             id=season['id'],
                             number=season['season_number'])

            # Add dub language attribute
            _season._crunchyroll_dub = language

            season_list.append(_season)
        return season_list

    @check_season
    def get_season_info(self,
                        season: Season = None,
                        season_id: str = None,
                        return_raw_info=False) -> Union[Season, dict]:
        '''
        Returns a full Season object from specified season identifier or from
        a partial Season object
        
        Only one season parameter is required
        :param season: Partial Season object
        :param season_id: Season identifier
        :param return_raw_info: Returns the JSON directly, without parsing 
        :return: Full Season object, or dict if return_raw_info
        '''
        _season = season if season is not None else Season()
        _season_id = season.id if season is not None else season_id
        season_json = request_json(
            self.CMS_API_URL + '/seasons/' + _season_id,
            headers={'Authorization': self.account_info['bearer']},
            params={
                'locale': self.options['meta_language'],
                'Signature': self.account_info['signature'],
                'Policy': self.account_info['policy'],
                'Key-Pair-Id': self.account_info['key_pair_id']
            })[0]
        vprint(
            lang['extractor']['get_media_info'] %
            (lang['types']['alt']['season'], season_json['title'], _season_id),
            level=2,
            module_name='crunchyroll')

        metadata = {
            'title': season_json['title'],
            'id': _season_id,
            'number': season_json['season_number'],
        }

        _season.set_metadata(**metadata)

        return _season

    def get_episodes_from_season(
            self,
            season_id: str = None,
            season: Season = None,
            return_raw_info=False) -> Union[list[Episode], dict]:
        '''
        Return a list with partial Episode objects from the episodes of the
        season
        
        Only one season parameter is required
        :param season_id: Season's identifier
        :param season: Season object
        :param return_raw_info: Returns the JSON directly without parsing
        :return: Returns a Full Episode object (with streams) if
        return_raw_info is False, else returns unparsed JSON dict
        '''
        identifier = season_id if season_id is not None else season.id
        if identifier is None:
            raise ExtractorError('No indentifier inputted')
        unparsed_list = request_json(self.CMS_API_URL + '/episodes',
                                     params={
                                         'season_id':
                                         identifier,
                                         'locale':
                                         self.options['meta_language'],
                                         'Signature':
                                         self.account_info['signature'],
                                         'Policy':
                                         self.account_info['policy'],
                                         'Key-Pair-Id':
                                         self.account_info['key_pair_id']
                                     })[0]
        if return_raw_info:
            return unparsed_list

        if hasattr(self, 'season') or season is not None:
            # Add episode count attribute to season
            _season = season if season is not None else self.season
            _season.episode_count = len(unparsed_list['items'])

        for episode in unparsed_list['items']:
            parsed_episode = self._parse_episode_info(episode)

            yield parsed_episode

    @check_episode
    def get_episode_info(self,
                         episode: Episode,
                         episode_id: str,
                         return_raw_info=False,
                         get_streams=True) -> Union[Episode, dict]:
        '''
        Get information from an episode using it's identifier or a partial
        Episode object
        
        Either an Episode object with an id or the raw id is required
        :param episode: Partial Episode object
        :param episode_id: Episode identifier
        :param return_raw_info: Returns the JSON directly, without parsing
        :param get_streams: Run the _get_streams function automatically
        :return: Full Episode object if not return_raw_info, else a dict
        '''

        _episode_id = episode.id if episode is not None else episode_id

        episode_info = request_json(
            self.CMS_API_URL + '/episodes/' + _episode_id,
            headers={'Authorization': self.account_info['bearer']},
            params={
                'locale': self.options['meta_language'],
                'Signature': self.account_info['signature'],
                'Policy': self.account_info['policy'],
                'Key-Pair-Id': self.account_info['key_pair_id']
            })[0]
        if return_raw_info:
            return episode_info

        episode = self._parse_episode_info(episode_info,
                                           get_streams=get_streams)
        if not self.check_episode_by_title(episode=episode):
            if not hasattr(episode, 'skip_download'):
                # If episode has not a skip reason already, add one
                episode.skip_download = '~TEMP~ Did not pass name filter check'
        return episode

    def _parse_episode_info(self,
                            episode_info: dict,
                            get_streams=True) -> Episode:
        'Parses info from an episode\'s JSON'
        vprint(
            lang['extractor']['get_media_info'] %
            (lang['types']['alt']['episode'], episode_info['title'],
             episode_info['id']), 3, 'crunchyroll')
        episode = Episode(title=episode_info['title'],
                          id=episode_info['id'],
                          synopsis=episode_info['description'],
                          number=episode_info['episode_number'])
        # If content does not have an episode number, assume it's a movie
        if episode.number is None:
            episode.number = 0
            episode.movie = True
            if episode_info['season_tags']:
                episode.year = re.search(
                    r'(\d+)', episode_info['season_tags'][0]).group(0)

        episode._partial = False

        if get_streams and 'playback' in episode_info:
            episode.streams = self._get_streams(episode_info['playback'])
        elif get_streams and 'playback' not in episode_info:
            episode.skip_download = 'unavailable'  # TODO: better string

        return episode

    def _get_streams(
        self,
        playback_url: str = None,
        episode: Episode = None,
        episode_id: str = None,
    ) -> list[Stream]:
        '''
        Get streams from an inputted episode identifier
        
        Also allows getting streams directly using the playback url
        
        Only one parameter is required
        :param playback_url: Direct playback url
        :param episode: Episode object, requires having an identifier set
        :param episode_id: Episode identifier
        :return: list with Stream objects if successful, else empty list
        '''

        streams = []

        # Set the streams page URL
        if playback_url is not None:
            playback = playback_url
        elif episode is not None or episode_id is not None:
            _id = episode.id if episode is not None else episode_id
            # Get raw episode info JSON
            inf = self.get_episode_info(episode_id=_id, return_raw_info=True)
            if 'playback' not in inf:
                return streams
            playback = inf['playback']

        streams_json = request_json(url=playback)[0]
        # Case 1: Disabled hardsubs or desired hardsub language does not exist
        if self.options['hardsub_language'] == 'none' or self.options[
                'hardsub_language'] not in streams_json['streams'][
                    'adaptive_hls']:
            is_preferred = 'ja-JP'
        # Case 2: Desired hardsub language exists
        elif self.options['hardsub_language'] in streams_json['streams'][
                'adaptive_hls']:
            is_preferred = streams_json['streams']['adaptive_hls'][
                self.options['hardsub_language']]['hardsub_locale']

        for stream in streams_json['streams']['adaptive_hls'].values():
            if stream['hardsub_locale'] == '':
                stream['hardsub_locale'] = 'ja-JP'
            _stream = Stream(
                url=stream['url'],
                id='video',
                preferred=stream['hardsub_locale'] == is_preferred,
                name={
                    'video': self.LANG_CODES[stream['hardsub_locale']]['name'],
                    'audio':
                    self.LANG_CODES[streams_json['audio_locale']]['name'],
                },
                language={
                    'video': self.LANG_CODES[stream['hardsub_locale']]['lang'],
                    'audio':
                    self.LANG_CODES[streams_json['audio_locale']]['lang']
                })
            streams.append(_stream)

        # Create subtitle stream list
        subtitles = [
            Stream(
                url=s['url'],
                name=self.LANG_CODES[s['locale']]['name'],
                language=self.LANG_CODES[s['locale']]['lang'],
                preferred='all' in self.options['sub_language']
                or s in self.options['sub_language'],
            ) for s in order_dict(to_order=streams_json['subtitles'],
                                  order_definer=self.LANG_CODES).values()
        ]
        for subtitle in subtitles:
            subtitle.extra_sub = True
            streams.append(subtitle)

        # TODO : remove
        if hasattr(self, 'progress_bar'):
            self.progress_bar.update(1)

        return streams

    # Threading

    def _threaded_season(self, season: Season) -> None:
        if not any(s in ('all', season._crunchyroll_dub)
                   for s in self.options['dub_language']):
            return
        self.get_season_info(season=season)
        self.info.link_season(season=season)
        for episode in self.get_episodes_from_season(season=season):
            season.link_episode(episode=episode)

    def search(self, term=str):
        # TODO: search
        search_results = request_json(url=self.API_URL + 'content/v1/search',
                                      headers={
                                          'Authorization':
                                          self.account_info['bearer'],
                                      },
                                      params={
                                          'q': term,
                                          'n': 30,
                                          'locale':
                                          self.options['meta_language']
                                      })
        print(search_results)

    def _true_extract(self, ):
        if not is_content_id(self.url):
            url_tuple = self.identify_url(url=self.url)
            url_type, media_id = url_tuple
        else:
            parsed = parse_content_id(id=self.url)
            url_type = parsed.content_type
            media_id = parsed.id

        # if self.options['region_spoof'] not in ('none', None):
        #     self.region_spoof(region_code=self.options['region_spoof'])

        # self.get_cms_tokens()

        if url_type == Series:
            # Posible series cases:
            # Case 1: Legacy URL -> .../series-name - ID-less
            # Case 2: Legacy URL -> .../series-000000 - has ID
            # Case 3: New URL -> .../series/AlphaNumID/... - has ID

            if media_id is None:
                # Case 1
                # Request the series' webpage and get id from page's source
                series_page = request_webpage(self.url, cookies=self.cjar)

                # Raise an Invalid URL error if page doesn't exist
                if series_page.status_code == 404:
                    raise InvalidURLError

                series_content = series_page.content.decode()
                series_id = re.search(
                    pattern=r'ass="show-actions" group_id="(?P<id>\d{5,})"',
                    string=series_content).group(1)

                # Get series GUID from the ID
                series_guid = self.get_etp_guid(series_id=series_id)['series']
            else:
                # Case 2
                if media_id.isdigit():
                    # Get series GUID from the ID
                    series_guid = self.get_etp_guid(
                        series_id=media_id)['series']
                else:
                    series_guid = media_id

            self.get_series_info(series_id=series_guid)

            self.progress_bar = ProgressBar(desc=self.info.title,
                                            total=self.info.episode_count,
                                            leave=False,
                                            head='extraction')

            season_threads = []

            for season in self.get_seasons(series_id=series_guid):
                _thread = Thread('__Subextractor',
                                 daemon=True,
                                 target=self._threaded_season,
                                 kwargs={'season': season})
                _thread.start()
                season_threads.append(_thread)

            while [t for t in season_threads if t.is_alive()]:
                time.sleep(0.1)

            self.progress_bar.close()

        elif url_type == Episode:
            if media_id.isdigit():
                episode_guid = self.get_etp_guid(
                    episode_id=media_id)['episode']
            else:
                episode_guid = media_id

            # Get raw episode info
            episode_info = self.get_episode_info(episode_id=episode_guid,
                                                 return_raw_info=True)

            # Get series and season's guid using regex
            series_guid = re.search(
                r'/(\w+)$',
                episode_info['__links__']['episode/series']['href']).group(1)
            season_guid = re.search(
                r'/(\w+)$',
                episode_info['__links__']['episode/season']['href']).group(1)

            # Get series and season info
            self.get_series_info(series_id=series_guid)
            self.season = self.get_season_info(season_id=season_guid)
            self.info.link_season(season=self.season)
            # Parse the raw episode info
            episode = self._parse_episode_info(episode_info=episode_info)
            # Link the episode with the season
            self.season.link_episode(episode=episode)
        # Since extraction has finished, remove the partial flag
        self.info._partial = False

    def _extract(self) -> Series:
        self.info = Series()
        # Create a thread to execute the extraction function in the
        # background
        extractor = Thread('__Extraction_Executor', target=self._true_extract)
        # Make the thread a child of current one
        self.set_child(child=extractor)
        extractor.start()
        # Return a partial (Series) information object
        return self.info
