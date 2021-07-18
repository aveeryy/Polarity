from polarity.paths import config_file, default_dl_dir, user_dir
from polarity.utils import filename_datetime, recurse_merge_dict
import os
import toml

'''Filename format codes:
----------------------
Titles
----------------------
{S}: Series name
{s}: Season name
{E}: Episode name
----------------------
Numbers
----------------------
{sn}: Season number (01)
{en}: Episode number (01)
{Sn}: Season number (1)
{En}: Episode number (1)
{y}: Release year
----------------------
Meta
----------------------
{W} - Website
{i} - Identifier
'''

DEFAULTS = {
	'verbose': 1,
	'language': 'enUS',
	'download': {
		'downloader': 'penguin',
		'simultaneous_urls': 3,
		'simultaneous_downloads_per_url': 3,
		'series_directory': f'{default_dl_dir + "Series/"}'.replace("\\", "/"),
		'movies_directory': f'{default_dl_dir + "Movies/"}'.replace("\\", "/"),
		'series_format': '{W}/{S} ({y})',
		'season_format': 'Season {sn} - {i}',
		'episode_format': '{S} S{sn}E{en} - {E}',
		'movie_format': '{E} ({Y})',
		'video_extension': 'mkv',
		'resolution': 4320,
		'redownload': False,
	},
	'extractor': {},
}

def create_config():
	global config
	'Create a new config file and load it'
	with open (config_file, 'w') as c:
		c.write(toml.dumps(DEFAULTS))
	config = toml.load(config_file)

# Saves configuration
def save_config():
	with open(config_file, 'w') as c:
		toml.dump(config, c)

if not os.path.exists(config_file):
	create_config()
try:
	config = toml.load(config_file)
	# Add new entries if non-existing
	config = recurse_merge_dict(DEFAULTS, config)
	save_config()
except toml.decoder.TomlDecodeError as e:
	print('[config/error] Failed to open the configuration file, creating a new one...')
	with open(config_file, 'a') as file:
		file.write(f'\n# Corrupt config file!\n# Exception:\n# {e}')
	os.rename(config_file, f'{user_dir}/Polarity_{filename_datetime()}.toml.bak')
	create_config()
except (IOError, OSError):
	create_config()

class ConfigError(Exception):
	pass