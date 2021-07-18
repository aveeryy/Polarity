from .base import BaseExtractor
from ..config import ConfigError
from ..utils import load_language, vprint
from urllib.parse import urlparse
import re
import os

class AtresplayerExtractor(BaseExtractor):
    '''
    ## Atresplayer Extractor
    `www.atresplayer.com`
    ### Region lock
    Stuff is region locked to Spain, some content is available worldwide with a premium account
    ### Fun stuff I found in the API:
    #### Smart TV interface on web
    `Any of these links work`
    - https://smarttv.atresplayer.com/_pruebas/DEVOPS/cmp_legacy/
    - https://smarttv.atresplayer.com/_pruebas/LAST_DEVELOP/
    - https://smarttv.atresplayer.com/_pruebas/startOver/
    - https://smarttv.atresplayer.com/_pruebas/samsung_sin_fix_2020/
    - https://smarttv.atresplayer.com/_pruebas/samsung_vjs7/
    - https://smarttv.atresplayer.com/_pruebas/DEVOPS/TRSLPR2021-1986_Multiaudio2020/
    - https://smarttv.atresplayer.com/_pruebas/DEVOPS/AVISO_PAGO_PRE/ `Will log you out!!`
    '''

    HOST = r'(?:http(?:s://|://|)|)(?:www.|)atresplayer.com'

    DEFAULTS = {
        'codec': 'hevc',
        'fetch_extras': False,
        }

    API_URL = 'https://api.atresplayer.com/'

    ARGUMENTS = [
        {
            'args': ['--atresplayer-codec'],
            'attrib': {
                'choices': ['avc', 'hevc'],
                'default': 'hevc',
                'help': 'Atresplayer codec preferance',
            },
            'variable': 'codec'
        },
        {
            'args': ['--atresplayer-extras'],
            'attrib': {
                'action': 'store_true',
                'help': 'Allows fetching extras when extracting'
            },
            'variable': 'fetch_extras'
        }
    ]

    @classmethod
    def return_class(self): return __class__.__name__.lower()

    def login(self, email=str, password=str):
        self.email, self.password = self.login_form(email, password)
        self.account_url = 'https://account.atresplayer.com/'
        self.res = self.request_json(self.account_url + 'auth/v1/login', 'POST',
                               data={'username': self.email, 'password': self.password},
                               cookies=self.cjar)
        if self.res[1].status_code == 200:
            vprint('Login successful', 1, 'atresplayer')
            vprint('Logged in as %s' % self.email, 3, 'atresplayer', 'debug')
            self.save_cookies_in_jar(self.res[1].cookies, ['A3PSID'])
            return True
        vprint('Login failed. error code: %s'
            % self.res[0]['error'], 1, 'atresplayer', 'error')
        return False

    @classmethod
    def identify_url(self, url=str):
        self.url_path = urlparse(url).path
        self.subtypes = ['antena3', 'lasexta', 'neox', 'nova', 'mega', 'atreseries', 'flooxer', 'kidz', 'novelas-nova']
        self.regex = {
            'series':  r'/[^/]+/[^/]+/\Z',
            'season':  r'/[^/]+/[^/]+/[^/]+/\Z',
            'episode': r'/[^/]+/[^/]+/[^/]+/.+?_[0-9a-f]{24}/\Z'}
        self.with_sub = any(s in self.url_path for s in self.subtypes)
        for utype, regular in self.regex.items():
            if self.with_sub:
                regular = r'/[^/]+' + regular
            if re.match(regular, self.url_path) is not None:
                return utype
        return

    def get_series_info(self):
        # self.load_info_template('series')
        self.series_json = self.request_json(self.API_URL +
                                            'client/v1/page/format/' +
                                            self.info['id'])[0]
        self._episodes = self.request_json(self.API_URL + 'client/v1/row/search',
                                           params={'entityType': 'ATPEpisode', 'formatId': self.info['id'], 'size': 1})
        self.info['title'] = self.series_json['title']
        if self.info['title'][-1] == ' ':
            self.info['title'] = self.info['title'][:-1]
        vprint(self.lang['extractor']['generals']['get_media_info']
               %(self.lang['extractor']['generals']['media_types']['series'], self.info['title'], self.info['id']) 
               , 1, 'atresplayer')
        self.info['synopsis'] = self.series_json['description'] or ''
        self.info['images']['wide'].append(self.series_json['image']['pathHorizontal'] + '0')
        self.info['images']['tall'].append(self.series_json['image']['pathVertical'] + '0')

        self.info['total_episodes'] = self._episodes[0]['pageInfo']['totalElements']

        for genre in self.series_json['tags']:
            self.info['genres'].append(genre['title'])

        return self.info

    def get_seasons(self):
        vprint(self.lang['extractor']['generals']['get_all_seasons'], 2, 'atresplayer')
        return [self.get_season_info(season_id=season['link']['href'][-24:]) for season in self.series_json['seasons']]
            
              
    def get_season_info(self, season_id=str, get_episodes=True):
        self._season_episodes = []
        # Download season info json
        self.season_json = self.request_json(self.API_URL +
                                             'client/v1/page/format/%s?seasonId=%s'
                                             %(self.info['id'], season_id))[0]
        vprint(self.lang['extractor']['generals']['get_media_info'] 
               % (self.lang['extractor']['generals']['media_types']['season'],
                  self.season_json['title'],
                  season_id),
               3, 'atresplayer')        
        self.season_number = self.request_json(self.API_URL + 
                                               'client/v1/jsonld/format/\
                                               %s?seasonId=%s' %(self.info['id'], season_id)
                                               )[0]['seasonNumber']
        if get_episodes:
            self.page = 0
            self.total_pages = 727  # placeholder variable
            while self.page < self.total_pages:
                self.page_json = self.request_json(self.API_URL +
                                            'client/v1/row/search?entityType=ATPEpisode&formatId=%s \
                                            &seasonId=%s&size=100&page=%d' %(self.info['id'], season_id, self.page))[0]
                try:
                    self._total_episodes = self.page_json['pageInfo']['totalElements']
                    self.total_pages = self.page_json['pageInfo']['totalPages']
                except KeyError:
                    self._total_episodes = 0
                    vprint(self.extractor_lang['no_content_in_season'] %(self.season_json['title'], season_id), 'atresplayer', 'warning')
                    break
                for episode in self.page_json['itemRows']:
                    # Add episode to episodes list
                    self._season_episodes.append(self.get_episode_info(episode['contentId']))
                self.page += 1
        return {
            'title': self.season_json['title'],
            'id': season_id,
            'synopsis': self.season_json['description'] if 'description' in self.season_json else '',
            'season_number': self.season_number,
            'images': {'wide': [self.season_json['image']['pathHorizontal'] + '0']},
            'total_episodes': self._total_episodes if hasattr(self, '_total_episodes') else None,
            'episodes': self._season_episodes
        }

    def get_episode_info(self, episode_id=str):
        if not self.cookie_exists('A3PSID'):
            self.login()
        self.metadata = [
            {
                'index': '0:a:0',
                'language': 'spa',
                'title': 'Español'
            },
            {
                'index': '0:s:0',
                'language': 'spa',
                'title': 'Español'
            }
        ]
        self._episode_info = {'streams': {}}

        # Download episode info json
        self.eps_info = self.request_json(self.API_URL +
                                                   'client/v1/page/episode/' + episode_id)[0]
        vprint(self.lang['extractor']['generals']['get_media_info'] 
               % (self.lang['extractor']['generals']['media_types']['episode'],
                  self.eps_info['title'],
                  episode_id),
               3, 'atresplayer')

        if 'languages' in self.eps_info and 'VO' in self.eps_info['languages']:
            self.metadata.append(
                {
                    'index': '0:a:1',
                    'language': 'eng',
                    'title': 'English'
                }
            )
        # Download episode player json
        self.eps_player = self.request_json(self.API_URL +
                                'player/v1/episode/' + episode_id, cookies=self.cjar)[0]

        if 'error' in self.eps_player:
            vprint('error message: ' + self.eps_player['error_description'], 1, 'atresplayer', 'error')
            self._episode_info['fail_to_download'] = self.eps_player['error_description']
        else:
            # Get streams from player json
            self.stream_map = (
                ('application/vnd.apple.mpegurl', 'hls'),
                ('application/hls+hevc', 'hls_hevc'),
                ('application/hls+legacy', 'hls_drmless'),
                ('application/dash+xml', 'dash'),
                ('application/dash+hevc', 'dash_hevc'),

                )
            for stream in self.eps_player['sources']:
                # HLS stream (may have DRM)
                for stream_type in self.stream_map:
                    if stream['type'] == stream_type[0]:
                        self._episode_info['streams'][stream_type[1]] = stream['src']
                        if 'drm' in stream and 'drm' not in self._episode_info:
                            self._episode_info['drm'] = True
            if 'drm' not in self._episode_info:
                self._episode_info['drm'] = False

            # TODO. Make this better and cleaner lol
            if self._episode_info['drm'] and 'hls_hevc' not in self._episode_info['streams'] or self._episode_info['drm'] and self.options['codec'].lower() == 'avc':
                self._episode_info['stream_preferance'] = 'hls_drmless'
                self._episode_info['extra_subs'] = [{'name': 'Español', 'url': self._episode_info['streams']['hls'], 'lang': 'spa'}]
                self._episode_info['subs_preferance'] = ['spa']
            elif 'hls_hevc' in self._episode_info['streams'] and self.options['codec'].lower() == 'hevc':
                self._episode_info['stream_preferance'] = 'hls_hevc'
            elif self.options['codec'].lower() == 'avc' or 'hls_hevc' not in self._episode_info['streams']:
                self._episode_info['stream_preferance'] = 'hls'
            else:
                raise ConfigError(self.extractor_lang['exceptions']['invalid_codec'])

        if 'tv-movies' in self.url:
            self._episode_info['type'] = 'movie'
        else:
            self._episode_info['type'] = 'episode'

        if hasattr(self, 'progress_bar'):
            self.progress_bar.update(1)

        return {
            **{
                'title': self.eps_info['title'],
                'id': episode_id,
                'synopsis': self.eps_info['description'] if 'description' in self.eps_info else '',
                'episode_number': self.eps_info['numberOfEpisode'],
                'images': {'wide': [self.eps_info['image']['pathHorizontal'] + '0']},
                'metadata': self.metadata,
            },
            **self._episode_info
        }

    @classmethod
    def search_function(self):
        pass

    'Fun stuff'

    @classmethod
    def get_all_genres(self):
        'Returns a dict containing name, id and api url of every Atresplayer genre'
        self.genres = {}
        self.list_index = 0
        while True:
            self.genre_list = self.request_json(
                url=self.API_URL + f'client/v1/row/search?entityType=ATPGenre&size=100&page={self.list_index}'
            )[0]
            for genre in self.genre_list['itemRows']:
                self.genres[genre['title']] = {
                    'id': genre['contentId'],
                    'api_url': genre['link']['href']
                }
            if self.genre_list['pageInfo']['last'] is not True:
                self.list_index += 1
                continue
            break
        return self.genres

    def get_account_info(self):
        'Requires to be logged in, returns an untouched dict containing account information like name, email or gender'
        return self.request_json('https://account.atresplayer.com/user/v1/me', cookies=self.cjar)[0]

    'Livestream stuff'

    @classmethod
    def get_live_tv_stream(self, channel='antena3' or 'lasexta' or 'neox' or 'nova' or 'mega' or 'atreseries'):
        'Gets the m3u8 stream of a live tv channel'
        _CHANNEL_IDS = {
            'antena3': '5a6a165a7ed1a834493ebf6a',
            'lasexta': '5a6a172c7ed1a834493ebf6b',
            'neox': '5a6a17da7ed1a834493ebf6d',
            'nova': '5a6a180b7ed1a834493ebf6e',
            'mega': '5a6a18357ed1a834493ebf6f',
            'atreseries': '5a6a189a7ed1a834493ebf70',
        }
        if channel not in _CHANNEL_IDS:
            vprint('Unsupported channel', module_name='atresplayer', error_level='error')
            return
        self.livetv_id = _CHANNEL_IDS[channel]
        self.channel_info = self.request_json(
            url=self.API_URL + f'player/v1/live/{self.livetv_id}'
        )[0]
        return self.channel_info['sources'][0]['src']

    # extractor
    #def extract(self, url=str):
    def extract(self):
        # Gets url's content type
        # self.url_type = self.identify_url(url=url)
        self.url_type = self.identify_url(self.url)
        self.load_info_template('series')
        # Gets series id if the content isn't an episode
        if self.url_type != 'episode':
            self.web = self.request_webpage(self.url).content.decode()
            self.info['id'] = re.search(r'u002Fpage\\u002Fformat\\u002F(?P<id>[0-9a-f]{24})', self.web).group(1)  # Series ID
            vprint(self.lang['extractor']['generals']['obtained_media_id']
                   %(self.lang['downloader']['media_types']['series'], self.info['id']), 2, 'atresplayer')
            # Gets series information
            self.get_series_info()
            self.create_progress_bar(desc=self.info['title'], total=self.info['total_episodes'], leave=False)

        if self.url_type == 'series':
            # Gets information from all seasons
            for season in self.get_seasons():
                self.create_season(**season)
                self.append_season()
            
        elif self.url_type == 'season':
            # Get season id from the page's html
            self.season_id = re.search(r'seasonId=(?P<season_id>[0-9a-f]{24})',self.web).group(1)  # Season ID
            vprint(self.lang['extractor']['generals']['obtained_media_id']
                   %(self.lang['downloader']['media_types']['season'], self.season_id), 2, 'atresplayer')
            # Gets single season information
            self.__season = self.get_season_info(self.season_id)
            self.create_season(**self.__season)
            self.append_season()

        elif self.url_type == 'episode':
            # Get episode ID from the inputted url
            self.episode_id = re.search(r'(?P<id>[0-9a-f]{24})', self.url).group(1)
            # Get season page from jsonld API
            self.json = self.request_json(self.API_URL + 'client/v1/jsonld/episode/' + self.episode_id)[0]
            self.web = self.request_webpage(self.json['partOfSeason']['@id']).content.decode()
            # Get the series identifier
            self.info['id'] = re.search(r'u002Fpage\\u002Fformat\\u002F(?P<id>[0-9a-f]{24})', self.web).group(1)  # Series ID
            vprint(self.lang['extractor']['generals']['obtained_media_id']
                   %(self.lang['downloader']['media_types']['series'], self.info['id']), 2, 'atresplayer')
            self.get_series_info()
            self.create_progress_bar(desc=self.info['title'], total=1, leave=False)
            self.season_id = re.search(r'seasonId=(?P<season_id>[0-9a-f]{24})', self.web).group(1)  # Season ID
            vprint(self.lang['extractor']['generals']['obtained_media_id']
                   %(self.lang['downloader']['media_types']['season'], self.season_id), 2, 'atresplayer')
            self.__season = self.get_season_info(self.season_id, get_episodes=False)
            self.create_season(**self.__season)
            self.__episode = self.get_episode_info(self.episode_id)
            self.create_episode(**self.__episode)
            self.append_episode()
            self.append_season()

        self.progress_bar.close()
        return self.info