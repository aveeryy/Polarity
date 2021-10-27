from shutil import which
from sys import platform
from threading import Thread, current_thread
from urllib.parse import urljoin, urlparse
from time import sleep, time
import colorama
import requests
from requests.models import Response
from tqdm import tqdm
from json.decoder import JSONDecodeError
from xml.parsers.expat import ExpatError
from urllib3.util.retry import Retry

from dataclasses import dataclass

import cloudscraper
import json
import logging
import os
import re
import subprocess
import toml
import xmltodict

colorama.init()

browser = {
    'browser': 'firefox',
    'platform': 'windows',
    'mobile': False
}

dump_requests = False

retry_config = Retry(total=10, backoff_factor=1, status_forcelist=[502, 503, 504, 403, 404])

def vprint(message, level=1, module_name='polarity', error_level=None, end='\n', use_print=False):
    '''
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
    '''
    try:
        from polarity.config import verbose_level
    except ImportError:
        verbose_level = 1

    # Colors
    red = colorama.Fore.RED
    blu = colorama.Fore.CYAN
    yel = colorama.Fore.YELLOW
    gre = colorama.Fore.GREEN
    reset = colorama.Fore.RESET

    module = f'[{module_name}{f"/{error_level}" if error_level is not None else ""}]'
    
    print_method = tqdm.write if not use_print else print

    if error_level in ('error', 'critical', 'exception'):
        module = f'{red}{module}{reset}'
    elif error_level == 'warning':
        module = f'{yel}{module}{reset}'
    elif error_level == 'debug':
        module = f'{blu}{module}{reset}'
    else:
        module = f'{gre}{module}{reset}'
    
    msg = f'{module} {message}'

    if level <= int(verbose_level):
        # Print the message
        print_method(msg, end=end)

    if error_level is None and level <= 4:
        logging.info(f'[{module_name}] {message}')
    elif error_level is not None and level <= 4:
        getattr(logging, error_level)(f'[{module_name}] {message}')

def threaded_vprint(*args, lock, **kwargs):
    '''
    ### Threaded verbose print
    #### Same as verbose print, but avoids overlapping caused by threads using Lock objects
    ##### Example usage
    >>> from polarity.utils import threaded_vprint
    >>> from threading import Lock
    >>> my_lock = Lock()  # Create a global lock object
        # On a Thread
    >>> threaded_vprint(
        message=f'Hello world from {threading.current_thread.get_name()}!',
        level=1,
        module_name='demo',
        error_level='debug',
        lock=my_lock)
    # Output assuming three different threads
    [demo/debug] Hello world from Thread-0!
    [demo/debug] Hello world from Thread-1!
    [demo/debug] Hello world from Thread-2!
    '''
    
    with lock:
        vprint(*args, **kwargs)

# Android Utilities

def running_on_android(): return 'ANDROID_ROOT' in os.environ

def send_android_notification(
    title='Polarity',
    contents=str,
    group=str,
    id=str,
    priority: int = 0,
    sound=bool,
    vibrate_pattern=list,
    image_path=str,
    **kwargs):
    '''
    Sends an Android notification using Termux:API
    #### Priority
    - 4: Max
    - 3: High
    - 2: Low
    - 1: Min
    - 0: Default
    '''
    if not running_on_android() or not which('termux-notification'):
        # Return if not running on an Android device, or if Termux-API is not installed
        return
    args = ['termux-notification', '-t', title, '-c', contents]
    if group != str:
        args.extend(['--group', group])
    if id != str:
        args.extend(['-i', id])
    args.extend(['--priority', str(priority)])
    subprocess.run(args, check=True)

def remove_android_notification(id=str):
    subprocess.run(['termux-notification-remove', id], check=True)

# String manipulation stuff

def sanitize_filename(filename=str, directory_replace=False, test_force_win32=False, test_force_android=False):
    'Remove unsupported characters from filename'
    replace_win32 = {
        '|': 'ꟾ',
        '<': '˂',
        '>': '˃',
        '"': "'",
        '?': '？',
        '*': '＊',
        ':': '-',
        '/': '-',
        '\\': '-',
    }

    if platform == 'win32' or test_force_win32:
        # Windows forbidden characters
        for forbidden, shit_looking_character in replace_win32.items():
            if forbidden == '\\' and directory_replace or forbidden == '/' and directory_replace:
                continue
            filename = filename.replace(forbidden, shit_looking_character)
        filename = filename.replace('-\\', ':\\').replace('-/', ':/')
    else:
        # Android forbidden characters
        if running_on_android():
            filename = filename.replace(':', '')
            filename = filename.replace('?', '')
        if not directory_replace:
            filename = filename.replace('/', '-')        
    while True:
        if filename[-1] in ('.', ' '):
            filename = filename[:-1]
            continue
        break
    return filename

