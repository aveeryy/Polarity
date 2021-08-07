import os
from sys import platform

HOME = os.path.expanduser('~') if not 'ANDROID_ROOT' in os.environ else '/storage/emulated/0'

# Set common directories
BASEDIR = HOME + '/.Polarity/'
ACCOUNTS = BASEDIR + 'Accounts/'
BINARIES = BASEDIR + 'Binaries/'
LANGUAGES = BASEDIR + 'Languages/'
LOGS = BASEDIR + 'Logs/'
TEMP = BASEDIR + 'Temp/'

DOWNLOADS = HOME + '/Polarity Downloads/'

# Set common file paths
CONFIGURATION_FILE = BASEDIR + 'Polarity.toml'
DOWNLOAD_LOG = BASEDIR + 'AlreadyDownloaded.log'
SYNC_LIST = BASEDIR + 'SyncList.json'

# Add the binaries directory to PATH
if platform == 'win32':
	os.environ['PATH'] += ';' + BINARIES
else:
	os.environ['PATH'] += ':' + BINARIES