import argparse
import logging
import os
import re
import sys

import tomli
import tomli_w

from polarity.lang import internal_lang
from polarity.utils import (
    dict_merge,
    filename_datetime,
    get_argument_value,
    get_home_path,
    mkfile,
    strip_extension,
    vprint,
)
from polarity.version import __version__


# Part 0: Functions
class ConfigError(Exception):
    pass


def generate_config(config_path: str) -> None:
    with open(config_path, "w") as c:
        tomli_w.dump(__defaults, c)


def load_config(config_path: str) -> dict:
    if not config_path:
        # Return default configuration if no config file is used:
        return __defaults
    with open(config_path, "r", encoding="utf-8") as c:
        try:
            # Load configuration
            config = tomli.loads(c.read())
        except tomli.TOMLDecodeError:
            # TODO: corrupt config handler
            raise Exception
    return config


def save_config(config_path: str, config: dict) -> None:
    with open(config_path, "wb") as c:
        tomli_w.dump(config, c)


def merge_external_config(obj: object, name: str, config_path: dict) -> None:
    if not hasattr(obj, "DEFAULTS"):
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
        dict_merge(lang, internal_lang)
    elif language_code == "internal":
        return internal_lang
    elif not os.path.exists(__lang_path):
        vprint("error: language file not found", error_level="error")
        dict_merge(lang, internal_lang, True)
    elif os.path.exists(__lang_path):
        lang_code = language_code
        with open(__lang_path, "r", encoding="utf-8") as l:
            # Change language to internal without modifying the variable
            # Doing this to avoid more languages than the internal one
            # and the currently loaded overlapping
            dict_merge(lang, internal_lang, True)
            # Now, change
            dict_merge(lang, tomli.load(l), True)
            # Merge internal language with loaded one, avoids errors due
            # missing strings
    return lang


def get_installed_languages() -> list[str]:
    return [strip_extension(f.name) for f in os.scandir(paths["lang"])]


def change_verbose_level(new_level: int, change_print=True, change_log=False):
    global verbose_level
    if new_level not in range(0, 6):
        raise ConfigError("tmp_string: invalid verbose level")
    if change_print:
        verbose_level["print"] = new_level
    if change_log:
        verbose_level["log"] = new_level


def change_paths(new_paths: dict):
    global paths
    for entry, path in new_paths.items():
        paths[entry] = path


def change_options(new_options: dict):
    global options
    dict_merge(options, new_options, True)


