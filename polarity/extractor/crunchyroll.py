
from .base import BaseExtractor, ExtractorError, InvalidURLError

from polarity.config import lang
from polarity.utils import get_country_from_ip, is_download_id, order_dict, parse_download_id, vprint, request_json, request_webpage

import re

from urllib.parse import urlparse
from uuid import uuid4

class CrunchyrollExtractor(BaseExtractor):
    
    HOST = r'(?:http(?:s://|://|)|)(?:www\.|beta\.|)crunchyroll\.com'
    
    LOGIN_REQUIRED = False
    
    DEFAULTS = {
        'sub_language': ['all'],
        'dub_language': ['all'],
        'meta_language': 'en-US',
        'hardsub_language': 'none',
        'premium_spoof': False,
        'region_spoof': 'none'
        }
    
    ARGUMENTS = [
        {
            'args': ['--crunchyroll-subs'],
            'attrib': {
                'choices': ['all', 'none', 'en-US', 'es-ES', 'es-LA', 'fr-FR', 'pt-BR', 'ar-ME', 'it-IT', 'de-DE', 'ru-RU'],
                'help': lang['crunchyroll']['args']['subs'],
                'nargs': '+',
            },
            'variable': 'sub_language'
        },
        {
            'args': ['--crunchyroll-dubs'],
            'attrib': {
                'choices': ['all', 'jp-JP', 'en-US', 'es-LA', 'fr-FR', 'pt-BR', 'it-IT', 'de-DE', 'ru-RU'],
                'help': lang['crunchyroll']['args']['dubs'],
                'nargs': '+',
            },
            'variable': 'dub_language'
        },
        {
            'args': ['--crunchyroll-meta'],
            'attrib': {
                'choices': ['en-US', 'es-LA', 'es-ES', 'fr-FR', 'pt-BR', 'ar-ME', 'it-IT', 'de-DE', 'ru-RU'],
                'help': lang['crunchyroll']['args']['meta'],
            },
            'variable': 'meta_language'
        },
        {
            'args': ['--crunchyroll-hardsub'],
            'attrib': {
                'choices': ['none', 'en-US', 'es-LA', 'es-ES', 'fr-FR', 'pt-BR', 'ar-ME', 'it-IT', 'de-DE', 'ru-RU'],
                'help': lang['crunchyroll']['args']['hard'],
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
            'args': ['--crunchyroll-spoof-premium'],
            'attrib': {
                'action': 'store_true',
                'help': lang['crunchyroll']['args']['premium']
                },
            'variable': 'premium_spoof'
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
    
    LANG_CODES = {
        'en-US': {'meta': '', 'lang': 'eng', 'name': 'English (USA)'},
        'es-ES': {'meta': 'es-es', 'lang': 'spa', 'name': 'Español (España)'},
        'es-LA': {'meta': 'es', 'lang': 'spa', 'name': 'Español (América Latina)'},
        'fr-FR': {'meta': 'fr', 'lang': 'fre', 'name': 'Français (France)'},
        'pt-BR': {'meta': 'pt-br', 'lang': 'por', 'name': 'Português (Brasil)'},
        'de-DE': {'meta': 'de', 'lang': 'ger', 'name': 'Deutsch'},
        'it-IT': {'meta': 'it', 'lang': 'ita', 'name': 'Italiano'},
        'ar-ME': {'meta': 'ar', 'lang': 'ara', 'name': 'العربية'},
        'ru-RU': {'meta': 'ru', 'lang': 'rus', 'name': 'Русский'},
        'ja-JP': {'meta': '', 'lang': 'jpn', 'name': '日本語'},
    }

    @classmethod
    # def return_class(self): return __class__.__name__.lower()
    def return_class(self): return __class__.__name__

    def load_at_init(self):
        self.spoofed_region = False
        self.proxy = {}
        if self.options['region_spoof'] not in ('none', None):
            self.region_spoof(region_code=self.options['region_spoof'])
        self.get_bearer_token(spoof_premium=self.options['premium_spoof'])
        self.get_cms_tokens()
    
    @staticmethod
    def check_for_error(contents=dict, error_msg=None) -> bool:
        if 'error' in contents and contents['error']:
            vprint(message=error_msg, module_name='cr:unified', error_level='error')
            return True
        return False
    
    @staticmethod
    def identify_url(url=str):
        'Identifies an url type'
        is_legacy = False
        parsed_url = urlparse(url=url)
        url_host = parsed_url.netloc
        url_path = parsed_url.path
        # Check if URL host is valid
        if not re.match(r'(?:www\.|beta\.|)crunchyroll\.com', url_host):
            raise ExtractorError
        # Identify if the url is a legacy one
        if url_host in ('www.crunchyroll.com', 'crunchyroll.com'):
            is_legacy = True
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
                'series': r'(?:/[a-z-]{2,5}/|/)(?:\w+-(?P<id>\d+)|[^/]+)(?:/$|$)',
                'episode': r'(?:/[a-z-]{2,5}/|/)(?:(?:[^/]+)/[\w-]+|media)-(?P<id>[\d]{6,})(?:/$|$)'
            }
        else:
            regexes = {
                # Regex breakdown
                # 1. (/[a-z-]{2,5}/|/) -> matches a language i.e: /es-es/ or /ru/
                # 2. (?P<id>[\w\d]+) -> matches the media id i.e: GVWU0P0K5
                # 3. (?:$|/[\w-]+) -> matches the end or the episode title i.e Se-cumpl...
                'series': r'(?:/[a-z-]{2,5}/|/)series/(?P<id>[\w\d]+)(?:$|/[\w-]+)(?:/$|$)',
                'episode': r'(?:/[a-z-]{2,5}/|/)watch/(?P<id>[\w\d]+)(?:$|/[\w-]+)(?:/$|$)',
            }
        for media_type, regex in regexes.items():
            match = re.match(regex, url_path)
            if match:
                return (media_type, match.group('id'))
        raise InvalidURLError
            
            
    # Session stuff   
    def get_session_id(self, save_to_cjar=False) -> str:
        req = request_json(
            url='https://api.crunchyroll.com/start_session.0.json',
            headers={'content-type': 'application/x-www-form-urlencoded'},
            params={
                'sess_id': '1',
                'device_type': 'com.crunchyroll.static',
                'device_id': '46n8i3b963vch0.95917811',
                'access_token': 'giKq5eY27ny3cqz'
            },
            proxies=self.proxy
        )
        self.account_info['session_id'] = req[0]['data']['session_id']
        if save_to_cjar:
            cookie = [c for c in req[1].cookies if c.name == 'session_id'][0].value
            self.save_session_id(cookie=cookie)
        return req[0]['data']['session_id']
    
    def save_session_id(self, cookie): self.save_cookies_in_jar(cookie)
    
    def login(self, user=None, password=None):
        session_id = self.get_session_id()
        login_req = request_json(
            url='https://api.crunchyroll.com/login.0.json',
            method='post',
            params={
                'session_id': session_id,
                'account': user,
                'password': password,
            },
            cookies=self.cjar
        )
        if not login_req[0]['error']:
            vprint(lang['extractor']['login_success'])
            self.save_cookies_in_jar(login_req[1].cookies, ['session_id', 'etp_rt'])
         
    def is_logged_in(self): return self.cookie_exists('etp_rt')
    
    def region_spoof(self, region_code=str):
        key = 0
        while key == 0:
            uuid = uuid4().hex
            key_request = request_json(
                url='https://client.hola.org/client_cgi/background_init',
                method='post',
                params={
                    'uuid': uuid
                },
                data={
                    'login': '1',
                    'ver': '1.164.641'
                }
            )[0]
            
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
                }
            )[0]
        self.spoofed_region = True
        self.spoofed_country = region_code.upper()
        self.proxy = {
            'http': f'http://user-uuid-{uuid}:{proxy_request["agent_key"]}@{list(proxy_request["ip_list"].values())[0]}:{proxy_request["port"]["direct"]}',
            'https': f'http://user-uuid-{uuid}:{proxy_request["agent_key"]}@{list(proxy_request["ip_list"].values())[0]}:{proxy_request["port"]["direct"]}'
            }
        return proxy_request
    
    def get_bearer_token(self, spoof_premium=True) -> str:
        'Grabs Bearer Authorization token'
        # Set token method
        # etp_rt -> logged in
        # client_id -> not logged in
        if not spoof_premium:
            vprint(self.extractor_lang['getting_bearer'], 2, 'crunchyroll',)
            method = 'etp_rt_cookie' if self.cookie_exists('etp_rt') else 'client_id'
            vprint(self.extractor_lang['using_method'] % method, 3, 'crunchyroll', 'debug')
            token_req = request_json(
                url=self.API_URL + 'auth/v1/token',
                method='post',
                headers={
                    'Authorization': self.account_info['basic'],
                    'Content-Type': 'application/x-www-form-urlencoded'
                    },
                data={'grant_type': method},
                cookies=self.cjar,
                proxies=self.proxy
            )
            if not 'access_token' in token_req[0]:
                # TODO: better error message
                vprint('bearer error', 1, 'cr:unified', 'error')
        elif spoof_premium:
            bearer_api = 'http://twili.duckdns.org:32934/crunchyroll/bearer/'
            if self.spoofed_region:
                bearer_api += self.spoofed_country.lower()
            else:
                bearer_api += get_country_from_ip()
            token_req = request_json(url=bearer_api)
            if not 'access_token' in token_req[0]:
                # Return a normal bearer if premium bearer server fails
                vprint(self.extractor_lang['spoof_premium_fail'], 2, 'crunchyroll', 'error')
                return self.get_bearer_token(spoof_premium=False)
            vprint(self.extractor_lang['spoof_premium_success'], 2, 'crunchyroll')
        self.account_info['bearer'] = f'Bearer {token_req[0]["access_token"]}'
        return self.account_info['bearer']
    
    def get_cms_tokens(self, ):
        bucket_re = r'/(?P<country>\w{2})/(?P<madurity>M[1-3])'
        if self.account_info['bearer'] is None:
            self.get_bearer_token()
        vprint(self.extractor_lang['getting_cms'], 2, 'crunchyroll')
        token_req = request_json(
            url=self.API_URL + 'index/v2',
            headers={'Authorization': self.account_info['bearer']},
            proxies=self.proxy
        )[0]
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
                vprint(self.extractor_lang['spoof_region_success'] % self.spoofed_country, 2, 'crunchyroll')
            else:
                vprint(self.extractor_lang['spoof_region_fail'], 2, 'crunchyroll', 'error')
        return {
            'policy': self.account_info['policy'],
            'signature': self.account_info['signature'],
            'key_pair_id': self.account_info['key_pair_id']
        }
        
    # Legacy Crunchyroll site support
    def get_etp_guid(self, series_id=None, collection_id=None, episode_id=None):
        'Grab the etp_guid from a legacy id'
        # TODO: make this cleaner
        info_api = 'https://api.crunchyroll.com/info.0.json'
        if series_id is not None:
            req = request_json(
                url=info_api,
                params={
                    'session_id': self.get_session_id(),
                    'series_id': series_id
                },
                proxies=self.proxy
            )
            if not self.check_for_error(req[0], 'Failed to fetch. Content unavailable'):
                return {
                    'series': req[0]['data']['etp_guid']
                    }
        if collection_id is not None:
            req = request_json(
                url=info_api,
                params={
                    'session_id': self.get_session_id(),
                    'collection_id': series_id
                },
                proxies=self.proxy
            )
            if not self.check_for_error(req[0], 'Failed to fetch. Content unavailable'):
                return {
                    'series': req[0]['data']['series_etp_guid'],
                    'season': req[0]['data']['etp_guid'],
                    }
        if episode_id is not None:
            req = request_json(
                url=info_api,
                params={
                    'session_id': self.get_session_id(),
                    'fields': 'media.etp_guid,media.collection_etp_guid,media.series_etp_guid',
                    'media_id': episode_id
                },
                proxies=self.proxy
            )
            if not self.check_for_error(req[0], 'Failed to fetch. Content unavailable'):
                return {
                    'series': req[0]['data']['series_etp_guid'],
                    'season': req[0]['data']['collection_etp_guid'],
                    'episode': req[0]['data']['etp_guid'],
                    }
        
    def get_series_info(self, series_id=str):
        if self.account_info['bearer'] is None:
            self.get_cms_tokens()
        self.set_main_info('series')
        series_json = request_json(
            url=self.CMS_API_URL + '/series/' + series_id,
            headers={'Authorization': self.account_info['bearer']},
            params={
                'locale': self.options['meta_language'],
                'Signature': self.account_info['signature'],
                'Policy': self.account_info['policy'],
                'Key-Pair-Id': self.account_info['key_pair_id']}
        )[0]
        
        vprint(lang['extractor']['get_media_info'] % (
            lang['types']['alt']['series'],
            series_json['title'],
            series_id
        ), 1, 'crunchyroll')
        
        self.info.title = series_json['title']
        self.info.id = series_id
        self.info.synopsis = series_json['description']
        self.info.genres = series_json['keywords']
        self.info.images.append(series_json['images']['poster_tall'][0][-1:][0]['source'])
        self.info.images.append(series_json['images']['poster_wide'][0][-1:][0]['source'])
        self.info.total_episodes = series_json['episode_count']
        self.info.total_seasons = series_json['season_count']
        if series_json['season_tags']:
            # Try to get release year from a season tag, i.e "Winter-2019"
            # Might be inaccurate with older series like Naruto
            self.info.year = re.search(r'(\d+)', series_json['season_tags'][0]).group(0)
            
        return self.info
    
    def get_seasons(self, series_guid=str):
        season_list = []
        api_season_list = request_json(
            self.CMS_API_URL + '/seasons',
            params={
                'series_id': series_guid,
                'locale': self.options['meta_language'],
                'Signature': self.account_info['signature'],
                'Policy': self.account_info['policy'],
                'Key-Pair-Id': self.account_info['key_pair_id']
                }
        )[0]
        for season in api_season_list['items']:
            season_list.append({
                'name': season['title'],
                'id': season['id'],
                'number': season['season_number']
            })
        return season_list
    
    def get_season_info(self, season_id=str):
        self.create_season(self.extraction is False)
        season_json = request_json(
            self.CMS_API_URL + '/seasons/' + season_id,
            headers={'Authorization': self.account_info['bearer']},
            params={
                'locale': self.options['meta_language'],
                'Signature': self.account_info['signature'],
                'Policy': self.account_info['policy'],
                'Key-Pair-Id': self.account_info['key_pair_id']
                }
            )[0]
        self.season.title = season_json['title']
        self.season.id = season_id
        self.season.number = season_json['season_number']
        return self.season

    def get_episodes_from_season(self, season_id=str):
        episodes_list = request_json(
            self.CMS_API_URL + '/episodes',
            params={
                'season_id': season_id,
                'locale': self.options['meta_language'],
                'Signature': self.account_info['signature'],
                'Policy': self.account_info['policy'],
                'Key-Pair-Id': self.account_info['key_pair_id']
                }            
        )[0]
        if hasattr(self, 'season'):
            self.season.total_episodes = len(episodes_list['items'])
            self.season.available_episodes = len([i for i in episodes_list['items'] if 'playback' in i])
        return [self._parse_episode_info(i) for i in episodes_list['items']]
    
    def get_episode_info(self, episode_id=str, return_raw_info=False):
        episode_info = request_json(
            self.CMS_API_URL + '/episodes/' + episode_id,
            headers={'Authorization': self.account_info['bearer']},
            params={
                'locale': self.options['meta_language'],
                'Signature': self.account_info['signature'],
                'Policy': self.account_info['policy'],
                'Key-Pair-Id': self.account_info['key_pair_id']
                }
            )[0]
        if not return_raw_info:
            return self._parse_episode_info(episode_info)
        return episode_info
        
    def _parse_episode_info(self, episode_info=dict):
        'Parses info from an episode\'s JSON'
        self.create_episode(self.extraction is False)
        
        vprint(lang['extractor']['get_media_info'] % (
            lang['types']['alt']['episode'],
            episode_info['title'],
            episode_info['id']
        ), 3, 'crunchyroll')
        self.episode.title = episode_info['title']
        self.episode.id = episode_info['id']
        self.episode.synopsis = episode_info['description']
        self.episode.number = episode_info['episode_number']
        if self.episode.number is None:
            self.episode.number = 0
            self.episode.movie = True
            if episode_info['season_tags']:
                self.episode.year = re.search(r'(\d+)', episode_info['season_tags'][0]).group(0)
        if 'playback' in episode_info:
            streams_json = request_json(
                url=episode_info['playback']
            )[0]
            # Case 1: Disabled hardsubs or desired hardsub language does not exist
            if self.options['hardsub_language'] == 'none' or self.options['hardsub_language'] not in streams_json['streams']['adaptive_hls']:
                preferred = 'ja-JP'
            # Case 2: Desired hardsub language exists
            elif self.options['hardsub_language'] in streams_json['streams']['adaptive_hls']:
                preferred = streams_json['streams']['adaptive_hls'][self.options['hardsub_language']]['hardsub_locale']
            
            for stream in streams_json['streams']['adaptive_hls'].values():
                if stream['hardsub_locale'] == '':
                    stream['hardsub_locale'] = 'ja-JP'
                self.create_stream(independent=False)
                self.stream.url = stream['url']
                self.stream.name = self.LANG_CODES[stream['hardsub_locale']]['name']
                self.stream.language = self.LANG_CODES[stream['hardsub_locale']]['lang']
                self.stream.audio_language = self.LANG_CODES[streams_json['audio_locale']]['lang']
                self.stream.audio_name = self.LANG_CODES[streams_json['audio_locale']]['name']
                if stream['hardsub_locale'] == preferred:
                    self.stream.preferred = True
                    
            # Get subtitles
            [
                self.create_stream(
                    url=s['url'],
                    sub_name=self.LANG_CODES[s['locale']]['name'],
                    sub_language=self.LANG_CODES[s['locale']]['lang'],
                    preferred='all' in self.options['sub_language'] or s in self.options['sub_language'],
                    extra_sub=True)
                for s in
                order_dict(
                    to_order=streams_json['subtitles'],
                    order_definer=self.LANG_CODES
                    ).values()
                ]
        else:
            self.episode.skip_download = lang['crunchyroll']['skip_download_reason']
        
        if hasattr(self, 'progress_bar'):
            self.progress_bar.update(1)
        
        return self.episode
    
    def search(self, term=str):
        search_results = request_json(
            url=self.API_URL + 'content/v1/search',
            headers={
                'Authorization': self.account_info['bearer'],
            },
            params={
                'q': term,
                'n': 30,
                'locale': self.options['meta_language']
            }
        )
        print(search_results)
    
    def extract(self, ):
        self.extraction = True
        if not is_download_id(self.url):
            url_tuple = self.identify_url(url=self.url)
            url_type, media_id = url_tuple
        else:
            parsed = parse_download_id(id=self.url)
            url_type = parsed.content_type
            media_id = parsed.id
        
        
        # if self.options['region_spoof'] not in ('none', None):
        #     self.region_spoof(region_code=self.options['region_spoof'])
        
        # self.get_cms_tokens()
        
        if url_type == 'series':
            # Posible series cases:
            # Case 1: Legacy URL -> .../series-name - ID-less
            # Case 2: Legacy URL -> .../series-000000 - has ID
            # Case 3: New URL -> .../series/AlphaNumID/... - has ID
            
            if media_id is None:
                # Case 1
                # Request the series' webpage and get id from page's source
                series_page = request_webpage(
                    self.url,
                    cookies=self.cjar
                )
                
                # Raise an Invalid URL error if page doesn't exist
                if series_page.status_code == 404:
                    raise InvalidURLError
                
                series_content = series_page.content.decode()
                series_id = re.search(
                    pattern=r'ass="show-actions" group_id="(?P<id>\d{5,})"',
                    string=series_content
                    ).group(1)
                
                # Get series GUID from the ID
                series_guid = self.get_etp_guid(series_id=series_id)['series']
            else:  
                # Case 2
                if media_id.isdigit():
                    # Get series GUID from the ID
                    series_guid = self.get_etp_guid(series_id=media_id)['series']
                else:
                    series_guid = media_id
                    
            self.get_series_info(series_id=series_guid)
            
            self.create_progress_bar(desc=self.info.title, total=self.info.total_episodes, leave=False)

            for season in self.get_seasons(series_guid=series_guid):
                self.get_season_info(season_id=season['id'])
                self.get_episodes_from_season(season_id=season['id'])
                
            self.progress_bar.close()
        
        elif url_type == 'episode':
            if media_id.isdigit():
                episode_guid = self.get_etp_guid(episode_id=media_id)['episode']
            else:
                episode_guid = media_id
                
            # Get raw episode info
            episode_info = self.get_episode_info(episode_id=episode_guid, return_raw_info=True)
            
            # Get series and season's guid using regex
            series_guid = re.search(r'/(\w+)$', episode_info['__links__']['episode/series']['href']).group(1)
            season_guid = re.search(r'/(\w+)$', episode_info['__links__']['episode/season']['href']).group(1)
            
            # Get series and season info
            self.get_series_info(series_id=series_guid)
            self.get_season_info(season_id=season_guid)
            # Parse the raw episode info
            self._parse_episode_info(episode_info=episode_info)
            # Link the episode with the season
            self.season.link_episode(episode=self.episode)
        
        return self.info