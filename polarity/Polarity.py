from copy import deepcopy
from datetime import datetime
from pprint import pprint
from time import sleep
from threading import Lock, Thread, current_thread
from tqdm import TqdmWarning

import json
import os
import toml
import warnings

from polarity.config import config, ConfigError, verbose_level, USAGE, lang
from polarity.downloader import DOWNLOADERS
from polarity.extractor import EXTRACTORS
from polarity.paths import DOWNLOAD_LOG, LANGUAGES
from polarity.types import *
from polarity.utils import filename_datetime, get_compatible_extractor, is_content_id, parse_content_id, request_webpage, sanitize_filename, sanitized_file_exists, send_android_notification, vprint, recurse_merge_dict, normalize_integer
from polarity.update import windows_install, download_languages
from polarity.version import __version__

_ALL_PROCESSES = []

downloader_lock = Lock()

warnings.filterwarnings('ignore', category=TqdmWarning)

class Polarity:
    
    def __init__(self, urls: list, options: dict):
        self.url_pool = urls
        # _STATS['url_queue'] = self.url_pool
        if not options:
            options = {'mode': {}}
        if verbose_level < 0 or verbose_level > 5:
            raise ConfigError(lang['polarity']['except']['verbose_error'] % verbose_level)
        self.options = recurse_merge_dict(config, options)

    def start(self):
        if 'dump' in self.options:
            dump_time = filename_datetime()
            if 'options' in self.options['dump']:
                with open(f'dump_options_{dump_time}.json', 'w') as s:
                    json.dump(self.options, s, indent=4)
            if 'urls' in self.options['dump']:
                with open(f'dump_urls_{dump_time}.log', 'a') as s:
                    for uri in self.url_pool:
                        s.write(f'{uri}\n')
            if 'exit_after_dump' in self.options:
                os._exit(0)
                
        if self.options['update_languages']:
            installed = [f.name.replace('.toml', '') for f in os.scandir(LANGUAGES)]
            download_languages(language_list=installed)
                
        if 'install_windows' in self.options:
            windows_install()
            
        if 'installed_languages' in self.options:
            languages = os.scandir(LANGUAGES)
            if languages is True:
                vprint('Listing installed languages')
                for lang_file in languages:
                    with open(lang_file.path, 'r') as l:
                        _lang = toml.load(f=l)
                    print(f'{_lang["name"]} [{_lang["code"]}] - {lang["author"]}')
            else:
                vprint('No languages found', 1, error_level='critical')
            os._exit(0)
        elif 'list_languages' in self.options:
            language_list = request_webpage('https://aveeryy.github.io/Polarity-Languages/languages.toml')
            parsed_list = toml.loads(language_list.content.decode())
            vprint('Listing available languages')
            for _lang in parsed_list['lang']:
                print(f'{_lang["name"]} [{_lang["code"]}] - {lang["author"]}')
            os._exit(0)
        elif 'install_languages' in self.options:
            download_languages(self.options['install_languages'])

        self.mode = self.options['mode']
        
        if self.mode == 'download':
            '''
            Download mode
            Default mode in Polarity
            Downloads content and metadata from inputted urls and ids
            Uses worker functions
            Input(s): URLs and Download IDs
            External Output(s): video, audio and metadata files
            '''
            if not self.url_pool:
                print(lang['polarity']['use'] + USAGE + '\n')
                print(lang['polarity']['no_urls'])
                print(lang['polarity']['use_help'])
                os._exit(1)
            url_pool = []
            self.workers = []
            for url in self.url_pool:
                extractor = get_compatible_extractor(url=url)
                if extractor[0] is None:
                    continue
                if 'REQUIRES_LOGIN' in extractor[1].FLAGS and not extractor[1]().is_logged_in():
                    vprint(f'Extractor {extractor[0]} requires to be logged in')
                    # Display login form if login is required for that extractor and not logged in
                    username, password = None, None
                    # See if username and password has been passed as an argument
                    if 'username' in self.options['extractor'][extractor[0].lower()]:
                        username = self.options['extractor'][extractor[0].lower()]['username']
                    if 'password' in self.options['extractor'][extractor[0].lower()]:
                        password = self.options['extractor'][extractor[0].lower()]['password']
                    extractor[1]().login_with_form(username, password)
                url_pool.append((url, *extractor))
            for i in range(self.options['download']['simultaneous_urls']):
                worker = Thread(target=self.worker, daemon=True, name=f'worker{i}')
                self.workers.append(worker)
                worker.start()

            while True:
                if [t for t in self.workers if t.is_alive()]:
                    sleep(0.5)
                    continue
                break
            vprint(lang['polarity']['all_tasks_finished'])
        elif self.mode == 'search':
            '''
            Search mode
            Searchs for media content in supported extractors
            Input: words
            Output: results formatted `type - name (download_id)`
            '''
            if not self.options['search_extractor']:
                vprint(lang['polarity']['search_no_extractor'], 1, error_level='error')
                os._exit(0)
            extractor = EXTRACTORS[self.options['search_extractor']]
            if not hasattr(extractor[1], 'search'):
                # TODO: better error handling lol
                raise Exception
            # Join all search terms in a string
            search_term = ' '.join(self.url_pool)
            vprint(lang['polarity']['search_term'] + search_term, 3, error_level='debug')
            results = extractor[1]().search(search_term)
            if not results:
                vprint(lang['polarity']['search_no_results'], 1, error_level='error')
                os._exit(1)
            for result in results:
                if 'search_max_length' in self.options and self.options['search_max_length']:
                    # Limit name length if specified in settings
                    self.options['search_max_length'] = int(self.options['search_max_length'])
                    if len(result.name) > self.options['search_max_length']:
                        result.name = result.name[:self.options['search_max_length']] + '...'
                print(f'{result.type.__name__} - {result.name} ({result.id})')
        elif self.mode == 'live_tv':
            '''
            Live TV mode
            Prints bare m3u8 playlist url, allowing it to be used with
            mpv or vlc for watching, ffmpeg for recording...
            Input: slightly modified download id `extractor/live-name`
            Output: m3u8 playlist `https://example.com/playlist.m3u8`
            '''
            channel = self.url_pool[0]
            parsed = parse_content_id(id=channel)
            print(EXTRACTORS[parsed.extractor][1].get_live_stream(parsed.id))
            os._exit(0)
        elif self.mode == 'print':
            '''
            Print mode
            Prints useful information
            Input: terms via the --printer argument
            Output: requested information
            '''
            def mprint(msg: str):
                'Print a small identifier if more than one information type is requested'
                if multi_print:
                    print(f'======={msg}=======')
            multi_print = len(self.options['printer']) > 1
            if 'urls' in self.options['printer']:
                mprint('URLs')
                print('\n'.join(self.url_pool))
            if 'options' in self.options['printer']:
                mprint('OPTIONS')
                pprint(self.options)
            if 'lang' in self.options['printer']:
                mprint('LANGUAGE')
                pprint(lang)
            if 'live_channels' in self.options['printer']:
                mprint('LIVE_CHANNELS')
                for extractor in EXTRACTORS.values():
                    if hasattr(extractor[1], 'LIVE_CHANNELS'):
                        for channel in extractor[1].LIVE_CHANNELS:
                            print(f'{extractor[0].lower()}/live-{channel}')
                           
        
    def worker(self):
        '''
        ## Worker
        ### Grabs an URL from a pool of URLs and does the extract and download process
        #### Embedded usage
            >>> from polarity import Polarity
            # Mode must be download and there must be at least one URL in urls
            >>> polar = Polarity(urls=[...], options={'mode': 'download', ...})
            # The start function automatically creates worker Threads
            >>> polar.start()
        #### TODO(s)
        - Metadata files creation
        - Status
        '''
        worker_stats = {
            'current_url': '',
            'current_tasks': {
                'extract': {
                    'extractor': None,
                    'finished': False,
                },
                'download': {},
                'metadata': {
                    'items_processed': 0,
                    'finished': False,
                }
            },
            'total_items': 0,
        }
        thread_name = current_thread().name
        # _STATS['running_threads'][thread_name] = stats

        def info_extract():
            extract_function = extractor(
                url=thread_url,
                options=self.options['extractor'][extractor_name.lower()]
            )
            # Call extractor's extract function
            worker_stats['current_tasks']['extract']['finished'] = True
            return extract_function.extract()
        
        def download_task():
            while True:
                if not download_pool:
                    return
                item = download_pool.pop(0)
                content_extended_id = f'{extractor_name.lower()}/{type(item).__name__.lower()}-{item.id}'
                # Skip if output file already exists or id in download log
                if self.id_in_archive(content_extended_id) or sanitized_file_exists(item.output): 
                    if not self.id_in_archive(content_extended_id):
                        self.add_id_to_archive(content_extended_id)
                    if not self.options['download']['redownload']:
                        vprint(
                            message=lang['dl']['no_redownload'] % (
                                lang['types'][type(item).__name__.lower()],
                                item.title),
                            level=1,
                            error_level='warning'
                        )
                        continue

                if hasattr(item, 'skip_download'):
                    vprint(
                        message=lang['dl']['cannot_download_content'] % (
                            lang['types'][type(item).__name__.lower()],
                            item.title,
                            item.skip_download),
                        error_level='warning'
                    )
                    continue

                # Set preferred stream as main stream if set else use stream 0
                stream = item.get_preferred_stream()
                if stream is None:
                    stream = item.streams[0]

                if type(item) == Episode and not item.movie:
                    name = f"{content_info.title} {item.season_id}"
                elif type(item) == Movie or type(item) == Episode and item.movie:
                    name = f"{item.title} ({item.year})"
                    
                vprint(
                    message=lang['dl']['downloading_content']%(
                        lang['types'][type(item).__name__.lower()],
                        item.title
                        )
                    )
                _downloader = DOWNLOADERS[self.options['download']['downloader']] if self.options['download']['downloader'] in DOWNLOADERS else DOWNLOADERS['penguin']
                downloader = _downloader(
                    stream,
                    options=self.options['download'],
                    extra_audio=item.get_extra_audio(),
                    extra_subs=item.get_extra_subs(),
                    name=name,
                    id=item.id,
                    output=item.output
                    )
                downloader.start()
                

                download_successful = lang['dl']['download_successful'] % (
                    lang['types'][type(item).__name__.lower()],
                    name
                    ) 

                vprint(download_successful)

                send_android_notification(contents=download_successful)

                # if self.options['extractor']['postprocessing'] and hasattr(self.extractor[0], 'postprocessing'):
                #     extractor[0]().postprocessing(item['output'])
                if not self.id_in_archive(content_extended_id):
                    self.add_id_to_archive(content_extended_id)
                    
        def make_metafiles_task():
            if content_info['type'] == 'series':
                pass
                               
        while True:
            # Return if there aren't any urls available
            if not self.url_pool:
                return
            thread_url = self.url_pool.pop(0)
            worker_stats['current_url'] = thread_url
            extractor_tupl = get_compatible_extractor(thread_url)
            # Skip if there's not an extractor available
            if extractor_tupl[0] is None:
                vprint(
                    lang['dl']['no_extractor_available'] % (
                        lang['dl']['url'] if not is_content_id(thread_url) else lang['dl']['download_id'],
                        thread_url
                        ),
                    error_level='error'
                    )
                return
            extractor_name, extractor = extractor_tupl
            content_info = info_extract()
            if content_info is None:
                continue
            # Create download and metadata pools
            download_pool = self.build_download_list(extractor_name, content_info)
            metadata_pool = deepcopy(download_pool)
            # Create downloader threads
            for i in range(self.options['download']['simultaneous_downloads_per_url']):
                worker_stats['current_tasks']['download'][f'{thread_name}-{i}'] = {
                    'thread': None,
                    'stats': {
                        'downloader': None,
                        'downloader_stats': {}
                        }
                    }
                worker_stats['current_tasks']['download'][f'{thread_name}-{i}']['thread'] = Thread(target=download_task, name=f'{thread_name}-{i}')
            for t in worker_stats['current_tasks']['download'].values():
                t['thread'].start()
            while True:
                if [t for t in worker_stats['current_tasks']['download'].values() if t['thread'].is_alive()]:
                    sleep(.25)
                    continue
                break
            
    def synchro_worker(self):
        pass


    def build_download_list(self, extractor_name: str, content_info: PolarType):
        'Build a download list out of an extractor output'
        download_list = []
        if type(content_info) == Series:
            # Format series output directory
            series_directory = self.options['download']['series_format'].format(
                W=extractor_name,
                S=content_info.title,
                i=content_info.id,
                y=content_info.year)
            # Sanitize series directory
            series_directory = sanitize_filename(series_directory, True)
            for season in content_info.seasons:
                # Format season output directory
                season_directory = self.options['download']['season_format'].format(
                    W= extractor_name,
                    S=content_info.title,
                    s=season.title,
                    i=season.id,
                    sn=normalize_integer(season.number),
                    Sn=season.number)
                # Sanitize season directory
                season_directory = sanitize_filename(season_directory, True)
                for episode in season.episodes:
                    if type(episode) == Episode and not episode.movie:
                        # Format episode output name
                        output_name = self.options['download']['episode_format'].format(
                            W=extractor_name,
                            S=content_info.title,
                            s=season.title,
                            E=episode.title,
                            i=episode.id,
                            Sn=season.number,
                            sn=normalize_integer(season.number),
                            En=episode.number,
                            en=normalize_integer(episode.number))
                        # Sanitize filename
                        episode.season_id = f'S{normalize_integer(season.number)}E{normalize_integer(episode.number)}'
                        output_name = sanitize_filename(output_name)
                        # Join all paths
                        output_path = os.path.join(
                            self.options['download']['series_directory'],
                            series_directory,
                            season_directory,
                            output_name
                            )
                    elif type(episode) == Movie or type(episode) == Episode and episode.movie:
                        # Format movie output name
                        output_name = self.options['download']['movie_format'].format(
                            W=extractor_name,
                            E=episode.title,
                            i=episode.id,
                            Y=episode.year)
                        output_name = sanitize_filename(output_name)
                        output_path = os.path.join(
                            self.options['download']['movies_directory'],
                            output_name
                        )
                    episode.output = output_path + '.mkv'
                    download_list.append(episode)
        elif type(content_info) == Movie:
            # Format movie output name
            output_name = self.options['download']['movie_format'].format(
                W=extractor_name,
                E=content_info.title,
                i=content_info.id,
                Y=content_info.year)
            output_name = sanitize_filename(output_name)
            output_path = os.path.join(
                self.options['download']['movies_directory'],
                output_name
            )
            content_info.output = output_path + '.mkv'
            download_list.append(content_info)
        return download_list


    @staticmethod
    def add_id_to_archive(id=str):
        with open(DOWNLOAD_LOG, 'a') as dl:
            dl.write(f'{id}\n')

    @staticmethod
    def id_in_archive(id=str):
        return id in open(DOWNLOAD_LOG, 'r').read()

    '''def write_status_file(self):
        global _STATS
        with open(self.status_file_path, 'w') as status:
            json.dump(_STATS, status)
    '''
    def search(self, extractor=str, search_term=str):
        pass

    def dump_options(self, format=str):
        with open(f'options_dump_{filename_datetime()}.txt', 'a') as z:
            z.write('Polarity (%s) %s' % (__version__, datetime.now()))
            for opt in self.opts_map:
                z.write('\n%s' % opt[0])
                if format == 'json':
                    # JSON
                    z.write(json.dumps(opt[1], indent=4))


class SearchError(Exception):
    pass
