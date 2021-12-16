import argparse
import atoml
import logging
import re
import os
import sys

from polarity.utils import filename_datetime, get_argument_value, get_home_path, dict_merge, vprint
from polarity.version import __version__


# Part 0: Functions
class ConfigError(Exception):
    pass


def generate_config(config_path: str) -> None:
    with open(config_path, 'w') as c:
        atoml.dump(__defaults, c)


def load_config(config_path: str) -> dict:
    if not config_path:
        # Return default configuration if no config file is used:
        return __defaults
    with open(config_path, 'r', encoding='utf-8') as c:
        try:
            # Load configuration
            config = atoml.loads(c.read())
        except atoml.exceptions.ATOMLError:
            # TODO: corrupt config handler
            raise Exception
    return config


def save_config(config_path: str, config: dict) -> None:
    with open(config_path, 'w') as c:
        atoml.dump(config, c)


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
    elif not os.path.exists(__lang_path):
        vprint('error!! lang file not found', error_level='error')
        dict_merge(lang, __internal_lang, True)
    elif os.path.exists(__lang_path):
        lang_code = language_code
        with open(__lang_path, 'r', encoding='utf-8') as l:
            # Change language to internal without modifying the variable
            # Doing this to avoid more languages than the internal one
            # and the currently loaded overlapping
            dict_merge(lang, __internal_lang, True)
            # Now, change
            dict_merge(lang, atoml.load(l), True)
            # Merge internal language with loaded one, avoids errors due
            # missing strings
    return lang


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

# Default config values
__defaults = {
    # Verbosity level
    # Does not affect logs
    'verbose': 1,
    # Log verbosity level
    # This must be 4 to report an issue
    # Please for the sake of your hard drive's available space
    # Do NOT put this to 5, there's nothing to avoid you doing it,
    # it's just a personal recommendation lmao
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
        # Number of threads to be used in season extraction
        'season_threads': 3,
        # Number of threads to be used in episode extraction of a season
        # Maximum number of simultaneous episode extractions can be
        # calculated using this formula:
        # active_extractions * season_threads * episode_threads
        # So by default:
        # 3 * 3 * 5 = 45 active threads assuming at least 3 URLs
        'episode_threads': 5,
    },
    'flags': []
}

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

lang = {}

# Create status lists
processes = []
progress_bars = []

verbose_level = {'print': 1, 'log': 4}

# Integrated language
# Uses very simple english words, and does not require installation
# so pretty much failure-proof, for example, if language files have not been
# updated it takes missing strings from here.

