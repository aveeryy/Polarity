import errno
import json
import logging
import ntpath
import os
import re
import shutil
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from json.decoder import JSONDecodeError
from shutil import which
from sys import platform
from time import sleep, time
from typing import List, Tuple, Union
from urllib.parse import urlparse
from xml.parsers.expat import ExpatError

import cloudscraper
import requests
import xmltodict
from requests.adapters import HTTPAdapter
from requests.models import Response
from tqdm import tqdm
from urllib3.util.retry import Retry

browser = {"browser": "firefox", "platform": "windows", "mobile": False}
retry_config = Retry(
    total=5, backoff_factor=0.5, status_forcelist=[502, 504, 504, 403, 404]
)
# create the cloudscraper's scraper
# equivalent to requests' session
scraper = cloudscraper.create_scraper(browser=browser, cipherSuite="HIGH:!DH:!aNULL")
# mount adapters
scraper.mount("http://", HTTPAdapter(max_retries=retry_config))
scraper.mount("https://", HTTPAdapter(max_retries=retry_config))
# https://stackoverflow.com/questions/38015537
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += "HIGH:!DH:!aNULL"

dump_requests = False
vprint_locked = False
vprint_failed_to_print = False
write_lock = False

##########################
#  Printing and logging  #
##########################


class _FormattedText:
    """
    FormattedText object

    Provides an easy way to color text in the terminal

    Example usage:
    >>> # Initialize the class
    >>> FT = _FormattedText()
    >>> print(f'{FT.red}hi{FT.reset}')
    """

    # foreground colors
    black = 30
    red = 31
    green = 32
    yellow = 33
    blue = 34
    magenta = 35
    cyan = 36
    white = 37
    # text stylization
    bold = 1
    dimmed = 2
    # reset all colors and styles
    reset = 0

    def __init__(self):
        for name, value in (
            (name, getattr(self, name)) for name in dir(self) if not name.startswith("_")
        ):
            setattr(self, name, f"\033[{value}m")

    def _strip(self, string: str) -> str:
        for code in (getattr(self, n) for n in dir(self) if not n.startswith("_")):
            string = string.replace(f"{code}".replace("\033", "\x1b"), "")
        return string


# Initialize the _FormattedText class
FormattedText = _FormattedText()


def vprint(
    message,
    level: str = "info",
    module_name: str = "polarity",
    end: str = "\n",
    extra_loggers: list = None,
    lock_printing=False,
) -> None:
    """
    ### Verbose print
    #### Prints a message based on verbose level

    ##### Example usage
    >>> from polarity.utils import vprint
    >>> vprint(
        message='Hello world!',
        level=1,
        module_name='demo',
        error_level='debug')
    [demo/debug] Hello world!  # Output
    >>>
    """

    global vprint_failed_to_print, vprint_locked

    def build_head() -> str:
        string = f"{FormattedText.bold}{table[level][1]}[{module_name}"
        if level != "info":
            string += f"/{level if level != 'verbose' else 'debug'}"
        string += f"]{FormattedText.reset}"

        return string

    def get_loggers() -> list:
        main_logger = logging.getLogger("polarity")
        _level = level if level != "verbose" else "debug"
        return [getattr(logger, _level) for logger in [main_logger, *extra_loggers]]

    locked_by_me = False

    if lock_printing:
        vprint_locked = True
        locked_by_me = True

    try:
        from polarity.config import options, VALID_VERBOSE_LEVELS, ConfigError, lang

    except ImportError as ex:
        # warn the user using poor man's vprint
        if not vprint_failed_to_print:
            print(f"[vprint/critical] failed to import from polarity.config: {ex}")
            print("[vprint/critical] falling back to default configuration")
            vprint_failed_to_print = True
        # Set verbose levels to default if cannot import from config
        options = {"verbose": "debug", "verbose_logs": "debug"}
        # since VALID_VERBOSE_LEVELS and ConfigError could not be imported
        # and using fallback config, do not check if verbose level is valid

    if not options:
        # using shtab, fallback to quiet
        options = {"verbose": "quiet", "verbose_logs": "quiet"}

    # Check if verbose level is valid
    if options["verbose"] not in VALID_VERBOSE_LEVELS and not vprint_failed_to_print:
        raise ConfigError(
            lang["polarity"]["except"]["verbose_error"] % options["verbose"]
        )
    # Check if verbose logs level is valid
    elif (
        options["verbose_logs"] not in VALID_VERBOSE_LEVELS and not vprint_failed_to_print
    ):
        raise ConfigError(
            lang["polarity"]["except"]["verbose_log_error"] % options["verbose_logs"]
        )

    if extra_loggers is None:
        extra_loggers = []

    table = {
        "verbose": (6, FormattedText.cyan),
        "debug": (5, FormattedText.cyan),
        "info": (4, FormattedText.green),
        "warning": (3, FormattedText.yellow),
        "error": (2, FormattedText.red),
        "critical": (1, FormattedText.red),
        "exception": (1, FormattedText.red),
        "quiet": (-8, None),
    }

    if type(message) is not str:
        message = str(message)

    # build the message head
    # example: [polarity/debug]
    head = build_head()

    if table[level][0] <= table[options["verbose"]][0] and (
        not vprint_locked or locked_by_me
    ):
        # Print the message if level is equal or smaller
        tqdm.write(f"{head} {message}{FormattedText.reset}", end=end)

    # Redact emails when logging
    message = redact_emails(message)

    for logger in get_loggers():
        # Log message if level is equal or smaller
        if table[level][0] <= table[options["verbose_logs"]][0]:
            logger(f"[{module_name}] {message}")


