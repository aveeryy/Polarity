import argparse
import logging
import os
import re
import sys

import tomli
import tomli_w

from polarity.utils import (dict_merge, filename_datetime, get_argument_value,
                            get_home_path, mkfile, strip_extension, vprint)
from polarity.version import __version__


# Part 0: Functions
class ConfigError(Exception):
    pass


def generate_config(config_path: str) -> None:
    with open(config_path, 'w') as c:
        tomli_w.dump(__defaults, c)


def load_config(config_path: str) -> dict:
    if not config_path:
        # Return default configuration if no config file is used:
        return __defaults
    with open(config_path, 'r', encoding='utf-8') as c:
        try:
            # Load configuration
            config = tomli.loads(c.read())
        except tomli.TOMLDecodeError:
            # TODO: corrupt config handler
            raise Exception
    return config


def save_config(config_path: str, config: dict) -> None:
    with open(config_path, 'wb') as c:
        tomli_w.dump(config, c)


def merge_external_config(obj: object, name: str, config_path: dict) -> None:
    if not hasattr(obj, 'DEFAULTS'):
        pass
    elif name.lower() not in config_path:
        # Downloader configuration not in config file, add it
        config_path[name.lower()] = obj.DEFAULTS
    elif name.lower() in config_path:
        dict_merge(config_path[name.lower()], obj.DEFAULTS)


def change_language(language_code: str) -> dict:
    global lang_code
    __lang_path = f"{paths['lang']}{language_code}.toml"
    if language_code is None:
        dict_merge(lang, __internal_lang)
    elif language_code == 'internal':
        return __internal_lang
    elif not os.path.exists(__lang_path):
        vprint('error: language file not found', error_level='error')
        dict_merge(lang, __internal_lang, True)
    elif os.path.exists(__lang_path):
        lang_code = language_code
        with open(__lang_path, 'r', encoding='utf-8') as l:
            # Change language to internal without modifying the variable
            # Doing this to avoid more languages than the internal one
            # and the currently loaded overlapping
            dict_merge(lang, __internal_lang, True)
            # Now, change
            dict_merge(lang, tomli.load(l), True)
            # Merge internal language with loaded one, avoids errors due
            # missing strings
    return lang


def get_installed_languages() -> list[str]:
    return [strip_extension(f.name) for f in os.scandir(paths['lang'])]


def change_verbose_level(new_level: int, change_print=True, change_log=False):
    global verbose_level
    if new_level not in range(0, 6):
        raise ConfigError('tmp_string: invalid verbose level')
    if change_print:
        verbose_level['print'] = new_level
    if change_log:
        verbose_level['log'] = new_level


def change_paths(new_paths: dict):
    global paths
    for entry, path in new_paths.items():
        paths[entry] = path


def change_options(new_options: dict):
    global options
    dict_merge(options, new_options, True)


class ConfigError(Exception):
    def __init__(self, msg: str = 'Failed to load configuration') -> None:
        super().__init__(msg)


# Part 1: Define default configurations

# Base path for configuration files
__main_path = f'{get_home_path()}/.Polarity/'
# Default base path for downloads
__download_path = f'{get_home_path()}/Polarity Downloads/'

# Default paths
paths = {
    k: __main_path + v
    for k, v in {
        'account': 'Accounts/',
        'bin': 'Binaries/',
        'cfg': 'config.toml',
        'dl_log': 'download.log',
        'dump': 'Dumps/',
        'lang': 'Languages/',
        'log': 'Logs/',
        'sync_list': 'sync.json',
        'tmp': 'Temp/'
    }.items()
}

