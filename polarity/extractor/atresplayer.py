from polarity.types.movie import Movie
from polarity.types import Series, Season, Episode
from polarity.extractor.base import BaseExtractor
from polarity.config import ConfigError, lang
from polarity.utils import is_download_id, parse_download_id, vprint, request_json, request_webpage
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
    
    LOGIN_REQUIRED = True

    DEFAULTS = {
        'codec': 'hevc',
        # 'fetch_extras': False,
        }

    API_URL = 'https://api.atresplayer.com/'
    
    LIVE_CHANNELS = ['antena3', 'lasexta', 'neox', 'nova', 'mega', 'atreseries']

    ARGUMENTS = [
        {
            'args': ['--atresplayer-codec'],
            'attrib': {
                'choices': ['avc', 'hevc'],
                'default': 'hevc',
                'help': lang['atresplayer']['args']['codec'],
            },
            'variable': 'codec'
        },
        #{
        #    'args': ['--atresplayer-extras'],
        #    'attrib': {
        #        'action': 'store_true',
        #        'help': 'Allows fetching extras when extracting'
        #    },
        #    'variable': 'fetch_extras'
        #}
    ]
    
    @classmethod
    def return_class(self): return __class__.__name__

    def login(self, user: str, password: str):
        print(user, password)
        self.account_url = 'https://account.atresplayer.com/'
        self.res = request_json(self.account_url + 'auth/v1/login', 'POST',
                               data={'username': user, 'password': password},
                               cookies=self.cjar)
        if self.res[1].status_code == 200:
            vprint('Login successful', 1, 'atresplayer')
            vprint('Logged in as %s' % user, 3, 'atresplayer', 'debug')
            self.save_cookies_in_jar(self.res[1].cookies, ['A3PSID'])
            return True
        vprint('Login failed. error code: %s'
            % self.res[0]['error'], 1, 'atresplayer', 'error')
        return False
    
    def is_logged_in(self): return self.cookie_exists('A3PSID')

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
        # self.set_main_info('series')
        self.series_json = request_json(self.API_URL +
                                            'client/v1/page/format/' +
                                            self.info.id)[0]
        self._episodes = request_json(self.API_URL + 'client/v1/row/search',
                                           params={'entityType': 'ATPEpisode', 'formatId': self.info.id, 'size': 1})
        self.info.title = self.series_json['title']
        if self.info.title[-1] == ' ':
            self.info.title = self.info.title[:-1]
        vprint(lang['extractor']['get_media_info']
               %(lang['types']['alt']['series'], self.info.title, self.info.id) 
               , 1, 'atresplayer')
        self.info.synopsis = self.series_json['description'] or ''
        self.info.images.append(self.series_json['image']['pathHorizontal'] + '0')
        self.info.images.append(self.series_json['image']['pathVertical'] + '0')

        self.info.total_episodes = self._episodes[0]['pageInfo']['totalElements']

        for genre in self.series_json['tags']:
            self.info.genres.append(genre['title'])

        return self.info

    def get_seasons(self):
        vprint(lang['extractor']['get_all_seasons'], 2, 'atresplayer')
        return [self.get_season_info(season_id=season['link']['href'][-24:]) for season in self.series_json['seasons']]
            
              
    def get_season_info(self, season_id=str):
        self.create_season(independent=self.extraction is False)
        # Download season info json
        self.season_json = request_json(self.API_URL +
                                             'client/v1/page/format/%s?seasonId=%s'
                                             %(self.info.id, season_id))[0]
        vprint(lang['extractor']['get_media_info'] 
               % (lang['types']['alt']['season'],
                  self.season_json['title'],
                  season_id),
               3, 'atresplayer')
        self.season.title = self.season_json['title']
        self.season.id = season_id
        self.season.synopsis = self.season_json['description'] if 'description' in self.season_json else '' 
        self.season.number = request_json(
            url=self.API_URL + 'client/v1/jsonld/format/%s' % self.info.id,
            params={'seasonId': season_id}
            )[0]['seasonNumber']
        self.season.images.append(self.season_json['image']['pathHorizontal'] + '0')

        return self.season
        
    def get_episodes_from_season(self, season_id: str):
        episodes = []
        page = 0
        total_pages = 727  # placeholder variable
        while page < total_pages:
            page_json = request_json(self.API_URL +
                                        'client/v1/row/search?entityType=ATPEpisode&formatId=%s \
                                        &seasonId=%s&size=100&page=%d' %(self.info.id, season_id, self.page))[0]
            try:
                total_episodes = page_json['pageInfo']['totalElements']
                total_pages = page_json['pageInfo']['totalPages']
            except KeyError:
                total_episodes = 0
                vprint(self.extractor_lang['no_content_in_season'] %(self.season_json['title'], season_id), 'atresplayer', 'warning')
                break
            for episode in self.page_json['itemRows']:
                # Add episode to episodes list
                episodes.append(self.get_episode_info(episode['contentId']))
            self.page += 1
        return episodes

    def get_episode_info(self, episode_id=str):
        if not self.cookie_exists('A3PSID'):
            self.login()
            
        drm = False

        self.create_episode(independent=self.extraction is False)

        # Download episode info json
        episode_info = request_json(
            url=self.API_URL + 'client/v1/page/episode/' + episode_id
            )[0]
        
        vprint(
            message=lang['extractor']['get_media_info'] % (
                lang['types']['alt']['episode'],
                episode_info['title'],
                episode_id),
            level=3,
            module_name='atresplayer'
            )

        self.episode.title = episode_info['title']
        self.episode.id = episode_id
        self.episode.synopsis = episode_info['description'] if 'description' in episode_info else ''
        self.episode.number = episode_info['numberOfEpisode']
        self.episode.images.append(episode_info['image']['pathHorizontal'] + '0')
        
        multi_lang = 'languages' in episode_info and 'VO' in episode_info['languages']
        subtitles = 'languages' in episode_info and 'SUBTITLES' in episode_info['languages']

        # Download episode player json
        episode_player = request_json(self.API_URL +
                                'player/v1/episode/' + episode_id, cookies=self.cjar)[0]

        if 'error' in episode_player:
            self.episode.skip_download = self.eps_player['error_description']
        else:
            # Get streams from player json
            stream_map = (
                ('application/vnd.apple.mpegurl', 'hls'),
                ('application/hls+hevc', 'hls_hevc'),
                ('application/hls+legacy', 'hls_drmless'),
                ('application/dash+xml', 'dash'),
                ('application/dash+hevc', 'dash_hevc'),

                )
            
            streams = []
            
            for stream in episode_player['sources']:
                # HLS stream (may have DRM)
                for stream_type in stream_map:
                    if stream['type'] == stream_type[0]:
                        self.create_stream()
                        self.stream.name = 'Español'
                        self.stream.language = 'spa'
                        self.stream.url = stream['src']
                        self.stream.id = stream_type[1]
                        if multi_lang:
                            self.stream.set_multilanguage_flag()
                            self.stream.audio_language = ['spa', 'eng']
                            self.stream.audio_name = ['Español', 'English']
                        if subtitles and stream_type[1] != 'hls_drmless':
                            if multi_lang:
                                self.stream.sub_language = ['spa']
                                self.stream.sub_name = ['Español']
                            else:
                                self.stream.sub_language = 'spa'
                                self.stream.sub_name = 'Español'
                        
                        if 'drm' in stream and not drm:
                            drm = True
                        streams.append(stream_type)

            if drm and 'hls_hevc' not in streams or drm and self.options['codec'].lower() == 'avc':
                # Case 1.1: DRM stream and not HEVC stream
                # Case 1.2: DRM stream and HEVC stream but codec preferance is AVC
                preferred = 'hls_drmless'
                # Get subtitles from the DRM-HLS stream
                self.create_stream()
                self.stream.url = self.episode.get_stream_by_id('hls').url
                self.stream.id = 'hls_drmless_subs'
                self.stream.sub_name = 'Español'
                self.stream.sub_language = 'spa'
                self.stream.extra_sub = True
                self.stream.preferred = True
            elif 'hls_hevc' in streams and self.options['codec'].lower() == 'hevc':
                # Case 2: HEVC stream and preferred codec is HEVC
                preferred = 'hls_hevc'
            elif self.options['codec'].lower() == 'avc' or 'hls_hevc' not in streams:
                # Case 3.1: Not DRM and codec preferance is AVC
                # Case 3.2: Not DRM and not HEVC stream
                preferred = 'hls'
            else:
                raise ConfigError(self.extractor_lang['except']['invalid_codec'])
            
            # Set preferred stream
            self.episode.get_stream_by_id(preferred).preferred = True
    
        self.episode.movie = any(i in self.url for i in ('tv-movies', '/movie-'))

        if hasattr(self, 'progress_bar'):
            self.progress_bar.update(1)

        return self.episode

    # Extra stuff

    @classmethod
    def get_all_genres(self):
        'Returns a dict containing name, id and API url of every Atresplayer genre'
        self.genres = {}
        self.list_index = 0
        while True:
            self.genre_list = request_json(
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
        return request_json('https://account.atresplayer.com/user/v1/me', cookies=self.cjar)[0]

    @classmethod
    def get_live_stream(self, channel: str):
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
            vprint('Unsupported channel', 0, module_name='atresplayer', error_level='error')
            return
        self.livetv_id = _CHANNEL_IDS[channel]
        self.channel_info = request_json(
            url=self.API_URL + f'player/v1/live/{self.livetv_id}'
        )[0]
        return self.channel_info['sources'][0]['src']

    def search(self, term: str):
        # Search within the FORMAT category
        format_results = request_json(
            url=self.API_URL + 'client/v1/row/search',
            params={
                'entityType': 'ATPFormat',
                'text': term,
                'size': 30
            }
        )[0]
        episode_results = request_json(
            url=self.API_URL + 'client/v1/row/search',
            params={
                'entityType': 'ATPEpisode',
                'text': term,
                'size': 30
            }
        )[0]
        if 'itemRows' in format_results and format_results['itemRows']:
            for item in format_results['itemRows']:
                self.create_search_result(item['title'], Series, item['contentId'], item['link']['url'])
        else:
            vprint(f'No results found in category FORMAT using term "{term}"', 2, 'atresplayer', 'warning')
        if 'itemRows' in format_results and format_results['itemRows']:
            for item in episode_results['itemRows']:
                item_type = Episode if not 'tv-movies' in item['link']['url'] else Movie
                self.create_search_result(item['title'], item_type, item['contentId'], item['link']['url'])
        else:
            vprint(f'No results found in category EPISODE using term "{term}"', 2, 'atresplayer', 'warning')
        return self.search_results

    # extractor
    #def extract(self, url=str):
    def extract(self):
        self.extraction = True
        self.set_main_info('series')
        
        download_id = is_download_id(self.url)
        
        if not download_id:
            # Gets url's content type
            self.url_type = self.identify_url(self.url)
        else:
            parsed = parse_download_id(self.url)
            self.url_type = parsed.content_type
        
        # Gets series id if the content isn't an episode
        if self.url_type not in ('episode', 'movie'):
            if not download_id:
                self.web = request_webpage(self.url).content.decode()
                self.info.id = re.search(r'u002Fpage\\u002Fformat\\u002F(?P<id>[0-9a-f]{24})', self.web).group(1)  # Series ID
            elif download_id:
                self.info.id = parsed.id
                # Gets series information
            self.get_series_info()
            self.create_progress_bar(desc=self.info.title, total=self.info.total_episodes, leave=False)

        if self.url_type == 'series':
            # Gets information from all seasons
            for season in self.get_seasons():
                self.create_season(False, **season)
            
        elif self.url_type == 'season':
            if not download_id:
                # Get season id from the page's html
                self.season_id = re.search(r'seasonId=(?P<season_id>[0-9a-f]{24})',self.web).group(1)  # Season ID
            else:
                self.season_id = parsed.id
            vprint(lang['extractor']['obtained_media_id']
                   %(lang['types']['season'], self.season_id), 2, 'atresplayer')
            # Gets single season information
            season = self.get_season_info(self.season_id)
            self.create_season(False, season)

        elif self.url_type in ('episode', 'movie'):
            if not download_id:
                # Get episode ID from the inputted url
                self.episode_id = re.search(r'(?P<id>[0-9a-f]{24})', self.url).group(1)
            else:
                self.episode_id = parsed.id
            # Get season page from jsonld API
            self.json = request_json(self.API_URL + 'client/v1/jsonld/episode/' + self.episode_id)[0]
            self.web = request_webpage(self.json['partOfSeason']['@id']).content.decode()
            # Get the series identifier
            self.info.id = re.search(r'u002Fpage\\u002Fformat\\u002F(?P<id>[0-9a-f]{24})', self.web).group(1)  # Series ID
            vprint(lang['extractor']['obtained_media_id']
                   %(lang['types']['series'], self.info.id), 2, 'atresplayer')
            self.get_series_info()
            self.season_id = re.search(r'seasonId=(?P<season_id>[0-9a-f]{24})', self.web).group(1)  # Season ID
            vprint(lang['extractor']['obtained_media_id']
                   %(lang['types']['season'], self.season_id), 2, 'atresplayer')
            self.get_season_info(self.season_id)
            self.get_episode_info(self.episode_id)
        return self.info