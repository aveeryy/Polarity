from polarity.types import Series, Season, Episode, Movie, Stream
from polarity.types.ffmpeg import VIDEO, AUDIO, SUBTITLES
from polarity.extractor.base import BaseExtractor
from polarity.config import ConfigError, lang
from polarity.utils import is_content_id, parse_content_id, vprint, request_json, request_webpage
from urllib.parse import urlparse
import re
import os


class AtresplayerExtractor(BaseExtractor):
    '''
    ## Atresplayer Extractor
    `www.atresplayer.com`
    ### Region lock
    Stuff is region locked to Spain, some content is available worldwide with a premium account
    '''

    HOST = r'(?:http(?:s://|://|)|)(?:www.|)atresplayer.com'
    DEFAULTS = {
        'codec': 'hevc',
        # 'fetch_extras': False,
        }
    API_URL = 'https://api.atresplayer.com/'
    ACCOUNT_URL = 'https://account.atresplayer.com/'
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
    
    FLAGS = {
        'REQUIRES_LOGIN'
    }
    
    @classmethod
    def return_class(self): return __class__.__name__

    def login(self, user: str, password: str):

        res = request_json(
            url=self.account_url + 'auth/v1/login',
            method='POST',
            data={'username': user, 'password': password},
            cookies=self.cjar
            )
        if self.res[1].status_code == 200:
            vprint(lang['extractor']['login_success'], 1, 'atresplayer')
            vprint('Logged in as %s' % user, 3, 'atresplayer', 'debug')
            self.save_cookies_in_jar(self.res[1].cookies, ['A3PSID'])
            return True
        vprint(lang['extractor']['login_success']
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

    def get_series_info(self, identifier: str):
        series_json = request_json(self.API_URL +'client/v1/page/format/' + identifier)[0]
        _episodes = request_json(
            self.API_URL + 'client/v1/row/search',
            params={
                'entityType': 'ATPEpisode',
                'formatId': identifier,
                'size': 1
            })

        vprint(
            lang['extractor']['get_media_info'] % (
                lang['types']['alt']['series'],
                series_json['title'].strip(),
                identifier
                ),
            level=1,
            module_name='atresplayer'
            )
        
        self.info = Series(
            title=series_json['title'].strip(),
            id=identifier,
            synopsis=series_json['description'] if 'description' in series_json else '',
            genres=[genre['title'] for genre in series_json['tags']],
            images=[
                series_json['image']['pathHorizontal'] + '0',
                series_json['image']['pathVertical'] + '0',
            ],
            season_count=None,
            episode_count=_episodes[0]['pageInfo']['totalElements'],
            year=1970,
        )

        return self.info

    def get_seasons(self):
        vprint(lang['extractor']['get_all_seasons'], 2, 'atresplayer')
        return [season['link']['href'][-24:] for season in self.series_json['seasons']]
            
              
    def get_season_info(self, season_id=str):
        # Download season info json
        season_json = request_json(self.API_URL + 'client/v1/page/format/%s?seasonId=%s' %(self.info.id, season_id))[0]
        
        vprint(
            message=lang['extractor']['get_media_info'] % (
                lang['types']['alt']['season'],
                season_json['title'],
                season_id),
            level=2,
            module_name='atresplayer'
            )
         
        season_jsonld = request_json(
            url=self.API_URL + 'client/v1/jsonld/format/%s' % self.info.id,
            params={'seasonId': season_id}
            )
        
        season = Season(
            title=season_json['title'],
            id=season_id,
            synopsis=season_json['description'] if 'description' in season_json else '',
            number=season_jsonld[0]['seasonNumber'],
            year=1970,
            images=[season_json['image']['pathHorizontal'] + '0'],
            episode_count=len(season_jsonld[0]['episode']),
            finished=False
        )

        return season
        
    def get_episodes_from_season(self, season_id: str) -> list[Episode]:
        episodes = []
        page = 0
        total_pages = 727  # placeholder variable
        while page < total_pages:
            page_json = request_json(
                url=self.API_URL + 'client/v1/row/search',
                params={
                    'entityType': 'ATPEpisode',
                    'formatId': self.info.id,
                    'seasonId': season_id,
                    'size': '100',
                    'page': page
                }
                )[0]
            
            if 'pageInfo' not in page_json:
                vprint(self.extractor_lang['no_content_in_season'] %(page_json['title'], season_id), 1, 'atresplayer', 'warning')
                break
            
            total_pages = page_json['pageInfo']['totalPages']
            for episode in page_json['itemRows']:
                # Add episode to episodes list
                episodes.append(self.get_episode_info(episode['contentId']))
            page += 1
        return episodes

    def get_episode_info(self, episode_id=str) -> Episode:
        if not self.cookie_exists('A3PSID'):
            self.login()
            
        drm = False


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
        self.episode = Episode()

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
                        self.stream = Stream(
                            url=stream['src'],
                            name={
                                AUDIO: 'Español'
                            },
                            language={
                                AUDIO: 'spa'
                            },
                            id=stream_type[1],
                            preferred=False,
                            key=None
                        )
                        self.episode.link_stream(self.stream)
                        if multi_lang:
                            self.stream.language = {AUDIO: ['spa', 'eng']}
                            self.stream.name = {AUDIO: ['Español', 'English']}
                        if subtitles:
                            self.stream.language[SUBTITLES] = 'spa'
                            self.stream.name[SUBTITLES] = 'Español'
                        
                        if 'drm' in stream and not drm:
                            drm = True
                        streams.append(stream_type[1])
                        

            if drm and 'hls_hevc' not in streams or drm and self.options['codec'].lower() == 'avc':
                # Case 1.1: DRM stream and not HEVC stream
                # Case 1.2: DRM stream and HEVC stream but codec preferance is AVC
                preferred = 'hls_drmless'
                # Get subtitles from the DRM-HLS stream
                self.stream = Stream(
                    url=self.episode.get_stream_by_id('hls').url,
                    id='hls_drmless_subs',
                    name='Español',
                    language='spa',
                    preferred=True,
                    key=None
                )
                self.episode.link_stream(self.stream)
                self.stream.extra_sub = True
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
        
        # TODO: support for this without extraction
        if self.url not in (None, str):
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

    def extract(self):
        self.extraction = True
        
        download_id = is_content_id(self.url)
        
        if not download_id:
            # Gets url's content type
            self.url_type = self.identify_url(self.url)
        else:
            parsed = parse_content_id(self.url)
            self.url_type = parsed.content_type
        
        # Gets series id if the content isn't an episode
        if self.url_type not in ('episode', 'movie'):
            if not download_id:
                self.web = request_webpage(self.url).content.decode()
                identifier = re.search(r'u002Fpage\\u002Fformat\\u002F(?P<id>[0-9a-f]{24})', self.web).group(1)  # Series ID
            elif download_id:
                identifier = parsed.id
                # Gets series information
            self.get_series_info(identifier)
            

        if self.url_type == 'series':
            # Gets information from all seasons
            self.create_progress_bar(desc=self.info.title, total=self.info.episode_count, leave=False)
            for season in self.get_seasons():
                season = self.get_season_info(season)
                episodes = self.get_episodes_from_season(season.id)
                self.info.link_season(season=season)
                for episode in episodes:
                    season.link_episode(episode=episode)
            self.progress_bar.close()
                
            
        elif self.url_type == 'season':
            if not download_id:
                # Get season id from the page's html
                identifier = re.search(r'seasonId=(?P<season_id>[0-9a-f]{24})',self.web).group(1)  # Season ID
            else:
                identifier = parsed.id
            # Gets single season information
            season = self.get_season_info(identifier)
            self.create_progress_bar(desc=self.info.title, total=season.episode_count, leave=False)
            episodes = self.get_episodes_from_season(season.id)
            self.info.link_season(season=season)
            for episode in episodes:
                season.link_episode(episode=episode)
            self.progress_bar.close()

        elif self.url_type in ('episode', 'movie'):
            if not download_id:
                # Get episode ID from the inputted url
                episode_identifier = re.search(r'(?P<id>[0-9a-f]{24})', self.url).group(1)
            else:
                episode_identifier = parsed.id
            # Get season page from jsonld API
            json = request_json(self.API_URL + 'client/v1/jsonld/episode/' + episode_identifier)[0]
            web = request_webpage(json['partOfSeason']['@id']).content.decode()
            # Get the series identifier
            identifier = re.search(r'u002Fpage\\u002Fformat\\u002F(?P<id>[0-9a-f]{24})', web).group(1)  # Series ID
            self.get_series_info(identifier)
            season_identifier = re.search(r'seasonId=(?P<season_id>[0-9a-f]{24})', web).group(1)  # Season ID
            season = self.get_season_info(season_identifier)
            episode = self.get_episode_info(episode_identifier)
            
            self.info.link_season(season)
            season.link_episode(episode=episode)
            
        return self.info