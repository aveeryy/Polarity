from .base import BaseExtractor, ExtractorError, ContentUnavailableError
from urllib.parse import urlparse
import requests
from requests.cookies import create_cookie
import json
import re
from ..utils import order_list, vprint

from cloudscraper import (CloudflareChallengeError, CloudflareCaptchaProvider, CloudflareCaptchaError)

class CrunchyrollExtractor(BaseExtractor):
    
    # Extractor config
    HOST = r'(?:http(?:s://|://|)|)(?:www.|)crunchyroll.com'

    # API URLs
    _url = 'https://www.crunchyroll.com/%s/'
    api_url = 'https://api.crunchyroll.com/'

    # Dict containing languages' respective lang codes
    # Format - code: (subs lang name, subs lang code, info lang code, dub regex)
    _lang_codes = {
        'enUS': ('English (USA)', 'eng', '', r'\(English Dub\)'),
        'esES': ('Español (España)', 'spa', 'es-es', r'null'),  
        'esLA': ('Español (América Latina)', 'spa', 'es', r'\(Spanish Dub\)'),
        'frFR': ('Français (France)', 'fre', 'fr', r'\(French Dub\)'),
        'ptBR': ('Português (Brasil)', 'por', 'pt-br', r'\(Portuguese Dub\)'),
        'arME': ('العربية', 'ara', 'ar', r'null'),
        'itIT': ('Italiano', 'ita', 'it', r'\(Italian Dub\)'),
        'deDE': ('Deutsch', 'ger', 'de', r'\(German Dub\)'),
        'ruRU': ('Русский', 'rus', 'ru', r'\(Russian\)'),
        'jpJP': ('日本語',  'jpn', '', r'[^()]'),
        }

    DEFAULTS = {
        'sub_language': ['all'],
        'dub_language': ['all'],
        'meta_language': 'enUS',
        'hardsub_language': 'none',
        'spoof_us_session': True}
        
    ARGUMENTS = [
        {
            'args': ['--crunchyroll-subs'],
            'attrib': {
                'choices': ['all', 'enUS', 'esES', 'esLA', 'frFR', 'ptBR', 'arME', 'itIT', 'deDE', 'ruRU'],
                'help': 'Crunchyroll subtitle languages to download',
                'nargs': '+',
            },
            'variable': 'sub_language'
        },
        {
            'args': ['--crunchyroll-dubs'],
            'attrib': {
                'choices': ['all', 'jpJP', 'enUS', 'esLA', 'frFR', 'ptBR', 'itIT', 'deDE', 'ruRU'],
                'help': 'Crunchyroll dub languages to download',
                'nargs': '+',
            },
            'variable': 'dub_language'
        },
        {
            'args': ['--crunchyroll-meta'],
            'attrib': {
                'choices': ['enUS', 'esLA', 'esES', 'frFR', 'ptBR', 'arME', 'itIT', 'deDE', 'ruRU'],
                'help': 'Metadata language for Crunchyroll',
            },
            'variable': 'meta_language'
        },
        {
            'args': ['--crunchyroll-hardsub'],
            'attrib': {
                'choices': ['none', 'enUS', 'esLA', 'esES', 'frFR', 'ptBR', 'arME', 'itIT', 'deDE', 'ruRU'],
                'help': 'Download a hardsubbed version',
            },
            'variable': 'hardsub_language'
        },
        {
            'args': ['--crunchyroll-usa-session'],
            'attrib': {
                'action': 'store_true',
                'help': 'Spoof a Crunchyroll USA session'
                },
            'variable': 'spoof_us_session'
        },
        {
            'args': ['--crunchyroll-email'],
            'attrib': {
                'help': 'Your Crunchyroll email'
            },
            'variable': 'username'
        },
        {
            'args': ['--crunchyroll-password'],
            'attrib': {
                'help': 'Your Crunchyroll password',
            },
            'variable': 'password'
        },
        {
            'args': ['--crunchyroll-session'],
            'attrib': {
                'help': 'Use a custom session_id'
            },
            'variable': 'session'
        }
    ]

    @classmethod
    def return_class(self): return __class__.__name__.lower()

    @classmethod
    def translate_beta_lang(self, lang_code=str): return lang_code.replace('-', '').replace('419', 'LA')

    def load_at_init(self):
        # Convert Crunchyroll's Beta language string to legacy ones
        # Examples: es-ES -> esES or es-419 -> esLA
        self.options['sub_language'] = [
            self.translate_beta_lang(s)
            for s in self.options['sub_language']
            ]
        self.options['dub_language'] = [
            self.translate_beta_lang(s)
            for s in self.options['dub_language']
            ]
        self.options['meta_language'] = self.translate_beta_lang(self.options['meta_language'])
        self.options['hardsub_language'] = self.translate_beta_lang(self.options['hardsub_language'])
        # Set metadata language
        try:
            self._url = self._url % self._lang_codes[self.options['meta_language']][2]
        except KeyError:
            vprint(self.lang['crunchyroll']['invalid_metadata'], 1, 'crunchyroll', 'warning')
            self._url = self._url % ''

    def get_session_id(self, force_new=False):
        def user_region():
            vprint(self.extractor_lang['session_id_region'], 1, 'crunchyroll')
            while True:
                self._cookies_req = self.request_webpage(self.api_url + 'start_session.0.json?device_type=com.crunchyroll.windows.desktop&device_id=00000000-0000-0000-0000-000000000000&access_token=LNDJgOit5yaRIWN', cookies=self.cjar)
                if not 'session_id' in self._cookies_req.cookies:
                    vprint(self.extractor_lang['session_id_failure'], 1, 'crunchyroll', 'error')
                    continue
                break
            for cookie in self._cookies_req.cookies:
                self.cjar.set_cookie(cookie)
            self.cjar.save(ignore_discard=True, ignore_expires=True)
            self._s = [c for c in self._cookies_req.cookies if c.name == 'session_id'][0].value
            return self._s

        def usa_region():           
            vprint(self.extractor_lang['session_id_usa'], 1, 'crunchyroll')
            self.id_server = 'https://cr-unblocker.us.to/start_session'
            self.session_json = self.request_json(url=self.id_server)[0]['data']
            self.cookie_values = {'name': 'session_id',
                                  'value': self.session_json['session_id'],
                                  'expires': None,
                                  'domain': '.crunchyroll.com',
                                  'path': '/',
                                  'version': 0}
            self.cookie = create_cookie(**self.cookie_values)
            # Create a requests session and set cookie created before
            self.s = requests.session()
            self.s.cookies.set_cookie(self.cookie)
            # Open cookie jar
            for cookie in self.s.cookies:
                self.cjar.set_cookie(cookie)
            self.cjar.save(ignore_discard=True, ignore_expires=True)            
            return self.session_json['session_id']

        def is_valid(session_id=str):
            self.check_req = self.request_json(self.api_url + 'list_collections.0.json',
                                              params={'session_id': session_id})[0]
            if 'error' in self.check_req and self.check_req['code'] == 'bad_session':
                return False
            return True
        
        if not force_new:
            # Check if there's a cookie
            if self.cookie_exists('session_id'):
                self.saved_session = [c for c in self.cjar if c.name == 'session_id'][0]
                if self.saved_session.value != '':
                    # Non empty session id, valid session
                    if is_valid(self.saved_session.value):
                        vprint(self.extractor_lang['session_id_local'], 1, 'crunchyroll')
                        self.session_id = self.saved_session.value
                        vprint(self.session_id, 3, 'crunchyroll', 'debug')
                        return self.session_id
                    pass
                pass
            
        # In case of invalid / expired session id, get a new one
        if 'session' in self.options:
            if is_valid(self.options['session']):
                self.session_id = self.options['session']
        elif self.options['spoof_us_session']:
            self.session_id = usa_region()
        else:
            self.session_id = user_region()
        vprint(self.extractor_lang['session_id'] + self.session_id, 3, 'crunchyroll', 'debug')
        return self.session_id

    def login(self, email=str, password=str):
        if not hasattr(self, 'session_id'):
            self.get_session_id()
        self.email, self.password = self.login_form(email, password)
        self.login_req = self.request_json(
            self.api_url + 'login.0.json',
            method='post',
            params={
                'session_id': self.session_id,
                'locale': 'enUS',
                'account': self.email,
                'password': self.password
            })
        if self.login_req[0]['error']:
            vprint(self.lang['extractor']['generals']['login_failure'] % self.login_req[0]['message'], 1, 'crunchyroll', 'error')
            return False
        else:
            vprint(self.lang['extractor']['generals']['login_success'], 1, 'crunchyroll')
            vprint(self.lang['extractor']['generals']['login_loggedas'] % self.email, 3, 'crunchyroll', 'debug')
            self.save_cookies_in_jar(self.login_req[1].cookies, ['session_id', 'etp_rt'])
            return True


    def get_series_info(self, series_id=int):
        self.load_info_template('series')
        _series_xml = self.request_xml(self._url +
                                    'syndication/feed?type=episodes&group_id='
                                    + str(series_id), cookies=self.cjar)[0]['rss']['channel']
        vprint(self.lang['extractor']['generals']['get_media_info'] % (self.lang['extractor']['generals']['media_types']['series'], _series_xml['image']['title'], series_id), 1, 'crunchyroll')
        self.info['title'] = _series_xml['image']['title']
        self.info['synopsis'] = _series_xml['description']
        self.info['id'] = series_id
        self.info['total_seasons'] = len(self.get_seasons(series_id))
        self.info['total_episodes'] = len(self.get_all_episodes(series_id).items())
        return self.info

    def get_seasons(self, series_id=int):
        self.seasons = []
        self.season_list = self.request_json(self.api_url +
                                          'list_collections.0.json?session_id=%s&series_id=%d'
                                          % (self.session_id, int(series_id)), cookies=self.cjar)[0]
        if 'error' in self.season_list and self.season_list['error']:
            vprint(self.lang['extractor']['generals']['generic_error'] % self.season_list['message'], 1, 'crunchyroll', 'error')
            vprint(self.lang['crunchyroll']['content_unavailable'], 1, 'crunchyroll', 'error')
            raise ContentUnavailableError
        else:
            self.season_list = self.season_list['data']       
        for s in self.season_list:
            for language, value in self._lang_codes.items():
                if re.search(value[3], s['name']) is not None:
                    self.language = language
                    break
            self.seasons.append({'name': s['name'], 'id': s['collection_id'], 'lang': self.language, 'n': s['season']})
        if not self.seasons:
            vprint(self.lang['crunchyroll']['content_unavailable'], 1, 'crunchyroll', 'error')
            raise ContentUnavailableError
        return self.seasons

    def get_season_info(self, season_id=int, get_episodes=True):
        self.season_xml = self.request_xml(self._url +
                                    'syndication/feed?type=episodes&id='
                                    + str(season_id), cookies=self.cjar)[0]['rss']['channel']
        vprint(self.lang['extractor']['generals']['get_media_info'] % (self.lang['extractor']['generals']['media_types']['season'], self.season_xml['image']['title'], season_id), 3, 'crunchyroll')
        for s in self.get_seasons(self.info['id']):
            if s['id'] == season_id:
                self.language = s['lang']
        self._season_info = {}
        self.season_episodes = []
        if type(self.season_xml['item']) == list:
            try:
                self._season_info['season_number'] = self.season_xml['item'][0]['crunchyroll:season']
            except KeyError: 
                self._season_info['season_number'] = 0
            self._season_info['total_episodes'] = len(self.season_xml['item'])
        else:
            try:
                self._season_info['season_number'] = self.season_xml['item']['crunchyroll:season']
            except KeyError: 
                self._season_info['season_number'] = 0
            self._season_info['total_episodes'] = 1
        self._season_info['season_number'] = int(self._season_info['season_number'])
        if get_episodes:
            if type(self.season_xml['item']) == list:
                for e in self.season_xml['item']:
                    self.episode = self.get_episode_info(e['crunchyroll:mediaId'])
                    self.season_episodes.append(self.episode)
            else:
                self.episode = self.get_episode_info(self.season_xml['item']['crunchyroll:mediaId'])
                self.season_episodes.append(self.episode)
        return {
            **{
                'title': self.season_xml['image']['title'],
                'id': season_id,
                'images': {'tall': [self.season_xml['image']['url']]},
                'synopsis': self.season_xml['description'] if 'description' in self.season_xml else '',
                'episodes': self.season_episodes
            },
            **self._season_info
        }

    def get_episode_info(self, episode_id=int, only_json=False):
        ''
        def get_json(episode_id=int):
            tries = 0
            while True:
                try:
                    eps_page = self.request_webpage(self._url +
                                                        'media-' +
                                                        str(episode_id), cookies=self.cjar).content.decode()
                    if 'vilos.config.media' not in eps_page:
                        tries += 1
                        if 'beta.crunchyroll.com' in eps_page:
                            raise NotImplementedError('Crunchyroll Beta is not supported!')
                        if tries >= 6:
                            vprint('Skipping episode with id %d, requires a premium account or unavailable in your region' %
                                int(episode_id), 1, 'crunchyroll', 'warning')
                            return ('a', 'a')
                        continue          
                    # Get episode json from page's content
                    un_json = re.search(r'vilos.config.media = (?P<json>{.+});', eps_page).group('json')
                    un_info = re.search(r'{"@context":".+}', eps_page).group(0)
                    if not hasattr(self, 'series_id'):
                        self.series_id = re.search(r'group_id="(?P<id>\d+)"', eps_page).group('id')
                    # General episode info
                    j = json.loads(un_json)
                    # Translated episode title and synopsis
                    e = json.loads(un_info)
                except AttributeError:
                    continue
                else:
                    break
            return (j, e)
        self.json, self.eps_info = get_json(episode_id)
        if only_json:
            return self.json
        if self.json == 'a':
            return
        vprint(self.lang['extractor']['generals']['get_media_info'] % (self.lang['extractor']['generals']['media_types']['episode'], self.eps_info['name'], episode_id), 3, 'crunchyroll')
        self.s = {'streams': {}}
        if self.json['metadata']['episode_number'] == '' or self.json['metadata']['episode_number'] is None:
            self.s['type'] = 'movie'
        else:
            self.s['type'] = 'episode'
        # Get adaptive HLS streams
        self.stream_list = [(s['url'], s['hardsub_lang'])
                            for s in self.json['streams']
                            if s['format'] == 'adaptive_hls']
        if not self.stream_list:
            self.s['skip_download'] = self.lang['crunchyroll']['fail_to_download_reason_01']
        else:
            for uri, lang in self.stream_list:
                if lang is None:
                    lang = 'default'
                self.s['streams'][lang] = uri
            # Set preferred hardsub stream
            if self.options['hardsub_language'] == 'none':
                self.s['stream_preferance'] = 'default'
            elif self.options['hardsub_language'] in self.s['streams']:
                self.s['stream_preferance'] = self.options['hardsub_language']
            else:
                self.s['stream_preferance'] = 'default'
            self.s['ffmpeg_args'] = '-map 0:a:0 -metadata:s:a:0 language=%s -metadata:s:a:0 title="%s"' % (
                self._lang_codes[self.language][1], self._lang_codes[self.language][0]
            )
            # Get subtitles
            self.subs = [{'url': s['url'],
                        'internal_code': s['language'],
                        'lang': self._lang_codes[s['language']][1],
                        'name': self._lang_codes[s['language']][0],
                        'forced': False}
                        for s in self.json['subtitles']]

            self.subs = [y for x in self._lang_codes for y in self.subs if x == y['internal_code']]
            
            if 'all' in self.options['sub_language']:
                self.s['subs_preferance'] = [s['lang'] for s in self.subs]
            else:
                self.s['subs_preferance'] = [s['lang']
                                                for s in self.subs
                                                if s['internal_code']
                                                in self.options['sub_language']]

            self.s['extra_subs'] = self.subs
        # Avoid exceptions when using a extractor as an API caller
        if hasattr(self, 'progress_bar'):
            self.progress_bar.update(1)
        return {
            **{
                'title': self.eps_info['name'],
                'id': episode_id,
                'synopsis': self.eps_info['description'] if 'description' in self.eps_info else '',
                'episode_number': self.json['metadata']['episode_number'],
                'image': self.json['thumbnail']['url'],
            },
            **self.s
        }


    def get_all_episodes(self, series_id=int):
        self.all_episodes = {}
        if not hasattr(self, 'season_list'):
            self.get_seasons(series_id)
        for s in self.seasons:
            self.season_eps = self.request_xml(self._url +
                                        'syndication/feed?type=episodes&id='
                                        + s['id'], cookies=self.cjar)[0]['rss']['channel']
            # Tuple format: episode_id: (season_number, episode_number, language)
            if type(self.season_eps['item']) == list:
                for eps in self.season_eps['item']:
                    self.all_episodes[str(eps['crunchyroll:mediaId'])] = (s['id'], s['lang'])
            else:
                eps = self.season_eps['item']
                # Seasons with a single item, like movies or new series, use season number 1
                self.all_episodes[str(eps['crunchyroll:mediaId'])] = (s['id'], s['lang'])
        return self.all_episodes

    def extract(self):
        # Set a session id
        self.get_session_id()
        self.load_info_template('series')
        try:
            _base_url = urlparse(self.url).path
            _series_reg = r'(/[a-z-]{2,5}/|/)([^/]+)(/$|$)'
            _episode_reg = r'(/[a-z-]{2,5}/|/)([^/]+)/[\w-]+-(?P<id>[\d]{6,})'
            _ep_id_reg = r'(/[a-z-]{2,5}/|/)media-(?P<id>[\d]{6,})'
            if re.match(_series_reg, _base_url):
                _url_type = 'series'
            elif re.match(_episode_reg, _base_url) or re.match(_ep_id_reg, _base_url):
                _url_type = 'episode'
            else:
                raise ExtractorError('Invalid Crunchyroll url')

            if _url_type == 'series':
                self._series_page = self.request_webpage(self.url, cookies=self.cjar)
                if self._series_page.status_code == 404:
                    raise ExtractorError('Invalid Crunchyroll url')
                self._series_id = int(re.search(r'ass="show-actions" group_id="(?P<id>\d{5,})"',
                                    self._series_page.content.decode()).group(1))
                self.get_series_info(self._series_id)


                self.total_episodes = len([s for s in self.all_episodes if self.all_episodes[s][1] in self.options['dub_language'] or 'all' in self.options['dub_language']])
                self.create_progress_bar(desc=self.info['title'], total=self.total_episodes, leave=False)
                for s in [s
                          for s in self.get_seasons(self._series_id)
                          if s['lang'] in self.options['dub_language'] or 'all' in self.options['dub_language']]:
                    self.season = self.get_season_info(s['id'])
                    self.create_season(**self.season)
                    self.append_season()

            elif _url_type == 'episode':
                self.episode_id = re.search(r'(\d+)($|/)', self.url).group(1)
                # Get episode info from selected dub
                if self.get_episode_info(self.episode_id, True) == 'a':
                    raise ContentUnavailableError
                self.get_series_info(self.series_id)
                self.create_progress_bar(desc=self.info['title'], total=1, leave=False)
                # Find season and episode dubs
                self.season_id = self.all_episodes[self.episode_id][0]
                self._season = self.get_season_info(self.season_id, False)
                self.create_season(**self._season)
                # Get actual episode info, with dubs and stuff
                self._episode = self.get_episode_info(self.episode_id)
                self.create_episode(**self._episode)
                self.append_episode()
                self.append_season()

        except (CloudflareChallengeError,
                CloudflareCaptchaProvider,
                CloudflareCaptchaError) as e:
            # Return in case of Cloudscraper error
            print(e)
            vprint('you made too many requests to Crunchyroll.', 1, 'crunchyroll', 'critical')
            vprint('all processed episodes will be downloaded, try again in 24 hours to download the rest!', 1, 'crunchyroll', 'critical')
        self.progress_bar.close()
        return self.info