def sanitized_file_exists(file_path=str):
    file_dir = os.path.dirname(file_path) + '/'
    sanitized_path = sanitize_filename(file_dir, directory_replace=True)
    sanitized_filename = sanitize_filename(os.path.basename(file_path))
    sanitized = os.path.join(sanitized_path, sanitized_filename)
    if os.path.exists(file_path):
        return True
    if os.path.exists(sanitized):
        return True
    return False

# Adds a '0' behind any number. Example S1 -> S01
def normalize_integer(number):
    try:
        number = float(number)
    except ValueError:
        # Get numbers from string
        number = re.search(r'(\d)+', number)
        number = float(number.group(0))
    if number < 10:
        number = str('0') + str(number)
    else:
        number = str(number)
    if number.endswith('.0'):
        number = re.sub(r'\.\d+', '', number)
    return number

# Returns extension from url
def get_extension(url):
    result = re.search(r'(?P<ext>\.\w+)($|[^/.\w\s,])', url)
    if result is None:
        return
    return result.group('ext')

def humanbytes(B):
   'Return the given bytes as a human friendly KB, MB, GB, or TB string\nhttps://stackoverflow.com/a/31631711'
   B = float(B)
   KB = float(1024)
   MB = float(KB ** 2) # 1,048,576
   GB = float(KB ** 3) # 1,073,741,824
   TB = float(KB ** 4) # 1,099,511,627,776

   if B < KB:
      return '{0} {1}'.format(B,'Bytes' if 0 == B > 1 else 'Byte')
   if KB <= B < MB:
      return '{0:.2f}KB'.format(B/KB)
   if MB <= B < GB:
      return '{0:.2f}MB'.format(B/MB)
   if GB <= B < TB:
      return '{0:.2f}GB'.format(B/GB)
   if TB <= B:
      return '{0:.2f}TB'.format(B/TB)

split_list = lambda lst, sz: [lst[i:i+sz] for i in range(0, len(lst), sz)]

def recurse_merge_dict(main_dict=dict, secondary_dict=dict):
    for key, val in main_dict.items():
        if isinstance(val, dict):
            secondary_node = secondary_dict.setdefault(key, {})
            recurse_merge_dict(val, secondary_node)
        else:
            if key not in secondary_dict:
                secondary_dict[key] = val
    return secondary_dict

def load_language(lang=None):
    'Returns dict containing selected language strings'
    from polarity.config import config, PATHS
    if lang is None:
        lang = config['language']
    base_language = toml.load(f'{PATHS["lang"]}enUS.toml')
    if os.path.exists(f'{PATHS["lang"]}{lang}.toml'):
        loaded_language = toml.load(f'{PATHS["lang"]}{lang}.toml')
        return recurse_merge_dict(base_language, loaded_language)
    else:
        # This string doesn't need to be translated \/
        # vprint('Specified language "%s" doesn\'t exist. Defaulting to english' % lang)
        return base_language
    
def is_language_installed(lang: str) -> bool:
    # from polarity.config import paths
    #return os.path.exists(f'{paths["lang"]}{lang}.toml')
    return True
    # FUCKING IMPORTANT TODO: fix this shit

def filename_datetime():
    from datetime import datetime
    return str(datetime.now()).replace(" ", "_").replace(":", ".")

def run_ffprobe(input, show_programs=True, extra_params=''):
    ffprobe_tries = 0
    vprint('Getting stream information', 1, 'ffprobe')
    params = ['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams']
    if show_programs:
        params.append('-show_programs')
    # Extra parameters
    for e in re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', extra_params):
        e = e.replace('"', '')
        params.append(e)
    params.append(input)
    while True:
        try:
            _json = json.loads(subprocess.check_output(params))
            break
        except subprocess.CalledProcessError:
            vprint('Ffprobe failed, retrying...', 1, 'ffprobe')
            ffprobe_tries += 1
            if ffprobe_tries > 3:
                raise
            continue
    return _json

@dataclass(frozen=True)
class ContentIdentifier:
    extractor: str
    content_type: str
    id: str

content_id_regex = r'(?P<extractor>[\w]+)/(?P<type>[\w]+)-(?P<id>[\S]+)'

