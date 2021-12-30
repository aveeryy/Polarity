import os
import shutil
import sys

from requests import get
from time import sleep
from zipfile import ZipFile

from polarity.utils import vprint, humanbytes, request_webpage, request_json, version_to_tuple

__version__ = '2021.12.15'
GIT_REPO = 'https://github.com/aveeryy/Polarity.git'
UPDATE_ENDPOINT = 'https://api.github.com/repos/aveeryy/Polarity/releases'


def check_for_updates() -> tuple[bool, str]:
    '''Check if a new stable Polarity release has been uploaded'''
    releases = request_json(UPDATE_ENDPOINT)
    latest = releases[0][0]
    return (version_to_tuple(__version__) < version_to_tuple(
        latest['tag_name']), latest['tag_name'])


def selfupdate(mode: str = 'git', version: str = None, branch: str = 'main'):
    '''Update Polarity to the latest release / git commit using pip'''

    if sys.argv[0].endswith('.py'):
        # Update python package
        # Try to import pip
        import pip
        if mode == 'release':
            vprint('Downloading latest stable release using pip')
            command = ['install', '--upgrade', 'Polarity']
            if version is not None:
                # If version is specified append it to the command
                # It should result in the command being
                # ['install', '--upgrade', 'Polarity=={version}']
                command[-1] += f'=={version}'
        elif mode == 'git':
            vprint(f'~TEMP~ updating from git repo\'s branch {branch}')
            command = ['install', '--upgrade', f'git+{GIT_REPO}@{branch}']
        pip.main(command)
        os._exit(0)
    else:
        raise NotImplementedError('Updating native binaries is not supported ')


def language_install(language_list: list):
    '''Install specified language files'''
    LANGUAGE_URL = 'https://aveeryy.github.io/Polarity-Languages/%s.toml'

    failed = 0

    from polarity.config import paths

    for lang in language_list:

        response = request_webpage(url=LANGUAGE_URL % lang)
        if response.status_code == 404:
            vprint(f'Language "{lang}" not found in server', 4, 'update',
                   'warning')
            failed += 1
            continue
        vprint(f'Installing language {lang}', 4, 'update')
        with open(paths['lang'] + f'{lang}.toml', 'wb') as f:
            f.write(response.content)
        vprint(f'Language {lang} written to file', 4, 'update', 'debug')
    if failed:
        vprint('Language installer finished with warnings', 2, 'update',
               'warning')
    else:
        vprint('All languages installed successfully', 2, 'update')
    # After install reload the language strings
    from polarity.config import change_language, lang_code
    if lang_code not in ('internal', ''):
        change_language(lang_code)


def windows_install() -> None:
    'Perform installation of dependencies on Windows systems'

    LATEST = 'https://www.gyan.dev/ffmpeg/builds/release-version'
    FFMPEG = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'

    TESTING_TOGGLE = True

    from polarity.config import paths

    if sys.platform != 'win32' and not TESTING_TOGGLE:
        raise NotImplementedError('Unsupported OS')

    hb = humanbytes

    vprint('Downloading FFmpeg', module_name='update')
    download = get(FFMPEG, stream=True)
    total = int(download.headers["Content-Length"])
    downloaded = 0
    with open('ffmpeg.zip', 'wb') as output:
        for chunk in download.iter_content(chunk_size=1024):
            output.write(chunk)
            downloaded += len(chunk)
            vprint(f'{hb(downloaded)} / {hb(total)}    ',
                   end='\r',
                   module_name='update')
    vprint('Extracting FFmpeg', module_name='update')
    ZipFile('ffmpeg.zip', 'r').extractall(paths["tmp"])
    os.remove('ffmpeg.zip')
    # Get latest FFmpeg version string
    version = get(LATEST).text
    version_str = f'ffmpeg-{version}-essentials_build'
    # Move binaries to their respective folder
    os.rename(f'{paths["tmp"]}{version_str}/bin/ffmpeg.exe',
              f'{paths["bin"]}ffmpeg.exe')
    os.rename(f'{paths["tmp"]}{version_str}/bin/ffprobe.exe',
              f'{paths["bin"]}ffprobe.exe')
    vprint('Cleaning up', module_name='update')
    shutil.rmtree(f'{paths["tmp"]}{version_str}')
    vprint('Installation complete', module_name='update')
    vprint('Exiting installer in 2 seconds', module_name='update')
    sleep(2)
    os._exit(0)
