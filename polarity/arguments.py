import argparse
import logging
import os
import re
import sys

from polarity.config import config, lang, USAGE
from polarity.paths import LOGS
from polarity.utils import filename_datetime, recurse_merge_dict, vprint
from polarity.version import __version__ as _version

# Argument parsing
class MinimalHelpFormatter(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        return ', '.join(action.option_strings)

class ExtendedHelpFormatter(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ', '.join(action.option_strings) + ' ' + args_string

FORMATTER = MinimalHelpFormatter if '--extended-help' not in sys.argv else ExtendedHelpFormatter

def argument_parser():
    global options

    def add_option(arg, opts_path: dict, opts_entry: str):
        'Adds an argument value to the options dict, if it\'s type isn\'t NoneType'
        if arg not in (None, False):
            opts_path[opts_entry] = arg

    def parse_arg_group(group: dict, dest: dict, dest_name: str):
        'Convert an ARGUMENTS object to argparse arguments'
        z = parser.add_argument_group(lang['args']['groups']['extractor'] % dest_name)
        dest[dest_name.lower()] = {}
        for arg in group:
            # Add argument to group
            z.add_argument(*arg['args'], **arg['attrib'])
            vprint(lang['args']['added_arg'] % (*arg['args'], dest_name), 4, 'polarity', 'debug')
            # Cure argument name for arg map
            arg_name = re.sub(r'^(--|-)', '', arg['args'][0]).replace('-', '_')
            args_map[arg_name] = (dest_name.lower(), arg['variable'], dest)

    def process_arguments():
        'Processes arguments added via an ARGUMENTS iterable'
        # Get argparse values
        kwargs = args._get_kwargs()
        for tupl in kwargs:
            if tupl[0] in args_map:
                # Skip if argument's value is None or False
                if tupl[1] in (None, False):
                    continue
                arg = args_map[tupl[0]]
                arg[2][arg[0]][arg[1]] = tupl[1]
            
    # Set language dictionaries
    lang_help = lang['args']['help']
    lang_meta = lang['args']['metavar']
    lang_group = lang['args']['groups']
    # Set logging filename and configuration
    log_filename = LOGS + f'log_{filename_datetime()}.log'
    logging.basicConfig(filename=log_filename, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)
    # Set options' base dictionaries
    opts = {'download': {}, 'sync': {}, 'extractor': {}}
    args_map = {}

    from polarity.downloader import DOWNLOADERS, __DOWNLOADERS__

    # Print Polarity version
    vprint(lang['polarity']['using_version'] % _version, 3, 'polarity', 'debug')

    parser = argparse.ArgumentParser(usage=USAGE, description='Polarity %s | https://github.com/Aveeryy/Polarity/' %(_version), prog='Polarity', add_help=False, formatter_class=FORMATTER)
    parser.add_argument('url', help=argparse.SUPPRESS, nargs='*')
    # Windows install finisher
    parser.add_argument('--install-windows', help=argparse.SUPPRESS, action='store_true')
    
    general = parser.add_argument_group(title=lang_group['general'])
    general.add_argument('-h', '--help', '--ayuda', action='store_true', help=lang_help['help'])
    general.add_argument('--extended-help', help=lang_help['extended_help'], action='store_true')
    general.add_argument('-v', '--verbose', choices=['0', '1', '2', '3', '4', '5'], help=lang_help['verbose'], metavar=lang_meta['verbose'])
    general.add_argument('-m', '--running-mode', '--mode', choices=['download', 'search', 'print', 'live_tv'], default='download')
    general.add_argument('-e', '--search-extractor', help='')
    general.add_argument('--search-strip-names')
    general.add_argument('--language', help='')
    general.add_argument('--list-languages', action='store_true')
    general.add_argument('--installed-languages', action='store_true')
    general.add_argument('--install-languages', nargs='*')
    general.add_argument('--update-git', action='store_true', help=lang_help['update_git'])
    general.add_argument('--printer', nargs='*')

    # Downloader options
    download = parser.add_argument_group(title=lang_group['download'])
    download.add_argument('-r', '--resolution', type=int, help=lang_help['resolution'])
    download.add_argument('--redownload', action='store_true', help=lang_help['redownload'])
    download.add_argument('--series-dir', help=lang_help['download_dir_series'])
    download.add_argument('--movies-dir', help=lang_help['download_dir_movies'])
    download.add_argument('--series-format', help=lang_help['format_series'])
    download.add_argument('--season-format', help=lang_help['format_season'])
    download.add_argument('--episode-format', help=lang_help['format_episode'])
    download.add_argument('--movie-format', help=lang_help['format_movie'])
    download.add_argument('-d', '--downloader', choices=DOWNLOADERS.keys(), help='Downloader to use')

    # Download rules
    download_rules = parser.add_argument_group(title='')
    download_rules.add_argument('--download-filter', action='append', nargs='+')
    download_rules.add_argument('--download-matching', action='append', nargs='+')
    download_rules.add_argument('--download-non-matching', action='append', nargs='+')

    # Gets all extractors with an ARGUMENTS object and converts their arguments to
    # argparse equivalents.
    for downloader in __DOWNLOADERS__.items():
        if not hasattr(downloader[1], 'ARGUMENTS'):
            continue
        downloader_name = downloader[0]
        parse_arg_group(downloader[1].ARGUMENTS, opts['download'], downloader_name)

    debug = parser.add_argument_group(title=lang_group['debug'])
    debug.add_argument('--dump', choices=['options', 'urls'], nargs='*', help='Dump to file')
    debug.add_argument('--exit-after-dump', action='store_true', help='Exit after a dump')

    from polarity.extractor import EXTRACTORS
    for extractor in EXTRACTORS.values():
        if not hasattr(extractor[1], 'ARGUMENTS'):
            continue
        extractor_name = extractor[0]
        parse_arg_group(extractor[1].ARGUMENTS, opts['extractor'], extractor_name)

    args = parser.parse_args()  # Parse arguments

    # Print help
    if args.help is True or args.extended_help:
        parser.print_help()
        os._exit(0)
    
    # Assign arguments' values to variables
    add_option(args.verbose, opts, 'verbose')
    add_option(args.resolution, opts['download'], 'resolution')
    add_option(args.redownload, opts['download'], 'redownload')
    add_option(args.downloader, opts['download'], 'downloader')
    add_option(args.series_dir, opts['download'], 'series_directory')
    add_option(args.movies_dir, opts['download'], 'movies_directory')
    add_option(args.series_format, opts['download'], 'series_format')
    add_option(args.season_format, opts['download'], 'season_format')
    add_option(args.episode_format, opts['download'], 'episode_format')
    add_option(args.movie_format, opts['download'], 'movie_format')
    add_option(args.series_format, opts['download'], 'series_format')
    add_option(args.dump, opts, 'dump')
    add_option(args.running_mode, opts, 'mode')
    add_option(args.search_extractor, opts, 'search_extractor')
    add_option(args.search_strip_names, opts, 'search_max_length')
    add_option(args.exit_after_dump, opts, 'exit_after_dump')
    add_option(args.install_windows, opts, 'install_windows')
    add_option(args.installed_languages, opts, 'installed_languages')
    add_option(args.list_languages, opts, 'list_languages')
    add_option(args.install_languages, opts, 'install_languages')
    add_option(args.printer, opts, 'printer')
    # Process downloader and extractor options
    process_arguments()
    
    options = recurse_merge_dict(config, opts)

    return (args.url, options)