def parse_arguments(get_parser=False) -> dict:
    def parse_external_args(args: dict, dest: dict, dest_name: str) -> None:
        "Convert an ARGUMENTS object to argparse arguments"
        group_name = lang["args"]["groups"]["extractor"] % dest_name
        # Create an argument group for the argument
        z = parser.add_argument_group(title=group_name)
        _external_arg_groups.append(group_name)
        dest[dest_name.lower()] = {}
        for arg in args:
            # Add argument to group
            z.add_argument(*arg["args"], **arg["attrib"])
            vprint(
                lang["args"]["added_arg"] % (*arg["args"], dest_name),
                4,
                "polarity",
                "debug",
            )
            # Add argument to map, to later put it in it's respective
            # config entry
            arg_name = re.sub(r"^(--|-)", "", arg["args"][0]).replace("-", "_")
            args_map[arg_name] = (dest, dest_name.lower(), arg["variable"])

    def process_args() -> None:
        "Add argument values to their respective config entries"
        for group in parser._action_groups:
            _active_dict = opts
            # Skip external groups
            if group.title in _external_arg_groups:
                continue
            elif group.title == lang_group["download"]:
                # Change active options dict to download
                _active_dict = opts["download"]
            elif group.title == lang_group["search"]:
                _active_dict = opts["search"]
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
        "Processes arguments added via an ARGUMENTS iterable"
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
    lang_help = lang["args"]["help"]
    lang_group = lang["args"]["groups"]
    # Set logging filename and configuration
    log_filename = paths["log"] + f"log_{filename_datetime()}.log"
    logging.basicConfig(
        filename=log_filename,
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
    )
    # Set options' base dictionaries
    opts = {"download": {}, "search": {}, "extractor": {}}
    args_map = {}

    parser = argparse.ArgumentParser(
        usage=USAGE,
        description="Polarity %s | https://github.com/aveeryy/Polarity/" % (__version__),
        prog="Polarity",
        add_help=False,
        formatter_class=__FORMATTER,
    )

    general = parser.add_argument_group(title=lang_group["general"])

    parser.add_argument("url", help=argparse.SUPPRESS, nargs="*")
    # Windows install finisher
    parser.add_argument("--windows-setup", help=argparse.SUPPRESS, action="store_true")

    general.add_argument("-h", "--help", action="store_true", help=lang_help["help"])
    general.add_argument(
        "--extended-help", help=lang_help["extended_help"], action="store_true"
    )
    general.add_argument(
        "-V",
        "--version",
        action="store_true",
        dest="print_version",
        help=lang_help["version"],
    )
    # Verbose options
    general.add_argument(
        "-v",
        "--verbose",
        choices=["0", "1", "2", "3", "4", "5"],
        help=lang_help["verbose"],
    )
    general.add_argument(
        "--log-verbose",
        choices=["0", "1", "2", "3", "4", "5"],
        help=lang_help["verbose_log"],
    )
    general.add_argument(
        "-m",
        "--mode",
        choices=["download", "search", "print", "livetv"],
        default="download",
        help=lang_help["mode"],
    )
    general.add_argument("--language", help=lang_help["language"])
    general.add_argument(
        "--installed-languages",
        action="store_true",
        help=lang_help["installed_languages"],
    )
    general.add_argument(
        "--install-languages", nargs="*", help=lang_help["install_languages"]
    )
    general.add_argument(
        "--update-languages", action="store_true", help=lang_help["update_languages"]
    )
    general.add_argument("--update", action="store_true", help=lang_help["update"])
    general.add_argument(
        "--update-git", action="store_true", help=lang_help["update_git"]
    )
    general.add_argument(
        "--check-for-updates", action="store_true", help=lang_help["update_check"]
    )
    general.add_argument("--filters", help=lang_help["filters"])
    general.add_argument("--accounts-directory", help=lang_help["accounts_dir"])
    general.add_argument("--binaries-directory", help=lang_help["binaries_dir"])
    general.add_argument("--config-file", help=lang_help["config_file"])
    general.add_argument("--download-log-file", help=lang_help["log_file"])
    general.add_argument("--language-directory", help=lang_help["language_dir"])
    general.add_argument("--log-directory", help=lang_help["log_dir"])
    general.add_argument("--temp-directory", help=lang_help["temp_dir"])

    # Search options
    search = parser.add_argument_group(title=lang_group["search"])
    search.add_argument("--results", type=int, help=lang_help["max_results"])
    search.add_argument(
        "--results-per-extractor",
        type=int,
        help=lang_help["max_results_per_extractor"],
    )
    search.add_argument(
        "--results-per-type", type=int, help=lang_help["max_results_per_type"]
    )

    download = parser.add_argument_group(title=lang_group["download"])
    # Downloader options
    download.add_argument("-r", "--resolution", type=int, help=lang_help["resolution"])
    download.add_argument(
        "-R", "--redownload", action="store_true", help=lang_help["redownload"]
    )
    download.add_argument("--series-directory", help=lang_help["download_dir_series"])
    download.add_argument("--movies-directory", help=lang_help["download_dir_movies"])
    download.add_argument("--series-format", help=lang_help["format_series"])
    download.add_argument("--season-format", help=lang_help["format_season"])
    download.add_argument("--episode-format", help=lang_help["format_episode"])
    download.add_argument("--movie-format", help=lang_help["format_movie"])

    # Gets all extractors with an ARGUMENTS object and converts their arguments to
    # argparse equivalents.
    for downloader in DOWNLOADERS.items():
        if not hasattr(downloader[1], "ARGUMENTS"):
            continue
        downloader_name = downloader[0]
        parse_external_args(downloader[1].ARGUMENTS, opts["download"], downloader_name)
    debug = parser.add_argument_group(title=lang_group["debug"])
    debug.add_argument("--dump", choices=["options"], nargs="+", help=lang_help["dump"])
    debug.add_argument(
        "--exit-after-dump", action="store_true", help=lang_help["exit_after_dump"]
    )
    # debug.add_argument('--list-tv-channels', action='store_true')
    debug.add_argument("--debug-colors", action="store_true")

    # Add extractor arguments
    for name, extractor in EXTRACTORS.items():
        if not hasattr(extractor, "ARGUMENTS"):
            continue
        parse_external_args(extractor.ARGUMENTS, opts["extractor"], name)

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
    if any(s in sys.argv for s in ("--debug-colors", "--a")):
        vprint(lang["polarity"]["enabled_debug"], error_level="debug")
        change_verbose_level(0, True, True)
        options["mode"] = "debug"

    return (args.url, options)


