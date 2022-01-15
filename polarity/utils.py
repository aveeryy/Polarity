import json
import logging
import ntpath
import os
import re
import subprocess
import sys

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from json.decoder import JSONDecodeError
from shutil import which
from sys import platform
from time import time
from typing import Union
from urllib.parse import urlparse
from xml.parsers.expat import ExpatError

import cloudscraper
import colorama
import requests
import xmltodict
from requests.models import Response
from tqdm import tqdm
from urllib3.util.retry import Retry


colorama.init()

browser = {"browser": "firefox", "platform": "windows", "mobile": False}

dump_requests = False

retry_config = Retry(
    total=10, backoff_factor=1, status_forcelist=[502, 504, 504, 403, 404]
)

##########################
#  Printing and logging  #
##########################


def vprint(
    message,
    level: int = 1,
    module_name: str = "polarity",
    error_level: str = None,
    end: str = "\n",
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
    try:
        from polarity.config import verbose_level
    except ImportError:
        # Set verbose levels to default if cannot import from config
        verbose_level = {"print": 1, "log": 4}

    # Colors
    red = colorama.Fore.RED
    blu = colorama.Fore.CYAN
    yel = colorama.Fore.YELLOW
    gre = colorama.Fore.GREEN
    reset = colorama.Fore.RESET

    head = f'[{module_name}{f"/{error_level}" if error_level is not None else ""}]'

    # Apply colors to head
    if error_level in ("error", "critical", "exception"):
        # Errors and exceptions
        head = f"{red}{head}{reset}"
    elif error_level == "warning":
        # Warnings
        head = f"{yel}{head}{reset}"
    elif error_level == "debug":
        # Debug, verbose level >= 3, strings
        head = f"{blu}{head}{reset}"
    else:
        # Rest of strings
        head = f"{gre}{head}{reset}"

    if level <= int(verbose_level["print"]):
        # Print the message
        tqdm.write(f"\033[1m{head}\033[0m {message}", end=end)

    # Redact emails out for logs
    if type(message) is not str:
        message = str(message)

    # Redact emails when logging
    message = re.sub(
        r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", "[REDACTED]", message
    )

    log = logging.info if error_level is None else getattr(logging, error_level)
    # Log message if msg level in range of logging level
    if level <= int(verbose_level["log"]):
        log(f"[{module_name}] {message}")


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


#######################
#  Android utilities  #
#######################


def running_on_android() -> bool:
    "Returns True if running on an Android system"
    return "ANDROID_ROOT" in os.environ


def send_android_notification(
    title: str = "Polarity",
    contents=str,
    group=str,
    id=str,
    priority: int = 0,
    sound=bool,
    vibrate_pattern=None,
    image_path=str,
    **kwargs,
) -> None:
    """
    Send an Android notification using Termux:API
    #### Priority values
    - 4: Max
    - 3: High
    - 2: Low
    - 1: Min
    - 0: Default
    """
    # TODO(s): better priority explanation, finish adding values
    if not running_on_android() or not which("termux-notification"):
        # Return if not running on an Android device, or if Termux-API is not installed
        return
    args = ["termux-notification", "-t", title, "-c", contents]
    if group != str:
        args.extend(["--group", group])
    if id != str:
        args.extend(["-i", id])
    args.extend(["--priority", str(priority)])
    subprocess.run(args, check=True)


def remove_android_notification(id: str) -> None:
    "Remove an Android notification by it's identifier"
    subprocess.run(["termux-notification-remove", id], check=True)


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
    from polarity.types import str_to_type

    if not is_content_id(id):
        vprint("~TEMP~ Failed to parse content identifier", level=1, error_level="error")
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
    global dump_requests
    from polarity.config import lang

    vprint(lang["polarity"]["requesting"] % url, 5, "cloudscraper", "debug")
    r = cloudscraper.create_scraper(browser=browser, cipherSuite="HIGH:!DH:!aNULL")
    # check if method is valid
    if not hasattr(r, method.lower()):
        raise Exception("~TEMP~ invalid method")
    request = getattr(r, method.lower())(url, **kwargs)

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
    "Same as request_webpage, but returns a tuple with the xml as a dict and the response object"
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


def get_compatible_extractor(text: str) -> Union[tuple[str, object], None]:
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
            if arg in sys.argv:
                _arg = arg
                break
    elif type(args) is str:
        _arg = args
    if _arg is None:
        return
    elif sys.argv.index(_arg) + 1 > len(sys.argv):
        return
    return sys.argv[sys.argv.index(_arg) + 1]


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


def version_to_tuple(version_string: str) -> tuple[str]:
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


def get_task_by_name(task_list: list, task_name: str):
    from polarity.types.task import Task

    _wanted_task = None
    for task in task_list:
        # Recursively parse the subtask list
        _wanted_task = get_task_by_name(task.subtasks, task_name)
        if task.name == task_name:
            _wanted_task = task
            break
    return _wanted_task


def order_list(
    to_order: list,
    order_definer: list[str],
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
):
    "Create a file POSIX's touch-style"
    if os.path.exists(path) and not overwrite:
        return
    open(path, "w").write(contents)