# Default config values
__defaults = {
    # Verbosity level
    # Does not affect logs
    'verbose': 1,
    # Log verbosity level
    # This must be 4 to report an issue
    'verbose_logs': 4,
    # Language file to use
    # Leave empty to use internal language
    # 'internal' also works
    'language': 'internal',
    # Check for updates on start-up
    # This does not automatically update Polarity
    'check_for_updates': False,
    # Automatically update language files
    'auto_update_languages': False,
    # Download options
    'download': {
        # Maximum active downloads
        'active_downloads': 5,
        # Output directory for series
        'series_directory': f'{__download_path}{"Series/"}'.replace("\\", "/"),
        # Output directory for movies
        'movies_directory': f'{__download_path}{"Movies/"}'.replace("\\", "/"),
        # Path formatting for series directories
        # Default format: Extractor/Title (Year)
        'series_format': '{W}/{S} ({y})',
        # Path formatting for season directories
        # Default format: Season 1 - Season identifier
        'season_format': 'Season {Sn} - {i}',
        # Filename formatting for episodes
        # Default format: Title S01E01 - Episode title
        'episode_format': '{S} S{sn}E{en} - {E}',
        # Filename formatting for movies
        # Default format: Movie title (Year)
        'movie_format': '{E} ({Y})',
        # Desired video resolution, number must be height
        # If resolution is not available, gets the closest value
        'resolution': 4320,
        # Allow downloading previously downloaded episodes
        'redownload': False,
        # Extension for video extractor downloads
        'video_extension': '.mkv',
        # Extension for audio extractor downloads
        'audio_extension': 'auto'
    },
    # Extractor options
    'extractor': {
        'active_extractions': 5,
    },
    'search': {
        # Absolute maximum for results
        'max_results': 100,
        # Maximum results per extractor
        'max_results_per_extractor': 100,
        # Maximum results per
        'max_results_per_type': 100,
        # Format for results
        # Default format: Title (Polarity content ID [extractor/type-id])
        # Default example: Pokémon (atresplayer/series-000000)
        # Available format codes:
        # https://github.com/aveeryy/Polarity/tree/main/polarity/docs/format.md
        'result_format': '\033[1m{n}\033[0m ({I})'
    },
    'flags': []
}

# Predefine configuration variables
lang = {}
verbose_level = {'print': 1, 'log': 4}

# Integrated language
# Uses very simple english words, and does not require installation
# so pretty much failure-proof, for example, if language files have not been
# updated it takes missing strings from here.