__internal_lang = {
    # Language metadata
    'name': 'Polarity Internal language',
    'code': 'internal',
    'author': 'Aveeryy',
    'main': {
        'exit_msg': 'exiting'
    },
    # Argument string group
    'args': {
        'added_arg': 'added arg "%s" from %s',
        # Argument groups string sub-group
        'groups': {
            'general': 'general opts',
            'download': 'download opts',
            'extractor': '%s options',
            'debug': 'debug options'
        },
        # Argument help string sub-group
        'help': {
            'all_extractors': 'Print info from extractors',
            'debug_dump_options': 'Writes options to the debug directory',
            'debug_print_options': 'Prints options, and exits',
            'download_dir_series': 'download dir for tv series',
            'download_dir_movies': 'download dir for movies',
            'extended_help': "show argument options",
            'format_episode': "Formatting for episodes' filenames",
            'format_movie': "Formatting for movies' filenames",
            'format_season': "Formatting for seasons' directories",
            'format_series': "Formatting for tv series' directories",
            'help': 'shows help',
            'redownload': 'Redownload previously downloaded episodes',
            'resolution': 'Preferred video resolution',
            'search': 'search content in extractors',
            'update': 'update to latest release',
            'update_git': 'update to latest git commit',
            'url': 'input urls',
            'verbose': 'verbose level'
        },
        'metavar': {
            'proxy': '<path>',
            'search': '<search term>',
            'verbose': '<level>'
        }
    },
    'polarity': {
        'all_tasks_finished': 'finished',
        'available_languages': 'available languages:',
        'language_format': '%s (%s) by %s',
        'use_help': 'Use --help to display all options',
        'use': 'Usage: ',
        'search_no_results': 'no results from search %s',
        'search_term': 'term: ',
        'update_available': 'version %s available',
        'usage': 'Polarity <url(s)> [OPTIONS]',
        'using_version': 'using ver. %s',
        'except': {
            'verbose_error': 'invalid verbose level: %s'
        }
    },
    'singularity': {
        'extracting_keys': 'extracting keys',
        'using__version__': 'using ver. %s'
    },
    'dl': {
        'cannot_download_content': '%s "%s" can\'t be downloaded: %s',
        'content_id': 'content id',
        'download_successful': 'downloaded: %s "%s"',
        'downloading_content': 'downloading: %s "%s"',
        'fail_to_delete': "failed to delete old file",
        'fail_to_move': "failed to move file to download directory",
        'redownload_enabled': 'deleting old file',
        'no_extractor': 'skipping %s "%s". no extractor',
        'no_redownload': 'skipping %s "%s". already downloaded',
        'url': 'url'
    },
    'penguin': {
        'doing_binary_concat': 'Doing binary segment concat on track %s of %s',
        'doing_decryption': 'Decrypting track %s of %s using key "%s"',
        'debug_already_downloaded': 'Skipping segment %s, already downloaded',
        'debug_time_download': 'Segment download took: %s',
        'debug_time_remux': 'Remux took: %s',
        'resuming': 'resuming %s...',
        'segment_downloaded': 'Successfully downloaded segment %s',
        'segment_retry': 'Download of segment %s failed, retrying...',
        'thread_started': 'Started downloader "%s"',
        'threads_started': 'start: %d download threads',
        'args': {
            'ffmpeg_codec': 'Postprocessing codification settings',
            'retries': 'Number of retries to download a segment',
            'segment_downloaders': 'Number of segment downloaders'
        },
        'protocols': {
            'getting_playlist': 'parsing: playlist',
            'getting_stream': 'parsing: streams',
            'multiple_video_bitrates':
            'Multiple video tracks with same resolution detected',
            'picking_best_stream_0':
            'Picking video stream with best resolution',
            'picking_best_stream_1': 'Picking best video stream',
            'picking_best_stream_2': 'Picking audio stream with best bitrate',
            'selected_stream': 'stream: %s'
        }
    },
    'extractor': {
        'base': {
            'email_prompt': 'Email/Username: ',
            'password_prompt': 'Password: ',
            'except': {
                'argument_variable_empty': 'Variable argument is empty',
            }
        },
        'filter_check_fail': 'did not pass filter check',
        'generic_error': 'error, error msg: ',
        'get_all_seasons': 'getting info: seasons',
        'get_media_info': 'getting info: %s "%s" (%s)',
        'login_failure': 'Failed to log in. error code: %s',
        'login_loggedas': 'Logged in as %s',
        'login_success': 'Login successful',
        'search_no_results': 'No results found on category %s with term %s',
        'waiting_for_login': 'Waiting for login',
        'except': {
            'cannot_identify_url': 'Failed to identify URL'
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
        'downloading_git': 'downloading latest git',
        'downloading_release': 'downloading latest stable',
        'downloading_native': 'downloading latest native',
        'installing_to_path': 'installing to %s',
        'new_release': 'new release (%s) available',
        'successful_install': 'success, exiting in %ds',
        'updating': 'updating...',
        'except': {
            'unsupported_native': 'native binary update is not supported yet'
        }
    },
    'atresplayer': {
        'no_content_in_season': 'no episodes in %s (%s)',
        'except': {
            'invalid_codec': 'Invalid codec set in settings.'
        },
        'args': {
            'codec': 'codec preferance'
        }
    },
    'crunchyroll': {
        'getting_bearer': 'fetching bearer token',
        'getting_cms': 'cms policies fetch success',
        'getting_cms_fail': 'cms policies fetch fail',
        'skip_download_reason': 'premium content, or not in your region',
        'using_method': 'login method "%s"',
        'args': {
            'subs': 'subt languages',
            'dubs': 'dub languages',
            'meta': 'metadata language',
            'hard': 'get a hardsub version',
            'email': "account email",
            'pass': "account password",
            'region': 'change content region',
        }
    }
}

lang = __internal_lang

# Part 2: Load options from configuration file (and some arguments)

# TODO: add arguments to argparse
__path_arguments = {
    '--accounts-directory': 'account',
    '--binaries-directory': 'bin',
    '--config-file': 'cfg',
    '--download-log-file': 'dl_log',
    '--dumps-directory': 'dump',
    '--language-directory': 'lang',
    '--log-directory': 'log',
    '--temp-directory': 'tmp'
}

# Set new paths from user arguments
for arg, path_name in __path_arguments.items():
    if arg in sys.argv:
        _value = sys.argv[sys.argv.index(arg) + 1]
        paths[path_name] = _value
        # Create directories if not existing
        os.makedirs(_value, exist_ok=True)

# If config file is specified and does not exist, create it
if paths['cfg'] and not os.path.exists(paths['cfg']):
    generate_config(paths['cfg'])

# Load configuration from file
config = load_config(paths['cfg'])

from polarity.extractor import EXTRACTORS
from polarity.downloader import DOWNLOADERS

for name, downloader in DOWNLOADERS.items():
    merge_external_config(downloader, name, config['download'])
for name, extractor in EXTRACTORS.items():
    merge_external_config(extractor, name, config['extractor'])

# Add new configuration entries to user's configuration and save to file
dict_merge(config, __defaults)

save_config(paths['cfg'], config)

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
    # This is forced to 0 to avoid any status string breaking any script
    verbose_level['print'] = 0
elif any(a in sys.argv for a in ('-q', '--quiet')):
    # Quiet parameter passed,
    verbose_level['print'] = 0
elif any(a in sys.argv for a in ('-v', '--verbose')):
    value = get_argument_value(('-v', '--verbose'))
    if value is None or int(value) not in [*range(0, 6)]:
        raise ConfigError(lang['polarity']['except']['verbose_error'] % value)
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
    def _format_action_invocation(self, action):
        return ', '.join(action.option_strings)


class ExtendedFormatter(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ', '.join(action.option_strings) + ' ' + args_string


# Set preferred help formatter
__FORMATTER = HelpFormatter if '--extended-help' not in sys.argv else ExtendedFormatter


def argument_parser() -> dict:
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
            for entry in group._group_actions:
                # Get argument value
                _value = getattr(args, entry.dest)
                if type(_value) is str and _value.isdigit():
                    _value = int(_value)
                if _value not in (None, False):
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
    lang_meta = lang['args']['metavar']
    lang_group = lang['args']['groups']
    # Set logging filename and configuration
    log_filename = paths['log'] + f'log_{filename_datetime()}.log'
    logging.basicConfig(filename=log_filename,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        level=logging.DEBUG)
    # Set options' base dictionaries
    opts = {'download': {}, 'sync': {}, 'extractor': {}}
    args_map = {}

    from polarity.downloader import DOWNLOADERS

    parser = argparse.ArgumentParser(
        usage=USAGE,
        description='Polarity %s | https://github.com/Aveeryy/Polarity/' %
        (__version__),
        prog='Polarity',
        add_help=False,
        formatter_class=__FORMATTER)

    general = parser.add_argument_group(title=lang_group['general'])

    parser.add_argument('url', help=argparse.SUPPRESS, nargs='*')
    # Windows install finisher
    parser.add_argument('--install-windows',
                        help=argparse.SUPPRESS,
                        action='store_true')

    general.add_argument('-h',
                         '--help',
                         '--ayuda',
                         action='store_true',
                         help=lang_help['help'])
    general.add_argument('--extended-help',
                         help=lang_help['extended_help'],
                         action='store_true')
    general.add_argument('-V',
                         '--version',
                         action='store_true',
                         help='~TEMP~ print version')
    general.add_argument('-v',
                         '--verbose',
                         choices=['0', '1', '2', '3', '4', '5'],
                         help=lang_help['verbose'],
                         metavar=lang_meta['verbose'])
    general.add_argument('--log-verbose',
                         choices=['0', '1', '2', '3', '4', '5'],
                         help='~TEMP~ logging verbose level')
    general.add_argument('-m',
                         '--mode',
                         choices=['download', 'search', 'print', 'livetv'],
                         default='download')
    general.add_argument('-e', '--search-extractor', help='')
    general.add_argument('--search-strip-names')
    general.add_argument('--language', help='')
    general.add_argument('--list-languages', choices=['local', 'remote'])
    general.add_argument('--install-languages', nargs='*')
    general.add_argument('--update', action='store_true')
    general.add_argument('--update-git',
                         action='store_true',
                         help=lang_help['update_git'])
    general.add_argument('--printer', nargs='*')
    general.add_argument('--filters', help='~TEMP~ download filters')

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
                       choices=['options', 'urls'],
                       nargs='*',
                       help='Dump to file')
    debug.add_argument('--exit-after-dump',
                       action='store_true',
                       help='Exit after a dump')

    # Add extractor arguments
    for name, extractor in EXTRACTORS.items():
        if not hasattr(extractor, 'ARGUMENTS'):
            continue
        parse_external_args(extractor.ARGUMENTS, opts['extractor'], name)

    args = parser.parse_args()  # Parse arguments

    # Print help
    if args.help is True or args.extended_help:
        parser.print_help()
        os._exit(0)

    # Add argument values to options
    process_args()

    options = dict_merge(config, opts, overwrite=True, modify=False)

    return (args.url, options)


# Parse arguments
urls, options = argument_parser()