def thread_vprint(*args, lock, **kwargs) -> None:
    """
    ### Thread verbose print
    Same as verbose print
    but avoids overlapping caused by threads using Lock objects

    #### Example usage
    >>> from polarity.utils import thread_vprint
    >>> from threading import Lock
    >>> my_lock = Lock()  # Create a global lock object
        # On a Thread
    >>> thread_vprint(
        message=f'Hello world from {threading.current_thread.get_name()}!',
        level=1,
        module_name='demo',
        error_level='debug',
        lock=my_lock)
    # Output assuming three different threads
    [demo/debug] Hello world from Thread-0!
    [demo/debug] Hello world from Thread-1!
    [demo/debug] Hello world from Thread-2!
    """

    with lock:
        vprint(*args, **kwargs)


def redact_emails(string) -> str:
    return re.sub(
        r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", "[REDACTED]", string
    )


def set_console_title(string) -> None:
    print(f"\033]2;{string}\a", end="\r")


#######################
#  Android utilities  #
#######################


def running_on_android() -> bool:
    "Returns True if running on an Android system"
    return "ANDROID_ROOT" in os.environ


def send_android_notification(
    title: str, contents: str, id: str, group: str = "Polarity", action: str = None
) -> None:
    """
    Send an Android notification using Termux:API
    """
    if not running_on_android() or not which("termux-notification"):
        # Return if not running on an Android device, or if Termux-API is not installed
        return
    regex = r"([^ ])(')([^ ])"
    args = [
        "termux-notification",
        "-t",
        f"'{title}'",
        "-c",
        f"'{contents}'",
        "-i",
        f"'{id}'",
        "--group",
        f"'{group}'",
    ]

    if action is not None:
        args.extend(("--action", action))

    command = " ".join(args)
    command = re.sub(regex, r"\1'\\\2'\3", command)

    os.system(command)


def remove_android_notification(id: str) -> None:
    "Remove an Android notification by it's identifier"
    if not running_on_android() or not which("termux-notification-remove"):
        return
    os.system(f"termux-notification-remove {id}")


###########################
#  Filenames and strings  #
###########################


def sanitize_path(path: str, force_win32=False) -> str:
    "Remove unsupported OS characters from file path"
    forbidden_windows = {
        "|": "ꟾ",
        "<": "˂",
        ">": "˃",
        '"': "'",
        "?": "？",
        "*": "＊",
        ":": "-",
    }

    def sanitize(string: str, is_dir: bool = False) -> str:
        # Platform-specific sanitization
        if platform == "win32" or force_win32:
            drive, string = ntpath.splitdrive(string)
            # Remove Windows forbidden characters
            for forb, char in forbidden_windows.items():
                # Do not replace '\' and '/' characters if string is a dir
                string = string.replace(forb, char)
            string = drive + string
        elif running_on_android():
            # Remove Android forbidden characters
            for char in (":", "?"):
                string = string.replace(char, "")
        if not is_dir:
            # Replace characters reserved for paths if string is a filename
            for char in ("\\", "/"):
                string = string.replace(char, "-")
        return string

    func = os.path if not re.match(r"\w", path) else ntpath

    directory = sanitize(f"{func.dirname(path)}", True)
    filename = sanitize(func.basename(path))

    return func.join(directory, filename)


def sanitized_path_exists(path: str) -> bool:
    "Checks if the path, or sanitized version of that path, exists"
    sanitized = sanitize_path(path)

    return os.path.exists(path) or os.path.exists(sanitized)


