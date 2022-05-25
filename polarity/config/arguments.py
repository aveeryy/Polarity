import argparse
import os

import shtab
from polarity.config import defaults
from polarity.config.formatters import formatter
from polarity.lang import lang
from polarity.version import __version__

urls = []
ACTIONS = ("download", "search", "livetv", "update")


def parse_arguments() -> dict:
    """Generate a config dict from arguments' values"""

    def process_args() -> None:
        """Add argument values to their respective config entries"""

        def set_value(dest, value):
            active = root
            chunks = dest.split("/")
            for chunk in chunks[:-1]:
                if chunk not in active:
                    active[chunk] = {}
                active = active[chunk]
            # Set the value
            active[chunks[-1]] = value

        root = {}
        for group in parser._action_groups:
            for entry in group._group_actions:
                value = getattr(args, entry.dest)
                if entry.dest == "url":
                    urls.extend(value)
                    continue
                set_value(entry.dest, value)
        return root

    # Parse arguments
    args, _ = parser.parse_known_args()
    # args = parser.parse_args()
    # Print help
    if args.help is True or args.extended_help:
        parser.print_help()
        os._exit(0)
    return process_args()


def mode_handler(value):
    if value not in ACTIONS:
        urls.append(value)
        return "download"
    return value


# Set language dictionaries
lang_help = lang["args"]["help"]
lang_group = lang["args"]["groups"]
# predefine preambles for shtab custom completion
preamble = {"bash": "", "zsh": "", "tcsh": ""}
types = {}
# extensions to generate preambles of
PREAMBLE_GEN = (".toml", ".log")

# shtab stuff, generate file completion with custom extensions
# for --config-file arguments and alike

# bash template for preamble
bash_preamble = """
# $1=COMP_WORDS[1]
_polarity_compgen_%s(){
  compgen -d -- $1
  compgen -f -X '!*?%s' -- $1
  compgen -f -X '!*?%s' -- $1
}\n
"""
for ext in PREAMBLE_GEN:
    # generate preamble for bash
    preamble["bash"] += bash_preamble % (
        f"{ext.strip('.')}File",
        ext.lower(),
        ext.upper(),
    )
    types[ext] = {
        "bash": "_polarity_compgen_%s" % f"{ext.strip('.')} File",
        "zsh": f"_files -g '(*{ext.lower()}|*{ext.upper()})'",
        "tcsh": f"f:*{ext}",
    }

parser = argparse.ArgumentParser(
    usage=lang["polarity"]["usage"],
    description="Polarity %s | https://github.com/aveeryy/Polarity/" % (__version__),
    prog="polarity",
    add_help=False,
    formatter_class=formatter,
)

general = parser.add_argument_group(title=lang_group["general"])
parser.add_argument(
    "action",
    choices=ACTIONS,
    default="download",
    nargs="?",
    type=mode_handler,
    help=lang_help["mode"],
)
parser.add_argument("url", help=argparse.SUPPRESS, nargs="*")
# Windows install finisher
parser.add_argument("--windows-setup", help=argparse.SUPPRESS, action="store_true")
general.add_argument("-h", "--help", action="store_true", help=lang_help["help"])
general.add_argument(
    "--extended-help", help=lang_help["extended_help"], action="store_true"
)
# Verbose options
general.add_argument(
    "-v",
    "--verbose",
    choices=defaults.VALID_VERBOSE_LEVELS,
    help=lang_help["verbose"],
)
general.add_argument(
    "--log-verbose",
    choices=defaults.VALID_VERBOSE_LEVELS,
    help=lang_help["verbose_log"],
    dest="verbose_logs",
)

general.add_argument("--language", help=lang_help["language"])
general.add_argument(
    "--list-languages",
    action="store_true",
    help=lang_help["installed_languages"],
)
general.add_argument("--update", action="store_true", help=lang_help["update"])
general.add_argument("--update-git", action="store_true", help=lang_help["update_git"])
general.add_argument(
    "--check-for-updates", action="store_true", help=lang_help["update_check"]
)
general.add_argument("--filters", help=lang_help["filters"])
general.add_argument(
    "--accounts-directory",
    help=lang_help["accounts_dir"],
    dest=None,
).complete = shtab.DIRECTORY
general.add_argument(
    "--binaries-directory",
    help=lang_help["binaries_dir"],
    dest=None,
).complete = shtab.DIRECTORY
general.add_argument(
    "--config-file",
    help=lang_help["config_file"],
    dest=None,
).complete = types[".toml"]
general.add_argument(
    "--download-log-file",
    help=lang_help["log_file"],
    dest=None,
).complete = types[".log"]
general.add_argument(
    "--log-directory",
    help=lang_help["log_dir"],
    dest=None,
).complete = shtab.DIRECTORY
general.add_argument(
    "--temp-directory",
    help=lang_help["temp_dir"],
    dest=None,
).complete = shtab.DIRECTORY
shtab.add_argument_to(general, preamble=preamble)

# Search options
search = parser.add_argument_group(title=lang_group["search"])
search.add_argument(
    "--search-format",
    help=lang_help["format_search"],
    dest="search/result_format",
)
search.add_argument(
    "--search-trim",
    type=int,
    help=lang_help["results_trim"],
    dest="search/trim_names",
)
search.add_argument("--results", type=int, help=lang_help["max_results"])
search.add_argument(
    "--results-per-extractor",
    type=int,
    help=lang_help["max_results_per_extractor"],
    dest="search/results_per_extractor",
)
search.add_argument(
    "--results-per-type",
    type=int,
    help=lang_help["max_results_per_type"],
    dest="search/results_per_type",
)

