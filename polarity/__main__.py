import argparse
import logging
import re
import os
import sys
from urllib import parse

import pretty_errors

from platform import system, version, python_version
from .Polarity import Polarity
from .extractor import get_extractors
from .paths import logs_dir
from .utils import vprint, load_language, filename_datetime
from .version import __version__

from polarity.config import config

from polarity.downloader import DOWNLOADERS, __DOWNLOADERS__

__usage__ = 'Polarity <url> [OPTIONS]'

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

if '-v' in sys.argv:
    verbose_level = sys.argv[sys.argv.index('-v') + 1]
elif '--verbose' in sys.argv:
    verbose_level = sys.argv[sys.argv.index('--verbose') + 1]
else:
    verbose_level = config['verbose']

def main():
    global parser, args_map, args, opts
    # Set language dictionaries
    lang_help = lang['main']['arguments']['help']
    lang_meta = lang['main']['arguments']['metavar']
    lang_group = lang['main']['arguments']['groups']
    # Set log filename
    log_filename = logs_dir + f'log_{filename_datetime()}.log'
    logging.basicConfig(filename=log_filename, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)
    # Set options defaults
    opts = {'download': {}, 'sync': {}, 'extractor': {}}
    args_map = {}

    # Print Polarity version
    vprint(lang['main']['using_version'] % __version__, 3, 'polarity', 'debug')

    parser = argparse.ArgumentParser(usage=__usage__, description='Polarity %s | https://github.com/Aveeryy/Polarity/' %(__version__), prog='Polarity', add_help=False, formatter_class=FORMATTER)
    parser.add_argument('url', help=argparse.SUPPRESS, nargs='*')
    general = parser.add_argument_group(title=lang_group['general'])
    general.add_argument('-h', '--help', '--ayuda', action='store_true', help=lang_help['help'])
    general.add_argument('--extended-help', help=lang_help['extended_help'], action='store_true')
    general.add_argument('-v', '--verbose', choices=['1', '2', '3', '4', '5'], help=lang_help['verbose'], metavar=lang_meta['verbose'])
    general.add_argument('-m', '--running-mode', choices=['download'], default='download')
    general.add_argument('-e', '--search-extractor', help='no')
    general.add_argument('-s', '--search-term', help=lang_help['search'], metavar='')
    general.add_argument('-d', '--downloader', choices=DOWNLOADERS.keys(), help='Downloader to use')
    general.add_argument('--update-git', action='store_true', help=lang_help['update_git'])
    #general.add_argument('--proxy-list', help=lang_help['proxy'], metavar=lang_meta['proxy'])

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

    for extractor in get_extractors():
        if not hasattr(extractor[1], 'ARGUMENTS'):
            continue
        extractor_name = extractor[0]
        parse_arg_group(extractor[1].ARGUMENTS, opts['extractor'], extractor_name)

    args = parser.parse_args()  # Parse arguments

    # Print help
    if args.help is True or args.extended_help:
        parser.print_help()
        os._exit(0)

    # Process downloader and extractor options
    process_arguments()
    
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
    add_option(args.exit_after_dump, opts, 'exit_after_dump')

    # Launches Polarity
    Polarity(urls=args.url, options=opts, verbose=args.verbose).start()

def add_option(arg, opts_path=dict, opts_entry=str):
    'Adds an argument value to the options dict, if it\'s type isn\'t NoneType'
    if arg not in (None, False):
        opts_path[opts_entry] = arg

def parse_arg_group(group=dict, dest=dict, dest_name=str):
    'Convert an ARGUMENTS object to argparse arguments'
    global args_map
    z = parser.add_argument_group(lang['main']['arguments']['groups']['extractor'] % dest_name)
    dest[dest_name.lower()] = {}
    for arg in group:
        # Add argument to group
        z.add_argument(*arg['args'], **arg['attrib'])
        vprint(lang['main']['added_arg'] % (*arg['args'], dest_name), 4, 'polarity', 'debug')
        # Cure argument name for arg map
        arg_name = re.sub(r'^(--|-)', '', arg['args'][0]).replace('-', '_')
        args_map[arg_name] = (dest_name.lower(), arg['variable'], dest)

def process_arguments():
    'Processes arguments added via an ARGUMENTS object'
    # Get argparse values
    kwargs = args._get_kwargs()
    for tupl in kwargs:
        if tupl[0] in args_map:
            # Skip if argument's value is None or False
            if tupl[1] in (None, False):
                continue
            arg = args_map[tupl[0]]
            arg[2][arg[0]][arg[1]] = tupl[1]


if __name__ == '__main__':
    lang = load_language()
    if '--update-git' in sys.argv:
        from polarity.update import selfupdate
        selfupdate(mode='git')
    # Launch main function and handle 
    try:
        main()
    except KeyboardInterrupt:
        vprint(lang['main']['exit_msg'], 1)
        os._exit(0)
    except Exception as e:
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        exception_filename = logs_dir + f'exception_{filename_datetime()}.log'
        with open(exception_filename, 'w', encoding='utf-8') as log:
            log.write('Polarity version: %s\nOS: %s %s\nPython %s\n' %(
                __version__, system(), version(), python_version()))
        logging.basicConfig(filename=exception_filename, level=logging.ERROR)
        logging.error(e, exc_info=True)
        # Re-raise exception
        raise