def normalize_number(number) -> str:
    """
    Add a facing 0 to a number if it only has one digit

    Example:
    >>> normalize_number(7)
    '07'
    >>> normalize_number(13)
    '13'
    """
    if type(number) is str and number.isdigit():
        # Get numbers from string
        number = re.search(r"(\d)+", number)
        number = float(number.group(0))
    number = float(number)
    if number < 10:
        number = str("0") + str(number)
    # Convert the number to a string
    number = str(number)
    # Remove decimals from float number if decimal is .0
    if number.endswith(".0"):
        number = re.sub(r"\.\d+", "", number)
    return number


def get_extension(url) -> str:
    """Returns the URI\'s file extension"""
    result = re.search(r"(?P<ext>\.\w+)($|[^/.\w\s,])", url)
    return result.group("ext") if result is not None else ""


def strip_extension(url: str) -> str:
    """Remove the file's extension from an URI"""
    return url.replace(get_extension(url), "")


def dict_merge(dct: dict, merge_dct: dict, overwrite=False, modify=True) -> dict:
    """Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :param overwrite: replace existing keys
    :param modify: modify dct directly
    :return: dict

    Thanks angstwad!
    https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
    """

    if not modify:
        # Make a copy of dct to not modify the obj directly
        dct = deepcopy(dct)
    for k in merge_dct:
        if k in dct and type(dct[k]) is dict and type(merge_dct[k] is dict):
            dict_merge(dct[k], merge_dct[k], overwrite, True)
        elif k not in dct or overwrite and merge_dct[k] not in (False, None):
            dct[k] = merge_dct[k]
    return dct


def filename_datetime() -> str:
    "Returns a filename-friendly datetime string"
    return str(datetime.now()).replace(" ", "_").replace(":", ".")


#########################
#  Content Identifiers  #
#########################


@dataclass(frozen=True)
class ContentIdentifier:
    "Content-unique global identifier"
    extractor: str
    content_type: str
    id: str

    def __str__(self):
        return self.string

    @property
    def string(self):
        return f"{self.extractor}/{self.content_type}-{self.id}"


content_id_regex = r"(?P<extractor>[\w]+)/(?:(?P<type>[\w]+|)-|)(?P<id>[\S]+)"


def is_content_id(text: str) -> bool:
    """
    #### Checks if inputted text is a Content Identifier
    >>> is_content_id('crunchyroll/series-000000')
        True
    >>> is_content_id('man')
        False
    """
    return bool(re.match(content_id_regex, text))


def parse_content_id(id: str) -> ContentIdentifier:
    """
    #### Returns a `ContentIdentifier` object with all attributes
    >>> from polarity.utils import parse_content_id
    >>> a = parse_content_id('crunchyroll/series-320430')
    >>> a.extractor
        'crunchyroll'
    >>> a.content_type
        'series'
    >>> a.id
        '320430'
    """

    from polarity.config import lang
    from polarity.types import str_to_type

    if not is_content_id(id):
        vprint(lang["polarity"]["not_a_content_id"] % id, level="error")
        return
    parsed_id = re.match(content_id_regex, id)
    extractor, _media_type, _id = parsed_id.groups()

    media_type = str_to_type(_media_type)
    return ContentIdentifier(extractor, media_type, _id)


###################
#  HTTP Requests  #
###################


def toggle_request_dumping() -> bool:
    global dump_requests
    dump_requests = dump_requests is False
    return dump_requests


def request_webpage(url: str, method: str = "get", **kwargs) -> Response:
    """
    Make a HTTP request using cloudscraper
    `url` url to make the request to
    `method` http request method
    `kwargs` extra requests arguments, for more info check the `requests wiki`
    """
    from polarity.config import lang

    vprint(lang["polarity"]["requesting"] % url, "verbose", "cloudscraper")
    # check if method is valid
    if not hasattr(scraper, method.lower()):
        raise Exception(lang["polarity"]["except"]["invalid_http_method"] % method)
    request = getattr(scraper, method.lower())(url, **kwargs)

    return request


def request_json(url: str, method: str = "get", **kwargs):
    """
    Same as request_webpage, but returns a tuple with the json
    as a dict and the response object
    :param url:
    """

    response = request_webpage(url, method, **kwargs)
    try:
        return (json.loads(response.content.decode()), response)
    except JSONDecodeError:
        return ({}, response)


