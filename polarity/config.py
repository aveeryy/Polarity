from polarity.update import download_languages
from requests import get
import sys
import toml
from toml.decoder import TomlDecodeError

from copy import deepcopy

from polarity.utils import filename_datetime, load_language, mkfile, recurse_merge_dict, running_on_android, vprint, language_installed
import traceback

USAGE = 'Polarity <url(s)> [OPTIONS]'

HOME = os.path.expanduser('~') if not 'ANDROID_ROOT' in os.environ else '/storage/emulated/0'
MAIN_PATH = HOME + '/.Polarity/'
DOWNLOAD_DEFAULT_BASE = HOME + '/Polarity Downloads/' 

PATHS = {
    'account': 'Accounts/',
    'bin': 'Binaries/',
    'cfg': 'Polarity.toml',
    'dl_log': 'AlreadyDownloaded.log',
    'dump': 'Dumps/',
    'lang': 'Languages/',
    'log': 'Logs/',
    'sync_list': 'SyncList.json',
    'tmp': 'Temp/'
}

# Too lazy to manually do this
# Makes the before specified relative paths absolute
PATHS = {k: MAIN_PATH + v for k, v in PATHS.items()}

try:
    # Create directory tree
    for path in PATHS if '/' not in path:
        os.makedirs(path, exist_ok=True)
    # Create configuration files
    mkfile(PATHS['cfg'], contents=toml.dumps(DEFAULTS))
    mkfile(PATHS['dl_log'], contents='')
    mkfile(PATHS['sync_list'], contents='[]')

except PermissionError as e:

    vprint(f'Failed to create configuration directories: ("{e}")', error_level='error')
    if running_on_android():
        vprint('You are using an Android device, make sure to use termux-setup-storage', error_level='error')
 
# Default config values
DEFAULTS = {
    'verbose': 1,
    'language': 'enUS',
    'update_languages': True,
    'simultaneous_urls': 3,
    'download': {
        'downloader': 'penguin',
        'downloads_per_url': 3,
        'series_directory': f'{DOWNLOAD_DEFAULT_BASE}{"Series/"}'.replace("\\", "/"),
        'movies_directory': f'{DOWNLOAD_DEFAULT_BASE}{"Movies/"}'.replace("\\", "/"),
        'series_format': '{W}/{S} ({y})',
        'season_format': 'Season {sn} - {i}',
        'episode_format': '{S} S{sn}E{en} - {E}',
        'movie_format': '{E} ({Y})',
        'video_extension': 'mkv',
        'resolution': 4320,
        'redownload': False,
    },
    'extractor': {},
    'flags': []
}

class ConfigError(Exception):
    pass

def create_config():
    with open(CONFIGURATION_FILE, 'w') as f:
        toml.dump(DEFAULTS, f)   
        
def load_config() -> dict:
    with open(CONFIGURATION_FILE, 'r') as f:
        return toml.load(f)

def save_config():
    if 'config' not in globals():
        raise Exception('Cannot save unloaded config')
    with open(CONFIGURATION_FILE, 'w') as f:
        toml.dump(config, f)
        
def reload_language():
    global lang, language
    lang = load_language(lang=language)

# Download base language if it does not exist
if not language_installed(lang='enUS'):
    download_languages(['enUS'])

try:
    # Load configuration from file
    config = load_config()
except TomlDecodeError as e:
    vprint('An error happenned while opening the configuration file', error_level='critical')
    # Make a copy of the current configuration file
    __failed_time = filename_datetime()
    os.rename(CONFIGURATION_FILE, f'{BASEDIR}config_{__failed_time}.toml.bak')
    vprint('A backup of the current config has been made', error_level='critical')
    # Create a exception traceback
    mkfile(f'{BASEDIR}traceback_{__failed_time}.log', traceback.format_exc())
    # Create the new configuration file
    mkfile(CONFIGURATION_FILE, contents=toml.dumps(DEFAULTS))
    vprint('A new configuration file has been created')
    # Load new configuration file
    config = load_config()

# Set verbosity level
if any(a in sys.argv for a in ('--mode', '-m')) and any(a in sys.argv for a in ('print', 'live_tv')):
    verbose_level = 0
elif any(a in sys.argv for a in ('-v', '--verbose')):
    __arg = '-v' if '-v' in sys.argv else '--verbose'
    verbose_level = int(sys.argv[sys.argv.index(__arg) + 1])
elif 'verbose' in config:
    verbose_level = int(config['verbose'])
else:
    verbose_level = 1
    
# Set language
language = sys.argv[sys.argv.index('--language') + 1] if '--language' in sys.argv else config['language']
lang = load_language(lang=language)

# Add new entries to file
config = recurse_merge_dict(DEFAULTS, config)
from polarity.extractor import EXTRACTORS
from polarity.downloader import DOWNLOADERS
for extractor in EXTRACTORS.values():
    extractor_name = extractor[0].lower()
    if extractor_name in config['extractor']:
        a = recurse_merge_dict(extractor[1].DEFAULTS, config['extractor'][extractor_name])
    else:
        a = extractor[1].DEFAULTS
    config['extractor'][extractor_name] = a
for downloader in DOWNLOADERS.items():
    downloader_name = downloader[0].lower()
    if downloader_name in config['download']:
        a = recurse_merge_dict(downloader[1].DEFAULTS, config['download'][downloader_name])
    else:
        a = downloader[1].DEFAULTS
    config['download'][downloader_name] = a
save_config()

options = deepcopy(config)
