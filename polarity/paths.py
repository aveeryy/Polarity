import os
from shutil import which
from sys import platform
from polarity.utils import mkfile

if not 'ANDROID_ROOT' in os.environ:
	home = os.path.expanduser('~')
else:
	home = '/storage/emulated/0'

# Set common directories
user_dir = home + '/.Polarity/'
default_dl_dir = home + '/Downloads/Polarity/'
cookies_dir = user_dir + 'Accounts/'
binaries_dir = user_dir + 'Binaries/'
logs_dir = user_dir + 'Logs/'
debug_dir = user_dir + 'Debug/'
temp_dir= user_dir + 'Temp/'

# Set common file paths
config_file = user_dir + 'Polarity.toml'
sync_file = user_dir + 'SyncList.json'
dl_arch_file = user_dir + 'AlreadyDownloaded.log'

# Create non-existing directories
for dir in [user_dir, cookies_dir, default_dl_dir, temp_dir, logs_dir]:
	if not os.path.isdir(dir):
		try:
			os.makedirs(dir)
		except PermissionError:
			# Android
			if 'ANDROID_ROOT' in os.environ:
				raise PermissionError('You need to execute "termux-setup-storage" before using Polarity!')

# Create non-existing files
mkfile(sync_file, '{}')
mkfile(dl_arch_file, '')

# Add the binaries directory to PATH
if platform == 'win32':
	os.environ['PATH'] += ';' + binaries_dir
else:
	os.environ['PATH'] += ':' + binaries_dir

# ffmpeg checks
if not which('ffmpeg'):
    raise Exception('FFmpeg is not installed. Go to https://ffmpeg.org/download.html to download it')