__internal_lang = {
    # Language metadata
    'name': 'Polarity Internal language',
    'code': 'internal',
    'author': 'aveeryy',
    'main': {
        'exit_msg': 'exiting'
    },
    # Argument string group
    'args': {
        'added_arg': 'added: arg "%s" from %s',
        # Argument groups string sub-group
        'groups': {
            'general': 'general options',
            'download': 'download options',
            'extractor': '%s options',
            'debug': 'debug options',
            'search': 'search options'
        },
        # Argument help string sub-group
        'help': {
            'accounts_dir': 'custom directory for account files',
            'binaries_dir': 'custom directory with ffmpeg binaries',
            'config_file': 'custom configuration file path',
            'language_dir': 'custom directory for language files',
            'log_dir': 'custom directory for logs',
            'log_file': 'custom download log file path',
            'temp_dir': 'custom directory for temporary files',
            'download_dir_series': 'download dir for tv series',
            'download_dir_movies': 'download dir for movies',
            'dump': 'dump information to a file',
            'exit_after_dump': 'exit after dumping information',
            'extended_help': "shows help with argument options",
            'install_languages': 'install specified languages',
            'installed_languages': 'list installed languages',
            'filters': 'extraction and download filters',
            'format_episode': "formatting for episodes' filenames",
            'format_movie': "formatting for movies' filenames",
            'format_season': "formatting for seasons' directories",
            'format_series': "formatting for tv series' directories",
            'help': 'shows help',
            'language': 'identifier of the language to load',
            'max_results': 'maximum number of results',
            'max_results_per_extractor':
            'maximum number of results per extractor',
            'max_results_per_type': 'maximum number of results per media type',
            # TODO: better 'mode' string
            'mode': 'execution mode',
            'redownload': 'allow episode redownload',
            'resolution': 'preferred resolution',
            'search': 'search content in extractors',
            'update': 'update to latest release',
            'update_check': 'check for updates on startup',
            'update_git': 'update to latest git commit',
            'update_languages': 'update installed language files',
            'url': 'input urls',
            'verbose': 'verbose level',
            'verbose_log': 'verbose level for logging',
            'version': 'print polarity\'s version'
        },
    },
    'polarity': {
        'all_tasks_finished': 'finished',
        'available_languages': 'available languages:',
        'changed_index': 'changed index: %s',
        'created_filter':
        'created: %s object with params "%s" and filter "%s"',
        'dump_options': 'dumping: options',
        'enabled_debug': 'enabled debug mode',
        'finished_download': 'finished: download tasks',
        'finished_extraction': 'finished: extraction tasks',
        'language_format': '%s (%s) by %s',
        'use_help': 'use --help to display all options',
        'use': 'usage: ',
        'requesting': 'requesting %s',
        'search_no_results': 'no results from search %s',
        'search_term': 'term: ',
        'unknown_channel': 'unknown channel',
        'update_available': 'version %s available',
        'usage': 'Polarity <url(s)> [OPTIONS]',
        'using_version': 'using ver. %s',
        'except': {
            'verbose_error': 'invalid verbose level: %s'
        }
    },
    'singularity': {
        'extracting_keys': 'extracting: keys',
        'using_version': 'using ver: %s'
    },
    'dl': {
        'cannot_download_content': '%s "%s" can\'t be downloaded: %s',
        'content_id': 'content id',
        'download_successful': 'downloaded: %s "%s"',
        'downloading_content': 'downloading: %s "%s"',
        'no_extractor': 'skipping: %s "%s". no extractor',
        'no_redownload': 'skipping: %s already downloaded',
        'url': 'url'
    },
    'penguin': {
        'doing_binary_concat': 'binary concat: track %s of %s',
        'doing_decryption': 'decrypting: track %s of %s with key "%s"',
        'debug_already_downloaded': 'skipping segment: %s',
        'debug_time_download': 'segment download took: %s',
        'debug_time_remux': 'remux took: %s',
        'incompatible_stream': 'incompatible stream: %s',
        # Output file
        'output_file_broken': 'failed to load output data file, recreating',
        # Resume file
        'resume_file_backup_broken':
        'error: failed to load backup of resume data, recreating',
        'resume_file_broken':
        'error: failed to load resume data file, using backup',
        'resume_file_recreation': 'recreating: resume data',
        'resuming': 'resuming: %s...',
        'segment_downloaded': 'downloaded: segment %s',
        'segment_retry': 'failed: segment %s download',
        'segment_skip': 'skipping: segment %s',
        'segment_start': 'start: download of segment %s',
        'thread_started': 'start: downloader "%s"',
        'threads_started': 'start: %d download threads',
        'args': {
            'ffmpeg_codec': 'Postprocessing codification settings',
            'segment_downloaders': 'number of threads per download'
        },
        'protocols': {
            'getting_playlist': 'parsing: playlist',
            'getting_stream': 'parsing: streams',
            'multiple_video_bitrates':
            'multiple stream with same resolution detected',
            'picking_best_stream_0':
            'picking: video stream with highest resolution',
            'picking_best_stream_1':
            'picking: video stream with highest bitrate',
            'picking_best_stream_2': 'picking: audio stream',
            'selected_stream': 'stream: %s'
        }
    },
    'extractor': {
        'base': {
            'check_failed':
            'failed: check for feature \033[1m%s\033[0m, conditions are false: %s',
            'email_prompt': 'email/username: ',
            'password_prompt': 'password: ',
            'using_filters': 'using filters, total count will be inaccurate',
            'except': {
                'argument_variable_empty': 'variable argument is empty',
                'failed_load_cookiejar': 'failed to load cookiejar: %s',
                'no_cookiejar': 'extractor has no cookiejar'
            }
        },
        'check': {
            'features': {
                'base': 'base_functionality',
                'login': 'login',
                'search': 'search',
                'livetv': 'live_tv'
            },
            'invalid_extractor': 'extractor %s is invalid'
        },
        'filter_check_fail': 'didn\'t pass filter check',
        'generic_error': 'error, error msg: ',
        'get_all_seasons': 'getting info: seasons',
        'get_media_info': 'getting info: %s "%s" (%s)',
        'login_expired': 'login expired, cleaning cookiejar',
        'login_failure': 'failed to login, error code: %s',
        'login_loggedas': 'logged in as: %s',
        'login_success': 'login successful',
        'search_no_results': 'no results: category %s with term %s',
        'skip_dl_premium': 'premium content, or not in your region',
        'waiting_for_login': 'waiting for login',
        'except': {
            'cannot_identify_url': 'failed to identify URL',
            'no_id': 'no id inputted',
            'no_url': 'no url inputted'
        }
    },
    'types': {
        'series': 'series',
        'season': 'season',
        'episode': 'episode',
        'movie': 'movie',
        'alt': {
            'series': 'series',
            'season': 'season',
            'episode': 'episode',
            'movie': 'movie'
        }
    },
    'update': {
        'downloading_git': 'updating from git repo\'s branch %s',
        'downloading_release': 'updating to latest release',
        'downloading_native': 'downloading latest native',
        'new_release': 'new release (%s) available',
        'except': {
            'unsupported_native': 'native binary update is not supported yet'
        }
    },
    'atresplayer': {
        'no_content_in_season': 'no episodes in %s (%s)',
        'except': {
            'invalid_codec': 'invalid codec'
        },
        'args': {
            'codec': 'codec preferance'
        }
    },
    'crunchyroll': {
        'bearer_fetch': 'fetching: bearer token',
        'bearer_fetch_fail': 'failed: bearer token fetch',
        'cms_fetch': 'fetching: cms policies',
        'cms_fetch_success': 'success: cms policies fetch',
        'cms_fetch_fail': 'failed: cms policies fetch',
        'unwanted_season': 'skip: season "%s", unwanted dub',
        'using_method': 'login method "%s"',
        'args': {
            'subs': 'subt languages',
            'dubs': 'dub languages',
            'meta': 'metadata language',
            'hard': 'get a hardsubbed version',
            'email': "account email",
            'pass': "account password",
            'region': 'change content region',
        }
    }
}