def get_parser():
    return parse_arguments(get_parser=True)


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
                return ""

            # add the heading if the section was non-empty
            if self.heading != "==SUPRESS==" and self.heading is not None:
                current_indent = self.formatter._current_indent
                heading = "%*s%s\n%s\n" % (
                    current_indent + 1,
                    "",
                    # Bold header
                    f"\033[1m{self.heading}\033[0m",
                    # Underline
                    "\u2500" * (len(self.heading) + 2),
                )
            else:
                heading = ""

            # join the section-initial newline, the heading and the help
            return join(["\n", heading, item_help, "\n"])

    def _format_usage(self, usage, actions, groups, prefix: str) -> str:
        # Change the usage text to the language provided one
        prefix = f"\033[1m{lang['polarity']['use']}\033[0m"
        return super()._format_usage(usage, actions, groups, prefix)

    def _format_text(self, text: str) -> str:
        # Make the text below the usage string bold
        return super()._format_text(f"\033[1m{text}\033[0m")

    def _format_action_invocation(self, action):
        return ", ".join(action.option_strings)


class ExtendedFormatter(HelpFormatter):
    def _format_args(self, action, default_metavar):
        get_metavar = self._metavar_formatter(action, default_metavar)
        if action.nargs is None:
            result = "%s" % get_metavar(1)
        elif action.nargs == argparse.OPTIONAL:
            result = "[%s]" % get_metavar(1)
        elif action.nargs == argparse.ZERO_OR_MORE:
            metavar = get_metavar(1)
            result = "[%s ...]" % metavar
        elif action.nargs == argparse.ONE_OR_MORE:
            result = "%s ..." % get_metavar(1)
        elif action.nargs == argparse.REMAINDER:
            result = "..."
        elif action.nargs == argparse.PARSER:
            result = "%s ..." % get_metavar(1)
        elif action.nargs == argparse.SUPPRESS:
            result = ""
        else:
            try:
                formats = ["%s" for _ in range(action.nargs)]
            except TypeError:
                raise ValueError("invalid nargs value") from None
            result = " ".join(formats) % get_metavar(action.nargs)
        return result

    def _metavar_formatter(self, action, default_metavar):
        if action.metavar is not None:
            result = action.metavar
        if action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            result = "(%s)" % ",".join(choice_strs)
        else:
            result = ""

        def format(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result,) * tuple_size

        return format

    def _format_action_invocation(self, action):
        if not action.option_strings or action.nargs == 0:
            return super()._format_action_invocation(action)
        default = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default)
        return ", ".join(action.option_strings) + " " + args_string


# Set preferred help formatter
__FORMATTER = HelpFormatter if "--extended-help" not in sys.argv else ExtendedFormatter

# Part 1: Define default configurations

# Base path for configuration files
__main_path = f"{get_home_path()}/.Polarity/"
# Default base path for downloads
__download_path = f"{get_home_path()}/Polarity Downloads/"

# Default paths
paths = {
    k: __main_path + v
    for k, v in {
        "account": "Accounts/",
        "bin": "Binaries/",
        "cfg": "config.toml",
        "dl_log": "download.log",
        "dump": "Dumps/",
        "lang": "Languages/",
        "log": "Logs/",
        "sync_list": "sync.json",
        "tmp": "Temp/",
    }.items()
}

# Default config values
__defaults = {
    # Verbosity level
    # Does not affect logs
    "verbose": 1,
    # Log verbosity level
    # This must be 4 to report an issue
    "verbose_logs": 4,
    # Language file to use
    # Leave empty to use internal language
    # 'internal' also works
    "language": "internal",
    # Check for updates on start-up
    # This does not automatically update Polarity
    "check_for_updates": False,
    # Automatically update language files
    "auto_update_languages": False,
    # Download options
    "download": {
        # Maximum active downloads
        "active_downloads": 5,
        # Output directory for series
        "series_directory": f'{__download_path}{"Series/"}'.replace("\\", "/"),
        # Output directory for movies
        "movies_directory": f'{__download_path}{"Movies/"}'.replace("\\", "/"),
        # Path formatting for series directories
        # Default format: Extractor/Title (Year)
        "series_format": "{W}/{S} ({y})",
        # Path formatting for season directories
        # Default format: Season 1 - Season identifier
        "season_format": "Season {Sn} - {i}",
        # Filename formatting for episodes
        # Default format: Title S01E01 - Episode title
        "episode_format": "{S} S{sn}E{en} - {E}",
        # Filename formatting for movies
        # Default format: Movie title (Year)
        "movie_format": "{E} ({Y})",
        # Desired video resolution, number must be height
        # If resolution is not available, gets the closest value
        "resolution": 4320,
        # Allow downloading previously downloaded episodes
        "redownload": False,
        # Extension for video extractor downloads
        "video_extension": ".mkv",
        # Extension for audio extractor downloads
        "audio_extension": "auto",
    },
    # Extractor options
    "extractor": {
        "active_extractions": 5,
    },
    "search": {
        # Absolute maximum for results
        "max_results": 100,
        # Maximum results per extractor
        "max_results_per_extractor": 100,
        # Maximum results per
        "max_results_per_type": 100,
        # Format for results
        # Default format: Title (Polarity content ID [extractor/type-id])
        # Default example: Pokémon (atresplayer/series-000000)
        # Available format codes:
        # https://github.com/aveeryy/Polarity/tree/main/polarity/docs/format.md
        "result_format": "\033[1m{n}\033[0m ({I})",
    },
    "flags": [],
}