def is_content_id(text=str):
    '''
    #### Checks if inputted text is a download id
    >>> is_content_id('crunchyroll/series-000000')
        True
    >>> is_content_id('man')
        False
    '''
    return bool(re.match(content_id_regex, text))

def parse_content_id(id: str):
    '''
    #### Returns a `ContentIdentifier` object with all attributes
    >>> from polarity.utils import parse_content_id
    >>> a = parse_content_id('crunchyroll/series-320430')
    >>> a.extractor
        'crunchyroll'
    >>> a.content_type
        'series'
    >>> a.id
        '320430'
    '''
    if not is_content_id(id):
        vprint('Failed to parse id', 1, 'utils/parse_content_id', 'error')
        return
    parsed_id = re.match(content_id_regex, id)
    return ContentIdentifier(*parsed_id.groups())

def order_list(to_order, index=None, order_definer=list):
    if index is None:
        return [y for x in order_definer for y in to_order if x == y]
    else:
        return [y for x in order_definer for y in to_order if x == y[index]]
    
def order_dict(to_order, order_definer):
    return {y: z for x in order_definer for y, z in to_order.items()  if x == y}

def make_thread(*args, **kwargs):
    from polarity.Polarity import _ALL_THREADS
    thread = Thread(*args, **kwargs)
    _ALL_THREADS[thread.name] = {'obj': thread, 'running': False, }
    return thread

def calculate_time_left(processed: int, total: int, time_start: float):
    elapsed = time() - time_start
    try:
        return elapsed / processed * total - elapsed
    except ZeroDivisionError:
        return 0

def mkfile(path=str, contents=str, ):
    if not os.path.exists(path):
        open(path, 'w').write(contents)
        
def request_webpage(url=str, method='get', **kwargs) -> Response:
    '''
    Make a HTTP request using cloudscraper
    `url` url to make the request to
    `method` http request method
    `cloudscraper_kwargs` extra cloudscraper arguments, for more info check the `requests wiki`
    '''
    # Create a cloudscraper session
    # Spoof an Android Firefox browser to bypass Captcha v2
    browser = {
        'browser': 'firefox',
        'platform': 'android',
        'desktop': False,
    } 
    r = cloudscraper.create_scraper(browser=browser)
    response = getattr(r, method.lower())(url, **kwargs)
    return response



def request_json(url=str, method='get', **kwargs):
    'Same as request_webpage, except it returns a tuple with the json as a dict and the response object'
    response = request_webpage(url, method, **kwargs)
    try:
        return (json.loads(response.content.decode()), response)
    except JSONDecodeError:
        return ({}, response)


def request_xml(url=str, method='get', **kwargs):
    'Same as request_webpage, except it returns a tuple with the xml as a dict and the response object'
    response = request_webpage(url, method, **kwargs)
    try:
        return (xmltodict.parse(response.content.decode()), response)
    except ExpatError:
        return ({}, response)
    

def get_country_from_ip() -> str:
    return requests.get('http://ipinfo.io/json').json().get('country')
    
def get_compatible_extractor(url: str) -> tuple[str, object]:
    'Returns a compatible extractor for the inputted url, if it exists'
    from polarity.extractor import EXTRACTORS
    if not is_content_id(text=url):
        url_host = urlparse(url).netloc
        extractor = [
            extractor
            for extractor in EXTRACTORS.values()
            if re.match(extractor[2], url_host)
            ]
        if not extractor:
            return(None, None)
        # Return (name, object)
        return (extractor[0][0], extractor[0][1])
    else:
        parsed_id = parse_content_id(id=url)
        extractor_name = parsed_id.extractor
        if not extractor_name in EXTRACTORS:
            return (None, None)
        return (EXTRACTORS[extractor_name][0], EXTRACTORS[extractor_name][1])


def get_installed_languages() -> list[str]:
    from polarity.config import paths
    return [f.name.replace('.toml', '') for f in os.scandir(paths['lang'])]

def format_language_code(code: str) -> str:
    '''
    Returns a correctly formatted language code
    
    Example:
    >>> format_language_code('EnuS')
    'enUS'
    '''
    code = code.strip('_')
    lang = code[0:2]
    country = code[2:4]
    return f'{lang.lower()}{country.upper()}'

def version_to_tuple(version_string: str) -> tuple:
    version = version_string.split('.')
    # Split the revision number
    if '-' in version[-1]:
        minor_rev = version[-1].split('-')
        del version[-1]
        version.extend(minor_rev)
    return tuple(version)

def get_item_by_id(iterable: list, identifier: str):
    for item in iterable:
        if item.id == identifier:
            return item