lang = __internal_lang

# Part 2: Load options from configuration file (and some arguments)

__path_arguments = {
    '--accounts-directory': 'account',
    '--binaries-directory': 'bin',
    '--config-file': 'cfg',
    '--download-log-file': 'dl_log',
    '--language-directory': 'lang',
    '--log-directory': 'log',
    '--temp-directory': 'tmp'
}

# Set new paths from user arguments
for arg, path_name in __path_arguments.items():
    if arg in sys.argv:
        _value = sys.argv[sys.argv.index(arg) + 1]
        paths[path_name] = _value
        # Create the directory if it does not exist
        if 'directory' in arg:
            os.makedirs(_value, exist_ok=True)

# If config file is specified and does not exist, create it
if paths['cfg'] and not os.path.exists(paths['cfg']):
    generate_config(paths['cfg'])

# Load configuration from file
config = load_config(paths['cfg'])

from polarity.downloader import DOWNLOADERS
from polarity.extractor import EXTRACTORS

# Load new configuration entries
dict_merge(config, __defaults)
# Load new configuration entries from extractors and downloaders
for name, downloader in DOWNLOADERS.items():
    merge_external_config(downloader, name, config['download'])
for name, extractor in EXTRACTORS.items():
    merge_external_config(extractor, name, config['extractor'])
# Save the configuration with the new entries to the file
save_config(paths['cfg'], config)

# Create the download log file
mkfile(paths['dl_log'], '')

# Load language file if specified
if '--language' in sys.argv:
    lang_code = sys.argv[sys.argv.index('--language') + 1]
elif config['language'] not in ('', 'internal', 'integrated'):
    lang_code = config['language']
else:
    lang_code = None

lang = change_language(language_code=lang_code)

USAGE = lang['polarity']['usage']

# Set printing verbosity level
if any(a in sys.argv
       for a in ('--mode', '-m')) and any(a in sys.argv
                                          for a in ('print', 'livetv')):
    # Mode is set to one designed to output a parsable string
    # This is forced to 0 to avoid any status msg breaking any script
    verbose_level['print'] = 0
