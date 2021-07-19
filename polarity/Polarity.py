from copy import deepcopy
from datetime import datetime
from logging import error
from urllib.parse import urlparse
from threading import Thread, current_thread

import json
import re
import os
import toml

from polarity.config import config, ConfigError, verbose_level, USAGE
from polarity.downloader import DOWNLOADERS
from polarity.extractor import get_extractors
from polarity.paths import dl_arch_file
from polarity.utils import filename_datetime, sanitize_filename, sanitized_file_exists, send_android_notification, vprint, load_language, recurse_merge_dict, normalize_integer, urlsjoin
from polarity.version import __version__

_ALL_THREADS = {}
_STATS = {
    'version': __version__,
    'url_queue': None,
    'tasks': {},
    'threads': _ALL_THREADS
    }


class Polarity:
    def __init__(self, urls=list, options=dict):
        self.url_pool = urls
        _STATS['url_queue'] = self.url_pool
        self.lang = load_language()
        if options == dict:
            options = {'mode': {}}
        if verbose_level < 1 or verbose_level > 5:
            raise ConfigError(self.lang['polarity']['exceptions']['verbose_error'] % verbose_level)
        self.options = recurse_merge_dict(config, options)

        if 'dump' in self.options:
            dump_time = filename_datetime()
            if 'options' in self.options['dump']:
                with open(f'dump_options_{dump_time}.json', 'w') as s:
                    json.dump(self.options, s, indent=4)
            if 'urls' in self.options['dump']:
                with open(f'dump_urls_{dump_time}.log', 'a') as s:
                    for uri in urls:
                        s.write(f'{uri}\n')
            if 'exit_after_dump' in self.options:
                os._exit(0)

        if not urls or urls == list:
            print(self.lang['polarity']['use'] + USAGE + '\n')
            print(self.lang['polarity']['no_urls'])
            print(self.lang['polarity']['use_help'])
            os._exit(1)

    def start(self):
        self.mode = 'download'
        if self.mode == 'download':
            # Temporary list
            self.workers = []
            for i in range(self.options['download']['simultaneous_urls']):
                self.workers.append(Thread(target=self.worker))
            for i in self.workers:
                i.start()
            for i in self.workers:
                i.join()
            # vprint('All downloads finished')
        
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
        stats = {
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
                options=self.options['extractor'][name.lower()]
            )
            # Call extractor's extract function
            stats['current_tasks']['extract']['finished'] = True
            return extract_function.extract()
            
        def download_task():
            while True:
                if not download_pool:
                    return
                item = download_pool.pop(0)
                content_extended_id = f'{name.lower()}/{item["type"]}-{item["id"]}'
                # Skip if output file already exists or id in download log
                if self.id_in_archive(content_extended_id) or sanitized_file_exists(item['output']):  
                    if not self.id_in_archive(content_extended_id):
                        self.add_id_to_archive(content_extended_id)
                    if not self.options['download']['redownload']:
                        vprint(
                            message=self.lang['downloader']['no_redownload'] % (
                                self.lang['downloader']['media_types'][item['type']],
                                item['title']),
                            error_level='warning     '
                        )
                        continue

                if 'skip_download' in item:
                    vprint(
                        message=self.lang['downloader']['cannot_download_content'] % (
                            self.lang['downloader']['media_types'][item['type']],
                            item['title'],
                            item['skip_download']),
                        error_level='warning'
                    )
                    continue

                # Set preferred stream as main stream if set else use stream 0
                if 'stream_preferance' in item:
                    stream = item['streams'][item['stream_preferance']]
                else:
                    stream = item['streams'][0]

                # TODO: add external downloader support
                vprint(
                    message=self.lang['downloader']['downloading_content']%(
                        self.lang['downloader']['media_types'][item['type']],
                        item['title']
                        )
                    )
                _downloader = DOWNLOADERS[self.options['download']['downloader']] if self.options['download']['downloader'] in DOWNLOADERS else DOWNLOADERS['penguin']
                try:
                    downloader = _downloader(
                        stream,
                        options=self.options['download'],
                        extra_audio=item['extra_audio'] if 'extra_audio' in item else [],
                        extra_subs=item['extra_subs'] if 'extra_subs' in item else [],
                        name=f"{content_info['title']} {item['season_id']}",
                        #media_metadata=item['metadata'],
                        output=item['output']
                        )
                    downloader.start()

                except KeyboardInterrupt:
                    if os.path.exists(item['output']):
                        os.remove(item['output'])
                    raise

                if item['type'] == 'episode':
                    series_str = f'{content_info["title"]} {item["season_id"]}'
                else:
                    series_str = ''

                download_successful = self.lang['downloader']['download_successful'] % (
                    self.lang['downloader']['media_types'][item['type']],
                    series_str,
                    item['title']) 

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
            stats['current_url'] = thread_url
            extractor_tupl = self.thread_get_compatible_extractor(thread_url)
            # Skip if there's not an extractor available
            if extractor_tupl[0] is None:
                vprint(f'Skipping URL {thread_url}. No extractor available.', error_level='error')
                return
            extractor, name = extractor_tupl
            content_info = info_extract()
            if content_info is None:
                continue
            # Create download and metadata pools
            download_pool = self.build_download_list(name, content_info)
            metadata_pool = deepcopy(download_pool)
            # Create downloader threads
            for i in range(self.options['download']['simultaneous_downloads_per_url']):
                stats['current_tasks']['download'][f'{thread_name}-{i}'] = {
                    'thread': None,
                    'stats': {
                        'downloader': None,
                        'downloader_stats': {}
                        }
                    }
                stats['current_tasks']['download'][f'{thread_name}-{i}']['thread'] = Thread(target=download_task, name=f'{thread_name}-{i}')
            for t in stats['current_tasks']['download'].values():
                t['thread'].start()


    def build_download_list(self, extractor_name=str, content_info=dict):
        'Build a download list out of an extractor output'
        download_list = []
        if content_info['type'] in ('series', ''):
            # Format series output directory
            series_directory = self.options['download']['series_format'].format(
                W=extractor_name,
                S=content_info['title'],
                i=content_info['id'],
                y=content_info['year'])
            # Sanitize series directory
            series_directory = sanitize_filename(series_directory, True)
            for season in content_info['seasons']:
                # Format season output directory
                season_directory = self.options['download']['season_format'].format(
                    W= extractor_name,
                    S=content_info['title'],
                    s=season['title'],
                    i=season['id'],
                    sn=normalize_integer(season['season_number']),
                    Sn=season['season_number'])
                # Sanitize season directory
                season_directory = sanitize_filename(season_directory, True)
                for episode in season['episodes']:
                    if episode['type'] in ('episode', ''):
                        # Format episode output name
                        output_name = self.options['download']['episode_format'].format(
                            W=extractor_name,
                            S=content_info['title'],
                            s=season['title'],
                            E=episode['title'],
                            i=episode['id'],
                            Sn=season['season_number'],
                            sn=normalize_integer(season['season_number']),
                            En=episode['episode_number'],
                            en=normalize_integer(episode['episode_number']))
                        # Sanitize filename
                        episode['season_id'] = f'S{normalize_integer(season["season_number"])}E{normalize_integer(episode["episode_number"])}'
                        output_name = sanitize_filename(output_name) + '.mkv'
                        # Join all paths
                        output_path = urlsjoin(
                            self.options['download']['series_directory'],
                            series_directory,
                            season_directory,
                            output_name
                            )
                    elif episode['type'] == 'movie':
                        # Format movie output name
                        output_name = self.options['download']['movie_format'].format(
                            W=extractor_name,
                            E=episode['title'],
                            i=episode['id'],
                            Y=episode['year'])
                        output_name = sanitize_filename(output_name)
                        output_path = urlsjoin(
                            self.options['download']['movies_directory'],
                            output_name
                        )
                    episode['output'] = output_path
                    download_list.append(episode)
        elif content_info['type'] == 'movie':
            # Format movie output name
            output_name = self.options['download']['movie_format'].format(
                W=extractor_name,
                E=content_info['title'],
                i=content_info['id'],
                Y=content_info['year'])
            output_name = sanitize_filename(output_name)
            output_path = urlsjoin(
                self.options['download']['movies_directory'],
                output_name
            )
            content_info['output'] = output_path
            download_list.append(content_info)
        return download_list

    @staticmethod
    def thread_get_compatible_extractor(url=str):
        'Returns a compatible extractor for the inputted url, if it exists'
        url_host = urlparse(url).netloc
        extractor = [
            extractor
            for extractor in get_extractors()
            if re.match(extractor[2], url_host)
            ]
        if not extractor:
            return(None, None)
        return (extractor[0][1], extractor[0][0])

    @staticmethod
    def add_id_to_archive(id=str):
        with open(dl_arch_file, 'a') as dl:
            dl.write(f'{id}\n')

    @staticmethod
    def id_in_archive(id=str):
        return id in open(dl_arch_file, 'r').read()

    def write_status_file(self):
        global _STATS
        with open(self.status_file_path, 'w') as status:
            json.dump(_STATS, status)

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
