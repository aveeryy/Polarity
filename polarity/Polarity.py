import json
import os
import re
import time
import warnings

from tqdm import TqdmWarning

import polarity.config
import polarity.utils
from polarity.config import (USAGE, ConfigError, config, lang, options, paths,
                             verbose_level, change_verbose_level)
from polarity.types.filter import Filter, build_filter
from polarity.types.search import SearchResult
from polarity.types.worker import Worker
from polarity.update import language_install, windows_install
from polarity.utils import dict_merge, filename_datetime, vprint

stats = {
    'pool': None,
    'processes': None,
}

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
        stats['pool'] = urls
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

    def start(self):
        # Pre-start functions

        # Windows dependency install
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
            if not stats['pool']:
                vprint(lang['main']['no_tasks'], error_level='error')
                vprint(USAGE, module_name='polarity/usage')
                os._exit(1)
            self.pool = [{'url': url, 'filters': []} for url in stats['pool']]

            workers = []
            # Create worker processes
            for i in range(options['simultaneous_urls']):
                w = Worker(self.pool, worker_id=i)
                workers.append(w)
                w.start()
            # Wait until workers finish
            while [w for w in workers if w.is_alive()]:
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