elif any(a in sys.argv for a in ('-q', '--quiet')):
    # Quiet parameter passed,
    verbose_level['print'] = 0
elif any(a in sys.argv for a in ('-v', '--verbose')):
    if 'shtab' not in sys.argv[0]:
        value = get_argument_value(('-v', '--verbose'))
        if value is None or int(value) not in [*range(0, 6)]:
            raise ConfigError(lang['polarity']['except']['verbose_error'] %
                              value)
        verbose_level['print'] = int(value)
elif 'verbose' in config:
    verbose_level['print'] = int(config['verbose'])

# Set logging verbosity level
if '--log-verbose' in sys.argv:
    log_value = get_argument_value('--log-verbose')
    # Check if value is valid
    if log_value is None or int(log_value) not in [*range(0, 6)]:
        raise ConfigError(lang['polarity']['except']['verbose_error'] %
                          log_value)
    verbose_level['log'] = int(log_value)
elif 'verbose_logs' in config:
    verbose_level['log'] = config['verbose_logs']

# Part 3: Load options from the rest of command line arguments


# Argument parsing
class HelpFormatter(argparse.HelpFormatter):
    class _Section(object):
        def __init__(self, formatter, parent, heading=None):
            self.formatter = formatter
            self.parent = parent
            self.heading = heading
            self.items = []

        def format_help(self):
            # format the indented section
            if self.parent is not None:
                self.formatter._indent()
            join = self.formatter._join_parts
            item_help = join([func(*args) for func, args in self.items])
            if self.parent is not None:
                self.formatter._dedent()

            # return nothing if the section was empty
            if not item_help:
                return ''

            # add the heading if the section was non-empty
            if self.heading != '==SUPRESS==' and self.heading is not None:
                current_indent = self.formatter._current_indent
                heading = '%*s%s\n%s\n' % (
                    current_indent + 1,
                    '',
                    # Bold header
                    f'\033[1m{self.heading}\033[0m',
                    # Underline
                    '\u2500' * (len(self.heading) + 2))
            else:
                heading = ''

            # join the section-initial newline, the heading and the help
            return join(['\n', heading, item_help, '\n'])

    def _format_usage(self, usage, actions, groups, prefix: str) -> str:
        # Change the usage text to the language provided one
        prefix = f"\033[1m{lang['polarity']['use']}\033[0m"
        return super()._format_usage(usage, actions, groups, prefix)

    def _format_text(self, text: str) -> str:
        # Make the text below the usage string bold
        return super()._format_text(f'\033[1m{text}\033[0m')

    def _format_action_invocation(self, action):
        return ', '.join(action.option_strings)


class ExtendedFormatter(HelpFormatter):
    def _format_args(self, action, default_metavar):
        get_metavar = self._metavar_formatter(action, default_metavar)
        if action.nargs is None:
            result = '%s' % get_metavar(1)
        elif action.nargs == argparse.OPTIONAL:
            result = '[%s]' % get_metavar(1)
        elif action.nargs == argparse.ZERO_OR_MORE:
            metavar = get_metavar(1)
            result = '[%s ...]' % metavar
        elif action.nargs == argparse.ONE_OR_MORE:
            result = '%s ...' % get_metavar(1)
        elif action.nargs == argparse.REMAINDER:
            result = '...'
        elif action.nargs == argparse.PARSER:
            result = '%s ...' % get_metavar(1)
        elif action.nargs == argparse.SUPPRESS:
            result = ''
        else:
            try:
                formats = ['%s' for _ in range(action.nargs)]
            except TypeError:
                raise ValueError("invalid nargs value") from None
            result = ' '.join(formats) % get_metavar(action.nargs)
        return result

    def _metavar_formatter(self, action, default_metavar):
        if action.metavar is not None:
            result = action.metavar
        if action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            result = '(%s)' % ','.join(choice_strs)
        else:
            result = ''

        def format(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result, ) * tuple_size

        return format

    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ', '.join(action.option_strings) + ' ' + args_string


# Set preferred help formatter
__FORMATTER = HelpFormatter if '--extended-help' not in sys.argv else ExtendedFormatter