download = parser.add_argument_group(title=lang_group["download"])

# Downloader options
download.add_argument("-r", "--resolution", type=int, help=lang_help["resolution"])
download_redownload = download.add_mutually_exclusive_group()
download_redownload.add_argument(
    "-R",
    "--redownload",
    action="store_true",
    default=None,
    help=lang_help["redownload"],
    dest="download/redownload",
)
download_redownload.add_argument(
    "--dont-redownload",
    action="store_false",
    help=lang_help["do_not_redownload"],
    dest="download/redownload",
)
download.add_argument(
    "--episode-format",
    help=lang_help["format_episode"],
    dest="download/episode_format",
)
download.add_argument(
    "--movie-format",
    help=lang_help["format_movie"],
    dest="download/movie_format",
)
download.add_argument(
    "--generic-format",
    help=lang_help["format_generic"],
    dest="download/generic_format",
)

##############################
# Downloader arguments below #
##############################

penguin = parser.add_argument_group(lang_group["extractor"] % "Penguin")
penguin.add_argument(
    "--penguin-attempts",
    type=int,
    help=lang["penguin"]["args"]["attempts"],
    dest="download/penguin/attempts",
)
penguin.add_argument(
    "--penguin-threads",
    type=int,
    help=lang["penguin"]["args"]["threads"],
    dest="download/penguin/threads",
)
penguin.add_argument(
    "--penguin-tag-output",
    help=lang["penguin"]["args"]["tag_output"],
    action="store_true",
    default=None,
    dest="download/penguin/tag_output",
)
penguin.add_argument(
    "--penguin-keep-logs",
    help=lang["penguin"]["args"]["keep_logs"],
    action="store_true",
    default=None,
    dest="download/penguin/keep_logs",
)

debug = parser.add_argument_group(title=lang_group["debug"])
debug.add_argument(
    "--dump", choices=["options", "urls"], nargs="+", help=lang_help["dump"]
)
debug.add_argument(
    "--exit-after-dump", action="store_true", help=lang_help["exit_after_dump"]
)

#############################
# Extractor arguments below #
#############################

atresplayer = parser.add_argument_group(lang_group["extractor"] % "Atresplayer")
atresplayer_codec = atresplayer.add_mutually_exclusive_group()
atresplayer_codec.add_argument(
    "--atresplayer-use-hevc",
    action="store_true",
    help=lang["atresplayer"]["args"]["hevc_codec"],
    dest="extractor/atresplayer/use_hevc",
)
atresplayer_codec.add_argument(
    "--atresplayer-use-avc",
    action="store_false",
    help=lang["atresplayer"]["args"]["avc_codec"],
    dest="extractor/atresplayer/use_hevc",
)
atresplayer.add_argument(
    "--atresplayer-email",
    help=lang["args"]["help"]["email"] % "Atresplayer",
    dest="extractor/atresplayer/username",
)
atresplayer.add_argument(
    "--atresplayer-password",
    help=lang["args"]["help"]["pass"] % "Atresplayer",
    dest="extractor/atresplayer/password",
)

crunchyroll = parser.add_argument_group(lang_group["extractor"] % "Crunchyroll")
crunchyroll.add_argument(
    "--crunchyroll-subs",
    choices=[
        "all",
        "none",
        "en-US",
        "es-ES",
        "es-LA",
        "fr-FR",
        "pt-BR",
        "ar-ME",
        "it-IT",
        "de-DE",
        "ru-RU",
        "tr-TR",
    ],
    help=lang["crunchyroll"]["args"]["subs"],
    nargs="+",
    dest="extractor/crunchyroll/sub_language",
)
crunchyroll.add_argument(
    "--crunchyroll-dubs",
    choices=[
        "all",
        "jp-JA",
        "en-US",
        "es-LA",
        "fr-FR",
        "pt-BR",
        "it-IT",
        "de-DE",
        "ru-RU",
    ],
    help=lang["crunchyroll"]["args"]["dubs"],
    nargs="+",
    dest="extractor/crunchyroll/dub_language",
)
crunchyroll.add_argument(
    "--crunchyroll-meta",
    choices=[
        "auto",
        "en-US",
        "es-ES",
        "es-LA",
        "fr-FR",
        "pt-BR",
        "pt-PT",
        "ar-ME",
        "it-IT",
        "de-DE",
        "ru-RU",
    ],
    help=lang["crunchyroll"]["args"]["meta"],
    dest="extractor/crunchyroll/meta_language",
)
crunchyroll.add_argument(
    "--crunchyroll-hardsub",
    choices=[
        "none",
        "en-US",
        "es-ES",
        "es-LA",
        "fr-FR",
        "pt-BR",
        "ar-ME",
        "it-IT",
        "de-DE",
        "ru-RU",
        "tr-TR",
    ],
    help=lang["crunchyroll"]["args"]["hard"],
    dest="extractor/crunchyroll/hardsub_language",
)
crunchyroll.add_argument(
    "--crunchyroll-email",
    help=lang["args"]["help"]["email"] % "Crunchyroll",
    dest="extractor/crunchyroll/username",
)
crunchyroll.add_argument(
    "--crunchyroll-password",
    help=lang["args"]["help"]["pass"] % "Crunchyroll",
    dest="extractor/crunchyroll/password",
)

limelight = parser.add_argument_group(lang_group["extractor"] % "Limelight")
limelight.add_argument(
    "--limelight-format",
    help=lang["limelight"]["args"]["format"],
    dest="extractor/limelight/preferred_format",
)
