import json
import os
import re
import time
import warnings
from threading import Lock
from typing import Union

from tqdm import TqdmWarning

import polarity.utils
from polarity.config import (USAGE, ConfigError, change_verbose_level, lang,
                             options, paths, verbose_level)
from polarity.types import Episode, Movie, Season, Series
from polarity.types.thread import Thread
from polarity.types.filter import Filter, build_filter
from polarity.types.search import SearchResult
from polarity.update import (check_for_updates, language_install,
                             windows_install)
from polarity.utils import (dict_merge, filename_datetime,
                            get_compatible_extractor, is_content_id,
                            normalize_integer, sanitize_path, thread_vprint,
                            vprint)

# ~TEMP~
from polarity.downloader import PenguinDownloader

warnings.filterwarnings('ignore', category=TqdmWarning)


class Polarity:
    def __init__(self,
                 urls: list,
                 opts: dict = None,
                 _verbose_level: int = None,
                 _logging_level: int = None) -> None:
        '''
        :param _verbose_level: override print verbose lvl
        :param _logging_level: override log verbose lvl
        '''
        self.status = {
            'pool': urls,
            'extraction': {
                'finished': False,
                'tasks': []
            }
        }
        self.status['pool'] = urls
        if opts is not None:
            # Merge user's script options with processed options
            dict_merge(options, opts)
        # Scripting only, override the session verbose level,
        # since verbose level is set before options merge.
        if _verbose_level is not None:
            change_verbose_level(_verbose_level, True)
        if _logging_level is not None:
            change_verbose_level(_logging_level, False, True)
        # Check if verbose level is valid
        if verbose_level['print'] not in range(
                0, 6) or verbose_level['log'] not in range(0, 6):
            raise ConfigError(lang['polarity']['except']['verbose_error'] %
                              verbose_level)

        self.__extract_lock = Lock()
        self.__print_lock = Lock()
        self.download_pool = []

    def start(self):
        # Pre-start functions

        # Windows dependency install
        if options['check_for_updates']:
            if check_for_updates():
                # Import latest server version now, if imported before
                # it'll just be None
                from polarity.update import latest_version_on_server
                vprint(
                    lang['polarity']['update_available'] %
                    latest_version_on_server, 1, 'update')
        if 'install_windows' in options:
            windows_install()
        if 'dump' in options:
            self.dump_information()
        # Language file update
        # if options['auto_update_languages'] or options[
        #        'update_languages']:
        #    language_install(get_installed_languages())

        # Actual start-up
        if options['mode'] == 'download':
            if not self.status['pool']:
                vprint(lang['main']['no_tasks'], level=2, error_level='error')
                print(f"{lang['polarity']['use']}{USAGE}\n")
                print(lang['polarity']['use_help'])
                os._exit(1)
            self.pool = [{
                'url': url,
                'filters': [],
                'reserved': False
            } for url in self.status['pool']]

            workers = []
            _workers = []
            if options['extractor']['active_extractions'] > len(self.pool):
                options['extractor']['active_extractions'] = len(self.pool)
            # Create worker processes
            for _ in range(options['extractor']['active_extractions']):
                w = Thread('Extractor_Worker',
                           target=self._extract_task,
                           daemon=True)
                w.start()
                workers.append(w)
            for _ in range(options['download']['active_downloads']):
                w = Thread('Download_Worker',
                           target=self._download_task,
                           daemon=True)
                w.start()
                _workers.append(w)

            # Wait until workers finish
            while True:
                if not [w for w in workers if w.is_alive()]:
                    self.status['extraction']['finished'] = True
                    if not [w for w in _workers if w.is_alive()]:
                        break
                time.sleep(0.1)
                continue
            vprint(lang['polarity']['all_tasks_finished'])

        if options['mode'] == 'search':
            search_string = ' '.join(self.pool)

    @classmethod
    def search(string: str) -> list[SearchResult]:
        pass

    def dump_information(self) -> None:
        'Dump requested debug information to current directory'
        dump_time = filename_datetime()

        if 'options' in options['dump']:
            vprint('Dumping options to file', 3, error_level='debug')
            with open(f'./{dump_time}_Polarity_dump_options.json',
                      'w',
                      encoding='utf-8') as f:
                json.dump(options, f, indent=4)

        if 'urls' in options['dump']:
            vprint('Dumping URLs to file')
            with open(f'./{dump_time}_Polarity_dump_urls.txt',
                      'w',
                      encoding='utf-8') as f:
                f.write(' \n'.join(self.pool))

        if 'requests' in options['dump']:
            vprint('Enabled dumping of HTTP requests', error_level='debug')
            polarity.utils.dump_requests = True

    @classmethod
    def process_filters(self, filters: str, link=True) -> list[Filter]:
        'Create Filter objects from a string and link them to their respective links'
        filter_list = []
        skip_next_item = False  # If True, skip a item in the loop
        current_index = None  # If None, apply filter to all URLs
        indexed = 0
        url_specifier = r'(global|i(\d)+)'
        filters = re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', filters)
        vprint('Starting filter processing', 4, 'polarity', 'debug')
        for filter in filters:
            if skip_next_item:
                skip_next_item = False
                continue
            specifier = re.match(url_specifier, filter)
            if specifier:
                if specifier.group(1) == 'global':
                    current_index = None
                elif specifier.group(1) != 'global':
                    current_index = int(specifier.group(2))
                vprint(
                    f'Changed index to: {current_index if current_index is not None else "global"}',
                    4, 'polarity', 'debug')
            else:
                _index = filters.index(filter, indexed)
                # Create a Filter object with specified parameters
                # and the next iterator, the actual filter
                raw_filter = filters[_index + 1]
                # Remove quotes
                if raw_filter.startswith('"') and raw_filter.endswith('"'):
                    raw_filter = raw_filter[1:-1]
                _filter, filter_type = build_filter(params=filter,
                                                    filter=raw_filter)
                filter_list.append(_filter)
                vprint(
                    f'Created a {filter_type.__name__} object with params: "{filter}" and filter: "{raw_filter}"',
                    level=4,
                    module_name='polarity',
                    error_level='debug')
                # Append to respective url's filter list
                if link:
                    if current_index is not None:
                        self.pool[current_index]['filters'].append(_filter)
                    elif current_index is None:
                        # If an index is not specified, or filter is in
                        # global group, append to all url's filter lists
                        for url in self.pool:
                            url['filters'].append(_filter)
                # Avoid creating another Filter object with the filter
                # as the parameter
                skip_next_item = True
                indexed += 2
        return filter_list

    def _extract_task(self, ) -> None:
        def take_item() -> Union[dict, None]:
            with self.__extract_lock:
                available = [i for i in self.pool if not i['reserved']]
                if not available:
                    return
                item = available[0]
                self.pool[self.pool.index(item)]['reserved'] = True
            return item

        while True:
            item = take_item()
            if item is None:
                vprint('~TEMP~ extraction tasks finished')
                break
            _extractor = get_compatible_extractor(url=item['url'])
            if _extractor is None:
                vprint(lang['dl']['no_extractor'] %
                       lang['dl']['url'] if not is_content_id(item['url']) else
                       lang['dl']['content_id'])
                continue
            name, extractor = _extractor
            extracted_info = extractor(item['url'], item['filters']).extract()

            if type(extracted_info) is Series:
                while True:
                    episodes = extracted_info.get_all_episodes(pop=True)
                    if not episodes and extracted_info._extracted:
                        # No more episodes to add to download list
                        # and extractor finish, end loop
                        break
                    for episode in episodes:
                        if type(episode) is Episode:
                            media = (extracted_info, episode._parent, episode)
                        elif type(episode) is Movie:
                            media = Episode
                        media_object = self._format_filenames(media, name)
                        self.download_pool.append(media_object)
            elif type(extracted_info) is Movie:
                while not extracted_info._extracted:
                    time.sleep(0.1)
                media_object = self._format_filenames(extracted_info, name)
                self.download_pool.append(media_object)
            print(self.download_pool)

    def _download_task(self) -> None:
        while True:
            if not self.download_pool and self.status['extraction']['finished']:

                break
            elif not self.download_pool:
                time.sleep(1)
                continue
            # Take an item from the download pool
            item = self.download_pool.pop(0)
            if item.skip_download is not None:
                thread_vprint(
                    lang['dl']['cannot_download_content'] %
                    type(item).__name__, item.short_name, item)
            # ~TEMP~ Set the downloader to Penguin
            _downloader = PenguinDownloader

            downloader = _downloader(stream=item.get_preferred_stream(),
                                     short_name=item.short_name,
                                     media_id=item.id,
                                     extra_audio=item.get_extra_audio(),
                                     extra_subs=item.get_extra_subs(),
                                     output=item.output)

            downloader.start()

    @staticmethod
    def _format_filenames(media_obj: Union[tuple[Series, Season, Episode],
                                           Movie],
                          extractor: str) -> Union[Series, Movie]:
        if type(media_obj) is tuple:
            series_dir = options['download']['series_format'].format(
                # Extractor's name
                W=extractor,
                # Series' title
                S=media_obj[0].title,
                # Series' identifier
                i=media_obj[0].id,
                # Series' year
                y=media_obj[0].year)
            season_dir = options['download']['season_format'].format(
                # Extractor's name
                W=extractor,
                # Series' title
                S=media_obj[0].title,
                # Season's title
                s=media_obj[1].title,
                # Season's identifier
                i=media_obj[1].id,
                # Season's number with trailing 0 if < 10
                sn=normalize_integer(media_obj[1].number),
                # Season's number
                Sn=media_obj[1].number)
            output_filename = options['download']['episode_format'].format(
                # Extractor's name
                W=extractor,
                # Series' title
                S=media_obj[0].title,
                # Season's title
                s=media_obj[1].title,
                # Episode's title
                E=media_obj[2].title,
                # Episode's identifier
                i=media_obj[2].id,
                # Season's number with trailing 0 if < 10
                sn=normalize_integer(media_obj[1].number),
                # Season's number
                Sn=media_obj[1].number,
                # Episode's number with trailing 0 if < 10
                en=normalize_integer(media_obj[2].number),
                # Episode's number
                En=media_obj[2].number)
            output_path = os.path.join(options['download']['series_directory'],
                                       series_dir, season_dir, output_filename)
            # Not using f-strings for readibility
            media_obj[2].short_name = '%s S%sE%s' % (
                media_obj[0].title, normalize_integer(media_obj[1].number),
                normalize_integer(media_obj[2].number))
            media_obj[2].output = sanitize_path(output_path)
            return media_obj[2]
        if type(media_obj) is Movie:
            output_filename = options['download']['movie_format'].format(
                # Extractor's name
                W=extractor,
                # Movie's title
                E=media_obj.title,
                # Movie's identifier
                i=media_obj.id,
                # Movie's year
                Y=media_obj.year)
            output_path = os.path.join(options['download']['movie_directory'],
                                       output_filename)
            media_obj.short_name = f'{media_obj.title} ({media_obj.year})'
            media_obj.output = sanitize_path(output_path)
            return media_obj