# Predefine configuration variables
lang = {}
verbose_level = {"print": 1, "log": 4}

lang = internal_lang

# Part 2: Load options from configuration file (and some arguments)

__path_arguments = {
    "--accounts-directory": "account",
    "--binaries-directory": "bin",
    "--config-file": "cfg",
    "--download-log-file": "dl_log",
    "--language-directory": "lang",
    "--log-directory": "log",
    "--temp-directory": "tmp",
}

# Set new paths from user arguments
for arg, path_name in __path_arguments.items():
    if arg in sys.argv:
        _value = sys.argv[sys.argv.index(arg) + 1]
        paths[path_name] = _value
        # Create the directory if it does not exist
        if "directory" in arg:
            os.makedirs(_value, exist_ok=True)

# If config file is specified and does not exist, create it
if paths["cfg"] and not os.path.exists(paths["cfg"]):
    generate_config(paths["cfg"])

# Load configuration from file
config = load_config(paths["cfg"])
# Import DOWNLOADER and EXTRACTOR list here to avoid import loops
from polarity.downloader import DOWNLOADERS  # noqa: E402
from polarity.extractor import EXTRACTORS  # noqa: E402

# Load new configuration entries
dict_merge(config, __defaults)
# Load new configuration entries from extractors and downloaders
for name, downloader in DOWNLOADERS.items():
    merge_external_config(downloader, name, config["download"])
for name, extractor in EXTRACTORS.items():
    merge_external_config(extractor, name, config["extractor"])
# Save the configuration with the new entries to the file
save_config(paths["cfg"], config)
# Create the download log file
mkfile(paths["dl_log"], "")
# Load language file if specified
if "--language" in sys.argv:
    lang_code = sys.argv[sys.argv.index("--language") + 1]
elif config["language"] not in ("", "internal", "integrated"):
    lang_code = config["language"]
else:
    lang_code = None
# Update the language
lang = change_language(language_code=lang_code)
# Set usage string
USAGE = lang["polarity"]["usage"]
# Set verbosity levels based from arguments and execution mode
if get_argument_value(["-m", "--mode"]) == "live_tv":
    # Mode is set to one designed to output a parsable string
    # This is forced to 0 to avoid any status msg breaking any script
    verbose_level["print"] = 0
elif any(a in sys.argv for a in ("-q", "--quiet")):
    # Quiet parameter passed,
    verbose_level["print"] = 0
elif any(a in sys.argv for a in ("-v", "--verbose")):
    # Avoid collision with shtab --verbose argument
    if "shtab" not in sys.argv[0]:
        value = get_argument_value(("-v", "--verbose"))
        if value is None or int(value) not in [*range(0, 6)]:
            raise ConfigError(lang["polarity"]["except"]["verbose_error"] % value)
        verbose_level["print"] = int(value)
elif "verbose" in config:
    verbose_level["print"] = int(config["verbose"])

# Set logging verbosity level
if "--log-verbose" in sys.argv:
    log_value = get_argument_value("--log-verbose")
    # Check if value is valid
    if log_value is None or int(log_value) not in [*range(0, 6)]:
        raise ConfigError(lang["polarity"]["except"]["verbose_error"] % log_value)
    verbose_level["log"] = int(log_value)
elif "verbose_logs" in config:
    verbose_level["log"] = config["verbose_logs"]

# Part 3: Load options from the rest of command line arguments

# Parse arguments
# Avoid argument parsing if running shtab to avoid argument collision
urls, options = parse_arguments() if "shtab" not in sys.argv[0] else (None, None)