def argument_parser(get_parser=False) -> dict:
    def parse_external_args(args: dict, dest: dict, dest_name: str) -> None:
        'Convert an ARGUMENTS object to argparse arguments'
        group_name = lang['args']['groups']['extractor'] % dest_name
        # Create an argument group for the argument
        z = parser.add_argument_group(title=group_name)
        _external_arg_groups.append(group_name)
        dest[dest_name.lower()] = {}
        for arg in args:
            # Add argument to group
            z.add_argument(*arg['args'], **arg['attrib'])
            vprint(lang['args']['added_arg'] % (*arg['args'], dest_name), 4,
                   'polarity', 'debug')
            # Add argument to map, to later put it in it's respective
            # config entry
            arg_name = re.sub(r'^(--|-)', '', arg['args'][0]).replace('-', '_')
            args_map[arg_name] = (dest, dest_name.lower(), arg['variable'])

    def process_args() -> None:
        'Add argument values to their respective config entries'
        for group in parser._action_groups:
            _active_dict = opts
            # Skip external groups
            if group.title in _external_arg_groups:
                continue
            elif group.title == lang_group['download']:
                # Change active options dict to download
                _active_dict = opts['download']
            elif group.title == lang_group['search']:
                _active_dict = opts['search']
            for entry in group._group_actions:
                # Get argument value
                _value = getattr(args, entry.dest)
                if type(_value) is str and _value.isdigit():
                    _value = int(_value)
                if _value or entry.dest not in _active_dict:
                    _active_dict[entry.dest] = _value

        # Process external arguments
        _process_external_args()

    def _process_external_args() -> None:
        'Processes arguments added via an ARGUMENTS iterable'
        # Get argparse values
        kwargs = args._get_kwargs()
        for tupl in kwargs:
            if tupl[0] in args_map:
                # Skip if value is None or False
                if tupl[1] in (None, False):
                    continue
                arg = args_map[tupl[0]]
                # arg[0] = Destination in options dict
                # arg[1] = Entry in destination
                # arg[2] = Variable in entry
                # tupl[1] = Value
                arg[0][arg[1]][arg[2]] = tupl[1]

    _external_arg_groups = []

    # Set language dictionaries
    lang_help = lang['args']['help']
    lang_group = lang['args']['groups']

    # Set logging filename and configuration
    log_filename = paths['log'] + f'log_{filename_datetime()}.log'
    logging.basicConfig(filename=log_filename,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)
    # Set options' base dictionaries
    opts = {'download': {}, 'search': {}, 'extractor': {}}
    args_map = {}

    from polarity.downloader import DOWNLOADERS

    parser = argparse.ArgumentParser(
        usage=USAGE,
        description='Polarity %s | https://github.com/aveeryy/Polarity/' %
        (__version__),
        prog='Polarity',
        add_help=False,
        formatter_class=__FORMATTER)

    general = parser.add_argument_group(title=lang_group['general'])

    parser.add_argument('url', help=argparse.SUPPRESS, nargs='*')
    # Windows install finisher
    parser.add_argument('--windows-setup',
                        help=argparse.SUPPRESS,
                        action='store_true')

    general.add_argument('-h',
                         '--help',
                         action='store_true',
                         help=lang_help['help'])
    general.add_argument('--extended-help',
                         help=lang_help['extended_help'],
                         action='store_true')
    general.add_argument('-V',
                         '--version',
                         action='store_true',
                         dest='print_version',
                         help=lang_help['version'])
    # Verbose options
    general.add_argument('-v',
                         '--verbose',
                         choices=['0', '1', '2', '3', '4', '5'],
                         help=lang_help['verbose'])
    general.add_argument('--log-verbose',
                         choices=['0', '1', '2', '3', '4', '5'],
                         help=lang_help['verbose_log'])
    general.add_argument('-m',
                         '--mode',
                         choices=['download', 'search', 'print', 'livetv'],
                         default='download',
                         help=lang_help['mode'])
    general.add_argument('--language', help=lang_help['language'])
    general.add_argument('--installed-languages',
                         action='store_true',
                         help=lang_help['installed_languages'])
    general.add_argument('--install-languages',
                         nargs='*',
                         help=lang_help['install_languages'])
    general.add_argument('--update-languages',
                         action='store_true',
                         help=lang_help['update_languages'])
    general.add_argument('--update',
                         action='store_true',
                         help=lang_help['update'])
    general.add_argument('--update-git',
                         action='store_true',
                         help=lang_help['update_git'])
    general.add_argument('--check-for-updates',
                         action='store_true',
                         help=lang_help['update_check'])
    general.add_argument('--filters', help=lang_help['filters'])
    general.add_argument('--accounts-directory',
                         help=lang_help['accounts_dir'])
    general.add_argument('--binaries-directory',
                         help=lang_help['binaries_dir'])
    general.add_argument('--config-file', help=lang_help['config_file'])
    general.add_argument('--download-log-file', help=lang_help['log_file'])
    general.add_argument('--language-directory',
                         help=lang_help['language_dir'])
    general.add_argument('--log-directory', help=lang_help['log_dir'])
    general.add_argument('--temp-directory', help=lang_help['temp_dir'])

    # Search options
    search = parser.add_argument_group(title=lang_group['search'])
    search.add_argument('--max-results',
                        type=int,
                        help=lang_help['max_results'])
    search.add_argument('--max-results-per-extractor',
                        type=int,
                        help=lang_help['max_results_per_extractor'])
    search.add_argument('--max-results-per-type',
                        type=int,
                        help=lang_help['max_results_per_type'])

    download = parser.add_argument_group(title=lang_group['download'])
    # Downloader options
    download.add_argument('-r',
                          '--resolution',
                          type=int,
                          help=lang_help['resolution'])
    download.add_argument('-R',
                          '--redownload',
                          action='store_true',
                          help=lang_help['redownload'])
    download.add_argument('--series-directory',
                          help=lang_help['download_dir_series'])
    download.add_argument('--movies-directory',
                          help=lang_help['download_dir_movies'])
    download.add_argument('--series-format', help=lang_help['format_series'])
    download.add_argument('--season-format', help=lang_help['format_season'])
    download.add_argument('--episode-format', help=lang_help['format_episode'])
    download.add_argument('--movie-format', help=lang_help['format_movie'])
    # Gets all extractors with an ARGUMENTS object and converts their arguments to
    # argparse equivalents.
    for downloader in DOWNLOADERS.items():
        if not hasattr(downloader[1], 'ARGUMENTS'):
            continue
        downloader_name = downloader[0]
        parse_external_args(downloader[1].ARGUMENTS, opts['download'],
                            downloader_name)
    debug = parser.add_argument_group(title=lang_group['debug'])
    debug.add_argument('--dump',
                       choices=['options'],
                       nargs='+',
                       help=lang_help['dump'])
    debug.add_argument('--exit-after-dump',
                       action='store_true',
                       help=lang_help['exit_after_dump'])
    # debug.add_argument('--list-tv-channels', action='store_true')
    debug.add_argument('--debug-colors', action='store_true')

    # Add extractor arguments
    for name, extractor in EXTRACTORS.items():
        if not hasattr(extractor, 'ARGUMENTS'):
            continue
        parse_external_args(extractor.ARGUMENTS, opts['extractor'], name)

    if get_parser:
        return parser

    args = parser.parse_args()  # Parse arguments

    # Print help
    if args.help is True or args.extended_help:
        parser.print_help()
        os._exit(0)

    # Add argument values to options
    process_args()

    options = dict_merge(config, opts, overwrite=True, modify=False)

    # See if list / debug mode needs to be set
    if any(s in sys.argv for s in ('--debug-colors', '--a')):
        vprint(lang['polarity']['enabled_debug'], error_level='debug')
        change_verbose_level(0, True, True)
        options['mode'] = 'debug'

    return (args.url, options)


def get_parser():
    return argument_parser(get_parser=True)


# Parse arguments
if 'shtab' not in sys.argv[0]:
    urls, options = argument_parser()
else:
    urls = options = None