def request_xml(url: str, method: str = "get", **kwargs):
    """
    Same as request_webpage, but returns a tuple with the xml
    as a dict and the response object
    """
    response = request_webpage(url, method, **kwargs)
    try:
        return (xmltodict.parse(response.content.decode()), response)
    except ExpatError:
        return ({}, response)


def get_country_from_ip() -> str:
    return requests.get("http://ipinfo.io/json").json().get("country")


################
#  Extractors  #
################


def get_compatible_extractor(text: str) -> Union[Tuple[str, object], None]:
    """
    Returns a compatible extractor for the inputted url or content id,
    if exists, else returns None
    """
    from polarity.extractor import EXTRACTORS

    if not is_content_id(text):
        # get the hostname from the URL
        url_host = urlparse(text).netloc
        # get extractors with matching hostname
        extractor = [
            (name, extractor)
            for name, extractor in EXTRACTORS.items()
            if re.match(extractor.HOST, url_host)
        ]
        # return the first extractor
        return extractor[0] if extractor else None
    elif is_content_id(text):
        parsed_id = parse_content_id(id=text)
        extractor_name = parsed_id.extractor
        # get extractors with matching name
        _EXTRACTORS = {k.lower(): v for k, v in EXTRACTORS.items()}
        return (
            (extractor_name, _EXTRACTORS[extractor_name])
            if extractor_name in _EXTRACTORS
            else None
        )


###############
#  Languages  #
###############


def get_argument_value(args: list):
    """Returns the value of one or more command line arguments"""
    _arg = None
    if type(args) is not str:
        for arg in args:
            if arg in sys.argv[1:]:
                _arg = arg
                break
    elif type(args) is str:
        _arg = args
    if _arg is None:
        return
    elif sys.argv[1:].index(_arg) + 1 > len(sys.argv[1:]):
        return
    return sys.argv[1:][sys.argv[1:].index(_arg) + 1]


def format_language_code(code: str) -> str:
    """
    Returns a correctly formatted language code

    Example:
    >>> format_language_code('EnuS')
    'enUS'
    """
    code = code.strip("-_")
    lang = code[0:2]
    country = code[2:4]
    return f"{lang.lower()}{country.upper()}"


###########
#  Other  #
###########


def get_home_path() -> str:
    if running_on_android():
        return "/storage/emulated/0"
    return os.path.expanduser("~")


def get_config_path() -> str:
    paths = {
        "linux": f"{get_home_path()}/.local/share/Polarity/",
        "win32": f"{get_home_path()}\\AppData\\Local\\Polarity\\",
        "android": f"{get_home_path()}/.Polarity/",
        "darwin": f"{get_home_path()}/Library/Application Support/Polarity/",
    }

    if sys.platform not in paths:
        return f"{get_home_path()}/.Polarity/"
    return paths[sys.platform] if not running_on_android() else paths["android"]


def version_to_tuple(version_string: str) -> Tuple[str]:
    "Splits a version string into a tuple"
    version = version_string.split(".")
    # Split the revision number
    if "-" in version[-1]:
        minor_rev = version[-1].split("-")
        del version[-1]
        version.extend(minor_rev)
    return tuple(version)


def get_item_by_id(iterable: list, identifier: str):
    for item in iterable:
        if item.id == identifier:
            return item


def order_list(
    to_order: list,
    order_definer: List[str],
    index=None,
) -> list:
    if index is None:
        return [y for x in order_definer for y in to_order if x == y]
    return [y for x in order_definer for y in to_order if x == y[index]]


def order_dict(to_order: dict, order_definer: list):
    return {y: z for x in order_definer for y, z in to_order.items() if x == y}


def calculate_time_left(processed: int, total: int, time_start: float) -> float:
    elapsed = time() - time_start
    try:
        return elapsed / processed * total - elapsed
    except ZeroDivisionError:
        return 0.0


def mkfile(
    path: str,
    contents: str,
    overwrite=False,
    writing_mode: str = "w",
    *args,
    **kwargs,
):
    """
    Create a file POSIX's touch-style

    :param path: file path
    :param contents: contents to write to file
    :param overwrite: if false, won't overwrite a file if it does exist
    :param writing_mode:
    """

    if os.path.exists(path) and not overwrite:
        return
    try:
        with open(path, writing_mode, *args, **kwargs) as fp:
            fp.write(contents)
    except OSError as ex:
        from polarity.config import lang

        if ex.errno == errno.ENOSPC:
            vprint(
                lang["polarity"]["no_space_left"],
                "critical",
                lock_printing=True,
            )
            os._exit(1)