import base64
class CrunchyrollBetaExtractor(BaseExtractor):
    '''
    TODO:
    - Login, need to wait until beta period is over.
    - Actual extracting.
    - Replace beta mentions when beta period is over
    - Starting a session
    '''
    host = 'beta.crunchyroll.com'
    def __init__(self, url=str, options=dict):

        _lang_codes = {
            'en-US': ('English (USA)', 'eng', ''),
            'es-ES': ('Español (España)', 'spa', 'es-es'),     
            'es-419': ('Español (América Latina)', 'spa', 'es'),
            'fr-FR': ('Français (France)', 'fre', 'fr'),
            'de-DE': ('Deutsch', 'ger', 'de'),
            'it-IT': ('Italiano', 'ita', 'it'),
            'pt-BR': ('Português (Brasil)', 'por', 'pt-br'),
            'ar-ME': ('العربية', 'ara', 'ar'),
            'ru-RU': ('Русский', 'rus', 'ru'),
            'jp-JP': ('日本語',  'jpn', ''),
            }
            
        self.token_format = '%s %s' # Token type, token
        self.api_url = 'https://beta-api.crunchyroll.com/'
        self.url = url
        self.defaults = {}
        self.user_options = options
        # TODO: move arguments here
        self.extractor_config('Crunchyroll',
                              'www.crunchyroll.com',
                              True,
                              'Crunchyroll.cjar')
        self.load_info_template('series')

    def fallback_login(self, user=str, password=str):
        'Use old login API'
        self.crunchy = CrunchyrollExtractor(options={'spoof_us_session': True})
        self.crunchy.login(email=user, password=password)
        return


    def check_if_logged_in(self):
        pass

    def grab_tokens(self):
        self.tokens = {}
        self.bucket_re = r'/(?P<country>\w{2})/(?P<madurity>M[1-3])'
        # Grab Basic Authorization token from the main page's content and encode it in base64
        self.contents = self.request_webpage('https://beta.crunchyroll.com', 'get').content.decode()
        self.uncoded_token = re.search(r'"accountAuthClientId":"(?P<id>\w+)"', self.contents).group('id')
        self.tokens['basic'] = base64.encodebytes(bytes(self.uncoded_token,'utf-8')).decode().replace('=', '6').replace('\n', '')
        # Using the Basic Auth token, get the Bearer Auth token
        self.contents = self.request_json(
            self.api_url + 'auth/v1/token',
            method='POST',
            headers={
                'Authorization': self.token_format %('Basic', self.tokens['basic']),
                'Content-Type': 'application/x-www-form-urlencoded'
                },
            data={'grant_type': 'etp_rt_cookie'},
            cookies=self.cjar)[0]
        # Return if an error happened
        if 'error' in self.contents:
            if self.contents['code'] == 'auth.obtain_access_token.oauth2_error':
                vprint('You need to login before using the beta!', module_name='crunchyroll_beta')
            print(self.contents)
            return
        self.tokens['bearer'] = self.contents['access_token']
        # Using the Bearer Auth Token, get api stuff
        self.contents = self.request_json(
            self.api_url + 'index/v2',
            method='GET',
            headers={'Authorization': 'Bearer ' + self.tokens['bearer']},
            cookies=self.cjar)[0]
        if 'error' in self.contents:
            print(self.contents)
            return
        # Get bucket, policy, signature and the key pair id
        self.tokens['bucket'] = self.contents['cms']['bucket']
        self.tokens['policy'] = self.contents['cms']['policy']
        self.tokens['signature'] = self.contents['cms']['signature']
        self.tokens['key_pair_id'] = self.contents['cms']['key_pair_id']
        self.tokens['cms_api_url'] = self.api_url + 'cms/v2' + self.bucket
        self.tokens['country'] = re.match(self.bucket_re, self.bucket).group('country')
        self.tokens['madurity'] = re.match(self.bucket_re, self.bucket).group('madurity')
        vprint('your country: %s' % self.tokens['country'], 1, 'crunchyroll')
        return self.tokens

    def grab_series_info(self, series_id=str):
        self.series_id = series_id
        self.series_json = self.request_json(
            self.cms_api_url + '/series/' + series_id,
            method='get',
            headers={'Authorization': 'Bearer ' + self.bearer_token},
            params={'locale': self.options['meta_language'],
                    'Signature': self.signature,
                    'Policy': self.policy,
                    'Key-Pair-Id': self.key_pair_id})[0]
        self.info['title'] = self.series_json['title']
        self.info['id'] = series_id
        self.info['synopsis'] = self.series_json['description']
        self.info['genres'] = self.series_json['keywords']
        self.info['images']['tall'].append(
            self.series_json['images']['poster_tall'][0][-1:][0]['source']
            )
        self.info['images']['wide'].append(
            self.series_json['images']['poster_wide'][0][-1:][0]['source']
            )
        if self.series_json['season_tags']:
            self.info['year'] = re.search(
                r'(\d+)',
                self.series_json['season_tags'][0]
                ).group(0)

    def grab_season_info(self, season_id=str):
        self.season_json = self.request_json(
            self.cms_api_url + '/seasons/' + season_id,
            method='get',
            headers={'Authorization': 'Bearer ' + self.bearer_token},
            params={
                'locale': self.options['meta_language'],
                'Signature': self.signature,
                'Policy': self.policy,
                'Key-Pair-Id': self.key_pair_id
                }
            )[0]
        self.create_season(
            title=self.season_json['title'],
            id=season_id,
            synopsis=self.season_json['description'],
            season_number=self.season_json['season_number']
        )

    def grab_episodes_from_season(self, season_id=str):
        self.season_episodes = self.request_json(
            self.cms_api_url + '/episodes/',
            method='get',
            headers={'Authorization': 'Bearer ' + self.bearer_token},
            params={
                'season_id': season_id,
                'locale': self.options['meta_language'],
                'Signature': self.signature,
                'Policy': self.policy,
                'Key-Pair-Id': self.key_pair_id
                }
            )[0]
        for episode in self.season_episodes:
            self.parse_episode_info(episode)
        
    def grab_episode_info(self, episode_id=str):
        self.episode_json = self.request_json(
            self.cms_api_url + '/episodes/' + episode_id,
            method='GET',
            headers={'Authorization': 'Bearer ' + self.bearer_token},
            params={
                'locale': self.options['meta_language'],
                'Signature': self.signature,
                'Policy': self.policy,
                'Key-Pair-Id': self.key_pair_id
                }
            )[0]
        if 'error' in self.episode_json:
            print(self.episode_json)
            return
        self.parse_episode_info(self.episode_json)

    def parse_episode_info(self, episode_entry=dict):

        self.create_episode(title=episode_entry['title'],
                            id=episode_entry['id'],
                            synopsis=episode_entry['description'])
        self.episode['images']['wide'].append(
            episode_entry['images']['thumbnail'][0][-1:][0]['source']
            )
        if 'playback' in episode_entry:
            self.stream_list_url = episode_entry['playback']
        elif 'streams' in episode_entry['__links__']:
            self.stream_list_url = episode_entry['__links__']['streams']
        else:
            self.episode['skip_download'] = self.lang['crunchyroll']['fail_to_download_reason_01']
            return
        self.stream_list = self.request_json(
            url=self.stream_list_url,
            method='get'
        )[0]
        # Case 1: Disabled hardsubs or desired hardsub language does not exist
        if self.options['hardsub_language'] == 'none' or self.options['hardsub_language'] not in self.stream_list['adaptive_hls']:
            self.stream = self.stream_list['adaptive_hls']['']
        # Case 2: Desired hardsub language exists
        elif self.options['hardsub_language'] in self.stream_list['adaptive_hls']:
            self.stream = self.stream_list['adaptive'][self.options['hardsub_language']]
        
        # Get subtitles
        if 'all' in self.options['sub_language']:
            self.subtitles = [
                s['url']
                for s in
                order_list(
                    to_order=self.stream_list['subtitles'],
                    order_definer=self._SUBTITLE_ORDER
                    )
                ]
        elif 'all' not in self.options['sub_language']:
            self.subtitles = [
                s['url']
                for s in
                order_list(
                    to_order=self.stream_list['subtitles'],
                    order_definer=self._SUBTITLE_ORDER
                    )
                if s in self.options['sub_language']
                ]
                